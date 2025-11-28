"""
@PURPOSE: 首次编辑物流信息 Tab 操作逻辑.
@OUTLINE:
  - class FirstEditLogisticsMixin: 切换物流栏,设置包裹重量与尺寸
"""

from __future__ import annotations

import asyncio

from loguru import logger
from playwright.async_api import Page

from ...utils.selector_race import TIMEOUTS, try_selectors_race
from .base import FirstEditBase


class FirstEditLogisticsMixin(FirstEditBase):
    """封装物流信息相关的设置流程."""

    async def navigate_to_logistics_tab(self, page: Page) -> bool:
        """切换到物流信息 Tab."""
        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            nav_config = first_edit_config.get("navigation", {})
            logistics_tab_selector = nav_config.get("logistics_info", "text='物流信息'")

            logger.info("导航到「物流信息」Tab...")
            await page.locator(logistics_tab_selector).click()
            logger.success("已切换到物流信息 Tab")
            return True
        except Exception as exc:
            logger.error(f"导航到物流信息 Tab 失败: {exc}")
            return False

    async def set_package_weight_in_logistics(self, page: Page, weight: float) -> bool:
        """在物流信息 Tab 中设置包裹重量."""
        logger.info("SOP 4.6: 设置包裹重量 -> {} G", weight)

        if not (5_000 <= weight <= 9_999):
            logger.warning("重量 {} G 超出推荐范围(5000-9999G)", weight)

        try:
            if not await self.navigate_to_logistics_tab(page):
                return False

            first_edit_config = self.selectors.get("first_edit_dialog", {})
            logistics_config = first_edit_config.get("logistics_info", {})
            weight_selector = logistics_config.get(
                "package_weight",
                "input[placeholder*='包裹重量'], input[placeholder*='重量']",
            )

            weight_selectors = [
                weight_selector,
                "input[placeholder='包裹重量']",
                "input[placeholder*='重量']",
                "input[placeholder*='重']",
            ]

            # 使用并行竞速策略查找重量输入框
            weight_input = await try_selectors_race(
                page,
                weight_selectors,
                timeout_ms=TIMEOUTS.NORMAL,
                context_name="物流-包裹重量",
            )

            if not weight_input:
                logger.error("未找到包裹重量输入框(物流信息 Tab)")
                logger.info("提示:需要通过 Playwright Codegen 录制实际操作以确认选择器")
                return False

            await weight_input.fill("")
            await weight_input.fill(str(weight))
            logger.success("包裹重量已设置: {} G", weight)
            return True
        except Exception as exc:
            logger.error(f"设置包裹重量失败: {exc}")
            return False

    async def set_package_dimensions_in_logistics(
        self,
        page: Page,
        length: float,
        width: float,
        height: float,
    ) -> bool:
        """在物流信息 Tab 中设置包裹尺寸."""
        logger.info("SOP 4.7: 设置包裹尺寸 -> {} x {} x {} CM", length, width, height)

        if not all(50 <= dim <= 99 for dim in [length, width, height]):
            logger.warning("尺寸超出推荐范围(50-99cm)")

        if not (length > width > height):
            raise ValueError(f"尺寸不符合 SOP 规则(长>宽>高): {length}>{width}>{height}")

        try:
            if not await self.navigate_to_logistics_tab(page):
                return False

            first_edit_config = self.selectors.get("first_edit_dialog", {})
            logistics_config = first_edit_config.get("logistics_info", {})

            length_selector = logistics_config.get(
                "package_length",
                "input[placeholder*='包裹长度'], input[placeholder*='长度'], input[placeholder*='长']",
            )
            width_selector = logistics_config.get(
                "package_width",
                "input[placeholder*='包裹宽度'], input[placeholder*='宽度'], input[placeholder*='宽']",
            )
            height_selector = logistics_config.get(
                "package_height",
                "input[placeholder*='包裹高度'], input[placeholder*='高度'], input[placeholder*='高']",
            )

            length_selectors = [s.strip() for s in length_selector.split(", ")]
            width_selectors = [s.strip() for s in width_selector.split(", ")]
            height_selectors = [s.strip() for s in height_selector.split(", ")]

            # 并行查找长、宽、高三个输入框
            length_input, width_input, height_input = await asyncio.gather(
                try_selectors_race(
                    page, length_selectors, TIMEOUTS.NORMAL, "物流-包裹长度"
                ),
                try_selectors_race(
                    page, width_selectors, TIMEOUTS.NORMAL, "物流-包裹宽度"
                ),
                try_selectors_race(
                    page, height_selectors, TIMEOUTS.NORMAL, "物流-包裹高度"
                ),
            )

            if not length_input or not width_input or not height_input:
                logger.error(
                    "未找到包裹尺寸输入框(长:%s 宽:%s 高:%s)",
                    length_input is not None,
                    width_input is not None,
                    height_input is not None,
                )
                logger.info("提示:需要通过 Playwright Codegen 录制实际操作以确认选择器")
                return False

            await length_input.fill("")
            await length_input.fill(str(length))

            await width_input.fill("")
            await width_input.fill(str(width))

            await height_input.fill("")
            await height_input.fill(str(height))

            logger.success("包裹尺寸已设置: {} x {} x {} CM", length, width, height)
            return True
        except ValueError:
            raise
        except Exception as exc:
            logger.error(f"设置包裹尺寸失败: {exc}")
            return False

