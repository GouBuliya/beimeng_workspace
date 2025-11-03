"""
@PURPOSE: 妙手采集箱控制器，负责导航和操作公用采集箱（基于SOP v2.0）
@OUTLINE:
  - class MiaoshouController: 妙手采集箱控制器主类
  - async def navigate_to_collection_box(): 导航到公用采集箱
  - async def search_products(): 搜索产品
  - async def select_products(): 选择产品
  - async def get_product_count(): 获取产品数量
  - async def click_edit_product_by_index(): 点击指定索引的产品编辑
  - async def claim_product(): 认领单个产品
  - async def claim_product_multiple_times(): 认领产品多次（SOP步骤5）
  - async def verify_claim_success(): 验证认领是否成功（SOP步骤6）
@GOTCHAS:
  - 使用文本定位器（text_locator）策略，提高稳定性
  - 产品列表是动态加载的
  - 需要确保已登录后再使用
  - 认领操作需要等待UI更新，避免操作过快
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

    async def navigate_to_collection_box(self, page: Page, use_sidebar: bool = False) -> bool:
        """导航到公用采集箱.

        Args:
            page: Playwright页面对象
            use_sidebar: 是否通过侧边栏导航（默认False，直接使用URL更可靠）

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
                # 方式1：通过侧边栏导航（可能不稳定）
                sidebar_config = self.selectors.get("sidebar_menu", {})
                collection_box_selector = sidebar_config.get("common_collection_box", "menuitem:has-text('公用采集箱')")

                logger.debug("点击侧边栏「公用采集箱」...")
                await page.locator(collection_box_selector).click()
                await page.wait_for_timeout(1000)

            else:
                # 方式2：直接导航到URL（推荐，更可靠）
                logger.debug(f"直接导航到: {target_url}")
                await page.goto(target_url, timeout=30000)

            # 等待页面加载
            await page.wait_for_load_state("domcontentloaded")

            # 验证是否成功
            if "common_collect_box/items" in page.url:
                logger.success("✓ 成功导航到公用采集箱")
                
                # 等待页面完全加载（弹窗、tab、产品列表）
                logger.debug("等待页面完全加载...")
                await page.wait_for_timeout(3000)
                
                # 关闭可能出现的弹窗（多次尝试，因为弹窗可能延迟出现）
                for attempt in range(3):
                    if await self.close_popup_if_exists(page):
                        break
                    if attempt < 2:
                        await page.wait_for_timeout(1000)
                
                return True
            else:
                logger.error(f"✗ 导航失败，当前URL: {page.url}")
                return False

        except Exception as e:
            logger.error(f"导航到公用采集箱失败: {e}")
            return False

    async def filter_and_search(self, page: Page, staff_name: str = None) -> bool:
        """筛选人员并执行搜索.
        
        在采集箱页面中，筛选指定人员的产品。
        
        Args:
            page: Playwright页面对象
            staff_name: 人员名称，如果为None则不筛选人员
            
        Returns:
            是否成功筛选和搜索
            
        Examples:
            >>> await ctrl.filter_and_search(page, "张三")
            True
        """
        logger.info(f"筛选人员并搜索: {staff_name or '(全部)'}")
        
        try:
            collection_box_config = self.selectors.get("collection_box", {})
            search_box_config = collection_box_config.get("search_box", {})
            
            # 如果指定了人员名称，先筛选人员
            if staff_name:
                logger.debug(f"筛选人员: {staff_name}")
                
                # 策略：直接通过索引定位"创建人员"选择框
                # 从截图可以看到：第二行左边是"创建人员：全部"的下拉框
                # 页面中的选择框顺序：第0个是"关联货源"，第1个是"创建人员"
                try:
                    logger.debug("查找'创建人员'选择框（第2个选择框）...")
                    
                    # 查找页面中所有的选择框
                    all_selects = page.locator(".jx-select")
                    select_count = await all_selects.count()
                    logger.debug(f"找到 {select_count} 个 jx-select 元素")
                    
                    if select_count < 2:
                        logger.warning(f"⚠️ 选择框数量不足，预期至少2个，实际 {select_count} 个")
                    else:
                        # 通常"创建人员"是第2个选择框（索引1）
                        staff_select = all_selects.nth(1)
                        
                        # 点击打开下拉菜单
                        logger.debug("点击'创建人员'选择框...")
                        await staff_select.click()
                        await page.wait_for_timeout(1000)
                        
                        # 检查下拉菜单是否出现
                        dropdown_count = await page.locator(".jx-select-dropdown, .jx-popper, [role='listbox']").count()
                        
                        if dropdown_count == 0:
                            logger.warning("⚠️ 下拉菜单未出现")
                        else:
                            logger.success("✓ 下拉菜单已打开")
                            
                            # 在下拉菜单中查找并点击指定人员
                            logger.debug(f"在下拉菜单中查找人员: {staff_name}")
                            await page.wait_for_timeout(500)
                            
                            # 尝试多种选择器来定位人员选项
                            staff_option_selectors = [
                                f"li:has-text('{staff_name}')",
                                f".jx-select-dropdown__item:has-text('{staff_name}')",
                                f".jx-option:has-text('{staff_name}')",
                                f"[role='option']:has-text('{staff_name}')",
                                f"div:has-text('{staff_name}')"
                            ]
                            
                            staff_option_clicked = False
                            for selector in staff_option_selectors:
                                try:
                                    elements = await page.locator(selector).all()
                                    if len(elements) > 0:
                                        logger.debug(f"找到 {len(elements)} 个匹配'{staff_name}'的选项: {selector}")
                                        # 点击第一个匹配的选项
                                        await elements[0].click()
                                        await page.wait_for_timeout(500)
                                        staff_option_clicked = True
                                        logger.success(f"✓ 已选择人员: {staff_name}")
                                        break
                                except Exception as e:
                                    logger.debug(f"选择器 {selector} 点击失败: {e}")
                                    continue
                            
                            if not staff_option_clicked:
                                logger.warning(f"⚠️ 未找到人员选项: {staff_name}")
                
                except Exception as e:
                    logger.error(f"人员筛选过程出错: {e}")
                    logger.warning("⚠️ 人员筛选失败，但继续执行")
            
            # 点击搜索按钮
            logger.debug("点击搜索按钮...")
            search_btn_selector = search_box_config.get("search_btn", "button:has-text('搜索')")
            
            search_btn_count = await page.locator(search_btn_selector).count()
            if search_btn_count == 0:
                logger.error("✗ 未找到搜索按钮")
                return False
            
            await page.locator(search_btn_selector).first.click()
            await page.wait_for_timeout(2000)  # 等待搜索结果加载
            
            logger.success(f"✓ 已筛选并搜索{f': {staff_name}' if staff_name else ''}")
            return True
            
        except Exception as e:
            logger.error(f"筛选和搜索失败: {e}")
            return False

    async def close_popup_if_exists(self, page: Page) -> bool:
        """关闭可能出现的弹窗（如"我知道了"等提示）.

        Args:
            page: Playwright页面对象

        Returns:
            是否找到并关闭了弹窗

        Examples:
            >>> await ctrl.close_popup_if_exists(page)
            True
        """
        try:
            # 常见的弹窗关闭按钮文本
            popup_buttons = [
                "text='我知道了'",
                "text='知道了'",
                "text='确定'",
                "text='关闭'",
                "button[aria-label='关闭']",
                "button[aria-label='Close']",
            ]

            for selector in popup_buttons:
                try:
                    locator = page.locator(selector)
                    if await locator.count() > 0:
                        logger.debug(f"发现弹窗按钮: {selector}")
                        await locator.first.click(timeout=2000)
                        await page.wait_for_timeout(1000)
                        logger.success(f"✓ 已关闭弹窗: {selector}")
                        return True
                except Exception:
                    continue

            logger.debug("未发现需要关闭的弹窗")
            return False

        except Exception as e:
            logger.warning(f"关闭弹窗时出错（可忽略）: {e}")
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

            # tab名称映射（英文 -> 中文）
            tab_name_map = {
                "all": "全部",
                "unclaimed": "未认领",
                "claimed": "已认领",
                "failed": "失败"
            }
            
            # 定义fallback选择器列表（参考test_quick_edit.py的策略）
            selectors = [
                tabs_config[tab_name],  # CSS类选择器：.jx-radio-button:has-text('全部')
                f"text=/{tab_name_map[tab_name]}.*\\(\\d+\\)/",  # 正则：全部 (7657)
                f"text='{tab_name_map[tab_name]}'"  # 简单文本：全部
            ]
            
            # 等待页面加载完成（等待任何一个tab出现）
            logger.debug(f"等待tab区域加载...")
            try:
                await page.wait_for_selector(
                    tabs_config.get('all', '.jx-radio-button:has-text("全部")'),
                    timeout=10000,
                    state="visible"
                )
            except Exception as wait_error:
                logger.warning(f"等待tab出现超时，继续尝试...")
            
            # 尝试多个选择器（fallback策略）
            clicked = False
            for i, selector in enumerate(selectors):
                logger.debug(f"尝试选择器 {i+1}/{len(selectors)}: {selector}")
                try:
                    # 先检查是否存在
                    count = await page.locator(selector).count()
                    if count == 0:
                        logger.debug(f"选择器 {i+1} 未找到元素")
                        continue
                    
                    # 尝试点击
                    await page.locator(selector).first.click(timeout=3000)
                    clicked = True
                    logger.success(f"✓ 使用选择器 {i+1} 成功点击")
                    break
                except Exception as e:
                    logger.debug(f"选择器 {i+1} 点击失败: {str(e)[:80]}...")
                    if i < len(selectors) - 1:
                        continue
                    else:
                        # 最后一次尝试：强制点击第一个选择器
                        logger.debug("所有选择器失败，尝试强制点击...")
                        try:
                            await page.locator(selectors[0]).first.click(force=True, timeout=3000)
                            clicked = True
                            logger.success("✓ 强制点击成功")
                        except Exception as force_error:
                            logger.error(f"强制点击也失败: {force_error}")
            
            if not clicked:
                logger.error(f"✗ 所有选择器都失败，无法切换到「{tab_name}」tab")
                return False
            
            # 等待列表刷新（参考test_quick_edit.py的成功策略）
            await page.wait_for_timeout(1000)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                # networkidle超时不影响继续执行
                pass

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
            
            # 使用更精确的选择器，避免strict mode violation
            # 优先使用复选框的label，而不是纯文本定位
            select_all_selectors = [
                ".jx-pagination__total .jx-checkbox__label",  # 分页器左侧的全选checkbox
                "label.jx-checkbox:has-text('全选')",
                ".jx-checkbox__label:has-text('全选')",
                "text='全选'"
            ]
            
            clicked = False
            for selector in select_all_selectors:
                try:
                    locator = page.locator(selector).first
                    if await locator.count() > 0:
                        await locator.click()
                        clicked = True
                        logger.debug(f"使用选择器成功全选: {selector}")
                        break
                except Exception as e:
                    logger.debug(f"选择器 {selector} 失败: {e}")
                    continue
            
            if not clicked:
                raise Exception("所有全选选择器都失败")
            
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

    async def click_edit_product_by_index(self, page: Page, index: int) -> bool:
        """点击指定索引的产品编辑按钮.

        Args:
            page: Playwright页面对象
            index: 产品索引（从0开始）

        Returns:
            是否成功打开编辑弹窗

        Examples:
            >>> await ctrl.click_edit_product_by_index(page, 2)  # 编辑第3个产品
            True
        """
        logger.info(f"点击第{index+1}个产品的编辑按钮...")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            product_list_config = collection_box_config.get("product_list", {})

            # 指定索引的产品编辑按钮
            edit_btn_selector = product_list_config.get("edit_btn_template", "button:has-text('编辑')")
            edit_buttons = page.locator(edit_btn_selector)
            
            # 检查是否有足够的产品
            count = await edit_buttons.count()
            if count <= index:
                logger.error(f"✗ 产品数量不足，当前只有{count}个产品")
                return False
            
            # 点击指定索引的编辑按钮
            await edit_buttons.nth(index).click()
            await page.wait_for_timeout(2000)  # 等待弹窗加载

            # 验证弹窗是否打开
            first_edit_config = self.selectors.get("first_edit_dialog", {})
            close_btn_selector = first_edit_config.get("close_btn", "button:has-text('关闭')")

            if await page.locator(close_btn_selector).first.is_visible():
                logger.success(f"✓ 第{index+1}个产品编辑弹窗已打开")
                return True
            else:
                logger.error("✗ 编辑弹窗未打开")
                return False

        except Exception as e:
            logger.error(f"打开编辑弹窗失败: {e}")
            return False

    async def claim_product(self, page: Page, product_index: int = 0) -> bool:
        """认领单个产品（SOP步骤5）.

        通过点击产品的"认领到"按钮来认领产品。
        
        Args:
            page: Playwright页面对象
            product_index: 产品索引（从0开始，默认第一个）

        Returns:
            是否认领成功

        Examples:
            >>> await ctrl.claim_product(page, 0)  # 认领第1个产品
            True
        """
        logger.info(f"认领第{product_index+1}个产品...")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            product_list_config = collection_box_config.get("product_list", {})

            # 定位"认领到"按钮
            claim_btn_selector = product_list_config.get("claim_to_btn_template", "button:has-text('认领到')")
            claim_buttons = page.locator(claim_btn_selector)
            
            # 检查是否有足够的产品
            count = await claim_buttons.count()
            if count <= product_index:
                logger.error(f"✗ 产品数量不足，当前只有{count}个产品")
                return False
            
            # 点击指定产品的认领按钮
            await claim_buttons.nth(product_index).click()
            await page.wait_for_timeout(1000)  # 等待认领操作完成

            logger.success(f"✓ 第{product_index+1}个产品认领成功")
            return True

        except Exception as e:
            logger.error(f"认领产品失败: {e}")
            return False

    async def claim_product_multiple_times(
        self,
        page: Page,
        product_index: int,
        times: int = 4
    ) -> bool:
        """认领产品多次（SOP步骤5 - 每条链接认领4次）.

        Args:
            page: Playwright页面对象
            product_index: 产品索引（从0开始）
            times: 认领次数（默认4次，符合SOP）

        Returns:
            是否全部认领成功

        Examples:
            >>> await ctrl.claim_product_multiple_times(page, 0, 4)  # 第1个产品认领4次
            True
        """
        logger.info(f"开始认领第{product_index+1}个产品{times}次...")

        try:
            success_count = 0
            
            for i in range(times):
                logger.debug(f"  [{i+1}/{times}] 认领中...")
                
                if await self.claim_product(page, product_index):
                    success_count += 1
                    # 每次认领后等待一下，避免操作过快
                    await page.wait_for_timeout(500)
                else:
                    logger.warning(f"  ⚠️  第{i+1}次认领失败")
            
            if success_count == times:
                logger.success(f"✓ 第{product_index+1}个产品已成功认领{success_count}次")
                return True
            else:
                logger.warning(f"⚠️  第{product_index+1}个产品认领了{success_count}/{times}次")
                return False

        except Exception as e:
            logger.error(f"多次认领失败: {e}")
            return False

    async def verify_claim_success(
        self,
        page: Page,
        expected_count: int = 20
    ) -> bool:
        """验证认领是否成功（SOP步骤6）.

        通过检查"已认领"tab的数量来验证。
        SOP要求：5条链接×4次认领=20条产品
        
        Args:
            page: Playwright页面对象
            expected_count: 期望的产品数量（默认20）

        Returns:
            是否达到预期数量

        Examples:
            >>> await ctrl.verify_claim_success(page, 20)
            True
        """
        logger.info(f"验证认领结果（期望数量: {expected_count}）...")

        try:
            # 切换到"已认领"tab
            await self.switch_tab(page, "claimed")
            await page.wait_for_timeout(1000)
            
            # 获取产品数量
            counts = await self.get_product_count(page)
            claimed_count = counts.get("claimed", 0)
            
            if claimed_count >= expected_count:
                logger.success(f"✓ 认领验证成功！已认领数量: {claimed_count}（期望≥{expected_count}）")
                return True
            else:
                logger.error(f"✗ 认领验证失败！已认领数量: {claimed_count}（期望≥{expected_count}）")
                return False

        except Exception as e:
            logger.error(f"验证认领失败: {e}")
            return False

    async def navigate_and_filter_collection_box(
        self,
        page: Page,
        filter_by_user: Optional[str] = None,
        switch_to_tab: str = "all"
    ) -> bool:
        """导航到妙手采集箱并应用筛选（工业化版本）.
        
        完整流程：
        1. 导航到公用采集箱
        2. 筛选创建人员（如果指定）
        3. 切换到指定tab
        4. 验证商品列表加载成功
        
        Args:
            page: Playwright页面对象
            filter_by_user: 创建人员筛选（如"张三(zhangsan123)"）
            switch_to_tab: 切换到的tab（all/unclaimed/claimed/failed）
            
        Returns:
            是否成功导航和筛选
            
        Examples:
            >>> # 导航并筛选自己的商品
            >>> await ctrl.navigate_and_filter_collection_box(
            ...     page,
            ...     filter_by_user="张三(zhangsan123)",
            ...     switch_to_tab="all"
            ... )
            True
        """
        logger.info("=" * 80)
        logger.info("【导航妙手采集箱】完整流程")
        logger.info("=" * 80)
        
        try:
            # 步骤1: 导航到公用采集箱
            logger.info("\n>>> 步骤1: 导航到公用采集箱...")
            if not await self.navigate_to_collection_box(page):
                logger.error("✗ 导航失败")
                return False
            
            logger.success("✓ 成功导航到采集箱")
            await page.wait_for_timeout(1000)
            
            # 步骤2: 筛选创建人员（如果指定）
            if filter_by_user:
                logger.info(f"\n>>> 步骤2: 筛选创建人员 - {filter_by_user}...")
                
                # 查找创建人员下拉框
                user_filter_selectors = [
                    "select:has-text('创建人员')",
                    ".jx-select:has-text('创建人员')",
                    "label:has-text('创建人员') + .jx-select",
                    "xpath=//label[contains(text(), '创建人员')]/following-sibling::*//input"
                ]
                
                filter_applied = False
                for selector in user_filter_selectors:
                    try:
                        count = await page.locator(selector).count()
                        if count > 0:
                            # 点击下拉框
                            await page.locator(selector).first.click()
                            await page.wait_for_timeout(500)
                            
                            # 选择用户
                            user_option = page.locator(f"text=/{filter_by_user}/")
                            if await user_option.count() > 0:
                                await user_option.first.click()
                                await page.wait_for_timeout(500)
                                
                                # 点击搜索按钮
                                search_btn = page.locator("button:has-text('搜索')")
                                if await search_btn.count() > 0:
                                    await search_btn.first.click()
                                    await page.wait_for_timeout(1000)
                                
                                filter_applied = True
                                logger.success(f"✓ 已筛选用户: {filter_by_user}")
                                break
                    except Exception as e:
                        logger.debug(f"尝试筛选器 {selector} 失败: {e}")
                        continue
                
                if not filter_applied:
                    logger.warning(f"⚠️  未能应用用户筛选，将显示所有用户的商品")
            else:
                logger.info("\n>>> 步骤2: 跳过用户筛选")
            
            # 步骤3: 切换到指定tab
            logger.info(f"\n>>> 步骤3: 切换到「{switch_to_tab}」tab...")
            if not await self.switch_tab(page, switch_to_tab):
                logger.error(f"✗ 切换tab失败")
                return False
            
            logger.success(f"✓ 已切换到「{switch_to_tab}」tab")
            await page.wait_for_timeout(1000)
            
            # 步骤4: 验证商品列表加载
            logger.info("\n>>> 步骤4: 验证商品列表...")
            counts = await self.get_product_count(page)
            
            if counts[switch_to_tab] > 0:
                logger.success(f"✓ 商品列表已加载，共 {counts[switch_to_tab]} 个商品")
            else:
                logger.warning(f"⚠️  当前tab没有商品")
            
            logger.info("\n" + "=" * 80)
            logger.info("【导航完成】妙手采集箱已就绪")
            logger.info("=" * 80 + "\n")
            
            return True
            
        except Exception as e:
            logger.error(f"导航和筛选失败: {e}")
            logger.exception("详细错误:")
            return False
    
    async def verify_collected_products(
        self,
        page: Page,
        expected_count: int,
        product_keywords: Optional[List[str]] = None,
        check_details: bool = False
    ) -> Dict:
        """验证采集箱中的商品（工业化版本）.
        
        验证内容：
        1. 商品数量是否达到预期
        2. 商品标题是否包含关键词（可选）
        3. 商品详细信息（可选）
        
        Args:
            page: Playwright页面对象
            expected_count: 期望的商品数量
            product_keywords: 商品关键词列表（用于验证）
            check_details: 是否检查商品详细信息
            
        Returns:
            验证结果字典：
            - success: 是否验证成功
            - actual_count: 实际商品数量
            - expected_count: 期望商品数量
            - keywords_matched: 关键词匹配数量
            - details: 详细信息（如果启用）
            
        Examples:
            >>> result = await ctrl.verify_collected_products(
            ...     page,
            ...     expected_count=5,
            ...     product_keywords=["药箱", "收纳盒"]
            ... )
            >>> print(f"验证结果: {result['success']}")
        """
        logger.info("=" * 80)
        logger.info(f"【验证采集结果】期望数量: {expected_count}")
        logger.info("=" * 80)
        
        result = {
            "success": False,
            "actual_count": 0,
            "expected_count": expected_count,
            "keywords_matched": 0,
            "details": []
        }
        
        try:
            # 1. 获取当前商品数量
            logger.info("\n>>> 步骤1: 检查商品数量...")
            counts = await self.get_product_count(page)
            actual_count = counts.get("all", 0)
            result["actual_count"] = actual_count
            
            if actual_count < expected_count:
                logger.error(f"✗ 商品数量不足: {actual_count} < {expected_count}")
                return result
            
            logger.success(f"✓ 商品数量满足要求: {actual_count} ≥ {expected_count}")
            
            # 2. 验证商品关键词（如果提供）
            if product_keywords:
                logger.info(f"\n>>> 步骤2: 验证商品关键词...")
                
                # 获取商品列表
                product_items = await page.locator(".product-item, .goods-item, [data-product-id]").all()
                
                matched_count = 0
                for i, item in enumerate(product_items[:expected_count]):
                    try:
                        title = await item.locator(".title, .product-title, h3").first.inner_text()
                        
                        # 检查是否包含任何关键词
                        has_keyword = any(keyword in title for keyword in product_keywords)
                        if has_keyword:
                            matched_count += 1
                            logger.debug(f"  ✓ 商品 {i+1}: {title[:40]}... (包含关键词)")
                        else:
                            logger.warning(f"  ⚠️  商品 {i+1}: {title[:40]}... (不包含关键词)")
                    except Exception as e:
                        logger.debug(f"  获取商品 {i+1} 标题失败: {e}")
                
                result["keywords_matched"] = matched_count
                
                if matched_count >= expected_count * 0.8:  # 80%匹配率
                    logger.success(f"✓ 关键词匹配: {matched_count}/{expected_count}")
                else:
                    logger.warning(f"⚠️  关键词匹配率较低: {matched_count}/{expected_count}")
            
            # 3. 检查商品详细信息（如果启用）
            if check_details:
                logger.info(f"\n>>> 步骤3: 检查商品详细信息...")
                
                product_items = await page.locator(".product-item, .goods-item, [data-product-id]").all()
                
                for i, item in enumerate(product_items[:expected_count]):
                    try:
                        title = await item.locator(".title, .product-title, h3").first.inner_text()
                        price = await item.locator(".price, .product-price").first.inner_text()
                        
                        detail = {
                            "index": i + 1,
                            "title": title,
                            "price": price
                        }
                        result["details"].append(detail)
                        
                        logger.debug(f"  商品 {i+1}: {title[:30]}... - {price}")
                    except Exception as e:
                        logger.debug(f"  获取商品 {i+1} 详情失败: {e}")
            
            # 验证成功
            result["success"] = True
            
            logger.info("\n" + "=" * 80)
            logger.success("【验证完成】采集结果符合预期")
            logger.info(f"  实际数量: {result['actual_count']}")
            logger.info(f"  期望数量: {result['expected_count']}")
            if product_keywords:
                logger.info(f"  关键词匹配: {result['keywords_matched']}/{expected_count}")
            logger.info("=" * 80 + "\n")
            
            return result
            
        except Exception as e:
            logger.error(f"验证采集结果失败: {e}")
            logger.exception("详细错误:")
            return result


# 测试代码
if __name__ == "__main__":
    # 这个控制器需要配合Page对象使用
    # 测试请在集成测试中进行
    pass

