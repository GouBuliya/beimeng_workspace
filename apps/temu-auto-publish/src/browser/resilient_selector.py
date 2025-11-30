"""
@PURPOSE: 弹性选择器 - 自动降级策略，提高元素定位的稳定性
@OUTLINE:
  - @dataclass SelectorChain: 选择器链配置
  - @dataclass SelectorHitMetrics: 选择器命中统计
  - class ResilientLocator: 弹性定位器
    - async def locate(): 按优先级尝试定位元素
    - async def locate_all(): 定位所有匹配元素
    - async def click(): 定位并点击元素
    - async def fill(): 定位并填写元素
    - def register_chain(): 注册新的选择器链
    - def get_metrics(): 获取选择器命中统计
@GOTCHAS:
  - 选择器链应按从精确到宽泛排序
  - 过多的降级尝试会增加执行时间
  - 需要定期根据命中统计优化选择器顺序
@DEPENDENCIES:
  - 外部: playwright, loguru
  - 内部: smart_wait_mixin.py
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Awaitable

from loguru import logger
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page, Frame


@dataclass
class SelectorChain:
    """选择器链 - 按优先级依次尝试
    
    Attributes:
        key: 唯一标识符
        primary: 首选选择器
        fallbacks: 降级选择器列表
        description: 用于日志的描述
        wait_state: 等待元素的状态 (visible, attached, hidden)
        timeout_per_selector: 每个选择器的超时时间(毫秒)
    """
    
    key: str
    primary: str
    fallbacks: list[str] = field(default_factory=list)
    description: str = ""
    wait_state: str = "visible"
    timeout_per_selector: int = 2000
    
    @property
    def all_selectors(self) -> list[str]:
        """获取所有选择器（主选择器 + 降级选择器）"""
        return [self.primary] + self.fallbacks


@dataclass
class SelectorHitMetrics:
    """选择器命中统计
    
    用于分析哪些选择器最有效，指导选择器顺序优化。
    """
    
    chain_key: str
    hits: dict[int, int] = field(default_factory=lambda: defaultdict(int))
    misses: int = 0
    total_time_ms: float = 0.0
    
    def record_hit(self, selector_index: int, time_ms: float) -> None:
        """记录命中"""
        self.hits[selector_index] += 1
        self.total_time_ms += time_ms
    
    def record_miss(self, time_ms: float) -> None:
        """记录未命中"""
        self.misses += 1
        self.total_time_ms += time_ms
    
    @property
    def total_attempts(self) -> int:
        """总尝试次数"""
        return sum(self.hits.values()) + self.misses
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.total_attempts
        if total == 0:
            return 0.0
        return sum(self.hits.values()) / total
    
    @property
    def primary_hit_rate(self) -> float:
        """主选择器命中率"""
        total = self.total_attempts
        if total == 0:
            return 0.0
        return self.hits.get(0, 0) / total
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "chain_key": self.chain_key,
            "hits_by_index": dict(self.hits),
            "misses": self.misses,
            "total_attempts": self.total_attempts,
            "success_rate": round(self.success_rate, 3),
            "primary_hit_rate": round(self.primary_hit_rate, 3),
            "avg_time_ms": round(self.total_time_ms / max(self.total_attempts, 1), 2),
        }


class ResilientLocator:
    """弹性定位器 - 自动降级选择器
    
    特点:
    1. 按优先级尝试多个选择器
    2. 支持自定义选择器链
    3. 收集命中统计用于优化
    4. 智能超时分配
    
    Examples:
        >>> locator = ResilientLocator()
        >>> element = await locator.locate(page, "claim_button")
        >>> if element:
        ...     await element.click()
    """
    
    ALLOWED_WAIT_STATES = {"attached", "detached", "visible", "hidden"}
    MIN_TIMEOUT_PER_SELECTOR_MS = 120

    # 预定义的选择器链
    DEFAULT_CHAINS: dict[str, SelectorChain] = {
        # 认领相关
        "claim_button": SelectorChain(
            key="claim_button",
            primary="#jx-id-1917-80",
            fallbacks=[
                "button.jx-button.jx-button--primary:has-text('认领到')",
                "button:has-text('认领到')",
                "[role='button']:has-text('认领')",
                "xpath=//button[contains(normalize-space(), '认领')]",
            ],
            description="认领按钮",
        ),
        "claim_temu_option": SelectorChain(
            key="claim_temu_option",
            primary=".el-dropdown-menu__item:has-text('Temu全托管')",
            fallbacks=[
                ".jx-dropdown-menu__item:has-text('Temu全托管')",
                "span:has-text('Temu全托管')",
                "[role='menuitem']:has-text('Temu')",
            ],
            description="Temu全托管选项",
        ),
        "claim_confirm_button": SelectorChain(
            key="claim_confirm_button",
            primary=".el-dialog__footer button.el-button--primary",
            fallbacks=[
                "button:has-text('确定')",
                "button:has-text('确认')",
                "[role='button']:has-text('确定')",
            ],
            description="认领确认按钮",
        ),
        
        # 批量编辑相关
        "batch_edit_dialog": SelectorChain(
            key="batch_edit_dialog",
            primary=".jx-dialog[aria-label*='批量编辑']",
            fallbacks=[
                ".el-dialog:has-text('批量编辑')",
                "[role='dialog']:has-text('批量编辑')",
                ".el-dialog__wrapper:visible",
            ],
            description="批量编辑对话框",
        ),
        "batch_edit_button": SelectorChain(
            key="batch_edit_button",
            primary="button:has-text('批量编辑')",
            fallbacks=[
                ".jx-button:has-text('批量编辑')",
                "[role='button']:has-text('批量编辑')",
            ],
            description="批量编辑按钮",
        ),
        "preview_button": SelectorChain(
            key="preview_button",
            primary="button[role='button']:has-text('预览')",
            fallbacks=[
                "button:has-text('预览')",
                ".el-button:has-text('预览')",
            ],
            description="预览按钮",
        ),
        "save_button": SelectorChain(
            key="save_button",
            primary="button:has-text('保存修改')",
            fallbacks=[
                "button:has-text('保存')",
                ".el-button--primary:has-text('保存')",
            ],
            description="保存按钮",
        ),
        "close_button": SelectorChain(
            key="close_button",
            primary="button:has-text('关闭')",
            fallbacks=[
                ".el-dialog__headerbtn",
                "[aria-label='关闭']",
                ".el-icon-close",
            ],
            description="关闭按钮",
        ),
        
        # 表格/列表相关
        "product_row": SelectorChain(
            key="product_row",
            primary=".pro-virtual-table__row-body",
            fallbacks=[
                ".pro-virtual-scroll__row",
                "tr.el-table__row",
            ],
            description="商品行",
        ),
        "checkbox": SelectorChain(
            key="checkbox",
            primary=".jx-checkbox__input",
            fallbacks=[
                "input[type='checkbox']",
                ".el-checkbox__input",
                "[role='checkbox']",
            ],
            description="复选框",
        ),
        
        # 输入相关
        "title_input": SelectorChain(
            key="title_input",
            primary="textarea[placeholder*='标题']",
            fallbacks=[
                "input[placeholder*='标题']",
                ".jx-input__inner[placeholder*='标题']",
            ],
            description="标题输入框",
        ),
        "price_input": SelectorChain(
            key="price_input",
            primary="input[placeholder*='价格']",
            fallbacks=[
                ".jx-input__inner[type='number']",
                "[role='spinbutton']",
            ],
            description="价格输入框",
        ),
        
        # 下拉选择相关
        "select_dropdown": SelectorChain(
            key="select_dropdown",
            primary=".el-select-dropdown:visible",
            fallbacks=[
                ".jx-select-dropdown:visible",
                "[role='listbox']:visible",
            ],
            description="下拉菜单",
        ),
        "select_option": SelectorChain(
            key="select_option",
            primary=".el-select-dropdown__item",
            fallbacks=[
                ".jx-select-dropdown__item",
                "[role='option']",
            ],
            description="下拉选项",
        ),
    }
    
    def __init__(self):
        """初始化弹性定位器"""
        self._chains: dict[str, SelectorChain] = self.DEFAULT_CHAINS.copy()
        self._metrics: dict[str, SelectorHitMetrics] = {}
    
    @classmethod
    def _normalize_wait_state(cls, requested: str | None, default_state: str) -> str:
        """确保等待状态合法，非法值回退到可见状态."""
        candidate = requested or default_state
        if candidate in cls.ALLOWED_WAIT_STATES:
            return candidate
        logger.debug(f"非法 wait_state={candidate!r}，回退为 visible")
        return "visible"

    @classmethod
    def _compute_timeout_per_selector(cls, total_timeout: int, selector_count: int) -> int:
        """计算单个选择器的等待时间，避免过小导致瞬时超时."""
        if selector_count <= 0:
            return total_timeout
        per_selector = max(total_timeout // selector_count, 1)
        if per_selector < cls.MIN_TIMEOUT_PER_SELECTOR_MS:
            logger.debug(
                "分配给单个选择器的超时过低({}ms)，提升至安全下限 {}ms",
                per_selector,
                cls.MIN_TIMEOUT_PER_SELECTOR_MS,
            )
            per_selector = min(cls.MIN_TIMEOUT_PER_SELECTOR_MS, total_timeout)
        return per_selector

    @staticmethod
    def _is_target_closed(page: Page | Frame) -> bool:
        """检测 Page/Frame 是否已关闭或分离."""
        try:
            if hasattr(page, "is_closed") and callable(page.is_closed) and page.is_closed():
                return True
            if hasattr(page, "is_detached") and callable(page.is_detached) and page.is_detached():
                return True
        except Exception:
            return False
        return False

    @staticmethod
    def _build_text_option_locator(page: Page | Frame, option_text: str):
        """构建基于文本的下拉选项定位器."""
        safe_text = option_text.replace('"', '\\"').replace("'", "\\'")
        selector = f'.el-select-dropdown__item:has-text("{safe_text}")'
        return page.locator(selector).first

    @staticmethod
    def _log_failure_context(
        chain: SelectorChain, timeout_per: int, failures: list[str]
    ) -> None:
        """输出失败上下文，便于调试."""
        if not failures:
            logger.error(f"所有选择器均失败: {chain.description}")
            return
        failure_detail = "; ".join(failures[:5])
        logger.error(
            "所有选择器均失败: {} | 单项超时: {}ms | 尝试: {}",
            chain.description,
            timeout_per,
            failure_detail,
        )

    def register_chain(self, chain: SelectorChain) -> None:
        """注册新的选择器链
        
        Args:
            chain: 选择器链配置
        """
        self._chains[chain.key] = chain
        logger.debug(f"已注册选择器链: {chain.key}")
    
    def get_chain(self, key: str) -> SelectorChain | None:
        """获取选择器链
        
        Args:
            key: 选择器链的键
            
        Returns:
            选择器链，不存在则返回 None
        """
        return self._chains.get(key)
    
    async def locate(
        self,
        page: Page | Frame,
        key: str,
        *,
        timeout: int | None = None,
        wait_state: str | None = None,
    ) -> Locator | None:
        """按优先级尝试定位元素
        
        Args:
            page: Playwright Page 或 Frame 对象
            key: 选择器链的键
            timeout: 总超时时间(毫秒)，默认使用链配置
            wait_state: 等待状态，默认使用链配置
            
        Returns:
            定位到的元素，失败则返回 None
        """
        chain = self._chains.get(key)
        if chain is None:
            logger.error(f"未知的选择器键: {key}")
            return None
        
        effective_timeout = timeout or (chain.timeout_per_selector * len(chain.all_selectors))
        effective_state = self._normalize_wait_state(wait_state, chain.wait_state)
        timeout_per = self._compute_timeout_per_selector(
            effective_timeout, len(chain.all_selectors)
        )
    
        start_time = time.perf_counter()
        
        # 初始化或获取指标
        if key not in self._metrics:
            self._metrics[key] = SelectorHitMetrics(chain_key=key)
        metrics = self._metrics[key]
        if self._is_target_closed(page):
            logger.error("页面已关闭/分离，无法定位 {}", chain.description)
            return None
        failures: list[str] = []
        
        for idx, selector in enumerate(chain.all_selectors):
            try:
                locator = page.locator(selector)
                await locator.wait_for(state=effective_state, timeout=timeout_per)
                
                elapsed_ms = (time.perf_counter() - start_time) * 1000
                metrics.record_hit(idx, elapsed_ms)
                
                if idx > 0:
                    logger.warning(
                        f"使用降级选择器[{idx}] 定位 {chain.description}: {selector}"
                    )
                else:
                    logger.debug(f"定位成功 {chain.description}: {selector}")
                
                return locator
                
            except PlaywrightTimeoutError:
                failures.append(f"#{idx} timeout {selector}")
                logger.debug(f"选择器超时 [{idx}] {chain.description}: {selector}")
                continue
            except Exception as exc:
                failures.append(f"#{idx} {type(exc).__name__}: {exc}")
                logger.debug(f"选择器异常 [{idx}] {chain.description}: {exc}")
                continue
        
        # 所有选择器都失败
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metrics.record_miss(elapsed_ms)
        self._log_failure_context(chain, timeout_per, failures)
        
        return None
    
    async def locate_with_selector(
        self,
        page: Page | Frame,
        selector: str,
        *,
        timeout: int = 5000,
        wait_state: str = "visible",
        description: str = "",
    ) -> Locator | None:
        """使用单个选择器定位元素
        
        用于不在预定义链中的临时选择器。
        
        Args:
            page: Playwright Page 或 Frame 对象
            selector: CSS 选择器
            timeout: 超时时间(毫秒)
            wait_state: 等待状态
            description: 描述（用于日志）
            
        Returns:
            定位到的元素，失败则返回 None
        """
        try:
            locator = page.locator(selector)
            await locator.wait_for(state=wait_state, timeout=timeout)
            logger.debug(f"定位成功 {description or selector}")
            return locator
        except PlaywrightTimeoutError:
            logger.warning(f"定位超时 {description or selector}")
            return None
        except Exception as exc:
            logger.warning(f"定位异常 {description or selector}: {exc}")
            return None
    
    async def locate_all(
        self,
        page: Page | Frame,
        key: str,
        *,
        timeout: int | None = None,
    ) -> list[Locator]:
        """定位所有匹配的元素
        
        Args:
            page: Playwright Page 或 Frame 对象
            key: 选择器链的键
            timeout: 超时时间(毫秒)
            
        Returns:
            匹配的元素列表
        """
        chain = self._chains.get(key)
        if chain is None:
            logger.error(f"未知的选择器键: {key}")
            return []
        
        effective_timeout = timeout or chain.timeout_per_selector
        timeout_per = self._compute_timeout_per_selector(
            effective_timeout, len(chain.all_selectors)
        )
        failures: list[str] = []
        if self._is_target_closed(page):
            logger.error("页面已关闭/分离，无法批量定位 {}", chain.description)
            return []
        
        for selector in chain.all_selectors:
            try:
                locator = page.locator(selector)
                # 等待至少一个元素
                await locator.first.wait_for(state="attached", timeout=timeout_per)
                
                count = await locator.count()
                if count > 0:
                    logger.debug(f"定位到 {count} 个 {chain.description}")
                    return [locator.nth(i) for i in range(count)]
                    
            except PlaywrightTimeoutError:
                failures.append(f"timeout {selector}")
                continue
            except Exception:
                failures.append(f"exception {selector}")
                continue
        
        logger.warning(f"未定位到任何 {chain.description} | 尝试: {'; '.join(failures[:5])}")
        return []
    
    async def click(
        self,
        page: Page | Frame,
        key: str,
        *,
        timeout: int | None = None,
        force: bool = False,
    ) -> bool:
        """定位并点击元素
        
        Args:
            page: Playwright Page 或 Frame 对象
            key: 选择器链的键
            timeout: 超时时间(毫秒)
            force: 是否强制点击
            
        Returns:
            是否成功点击
        """
        locator = await self.locate(page, key, timeout=timeout)
        if locator is None:
            return False
        
        try:
            await locator.click(force=force)
            return True
        except Exception as exc:
            logger.error(f"点击失败 {key}: {exc}")
            return False
    
    async def fill(
        self,
        page: Page | Frame,
        key: str,
        value: str,
        *,
        timeout: int | None = None,
        clear_first: bool = True,
    ) -> bool:
        """定位并填写元素
        
        Args:
            page: Playwright Page 或 Frame 对象
            key: 选择器链的键
            value: 要填写的值
            timeout: 超时时间(毫秒)
            clear_first: 是否先清空
            
        Returns:
            是否成功填写
        """
        locator = await self.locate(page, key, timeout=timeout)
        if locator is None:
            return False
        
        try:
            if clear_first:
                await locator.clear()
            await locator.fill(value)
            return True
        except Exception as exc:
            logger.error(f"填写失败 {key}: {exc}")
            return False
    
    async def select_option(
        self,
        page: Page | Frame,
        key: str,
        option_text: str,
        *,
        timeout: int | None = None,
        option_chain_key: str | None = "select_option",
    ) -> bool:
        """定位下拉框并选择选项
        
        Args:
            page: Playwright Page 或 Frame 对象
            key: 选择器链的键
            option_text: 选项文本
            timeout: 超时时间(毫秒)
            option_chain_key: 选项列表的选择器链键，None 时仅使用文本匹配
            
        Returns:
            是否成功选择
        """
        if self._is_target_closed(page):
            logger.error("页面已关闭/分离，无法选择选项 {}", option_text)
            return False

        option_timeout = timeout or 3000
        # 先定位并点击下拉框
        dropdown = await self.locate(page, key, timeout=timeout)
        if dropdown is None:
            return False
        
        try:
            await dropdown.click()
            
            # 等待下拉菜单出现
            dropdown_container = await self.locate(
                page, "select_dropdown", timeout=option_timeout, wait_state="visible"
            )
            if dropdown_container is None:
                await asyncio.sleep(0.2)
            
            # 定位并点击选项
            option_locator = None
            if option_chain_key:
                option_locator = await self.locate(
                    page, option_chain_key, timeout=option_timeout, wait_state="visible"
                )
            
            if option_locator is None:
                option_locator = self._build_text_option_locator(page, option_text)
                await option_locator.wait_for(state="visible", timeout=option_timeout)
            
            await option_locator.click()
            
            return True
        except Exception as exc:
            logger.error(f"选择选项失败 {key} -> {option_text}: {exc}")
            return False
    
    def get_metrics(self, key: str | None = None) -> dict[str, Any]:
        """获取选择器命中统计
        
        Args:
            key: 选择器链的键，为空则返回所有统计
            
        Returns:
            统计数据字典
        """
        if key:
            metrics = self._metrics.get(key)
            return metrics.to_dict() if metrics else {}
        
        return {k: m.to_dict() for k, m in self._metrics.items()}
    
    def reset_metrics(self) -> None:
        """重置所有统计数据"""
        self._metrics.clear()
    
    def suggest_optimizations(self) -> list[dict[str, Any]]:
        """根据统计数据建议选择器优化
        
        Returns:
            优化建议列表
        """
        suggestions = []
        
        for key, metrics in self._metrics.items():
            if metrics.total_attempts < 10:
                continue  # 样本太少
            
            # 主选择器命中率低
            if metrics.primary_hit_rate < 0.5:
                # 找到命中最多的索引
                best_idx = max(metrics.hits.keys(), key=lambda i: metrics.hits[i], default=0)
                if best_idx > 0:
                    chain = self._chains.get(key)
                    if chain:
                        suggestions.append({
                            "key": key,
                            "type": "reorder",
                            "message": f"建议将选择器[{best_idx}]提升为主选择器",
                            "current_primary": chain.primary,
                            "suggested_primary": chain.all_selectors[best_idx] if best_idx < len(chain.all_selectors) else None,
                            "primary_hit_rate": metrics.primary_hit_rate,
                        })
            
            # 成功率低
            if metrics.success_rate < 0.8:
                suggestions.append({
                    "key": key,
                    "type": "add_selectors",
                    "message": f"成功率仅 {metrics.success_rate:.1%}，建议添加更多降级选择器",
                    "success_rate": metrics.success_rate,
                    "misses": metrics.misses,
                })
        
        return suggestions


# 全局实例
_global_locator: ResilientLocator | None = None


def get_resilient_locator() -> ResilientLocator:
    """获取全局弹性定位器实例"""
    global _global_locator
    if _global_locator is None:
        _global_locator = ResilientLocator()
    return _global_locator


# 便捷函数
async def resilient_locate(
    page: Page | Frame,
    key: str,
    **kwargs,
) -> Locator | None:
    """便捷函数：弹性定位元素
    
    Args:
        page: Playwright Page 或 Frame 对象
        key: 选择器链的键
        **kwargs: 传递给 locate 的其他参数
        
    Returns:
        定位到的元素
    """
    return await get_resilient_locator().locate(page, key, **kwargs)


async def resilient_click(
    page: Page | Frame,
    key: str,
    **kwargs,
) -> bool:
    """便捷函数：弹性定位并点击
    
    Args:
        page: Playwright Page 或 Frame 对象
        key: 选择器链的键
        **kwargs: 传递给 click 的其他参数
        
    Returns:
        是否成功点击
    """
    return await get_resilient_locator().click(page, key, **kwargs)


# 导出
__all__ = [
    "SelectorChain",
    "SelectorHitMetrics",
    "ResilientLocator",
    "get_resilient_locator",
    "resilient_locate",
    "resilient_click",
]


