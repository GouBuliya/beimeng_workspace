"""
@PURPOSE: 首次编辑中与 SKU 相关的字段维护逻辑.
@OUTLINE:
  - class FirstEditSkuMixin: 设置价格,库存,重量,尺寸
"""

from __future__ import annotations

import asyncio

from loguru import logger
from playwright.async_api import Page

from ...utils.selector_race import TIMEOUTS, try_selectors_race_with_elements
from .base import FirstEditBase


class FirstEditSkuMixin(FirstEditBase):
    """封装首次编辑流程中的 SKU 维度操作."""

    async def set_sku_price(self, page: Page, price: float, sku_index: int = 0) -> bool:
        """设置 SKU 价格(SOP 步骤 4.4)."""
        logger.info("SOP 4.4: 设置价格 -> {} CNY", price)

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})

            nav_config = first_edit_config.get("navigation", {})
            sales_tab_selector = nav_config.get("sales_attrs", "text='销售属性'")
            await page.locator(sales_tab_selector).click()

            price_selectors = [
                "input[placeholder='价格']:not([aria-label='页'])",
                "input[placeholder*='价格'][type='text']",
            ]

            # 使用并行竞速策略查找价格输入框（支持第 N 个元素）
            price_input = await try_selectors_race_with_elements(
                page,
                price_selectors,
                timeout_ms=TIMEOUTS.FAST,
                context_name="SKU-价格输入框",
                nth=sku_index,
            )

            if not price_input:
                logger.error("未找到价格输入框")
                return False

            await price_input.fill("")
            await price_input.fill(str(price))
            logger.success("价格已设置: {} CNY", price)
            return True
        except Exception as exc:
            logger.error(f"设置价格失败: {exc}")
            return False

    async def set_sku_stock(self, page: Page, stock: int, sku_index: int = 0) -> bool:
        """设置 SKU 库存(SOP 步骤 4.5)."""
        logger.info("SOP 4.5: 设置库存 -> {}", stock)

        try:
            stock_selectors = [
                "input[placeholder='库存']",
                "input[placeholder*='库存'][type='text']",
                "input[type='number']",
            ]

            # 使用并行竞速策略查找库存输入框
            stock_input = await try_selectors_race_with_elements(
                page,
                stock_selectors,
                timeout_ms=TIMEOUTS.FAST,
                context_name="SKU-库存输入框",
                nth=sku_index,
            )

            if not stock_input:
                logger.error("未找到库存输入框")
                return False

            await stock_input.fill("")
            await stock_input.fill(str(stock))
            logger.success("库存已设置: {}", stock)
            return True
        except Exception as exc:
            logger.error(f"设置库存失败: {exc}")
            return False

    async def set_sku_weight(self, page: Page, weight: float, sku_index: int = 0) -> bool:
        """设置 SKU 重量(SOP 步骤 4.6)."""
        logger.info("SOP 4.6: 设置重量 -> {} KG", weight)

        try:
            weight_selectors = [
                "input[placeholder='重量']",
                "input[placeholder*='重量']",
                "input[placeholder*='重']",
            ]

            # 使用并行竞速策略查找重量输入框
            weight_input = await try_selectors_race_with_elements(
                page,
                weight_selectors,
                timeout_ms=TIMEOUTS.FAST,
                context_name="SKU-重量输入框",
                nth=sku_index,
            )

            if not weight_input:
                logger.error("未找到重量输入框")
                return False

            await weight_input.fill("")
            await weight_input.fill(str(weight))
            logger.success("重量已设置: {} KG", weight)
            return True
        except Exception as exc:
            logger.error(f"设置重量失败: {exc}")
            return False

    async def set_sku_dimensions(
        self,
        page: Page,
        length: float,
        width: float,
        height: float,
        sku_index: int = 0,
    ) -> bool:
        """设置 SKU 尺寸(SOP 步骤 4.7)."""
        logger.info("SOP 4.7: 设置尺寸 -> {} x {} x {} CM", length, width, height)

        try:
            length_selectors = ["input[placeholder='长']", "input[placeholder*='长']"]
            width_selectors = ["input[placeholder='宽']", "input[placeholder*='宽']"]
            height_selectors = ["input[placeholder='高']", "input[placeholder*='高']"]

            # 并行查找长、宽、高三个输入框
            length_input, width_input, height_input = await asyncio.gather(
                try_selectors_race_with_elements(
                    page, length_selectors, TIMEOUTS.FAST, "SKU-长度输入框", sku_index
                ),
                try_selectors_race_with_elements(
                    page, width_selectors, TIMEOUTS.FAST, "SKU-宽度输入框", sku_index
                ),
                try_selectors_race_with_elements(
                    page, height_selectors, TIMEOUTS.FAST, "SKU-高度输入框", sku_index
                ),
            )

            if not length_input or not width_input or not height_input:
                logger.error(
                    "未找到尺寸输入框(长:%s 宽:%s 高:%s)",
                    length_input is not None,
                    width_input is not None,
                    height_input is not None,
                )
                return False

            await length_input.fill("")
            await length_input.fill(str(length))

            await width_input.fill("")
            await width_input.fill(str(width))

            await height_input.fill("")
            await height_input.fill(str(height))

            logger.success("尺寸已设置: {} x {} x {} CM", length, width, height)
            return True
        except Exception as exc:
            logger.error(f"设置尺寸失败: {exc}")
            return False

