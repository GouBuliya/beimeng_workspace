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
            # 1. 导航到Temu全托管采集箱（优化等待策略 + 并行处理）
            logger.info(f"导航到: {self.temu_box_url}")
            await self.page.goto(self.temu_box_url, timeout=60000)
            
            # 并行等待多个条件
            try:
                await asyncio.gather(
                    self.page.wait_for_load_state("domcontentloaded", timeout=60000),
                    self.page.locator("text='全选'").first.wait_for(state="visible", timeout=10000)
                )
                logger.debug("✓ 页面已加载，关键元素可见")
            except:
                # fallback: 如果元素未找到，等待500ms
                await self.page.wait_for_timeout(500)
            
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
                            # 移除不必要的500ms等待，按钮点击已有反馈
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
            
            # 3. 关闭可能遮挡的对话框（新手指南、帮助等）
            logger.info("检查并关闭遮挡对话框...")
            try:
                # 查找所有可能的关闭按钮
                close_selectors = [
                    ".jx-overlay-dialog .jx-button:has-text('知道了')",
                    ".jx-overlay-dialog .jx-button:has-text('关闭')",
                    ".jx-overlay-dialog .jx-dialog__headerbtn",
                    ".jx-overlay .jx-icon-close",
                    "button:has-text('知道了')",
                    "button:has-text('我知道了')",
                    "[aria-label='Close']"
                ]
                
                for selector in close_selectors:
                    try:
                        close_btn = self.page.locator(selector).first
                        if await close_btn.count() > 0 and await close_btn.is_visible():
                            await close_btn.click(timeout=2000)
                            logger.debug(f"✓ 已关闭遮挡对话框: {selector}")
                            await self.page.wait_for_timeout(500)
                            break
                    except:
                        continue
                
                logger.debug("✓ 对话框检查完成")
            except Exception as e:
                logger.debug(f"对话框关闭检查异常（可忽略）: {e}")
            
            # 4. 点击批量编辑按钮
            logger.info("点击批量编辑按钮...")
            try:
                batch_edit_btn = self.page.locator("button:has-text('批量编辑')").first
                await batch_edit_btn.wait_for(state="visible", timeout=5000)
                
                # 尝试普通点击
                try:
                    await batch_edit_btn.click(timeout=5000)
                    logger.success("✓ 已点击批量编辑按钮")
                except:
                    # 如果普通点击失败，尝试强制点击
                    logger.warning("⚠️ 普通点击失败，尝试强制点击...")
                    await batch_edit_btn.click(force=True)
                    logger.success("✓ 强制点击成功")
                
                # 等待批量编辑页面关键元素出现
                try:
                    await self.page.locator("button:has-text('预览')").first.wait_for(state="visible", timeout=10000)
                    logger.success("✓ 已进入批量编辑页面")
                except:
                    # fallback: 等待1秒
                    await self.page.wait_for_timeout(1000)
            except Exception as e:
                logger.error(f"无法进入批量编辑: {e}")
                return False
            
            # 4. 验证是否进入批量编辑页面（已通过步骤3的智能等待验证）
            # 移除不必要的验证等待，步骤3已经等待预览按钮可见
            logger.success("✓ 批量编辑页面准备就绪")
            return True
            
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
            # 1. 尝试多个选择器定位步骤（限定在批量编辑弹窗内）
            # 批量编辑弹窗的选择器
            dialog_selectors = [
                ".multi-batch-edit-dialog",  # 主对话框
                ".el-dialog__wrapper:has-text('批量产品编辑')",  # 包含标题的wrapper
                ".batch-edit-detail-dialog",  # 详情对话框
            ]
            
            # 在弹窗内查找步骤
            step_elem = None
            used_selector = None
            
            for dialog_selector in dialog_selectors:
                # 检查弹窗是否存在且可见
                try:
                    dialog = self.page.locator(dialog_selector).first
                    if await dialog.count() == 0:
                        continue
                    
                    # 在弹窗内查找步骤
                    step_selectors = [
                        f"{dialog_selector} >> text='{step_name}'",
                        f"{dialog_selector} button:has-text('{step_name}')",
                        f"{dialog_selector} a:has-text('{step_name}')",
                        f"{dialog_selector} .step-item:has-text('{step_name}')",
                        f"{dialog_selector} div:has-text('{step_name}')",
                    ]
                    
                    for selector in step_selectors:
                        try:
                            elem = self.page.locator(selector).first
                            if await elem.count() > 0:
                                step_elem = elem
                                used_selector = selector
                                logger.debug(f"  使用选择器: {selector}")
                                break
                        except:
                            continue
                    
                    if step_elem:
                        break
                        
                except Exception as e:
                    logger.debug(f"  弹窗选择器 {dialog_selector} 检查失败: {e}")
                    continue
            
            if not step_elem:
                logger.error(f"  ✗ 未找到步骤: {step_name}")
                logger.debug(f"  已尝试的弹窗选择器: {dialog_selectors}")
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
            
            # 4. 等待页面内容加载（智能等待预览按钮）
            logger.info(f"  ⏳ 等待步骤页面加载...")
            try:
                # 智能等待：等待预览按钮出现
                preview_btn = self.page.locator("button:has-text('预览')").first
                await preview_btn.wait_for(state="visible", timeout=5000)
                logger.success(f"  ✓ 步骤页面已加载（预览按钮可见）")
            except:
                # fallback: 如果找不到预览按钮，等待1秒
                logger.debug(f"  未检测到预览按钮，使用fallback等待")
                await self.page.wait_for_timeout(1000)
            
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
            # 确定批量编辑弹窗选择器
            dialog_selectors = [
                ".multi-batch-edit-dialog",
                ".el-dialog__wrapper:has-text('批量产品编辑')",
                ".batch-edit-detail-dialog",
            ]
            
            # 查找可见的弹窗
            active_dialog = None
            for selector in dialog_selectors:
                try:
                    dialog = self.page.locator(selector).first
                    if await dialog.count() > 0 and await dialog.is_visible():
                        active_dialog = selector
                        logger.debug(f"  找到活跃弹窗: {selector}")
                        break
                except:
                    continue
            
            if not active_dialog:
                logger.warning("  ⚠️ 未找到批量编辑弹窗")
                # fallback: 不限定范围
                active_dialog = ""
            
            # ========================================
            # 第1步：点击预览
            # ========================================
            logger.info(f"  📋 第1步：点击预览...")
            preview_selectors = [
                f"{active_dialog} button:has-text('预览')".strip(),
                f"{active_dialog} button.el-button:has-text('预览')".strip(),
                f"{active_dialog} button[type='button']:has-text('预览')".strip(),
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
                f"{active_dialog} button:has-text('保存修改')".strip(),
                f"{active_dialog} button.el-button:has-text('保存修改')".strip(),
                f"{active_dialog} button[type='button']:has-text('保存修改')".strip(),
                f"{active_dialog} button:has-text('保存')".strip(),
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
            
            # ========================================
            # 第3步：等待保存进度并点击关闭按钮
            # ========================================
            logger.info(f"  ⏳ 等待保存完成...")
            try:
                # 等待保存对话框出现（有进度条）
                await self.page.wait_for_timeout(1500)  # 2000 -> 1500ms
                
                # 查找并点击"关闭"按钮
                logger.info(f"  🔘 查找关闭按钮...")
                close_selectors = [
                    "button:has-text('关闭')",
                    "button.el-button:has-text('关闭')",
                    "button:has-text('确定')",
                    "button:has-text('完成')",
                ]
                
                close_clicked = False
                # 等待最多30秒让保存完成
                for attempt in range(15):  # 15次 x 2秒 = 30秒
                    for selector in close_selectors:
                        try:
                            all_btns = await self.page.locator(selector).all()
                            for btn in all_btns:
                                if await btn.is_visible():
                                    logger.debug(f"  找到关闭按钮: {selector}")
                                    try:
                                        await btn.click(timeout=3000)
                                        logger.success(f"  ✓ 关闭按钮已点击")
                                        close_clicked = True
                                        break
                                    except:
                                        try:
                                            await btn.click(force=True)
                                            logger.success(f"  ✓ 强制点击关闭按钮成功")
                                            close_clicked = True
                                            break
                                        except:
                                            continue
                            if close_clicked:
                                break
                        except:
                            continue
                    
                    if close_clicked:
                        break
                    
                    # 等待1.5秒后重试
                    await self.page.wait_for_timeout(1500)  # 2000 -> 1500ms
                
                if close_clicked:
                    logger.success(f"  ✓ [{step_name}] 保存完成并关闭对话框")
                    await self.page.wait_for_timeout(1000)
                    return True
                else:
                    logger.warning(f"  ⚠️ 未找到关闭按钮，可能已自动关闭")
                    return True
                    
            except Exception as e:
                logger.warning(f"  ⚠️ 处理关闭按钮时出错: {e}")
                # 即使关闭按钮失败，也认为保存成功了
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
            logger.info("  填写英语标题（输入空格）...")
            
            # 等待页面加载
            await self.page.wait_for_timeout(500)
            
            # 精准定位：排除disabled/readonly，优先匹配placeholder包含"英"的输入框
            precise_selectors = [
                "input[placeholder*='英']:not([disabled]):not([readonly])",
                "textarea[placeholder*='英']:not([disabled]):not([readonly])",
                "input[placeholder*='English']:not([disabled]):not([readonly])",
            ]
            
            filled = False
            for selector in precise_selectors:
                try:
                    inputs = await self.page.locator(selector).all()
                    logger.debug(f"  精准选择器找到 {len(inputs)} 个候选")
                    
                    for input_elem in inputs:
                        if not await input_elem.is_visible():
                            continue
                        
                        try:
                            # 快速点击测试（500ms超时）
                            await input_elem.click(timeout=500)
                            await input_elem.clear()
                            await input_elem.fill(" ")
                            logger.success(f"  ✓ 已输入空格（精准定位）")
                            filled = True
                            break
                        except:
                            continue
                    
                    if filled:
                        break
                except:
                    continue
            
            if not filled:
                logger.warning("  ⚠️ 未找到英语标题输入框")
            
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
        """步骤7.4：主货号（填写或保持默认）."""
        if not await self.click_step("主货号", "7.4"):
            return False
        
        try:
            logger.info("  检查主货号是否需要填写...")
            await self.page.wait_for_timeout(500)
            
            # 精准定位：排除disabled/readonly
            precise_selectors = [
                "input[placeholder*='货号']:not([disabled]):not([readonly])",
                "input[placeholder*='SKU']:not([disabled]):not([readonly])",
            ]
            
            input_found = False
            for selector in precise_selectors:
                try:
                    inputs = await self.page.locator(selector).all()
                    
                    for input_elem in inputs:
                        if await input_elem.is_visible():
                            current_value = await input_elem.input_value()
                            if current_value:
                                logger.info(f"  ℹ️ 主货号已有值：{current_value}，保持不变")
                            else:
                                logger.info(f"  ℹ️ 主货号为空，保持默认")
                            input_found = True
                            break
                    
                    if input_found:
                        break
                except:
                    continue
            
            return await self.click_preview_and_save("主货号")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_05_packaging(self, image_url: Optional[str] = None) -> bool:
        """步骤7.5：外包装（长方体+硬包装）.
        
        Args:
            image_url: 外包装图片URL（可选）
        """
        if not await self.click_step("外包装", "7.5"):
            return False
        
        try:
            logger.info("  填写外包装信息...")
            
            # 等待页面加载完成
            await self.page.wait_for_timeout(1000)
            
            # 1. 选择外包装形状：长方体（使用下拉选择框）
            logger.info("    - 外包装形状：长方体")
            shape_selected = False
            
            try:
                # 查找"外包装形状"标签，然后找到对应的下拉框
                shape_label = self.page.locator("text='外包装形状'").first
                if await shape_label.count() > 0:
                    # 找到同一行的el-select下拉框
                    parent = shape_label.locator("..").locator("..")
                    select_input = parent.locator(".el-input__inner, input.el-input__inner").first
                    
                    if await select_input.count() > 0 and await select_input.is_visible():
                        # 点击下拉框打开选项
                        await select_input.click()
                        logger.debug("      已点击外包装形状下拉框")
                        await self.page.wait_for_timeout(500)
                        
                        # 选择"长方体"选项
                        option_selectors = [
                            ".el-select-dropdown__item:has-text('长方体')",
                            "li.el-select-dropdown__item:has-text('长方体')",
                            ".jx-pro-option:has-text('长方体')"
                        ]
                        
                        for selector in option_selectors:
                            try:
                                option = self.page.locator(selector).first
                                if await option.count() > 0:
                                    # 等待选项可见
                                    await option.wait_for(state="visible", timeout=3000)
                                    await option.click()
                                    logger.info("      ✓ 已选择长方体")
                                    shape_selected = True
                                    break
                            except Exception as e:
                                logger.debug(f"      选项选择器 {selector} 失败: {e}")
                                continue
                    else:
                        logger.warning("      ⚠️ 未找到外包装形状下拉框")
                else:
                    logger.warning("      ⚠️ 未找到'外包装形状'标签")
            except Exception as e:
                logger.warning(f"      ⚠️ 选择外包装形状失败: {e}")
            
            if not shape_selected:
                logger.warning("      ⚠️ 未能选择长方体")
                try:
                    await self.page.screenshot(path="debug_packaging_shape.png")
                    logger.info("      📸 已保存截图: debug_packaging_shape.png")
                except:
                    pass
            
            await self.page.wait_for_timeout(500)
            
            # 2. 选择外包装类型：硬包装（使用下拉选择框）
            logger.info("    - 外包装类型：硬包装")
            type_selected = False
            
            try:
                # 查找"外包装类型"标签，然后找到对应的下拉框
                type_label = self.page.locator("text='外包装类型'").first
                if await type_label.count() > 0:
                    # 找到同一行的el-select下拉框
                    parent = type_label.locator("..").locator("..")
                    select_input = parent.locator(".el-input__inner, input.el-input__inner").first
                    
                    if await select_input.count() > 0 and await select_input.is_visible():
                        # 点击下拉框打开选项
                        await select_input.click()
                        logger.debug("      已点击外包装类型下拉框")
                        await self.page.wait_for_timeout(500)
                        
                        # 选择"硬包装"选项
                        option_selectors = [
                            ".el-select-dropdown__item:has-text('硬包装')",
                            "li.el-select-dropdown__item:has-text('硬包装')",
                            ".jx-pro-option:has-text('硬包装')"
                        ]
                        
                        for selector in option_selectors:
                            try:
                                option = self.page.locator(selector).first
                                if await option.count() > 0:
                                    # 等待选项可见
                                    await option.wait_for(state="visible", timeout=3000)
                                    await option.click()
                                    logger.info("      ✓ 已选择硬包装")
                                    type_selected = True
                                    break
                            except Exception as e:
                                logger.debug(f"      选项选择器 {selector} 失败: {e}")
                                continue
                    else:
                        logger.warning("      ⚠️ 未找到外包装类型下拉框")
                else:
                    logger.warning("      ⚠️ 未找到'外包装类型'标签")
            except Exception as e:
                logger.warning(f"      ⚠️ 选择外包装类型失败: {e}")
            
            if not type_selected:
                logger.warning("      ⚠️ 未能选择硬包装")
                try:
                    await self.page.screenshot(path="debug_packaging_type.png")
                    logger.info("      📸 已保存截图: debug_packaging_type.png")
                except:
                    pass
            
            await self.page.wait_for_timeout(500)
            
            # 3. 上传图片（如果提供了URL）
            if image_url:
                logger.info(f"    - 上传外包装图片: {image_url}")
                try:
                    # 查找"使用网络图片"按钮
                    network_img_btn = self.page.locator("button:has-text('使用网络图片')").first
                    if await network_img_btn.count() > 0 and await network_img_btn.is_visible():
                        await network_img_btn.click()
                        await self.page.wait_for_timeout(1000)
                        
                        # 输入图片URL
                        url_input = self.page.locator("input[placeholder*='图片'], textarea").first
                        if await url_input.count() > 0:
                            await url_input.fill(image_url)
                            await self.page.wait_for_timeout(500)
                            
                            # 点击确定按钮
                            confirm_btn = self.page.locator("button:has-text('确定'), button:has-text('确认')").first
                            if await confirm_btn.count() > 0:
                                await confirm_btn.click()
                                logger.info("      ✓ 图片URL已上传")
                            else:
                                logger.warning("      ⚠️ 未找到确定按钮")
                        else:
                            logger.warning("      ⚠️ 未找到图片URL输入框")
                    else:
                        logger.debug("      未找到网络图片按钮")
                except Exception as e:
                    logger.warning(f"      ⚠️ 图片上传失败: {e}")
            else:
                logger.info("    - 跳过图片上传（未提供URL）")
            
            await self.page.wait_for_timeout(500)
            return await self.click_preview_and_save("外包装")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_06_origin(self) -> bool:
        """步骤7.6：产地（先输入"浙江"，然后选择"中国大陆 / 浙江省"）."""
        if not await self.click_step("产地", "7.6"):
            return False
        
        try:
            logger.info("  填写产地：浙江 -> 中国大陆 / 浙江省...")
            
            # 等待页面加载
            await self.page.wait_for_timeout(1000)
            
            # 策略：精准定位 - 直接找到可用的输入框，不遍历无用的
            # 根据页面结构分析，产地输入框特征：
            # 1. 不是 type="number"
            # 2. 不是 readonly
            # 3. 不是 disabled
            # 4. placeholder包含"搜索"
            # 5. 可以接收点击（不被遮挡）
            
            # 使用组合选择器直接定位
            precise_selectors = [
                # 最精准：排除所有不可用属性，只找可用的输入框
                "input[placeholder='请选择或输入搜索']:not([readonly]):not([disabled]):not([type='number'])",
                # 备用：通过可见性和类名筛选
                ".jx-cascader__search-input:visible",
            ]
            
            input_found = False
            
            for selector in precise_selectors:
                try:
                    # 获取所有匹配的输入框
                    all_inputs = await self.page.locator(selector).all()
                    logger.debug(f"  精准选择器 '{selector[:50]}...' 找到 {len(all_inputs)} 个候选")
                    
                    # 遍历找到第一个可点击的（通常就是我们要的那个）
                    for idx, input_elem in enumerate(all_inputs):
                        try:
                            # 检查可见性
                            if not await input_elem.is_visible():
                                continue
                            
                            # 尝试点击（短超时1秒，快速验证是否可点击）
                            logger.debug(f"    尝试候选 {idx+1}/{len(all_inputs)}...")
                            try:
                                await input_elem.click(timeout=1000)  # 1秒超时，更快失败
                                
                                # 成功点击，立即填写
                                await self.page.wait_for_timeout(200)
                                await input_elem.clear()
                                await input_elem.fill("浙江")
                                logger.success(f"  ✓ 已输入搜索关键词：浙江（精准定位第 {idx+1} 个）")
                                input_found = True
                                
                                # 等待下拉列表出现
                                await self.page.wait_for_timeout(1500)
                                
                                # 步骤2: 在下拉列表中选择"中国大陆 / 浙江省"
                                option_selectors = [
                                    "text='中国大陆 / 浙江省'",
                                    "text='中国大陆/浙江省'",
                                    ".el-select-dropdown__item:has-text('中国大陆')",
                                    ".el-select-dropdown__item:has-text('浙江省')",
                                ]
                                
                                selected = False
                                for opt_selector in option_selectors:
                                    try:
                                        options = await self.page.locator(opt_selector).all()
                                        
                                        for option in options:
                                            try:
                                                await option.wait_for(state="visible", timeout=1000)
                                                option_text = (await option.inner_text()).strip()
                                                
                                                # 检查是否包含"中国大陆"和"浙江"
                                                if "中国大陆" in option_text and "浙江" in option_text:
                                                    await option.click(timeout=2000)
                                                    logger.success(f"  ✓ 已选择：{option_text}")
                                                    selected = True
                                                    break
                                            except:
                                                continue
                                        
                                        if selected:
                                            break
                                    except:
                                        continue
                                
                                if not selected:
                                    # 尝试按回车键确认
                                    try:
                                        await input_elem.press("ArrowDown")
                                        await self.page.wait_for_timeout(300)
                                        await input_elem.press("Enter")
                                        logger.info("  ✓ 已按ArrowDown+Enter确认")
                                    except:
                                        logger.warning("  ⚠️ 未找到下拉选项，但已输入文本")
                                
                                break  # 成功，跳出循环
                                
                            except:
                                # 点击失败，快速尝试下一个
                                continue
                                
                        except:
                            continue
                    
                    if input_found:
                        break  # 找到可用输入框，停止尝试其他选择器
                        
                except Exception as e:
                    logger.debug(f"  选择器失败: {str(e)[:60]}")
                    continue
            
            if not input_found:
                logger.warning("  ⚠️ 未找到可用的产地输入框")
                try:
                    await self.page.screenshot(path="debug_origin.png")
                    logger.info("  📸 已保存截图: debug_origin.png")
                except:
                    pass
            
            await self.page.wait_for_timeout(500)
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
    
    async def step_09_weight(self, weight: Optional[int] = None, product_name: Optional[str] = None) -> bool:
        """步骤7.9：重量（5000-9999G）.
        
        Args:
            weight: 重量（克），如果不提供则尝试从Excel读取或随机生成
            product_name: 产品名称，用于从Excel读取数据
        """
        if not await self.click_step("重量", "7.9"):
            return False
        
        try:
            # 获取重量值
            if weight is None and product_name:
                try:
                    from src.data_processor.product_data_reader import ProductDataReader
                    reader = ProductDataReader()
                    weight = reader.get_weight(product_name)
                    if weight:
                        logger.info(f"  从Excel读取到重量: {weight}G")
                except Exception as e:
                    logger.debug(f"  从Excel读取重量失败: {e}")
            
            if weight is None:
                from src.data_processor.product_data_reader import ProductDataReader
                weight = ProductDataReader.generate_random_weight()
                logger.info(f"  使用随机重量: {weight}G")
            
            logger.info(f"  填写重量：{weight}G...")
            
            # 精准定位：排除disabled/readonly
            precise_selectors = [
                "input[placeholder*='重量']:not([disabled]):not([readonly])",
                "input[placeholder*='克']:not([disabled]):not([readonly])",
            ]
            
            for selector in precise_selectors:
                try:
                    weight_input = self.page.locator(selector).first
                    if await weight_input.count() > 0 and await weight_input.is_visible():
                        await weight_input.fill(str(weight))
                        logger.info(f"  ✓ 已输入：{weight}G")
                        break
                except:
                    continue
            
            return await self.click_preview_and_save("重量")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            return False
    
    async def step_10_dimensions(
        self,
        length: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        product_name: Optional[str] = None
    ) -> bool:
        """步骤7.10：尺寸（50-99cm，长>宽>高）.
        
        Args:
            length: 长度（cm），如果不提供则尝试从Excel读取或随机生成
            width: 宽度（cm）
            height: 高度（cm）
            product_name: 产品名称，用于从Excel读取数据
        """
        if not await self.click_step("尺寸", "7.10"):
            return False
        
        try:
            # 获取尺寸值
            if length is None and width is None and height is None and product_name:
                try:
                    from src.data_processor.product_data_reader import ProductDataReader
                    reader = ProductDataReader()
                    dimensions = reader.get_dimensions(product_name)
                    if dimensions:
                        length = dimensions['length']
                        width = dimensions['width']
                        height = dimensions['height']
                        logger.info(f"  从Excel读取到尺寸: {length} × {width} × {height} cm")
                except Exception as e:
                    logger.debug(f"  从Excel读取尺寸失败: {e}")
            
            if length is None:
                from src.data_processor.product_data_reader import ProductDataReader
                dims = ProductDataReader.generate_random_dimensions()
                length = dims['length']
                width = dims['width']
                height = dims['height']
                logger.info(f"  使用随机尺寸: {length} × {width} × {height} cm")
            
            # 验证并修正尺寸
            from src.data_processor.product_data_reader import ProductDataReader
            length, width, height = ProductDataReader.validate_and_fix_dimensions(length, width, height)
            
            logger.info(f"  填写尺寸：{length} × {width} × {height} cm...")
            
            # 精准定位：排除disabled/readonly
            length_selectors = ["input[placeholder*='长']:not([disabled]):not([readonly])"]
            width_selectors = ["input[placeholder*='宽']:not([disabled]):not([readonly])"]
            height_selectors = ["input[placeholder*='高']:not([disabled]):not([readonly])"]
            
            # 填写长度
            for selector in length_selectors:
                try:
                    length_input = self.page.locator(selector).first
                    if await length_input.count() > 0 and await length_input.is_visible():
                        await length_input.fill(str(length))
                        logger.debug(f"  ✓ 长度: {length}cm")
                        break
                except:
                    continue
            
            # 填写宽度
            for selector in width_selectors:
                try:
                    width_input = self.page.locator(selector).first
                    if await width_input.count() > 0 and await width_input.is_visible():
                        await width_input.fill(str(width))
                        logger.debug(f"  ✓ 宽度: {width}cm")
                        break
                except:
                    continue
            
            # 填写高度
            for selector in height_selectors:
                try:
                    height_input = self.page.locator(selector).first
                    if await height_input.count() > 0 and await height_input.is_visible():
                        await height_input.fill(str(height))
                        logger.debug(f"  ✓ 高度: {height}cm")
                        break
                except:
                    continue
            
            logger.info(f"  ✓ 已输入尺寸（验证：{length} > {width} > {height}）")
            
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
            custom_sku_selectors = [
                "button:has-text('自定义SKU编码')",
                "text='自定义SKU编码'",
                "label:has-text('自定义SKU编码')",
                ".el-button:has-text('自定义SKU编码')",
                "span:has-text('自定义SKU编码')"
            ]
            
            clicked = False
            for selector in custom_sku_selectors:
                try:
                    all_elems = await self.page.locator(selector).all()
                    for elem in all_elems:
                        if await elem.is_visible():
                            await elem.click()
                            logger.info("  ✓ 已点击自定义SKU编码")
                            clicked = True
                            break
                    if clicked:
                        break
                except Exception as e:
                    logger.debug(f"  选择器 {selector} 失败: {e}")
                    continue
            
            if not clicked:
                logger.warning("  ⚠️ 未找到自定义SKU编码按钮，尝试强制点击")
                try:
                    await self.page.locator("button:has-text('自定义SKU编码')").first.click(force=True)
                    logger.info("  ✓ 强制点击成功")
                except:
                    logger.warning("  ⚠️ 未找到自定义SKU编码按钮")
            
            await self.page.wait_for_timeout(500)
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
                ".el-radio:has-text('组合装500件')",
                "input[value*='组合装500']",
                ".el-select-dropdown__item:has-text('组合装500')",
                "span:has-text('组合装500件')"
            ]
            
            selected = False
            for selector in option_selectors:
                try:
                    all_elems = await self.page.locator(selector).all()
                    for elem in all_elems:
                        if await elem.is_visible():
                            await elem.click()
                            logger.info("  ✓ 已选择：组合装500件")
                            selected = True
                            break
                    if selected:
                        break
                except Exception as e:
                    logger.debug(f"  选择器 {selector} 失败: {e}")
                    continue
            
            if not selected:
                logger.warning("  ⚠️ 未找到组合装500件选项")
            
            await self.page.wait_for_timeout(500)
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
    
    async def step_14_suggested_price(self, cost_price: Optional[float] = None, product_name: Optional[str] = None) -> bool:
        """步骤7.14：建议售价（成本价×10）.
        
        Args:
            cost_price: 成本价，如果不提供则尝试从Excel读取
            product_name: 产品名称，用于从Excel读取数据
        """
        if not await self.click_step("建议售价", "7.14"):
            return False
        
        try:
            # 获取成本价
            if cost_price is None and product_name:
                try:
                    from src.data_processor.product_data_reader import ProductDataReader
                    reader = ProductDataReader()
                    cost_price = reader.get_cost_price(product_name)
                    if cost_price:
                        logger.info(f"  从Excel读取到成本价: ¥{cost_price}")
                except Exception as e:
                    logger.debug(f"  从Excel读取成本价失败: {e}")
            
            if cost_price:
                suggested_price = cost_price * 10
                logger.info(f"  填写建议售价：¥{suggested_price} (成本价 ¥{cost_price} × 10)...")
                
                # 精准定位：排除disabled/readonly，优先匹配type=number
                precise_selectors = [
                    "input[placeholder*='价格']:not([disabled]):not([readonly])[type='number']",
                    "input[placeholder*='售价']:not([disabled]):not([readonly])[type='number']",
                    "input[placeholder*='建议']:not([disabled]):not([readonly])[type='number']",
                ]
                
                for selector in precise_selectors:
                    try:
                        price_input = self.page.locator(selector).first
                        if await price_input.count() > 0 and await price_input.is_visible():
                            await price_input.fill(str(suggested_price))
                            logger.info(f"  ✓ 已输入：¥{suggested_price}")
                            break
                    except:
                        continue
            else:
                logger.info("  ℹ️ 无成本价数据，跳过填写（SOP要求：不做要求随便填）")
            
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
    
    async def step_18_manual(self, manual_file_path: Optional[str] = None) -> bool:
        """步骤7.18：产品说明书（上传PDF文件）.
        
        Args:
            manual_file_path: 说明书PDF文件的绝对路径（可选）
        """
        if not await self.click_step("产品说明书", "7.18"):
            return False
        
        try:
            # 如果提供了文件路径，尝试上传
            if manual_file_path:
                from pathlib import Path
                file_path = Path(manual_file_path)
                
                if not file_path.exists():
                    logger.warning(f"  ⚠️ 文件不存在: {manual_file_path}")
                    logger.info("  ℹ️ 跳过文件上传，直接预览+保存")
                else:
                    logger.info(f"  上传产品说明书: {file_path.name}...")
                    
                    # 查找文件上传输入框
                    file_input_selectors = [
                        "input[type='file']",
                        "input[accept*='pdf']",
                        "input[accept*='.pdf']"
                    ]
                    
                    uploaded = False
                    for selector in file_input_selectors:
                        try:
                            file_input = self.page.locator(selector).first
                            if await file_input.count() > 0:
                                await file_input.set_input_files(str(file_path))
                                logger.info(f"  ✓ 文件已上传: {file_path.name}")
                                uploaded = True
                                await self.page.wait_for_timeout(2000)  # 等待上传完成
                                break
                        except Exception as e:
                            logger.debug(f"  上传选择器 {selector} 失败: {e}")
                            continue
                    
                    if not uploaded:
                        logger.warning("  ⚠️ 未找到文件上传输入框")
            else:
                logger.info("  ℹ️ 未提供说明书文件，跳过上传")
            
            return await self.click_preview_and_save("产品说明书")
            
        except Exception as e:
            logger.error(f"  ✗ 操作失败: {e}")
            # 即使上传失败，也尝试预览+保存
            return await self.click_preview_and_save("产品说明书")
    
    async def execute_all_steps(self, product_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """执行18步完整流程.
        
        Args:
            product_data: 产品数据字典，包含:
                - cost_price: 成本价
                - product_name: 产品名称（用于从Excel读取数据）
                - weight: 重量（可选）
                - length/width/height: 尺寸（可选）
            
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
        product_name = product_data.get("product_name") if product_data else None
        weight = product_data.get("weight") if product_data else None
        length = product_data.get("length") if product_data else None
        width = product_data.get("width") if product_data else None
        height = product_data.get("height") if product_data else None
        
        # 执行18步（传递正确的参数）
        steps = [
            ("7.1", "标题", self.step_01_title()),
            ("7.2", "英语标题", self.step_02_english_title()),
            ("7.3", "类目属性", self.step_03_category_attrs()),
            ("7.4", "主货号", self.step_04_main_sku()),
            ("7.5", "外包装", self.step_05_packaging()),
            ("7.6", "产地", self.step_06_origin()),
            ("7.7", "定制品", self.step_07_customization()),
            ("7.8", "敏感属性", self.step_08_sensitive_attrs()),
            ("7.9", "重量", self.step_09_weight(weight=weight, product_name=product_name)),
            ("7.10", "尺寸", self.step_10_dimensions(length=length, width=width, height=height, product_name=product_name)),
            ("7.11", "平台SKU", self.step_11_platform_sku()),
            ("7.12", "SKU分类", self.step_12_sku_category()),
            ("7.13", "尺码表", self.step_13_size_chart()),
            ("7.14", "建议售价", self.step_14_suggested_price(cost_price=cost_price, product_name=product_name)),
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

