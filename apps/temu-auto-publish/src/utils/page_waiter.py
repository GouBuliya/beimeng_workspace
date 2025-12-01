"""
@PURPOSE: 提供统一的页面等待策略，减少硬编码等待时间并提高脚本效率
@OUTLINE:
  - @dataclass WaitStrategy: 定义等待参数
  - class PageWaiter: 基于策略的等待工具
    - async def post_action_wait(): 操作后的统一等待
    - async def wait_for_network_idle(): 等待网络空闲
    - async def wait_for_dom_stable(): 等待DOM稳定
    - async def apply_retry_backoff(): 应用指数退避
    - async def wait_for_condition(): 通用条件等待
@GOTCHAS:
  - DOM稳定检测依赖页面可执行JavaScript
  - 网络空闲在部分站点可能永远触发不到，需要捕获超时
@DEPENDENCIES:
  - 外部: playwright, loguru
@RELATED: smart_locator.py, browser_manager.py
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from loguru import logger
from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError


@dataclass(slots=True)
class WaitStrategy:
    """等待策略配置."""

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
        """根据重试次数计算指数退避延迟（秒）."""

        delay_ms = self.retry_initial_delay_ms * (self.retry_backoff_factor**attempt)
        delay_ms = min(delay_ms, self.retry_max_delay_ms)
        return max(delay_ms, 0) / 1000


class PageWaiter:
    """基于策略的页面等待工具."""

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

    async def wait_for_network_idle(self, timeout_ms: Optional[int] = None) -> None:
        """等待网络空闲."""

        timeout = timeout_ms or self.strategy.wait_for_network_idle_timeout_ms

        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except PlaywrightTimeoutError:
            logger.debug("等待 networkidle 超时，继续执行后续逻辑。")

    async def wait_for_dom_stable(
        self,
        timeout_ms: Optional[int] = None,
        checks: Optional[int] = None,
        interval_ms: Optional[int] = None,
    ) -> None:
        """等待 DOM 在多次采样内保持稳定."""

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
        """应用指数退避等待."""

        delay = self.strategy.next_retry_delay(attempt)
        if delay > 0:
            logger.debug(f"重试退避等待 {delay:.3f}s")
            await asyncio.sleep(delay)

    async def wait_for_condition(
        self,
        condition: Callable[[Page], Awaitable[bool]],
        timeout_ms: Optional[int] = None,
        interval_ms: Optional[int] = None,
    ) -> bool:
        """等待自定义条件满足."""

        timeout = timeout_ms or self.strategy.wait_for_stability_timeout_ms
        poll_interval = interval_ms or self.strategy.dom_stable_interval_ms

        deadline = time.monotonic() + timeout / 1000

        while time.monotonic() < deadline:
            try:
                if await condition(self.page):
                    return True
            except Exception as exc:
                logger.debug(f"条件检测失败: {exc}")

            await asyncio.sleep(poll_interval / 1000)

        return False

    async def wait_for_locator_hidden(
        self, locator: Locator, timeout_ms: Optional[int] = None
    ) -> bool:
        """等待指定定位器隐藏."""

        timeout = timeout_ms or self.strategy.validation_timeout_ms

        try:
            await locator.wait_for(state="hidden", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            return False

    async def _capture_dom_snapshot(self) -> tuple[int, int]:
        """捕获页面 DOM 快照."""

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
