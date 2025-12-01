"""
@PURPOSE: 提供统一的页面等待能力，减少硬编码等待时间并提升脚本效率
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
  - 网络空闲在内网站点可能无法自动触发，需要兜底等待
@DEPENDENCIES:
  - 外部: playwright, loguru
@RELATED: smart_locator.py, browser_manager.py
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from functools import wraps
from typing import Awaitable, Callable, Optional, ParamSpec, TypeVar

from loguru import logger
from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(slots=True)
class WaitStrategy:
    """等待策略配置。"""

    wait_after_action_ms: int = 300
    wait_for_stability_timeout_ms: int = 3750
    wait_for_network_idle_timeout_ms: int = 5000
    retry_initial_delay_ms: int = 300
    retry_backoff_factor: float = 1.6
    retry_max_delay_ms: int = 3750
    validation_timeout_ms: int = 5000
    dom_stable_checks: int = 3
    dom_stable_interval_ms: int = 300

    def next_retry_delay(self, attempt: int) -> float:
        """根据重试次数计算指数退避延迟（秒）。"""

        delay_ms = self.retry_initial_delay_ms * (self.retry_backoff_factor**attempt)
        delay_ms = min(delay_ms, self.retry_max_delay_ms)
        return max(delay_ms, 0) / 1000


def ensure_dom_ready(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    """页面入口装饰器：确保 DOMContentLoaded + DOM 稳定只等待一次。"""

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
    """可复用的页面等待工具。"""

    def __init__(self, page: Page, strategy: WaitStrategy | None = None):
        """初始化等待工具。

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
        """执行操作后等待页面稳定。"""

        if wait_for_network_idle:
            await self.wait_for_network_idle()

        if wait_for_dom_stable:
            await self.wait_for_dom_stable()

        if not wait_for_network_idle and not wait_for_dom_stable:
            await asyncio.sleep(self.strategy.wait_after_action_ms / 1000)

    async def wait_for_network_idle(self, timeout_ms: Optional[int] = None) -> None:
        """等待网络空闲。"""

        timeout = timeout_ms or self.strategy.wait_for_network_idle_timeout_ms

        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except PlaywrightTimeoutError:
            logger.debug("等待 networkidle 超时，继续执行后续逻辑")

    async def wait_for_dom_stable(
        self,
        timeout_ms: Optional[int] = None,
        checks: Optional[int] = None,
        interval_ms: Optional[int] = None,
    ) -> None:
        """等待 DOM 稳定或达成超时。"""

        timeout = timeout_ms or self.strategy.wait_for_stability_timeout_ms
        required_checks = checks or self.strategy.dom_stable_checks
        poll_interval = interval_ms or self.strategy.dom_stable_interval_ms

        deadline = time.monotonic() + timeout / 1000
        last_snapshot: tuple[int, int] | None = None
        stable_count = 0

        while time.monotonic() < deadline:
            snapshot = await self._capture_dom_snapshot()

            if snapshot == last_snapshot:
                stable_count += 1
                if stable_count >= required_checks:
                    return
            else:
                stable_count = 0
                last_snapshot = snapshot

            await asyncio.sleep(poll_interval / 1000)

        logger.debug("等待 DOM 稳定超时，继续后续流程。")

    async def apply_retry_backoff(self, attempt: int) -> None:
        """应用指数退避等待。"""

        delay = self.strategy.next_retry_delay(attempt)
        if delay > 0:
            logger.debug(f"指数退避等待 {delay:.3f}s")
            await asyncio.sleep(delay)

    async def wait_for_condition(
        self,
        condition: Callable[[Page], Awaitable[bool]],
        timeout_ms: Optional[int] = None,
        interval_ms: Optional[int] = None,
    ) -> bool:
        """等待自定义条件成立。"""

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
        timeout_ms: Optional[int] = None,
        ensure_visible: bool = True,
        ensure_enabled: bool = True,
        scroll: bool = True,
        force: bool = False,
        wait_after: bool = True,
        name: str | None = None,
    ) -> bool:
        """安全点击：可见/可用校验 + 可选滚动。"""

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
        timeout_ms: Optional[int] = None,
        ensure_visible: bool = True,
        click_first: bool = False,
        clear: bool = True,
        wait_after: bool = True,
        name: str | None = None,
    ) -> bool:
        """安全填充：可见校验 + 可选点击/保留原值。"""

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
        self, locator: Locator, timeout_ms: Optional[int] = None
    ) -> bool:
        """等待指定定位器隐藏。"""

        timeout = timeout_ms or self.strategy.validation_timeout_ms

        try:
            await locator.wait_for(state="hidden", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    async def _capture_dom_snapshot(self) -> tuple[int, int]:
        """采集页面 DOM 摘要。"""

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
