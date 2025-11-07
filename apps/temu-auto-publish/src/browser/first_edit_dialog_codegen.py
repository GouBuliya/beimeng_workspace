"""
@PURPOSE: 使用 Codegen 录制逻辑填写首次编辑弹窗的所有字段
@OUTLINE:
  - async def fill_first_edit_dialog_codegen(): 主函数,填写弹窗内所有字段
  - async def _fill_title(): 填写产品标题
  - async def _fill_attributes(): 填写产品属性(产地、推荐用途、形状等)
  - async def _switch_to_multi_spec(): 切换到多规格模式
  - async def _fill_sku_info(): 填写 SKU 信息(价格、库存、重量、尺寸)
  - async def _click_save(): 点击保存修改按钮
@GOTCHAS:
  - 避免使用动态 ID 选择器(如 #jx-id-6368-578)
  - 优先使用 get_by_label、get_by_role、get_by_placeholder 等稳定定位器
  - 跳过图片/视频上传部分,由 FirstEditController 的 upload_* 方法处理
@DEPENDENCIES:
  - 外部: playwright, loguru
@RELATED: first_edit_controller.py, first_edit_codegen.py
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from playwright.async_api import Page


async def fill_first_edit_dialog_codegen(page: Page, payload: dict[str, Any]) -> bool:
    """使用 Codegen 录制逻辑填写首次编辑弹窗的所有字段.

    Args:
        page: Playwright 页面对象.
        payload: 包含所有需要填写的字段数据的字典.
            - title: 产品标题
            - origin: 产地 (如 "Guangdong,China")
            - product_use: 产品推荐用途 (如 "多用途")
            - shape: 形状 (如 "矩形")
            - material: 材料 (如 "塑料")
            - closure_type: 闭合类型 (如 "磁性")
            - style: 风格 (如 "现代")
            - brand_name: 品牌名 (如 "佰森物语")
            - product_number: 商品编号 (如 "RC2808645")
            - price: SKU 价格
            - stock: SKU 库存
            - weight_g: 重量 (克)
            - length_cm: 长度 (厘米)
            - width_cm: 宽度 (厘米)
            - height_cm: 高度 (厘米)

    Returns:
        bool: 如果成功填写并保存则返回 True,否则返回 False.

    Examples:
        >>> payload = {
        ...     "title": "五层储物柜A092 - 可折叠带盖设计 A0049型号",
        ...     "origin": "Guangdong,China",
        ...     "product_use": "多用途",
        ...     "shape": "矩形",
        ...     "material": "塑料",
        ...     "closure_type": "磁性",
        ...     "style": "现代",
        ...     "brand_name": "佰森物语",
        ...     "product_number": "RC2808645",
        ...     "price": 578.99,
        ...     "stock": 99,
        ...     "weight_g": 6000,
        ...     "length_cm": 75,
        ...     "width_cm": 71,
        ...     "height_cm": 61,
        ... }
        >>> success = await fill_first_edit_dialog_codegen(page, payload)
    """
    logger.info("=" * 60)
    logger.info("使用 Codegen 录制逻辑填写首次编辑弹窗")
    logger.info("=" * 60)

    try:
        # 等待弹窗加载完成
        await page.wait_for_selector(".jx-overlay-dialog", state="visible", timeout=10000)
        await page.wait_for_timeout(1000)
        logger.success("✓ 编辑弹窗已加载")

        # 1. 填写标题
        if not await _fill_title(page, payload.get("title", "")):
            return False

        # 2. 填写产品属性
        if not await _fill_attributes(page, payload):
            return False

        # 3. 切换到多规格模式并填写 SKU 信息
        if not await _switch_to_multi_spec(page):
            return False

        # 4. 填写 SKU 信息
        if not await _fill_sku_info(page, payload):
            return False

        # 5. 跳过图片/视频上传(由 FirstEditController 处理)
        logger.info("跳过图片/视频上传部分")

        # 6. 保存修改
        if not await _click_save(page):
            return False

        logger.success("✓ 首次编辑弹窗填写完成")
        return True

    except Exception as exc:
        logger.error(f"填写首次编辑弹窗失败: {exc}")
        return False


async def _fill_title(page: Page, title: str) -> bool:
    """填写产品标题.

    Args:
        page: Playwright 页面对象.
        title: 产品标题.

    Returns:
        bool: 是否成功填写.
    """
    try:
        logger.info(f"填写产品标题: {title}")

        # 尝试多种选择器策略
        dialog = page.locator(".collect-box-editor-dialog-V2, .jx-overlay-dialog").first
        try:
            await dialog.wait_for(state="visible", timeout=3_000)
        except Exception:
            logger.debug("标题填写时未能定位到弹窗容器, 使用全局查找")

        candidate_locators = [
            dialog.locator("input.jx-input__inner[type='text']").first,
            dialog.locator("input[placeholder*='标题']").first,
            dialog.locator("input[placeholder*='Title']").first,
            page.locator(".collect-box-editor-dialog-V2 input.jx-input__inner[type='text']").first,
            page.get_by_placeholder("请输入标题", exact=False),
        ]

        for locator in candidate_locators:
            try:
                await locator.wait_for(state="visible", timeout=2_000)
            except Exception:
                continue

            try:
                await locator.click()
                await locator.press("ControlOrMeta+a")
                await locator.fill(title)
                logger.success("✓ 标题已填写")
                await page.wait_for_timeout(500)
                return True
            except Exception as exc:
                logger.debug("标题输入失败: {}", exc)
                continue

        logger.error("✗ 未能找到标题输入框")
        return False

    except Exception as exc:
        logger.error(f"填写标题失败: {exc}")
        return False


async def _fill_attributes(page: Page, payload: dict[str, Any]) -> bool:
    """填写产品属性(产地、推荐用途、形状、材料、闭合类型、风格、品牌名、商品编号).

    Args:
        page: Playwright 页面对象.
        payload: 包含属性数据的字典.

    Returns:
        bool: 是否成功填写所有属性.
    """
    try:
        logger.info("填写产品属性...")

        # 定义属性字段映射(按照 Codegen 录制的顺序)
        attributes = [
            ("origin", "产地"),
            ("product_use", "产品推荐用途"),
            ("shape", "形状"),
            ("material", "材料"),
            ("closure_type", "闭合类型"),
            ("style", "风格"),
            ("brand_name", "品牌名"),
            ("product_number", "商品编号"),
        ]

        # 获取所有属性输入框
        attribute_inputs = page.locator(".product-attribute-item .jx-input__inner")
        input_count = await attribute_inputs.count()
        logger.debug(f"找到 {input_count} 个属性输入框")

        # 逐个填写属性
        for index, (key, label) in enumerate(attributes):
            value = payload.get(key, "")
            if not value:
                logger.warning(f"⚠️ 属性 {label} 未提供值,跳过")
                continue

            try:
                # 使用索引定位输入框
                if index < input_count:
                    input_field = attribute_inputs.nth(index)
                    await input_field.click()
                    await input_field.press("ControlOrMeta+a")
                    await input_field.fill(str(value))
                    logger.success(f"✓ 已填写 {label}: {value}")
                    await page.wait_for_timeout(300)
                else:
                    logger.warning(f"⚠️ 属性 {label} 索引超出范围,跳过")
            except Exception as exc:
                logger.warning(f"⚠️ 填写属性 {label} 失败: {exc}")
                continue

        logger.success("✓ 产品属性填写完成")
        return True

    except Exception as exc:
        logger.error(f"填写产品属性失败: {exc}")
        return False


async def _switch_to_multi_spec(page: Page) -> bool:
    """切换到多规格模式.

    Args:
        page: Playwright 页面对象.

    Returns:
        bool: 是否成功切换.
    """
    try:
        logger.info("切换到多规格模式...")

        # 点击"多规格"标签
        multi_spec_selectors = [
            "text='多规格'",
            "label:has-text('多规格')",
            ".jx-radio-button:has-text('多规格')",
        ]

        for selector in multi_spec_selectors:
            try:
                multi_spec_btn = page.locator(selector).first
                if await multi_spec_btn.is_visible(timeout=2000):
                    await multi_spec_btn.click()
                    logger.success(f"✓ 已切换到多规格模式 (选择器: {selector})")
                    await page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue

        logger.warning("⚠️ 未能找到多规格切换按钮,可能已处于多规格模式")
        return True

    except Exception as exc:
        logger.error(f"切换到多规格模式失败: {exc}")
        return False


async def _fill_sku_info(page: Page, payload: dict[str, Any]) -> bool:
    """填写 SKU 信息(价格、库存、重量、尺寸).

    Args:
        page: Playwright 页面对象.
        payload: 包含 SKU 数据的字典.

    Returns:
        bool: 是否成功填写.
    """
    try:
        logger.info("填写 SKU 信息...")

        # 1. 填写价格
        price = payload.get("price", 0)
        price_input = page.locator("input[placeholder*='价格']").first
        if await price_input.is_visible(timeout=2000):
            await price_input.click()
            await price_input.press("ControlOrMeta+a")
            await price_input.fill(str(price))
            logger.success(f"✓ 已填写价格: {price}")
            await page.wait_for_timeout(300)

        # 2. 填写库存
        stock = payload.get("stock", 0)
        stock_input = page.locator("input[placeholder*='库存']").first
        if await stock_input.is_visible(timeout=2000):
            await stock_input.click()
            await stock_input.fill(str(stock))
            logger.success(f"✓ 已填写库存: {stock}")
            await page.wait_for_timeout(300)

        # 3. 切换重量单位到克(g)
        try:
            weight_unit_btn = page.get_by_text("KG").first
            if await weight_unit_btn.is_visible(timeout=1000):
                await weight_unit_btn.click()
                await page.wait_for_timeout(500)
                logger.success("✓ 已切换重量单位到克(g)")
        except Exception:
            logger.debug("重量单位切换跳过(可能已是克)")

        # 4. 填写重量
        weight_g = payload.get("weight_g", 0)
        weight_input = page.locator("input[placeholder*='重量']").first
        if await weight_input.is_visible(timeout=2000):
            await weight_input.click()
            await weight_input.fill(str(weight_g))
            logger.success(f"✓ 已填写重量: {weight_g}g")
            await page.wait_for_timeout(300)

        # 5. 填写尺寸(长、宽、高)
        length = payload.get("length_cm", 0)
        width = payload.get("width_cm", 0)
        height = payload.get("height_cm", 0)

        dimension_inputs = page.locator(
            "input[placeholder*='长度'], input[placeholder*='宽度'], input[placeholder*='高度']"
        )
        dimension_count = await dimension_inputs.count()

        if dimension_count >= 3:
            # 长度
            await dimension_inputs.nth(0).click()
            await dimension_inputs.nth(0).fill(str(length))
            logger.success(f"✓ 已填写长度: {length}cm")
            await page.wait_for_timeout(300)

            # 宽度
            await dimension_inputs.nth(1).click()
            await dimension_inputs.nth(1).fill(str(width))
            logger.success(f"✓ 已填写宽度: {width}cm")
            await page.wait_for_timeout(300)

            # 高度
            await dimension_inputs.nth(2).click()
            await dimension_inputs.nth(2).fill(str(height))
            logger.success(f"✓ 已填写高度: {height}cm")
            await page.wait_for_timeout(300)
        else:
            logger.warning(f"⚠️ 尺寸输入框数量不足(期望3个,实际{dimension_count}个)")

        logger.success("✓ SKU 信息填写完成")
        return True

    except Exception as exc:
        logger.error(f"填写 SKU 信息失败: {exc}")
        return False


async def _click_save(page: Page) -> bool:
    """点击保存修改按钮.

    Args:
        page: Playwright 页面对象.

    Returns:
        bool: 是否成功点击保存按钮.
    """
    try:
        logger.info("点击保存修改按钮...")

        # 尝试多种保存按钮选择器
        save_selectors = [
            "button:has-text('保存修改')",
            "button:has-text('保存')",
            ".jx-button--primary:has-text('保存')",
        ]

        for selector in save_selectors:
            try:
                save_btn = page.locator(selector).first
                if await save_btn.is_visible(timeout=2000):
                    await save_btn.click()
                    logger.success(f"✓ 已点击保存按钮 (选择器: {selector})")
                    await page.wait_for_timeout(2000)  # 等待保存完成
                    return True
            except Exception:
                continue

        logger.error("✗ 未能找到保存按钮")
        return False

    except Exception as exc:
        logger.error(f"点击保存按钮失败: {exc}")
        return False
