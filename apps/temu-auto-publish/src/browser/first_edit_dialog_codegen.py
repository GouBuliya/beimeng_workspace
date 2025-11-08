"""
@PURPOSE: 使用 Codegen 录制逻辑填写首次编辑弹窗中的基础规格字段
@OUTLINE:
  - def smart_retry(): 智能重试装饰器,用于关键操作的自动重试
  - async def fill_first_edit_dialog_codegen(): 主函数,填写弹窗内所有字段
  - async def _fill_title(): 填写产品标题
  - async def _fill_basic_specs(): 填写价格/库存/重量/尺寸等基础字段
  - async def _upload_size_chart_local(): 上传尺寸图(简化版,参考batch_edit实现)
  - async def _click_save(): 点击保存修改按钮
@GOTCHAS:
  - 避免使用动态 ID 选择器(如 #jx-id-6368-578)
  - 优先使用 get_by_label、get_by_role、get_by_placeholder 等稳定定位器
  - 跳过图片/视频上传部分,由 FirstEditController 的 upload_* 方法处理
  - 尺寸图上传使用简化逻辑,参考 batch_edit_codegen 的外包装上传方式
@DEPENDENCIES:
  - 外部: playwright, loguru
@RELATED: first_edit_controller.py, first_edit_codegen.py, batch_edit_codegen.py
"""

from __future__ import annotations

import asyncio
import re
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

from loguru import logger
from playwright.async_api import Locator, Page

# 定义泛型类型
T = TypeVar("T")


def smart_retry(max_attempts: int = 2, delay: float = 0.5, exceptions: tuple = (Exception,)):
    """智能重试装饰器,用于关键操作的自动重试。

    Args:
        max_attempts: 最大尝试次数(默认2次,即1次重试)。
        delay: 重试间隔秒数(默认0.5秒)。
        exceptions: 需要捕获并重试的异常类型元组。

    Returns:
        装饰后的函数。
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt < max_attempts:
                        logger.warning(
                            f"⚠ {func.__name__} 执行失败(第{attempt}次尝试),{delay}秒后重试: {exc}"
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"✗ {func.__name__} 执行失败(已达最大重试次数{max_attempts})")
            raise last_exception  # type: ignore

        return wrapper

    return decorator


async def fill_first_edit_dialog_codegen(page: Page, payload: dict[str, Any]) -> bool:
    """使用 Codegen 录制逻辑填写首次编辑弹窗的所有字段.

    Args:
        page: Playwright 页面对象.
        payload: 包含所有需要填写的字段数据的字典.
            - title: 产品标题
            - product_number: 商品编号 (如 "RC2808645")
            - price: SKU 价格
            - supply_price: 供货价
            - stock: SKU 库存
            - weight_g: 重量 (克)
            - length_cm: 长度 (厘米)
            - width_cm: 宽度 (厘米)
            - height_cm: 高度 (厘米)
            - model_spec_name: 多规格新增维度名称(默认“型号”)
            - model_spec_option: 规格选项值(默认使用 product_number)
            - supplier_link: 供货商链接

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
        # await page.wait_for_timeout(1000)
        logger.success("✓ 编辑弹窗已加载")

        # 1. 填写标题
        if not await _fill_title(page, payload.get("title", "")):
            return False

        # 2. 填写基础规格字段
        logger.info("跳过销售属性/多规格, 仅填写价格与库存等基础字段")
        if not await _fill_basic_specs(page, payload):
            return False

        # 4. 记录供货商链接
        if not await _fill_supplier_link(page, payload.get("supplier_link", "")):
            return False

        # 5. 上传尺寸图（如果提供了图片路径）
        size_chart_image = payload.get("size_chart_image", "")
        if size_chart_image:
            logger.info("开始上传尺寸图...")
            upload_success = await _upload_size_chart_local(page, size_chart_image)
            if upload_success:
                logger.success("✓ 尺寸图上传成功")
            else:
                logger.warning("⚠️ 尺寸图上传失败，继续后续流程")
        else:
            logger.info("跳过尺寸图上传（未提供图片路径）")

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
                # await page.wait_for_timeout(500)
                return True
            except Exception as exc:
                logger.debug("标题输入失败: {}", exc)
                continue

        logger.error("✗ 未能找到标题输入框")
        return False

    except Exception as exc:
        logger.error(f"填写标题失败: {exc}")
        return False


async def _fill_basic_specs(page: Page, payload: dict[str, Any]) -> bool:
    """填写价格、库存、重量、尺寸等基础字段."""

    try:
        logger.info("填写基础规格字段...")
        dialog = page.locator(".collect-box-editor-dialog-V2, .jx-overlay-dialog").first
        await dialog.wait_for(state="visible", timeout=3_000)
    except Exception as exc:
        logger.error("未能定位首次编辑弹窗: %s", exc)
        return False

    variants = payload.get("variants") or []
    if variants:
        if not await _fill_variant_rows(dialog, payload, variants, page):
            return False
    else:
        await _fill_single_value_fields(dialog, payload)

    await _fill_dimension_fields(dialog, payload)
    return True


async def _fill_single_value_fields(dialog: Locator, payload: dict[str, Any]) -> None:
    """在无多规格时填充统一价格和库存字段."""

    field_map = [
        ("price", ["input[placeholder*='建议售价']", "input[placeholder*='售价']"]),
        ("supply_price", ["input[placeholder*='供货价']", "input[placeholder*='供货价格']"]),
        (
            "source_price",
            [
                "input[placeholder*='货源价']",
                "input[placeholder*='来源价格']",
                "input[placeholder*='采购价']",
            ],
        ),
        ("stock", ["input[placeholder*='库存']", "input[placeholder*='数量']"]),
    ]

    for field, selectors in field_map:
        value = payload.get(field)
        if value is None:
            continue
        str_value = str(value)
        success = await _fill_first_match(dialog, selectors, str_value)
        if success:
            logger.debug("✓ 字段 %s 已写入 %s", field, str_value)
        else:
            logger.debug("字段 %s 未找到任何输入框", field)


async def _fill_variant_rows(
    dialog: Locator, payload: dict[str, Any], variants: list[dict[str, Any]], page: Page
) -> bool:
    """按行填写多规格价格与库存."""

    row_selector = ".pro-virtual-scroll__row.pro-virtual-table__row, .pro-virtual-table__row"
    rows = dialog.locator(row_selector)
    row_count = await rows.count()
    if row_count == 0:
        await _dump_dialog_snapshot(page, "variant_rows_missing.html")
        logger.error("✗ 未找到规格行，无法填写多规格数据")
        return False

    field_map = [
        ("price", ["input[placeholder*='建议售价']", "input[placeholder*='售价']"]),
        ("supply_price", ["input[placeholder*='供货价']", "input[placeholder*='供货价格']"]),
        (
            "source_price",
            [
                "input[placeholder*='货源价']",
                "input[placeholder*='来源价格']",
                "input[placeholder*='采购价']",
            ],
        ),
        ("stock", ["input[placeholder*='库存']", "input[placeholder*='数量']"]),
    ]

    for index, variant in enumerate(variants):
        if index >= row_count:
            logger.warning("⚠️ 规格行数量不足，忽略多余的规格数据 (row=%s)", index + 1)
            break

        row = rows.nth(index)
        for field, selectors in field_map:
            value = variant.get(field, payload.get(field))
            if value is None:
                continue
            str_value = str(value)
            filled = await _fill_row_field(row, selectors, str_value)
            if filled:
                logger.debug("✓ 规格行%s 字段%s 写入 %s", index + 1, field, str_value)
            else:
                logger.debug("规格行%s 字段%s 未找到输入框", index + 1, field)

    return True


async def _fill_dimension_fields(dialog: Locator, payload: dict[str, Any]) -> None:
    """填写重量与尺寸字段，所有匹配输入统一赋值."""

    field_map = [
        (
            "weight_g",
            [
                "input[placeholder*='重量'][type='number']",
                "input[placeholder*='重量'][type='text']",
            ],
        ),
        ("length_cm", ["input[placeholder*='长']", "input[aria-label*='长']"]),
        ("width_cm", ["input[placeholder*='宽']", "input[aria-label*='宽']"]),
        ("height_cm", ["input[placeholder*='高']", "input[aria-label*='高']"]),
    ]

    for field, selectors in field_map:
        value = payload.get(field)
        if value is None:
            continue
        str_value = str(value)
        success = await _fill_all_matches(dialog, selectors, str_value)
        if success:
            logger.debug("✓ 字段 %s 已写入所有匹配输入", field)
        else:
            logger.debug("字段 %s 未能写入任何输入", field)


async def _fill_row_field(row: Locator, selectors: list[str], value: str) -> bool:
    for selector in selectors:
        locator = row.locator(selector).first
        if await locator.count():
            try:
                await locator.wait_for(state="visible", timeout=2_000)
                await _set_input_value(locator, value)
                return True
            except Exception:
                continue
    return False


async def _fill_first_match(container: Locator, selectors: list[str], value: str) -> bool:
    for selector in selectors:
        locator = container.locator(selector).first
        if await locator.count():
            try:
                await locator.wait_for(state="visible", timeout=2_000)
                await _set_input_value(locator, value)
                return True
            except Exception:
                continue
    return False


async def _fill_all_matches(container: Locator, selectors: list[str], value: str) -> bool:
    filled = False
    for selector in selectors:
        locator = container.locator(selector)
        count = await locator.count()
        for index in range(count):
            input_locator = locator.nth(index)
            try:
                await input_locator.wait_for(state="visible", timeout=2_000)
                await _set_input_value(input_locator, value)
                filled = True
            except Exception:
                continue
    return filled


async def _click_save(page: Page) -> bool:
    """点击保存修改按钮.

    Args:
        page: Playwright 页面对象.

    Returns:
        bool: 是否成功点击保存按钮.
    """
    try:
        logger.info("点击保存修改按钮...")

        dialog = page.get_by_role("dialog")
        footer = dialog.locator(".jx-dialog__footer, .pro-dialog__footer").last

        candidate_buttons = [
            footer.locator("button", has_text=re.compile(r"保存修改")),
            page.get_by_role("button", name="保存修改"),
        ]

        for candidate in candidate_buttons:
            total = await candidate.count()
            if total == 0:
                continue
            save_btn = candidate.nth(total - 1)
            try:
                await save_btn.wait_for(state="visible", timeout=2_000)
                await _dismiss_scroll_overlay(page)
                await save_btn.scroll_into_view_if_needed()
                await save_btn.focus()
                await save_btn.click()
                logger.success("✓ 已点击保存按钮")

                # 等待保存成功提示或按钮禁用
                # await page.wait_for_timeout(800)
                toast = page.locator(".jx-message--success, .el-message--success")
                try:
                    await toast.wait_for(state="visible", timeout=1_500)
                    await toast.wait_for(state="hidden", timeout=2_000)
                except Exception:
                    pass
                return True
            except Exception:
                continue

        await _dump_dialog_snapshot(page, "save_button_failure.html")
        logger.error("✗ 未能找到保存按钮")
        return False

    except Exception as exc:
        logger.error(f"点击保存按钮失败: {exc}")
        return False


async def _fill_supplier_link(page: Page, supplier_link: str) -> bool:
    """填写供货商链接."""

    if not supplier_link:
        return True

    try:
        textbox = page.get_by_role("textbox", name=re.compile("供货商链接"))
        if await textbox.count():
            await textbox.first.click()
            await textbox.first.press("ControlOrMeta+a")
            await textbox.first.fill(supplier_link)
            # await page.wait_for_timeout(200)
            logger.success("✓ 已更新供货商链接")
            return True
        logger.warning("⚠️ 未找到供货商链接输入框")
        return True
    except Exception as exc:
        logger.error("填写供货商链接失败: %s", exc)
        return False


@smart_retry(max_attempts=2, delay=0.5)
async def _upload_size_chart_local(page: Page, image_path: str) -> bool:
    """上传尺寸图（本地文件）- 参考 batch_edit 的外包装图片上传逻辑.
    
    流程（参考 _step_05_outer_package）:
    1. 滚动弹窗到底部，确保尺寸图区域可见
    2. 点击图片上传区域的 radio 按钮（触发文件输入框）
    3. 上传文件到 input[type='file']
    
    Args:
        page: Playwright 页面对象.
        image_path: 本地图片文件的绝对路径.
    
    Returns:
        是否上传成功.
    """
    if not image_path:
        logger.info("未提供图片路径，跳过尺寸图上传")
        return True

    if not Path(image_path).exists():
        logger.warning("⚠️ 图片文件不存在: %s", image_path)
        return False

    logger.info("上传尺寸图: %s", image_path)

    # 调试：上传前截图
    debug_dir = Path(__file__).resolve().parents[2] / "data" / "debug_screenshots"
    debug_dir.mkdir(parents=True, exist_ok=True)

    try:
        await page.screenshot(path=str(debug_dir / "before_size_chart_upload.png"))
        logger.debug("已保存上传前截图: %s", debug_dir / "before_size_chart_upload.png")
    except Exception:
        pass

    # 步骤1: 滚动弹窗到底部，确保尺寸图区域渲染
    dialog_locator = page.get_by_role("dialog")
    dialog: Locator | None = None
    try:
        if await dialog_locator.count() > 0:
            dialog = dialog_locator.first
            await dialog.evaluate("el => { el.scrollTop = el.scrollHeight; }")
            await page.wait_for_timeout(500)
            logger.debug("✓ 已滚动首次编辑弹窗到底部")
    except Exception as exc:
        logger.debug(f"滚动弹窗失败: {exc}")

    # 步骤2: 精确定位尺寸图区域（可选，但尽量缩小范围）
    size_chart_group: Locator | None = None
    if dialog is not None:
        size_chart_locators = [
            dialog.get_by_role("group", name=re.compile("尺寸图表")),
            dialog.locator("text=尺寸图表").locator(".."),
        ]
    else:
        size_chart_locators = [
            page.get_by_role("group", name=re.compile("尺寸图表")),
            page.locator("text=尺寸图表").locator(".."),
        ]

    for locator in size_chart_locators:
        try:
            if await locator.count() > 0:
                candidate = locator.first
                await candidate.scroll_into_view_if_needed()
                await page.wait_for_timeout(200)
                size_chart_group = candidate
                logger.debug("✓ 已定位到尺寸图表区域")
                break
        except Exception:
            continue

    # 步骤3: 尝试点击触发上传的按钮或单选框
    trigger_clicked = False
    try:
        if size_chart_group is not None:
            radio_btn = size_chart_group.locator("role=radio").filter(has_text="addImages")
        else:
            radio_btn = page.get_by_role("radio").filter(has_text="addImages")

        if await radio_btn.count() > 0:
            await radio_btn.last.click()
            await page.wait_for_timeout(150)
            trigger_clicked = True
            logger.debug("✓ 已点击尺寸图区域 radio 按钮")
    except Exception as exc:
        logger.debug(f"点击尺寸图 radio 按钮失败: {exc}")

    # 若未触发，则尝试点击“上传文件”或“添加图片”等按钮
    upload_trigger_locators: list[Locator] = []
    if size_chart_group is not None:
        upload_trigger_locators.extend(
            [
                size_chart_group.get_by_role("button", name=re.compile("上传文件|添加图片")),
                size_chart_group.locator(".product-picture-item-add"),
            ]
        )

    if dialog is not None:
        upload_trigger_locators.append(dialog.get_by_role("button", name=re.compile("上传文件|添加图片")))

    upload_trigger_locators.append(page.get_by_role("button", name=re.compile("上传文件|添加图片")))

    for locator in upload_trigger_locators:
        try:
            if await locator.count() > 0:
                target = locator.first
                if await target.is_visible():
                    await target.click()
                    await page.wait_for_timeout(200)
                    trigger_clicked = True
                    logger.debug("✓ 已点击上传触发按钮")
                    break
        except Exception:
            continue

    # 某些情况下会弹出“本地上传”菜单，需要明确选择
    upload_menu_locators = [
        page.get_by_role("menuitem", name=re.compile("本地上传")),
        page.locator("button:has-text('本地上传')"),
        page.locator("li:has-text('本地上传')"),
    ]
    for locator in upload_menu_locators:
        try:
            if await locator.count() > 0:
                target = locator.first
                if await target.is_visible():
                    await target.click()
                    await page.wait_for_timeout(150)
                    logger.debug("✓ 已选择本地上传选项")
                    break
        except Exception:
            continue

    if not trigger_clicked:
        logger.warning("未能触发尺寸图上传控件，跳过上传")
        return False

    # 步骤4: 查找文件输入框并上传（优先在当前对话框/区域内）
    upload_success = False
    candidate_inputs: list[Locator] = []
    if size_chart_group is not None:
        candidate_inputs.append(size_chart_group.locator("input[type='file']"))
    if dialog is not None:
        candidate_inputs.append(dialog.locator("input[type='file']"))
    candidate_inputs.append(page.locator("input[type='file']"))

    for locator in candidate_inputs:
        try:
            count = await locator.count()
            if count == 0:
                continue
            # 优先使用可见且启用的输入框
            for index in reversed(range(count)):
                file_input = locator.nth(index)
                try:
                    if await file_input.is_enabled():
                        await file_input.set_input_files(image_path)
                        upload_success = True
                        logger.success("✓ 尺寸图已上传: {}", image_path)
                        break
                except Exception:
                    continue
            if upload_success:
                break
        except Exception:
            continue

    if not upload_success:
        logger.warning("未找到可用的文件输入框，尺寸图上传跳过")
        return False

    await page.wait_for_timeout(500)

    # 调试：上传后截图
    try:
        await page.screenshot(path=str(debug_dir / "after_size_chart_upload.png"))
        logger.debug("已保存上传后截图: %s", debug_dir / "after_size_chart_upload.png")
    except Exception:
        pass

    return True


async def _dismiss_scroll_overlay(page: Page) -> None:
    """尝试关闭可能遮挡输入框的浮层."""

    overlay = page.locator(".scroll-menu-pane__content")
    if not await overlay.count():
        return

    try:
        await page.keyboard.press("Escape")
        await overlay.first.wait_for(state="hidden", timeout=1000)
        logger.debug("已通过 Escape 关闭浮层")
    except Exception:
        try:
            await page.mouse.click(5, 5)
            await overlay.first.wait_for(state="hidden", timeout=1000)
            logger.debug("已通过点击页面关闭浮层")
        except Exception:
            logger.debug("浮层未完全关闭, 将继续尝试填写")


async def _set_input_value(locator, value: str) -> None:
    """使用脚本方式设置输入框的值并触发 input 事件."""

    try:
        await locator.scroll_into_view_if_needed()
        await locator.click()
        await locator.press("ControlOrMeta+a")
        await locator.fill(value)
    except Exception:
        await locator.evaluate("(el) => { el.focus(); el.select && el.select(); }")
        await locator.evaluate(
            "(el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); el.dispatchEvent(new Event('change', { bubbles: true })); }",
            value,
        )


async def _dump_dialog_snapshot(page: Page, filename: str) -> None:
    """将当前弹窗 HTML 快照写入调试目录."""

    try:
        dialog = page.get_by_role("dialog")
        html = await dialog.inner_html()
        target = Path(__file__).resolve().parents[2] / "data" / "debug_screenshots" / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        logger.debug("已写入调试快照: %s", target)
    except Exception as exc:
        logger.warning("写入调试快照失败: %s", exc)
