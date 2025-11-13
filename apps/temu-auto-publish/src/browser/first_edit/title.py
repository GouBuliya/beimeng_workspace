"""
@PURPOSE: 首次编辑标题读取与 AI 生成逻辑.
@OUTLINE:
  - class FirstEditTitleMixin: 获取原始标题,编辑标题,AI 标题生成
"""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

from .base import FirstEditBase


class FirstEditTitleMixin(FirstEditBase):
    """提供首次编辑中的标题获取与编辑能力."""

    async def get_original_title(self, page: Page) -> str:
        """获取产品的原始标题(SOP 步骤 4.2 准备).

        Args:
            page: Playwright 页面对象.

        Returns:
            原始标题文本;若获取失败返回空字符串.
        """
        logger.debug("获取产品原始标题...")

        try:
            title_selectors = [
                "xpath=//label[contains(text(), '产品标题')]/following-sibling::*/descendant::input[@type='text'][1]",
                "xpath=//label[contains(text(), '产品标题')]/following::input[@type='text'][1]",
                "xpath=//div[contains(@class, 'jx-form-item')]//label[contains(text(), '产品标题:')]//following-sibling::*/descendant::input[@type='text']",
                "xpath=//label[contains(text(), '产品标题')]/ancestor::div[contains(@class, 'jx-form-item')]//input[contains(@class, 'jx-input__inner') and @type='text']",
                ".jx-overlay-dialog input.jx-input__inner[type='text']:visible",
            ]

            title_input = None
            for selector in title_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        for index in range(count):
                            element = page.locator(selector).nth(index)
                            if await element.is_visible(timeout=1_000):
                                title_input = element
                                logger.debug("使用选择器: %s (第 %s 个)", selector, index + 1)
                                break
                        if title_input:
                            break
                except Exception:
                    continue

            if not title_input:
                logger.error("未找到标题输入框")
                return ""

            title = await title_input.input_value()
            logger.success("获取到原始标题: %s...", title[:50])
            return title
        except Exception as exc:
            logger.error(f"获取原始标题失败: {exc}")
            return ""

    async def edit_title(self, page: Page, new_title: str) -> bool:
        """编辑产品标题(SOP 步骤 4.1).

        Args:
            page: Playwright 页面对象.
            new_title: 新标题,应包含型号后缀.

        Returns:
            标题是否成功更新.
        """
        logger.info("SOP 4.1: 编辑标题 -> %s", new_title)
        logger.debug("标题长度: %s 字符", len(new_title))

        try:
            title_selectors = [
                "xpath=//label[contains(text(), '产品标题')]/following-sibling::*/descendant::input[@type='text'][1]",
                "xpath=//label[contains(text(), '产品标题')]/following::input[@type='text'][1]",
                "xpath=//div[contains(@class, 'jx-form-item')]//label[contains(text(), '产品标题:')]//following-sibling::*/descendant::input[@type='text']",
                "xpath=//label[contains(text(), '产品标题')]/ancestor::div[contains(@class, 'jx-form-item')]//input[contains(@class, 'jx-input__inner') and @type='text']",
                ".jx-overlay-dialog input.jx-input__inner[type='text']:visible",
            ]

            title_input = None
            used_selector = None
            for index, selector in enumerate(title_selectors, start=1):
                try:
                    logger.debug("[%s/%s] 尝试选择器: %s...", index, len(title_selectors), selector[:60])
                    count = await page.locator(selector).count()
                    logger.debug("找到 %s 个匹配元素", count)

                    if count > 0:
                        for elem_index in range(count):
                            element = page.locator(selector).nth(elem_index)
                            if await element.is_visible(timeout=1_000):
                                title_input = element
                                used_selector = f"{selector} (第 {elem_index + 1} 个)"
                                logger.info("使用选择器定位到标题输入框: %s", used_selector)
                                break
                        if title_input:
                            break
                except Exception as exc:
                    logger.debug("选择器失败: %s", exc)
                    continue

            if not title_input:
                logger.error("未找到标题输入框")
                logger.error("尝试了 %s 种选择器均失败", len(title_selectors))
                return False

            current_title = await title_input.input_value()
            logger.debug("当前标题: %s...", current_title[:50])

            logger.info("清空标题字段并填写新标题")
            await title_input.fill("")
            await title_input.fill(new_title)

            updated_title = await title_input.input_value()
            logger.debug("更新后的标题: %s...", updated_title[:50])

            if updated_title == new_title:
                logger.success("标题已成功更新: %s", new_title)
                return True

            logger.warning("标题可能未完全更新")
            logger.warning("期望: %s", new_title)
            logger.warning("实际: %s", updated_title)
            return True
        except Exception as exc:
            logger.error(f"编辑标题失败: {exc}")
            return False

    async def edit_title_with_ai(
        self,
        page: Page,
        product_index: int,
        all_original_titles: list[str],
        model_number: str,
        use_ai: bool = True,
    ) -> bool:
        """使用 AI 生成的新标题编辑产品标题(SOP 步骤 4.2).

        Args:
            page: Playwright 页面对象.
            product_index: 产品索引(0-4).
            all_original_titles: 原始标题列表.
            model_number: 型号后缀.
            use_ai: 是否启用 AI 生成.

        Returns:
            标题是否成功更新.
        """
        logger.info("SOP 4.2: 使用 AI 生成标题(产品 %s/5)", product_index + 1)

        try:
            from ...data_processor.ai_title_generator import AITitleGenerator

            ai_generator = AITitleGenerator()
            new_titles = await ai_generator.generate_titles(
                all_original_titles,
                model_number=model_number,
                use_ai=use_ai,
            )

            if product_index >= len(new_titles):
                logger.error("产品索引超出范围: %s/%s", product_index, len(new_titles))
                return False

            new_title = new_titles[product_index]
            logger.info("为产品 %s 生成的标题: %s", product_index + 1, new_title)
            return await self.edit_title(page, new_title)
        except Exception as exc:
            logger.error(f"使用 AI 编辑标题失败: {exc}")
            if product_index < len(all_original_titles):
                fallback_title = f"{all_original_titles[product_index]} {model_number}"
                logger.warning("使用降级方案: %s", fallback_title)
                return await self.edit_title(page, fallback_title)
            return False

