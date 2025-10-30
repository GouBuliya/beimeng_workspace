"""
@PURPOSE: 妙手采集箱控制器，负责导航和操作公用采集箱（基于SOP v2.0）
@OUTLINE:
  - class MiaoshouController: 妙手采集箱控制器主类
  - async def navigate_to_collection_box(): 导航到公用采集箱
  - async def search_products(): 搜索产品
  - async def select_products(): 选择产品
  - async def get_product_count(): 获取产品数量
@GOTCHAS:
  - 使用aria-ref定位元素（妙手ERP特有）
  - 产品列表是动态加载的
  - 需要确保已登录后再使用
@DEPENDENCIES:
  - 内部: browser_manager, login_controller
  - 外部: playwright, loguru
@RELATED: login_controller.py, first_edit_controller.py
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from playwright.async_api import Page


class MiaoshouController:
    """妙手采集箱控制器（基于SOP流程）.

    负责妙手ERP公用采集箱的导航和操作：
    - 导航到公用采集箱
    - 搜索和筛选产品
    - 选择产品
    - 批量操作

    Attributes:
        selectors: 妙手ERP选择器配置

    Examples:
        >>> ctrl = MiaoshouController()
        >>> await ctrl.navigate_to_collection_box(page)
    """

    def __init__(self, selector_path: str = "config/miaoshou_selectors_v2.json"):
        """初始化妙手控制器.

        Args:
            selector_path: 选择器配置文件路径（默认使用v2文本定位器版本）
        """
        self.selector_path = Path(selector_path)
        self.selectors = self._load_selectors()
        logger.info("妙手控制器初始化（SOP v2.0 - 文本定位器）")

    def _load_selectors(self) -> dict:
        """加载选择器配置.

        Returns:
            选择器配置字典
        """
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

    async def navigate_to_collection_box(self, page: Page, use_sidebar: bool = True) -> bool:
        """导航到公用采集箱.

        Args:
            page: Playwright页面对象
            use_sidebar: 是否通过侧边栏导航（默认True，更可靠）

        Returns:
            是否成功导航

        Examples:
            >>> await ctrl.navigate_to_collection_box(page)
            True
        """
        logger.info("导航到公用采集箱...")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            target_url = collection_box_config.get("url", "https://erp.91miaoshou.com/common_collect_box/items")

            if use_sidebar:
                # 方式1：通过侧边栏导航（推荐）
                sidebar_config = self.selectors.get("sidebar_menu", {})
                collection_box_selector = sidebar_config.get("common_collection_box", "menuitem:has-text('公用采集箱')")

                logger.debug("点击侧边栏「公用采集箱」...")
                await page.locator(collection_box_selector).click()
                await page.wait_for_timeout(1000)

            else:
                # 方式2：直接导航到URL
                logger.debug(f"直接导航到: {target_url}")
                await page.goto(target_url, timeout=30000)

            # 等待页面加载
            await page.wait_for_load_state("domcontentloaded")

            # 验证是否成功
            if "common_collect_box/items" in page.url:
                logger.success("✓ 成功导航到公用采集箱")
                
                # 等待产品列表加载
                await page.wait_for_timeout(2000)
                
                return True
            else:
                logger.error(f"✗ 导航失败，当前URL: {page.url}")
                return False

        except Exception as e:
            logger.error(f"导航到公用采集箱失败: {e}")
            return False

    async def get_product_count(self, page: Page) -> Dict[str, int]:
        """获取产品数量统计.

        Args:
            page: Playwright页面对象

        Returns:
            包含各状态产品数量的字典：{
                "all": 总数,
                "unclaimed": 未认领,
                "claimed": 已认领,
                "failed": 失败
            }

        Examples:
            >>> counts = await ctrl.get_product_count(page)
            >>> print(f"已认领: {counts['claimed']}")
        """
        logger.info("获取产品数量...")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            tabs_config = collection_box_config.get("tabs", {})

            counts = {}

            # 优化：使用正则表达式匹配完整的tab文本（包含数字）
            import re
            
            # 定义tab名称映射
            tab_patterns = {
                "all": r"全部.*\((\d+)\)",
                "unclaimed": r"未认领.*\((\d+)\)",
                "claimed": r"已认领.*\((\d+)\)",
                "failed": r"(采集失败|失败).*\((\d+)\)",
            }
            
            for status, pattern in tab_patterns.items():
                try:
                    # 查找匹配的元素
                    tab_locator = page.locator(f"text=/{pattern}/")
                    count = await tab_locator.count()
                    
                    if count > 0:
                        tab_text = await tab_locator.first.text_content(timeout=3000)
                        match = re.search(r"\((\d+)\)", tab_text or "")
                        if match:
                            counts[status] = int(match.group(1))
                        else:
                            counts[status] = 0
                    else:
                        counts[status] = 0
                except Exception as e:
                    logger.debug(f"获取{status}数量失败: {e}")
                    counts[status] = 0

            logger.success(f"✓ 产品统计: {counts}")
            return counts

        except Exception as e:
            logger.error(f"获取产品数量失败: {e}")
            return {"all": 0, "unclaimed": 0, "claimed": 0, "failed": 0}

    async def switch_tab(self, page: Page, tab_name: str) -> bool:
        """切换产品列表tab.

        Args:
            page: Playwright页面对象
            tab_name: tab名称，可选值: "all", "unclaimed", "claimed", "failed"

        Returns:
            是否切换成功

        Examples:
            >>> await ctrl.switch_tab(page, "claimed")
            True
        """
        logger.info(f"切换到「{tab_name}」tab...")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            tabs_config = collection_box_config.get("tabs", {})

            if tab_name not in tabs_config:
                logger.error(f"✗ 无效的tab名称: {tab_name}")
                return False

            selector = tabs_config[tab_name]
            await page.locator(selector).click()
            await page.wait_for_timeout(1500)  # 等待列表刷新

            logger.success(f"✓ 已切换到「{tab_name}」tab")
            return True

        except Exception as e:
            logger.error(f"切换tab失败: {e}")
            return False

    async def search_products(
        self,
        page: Page,
        title: Optional[str] = None,
        source_id: Optional[str] = None,
        price_min: Optional[float] = None,
        price_max: Optional[float] = None,
    ) -> bool:
        """搜索产品.

        Args:
            page: Playwright页面对象
            title: 产品标题（模糊搜索）
            source_id: 货源ID
            price_min: 最低价格
            price_max: 最高价格

        Returns:
            是否搜索成功

        Examples:
            >>> await ctrl.search_products(page, title="洗衣篮")
            True
        """
        logger.info("搜索产品...")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            search_config = collection_box_config.get("search_box", {})

            # 填写搜索条件
            if title:
                logger.debug(f"填写标题: {title}")
                title_selector = search_config.get("product_title", "input[placeholder*='标题']")
                await page.locator(title_selector).fill(title)
                await page.wait_for_timeout(300)

            if source_id:
                logger.debug(f"填写货源ID: {source_id}")
                id_selector = search_config.get("source_id", "input[placeholder*='ID']")
                await page.locator(id_selector).fill(source_id)
                await page.wait_for_timeout(300)

            if price_min is not None:
                logger.debug(f"填写最低价格: {price_min}")
                min_selector = search_config.get("source_price_min", "input[placeholder*='最低']")
                await page.locator(min_selector).fill(str(price_min))
                await page.wait_for_timeout(300)

            if price_max is not None:
                logger.debug(f"填写最高价格: {price_max}")
                max_selector = search_config.get("source_price_max", "input[placeholder*='最高']")
                await page.locator(max_selector).fill(str(price_max))
                await page.wait_for_timeout(300)

            # 点击搜索按钮
            search_btn_selector = search_config.get("search_btn", "button:has-text('搜索')")
            await page.locator(search_btn_selector).click()
            await page.wait_for_timeout(2000)  # 等待搜索结果加载

            logger.success("✓ 搜索完成")
            return True

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return False

    async def select_all_products(self, page: Page) -> bool:
        """全选当前页的所有产品.

        Args:
            page: Playwright页面对象

        Returns:
            是否成功全选

        Examples:
            >>> await ctrl.select_all_products(page)
            True
        """
        logger.info("全选产品...")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            pagination_config = collection_box_config.get("pagination", {})
            
            select_all_selector = pagination_config.get("select_all", "text='全选'")
            await page.locator(select_all_selector).click()
            await page.wait_for_timeout(500)

            logger.success("✓ 已全选产品")
            return True

        except Exception as e:
            logger.error(f"全选产品失败: {e}")
            return False

    async def click_edit_first_product(self, page: Page) -> bool:
        """点击第一个产品的编辑按钮，进入首次编辑页面.

        Args:
            page: Playwright页面对象

        Returns:
            是否成功打开编辑弹窗

        Examples:
            >>> await ctrl.click_edit_first_product(page)
            True
        """
        logger.info("点击第一个产品的编辑按钮...")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            product_list_config = collection_box_config.get("product_list", {})

            # 第一个产品的编辑按钮
            edit_btn_selector = product_list_config.get("edit_btn_template", "button:has-text('编辑')")
            await page.locator(edit_btn_selector).first.click()
            await page.wait_for_timeout(2000)  # 等待弹窗加载

            # 验证弹窗是否打开
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            close_btn_selector = first_edit_config.get("close_btn", "button:has-text('关闭')")

            if await page.locator(close_btn_selector).is_visible():
                logger.success("✓ 编辑弹窗已打开")
                return True
            else:
                logger.error("✗ 编辑弹窗未打开")
                return False

        except Exception as e:
            logger.error(f"打开编辑弹窗失败: {e}")
            return False


# 测试代码
if __name__ == "__main__":
    # 这个控制器需要配合Page对象使用
    # 测试请在集成测试中进行
    pass
