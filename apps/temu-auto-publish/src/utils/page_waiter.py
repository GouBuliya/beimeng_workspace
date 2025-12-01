"""
@PURPOSE: 提供统一的页面等待能力,减少硬编码等待时间并提升脚本效率
@OUTLINE:
  - def ensure_dom_ready(): 为页面入口方法提供 DOM 初始化等待的装饰器
  - @dataclass WaitStrategy: 存放等待策略
  - class PageWaiter: 封装可复用的等待工具
    - async def post_action_wait(): 操作后的统一等待
    - async def wait_for_network_idle(): 等待网络空闲
    - async def wait_for_dom_stable(): 等待DOM稳定
    - async def apply_retry_backoff(): 应用指数退避
    - async def wait_for_condition(): 通用条件等待
    - async def safe_click(): 确保可见可用的安全点击
    - async def safe_fill(): 确保可见的安全填充
@GOTCHAS:
  - DOM稳定检测依赖页面执行JavaScript
  - 网络空闲在内网站点可能无法自动触发,需要兜底等待
@DEPENDENCIES:
  - 外部: playwright, loguru
@RELATED: smart_locator.py, browser_manager.py
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import wraps
from typing import ParamSpec, TypeVar

from loguru import logger
from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(slots=True)
class WaitStrategy:
    """等待策略配置.

    性能优化说明:
    - 原默认参数较为保守,最小等待 900ms (3次检测 × 300ms间隔)
    - 优化后参数平衡稳定性和性能,最小等待 300ms (2次检测 × 150ms间隔)
    - 可通过 conservative()/balanced()/aggressive() 工厂方法选择预设模式
    """

    wait_after_action_ms: int = 100  # 优化: 300 → 100
    wait_for_stability_timeout_ms: int = 2000  # 优化: 3750 → 2000
    wait_for_network_idle_timeout_ms: int = 3000  # 优化: 5000 → 3000
    retry_initial_delay_ms: int = 200  # 优化: 300 → 200
    retry_backoff_factor: float = 1.5  # 优化: 1.6 → 1.5
    retry_max_delay_ms: int = 2000  # 优化: 3750 → 2000
    validation_timeout_ms: int = 3000  # 优化: 5000 → 3000
    dom_stable_checks: int = 2  # 优化: 3 → 2
    dom_stable_interval_ms: int = 150  # 优化: 300 → 150
    # 新增: 快速检测间隔 (用于初始快速检测)
    quick_check_interval_ms: int = 50

    @classmethod
    def conservative(cls) -> WaitStrategy:
        """保守模式 - 更长的等待时间,适合不稳定的网络环境."""
        return cls(
            wait_after_action_ms=300,
            wait_for_stability_timeout_ms=3750,
            wait_for_network_idle_timeout_ms=5000,
            retry_initial_delay_ms=300,
            retry_backoff_factor=1.6,
            retry_max_delay_ms=3750,
            validation_timeout_ms=5000,
            dom_stable_checks=3,
            dom_stable_interval_ms=300,
            quick_check_interval_ms=100,
        )

    @classmethod
    def balanced(cls) -> WaitStrategy:
        """平衡模式 - 默认配置,平衡稳定性和性能."""
        return cls()  # 使用默认值

    @classmethod
    def aggressive(cls) -> WaitStrategy:
        """激进模式 - 更短的等待时间,适合稳定的网络环境."""
        return cls(
            wait_after_action_ms=50,
            wait_for_stability_timeout_ms=1000,
            wait_for_network_idle_timeout_ms=1500,
            retry_initial_delay_ms=100,
            retry_backoff_factor=1.3,
            retry_max_delay_ms=1000,
            validation_timeout_ms=2000,
            dom_stable_checks=1,
            dom_stable_interval_ms=80,
            quick_check_interval_ms=30,
        )

    def next_retry_delay(self, attempt: int) -> float:
        """根据重试次数计算指数退避延迟(秒)."""

        delay_ms = self.retry_initial_delay_ms * (self.retry_backoff_factor**attempt)
        delay_ms = min(delay_ms, self.retry_max_delay_ms)
        return max(delay_ms, 0) / 1000


def ensure_dom_ready[**P, R](func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """页面入口装饰器:确保 DOMContentLoaded + DOM 稳定只等待一次."""

    @wraps(func)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        page: Page | None = kwargs.get("page")

        if page is None and len(args) >= 2:
            candidate = args[1]
            if isinstance(candidate, Page):
                page = candidate

        if page is None:
            return await func(*args, **kwargs)

        guard_attr = "_bemg_dom_ready_guard"
        guard_active = getattr(page, guard_attr, False)

        if not guard_active:
            setattr(page, guard_attr, True)
            waiter = PageWaiter(page)
            try:
                await page.wait_for_load_state("domcontentloaded")
                await waiter.wait_for_dom_stable(
                    timeout_ms=waiter.strategy.wait_for_stability_timeout_ms
                )
                return await func(*args, **kwargs)
            finally:
                setattr(page, guard_attr, False)

        return await func(*args, **kwargs)

    return wrapper


class PageWaiter:
    """可复用的页面等待工具."""

    def __init__(self, page: Page, strategy: WaitStrategy | None = None):
        """初始化等待工具.

        Args:
            page: Playwright Page 对象
            strategy: 等待策略配置
        """
        self.page = page
        self.strategy = strategy or WaitStrategy()

    async def post_action_wait(
        self,
        *,
        wait_for_network_idle: bool = True,
        wait_for_dom_stable: bool = True,
    ) -> None:
        """执行操作后等待页面稳定."""

        if wait_for_network_idle:
            await self.wait_for_network_idle()

        if wait_for_dom_stable:
            await self.wait_for_dom_stable()

        if not wait_for_network_idle and not wait_for_dom_stable:
            await asyncio.sleep(self.strategy.wait_after_action_ms / 1000)

    async def wait_for_network_idle(self, timeout_ms: int | None = None) -> None:
        """等待网络空闲."""

        timeout = timeout_ms or self.strategy.wait_for_network_idle_timeout_ms

        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except PlaywrightTimeoutError:
            logger.debug("等待 networkidle 超时,继续执行后续逻辑")

    async def wait_for_dom_stable(
        self,
        timeout_ms: int | None = None,
        checks: int | None = None,
        interval_ms: int | None = None,
        enable_quick_check: bool = True,
    ) -> bool:
        """等待 DOM 稳定或达成超时.

        性能优化: 添加快速检测机制,如果页面在短时间内已稳定则提前返回.

        Args:
            timeout_ms: 超时时间(毫秒)
            checks: 需要连续稳定的采样次数
            interval_ms: 采样间隔(毫秒)
            enable_quick_check: 是否启用快速检测(默认启用)

        Returns:
            True 表示检测到稳定,False 表示超时
        """
        timeout = timeout_ms or self.strategy.wait_for_stability_timeout_ms
        required_checks = checks or self.strategy.dom_stable_checks
        poll_interval = interval_ms or self.strategy.dom_stable_interval_ms
        quick_interval = self.strategy.quick_check_interval_ms

        # 快速检测: 先用短间隔检测一次,如果已稳定则立即返回
        if enable_quick_check:
            try:
                first_snapshot = await self._capture_dom_snapshot()
                await asyncio.sleep(quick_interval / 1000)
                second_snapshot = await self._capture_dom_snapshot()

                if first_snapshot == second_snapshot:
                    # 页面已稳定,无需继续等待
                    logger.debug("DOM 快速检测通过,页面已稳定")
                    return True
            except Exception as exc:
                logger.debug(f"快速检测失败: {exc},继续标准检测")

        # 标准检测流程
        deadline = time.monotonic() + timeout / 1000
        last_snapshot: tuple[int, int] | None = None
        stable_count = 0

        while time.monotonic() < deadline:
            try:
                snapshot = await self._capture_dom_snapshot()
            except Exception as exc:
                logger.debug(f"DOM 快照捕获失败: {exc}")
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

        logger.debug("等待 DOM 稳定超时,继续后续流程.")
        return False

    async def apply_retry_backoff(self, attempt: int) -> None:
        """应用指数退避等待."""

        delay = self.strategy.next_retry_delay(attempt)
        if delay > 0:
            logger.debug(f"指数退避等待 {delay:.3f}s")
            await asyncio.sleep(delay)

    async def wait_for_condition(
        self,
        condition: Callable[[Page], Awaitable[bool]],
        timeout_ms: int | None = None,
        interval_ms: int | None = None,
    ) -> bool:
        """等待自定义条件成立."""

        timeout = timeout_ms or self.strategy.wait_for_stability_timeout_ms
        poll_interval = interval_ms or self.strategy.dom_stable_interval_ms

        deadline = time.monotonic() + timeout / 1000

        while time.monotonic() < deadline:
            try:
                if await condition(self.page):
                    return True
            except Exception as exc:
                logger.debug(f"条件检查失败: {exc}")

            await asyncio.sleep(poll_interval / 1000)

        return False

    async def safe_click(
        self,
        locator: Locator | None,
        *,
        timeout_ms: int | None = None,
        ensure_visible: bool = True,
        ensure_enabled: bool = True,
        scroll: bool = True,
        force: bool = False,
        wait_after: bool = True,
        quick_wait: bool = False,
        name: str | None = None,
    ) -> bool:
        """安全点击:可见/可用校验 + 可选滚动.

        Args:
            locator: 目标元素定位器
            timeout_ms: 超时时间(毫秒)
            ensure_visible: 是否确保元素可见
            ensure_enabled: 是否确保元素可用
            scroll: 是否滚动到元素位置
            force: 是否强制点击
            wait_after: 是否在点击后等待
            quick_wait: 快速等待模式(仅等待50ms,用于连续操作)
            name: 元素名称(用于日志)

        Returns:
            点击是否成功
        """
        if locator is None:
            return False

        target = locator.first
        effective_timeout = timeout_ms or self.strategy.validation_timeout_ms
        label = name or ""

        try:
            if ensure_visible:
                await target.wait_for(state="visible", timeout=effective_timeout)
            if ensure_enabled:
                try:
                    if not await target.is_enabled():
                        logger.debug(f"safe_click: 元素未启用 name={label}")
                        return False
                except Exception as exc:
                    logger.debug(f"safe_click: 检查启用失败 name={label} err={exc}")

            if scroll:
                try:
                    await target.scroll_into_view_if_needed(timeout=effective_timeout)
                except Exception as exc:
                    logger.debug(f"safe_click: 滚动失败 name={label} err={exc}")

            await target.click(timeout=effective_timeout, force=force)

            if wait_after:
                if quick_wait:
                    # 快速等待模式:仅短暂等待,用于连续操作
                    await asyncio.sleep(self.strategy.quick_check_interval_ms / 1000)
                else:
                    await self.post_action_wait(
                        wait_for_network_idle=False,
                        wait_for_dom_stable=True,
                    )

            return True
        except PlaywrightTimeoutError:
            return False
        except Exception as exc:
            logger.debug(f"safe_click: 点击异常 name={label} err={exc}")
            return False

    async def safe_fill(
        self,
        locator: Locator | None,
        value: str,
        *,
        timeout_ms: int | None = None,
        ensure_visible: bool = True,
        click_first: bool = False,
        clear: bool = True,
        wait_after: bool = True,
        quick_wait: bool = False,
        name: str | None = None,
    ) -> bool:
        """安全填充:可见校验 + 可选点击/保留原值.

        Args:
            locator: 目标元素定位器
            value: 要填充的值
            timeout_ms: 超时时间(毫秒)
            ensure_visible: 是否确保元素可见
            click_first: 是否先点击元素
            clear: 是否清除原有内容(True=fill, False=type)
            wait_after: 是否在填充后等待
            quick_wait: 快速等待模式(仅等待50ms,用于连续操作)
            name: 元素名称(用于日志)

        Returns:
            填充是否成功
        """
        if locator is None:
            return False

        target = locator.first
        effective_timeout = timeout_ms or self.strategy.validation_timeout_ms
        label = name or ""

        try:
            if ensure_visible:
                await target.wait_for(state="visible", timeout=effective_timeout)

            if click_first:
                try:
                    await target.click(timeout=effective_timeout)
                except Exception as exc:
                    logger.debug(f"safe_fill: 预点击失败 name={label} err={exc}")

            if clear:
                await target.fill(value, timeout=effective_timeout)
            else:
                await target.type(value, timeout=effective_timeout)

            if wait_after:
                if quick_wait:
                    # 快速等待模式:仅短暂等待,用于连续操作
                    await asyncio.sleep(self.strategy.quick_check_interval_ms / 1000)
                else:
                    await self.post_action_wait(
                        wait_for_network_idle=False,
                        wait_for_dom_stable=True,
                    )

            return True
        except PlaywrightTimeoutError:
            return False
        except Exception as exc:
            logger.debug(f"safe_fill: 填充异常 name={label} err={exc}")
            return False

    async def wait_for_locator_hidden(
        self, locator: Locator, timeout_ms: int | None = None
    ) -> bool:
        """等待指定定位器隐藏."""

        timeout = timeout_ms or self.strategy.validation_timeout_ms

        try:
            await locator.wait_for(state="hidden", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    async def _capture_dom_snapshot(self) -> tuple[int, int]:
        """采集页面 DOM 摘要."""

        return await self.page.evaluate(
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
