"""
@PURPOSE: 首次编辑弹窗的通用操作(等待,保存,关闭).
@OUTLINE:
  - class FirstEditDialogMixin: 弹窗等待,保存修改,关闭弹窗
"""

from __future__ import annotations

import re
from contextlib import suppress

from loguru import logger
from playwright.async_api import Locator, Page

from .base import FirstEditBase


class FirstEditDialogMixin(FirstEditBase):
    """封装首次编辑弹窗的等待,保存与关闭逻辑."""

    async def wait_for_dialog(self, page: Page, timeout: int = 5_000) -> bool:
        """等待首次编辑弹窗打开.

        Args:
            page: Playwright 页面对象.
            timeout: 等待弹窗的超时时间(毫秒).

        Returns:
            弹窗是否在超时时间内成功打开.
        """
        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            close_btn_selector = first_edit_config.get("close_btn", "button:has-text('关闭')")

            await page.wait_for_selector(close_btn_selector, timeout=timeout)
            logger.success("编辑弹窗已打开")
            return True
        except Exception as exc:
            logger.error(f"等待编辑弹窗失败: {exc}")
            return False

    async def save_changes(self, page: Page, wait_for_close: bool = False) -> bool:
        """保存首次编辑弹窗中的变更.

        Args:
            page: Playwright 页面对象.
            wait_for_close: 是否等待弹窗关闭.

        Returns:
            保存行为是否成功.
        """
        logger.info("保存修改...")

        try:
            save_selectors = [
                "button:has-text('保存')",
                "button:has-text('确定')",
                "button:has-text('提交')",
            ]

            saved = False
            for selector in save_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        logger.debug("找到保存按钮: %s", selector)
                        await page.locator(selector).first.click()
                        saved = True
                        break
                except Exception:
                    continue

            if not saved:
                logger.error("未找到保存按钮")
                return False

            if wait_for_close:
                try:
                    logger.debug("等待编辑弹窗关闭...")
                    dialog_count = await page.locator(".jx-dialog, .el-dialog, [role='dialog']").count()
                    if dialog_count == 0:
                        logger.success("修改已保存并关闭弹窗")
                    else:
                        logger.debug("弹窗仍存在(%s 个),继续等待", dialog_count)
                        dialog_count = await page.locator(".jx-dialog, .el-dialog, [role='dialog']").count()
                        if dialog_count == 0:
                            logger.success("修改已保存并关闭弹窗")
                        else:
                            logger.warning("修改已保存,但弹窗仍打开(%s 个)", dialog_count)
                except Exception as exc:
                    logger.warning("检查弹窗状态时出错: %s", exc)
                    logger.success("修改已保存")
            else:
                logger.success("修改已保存")

            return True
        except Exception as exc:
            logger.error(f"保存修改失败: {exc}")
            return False

    async def close_dialog(self, page: Page) -> bool:
        """关闭首次编辑弹窗.

        Args:
            page: Playwright 页面对象.

        Returns:
            弹窗是否成功关闭.
        """
        logger.info("关闭编辑弹窗(点击x)...")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            close_btn_selector = first_edit_config.get(
                "close_btn",
                "button[aria-label='关闭'], button[aria-label='Close'], .jx-dialog__headerbtn, .el-dialog__headerbtn",
            )

            selectors = [selector.strip() for selector in close_btn_selector.split(",")]
            fallback_selectors = [
                ".pro-dialog__close",
                ".pro-dialog__header button",
                ".dialog-close",
                "[class*='icon-close']",
            ]
            text_button_patterns = [
                "关闭此对话框",
                "关闭广告",
                "关闭",
                "我知道了",
                "知道了",
                "确定",
                "确认",
                "立即进入",
                "关闭弹窗",
            ]
            text_button_regex = [re.compile(pattern) for pattern in text_button_patterns]

            visible_dialog_selector = (
                ".jx-overlay-dialog:visible, .jx-dialog:visible, .el-dialog:visible, [role='dialog']:visible"
            )

            max_attempts = 8
            attempt = 0

            async def _click_first_visible(candidates: list[Locator]) -> bool:
                for locator in candidates:
                    try:
                        count = await locator.count()
                        if count == 0:
                            continue
                        for index in range(count):
                            candidate = locator.nth(index)
                            if await candidate.is_visible(timeout=500):
                                await candidate.click()
                                return True
                    except Exception:
                        continue
                return False

            while attempt < max_attempts:
                dialogs = page.locator(visible_dialog_selector)
                dialog_count = await dialogs.count()

                if dialog_count == 0:
                    logger.success("编辑弹窗已关闭")
                    return True

                target_dialog = dialogs.nth(dialog_count - 1)

                candidate_locators: list[Locator] = []
                candidate_locators.extend(target_dialog.locator(selector) for selector in selectors)
                candidate_locators.extend(target_dialog.locator(selector) for selector in fallback_selectors)

                button_locators = [
                    target_dialog.get_by_role("button", name=regex) for regex in text_button_regex
                ]
                button_locators.extend(
                    target_dialog.locator("button").filter(has_text=regex) for regex in text_button_regex
                )
                button_locators.extend(
                    target_dialog.locator("a").filter(has_text=regex) for regex in text_button_regex
                )
                candidate_locators.extend(button_locators)

                closed = await _click_first_visible(candidate_locators)

                if not closed:
                    logger.debug("未找到明确的关闭按钮,尝试发送 Escape")
                    with suppress(Exception):
                        await page.keyboard.press("Escape")

                overlay = page.locator(".scroll-menu-pane__content")
                with suppress(Exception):
                    if await overlay.count() and await overlay.first.is_visible(timeout=500):
                        logger.debug("检测到遮挡浮层,尝试点击背景关闭")
                        try:
                            await page.mouse.click(5, 5)
                        except Exception:
                            await page.keyboard.press("Escape")

                await page.wait_for_timeout(200)
                attempt += 1

            remaining = await page.locator(visible_dialog_selector).count()
            if remaining == 0:
                logger.success("编辑弹窗已关闭")
                return True

            logger.error("关闭弹窗超时,仍检测到 %s 个弹窗", remaining)
            return False
        except Exception as exc:
            logger.error(f"关闭弹窗失败: {exc}")
            return False

