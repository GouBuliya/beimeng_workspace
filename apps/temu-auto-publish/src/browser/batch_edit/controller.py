"""
@PURPOSE: 批量编辑控制器主体，负责导航、步骤调度与执行结果汇总
@OUTLINE:
  - class BatchEditController(BatchEditStepsMixin):
      - __init__
      - navigate_to_batch_edit()
      - click_step()
      - click_preview_and_save()
      - execute_all_steps()
@DEPENDENCIES:
  - 内部: .steps.BatchEditStepsMixin
  - 外部: playwright.async_api.Page, loguru.logger
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .steps import BatchEditStepsMixin


class BatchEditController(BatchEditStepsMixin):
    """批量编辑控制器（改进版）."""

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
            await self.page.goto(self.temu_box_url, timeout=60_000)

            # 并行等待多个条件
            try:
                await asyncio.gather(
                    self.page.wait_for_load_state("domcontentloaded", timeout=60_000),
                    self.page.locator("text='全选'").first.wait_for(state="visible", timeout=10_000),
                )
                logger.debug("✓ 页面已加载，关键元素可见")
            except Exception:
                await self.page.wait_for_timeout(500)

            # 2. 全选产品
            logger.info(f"选择 {select_count} 个产品...")
            try:
                select_all_selectors = [
                    "text='全选'",
                    "button:has-text('全选')",
                    "label:has-text('全选')",
                    ".jx-checkbox:has-text('全选')",
                ]

                selected = False
                for selector in select_all_selectors:
                    try:
                        btn = self.page.locator(selector).first
                        if await btn.count() > 0:
                            await btn.click(timeout=10_000)
                            logger.success("✓ 已全选产品")
                            selected = True
                            break
                    except Exception:
                        continue

                if not selected:
                    logger.warning("全选失败，尝试手动勾选前20个...")
                    checkboxes = self.page.locator(".jx-table__body .jx-checkbox").first
                    for i in range(min(20, await checkboxes.count())):
                        try:
                            await checkboxes.nth(i).click()
                            await self.page.wait_for_timeout(100)
                        except Exception:
                            continue
                    logger.info("✓ 已手动勾选产品")

            except Exception as exc:
                logger.warning(f"选择产品失败: {exc}")
                return False

            # 3. 关闭可能遮挡的对话框
            logger.info("检查并关闭遮挡对话框...")
            try:
                close_selectors = [
                    ".jx-overlay-dialog .jx-button:has-text('知道了')",
                    ".jx-overlay-dialog .jx-button:has-text('关闭')",
                    ".jx-overlay-dialog .jx-dialog__headerbtn",
                    ".jx-overlay .jx-icon-close",
                    "button:has-text('知道了')",
                    "button:has-text('我知道了')",
                    "[aria-label='Close']",
                ]

                for selector in close_selectors:
                    try:
                        close_btn = self.page.locator(selector).first
                        if await close_btn.count() > 0 and await close_btn.is_visible():
                            await close_btn.click(timeout=2000)
                            logger.debug(f"✓ 已关闭遮挡对话框: {selector}")
                            await self.page.wait_for_timeout(500)
                            break
                    except Exception:
                        continue

                logger.debug("✓ 对话框检查完成")
            except Exception as exc:
                logger.debug(f"对话框关闭检查异常（可忽略）: {exc}")

            # 4. 点击批量编辑按钮
            logger.info("点击批量编辑按钮...")
            try:
                batch_edit_btn = self.page.locator("button:has-text('批量编辑')").first
                await batch_edit_btn.wait_for(state="visible", timeout=5000)

                try:
                    await batch_edit_btn.click(timeout=5000)
                    logger.success("✓ 已点击批量编辑按钮")
                except Exception:
                    logger.warning("⚠️ 普通点击失败，尝试强制点击...")
                    await batch_edit_btn.click(force=True)
                    logger.success("✓ 强制点击成功")

                try:
                    popover_selectors = [
                        ".batch-editor-group-box",
                        ".jx-popper:has(.batch-editor-group-field)",
                        "[id*='jx-id-']:has(.batch-editor-group-field)",
                    ]

                    menu_found = False
                    for selector in popover_selectors:
                        try:
                            menu = self.page.locator(selector).first
                            await menu.wait_for(state="visible", timeout=3000)
                            logger.success(f"✓ Popover菜单已显示: {selector}")
                            menu_found = True
                            break
                        except Exception:
                            continue

                    if not menu_found:
                        logger.warning("⚠️ 未检测到Popover菜单，但继续执行")
                        await self.page.wait_for_timeout(1000)

                except Exception as exc:
                    logger.debug(f"等待Popover菜单异常: {exc}")
                    await self.page.wait_for_timeout(1000)

            except Exception as exc:
                logger.error(f"无法进入批量编辑: {exc}")
                return False

            logger.success("✓ 批量编辑准备就绪")
            return True

        except Exception as exc:
            logger.error(f"导航失败: {exc}")
            return False

    async def click_step(self, step_name: str, step_num: str) -> bool:
        """智能点击步骤（处理遮挡问题）."""
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"[步骤 {step_num}] {step_name}")
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        try:
            dialog_selectors = [
                ".multi-batch-edit-dialog",
                ".el-dialog__wrapper:has-text('批量产品编辑')",
                ".batch-edit-detail-dialog",
            ]

            step_elem = None

            for dialog_selector in dialog_selectors:
                try:
                    dialog = self.page.locator(dialog_selector).first
                    if await dialog.count() == 0:
                        continue

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
                                logger.debug(f"  使用选择器: {selector}")
                                break
                        except Exception:
                            continue

                    if step_elem:
                        break

                except Exception as exc:
                    logger.debug(f"  弹窗选择器 {dialog_selector} 检查失败: {exc}")
                    continue

            if not step_elem:
                logger.error(f"  ✗ 未找到步骤: {step_name}")
                logger.debug(f"  已尝试的弹窗选择器: {dialog_selectors}")
                return False

            try:
                await step_elem.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(500)
            except Exception:
                pass

            try:
                await step_elem.click(timeout=5000)
                logger.success("  ✓ 已点击步骤导航")
            except PlaywrightTimeoutError:
                logger.warning("  ⚠️ 元素被遮挡，尝试强制点击...")
                try:
                    await step_elem.click(force=True)
                    logger.success("  ✓ 强制点击成功")
                except Exception as exc:
                    logger.error(f"  ✗ 强制点击也失败: {exc}")
                    return False

            logger.info("  ⏳ 等待步骤页面加载...")
            try:
                preview_btn = self.page.locator("button:has-text('预览')").first
                await preview_btn.wait_for(state="visible", timeout=5000)
                logger.success("  ✓ 步骤页面已加载（预览按钮可见）")
            except Exception:
                logger.debug("  未检测到预览按钮，使用fallback等待")
                await self.page.wait_for_timeout(1000)

            return True

        except Exception as exc:
            logger.error(f"  ✗ 点击失败: {exc}")
            return False

    async def click_preview_and_save(self, step_name: str) -> bool:
        """点击预览和保存按钮（先预览，再保存）."""
        try:
            dialog_selectors = [
                ".multi-batch-edit-dialog",
                ".el-dialog__wrapper:has-text('批量产品编辑')",
                ".batch-edit-detail-dialog",
            ]

            active_dialog = None
            for selector in dialog_selectors:
                try:
                    dialog = self.page.locator(selector).first
                    if await dialog.count() > 0 and await dialog.is_visible():
                        active_dialog = selector
                        logger.debug(f"  找到活跃弹窗: {selector}")
                        break
                except Exception:
                    continue

            if not active_dialog:
                logger.warning("  ⚠️ 未找到批量编辑弹窗")
                active_dialog = ""

            logger.info("  📋 第1步：点击预览...")
            preview_selectors = [
                f"{active_dialog} button:has-text('预览')".strip(),
                f"{active_dialog} button.el-button:has-text('预览')".strip(),
                f"{active_dialog} button[type='button']:has-text('预览')".strip(),
            ]

            preview_clicked = False
            for selector in preview_selectors:
                try:
                    all_btns = await self.page.locator(selector).all()
                    logger.debug(f"  预览选择器 {selector} 找到 {len(all_btns)} 个")

                    for btn in all_btns:
                        if await btn.is_visible():
                            await btn.scroll_into_view_if_needed()
                            await self.page.wait_for_timeout(300)
                            await btn.click()
                            logger.success("  ✓ 预览按钮已点击")
                            await self.page.wait_for_timeout(2000)
                            logger.info("  ⏳ 等待预览加载...")
                            preview_clicked = True
                            break

                    if preview_clicked:
                        break

                except Exception as exc:
                    logger.debug(f"    预览选择器 {selector} 失败: {exc}")
                    continue

            if not preview_clicked:
                logger.warning("  ⚠️ 未找到预览按钮，跳过预览直接保存")
            else:
                logger.success("  ✓ 预览完成")

            logger.info("  💾 第2步：点击保存修改...")

            save_selectors = [
                f"{active_dialog} button:has-text('保存修改')".strip(),
                f"{active_dialog} button.el-button:has-text('保存修改')".strip(),
                f"{active_dialog} button[type='button']:has-text('保存修改')".strip(),
                f"{active_dialog} button:has-text('保存')".strip(),
            ]

            save_clicked = False
            for selector in save_selectors:
                try:
                    all_btns = await self.page.locator(selector).all()
                    logger.debug(f"  保存选择器 {selector} 找到 {len(all_btns)} 个")

                    for btn in all_btns:
                        try:
                            if await btn.is_visible():
                                try:
                                    await btn.click(timeout=5000)
                                    logger.success("  ✓ 保存按钮已点击")
                                except Exception:
                                    logger.warning("  ⚠️ 普通点击失败，尝试强制点击...")
                                    await btn.click(force=True)
                                    logger.success("  ✓ 强制点击成功")
                                save_clicked = True
                                break
                        except Exception:
                            continue

                    if save_clicked:
                        break

                except Exception as exc:
                    logger.debug(f"    保存选择器 {selector} 失败: {exc}")
                    continue

            if not save_clicked:
                logger.error("  ✗ 未找到可用的保存按钮")
                try:
                    screenshot_path = f"debug_save_button_{step_name}.png"
                    await self.page.screenshot(path=screenshot_path)
                    logger.info(f"  📸 已保存调试截图: {screenshot_path}")
                except Exception:
                    pass
                return False

            logger.info("  ⏳ 等待保存完成...")
            try:
                await self.page.wait_for_timeout(1500)

                logger.info("  🔘 查找关闭按钮...")
                close_selectors = [
                    "button:has-text('关闭')",
                    "button.el-button:has-text('关闭')",
                    "button:has-text('确定')",
                    "button:has-text('完成')",
                ]

                close_clicked = False
                for _ in range(15):
                    for selector in close_selectors:
                        try:
                            all_btns = await self.page.locator(selector).all()
                            for btn in all_btns:
                                if await btn.is_visible():
                                    logger.debug(f"  找到关闭按钮: {selector}")
                                    try:
                                        await btn.click(timeout=3000)
                                        logger.success("  ✓ 关闭按钮已点击")
                                        close_clicked = True
                                        break
                                    except Exception:
                                        try:
                                            await btn.click(force=True)
                                            logger.success("  ✓ 强制点击关闭按钮成功")
                                            close_clicked = True
                                            break
                                        except Exception:
                                            continue
                            if close_clicked:
                                break
                        except Exception:
                            continue

                    if close_clicked:
                        break

                    await self.page.wait_for_timeout(1500)

                if close_clicked:
                    logger.success(f"  ✓ [{step_name}] 保存完成并关闭对话框")
                    await self.page.wait_for_timeout(1000)
                    return True

                logger.warning("  ⚠️ 未找到关闭按钮，可能已自动关闭")
                return True

            except Exception as exc:
                logger.warning(f"  ⚠️ 处理关闭按钮时出错: {exc}")
                return True

        except Exception as exc:
            logger.error(f"  ✗ 预览/保存失败: {exc}")
            return False

    async def execute_all_steps(
        self,
        product_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """执行18步完整流程."""
        logger.info("\n" + "=" * 60)
        logger.info("开始执行批量编辑18步")
        logger.info("=" * 60 + "\n")

        results: Dict[str, Any] = {"total": 18, "success": 0, "failed": 0, "steps": []}

        cost_price = product_data.get("cost_price") if product_data else None
        product_name = product_data.get("product_name") if product_data else None
        weight = product_data.get("weight") if product_data else None
        length = product_data.get("length") if product_data else None
        width = product_data.get("width") if product_data else None
        height = product_data.get("height") if product_data else None

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
            (
                "7.10",
                "尺寸",
                self.step_10_dimensions(
                    length=length,
                    width=width,
                    height=height,
                    product_name=product_name,
                ),
            ),
            ("7.11", "平台SKU", self.step_11_platform_sku()),
            ("7.12", "SKU分类", self.step_12_sku_category()),
            ("7.13", "尺码表", self.step_13_size_chart()),
            (
                "7.14",
                "建议售价",
                self.step_14_suggested_price(
                    cost_price=cost_price,
                    product_name=product_name,
                ),
            ),
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
                    results["steps"].append(
                        {"step": step_num, "name": step_name, "status": "success"},
                    )
                    logger.success(f"✓ 步骤{step_num}完成\n")
                else:
                    results["failed"] += 1
                    results["steps"].append(
                        {"step": step_num, "name": step_name, "status": "failed"},
                    )
                    logger.error(f"✗ 步骤{step_num}失败\n")

            except Exception as exc:
                results["failed"] += 1
                results["steps"].append(
                    {"step": step_num, "name": step_name, "status": "error", "error": str(exc)},
                )
                logger.error(f"✗ 步骤{step_num}出错: {exc}\n")

        logger.info("\n" + "=" * 60)
        logger.info("批量编辑18步完成")
        logger.info("=" * 60)
        logger.info(f"总计: {results['total']} 步")
        logger.info(f"成功: {results['success']} 步")
        logger.info(f"失败: {results['failed']} 步")
        logger.info(f"成功率: {results['success'] * 100 // results['total']}%")
        logger.info("=" * 60 + "\n")

        return results

