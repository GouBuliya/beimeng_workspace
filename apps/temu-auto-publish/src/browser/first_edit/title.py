"""
@PURPOSE: 首次编辑标题读取与 AI 生成逻辑.
@OUTLINE:
  - class FirstEditTitleMixin: 获取原始标题,编辑标题,AI 标题生成
"""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

from ...utils.selector_race import TIMEOUTS, try_selectors_race
from .base import FirstEditBase


class FirstEditTitleMixin(FirstEditBase):
    """提供首次编辑中的标题获取与编辑能力."""

    async def get_original_title(self, page: Page, max_retries: int = 3) -> str:
        """获取产品的原始标题(SOP 步骤 4.2 准备).

        Args:
            page: Playwright 页面对象.
            max_retries: 最大重试次数,默认 3 次.

        Returns:
            原始标题文本;若获取失败返回空字符串.
        """
        logger.debug("获取产品原始标题...")

        # 优化顺序：基于选择器命中记录，将成功率最高的选择器放在前面
        title_selectors = [
            ".jx-overlay-dialog input.jx-input__inner[type='text']:visible",  # 命中率最高
            "xpath=//label[contains(text(), '产品标题')]/following-sibling::*/descendant::input[@type='text'][1]",
            "xpath=//label[contains(text(), '产品标题')]/following::input[@type='text'][1]",
            "xpath=//div[contains(@class, 'jx-form-item')]//label[contains(text(), '产品标题:')]//following-sibling::*/descendant::input[@type='text']",
            "xpath=//label[contains(text(), '产品标题')]/ancestor::div[contains(@class, 'jx-form-item')]//input[contains(@class, 'jx-input__inner') and @type='text']",
        ]

        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    logger.info("第 {}/{} 次尝试获取原始标题...", attempt, max_retries)

                # 使用并行竞速策略查找标题输入框
                title_input = await try_selectors_race(
                    page,
                    title_selectors,
                    timeout_ms=TIMEOUTS.NORMAL,
                    context_name="获取原始标题",
                )

                if not title_input:
                    if attempt < max_retries:
                        logger.warning("第 {} 次尝试未找到标题输入框,准备重试...", attempt)
                        # 智能等待: 等待 DOM 稳定而非固定延迟
                        await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUTS.NORMAL)
                        continue
                    logger.error("未找到标题输入框(已重试 {} 次)", max_retries)
                    return ""

                title = await title_input.input_value()
                logger.success("获取到原始标题: {}...", title[:50])
                return title
            except Exception as exc:
                if attempt < max_retries:
                    logger.warning(f"第 {attempt} 次获取原始标题失败: {exc},准备重试...")
                    # 智能等待: 等待 DOM 稳定而非固定延迟
                    await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUTS.NORMAL)
                    continue
                logger.error(f"获取原始标题失败(已重试 {max_retries} 次): {exc}")
                return ""

        return ""

    async def edit_title(self, page: Page, new_title: str) -> bool:
        """编辑产品标题(SOP 步骤 4.1).

        Args:
            page: Playwright 页面对象.
            new_title: 新标题,应包含型号后缀.

        Returns:
            标题是否成功更新.
        """
        logger.info("SOP 4.1: 编辑标题 -> {}", new_title)
        logger.debug("标题长度: {} 字符", len(new_title))

        try:
            # 优化顺序：基于选择器命中记录，将成功率最高的选择器放在前面
            title_selectors = [
                ".jx-overlay-dialog input.jx-input__inner[type='text']:visible",  # 命中率最高
                "xpath=//label[contains(text(), '产品标题')]/following-sibling::*/descendant::input[@type='text'][1]",
                "xpath=//label[contains(text(), '产品标题')]/following::input[@type='text'][1]",
                "xpath=//div[contains(@class, 'jx-form-item')]//label[contains(text(), '产品标题:')]//following-sibling::*/descendant::input[@type='text']",
                "xpath=//label[contains(text(), '产品标题')]/ancestor::div[contains(@class, 'jx-form-item')]//input[contains(@class, 'jx-input__inner') and @type='text']",
            ]

            # 使用并行竞速策略查找标题输入框
            title_input = await try_selectors_race(
                page,
                title_selectors,
                timeout_ms=TIMEOUTS.NORMAL,
                context_name="编辑标题输入框",
            )

            if not title_input:
                logger.error("未找到标题输入框")
                logger.error("尝试了 {} 种选择器均失败", len(title_selectors))
                return False

            current_title = await title_input.input_value()
            logger.debug("当前标题: {}...", current_title[:50])

            logger.info("清空标题字段并填写新标题")
            await title_input.fill("")
            await title_input.fill(new_title)

            updated_title = await title_input.input_value()
            logger.debug("更新后的标题: {}...", updated_title[:50])

            if updated_title == new_title:
                logger.success("标题已成功更新: {}", new_title)
                return True

            logger.warning("标题可能未完全更新")
            logger.warning("期望: {}", new_title)
            logger.warning("实际: {}", updated_title)
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
        logger.info("SOP 4.2: 使用 AI 生成标题(产品 {}/5)", product_index + 1)

        try:
            from ...data_processor.ai_title_generator import AITitleGenerator

            ai_generator = AITitleGenerator()
            new_titles = await ai_generator.generate_titles(
                all_original_titles,
                model_number=model_number,
                use_ai=use_ai,
            )

            if product_index >= len(new_titles):
                logger.error("产品索引超出范围: {}/{}", product_index, len(new_titles))
                return False

            new_title = new_titles[product_index]
            logger.info("为产品 {} 生成的标题: {}", product_index + 1, new_title)
            return await self.edit_title(page, new_title)
        except Exception as exc:
            logger.error(f"使用 AI 编辑标题失败: {exc}")
            if product_index < len(all_original_titles):
                fallback_title = f"{all_original_titles[product_index]} {model_number}"
                logger.warning("使用降级方案: {}", fallback_title)
                return await self.edit_title(page, fallback_title)
            return False

