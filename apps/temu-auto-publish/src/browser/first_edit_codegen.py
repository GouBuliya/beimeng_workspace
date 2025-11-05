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
from playwright.async_api import Page, expect


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
                        logger.debug("已点击弹窗关闭按钮: %s", selector)
                        await page.wait_for_timeout(300)
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
        edit_buttons = page.locator(
            ".jx-button.jx-button--primary.jx-button--small.is-text.pro-button.J_commonCollectBoxEdit"
        )
        count = await edit_buttons.count()
        if count == 0:
            logger.warning("未找到任何编辑按钮 (codegen)")
            return False

        if index >= count:
            logger.warning("编辑按钮数量不足: 需要 %s, 实际 %s", index + 1, count)
            return False

        target = edit_buttons.nth(index)
        await target.scroll_into_view_if_needed()
        await target.click(timeout=5_000)
        await page.wait_for_timeout(500)

        dialog = page.locator(
            ".jx-overlay-dialog:visible, .jx-dialog:visible, .el-dialog:visible, [role='dialog']:visible"
        )
        await expect(dialog).to_be_visible(timeout=5_000)
        logger.debug("已打开第 %s 个商品的编辑弹窗 (codegen)", index + 1)
        return True
    except Exception as exc:  # pragma: no cover - 依赖实际页面结构
        logger.error("codegen 打开编辑弹窗失败: %s", exc)
        return False
