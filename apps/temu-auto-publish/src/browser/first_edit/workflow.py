"""
@PURPOSE: 首次编辑整体流程编排.
@OUTLINE:
  - class FirstEditWorkflowMixin: complete_first_edit orchestrator
"""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

from .base import FirstEditBase


class FirstEditWorkflowMixin(FirstEditBase):
    """封装首次编辑完整流程的编排逻辑."""

    async def complete_first_edit(
        self,
        page: Page,
        title: str,
        price: float,
        stock: int,
        weight: float,
        dimensions: tuple[float, float, float],
    ) -> bool:
        """执行首次编辑的完整 SOP 流程."""
        logger.info("=" * 60)
        logger.info("开始执行首次编辑完整流程(SOP 步骤 4)")
        logger.info("=" * 60)
        await page.wait_for_load_state("domcontentloaded")
        try:
            if not await self.edit_title(page, title):
                logger.error("标题设置失败")
                return False
            await page.wait_for_load_state("domcontentloaded")

            if not await self.set_sku_price(page, price):
                logger.error("价格设置失败")
                return False
            await page.wait_for_load_state("domcontentloaded")

            if not await self.set_sku_stock(page, stock):
                logger.error("库存设置失败")
                return False
            await page.wait_for_load_state("domcontentloaded")

            logger.info("尝试设置包裹重量(物流信息 Tab)...")
            weight_success = await self.set_package_weight_in_logistics(page, weight)
            if not weight_success:
                logger.warning("包裹重量设置失败 - 可能需要 Codegen 验证选择器")
            await page.wait_for_load_state("domcontentloaded")

            logger.info("尝试设置包裹尺寸(物流信息 Tab)...")
            length, width, height = dimensions
            try:
                dimensions_success = await self.set_package_dimensions_in_logistics(
                    page,
                    length,
                    width,
                    height,
                )
                if not dimensions_success:
                    logger.warning("包裹尺寸设置失败 - 可能需要 Codegen 验证选择器")
            except ValueError as exc:
                logger.error(f"尺寸验证失败: {exc}")
                logger.warning("跳过尺寸设置")
            await page.wait_for_load_state("domcontentloaded")
            logger.info("切换回基本信息 Tab...")
            nav_config = self.selectors.get("first_edit_dialog", {}).get("navigation", {})
            basic_info_selector = nav_config.get("basic_info", "text='基本信息'")
            try:
                await page.locator(basic_info_selector).click()
            except Exception:
                logger.warning("切换回基本信息 Tab 失败,但继续执行")

            if not await self.save_changes(page, wait_for_close=False):
                logger.error("保存修改失败")
                return False

            logger.debug("点击关闭按钮(x)...")
            if not await self.close_dialog(page):
                logger.warning("关闭弹窗失败,但继续执行")

            logger.info("=" * 60)
            logger.success("首次编辑完整流程已完成(标题,价格,库存,重量,尺寸)")
            logger.info("=" * 60)
            return True
        except Exception as exc:
            logger.error(f"首次编辑流程失败: {exc}")
            return False

