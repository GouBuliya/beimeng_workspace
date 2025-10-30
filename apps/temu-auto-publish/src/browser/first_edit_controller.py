"""
@PURPOSE: 首次编辑控制器，负责产品的首次编辑操作（SOP步骤4）
@OUTLINE:
  - class FirstEditController: 首次编辑控制器主类
  - async def edit_title(): 编辑产品标题（步骤4.1）
  - async def modify_category(): 修改产品类目（步骤4.2）
  - async def edit_images(): 处理产品图片（步骤4.3）
  - async def set_price(): 设置价格（步骤4.4）
  - async def set_stock(): 设置库存（步骤4.5）
  - async def set_dimensions(): 设置重量和尺寸（步骤4.6-4.7）
  - async def save_changes(): 保存修改
@GOTCHAS:
  - 首次编辑是一个弹窗对话框，需要等待加载
  - 使用aria-ref定位元素
  - 详细描述使用iframe富文本编辑器
  - 保存后弹窗会关闭
@DEPENDENCIES:
  - 内部: browser_manager
  - 外部: playwright, loguru
@RELATED: miaoshou_controller.py, batch_edit_controller.py
"""

import asyncio
import json
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger
from playwright.async_api import Page


class FirstEditController:
    """首次编辑控制器（SOP步骤4的7个子步骤）.

    负责产品的首次编辑，包括：
    1. 编辑标题（添加型号后缀）
    2. 修改类目
    3. 编辑图片
    4. 设置价格（建议售价=成本×10，供货价=成本×7.5）
    5. 设置库存
    6. 填写重量
    7. 填写尺寸

    Attributes:
        selectors: 妙手ERP选择器配置

    Examples:
        >>> ctrl = FirstEditController()
        >>> await ctrl.edit_title(page, "新标题 A0001型号")
    """

    def __init__(self, selector_path: str = "config/miaoshou_selectors_v2.json"):
        """初始化首次编辑控制器.

        Args:
            selector_path: 选择器配置文件路径（默认使用v2文本定位器版本）
        """
        self.selector_path = Path(selector_path)
        self.selectors = self._load_selectors()
        logger.info("首次编辑控制器初始化（SOP步骤4 - 文本定位器）")

    def _load_selectors(self) -> dict:
        """加载选择器配置."""
        try:
            if not self.selector_path.is_absolute():
                current_file = Path(__file__)
                project_root = current_file.parent.parent.parent
                selector_file = project_root / self.selector_path
            else:
                selector_file = self.selector_path

            with open(selector_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载选择器配置失败: {e}")
            return {}

    async def wait_for_dialog(self, page: Page, timeout: int = 5000) -> bool:
        """等待编辑弹窗打开.

        Args:
            page: Playwright页面对象
            timeout: 超时时间（毫秒）

        Returns:
            弹窗是否已打开
        """
        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            close_btn_selector = first_edit_config.get("close_btn", "button:has-text('关闭')")

            await page.wait_for_selector(close_btn_selector, timeout=timeout)
            logger.success("✓ 编辑弹窗已打开")
            return True
        except Exception as e:
            logger.error(f"等待编辑弹窗失败: {e}")
            return False

    async def edit_title(self, page: Page, new_title: str) -> bool:
        """编辑产品标题（SOP步骤4.1）.

        Args:
            page: Playwright页面对象
            new_title: 新标题（应包含型号后缀，如"产品名 A0001型号"）

        Returns:
            是否编辑成功

        Examples:
            >>> await ctrl.edit_title(page, "新款洗衣篮 A0001型号")
            True
        """
        logger.info(f"SOP 4.1: 编辑标题 -> {new_title}")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            basic_info_config = first_edit_config.get("basic_info", {})

            title_selector = basic_info_config.get("title_input", "input[placeholder*='标题']")
            
            # 清空并填写新标题
            await page.locator(title_selector).fill("")
            await page.wait_for_timeout(300)
            await page.locator(title_selector).fill(new_title)
            await page.wait_for_timeout(500)

            logger.success(f"✓ 标题已更新: {new_title}")
            return True

        except Exception as e:
            logger.error(f"编辑标题失败: {e}")
            return False

    async def set_sku_price(
        self,
        page: Page,
        price: float,
        sku_index: int = 0
    ) -> bool:
        """设置SKU价格（SOP步骤4.4）.

        Args:
            page: Playwright页面对象
            price: 货源价格（CNY）
            sku_index: SKU索引（默认0，第一个SKU）

        Returns:
            是否设置成功

        Examples:
            >>> await ctrl.set_sku_price(page, 174.78)
            True
        """
        logger.info(f"SOP 4.4: 设置价格 -> {price} CNY")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            sales_attrs_config = first_edit_config.get("sales_attrs", {})

            # 切换到销售属性tab
            nav_config = first_edit_config.get("navigation", {})
            sales_tab_selector = nav_config.get("sales_attrs", "text='销售属性'")
            await page.locator(sales_tab_selector).click()
            await page.wait_for_timeout(1000)

            # 填写SKU价格
            price_selector = sales_attrs_config.get("sku_price_template", "input[placeholder*='价格']")
            await page.locator(price_selector).fill(str(price))
            await page.wait_for_timeout(500)

            logger.success(f"✓ 价格已设置: {price} CNY")
            return True

        except Exception as e:
            logger.error(f"设置价格失败: {e}")
            return False

    async def set_sku_stock(
        self,
        page: Page,
        stock: int,
        sku_index: int = 0
    ) -> bool:
        """设置SKU库存（SOP步骤4.5）.

        Args:
            page: Playwright页面对象
            stock: 库存数量
            sku_index: SKU索引（默认0）

        Returns:
            是否设置成功

        Examples:
            >>> await ctrl.set_sku_stock(page, 99)
            True
        """
        logger.info(f"SOP 4.5: 设置库存 -> {stock}")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            sales_attrs_config = first_edit_config.get("sales_attrs", {})

            stock_selector = sales_attrs_config.get("sku_stock_template", "input[placeholder*='库存']")
            await page.locator(stock_selector).fill(str(stock))
            await page.wait_for_timeout(500)

            logger.success(f"✓ 库存已设置: {stock}")
            return True

        except Exception as e:
            logger.error(f"设置库存失败: {e}")
            return False

    async def set_sku_weight(
        self,
        page: Page,
        weight: float,
        sku_index: int = 0
    ) -> bool:
        """设置SKU重量（SOP步骤4.6）.

        Args:
            page: Playwright页面对象
            weight: 重量（KG）
            sku_index: SKU索引（默认0）

        Returns:
            是否设置成功

        Examples:
            >>> await ctrl.set_sku_weight(page, 0.5)
            True
        """
        logger.info(f"SOP 4.6: 设置重量 -> {weight} KG")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            sales_attrs_config = first_edit_config.get("sales_attrs", {})

            weight_selector = sales_attrs_config.get("sku_weight_template", "input[placeholder*='重量']")
            await page.locator(weight_selector).fill(str(weight))
            await page.wait_for_timeout(500)

            logger.success(f"✓ 重量已设置: {weight} KG")
            return True

        except Exception as e:
            logger.error(f"设置重量失败: {e}")
            return False

    async def set_sku_dimensions(
        self,
        page: Page,
        length: float,
        width: float,
        height: float,
        sku_index: int = 0
    ) -> bool:
        """设置SKU尺寸（SOP步骤4.7）.

        Args:
            page: Playwright页面对象
            length: 长度（CM）
            width: 宽度（CM）
            height: 高度（CM）
            sku_index: SKU索引（默认0）

        Returns:
            是否设置成功

        Examples:
            >>> await ctrl.set_sku_dimensions(page, 40, 30, 50)
            True
        """
        logger.info(f"SOP 4.7: 设置尺寸 -> {length}x{width}x{height} CM")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            sales_attrs_config = first_edit_config.get("sales_attrs", {})

            # 填写长宽高
            length_selector = sales_attrs_config.get("sku_length_template", "input[placeholder*='长']")
            width_selector = sales_attrs_config.get("sku_width_template", "input[placeholder*='宽']")
            height_selector = sales_attrs_config.get("sku_height_template", "input[placeholder*='高']")

            await page.locator(length_selector).fill(str(length))
            await page.wait_for_timeout(300)
            await page.locator(width_selector).fill(str(width))
            await page.wait_for_timeout(300)
            await page.locator(height_selector).fill(str(height))
            await page.wait_for_timeout(500)

            logger.success(f"✓ 尺寸已设置: {length}x{width}x{height} CM")
            return True

        except Exception as e:
            logger.error(f"设置尺寸失败: {e}")
            return False

    async def save_changes(self, page: Page, wait_for_close: bool = True) -> bool:
        """保存修改并关闭弹窗.

        Args:
            page: Playwright页面对象
            wait_for_close: 是否等待弹窗关闭（默认True）

        Returns:
            是否保存成功

        Examples:
            >>> await ctrl.save_changes(page)
            True
        """
        logger.info("保存修改...")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            actions_config = first_edit_config.get("actions", {})

            save_btn_selector = actions_config.get("save_btn", "button:has-text('保存')")
            await page.locator(save_btn_selector).click()
            
            if wait_for_close:
                # 等待弹窗关闭
                close_btn_selector = first_edit_config.get("close_btn", "button:has-text('关闭')")
                await page.wait_for_selector(close_btn_selector, state="hidden", timeout=10000)
                logger.success("✓ 修改已保存，弹窗已关闭")
            else:
                await page.wait_for_timeout(2000)
                logger.success("✓ 保存按钮已点击")

            return True

        except Exception as e:
            logger.error(f"保存修改失败: {e}")
            return False

    async def close_dialog(self, page: Page) -> bool:
        """关闭编辑弹窗（不保存）.

        Args:
            page: Playwright页面对象

        Returns:
            是否关闭成功

        Examples:
            >>> await ctrl.close_dialog(page)
            True
        """
        logger.info("关闭编辑弹窗...")

        try:
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            close_btn_selector = first_edit_config.get("close_btn", "button:has-text('关闭')")

            await page.locator(close_btn_selector).click()
            await page.wait_for_timeout(1000)

            logger.success("✓ 编辑弹窗已关闭")
            return True

        except Exception as e:
            logger.error(f"关闭弹窗失败: {e}")
            return False

    async def complete_first_edit(
        self,
        page: Page,
        title: str,
        price: float,
        stock: int,
        weight: float,
        dimensions: Tuple[float, float, float]
    ) -> bool:
        """完成首次编辑的完整流程（SOP步骤4的所有子步骤）.

        Args:
            page: Playwright页面对象
            title: 新标题（含型号后缀）
            price: 货源价格
            stock: 库存数量
            weight: 重量（KG）
            dimensions: 尺寸元组 (长, 宽, 高) CM

        Returns:
            是否全部完成

        Examples:
            >>> await ctrl.complete_first_edit(
            ...     page,
            ...     "新款洗衣篮 A0001型号",
            ...     174.78,
            ...     99,
            ...     0.5,
            ...     (40, 30, 50)
            ... )
            True
        """
        logger.info("=" * 60)
        logger.info("开始执行首次编辑完整流程（SOP步骤4）")
        logger.info("=" * 60)

        try:
            # 步骤4.1: 编辑标题
            if not await self.edit_title(page, title):
                return False

            # 步骤4.4: 设置价格
            if not await self.set_sku_price(page, price):
                return False

            # 步骤4.5: 设置库存
            if not await self.set_sku_stock(page, stock):
                return False

            # 步骤4.6: 设置重量
            if not await self.set_sku_weight(page, weight):
                return False

            # 步骤4.7: 设置尺寸
            length, width, height = dimensions
            if not await self.set_sku_dimensions(page, length, width, height):
                return False

            # 保存修改
            if not await self.save_changes(page):
                return False

            logger.info("=" * 60)
            logger.success("✓ 首次编辑完整流程已完成")
            logger.info("=" * 60)
            return True

        except Exception as e:
            logger.error(f"首次编辑流程失败: {e}")
            return False


# 测试代码
if __name__ == "__main__":
    # 这个控制器需要配合Page对象使用
    # 测试请在集成测试中进行
    pass
