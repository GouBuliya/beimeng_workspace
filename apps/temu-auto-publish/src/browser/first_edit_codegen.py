"""
@PURPOSE: 提供基于 Playwright Codegen 的简化首次编辑辅助方法
@OUTLINE:
  - async def close_known_popups(page): 关闭妙手常见弹窗
  - async def open_edit_dialog_codegen(page, index): 打开指定索引商品的编辑弹窗
@GOTCHAS:
  - 依赖页面结构, 可能因 UI 更新需要调整选择器
@DEPENDENCIES:
  - 外部: playwright.async_api
  - 内部: 无
"""

from __future__ import annotations

from collections.abc import Iterable

from loguru import logger
from playwright.async_api import Locator, Page, TimeoutError


async def close_known_popups(page: Page, selectors: Iterable[str] | None = None) -> None:
    """关闭妙手 ERP 页面常见弹窗.

    Args:
        page: Playwright 页面实例
        selectors: 额外的弹窗关闭按钮选择器
    """

    default_selectors = [
        "button:has-text('关闭此对话框')",
        "button:has-text('我知道了')",
        "button:has-text('关闭')",
        "[aria-label='关闭此对话框']",
        "[aria-label='关闭']",
        ".jx-dialog__headerbtn",
        ".el-dialog__headerbtn",
    ]

    combined = list(default_selectors)
    if selectors:
        combined.extend(selectors)

    for selector in combined:
        try:
            locator = page.locator(selector)
            count = await locator.count()
            if count == 0:
                continue
            for idx in range(count):
                try:
                    element = locator.nth(idx)
                    if await element.is_visible(timeout=500):
                        await element.click(timeout=1_000)
                        logger.debug("已点击弹窗关闭按钮: {}", selector)
                        # await page.wait_for_timeout(300)
                except Exception:
                    continue
        except Exception:
            continue


async def open_edit_dialog_codegen(page: Page, index: int = 0) -> bool:
    """使用 codegen 录制的选择器打开指定索引商品的编辑弹窗.

    Args:
        page: Playwright 页面实例
        index: 商品索引(从 0 开始)

    Returns:
        bool: 是否成功打开弹窗
    """

    try:
        await close_known_popups(page)

        candidates = _collect_edit_button_candidates(page)
        target = await _resolve_target_button(candidates, index)
        if target is None:
            logger.warning("未找到可用的编辑按钮 (codegen) - index={}", index)
            return False

        await target.scroll_into_view_if_needed()
        await target.click(timeout=5_000)
        # await page.wait_for_timeout(500)

        if not await _wait_for_edit_dialog(page):
            raise TimeoutError("未在预期时间内检测到首次编辑弹窗")

        logger.debug("已打开第 {} 个商品的编辑弹窗 (codegen)", index + 1)
        return True
    except Exception as exc:  # pragma: no cover - 依赖实际页面结构
        logger.error("codegen 打开编辑弹窗失败: {}", exc)
        return False


def _collect_edit_button_candidates(page: Page) -> list[Locator]:
    """收集所有可能的编辑按钮定位器集合."""

    selector_pool = [
        ".jx-button.jx-button--primary.jx-button--small.is-text.pro-button.J_collectBoxEdit",
        ".jx-button.jx-button--primary.jx-button--small.is-text.pro-button.J_commonCollectBoxEdit",
        "button:has-text('首次编辑')",
        "button:has-text('编辑')",
        "a:has-text('首次编辑')",
        "a:has-text('编辑')",
        "[data-action='edit']",
        "text='首次编辑'",
        "text='编辑'",
    ]

    locators: list[Locator] = []
    for selector in selector_pool:
        try:
            locator = page.locator(selector)
            locators.append(locator)
        except Exception:
            continue
    return locators


async def _resolve_target_button(locators: list[Locator], index: int) -> Locator | None:
    """尝试在候选定位器中找到第 index 个可点击的按钮."""

    for locator in locators:
        try:
            count = await locator.count()
        except Exception:
            continue

        if count == 0:
            continue

        if index < count:
            candidate = locator.nth(index)
            is_visible = False
            try:
                is_visible = await candidate.is_visible(timeout=1_000)
            except Exception:
                is_visible = False
            if is_visible:
                return candidate

    # 尝试逐行查找
    page_ref = locators[0].page if locators else None
    try:
        if page_ref is None:
            return None

        rows = page_ref.locator(".pro-table tbody tr, tr")
        row_count = await rows.count()
        if row_count == 0:
            return None

        row_index = index if index < row_count else row_count - 1
        row = rows.nth(row_index)
        for selector in ["button:has-text('编辑')", "a:has-text('编辑')", "text='编辑'"]:
            try:
                elem = row.locator(selector).first
                if await elem.is_visible(timeout=500):
                    return elem
            except Exception:
                continue
    except Exception:
        return None

    return None


async def _wait_for_edit_dialog(page: Page) -> bool:
    """等待首次编辑弹窗出现并可见."""

    dialog_selectors = [
        ".collect-box-editor-dialog-V2",
        ".jx-overlay-dialog:visible",
        ".jx-dialog:visible",
        "[role='dialog']:visible",
    ]

    for selector in dialog_selectors:
        locator = page.locator(selector).first
        try:
            await locator.wait_for(state="visible", timeout=7_000)
            return True
        except TimeoutError:
            continue
        except Exception:
            continue

    # 如果仍未检测到, 尝试确认是否至少存在任意弹窗元素
    combined = page.locator(
        ".collect-box-editor-dialog-V2, .jx-overlay-dialog, .jx-dialog, [role='dialog']"
    )
    try:
        count = await combined.count()
    except Exception:
        return False

    if count == 0:
        return False

    for idx in range(count):
        element = combined.nth(idx)
        try:
            if await element.is_visible(timeout=500):
                logger.debug("检测到可见弹窗元素, 继续执行")
                return True
        except Exception:
            continue

    return False
