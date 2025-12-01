"""
@PURPOSE: 并行竞速选择器工具 - 同时尝试多个选择器，返回第一个成功的结果.
@OUTLINE:
  - class SelectorTimeouts: 统一的超时配置常量
  - async def try_selectors_race(): 并行竞速尝试多个选择器
  - async def try_selector_single(): 尝试单个选择器
@GOTCHAS:
  - 使用 asyncio.as_completed 实现竞速，第一个成功立即返回
  - 所有任务完成或超时后自动清理
  - 集成选择器命中记录器
@DEPENDENCIES:
  - 内部: utils.selector_hit_recorder
  - 外部: playwright.async_api, asyncio
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from loguru import logger
from playwright.async_api import Locator, Page

from .selector_hit_recorder import record_selector_hit


@dataclass(frozen=True)
class SelectorTimeouts:
    """统一的选择器超时配置.

    可通过环境变量覆盖：
    - SELECTOR_TIMEOUT_FAST: 快速检测超时
    - SELECTOR_TIMEOUT_NORMAL: 默认超时
    - SELECTOR_TIMEOUT_SLOW: 慢速超时

    性能优化说明：
    - FAST: 3000ms -> 1500ms (50% 减少)
    - NORMAL: 5000ms -> 2000ms (60% 减少)
    - SLOW: 5000ms -> 2500ms (50% 减少)
    """

    FAST: int = int(os.environ.get("SELECTOR_TIMEOUT_FAST", str(min(300 * 5, 1500))))
    NORMAL: int = int(os.environ.get("SELECTOR_TIMEOUT_NORMAL", str(min(500 * 4, 2000))))
    SLOW: int = int(os.environ.get("SELECTOR_TIMEOUT_SLOW", str(min(1000 * 5, 2500))))


# 全局超时配置实例
TIMEOUTS = SelectorTimeouts()


async def _try_selector_single(
    page: Page,
    selector: str,
    timeout_ms: int,
    index: int,
) -> tuple[Locator | None, int, str]:
    """尝试单个选择器.

    Args:
        page: Playwright 页面对象.
        selector: CSS/XPath 选择器字符串.
        timeout_ms: 超时时间（毫秒）.
        index: 选择器在列表中的索引.

    Returns:
        三元组: (成功的 Locator 或 None, 索引, 选择器字符串)
    """
    try:
        locator = page.locator(selector)
        count = await locator.count()
        if count > 0:
            first = locator.first
            # 使用较短的超时检查可见性
            if await first.is_visible(timeout=timeout_ms):
                return (first, index, selector)
    except Exception:
        pass
    return (None, index, selector)


async def try_selectors_race(
    page: Page,
    selectors: list[str],
    timeout_ms: int = TIMEOUTS.NORMAL,
    context_name: str = "",
) -> Locator | None:
    """并行竞速尝试多个选择器，返回第一个成功的.

    Args:
        page: Playwright 页面对象.
        selectors: 选择器列表.
        timeout_ms: 每个选择器的超时时间（毫秒）.
        context_name: 业务上下文名称，用于记录命中.

    Returns:
        第一个成功匹配的 Locator，如果都失败则返回 None.

    Examples:
        >>> selectors = [
        ...     ".jx-overlay-dialog input.jx-input__inner",
        ...     "xpath=//label[contains(text(), '标题')]//input",
        ... ]
        >>> locator = await try_selectors_race(page, selectors, context_name="标题输入框")
    """
    if not selectors:
        return None

    # 创建所有选择器的任务
    tasks = [
        asyncio.create_task(
            _try_selector_single(page, sel, timeout_ms, idx),
            name=f"selector_{idx}",
        )
        for idx, sel in enumerate(selectors)
    ]

    result_locator: Locator | None = None
    winning_index: int = -1
    winning_selector: str = ""

    try:
        # 使用 as_completed 竞速，第一个成功的立即返回
        for coro in asyncio.as_completed(tasks):
            locator, index, selector = await coro
            if locator is not None:
                result_locator = locator
                winning_index = index
                winning_selector = selector
                break
    finally:
        # 取消所有未完成的任务
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    # 记录命中信息
    if result_locator is not None:
        record_selector_hit(
            selector=winning_selector,
            selector_list=selectors,
            index=winning_index,
            context=context_name,
        )
        if winning_index > 0:
            logger.debug(
                "[竞速] {} 命中索引 {} (可优化顺序)",
                context_name or "选择器",
                winning_index,
            )
    else:
        logger.debug(
            "[竞速] {} 全部 {} 个选择器均失败",
            context_name or "选择器",
            len(selectors),
        )

    return result_locator


async def try_selectors_race_with_elements(
    page: Page,
    selectors: list[str],
    timeout_ms: int = TIMEOUTS.NORMAL,
    context_name: str = "",
    nth: int = 0,
) -> Locator | None:
    """并行竞速尝试多个选择器，支持选择第 N 个元素.

    Args:
        page: Playwright 页面对象.
        selectors: 选择器列表.
        timeout_ms: 每个选择器的超时时间（毫秒）.
        context_name: 业务上下文名称.
        nth: 选择第几个元素（0-based）.

    Returns:
        第一个成功匹配的 Locator 的第 nth 个元素.
    """
    if not selectors:
        return None

    async def try_nth(selector: str, idx: int) -> tuple[Locator | None, int, str]:
        try:
            locator = page.locator(selector)
            count = await locator.count()
            if count > nth:
                element = locator.nth(nth)
                if await element.is_visible(timeout=timeout_ms):
                    return (element, idx, selector)
        except Exception:
            pass
        return (None, idx, selector)

    tasks = [
        asyncio.create_task(try_nth(sel, idx), name=f"selector_{idx}")
        for idx, sel in enumerate(selectors)
    ]

    result_locator: Locator | None = None
    winning_index: int = -1
    winning_selector: str = ""

    try:
        for coro in asyncio.as_completed(tasks):
            locator, index, selector = await coro
            if locator is not None:
                result_locator = locator
                winning_index = index
                winning_selector = selector
                break
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    if result_locator is not None:
        record_selector_hit(
            selector=winning_selector,
            selector_list=selectors,
            index=winning_index,
            context=context_name,
        )

    return result_locator


async def try_selectors_sequential(
    page: Page,
    selectors: list[str],
    timeout_ms: int = TIMEOUTS.FAST,
    context_name: str = "",
) -> Locator | None:
    """顺序尝试选择器（快速失败模式）.

    与竞速模式不同，这个函数按顺序尝试，但使用更短的超时时间。
    适用于选择器优先级明确的场景。

    Args:
        page: Playwright 页面对象.
        selectors: 选择器列表（按优先级排序）.
        timeout_ms: 每个选择器的超时时间.
        context_name: 业务上下文名称.

    Returns:
        第一个成功匹配的 Locator.
    """
    for index, selector in enumerate(selectors):
        try:
            locator = page.locator(selector)
            count = await locator.count()
            if count > 0:
                first = locator.first
                if await first.is_visible(timeout=timeout_ms):
                    record_selector_hit(selector, selectors, index, context_name)
                    return first
        except Exception:
            continue

    return None


# 导出
__all__ = [
    "SelectorTimeouts",
    "TIMEOUTS",
    "try_selectors_race",
    "try_selectors_race_with_elements",
    "try_selectors_sequential",
]
