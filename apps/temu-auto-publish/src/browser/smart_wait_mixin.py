"""
@PURPOSE: 统一的智能等待策略混入类,替代所有硬编码等待
@OUTLINE:
  - class SmartWaitMixin: 智能等待混入类
    - async def adaptive_wait(): 自适应等待
    - async def _wait_for_network_quiet(): 等待网络静止
    - async def _wait_for_dom_stable(): 等待DOM稳定
    - async def wait_for_element_stable(): 等待元素稳定
    - async def batch_wait(): 批量等待多个条件
@GOTCHAS:
  - 网络空闲检测可能在某些页面永远触发不到
  - DOM稳定检测依赖页面可执行JavaScript
@DEPENDENCIES:
  - 外部: playwright, loguru
  - 内部: page_waiter.py
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loguru import logger
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

if TYPE_CHECKING:
    from playwright.async_api import Locator, Page


@dataclass(slots=True)
class WaitMetrics:
    """等待操作的统计指标"""

    operation: str
    success_count: int = 0
    failure_count: int = 0
    total_wait_ms: float = 0.0
    avg_wait_ms: float = 0.0

    def record(self, wait_ms: float, success: bool) -> None:
        """记录一次等待操作"""
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.total_wait_ms += wait_ms
        total = self.success_count + self.failure_count
        if total > 0:
            self.avg_wait_ms = self.total_wait_ms / total


@dataclass(slots=True)
class AdaptiveWaitConfig:
    """自适应等待配置

    注意: 平衡模式 - 在保持响应速度的同时减少 CPU 负担

    性能优化调整:
    - min_wait_ms: 5 -> 10 (避免过于频繁的检测)
    - network_idle_timeout_ms: 50 -> 80 (减少超时误判)
    - dom_stable_timeout_ms: 50 -> 80 (减少超时误判)
    - dom_stable_interval_ms: 10 -> 15 (降低 CPU 负担)
    """

    min_wait_ms: int = 10  # 平衡: 最小等待稍微增加,减少空转
    max_wait_ms: int = 300  # 保持: 最大等待限制
    network_idle_timeout_ms: int = 80  # 平衡: 减少网络空闲超时误判
    dom_stable_timeout_ms: int = 80  # 平衡: 减少 DOM 稳定超时误判
    dom_stable_checks: int = 1  # 保持: 单次检查
    dom_stable_interval_ms: int = 15  # 平衡: 降低采样频率减少 CPU 负担
    # 学习因子:根据历史数据调整等待时间
    learning_factor: float = 0.2


class SmartWaitMixin:
    """统一的智能等待混入类,替代所有硬编码等待

    特点:
    1. 自适应等待 - 基于历史数据动态调整等待时间
    2. 多条件并行检测 - 网络空闲+DOM稳定同时检测
    3. 非阻塞式 - 超时不会阻塞后续操作
    4. 指标收集 - 记录等待效率用于持续优化

    Examples:
        >>> class MyController(SmartWaitMixin):
        ...     async def do_action(self, page):
        ...         await page.click("button")
        ...         await self.adaptive_wait(page, "click_button")
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._wait_config = AdaptiveWaitConfig()
        self._wait_metrics: dict[str, WaitMetrics] = {}
        self._wait_cache: dict[str, float] = {}  # operation -> 历史平均等待时间

    async def adaptive_wait(
        self,
        page: Page,
        operation: str,
        *,
        min_ms: int | None = None,
        max_ms: int | None = None,
        wait_for_network: bool = True,
        wait_for_dom: bool = True,
    ) -> float:
        """自适应等待 - 基于历史数据动态调整等待时间

        Args:
            page: Playwright Page 对象
            operation: 操作标识(用于统计和缓存)
            min_ms: 最小等待时间(毫秒)
            max_ms: 最大等待时间(毫秒)
            wait_for_network: 是否等待网络空闲
            wait_for_dom: 是否等待DOM稳定

        Returns:
            实际等待时间(毫秒)
        """
        min_wait = min_ms or self._wait_config.min_wait_ms
        max_wait = max_ms or self._wait_config.max_wait_ms

        # 获取历史平均等待时间作为参考
        cached_wait = self._wait_cache.get(operation, min_wait)
        target_timeout = int(min(max(cached_wait, min_wait), max_wait))

        start_time = time.perf_counter()
        success = True

        try:
            # 并行执行多种稳定性检测
            tasks: list[Awaitable[bool]] = []

            if wait_for_network:
                tasks.append(
                    self._wait_for_network_quiet(
                        page,
                        timeout_ms=min(target_timeout, self._wait_config.network_idle_timeout_ms),
                    )
                )

            if wait_for_dom:
                tasks.append(
                    self._wait_for_dom_stable(
                        page,
                        timeout_ms=min(target_timeout, self._wait_config.dom_stable_timeout_ms),
                    )
                )

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                success = all(r is True for r in results if not isinstance(r, Exception))
            else:
                # 如果没有任何检测条件,至少等待最小时间
                await asyncio.sleep(min_wait / 1000)

        except Exception as exc:
            logger.debug(f"自适应等待异常 ({operation}): {exc}")
            success = False

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # 确保至少等待最小时间
        if elapsed_ms < min_wait:
            remaining = (min_wait - elapsed_ms) / 1000
            await asyncio.sleep(remaining)
            elapsed_ms = min_wait

        # 更新统计和缓存
        self._update_wait_metrics(operation, elapsed_ms, success)

        return elapsed_ms

    async def _wait_for_network_quiet(self, page: Page, timeout_ms: int = 500) -> bool:
        """等待网络请求静止(非阻塞式)

        Args:
            page: Playwright Page 对象
            timeout_ms: 超时时间(毫秒)

        Returns:
            是否成功等待到网络空闲
        """
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
            return True
        except PlaywrightTimeoutError:
            # 超时不阻塞,继续执行
            logger.debug(f"网络空闲等待超时 ({timeout_ms}ms),继续执行")
            return False
        except Exception as exc:
            logger.debug(f"网络空闲等待异常: {exc}")
            return False

    async def _wait_for_dom_stable(
        self,
        page: Page,
        timeout_ms: int | None = None,
        checks: int | None = None,
        interval_ms: int | None = None,
    ) -> bool:
        """等待 DOM 在多次采样内保持稳定

        通过对比DOM快照来检测页面是否稳定,避免在动态加载过程中进行操作.

        Args:
            page: Playwright Page 对象
            timeout_ms: 总超时时间(毫秒)
            checks: 需要连续稳定的采样次数
            interval_ms: 采样间隔(毫秒)

        Returns:
            是否检测到DOM稳定
        """
        timeout = timeout_ms or self._wait_config.dom_stable_timeout_ms
        required_checks = checks or self._wait_config.dom_stable_checks
        poll_interval = interval_ms or self._wait_config.dom_stable_interval_ms

        deadline = time.monotonic() + timeout / 1000
        last_snapshot: tuple[int, int] | None = None
        stable_count = 0

        while time.monotonic() < deadline:
            try:
                snapshot = await self._capture_dom_snapshot(page)
            except Exception:
                # JavaScript执行失败,跳过本次采样
                await asyncio.sleep(poll_interval / 1000)
                continue

            if snapshot == last_snapshot:
                stable_count += 1
                if stable_count >= required_checks:
                    return True
            else:
                stable_count = 0
                last_snapshot = snapshot

            await asyncio.sleep(poll_interval / 1000)

        logger.debug(f"DOM稳定等待超时 ({timeout}ms)")
        return False

    async def _capture_dom_snapshot(self, page: Page) -> tuple[int, int]:
        """捕获页面 DOM 快照用于稳定性对比

        Returns:
            (文本长度, 节点数量) 元组
        """
        return await page.evaluate(
            """
            () => {
                const body = document.body;
                if (!body) {
                    return [0, 0];
                }
                const textLength = body.innerText ? body.innerText.length : 0;
                const nodeCount = body.querySelectorAll('*').length;
                return [textLength, nodeCount];
            }
            """
        )

    async def wait_for_element_stable(
        self,
        locator: Locator,
        *,
        timeout_ms: int = 1000,
        checks: int = 2,
        interval_ms: int = 100,
    ) -> bool:
        """等待特定元素稳定(位置和尺寸不变)

        Args:
            locator: Playwright Locator 对象
            timeout_ms: 超时时间(毫秒)
            checks: 连续稳定的检查次数
            interval_ms: 检查间隔(毫秒)

        Returns:
            元素是否稳定
        """
        deadline = time.monotonic() + timeout_ms / 1000
        last_box: dict[str, float] | None = None
        stable_count = 0

        while time.monotonic() < deadline:
            try:
                box = await locator.bounding_box()
                if box is None:
                    await asyncio.sleep(interval_ms / 1000)
                    continue

                if last_box is not None and self._boxes_equal(box, last_box):
                    stable_count += 1
                    if stable_count >= checks:
                        return True
                else:
                    stable_count = 0
                    last_box = box

            except Exception:
                stable_count = 0

            await asyncio.sleep(interval_ms / 1000)

        return False

    @staticmethod
    def _boxes_equal(
        box1: dict[str, float], box2: dict[str, float], tolerance: float = 1.0
    ) -> bool:
        """比较两个边界框是否相等(允许容差)"""
        for key in ("x", "y", "width", "height"):
            if abs(box1.get(key, 0) - box2.get(key, 0)) > tolerance:
                return False
        return True

    async def batch_wait(
        self,
        page: Page,
        conditions: list[Callable[[Page], Awaitable[bool]]],
        *,
        timeout_ms: int = 2000,
        require_all: bool = False,
    ) -> tuple[bool, list[bool]]:
        """批量等待多个条件

        Args:
            page: Playwright Page 对象
            conditions: 条件检查函数列表
            timeout_ms: 总超时时间(毫秒)
            require_all: 是否需要所有条件都满足

        Returns:
            (总体是否满足, 各条件结果列表)
        """

        async def check_condition(cond: Callable) -> bool:
            try:
                return await asyncio.wait_for(cond(page), timeout=timeout_ms / 1000)
            except TimeoutError:
                return False
            except Exception:
                return False

        results = await asyncio.gather(
            *[check_condition(c) for c in conditions], return_exceptions=True
        )

        bool_results = [r if isinstance(r, bool) else False for r in results]

        overall = all(bool_results) if require_all else any(bool_results)

        return overall, bool_results

    def _update_wait_metrics(self, operation: str, elapsed_ms: float, success: bool) -> None:
        """更新等待操作的统计指标

        Args:
            operation: 操作标识
            elapsed_ms: 实际等待时间(毫秒)
            success: 是否成功
        """
        if operation not in self._wait_metrics:
            self._wait_metrics[operation] = WaitMetrics(operation=operation)

        metrics = self._wait_metrics[operation]
        metrics.record(elapsed_ms, success)

        # 使用指数移动平均更新缓存
        old_avg = self._wait_cache.get(operation, elapsed_ms)
        factor = self._wait_config.learning_factor
        new_avg = old_avg * (1 - factor) + elapsed_ms * factor
        self._wait_cache[operation] = new_avg

    def get_wait_statistics(self) -> dict[str, Any]:
        """获取等待操作的统计数据

        Returns:
            统计数据字典
        """
        return {
            operation: {
                "success_count": m.success_count,
                "failure_count": m.failure_count,
                "avg_wait_ms": round(m.avg_wait_ms, 2),
                "total_wait_ms": round(m.total_wait_ms, 2),
            }
            for operation, m in self._wait_metrics.items()
        }

    def reset_wait_cache(self) -> None:
        """重置等待时间缓存(用于新场景)"""
        self._wait_cache.clear()
        self._wait_metrics.clear()


# 便捷函数:直接使用而无需继承
_global_wait_mixin: SmartWaitMixin | None = None


def get_smart_waiter() -> SmartWaitMixin:
    """获取全局智能等待实例"""
    global _global_wait_mixin
    if _global_wait_mixin is None:
        _global_wait_mixin = SmartWaitMixin()
    return _global_wait_mixin


async def smart_wait(
    page: Page,
    operation: str,
    *,
    min_ms: int = 30,
    max_ms: int = 2000,
    wait_for_network: bool = True,
    wait_for_dom: bool = True,
) -> float:
    """便捷函数:执行智能等待

    Args:
        page: Playwright Page 对象
        operation: 操作标识
        min_ms: 最小等待时间(毫秒)
        max_ms: 最大等待时间(毫秒)
        wait_for_network: 是否等待网络空闲
        wait_for_dom: 是否等待DOM稳定

    Returns:
        实际等待时间(毫秒)

    Examples:
        >>> await smart_wait(page, "click_submit", min_ms=100)
    """
    waiter = get_smart_waiter()
    return await waiter.adaptive_wait(
        page,
        operation,
        min_ms=min_ms,
        max_ms=max_ms,
        wait_for_network=wait_for_network,
        wait_for_dom=wait_for_dom,
    )
