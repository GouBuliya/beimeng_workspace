"""
@PURPOSE: 首次编辑类目核对逻辑.
@OUTLINE:
  - class FirstEditCategoryMixin: 核对类目合规
"""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

from .base import TIMEOUTS, FirstEditBase


class FirstEditCategoryMixin(FirstEditBase):
    """提供首次编辑时的类目核对逻辑。"""

    async def check_category(self, page: Page) -> tuple[bool, str]:
        """核对商品类目是否合规(SOP 步骤 4.3).

        Args:
            page: Playwright 页面对象.

        Returns:
            二元组:
                - 是否合规.
                - 检测到的类目名称.
        """
        logger.info("SOP 4.3: 核对商品类目...")

        unsupported_categories = [
            "药品",
            "医疗器械",
            "保健品",
            "电子产品",
            "数码产品",
            "食品",
            "化妆品",
        ]

        try:
            category_selectors = [
                "xpath=//label[contains(text(), '类目')]/following-sibling::*/descendant::input[1]",
                (
                    "xpath=//label[contains(text(), '类目')]/following-sibling::*//"
                    "div[contains(@class, 'jx-input')]"
                ),
                ".jx-overlay-dialog .jx-select input[placeholder*='类目']",
                ".jx-overlay-dialog input[placeholder*='选择类目']",
            ]

            category_element = await self.find_visible_element(
                page,
                category_selectors,
                timeout_ms=TIMEOUTS.NORMAL,
                context_name="类目选择",
            )

            category_text = ""
            if category_element:
                category_text = (
                    await category_element.input_value()
                    or await category_element.inner_text()
                )
                if category_text:
                    logger.debug("找到类目信息: {}", category_text)

            if not category_text:
                logger.warning("未能读取类目信息,默认认为合规(建议人工确认)")
                return True, "未知类目"

            for unsupported in unsupported_categories:
                if unsupported in category_text:
                    logger.warning("类目不合规: {}(包含 {})", category_text, unsupported)
                    return False, category_text

            logger.success("类目合规: {}", category_text)
            return True, category_text
        except Exception as exc:
            logger.error(f"核对类目失败: {exc}")
            logger.warning("默认认为类目合规(建议人工确认)")
            return True, "检查失败"
