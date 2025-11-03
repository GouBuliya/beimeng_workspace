"""
@PURPOSE: 批量编辑控制器（改进版），负责Temu全托管采集箱的批量编辑18步流程
@OUTLINE:
  - class BatchEditController: 批量编辑控制器主类
  - async def navigate_to_batch_edit(): 导航并进入批量编辑
  - async def execute_all_steps(): 执行18步完整流程
  - async def click_step(): 智能点击步骤（处理遮挡）
  - async def click_preview_and_save(): 点击预览和保存
  - 各步骤的具体实现方法
@GOTCHAS:
  - 某些步骤（主货号、平台SKU）可能被遮挡，需要force点击
  - 保存按钮可能在页面底部，需要滚动
  - 每步操作后需要等待UI更新
@DEPENDENCIES:
  - 内部: browser_manager
  - 外部: playwright, loguru
@RELATED: miaoshou_controller.py, first_edit_controller.py
"""

import asyncio
import random
from typing import Optional, Dict, Any
from pathlib import Path
from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


class BatchEditController:
    """批量编辑控制器（改进版）.
    
    实现SOP步骤7的18步批量编辑流程，处理遮挡和选择器问题。
    
    Attributes:
        page: Playwright页面对象
        temu_box_url: Temu全托管采集箱URL
        
    Examples:
        >>> controller = BatchEditController(page)
        >>> await controller.navigate_to_batch_edit()
        >>> result = await controller.execute_all_steps(product_data)
    """
    
    def __init__(self, page: Page):
        """初始化控制器.
        
        Args:
            page: Playwright页面对象
        """
        self.page = page
        self.temu_box_url = "https://erp.91miaoshou.com/pddkj/collect_box/items"
        logger.info("批量编辑控制器已初始化（改进版）")
    
    async def navigate_to_batch_edit(self, select_count: int = 20) -> bool:
        """导航到批量编辑页面.
        
        Args:
            select_count: 选择的产品数量（默认20）
            
        Returns:
            是否成功进入批量编辑
        """
        logger.info("=" * 60)
        logger.info("导航到批量编辑页面")
        logger.info("=" * 60)
        
        try:
            # 1. 导航到Temu全托管采集箱
            logger.info(f"导航到: {self.temu_box_url}")
            await self.page.goto(self.temu_box_url, timeout=60000)
            await self.page.wait_for_load_state("networkidle", timeout=60000)
            await self.page.wait_for_timeout(3000)
            
            # 2. 全选产品
            logger.info(f"选择 {select_count} 个产品...")
            try:
                # 尝试多个选择器
                select_all_selectors = [
                    "text='全选'",
                    "button:has-text('全选')",
                    "label:has-text('全选')",
                    ".jx-checkbox:has-text('全选')"
                ]
                
                selected = False
                for selector in select_all_selectors:
                    try:
                        btn = self.page.locator(selector).first
                        if await btn.count() > 0:
                            await btn.click(timeout=10000)
                            await self.page.wait_for_timeout(1000)
                            logger.success("✓ 已全选产品")
                            selected = True
                            break
                    except:
                        continue
                
                if not selected:
                    logger.warning("全选失败，尝试手动勾选前20个...")
                    # 备用方案：手动勾选
                    checkboxes = self.page.locator(".jx-table__body .jx-checkbox").first
                    for i in range(min(20, await checkboxes.count())):
                        try:
                            await checkboxes.nth(i).click()
                            await self.page.wait_for_timeout(100)
                        except:
                            pass
                    logger.info("✓ 已手动勾选产品")
                    
            except Exception as e:
                logger.warning(f"选择产品失败: {e}")
                return False
            
            # 3. 点击批量编辑按钮
            logger.info("点击批量编辑按钮...")
            try:
                batch_edit_btn = self.page.locator("button:has-text('批量编辑')").first
                await batch_edit_btn.click(timeout=10000)
                await self.page.wait_for_timeout(3000)
                logger.success("✓ 已进入批量编辑页面")
            except Exception as e:
                logger.error(f"无法进入批量编辑: {e}")
                return False
            
            # 4. 验证是否进入
            try:
                # 检查是否有步骤导航
                title_step = self.page.locator("text='标题'").first
                if await title_step.count() > 0:
                    logger.success("✓ 批量编辑页面加载成功")
                    return True
            except:
                pass
            
            logger.warning("⚠️ 可能未正确进入批量编辑页面")
            return False
            
        except Exception as e:
            logger.error(f"导航失败: {e}")
            return False
    
    async def click_step(self, step_name: str, step_num: str) -> bool:
        """智能点击步骤（处理遮挡问题）.
        
        Args:
            step_name: 步骤名称（如：标题、重量）
            step_num: 步骤编号（如：7.1）
            
        Returns:
            是否成功点击
        """
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"[步骤 {step_num}] {step_name}")
        logger.info(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        try:
            # 1. 尝试多个选择器定位步骤
            selectors = [
                f"text='{step_name}'",
                f"button:has-text('{step_name}')",
                f"a:has-text('{step_name}')",
                f".step-item:has-text('{step_name}')",
                f"div:has-text('{step_name}')"
            ]
            
            step_elem = None
            for selector in selectors:
                try:
                    elem = self.page.locator(selector).first
                    if await elem.count() > 0:
                        step_elem = elem
                        logger.debug(f"  使用选择器: {selector}")
                        break
                except:
                    continue
            
            if not step_elem:
                logger.error(f"  ✗ 未找到步骤: {step_name}")
                return False
            
            # 2. 滚动到元素位置
            try:
                await step_elem.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(500)
            except:
                pass
            
            # 3. 点击步骤（处理遮挡情况）
            try:
                await step_elem.click(timeout=5000)
                logger.success(f"  ✓ 已点击步骤导航")
            except PlaywrightTimeoutError:
                logger.warning(f"  ⚠️ 元素被遮挡，尝试强制点击...")
                try:
                    await step_elem.click(force=True)
                    logger.success(f"  ✓ 强制点击成功")
                except Exception as e:
                    logger.error(f"  ✗ 强制点击也失败: {e}")
                    return False
            
            # 4. 等待页面内容加载（重要！增加等待时间）
            logger.info(f"  ⏳ 等待步骤页面加载...")
            await self.page.wait_for_timeout(3000)  # 从1.5秒增加到3秒
            
            # 5. 验证页面是否加载（检查预览和保存按钮）
            try:
                preview_btn = self.page.locator("button:has-text('预览')").first
                if await preview_btn.count() > 0:
                    logger.success(f"  ✓ 步骤页面已加载")
                else:
                    logger.warning(f"  ⚠️ 未检测到预览按钮，可能页面未完全加载")
            except:
                pass
            
            return True
            
        except Exception as e:
            logger.error(f"  ✗ 点击失败: {e}")
            return False
    
    async def click_preview_and_save(self, step_name: str) -> bool:
        """点击预览和保存按钮（先预览，再保存）.
        
        Args:
            step_name: 步骤名称（用于日志）
            
        Returns:
            是否成功保存
        """
        try:
            # ========================================
            # 第1步：点击预览
            # ========================================
            logger.info(f"  📋 第1步：点击预览...")
            preview_selectors = [
                "button:has-text('预览')",
                "button.el-button:has-text('预览')",
                "button[type='button']:has-text('预览')",
            ]
            
            preview_clicked = False
            for selector in preview_selectors:
                try:
                    # 获取所有匹配的按钮
                    all_btns = await self.page.locator(selector).all()
                    logger.debug(f"  预览选择器 {selector} 找到 {len(all_btns)} 个")
                    
                    # 找到第一个可见的按钮
                    for btn in all_btns:
                        if await btn.is_visible():
                            # 滚动到预览按钮
                            await btn.scroll_into_view_if_needed()
                            await self.page.wait_for_timeout(300)
                            
                            # 点击预览
                            await btn.click()
                            logger.success(f"  ✓ 预览按钮已点击")
                            
                            # 等待预览加载完成（重要！）
                            await self.page.wait_for_timeout(2000)
                            logger.info(f"  ⏳ 等待预览加载...")
                            
                            preview_clicked = True
                            break
                    
                    if preview_clicked:
                        break
                        
                except Exception as e:
                    logger.debug(f"    预览选择器 {selector} 失败: {e}")
                    continue
            
            if not preview_clicked:
                logger.warning(f"  ⚠️ 未找到预览按钮，跳过预览直接保存")
            else:
                logger.success(f"  ✓ 预览完成")
            
            # ========================================
            # 第2步：点击保存修改
            # ========================================
            logger.info(f"  💾 第2步：点击保存修改...")
            
            save_selectors = [
                "button:has-text('保存修改')",
                "button.el-button:has-text('保存修改')",
                "button[type='button']:has-text('保存修改')",
                "button:has-text('保存')",
            ]
            
            save_clicked = False
            for selector in save_selectors:
                try:
                    # 获取所有匹配的按钮
                    all_btns = await self.page.locator(selector).all()
                    logger.debug(f"  保存选择器 {selector} 找到 {len(all_btns)} 个")
                    
                    # 找到第一个可见的按钮
                    for btn in all_btns:
                        try:
                            is_visible = await btn.is_visible()
                            if is_visible:
                                logger.debug(f"  找到可见的保存按钮")
                                
                                # 尝试点击
                                try:
                                    await btn.click(timeout=5000)
                                    logger.success(f"  ✓ 保存按钮已点击")
                                except:
                                    # 尝试强制点击
                                    logger.warning(f"  ⚠️ 普通点击失败，尝试强制点击...")
                                    await btn.click(force=True)
                                    logger.success(f"  ✓ 强制点击成功")
                                
                                # 等待保存完成
                                await self.page.wait_for_timeout(2000)
                                logger.success(f"  ✓ [{step_name}] 保存成功")
                                save_clicked = True
                                break
                        except:
                            continue
                    
                    if save_clicked:
                        break
                        
                except Exception as e:
                    logger.debug(f"    保存选择器 {selector} 失败: {e}")
                    continue
            
            if not save_clicked:
                logger.error(f"  ✗ 未找到可用的保存按钮")
                # 截图调试
                try:
                    screenshot_path = f"debug_save_button_{step_name}.png"
                    await self.page.screenshot(path=screenshot_path)
                    logger.info(f"  📸 已保存调试截图: {screenshot_path}")
                except:
                    pass
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"  ✗ 预览/保存失败: {e}")
            return False
    
    async def step_01_title(self) -> bool:
        """步骤7.1：标题（不改动）."""
        if not await self.click_step("标题", "7.1"):
            return False
        
        logger.info("  ℹ️ 标题不改动，直接预览+保存")
        return await self.click_preview_and_save("标题")
    
    async def step_02_english_title(self) -> bool:
        """步骤7.2：英语标题（按空格）."""
        if not await self.click_step("英语标题", "7.2"):
            return False
        
        try:
            logger.info("  填写英语标题（按空格）...")
            # 查找输入框
            input_selectors = [
                "input[placeholder*='英语']",
                "input[placeholder*='英文']",
                "textarea[placeholder*='英语']"
            ]
            
            for selector in input_selectors:
                try:
                    input_elem = self.page.locator(selector).first
                    if await input_elem.count() > 0:
                        await input_elem.fill(" ")  # 按空格
                        logger.info("  ✓ 已输入空格")
                        break
                except:
                    continue
            
            return await self.click_preview_and_save("英语标题")
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_03_category_attrs(self) -> bool:
        """步骤7.3：类目属性（参考采集链接填写）."""
        if not await self.click_step("类目属性", "7.3"):
            return False
        
        logger.info("  ℹ️ 类目属性需要参考原商品链接")
        logger.info("  ℹ️ 当前跳过，实际使用时需要填写")
        
        return await self.click_preview_and_save("类目属性")
    
    async def step_04_main_sku(self) -> bool:
        """步骤7.4：主货号（不改动）."""
        if not await self.click_step("主货号", "7.4"):
            return False
        
        logger.info("  ℹ️ 主货号不改动，直接预览+保存")
        return await self.click_preview_and_save("主货号")
    
    async def step_05_packaging(self) -> bool:
        """步骤7.5：外包装（长方体+硬包装）."""
        if not await self.click_step("外包装", "7.5"):
            return False
        
        try:
            logger.info("  填写外包装信息...")
            
            # 选择长方体
            logger.info("    - 外包装形状：长方体")
            shape_selectors = [
                "text='长方体'",
                "label:has-text('长方体')",
                "input[value='长方体']"
            ]
            for selector in shape_selectors:
                try:
                    elem = self.page.locator(selector).first
                    if await elem.count() > 0:
                        await elem.click()
                        break
                except:
                    continue
            
            # 选择硬包装
            logger.info("    - 外包装类型：硬包装")
            type_selectors = [
                "text='硬包装'",
                "label:has-text('硬包装')",
                "input[value='硬包装']"
            ]
            for selector in type_selectors:
                try:
                    elem = self.page.locator(selector).first
                    if await elem.count() > 0:
                        await elem.click()
                        break
                except:
                    continue
            
            await self.page.wait_for_timeout(500)
            return await self.click_preview_and_save("外包装")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_06_origin(self) -> bool:
        """步骤7.6：产地（浙江）."""
        if not await self.click_step("产地", "7.6"):
            return False
        
        try:
            logger.info("  填写产地：浙江...")
            
            # 查找产地输入框
            origin_input = self.page.locator("input[placeholder*='产地'], input[placeholder*='省份']").first
            if await origin_input.count() > 0:
                await origin_input.fill("浙江")
                await self.page.wait_for_timeout(1000)
                
                # 选择下拉选项
                try:
                    option = self.page.locator("text='浙江', text='中国大陆/浙江省'").first
                    if await option.count() > 0:
                        await option.click()
                        logger.info("  ✓ 已选择：浙江")
                except:
                    pass
            
            return await self.click_preview_and_save("产地")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_07_customization(self) -> bool:
        """步骤7.7：定制品（不改动）."""
        if not await self.click_step("定制品", "7.7"):
            return False
        
        logger.info("  ℹ️ 定制品不改动，直接预览+保存")
        return await self.click_preview_and_save("定制品")
    
    async def step_08_sensitive_attrs(self) -> bool:
        """步骤7.8：敏感属性（不改动）."""
        if not await self.click_step("敏感属性", "7.8"):
            return False
        
        logger.info("  ℹ️ 敏感属性不改动，直接预览+保存")
        return await self.click_preview_and_save("敏感属性")
    
    async def step_09_weight(self, weight: Optional[int] = None) -> bool:
        """步骤7.9：重量（5000-9999G）.
        
        Args:
            weight: 重量（克），如果不提供则随机生成
        """
        if not await self.click_step("重量", "7.9"):
            return False
        
        try:
            if weight is None:
                weight = random.randint(5000, 9999)
            
            logger.info(f"  填写重量：{weight}G...")
            
            # 查找重量输入框
            weight_input = self.page.locator("input[placeholder*='重量'], input[placeholder*='克']").first
            if await weight_input.count() > 0:
                await weight_input.fill(str(weight))
                logger.info(f"  ✓ 已输入：{weight}G")
            
            return await self.click_preview_and_save("重量")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_10_dimensions(
        self,
        length: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> bool:
        """步骤7.10：尺寸（50-99cm，长>宽>高）.
        
        Args:
            length: 长度（cm），如果不提供则随机生成
            width: 宽度（cm）
            height: 高度（cm）
        """
        if not await self.click_step("尺寸", "7.10"):
            return False
        
        try:
            # 生成随机尺寸（确保长>宽>高）
            if length is None:
                length = random.randint(80, 99)
                width = random.randint(60, length - 10)
                height = random.randint(50, width - 5)
            
            logger.info(f"  填写尺寸：{length} × {width} × {height} cm...")
            
            # 查找输入框
            length_input = self.page.locator("input[placeholder*='长']").first
            width_input = self.page.locator("input[placeholder*='宽']").first
            height_input = self.page.locator("input[placeholder*='高']").first
            
            if await length_input.count() > 0:
                await length_input.fill(str(length))
            if await width_input.count() > 0:
                await width_input.fill(str(width))
            if await height_input.count() > 0:
                await height_input.fill(str(height))
            
            logger.info(f"  ✓ 已输入尺寸（长>宽>高）")
            
            return await self.click_preview_and_save("尺寸")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_11_platform_sku(self) -> bool:
        """步骤7.11：平台SKU（自定义SKU编码）."""
        if not await self.click_step("平台SKU", "7.11"):
            return False
        
        try:
            logger.info("  点击自定义SKU编码...")
            
            # 查找并点击"自定义SKU编码"按钮
            custom_sku_btn = self.page.locator("button:has-text('自定义SKU编码'), text='自定义SKU编码'").first
            if await custom_sku_btn.count() > 0:
                await custom_sku_btn.click()
                logger.info("  ✓ 已点击自定义SKU编码")
            
            return await self.click_preview_and_save("平台SKU")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_12_sku_category(self) -> bool:
        """步骤7.12：SKU分类（组合装500件）."""
        if not await self.click_step("SKU分类", "7.12"):
            return False
        
        try:
            logger.info("  选择：组合装500件...")
            
            # 查找并选择"组合装500件"
            option_selectors = [
                "text='组合装500件'",
                "label:has-text('组合装500件')",
                "input[value*='组合装500']"
            ]
            
            for selector in option_selectors:
                try:
                    elem = self.page.locator(selector).first
                    if await elem.count() > 0:
                        await elem.click()
                        logger.info("  ✓ 已选择：组合装500件")
                        break
                except:
                    continue
            
            return await self.click_preview_and_save("SKU分类")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_13_size_chart(self) -> bool:
        """步骤7.13：尺码表（不用修改）."""
        if not await self.click_step("尺码表", "7.13"):
            return False
        
        logger.info("  ℹ️ 尺码表不用修改")
        return await self.click_preview_and_save("尺码表")
    
    async def step_14_suggested_price(self, cost_price: Optional[float] = None) -> bool:
        """步骤7.14：建议售价（成本价×10）.
        
        Args:
            cost_price: 成本价，如果不提供则跳过
        """
        if not await self.click_step("建议售价", "7.14"):
            return False
        
        try:
            if cost_price:
                suggested_price = cost_price * 10
                logger.info(f"  填写建议售价：¥{suggested_price}...")
                
                # 查找价格输入框
                price_input = self.page.locator("input[placeholder*='价格'], input[type='number']").first
                if await price_input.count() > 0:
                    await price_input.fill(str(suggested_price))
                    logger.info(f"  ✓ 已输入：¥{suggested_price}")
            else:
                logger.info("  ℹ️ 未提供成本价，跳过填写")
            
            return await self.click_preview_and_save("建议售价")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_15_package_list(self) -> bool:
        """步骤7.15：包装清单（不改动）."""
        if not await self.click_step("包装清单", "7.15"):
            return False
        
        logger.info("  ℹ️ 包装清单不改动，直接预览+保存")
        return await self.click_preview_and_save("包装清单")
    
    async def step_16_carousel_images(self) -> bool:
        """步骤7.16：轮播图（暂时不需要）."""
        if not await self.click_step("轮播图", "7.16"):
            return False
        
        logger.info("  ℹ️ 轮播图暂时不修改")
        return await self.click_preview_and_save("轮播图")
    
    async def step_17_color_images(self) -> bool:
        """步骤7.17：颜色图（不需要）."""
        if not await self.click_step("颜色图", "7.17"):
            return False
        
        logger.info("  ℹ️ 颜色图不需要修改")
        return await self.click_preview_and_save("颜色图")
    
    async def step_18_manual(self) -> bool:
        """步骤7.18：产品说明书（上传文件）."""
        if not await self.click_step("产品说明书", "7.18"):
            return False
        
        logger.info("  ℹ️ 产品说明书需要上传文件，实际使用时处理")
        return await self.click_preview_and_save("产品说明书")
    
    async def execute_all_steps(self, product_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行18步完整流程.
        
        Args:
            product_data: 产品数据（成本价等），可选
            
        Returns:
            执行结果字典
        """
        logger.info("\n" + "=" * 60)
        logger.info("开始执行批量编辑18步")
        logger.info("=" * 60 + "\n")
        
        results = {
            "total": 18,
            "success": 0,
            "failed": 0,
            "steps": []
        }
        
        # 获取产品数据
        cost_price = product_data.get("cost_price") if product_data else None
        
        # 执行18步
        steps = [
            ("7.1", "标题", self.step_01_title()),
            ("7.2", "英语标题", self.step_02_english_title()),
            ("7.3", "类目属性", self.step_03_category_attrs()),
            ("7.4", "主货号", self.step_04_main_sku()),
            ("7.5", "外包装", self.step_05_packaging()),
            ("7.6", "产地", self.step_06_origin()),
            ("7.7", "定制品", self.step_07_customization()),
            ("7.8", "敏感属性", self.step_08_sensitive_attrs()),
            ("7.9", "重量", self.step_09_weight()),
            ("7.10", "尺寸", self.step_10_dimensions()),
            ("7.11", "平台SKU", self.step_11_platform_sku()),
            ("7.12", "SKU分类", self.step_12_sku_category()),
            ("7.13", "尺码表", self.step_13_size_chart()),
            ("7.14", "建议售价", self.step_14_suggested_price(cost_price)),
            ("7.15", "包装清单", self.step_15_package_list()),
            ("7.16", "轮播图", self.step_16_carousel_images()),
            ("7.17", "颜色图", self.step_17_color_images()),
            ("7.18", "产品说明书", self.step_18_manual()),
        ]
        
        for step_num, step_name, step_coro in steps:
            try:
                success = await step_coro
                
                if success:
                    results["success"] += 1
                    results["steps"].append({
                        "step": step_num,
                        "name": step_name,
                        "status": "success"
                    })
                    logger.success(f"✓ 步骤{step_num}完成\n")
                else:
                    results["failed"] += 1
                    results["steps"].append({
                        "step": step_num,
                        "name": step_name,
                        "status": "failed"
                    })
                    logger.error(f"✗ 步骤{step_num}失败\n")
                
            except Exception as e:
                results["failed"] += 1
                results["steps"].append({
                    "step": step_num,
                    "name": step_name,
                    "status": "error",
                    "error": str(e)
                })
                logger.error(f"✗ 步骤{step_num}出错: {e}\n")
        
        # 总结
        logger.info("\n" + "=" * 60)
        logger.info("批量编辑18步完成")
        logger.info("=" * 60)
        logger.info(f"总计: {results['total']} 步")
        logger.info(f"成功: {results['success']} 步")
        logger.info(f"失败: {results['failed']} 步")
        logger.info(f"成功率: {results['success']*100//results['total']}%")
        logger.info("=" * 60 + "\n")
        
        return results


# 测试代码
if __name__ == "__main__":
    async def test():
        from browser_manager import BrowserManager
        from login_controller import LoginController
        import os
        
        # 登录
        login_ctrl = LoginController()
        username = os.getenv("MIAOSHOU_USERNAME")
        password = os.getenv("MIAOSHOU_PASSWORD")
        
        if await login_ctrl.login(username, password, headless=False):
            page = login_ctrl.browser_manager.page
            
            # 批量编辑
            controller = BatchEditController(page)
            await controller.navigate_to_batch_edit()
            
            product_data = {"cost_price": 150.0}
            result = await controller.execute_all_steps(product_data)
            
            print(f"\n结果: {result}")
            
            await login_ctrl.browser_manager.close()
    
    asyncio.run(test())

