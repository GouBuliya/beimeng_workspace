"""
@PURPOSE: 使用 Codegen 录制逻辑填写首次编辑弹窗中的基础规格字段
@OUTLINE:
  - def smart_retry(): 智能重试装饰器,用于关键操作的自动重试
  - async def fill_first_edit_dialog_codegen(): 主函数,填写弹窗内所有字段
  - (步骤0) 规格名称填写 + SKU规格替换: 通过 payload.spec_unit 与 payload.spec_array 传入
  - async def _fill_title(): 填写产品标题
  - async def _fill_basic_specs(): 填写价格/库存/重量/尺寸等基础字段
  - async def _upload_size_chart_via_url(): 使用网络图片URL上传尺寸图
  - async def _upload_product_video_via_url(): 使用网络视频URL上传产品视频(支持API记录)
  - def _save_captured_api(): 保存捕获的 API 请求到文件
  - async def _handle_existing_video_prompt(): 处理已有视频的删除确认提示
  - async def _click_save(): 点击保存修改按钮
@GOTCHAS:
  - 避免使用动态 ID 选择器(如 #jx-id-6368-578)
  - 优先使用 get_by_label,get_by_role,get_by_placeholder 等稳定定位器
  - 跳过图片/视频上传部分,由 FirstEditController 的 upload_* 方法处理
  - 尺寸图上传仅支持网络图片URL,需确保外链可直接访问
  - 设置 CAPTURE_VIDEO_API=1 环境变量启用视频 API 请求记录功能
@DEPENDENCIES:
  - 外部: playwright, loguru
@RELATED: first_edit_controller.py, first_edit_codegen.py, batch_edit_codegen.py
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
from collections.abc import Callable, Sequence
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urljoin

from loguru import logger
from playwright.async_api import Locator, Page

# 性能追踪已移至工作流层级的 PerformanceTracker
from ..utils.page_waiter import PageWaiter
from .first_edit.retry import first_edit_step_retry
from .first_edit.sku_spec_replace import fill_first_spec_unit, replace_sku_spec_options

# 激进优化: 进一步最小化超时时间
DEFAULT_PRIMARY_TIMEOUT_MS = 200  # 激进: 300 -> 200
FALLBACK_TIMEOUT_MS = 80  # 激进: 100 -> 80
VARIANT_ROW_SCOPE_SELECTOR = (
    ".pro-virtual-scroll__row.pro-virtual-table__row, .pro-virtual-table__row"
)
DEFAULT_VIDEO_BASE_URL = os.getenv(
    "VIDEO_BASE_URL", "https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/video/"
).strip()
VIDEO_UPLOAD_TIMEOUT_MS = 200  # 激进: 300 -> 200

# API 记录功能开关 (用于调试和逆向工程)
CAPTURE_VIDEO_API = os.getenv("CAPTURE_VIDEO_API", "0").lower() in ("1", "true", "yes")
CAPTURED_API_LOG_PATH = Path("data/debug/captured_video_api.json")

FIELD_KEYWORDS: dict[str, list[str]] = {
    "price": ["建议售价", "售价", "price"],
    "supply_price": ["供货价", "供货价格", "supply price"],
    "source_price": ["货源价", "来源价格", "采购价", "source price"],
    "stock": ["库存", "数量", "stock"],
}

# 定义泛型类型
T = TypeVar("T")


def _save_captured_api(request_data: dict[str, Any]) -> None:
    """保存捕获的 API 请求数据到文件.

    Args:
        request_data: 包含 url, method, headers, post_data 的字典
    """
    CAPTURED_API_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing_data: list[dict[str, Any]] = []
    if CAPTURED_API_LOG_PATH.exists():
        try:
            with open(CAPTURED_API_LOG_PATH, encoding="utf-8") as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing_data = []

    request_data["captured_at"] = datetime.now().isoformat()
    existing_data.append(request_data)

    with open(CAPTURED_API_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    logger.info("✓ API 请求已记录到: {}", CAPTURED_API_LOG_PATH)


def _resolve_page(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Page | None:
    """尝试从参数中提取 Page."""

    for arg in args:
        if isinstance(arg, Page):
            return arg
    for value in kwargs.values():
        if isinstance(value, Page):
            return value
    return None


def smart_retry(max_attempts: int = 2, delay: float = 0.5, exceptions: tuple = (Exception,)):
    """智能重试装饰器,用于关键操作的自动重试.

    Args:
        max_attempts: 最大尝试次数(默认2次,即1次重试).
        delay: 重试间隔秒数(默认0.5秒).
        exceptions: 需要捕获并重试的异常类型元组.

    Returns:
        装饰后的函数.
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
                        page = _resolve_page(args, kwargs)
                        if page:
                            waiter = PageWaiter(page)
                            await waiter.wait_for_dom_stable(timeout_ms=int(delay * 1000))
                        else:
                            await asyncio.sleep(delay)
                    else:
                        logger.error(f"✗ {func.__name__} 执行失败(已达最大重试次数{max_attempts})")
            raise last_exception  # type: ignore

        return wrapper

    return decorator


def _fallback_video_url_from_payload(payload: dict[str, Any]) -> str | None:
    """尝试根据型号编号拼接默认视频 OSS URL."""

    if not DEFAULT_VIDEO_BASE_URL:
        return None

    model_candidates = (
        payload.get("model_number"),
        payload.get("model_spec_option"),
    )
    for candidate in model_candidates:
        if candidate:
            safe_name = _sanitize_media_identifier(str(candidate))
            if safe_name:
                return urljoin(
                    f"{DEFAULT_VIDEO_BASE_URL.rstrip('/')}/",
                    f"{safe_name}.mp4",
                )
    return None


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
            - model_spec_name: 多规格新增维度名称(默认"型号")
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
        # 优化:弹窗检测超时从 3000ms 减少到 1500ms
        await page.wait_for_selector(".jx-overlay-dialog", state="visible", timeout=1500)
        logger.success("✓ 编辑弹窗已加载")

        # 0. 填写规格名称/规格单位(如果提供了 spec_unit)
        spec_unit = (payload.get("spec_unit") or "").strip()
        if not spec_unit:
            specs_payload = payload.get("specs") or []
            if specs_payload and isinstance(specs_payload, list):
                first_spec = specs_payload[0] or {}
                spec_unit = str(first_spec.get("name") or "").strip()

        if spec_unit:
            unit_success = await fill_first_spec_unit(page, spec_unit)
            if not unit_success:
                logger.warning("⚠️ 规格单位填写失败,继续后续流程")

        # 0. 替换 SKU 规格选项(如果提供了 spec_array)
        spec_array = payload.get("spec_array") or payload.get("sku_spec_array")
        if spec_array:
            spec_success = await replace_sku_spec_options(page, spec_array)
            if not spec_success:
                logger.warning("⚠️ SKU 规格替换失败,继续后续流程")

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

        # 5. 上传尺寸图(仅支持网络图片URL)
        size_chart_image_url = (payload.get("size_chart_image_url") or "").strip()
        if size_chart_image_url:
            logger.info("开始通过网络图片上传尺寸图...")
            upload_success = await _upload_size_chart_via_url(page, size_chart_image_url)
            if upload_success:
                logger.success("✓ 尺寸图上传成功(网络图片)")
            else:
                logger.warning("⚠️ 尺寸图网络图片上传失败,继续后续流程")
        else:
            logger.info("⚠️ 未提供尺寸图URL,跳过尺寸图上传")

        # 6. 上传产品视频(仅支持网络视频URL)
        product_video_url = (payload.get("product_video_url") or "").strip()
        if not product_video_url:
            fallback_video_url = _fallback_video_url_from_payload(payload)
            if fallback_video_url:
                product_video_url = fallback_video_url
                logger.info("未提供视频URL,使用 OSS 默认视频: {}", product_video_url)
            else:
                logger.warning("⚠️ 未提供有效视频URL,跳过视频上传")

        if product_video_url:
            logger.info("开始通过网络视频上传产品视频...")
            video_result = await _upload_product_video_via_url(page, product_video_url)
            if video_result is True:
                logger.success("✓ 产品视频上传成功(网络视频)")
            elif video_result is None:
                logger.info("已存在产品视频,跳过上传步骤.")
            else:
                logger.warning("⚠️ 产品视频网络上传失败,继续后续流程")
        else:
            logger.warning("⚠️ 未提供视频URL,跳过视频上传")

        # 注意:SKU 图片同步已移至 workflow 层的 post_fill_hook 统一处理,避免重复上传

        # 7. 保存修改
        if not await _click_save(page):
            return False

        logger.success("✓ 首次编辑弹窗填写完成")
        return True

    except Exception as exc:
        logger.error(f"填写首次编辑弹窗失败: {exc}")
        return False


@first_edit_step_retry(max_attempts=3)
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

        dialog = page.locator(".collect-box-editor-dialog-V2, .jx-overlay-dialog").first
        try:
            await dialog.wait_for(state="visible", timeout=200)  # 激进: 300 -> 200
        except Exception:
            logger.debug("标题填写时未能定位到弹窗容器, 使用全局查找")

        candidate_locators = [
            dialog.locator("input.jx-input__inner[type='text']"),
            dialog.locator("input[placeholder*='标题']"),
            page.get_by_placeholder("请输入标题", exact=False),
        ]

        target_input = await _wait_first_visible(candidate_locators)
        if target_input is None:
            logger.error("✗ 未能找到标题输入框")
            return False

        await _set_input_value(target_input, title)
        logger.success("✓ 标题已填写")
        return True

    except Exception as exc:
        logger.error(f"填写标题失败: {exc}")
        return False


@first_edit_step_retry(max_attempts=3)
async def _fill_basic_specs(page: Page, payload: dict[str, Any]) -> bool:
    """填写价格,库存,重量,尺寸等基础字段."""

    try:
        logger.info("填写基础规格字段...")
        dialog = page.locator(".collect-box-editor-dialog-V2, .jx-overlay-dialog").first
        await dialog.wait_for(state="visible", timeout=200)  # 激进: 300 -> 200
    except Exception as exc:
        logger.error("未能定位首次编辑弹窗: {}", exc)
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

    field_values = {key: payload.get(key) for key in FIELD_KEYWORDS if payload.get(key) is not None}
    if not field_values:
        return

    candidates = await _collect_input_candidates(
        dialog, exclude_selector=VARIANT_ROW_SCOPE_SELECTOR
    )
    if not candidates:
        logger.debug("未获取到单规格输入候选")
        return

    await _assign_values_by_keywords(candidates, field_values)


@first_edit_step_retry(max_attempts=3)
async def _fill_variant_rows(
    dialog: Locator, payload: dict[str, Any], variants: list[dict[str, Any]], page: Page
) -> bool:
    """按行填写多规格价格与库存."""

    rows = dialog.locator(VARIANT_ROW_SCOPE_SELECTOR)
    row_count = await rows.count()
    if row_count == 0:
        await _dump_dialog_snapshot(page, "variant_rows_missing.html")
        logger.error("✗ 未找到规格行,无法填写多规格数据")
        return False

    for index, variant in enumerate(variants):
        if index >= row_count:
            logger.warning("⚠️ 规格行数量不足,忽略多余的规格数据 (row={})", index + 1)
            break

        row = rows.nth(index)
        field_values = {}
        for field in FIELD_KEYWORDS:
            value = variant.get(field, payload.get(field))
            if value is not None:
                field_values[field] = value
        if not field_values:
            continue

        candidates = await _collect_input_candidates(row)
        if not candidates:
            logger.debug("规格行{} 未找到可用输入框", index + 1)
            continue

        await _assign_values_by_keywords(candidates, field_values, log_prefix=f"规格行{index + 1}")

    return True


@first_edit_step_retry(max_attempts=2, retry_on_false=False)
async def _fill_dimension_fields(dialog: Locator, payload: dict[str, Any]) -> None:
    """批量填写重量与三维尺寸字段."""

    field_keywords: dict[str, list[str]] = {
        "weight_g": ["重量", "重", "weight"],
        "length_cm": ["长度", "长", "length"],
        "width_cm": ["宽度", "宽", "width"],
        "height_cm": ["高度", "高", "height"],
    }

    inputs = dialog.locator("input[type='number'], input[type='text']")
    input_count = await inputs.count()
    if input_count == 0:
        logger.debug("未发现尺寸输入框")
        return

    cached_inputs: list[tuple[Locator, str]] = []
    for index in range(input_count):
        candidate = inputs.nth(index)
        placeholder = (await candidate.get_attribute("placeholder") or "").lower()
        aria_label = (await candidate.get_attribute("aria-label") or "").lower()
        cached_inputs.append((candidate, f"{placeholder} {aria_label}"))

    for field, keywords in field_keywords.items():
        value = payload.get(field)
        if value is None:
            continue
        str_value = str(value)
        normalized_keywords = [keyword.lower() for keyword in keywords]

        matched_inputs = [
            candidate
            for candidate, label in cached_inputs
            if any(keyword in label for keyword in normalized_keywords)
        ]

        if not matched_inputs:
            logger.debug("字段 {} 未能写入任何输入", field)
            continue

        field_filled = False
        for index, candidate in enumerate(matched_inputs):
            timeout = DEFAULT_PRIMARY_TIMEOUT_MS if index == 0 else FALLBACK_TIMEOUT_MS
            try:
                await candidate.wait_for(state="visible", timeout=timeout)
                await _set_input_value(candidate, str_value)
                field_filled = True
            except Exception:
                continue

        if field_filled:
            logger.debug("✓ 字段 {} 已写入所有匹配输入", field)
        else:
            logger.debug("字段 {} 未能写入任何输入", field)


@first_edit_step_retry(max_attempts=3)
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
                await save_btn.wait_for(state="visible", timeout=200)  # 激进: 300 -> 200
                await _dismiss_scroll_overlay(page)
                await save_btn.scroll_into_view_if_needed()
                await save_btn.focus()
                await save_btn.click()
                logger.success("✓ 已点击保存按钮")

                await _wait_button_completion(save_btn, page)

                toast = page.locator(".jx-message--success, .el-message--success")
                try:
                    await toast.wait_for(state="visible", timeout=100)  # 极速: 300 -> 100
                    await toast.wait_for(state="hidden", timeout=200)  # 极速: 500 -> 200
                except Exception:
                    logger.debug("保存成功提示未出现或已快速消失")
                return True
            except Exception:
                continue

        await _dump_dialog_snapshot(page, "save_button_failure.html")
        logger.error("✗ 未能找到保存按钮")
        return False

    except Exception as exc:
        logger.error(f"点击保存按钮失败: {exc}")
        return False


@first_edit_step_retry(max_attempts=3)
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
        logger.error("填写供货商链接失败: {}", exc)
        return False


@smart_retry(max_attempts=2, delay=0.5)
async def _upload_size_chart_via_url(page: Page, image_url: str) -> bool:
    """通过网络图片URL上传尺寸图."""

    if not image_url:
        logger.info("未提供尺寸图URL,跳过网络图片上传")
        return False

    logger.debug("使用网络图片上传尺寸图: {}", image_url[:120])

    try:
        normalized_url = _normalize_input_url(image_url)
        if not normalized_url:
            logger.warning("提供的尺寸图URL无效,跳过上传: {}", image_url)
            return False

        # [增强] 尺寸图分组定位 - 多种备用方式
        size_group = None
        size_group_selectors = [
            page.get_by_role("group", name="尺寸图表 :", exact=True),
            page.get_by_role("group", name=re.compile("尺寸图")),
            page.locator("[class*='size-chart'], [class*='sizeChart']"),
            page.locator("text=尺寸图表").locator(".."),
        ]
        for selector in size_group_selectors:
            try:
                if await selector.count():
                    size_group = selector.first
                    logger.debug("尺寸图分组定位成功")
                    break
            except Exception:
                continue

        if size_group is None:
            logger.warning("未找到尺寸图 group")
            await _capture_html(page, "data/debug/html/size_chart_missing_group.html")
            return False

        await size_group.scroll_into_view_if_needed()

        # [核心修复] 优先点击"添加新图片"按钮，这才是正确的触发方式
        # 参考用户反馈的正确元素: .product-picture-item-add
        add_btn_clicked = False
        add_image_selectors = [
            # [最优先] 用户反馈的正确选择器
            size_group.locator(".product-picture-item-add"),
            page.locator(".product-picture-item-add").filter(
                has=page.locator("[class*='jx-icon']")
            ),
            # 带 jx-tooltip 的添加按钮
            size_group.locator(".jx-tooltip__trigger").filter(
                has=page.locator("[class*='jx-icon']")
            ),
            # 旧版选择器作为备用
            size_group.locator(".add-image-box .add-image-box-content"),
            size_group.locator(".add-image-box"),
            size_group.locator("[class*='add-image']"),
            # 尝试全局范围查找（尺寸图区域可能嵌套）
            page.locator(".scroll-menu-pane")
            .filter(has_text=re.compile("尺寸图"))
            .locator(".product-picture-item-add"),
            page.locator(".scroll-menu-pane")
            .filter(has_text=re.compile("尺寸图"))
            .locator(".add-image-box"),
            # 文本匹配备选
            size_group.locator("text=添加新图片"),
            size_group.get_by_text("添加新图片", exact=False),
            # 通用添加按钮
            size_group.locator("[class*='add'], [class*='upload']").filter(
                has_text=re.compile("添加|上传|\\+")
            ),
        ]

        for add_selector in add_image_selectors:
            try:
                if await add_selector.count():
                    await add_selector.first.click()
                    add_btn_clicked = True
                    logger.debug("已点击『添加新图片』按钮")
                    # 等待菜单出现
                    await asyncio.sleep(0.3)
                    break
            except Exception:
                continue

        # 如果添加按钮点击失败，尝试点击缩略图作为后备
        if not add_btn_clicked:
            logger.debug("添加按钮点击失败，尝试点击缩略图")
            try:
                thumbnails = size_group.get_by_role("img")
                thumb_count = await thumbnails.count()
                if thumb_count:
                    target_index = min(4, max(thumb_count - 1, 0))
                    await thumbnails.nth(target_index).click()
                    logger.debug("已点击尺寸图缩略图")
                    await asyncio.sleep(0.3)
            except Exception as exc:
                logger.debug("点击尺寸图缩略图失败: {}", exc)

        # [增强] "使用网络图片"按钮 - 多种备用定位方式
        upload_btn = None
        upload_btn_selectors = [
            page.get_by_text("使用网络图片", exact=True),
            page.get_by_text("使用网络图片", exact=False).first,
            page.locator("text=使用网络图片").first,
            page.locator("[class*='network'], [class*='url']").filter(has_text="网络"),
            page.get_by_role("button", name=re.compile("网络图片")),
            page.get_by_role("menuitem", name=re.compile("网络图片")),
            # 尝试 dropdown menu 中的选项
            page.locator(".jx-dropdown-menu").get_by_text("使用网络图片", exact=False),
            page.locator("[role='menu']").get_by_text("使用网络图片", exact=False),
        ]
        for selector in upload_btn_selectors:
            try:
                await selector.wait_for(state="visible", timeout=1500)
                upload_btn = selector
                logger.debug("使用网络图片按钮定位成功")
                break
            except Exception:
                continue

        if upload_btn is None:
            logger.warning("未找到『使用网络图片』按钮")
            await _capture_html(page, "data/debug/html/size_chart_missing_upload_btn.html")
            return False

        await upload_btn.click()

        # [增强] URL输入框 - 多种备用定位方式
        url_input = None
        url_input_selectors = [
            page.get_by_role(
                "textbox", name="请输入图片链接，若要输入多个链接，请以回车换行", exact=True
            ),
            page.get_by_role("textbox", name=re.compile("请输入图片链接")),
            page.get_by_role("textbox", name=re.compile("图片链接|图片URL|输入链接")),
            page.locator("input[placeholder*='图片链接'], textarea[placeholder*='图片链接']"),
            page.locator("input[placeholder*='URL'], textarea[placeholder*='URL']"),
            page.locator(".jx-dialog, .el-dialog, [role='dialog']")
            .locator("input[type='text'], textarea")
            .first,
        ]
        for selector in url_input_selectors:
            try:
                await selector.wait_for(state="visible", timeout=800)
                url_input = selector
                logger.debug("URL输入框定位成功")
                break
            except Exception:
                continue

        if url_input is None:
            logger.warning("未找到URL输入框")
            await _capture_html(page, "data/debug/html/size_chart_missing_input.html")
            return False

        await url_input.click()
        await url_input.press("ControlOrMeta+a")
        await url_input.fill(normalized_url)

        # 确保「同时保存图片到妙手图片空间」保持未勾选状态
        try:
            save_to_space_checkbox = page.get_by_role(
                "checkbox", name=re.compile("同时保存图片到妙手图片空间")
            )
            if not await save_to_space_checkbox.count():
                save_to_space_checkbox = page.get_by_text(
                    "同时保存图片到妙手图片空间", exact=False
                ).locator("input[type='checkbox'], [role='checkbox']")

            if await save_to_space_checkbox.count():
                checkbox = save_to_space_checkbox.first
                try:
                    is_checked = await checkbox.is_checked()
                except Exception:
                    aria_checked = (await checkbox.get_attribute("aria-checked") or "").lower()
                    is_checked = aria_checked == "true"

                if is_checked:
                    await checkbox.click()
                    logger.debug("已取消勾选『同时保存图片到妙手图片空间』")
                else:
                    logger.debug("复选框已处于未勾选状态")
        except Exception as exc:
            logger.debug("处理图片空间复选框状态失败: {}", exc)

        # [增强] 确认按钮 - 多种备用定位方式
        confirm_btn = None
        confirm_btn_selectors = [
            page.get_by_role("button", name="确定"),
            page.get_by_role("button", name=re.compile("确定|确认|OK")),
            page.locator(".jx-dialog, .el-dialog, [role='dialog']").get_by_role(
                "button", name=re.compile("确定|确认")
            ),
            page.locator("button:has-text('确定')"),
        ]
        for selector in confirm_btn_selectors:
            try:
                await selector.first.wait_for(state="visible", timeout=800)
                confirm_btn = selector.first
                logger.debug("确认按钮定位成功")
                break
            except Exception:
                continue

        if confirm_btn is None:
            logger.warning("未找到确认按钮")
            return False

        await confirm_btn.click()

        await _ensure_dialog_closed(
            page,
            name_pattern="上传图片",
            timeout_ms=VIDEO_UPLOAD_TIMEOUT_MS,
        )
        await _close_prompt_dialog(page, timeout_ms=VIDEO_UPLOAD_TIMEOUT_MS)

        # 等待尺寸图资源加载完成
        await _wait_for_size_chart_loaded(page, size_group)

        logger.success("✓ 尺寸图已上传(网络图片): {}", normalized_url[:120])
        return True

    except Exception as exc:
        logger.warning("网络图片上传尺寸图失败: {}", exc)
        await _capture_html(page, "data/debug/html/size_chart_exception.html")
        return False


@smart_retry(max_attempts=2, delay=0.5)
async def _upload_product_video_via_url(page: Page, video_url: str) -> bool | None:
    """通过网络视频URL上传产品视频.

    Returns:
        bool | None: 上传成功返回 True,出现错误返回 False,若检测到已有视频并跳过返回 None.
    """

    if not video_url:
        logger.info("未提供视频URL,跳过网络视频上传")
        return False

    normalized_url = _normalize_input_url(video_url)
    if not normalized_url:
        logger.warning("提供的视频URL无效,跳过上传: {}", video_url)
        return False

    logger.debug("使用网络视频上传产品视频: {}", normalized_url[:120])

    try:
        dialog = page.get_by_role("dialog")
        if await dialog.count():
            with contextlib.suppress(Exception):
                await dialog.first.evaluate("el => { el.scrollTop = 0; }")

        # 多候选产品视频分组定位器
        video_group_selectors = [
            page.get_by_role("group", name="产品视频 :", exact=True),
            page.get_by_role("group", name="产品视频", exact=False),
            page.get_by_role("group", name=re.compile(r"产品视频|商品视频")),
            page.locator("[class*='video-group'], [class*='videoGroup']"),
            page.locator("text=产品视频").locator(".."),
        ]

        video_group = None
        for selector in video_group_selectors:
            try:
                if await selector.count():
                    video_group = selector.first
                    break
            except Exception:
                continue

        if video_group is None:
            logger.warning("未找到产品视频分组,跳过视频上传")
            await _capture_html(page, "data/debug/html/video_missing_group.html")
            return False

        await video_group.scroll_into_view_if_needed()

        video_wrapper = video_group.locator(".video-wrap").first
        if await video_wrapper.count():
            try:
                has_existing_video = await video_wrapper.evaluate(
                    r"""
                    (node) => {
                        if (!node) return false;
                        const classList = Array.from(node.classList || []);
                        if (classList.some(cls => /has|exist|uploaded|filled|active/.test(cls))) {
                            return true;
                        }
                        const dataset = node.dataset || {};
                        if (dataset.url || dataset.src || dataset.value) {
                            return true;
                        }
                        const iframe = node.querySelector('iframe');
                        if (iframe) {
                            const attrSrc = iframe.getAttribute('src') || '';
                            const propSrc = iframe.src || '';
                            const src = attrSrc || propSrc;
                            if (src && !src.startsWith('about:blank') && !/\/\/.*\/empty/i.test(src)) {
                                return true;
                            }
                        }
                        const videoEl = node.querySelector('video');
                        if (videoEl) {
                            const src = videoEl.currentSrc || videoEl.src || videoEl.getAttribute('src') || '';
                            if (src && !/placeholder|demo|sample|^\s*$/.test(src)) {
                                return true;
                            }
                        }
                        const img = node.querySelector('img');
                        if (img) {
                            const src = (img.currentSrc || img.src || img.getAttribute('src') || '').toLowerCase();
                            if (src && !/add|placeholder|empty|default|plus/.test(src)) {
                                return true;
                            }
                        }
                        const style = window.getComputedStyle(node);
                        const bg = style.backgroundImage || '';
                        if (bg && bg !== 'none' && !/placeholder|empty|add|plus/.test(bg)) {
                            return true;
                        }
                        const text = (node.innerText || '').trim();
                        if (text && !/上传|添加|点击|暂无|空|选择|使用网络视频/.test(text)) {
                            return true;
                        }
                        return false;
                    }
                    """
                )
                if has_existing_video:
                    logger.info("检测到已有产品视频,跳过上传步骤.")
                    return None
            except Exception as exc:
                logger.debug("检测现有视频状态失败: {}", exc)

        try:
            await page.locator(".video-wrap").click()
        except Exception:
            try:
                await video_group.get_by_role("img").first.click()
            except Exception as exc:
                logger.debug("点击产品视频区域失败: {}", exc)

        # 多候选网络上传按钮定位器
        network_upload_selectors = [
            page.get_by_text("网络上传", exact=True),
            page.get_by_text("网络上传", exact=False).first,
            page.locator("text=网络上传").first,
            page.get_by_role("button", name=re.compile(r"网络上传|网络视频")),
            page.get_by_role("menuitem", name=re.compile(r"网络上传|网络视频")),
            page.locator("[class*='network'], [class*='url']").filter(has_text="网络"),
            video_group.get_by_text("网络上传", exact=False) if video_group else None,
        ]

        network_clicked = False
        for selector in network_upload_selectors:
            if selector is None:
                continue
            try:
                if await selector.count():
                    await selector.first.wait_for(state="visible", timeout=2000)
                    await selector.first.click()
                    logger.debug("已点击『网络上传』按钮")
                    network_clicked = True
                    break
            except Exception:
                continue

        if not network_clicked:
            logger.warning("未能点击『网络上传』按钮")
            await _capture_html(page, "data/debug/html/video_missing_network_btn.html")
            raise RuntimeError("未能点击『网络上传』按钮")

        video_dialog = await _wait_for_dialog(page, name_pattern="上传视频")

        video_input_candidates: list[Locator | None] = []
        name_patterns = [
            re.compile("输入视频URL地址", re.IGNORECASE),
            re.compile("视频URL", re.IGNORECASE),
            re.compile("视频链接", re.IGNORECASE),
        ]

        for pattern in name_patterns:
            video_input_candidates.append(page.get_by_role("textbox", name=pattern))
        if video_dialog is not None:
            for pattern in name_patterns:
                video_input_candidates.append(video_dialog.get_by_role("textbox", name=pattern))

        video_input_candidates.extend(
            [
                page.locator("input[placeholder*='视频']"),
                page.locator("textarea[placeholder*='视频']"),
                video_dialog.locator("input[placeholder*='视频']") if video_dialog else None,
                video_dialog.locator("textarea[placeholder*='视频']") if video_dialog else None,
            ]
        )

        target_input = await _first_visible(video_input_candidates, timeout=2500)
        if target_input is None:
            logger.warning("未找到视频URL输入框")
            await _capture_html(page, "data/debug/html/video_missing_input.html")
            return False

        await target_input.click()
        await target_input.press("ControlOrMeta+a")
        await target_input.fill(normalized_url)

        # 取消勾选"同时保存图片到妙手图片空间"(视频上传弹窗)
        try:
            scope = video_dialog if video_dialog is not None else page
            save_to_space_checkbox = scope.get_by_text("同时保存图片到妙手图片空间", exact=True)
            if await save_to_space_checkbox.count():
                await save_to_space_checkbox.click()
                logger.debug("已取消勾选『同时保存图片到妙手图片空间』")
        except Exception as exc:
            logger.debug("取消勾选保存到图片空间失败(可能已取消勾选): {}", exc)

        # 多候选确认按钮定位器
        scope = video_dialog if video_dialog is not None else page
        confirm_btn_selectors = [
            scope.get_by_role("button", name="确定"),
            scope.get_by_role("button", name=re.compile(r"确定|确认|OK|提交")),
            scope.locator("button").filter(has_text=re.compile(r"确定|确认")),
            scope.locator("[class*='confirm'], [class*='submit']").filter(
                has_text=re.compile(r"确定|确认")
            ),
            scope.locator("text=确定").first,
        ]

        confirm_btn = None
        for selector in confirm_btn_selectors:
            try:
                if await selector.count():
                    confirm_btn = selector.last
                    break
            except Exception:
                continue

        if confirm_btn is None:
            logger.warning("未找到视频上传确认按钮")
            await _capture_html(page, "data/debug/html/video_missing_confirm.html")
            return False

        # API 请求捕获逻辑 (通过 CAPTURE_VIDEO_API 环境变量启用)
        captured_requests: list[dict[str, Any]] = []

        async def _capture_request(request) -> None:
            """捕获视频相关 API 请求."""
            url = request.url
            # 筛选视频上传相关的 API 请求
            if any(
                keyword in url
                for keyword in ["video", "upload", "media", "file", "oss", "alicdn"]
            ):
                request_data = {
                    "url": url,
                    "method": request.method,
                    "headers": dict(request.headers),
                    "post_data": None,
                    "resource_type": request.resource_type,
                }
                try:
                    post_data = request.post_data
                    if post_data:
                        request_data["post_data"] = post_data
                except Exception:
                    pass
                captured_requests.append(request_data)
                logger.debug("捕获到视频相关请求: {} {}", request.method, url[:100])

        if CAPTURE_VIDEO_API:
            logger.info("🎬 API 记录模式已启用，开始捕获视频上传请求...")
            page.on("request", _capture_request)

        await confirm_btn.click()

        # 等待一小段时间让请求发出
        if CAPTURE_VIDEO_API:
            await asyncio.sleep(1.0)
            page.remove_listener("request", _capture_request)

            # 保存捕获的请求
            if captured_requests:
                for req in captured_requests:
                    req["video_url_input"] = normalized_url
                    _save_captured_api(req)
                logger.success("✓ 捕获到 {} 个视频相关 API 请求", len(captured_requests))
            else:
                logger.warning("未捕获到任何视频相关 API 请求")

        await _ensure_dialog_closed(
            page,
            name_pattern="上传视频",
            dialog=video_dialog,
            timeout_ms=VIDEO_UPLOAD_TIMEOUT_MS,
        )
        await _close_prompt_dialog(page, timeout_ms=VIDEO_UPLOAD_TIMEOUT_MS)

        # 等待视频资源加载完成
        await _wait_for_video_loaded(page, video_group)

        logger.success("✓ 产品视频已上传(网络视频): {}", normalized_url[:120])
        return True

    except Exception as exc:
        logger.warning("网络视频上传产品视频失败: {}", exc)
        await _capture_html(page, "data/debug/html/video_upload_exception.html")
        return False


async def _handle_existing_video_prompt(page: Page) -> bool:
    """处理已有产品视频时出现的删除确认提示 (已注释)."""

    dialog_locator = page.get_by_role("dialog").filter(
        has_text=re.compile("删除.*视频|确认要删除.*视频")
    )

    if not await dialog_locator.count():
        return False

    # 已注释逻辑,不再自动确认删除
    return False


async def _dismiss_scroll_overlay(page: Page) -> None:
    """尝试关闭可能遮挡输入框的浮层."""

    overlay = page.locator(".scroll-menu-pane__content")
    if not await overlay.count():
        return

    try:
        await page.keyboard.press("Escape")
        await overlay.first.wait_for(state="hidden", timeout=1500)
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
        logger.debug("已写入调试快照: {}", target)
    except Exception as exc:
        logger.warning("写入调试快照失败: {}", exc)


async def _wait_first_visible(
    candidates: list[Locator | None],
    *,
    primary_timeout: int = DEFAULT_PRIMARY_TIMEOUT_MS,
    fallback_timeout: int = FALLBACK_TIMEOUT_MS,
) -> Locator | None:
    """返回第一个可见元素,首个候选使用较长超时,后续快速失败."""

    for index, candidate in enumerate(candidates):
        if candidate is None:
            continue
        try:
            if not await candidate.count():
                continue
            target = candidate.first
            timeout = primary_timeout if index == 0 else fallback_timeout
            await target.wait_for(state="visible", timeout=timeout)
            return target
        except Exception:
            continue
    return None


async def _wait_for_visibility(locator: Locator, timeout: int) -> Locator | None:
    """等待单个定位器可见,失败时返回 None."""

    try:
        await locator.wait_for(state="visible", timeout=timeout)
        return locator
    except Exception:
        return None


async def _wait_button_completion(
    button: Locator, page: Page | None = None, timeout_ms: int = 1_000
) -> None:
    """等待按钮被禁用或从页面移除,用于确认操作完成."""

    waiter = PageWaiter(page) if page else None

    try:
        await button.wait_for(state="hidden", timeout=timeout_ms)
        return
    except Exception:
        pass

    try:
        await button.wait_for(state="detached", timeout=timeout_ms)
        return
    except Exception:
        pass

    end_time = asyncio.get_running_loop().time() + timeout_ms / 1_000
    while asyncio.get_running_loop().time() < end_time:
        try:
            if not await button.count():
                return
            if await button.is_disabled():
                return
        except Exception:
            return
        if waiter:
            await waiter.wait_for_dom_stable(timeout_ms=120)
        else:
            await asyncio.sleep(0.1)


async def _collect_input_candidates(
    scope: Locator, *, exclude_selector: str | None = None
) -> list[dict[str, Any]]:
    """收集范围内的输入框候选,提取标识文本用于关键字匹配."""

    inputs = scope.locator("input[type='number'], input[type='text']")
    count = await inputs.count()
    candidates: list[dict[str, Any]] = []

    for index in range(count):
        locator = inputs.nth(index)
        try:
            if exclude_selector:
                inside_excluded = await locator.evaluate(
                    "(el, sel) => !!el.closest(sel)", exclude_selector
                )
                if inside_excluded:
                    continue

            placeholder = (await locator.get_attribute("placeholder") or "").lower()
            aria_label = (await locator.get_attribute("aria-label") or "").lower()
            name_attr = (await locator.get_attribute("name") or "").lower()
            data_label = (await locator.get_attribute("data-label") or "").lower()
            context_text = await locator.evaluate(
                "(el) => (el.closest('.pro-form-item')?.textContent || "
                "el.parentElement?.textContent || '')"
            )
            combined = " ".join(
                filter(
                    None,
                    [
                        placeholder,
                        aria_label,
                        name_attr,
                        data_label,
                        (context_text or "").lower(),
                    ],
                )
            )
            candidates.append({"locator": locator, "label": combined, "used": False})
        except Exception:
            continue

    return candidates


async def _assign_values_by_keywords(
    candidates: list[dict[str, Any]],
    field_values: dict[str, Any],
    log_prefix: str = "",
) -> None:
    """根据关键字匹配输入框并填充值."""

    prefix = f"{log_prefix} " if log_prefix else ""
    for field, raw_value in field_values.items():
        keywords = [keyword.lower() for keyword in FIELD_KEYWORDS.get(field, [])]
        if not keywords:
            continue
        locator = _match_candidate(candidates, keywords)
        str_value = str(raw_value)
        if locator is None:
            logger.debug("{}字段 {} 未找到匹配输入框", prefix, field)
            continue
        try:
            await locator.wait_for(state="visible", timeout=DEFAULT_PRIMARY_TIMEOUT_MS)
            await _set_input_value(locator, str_value)
            logger.debug("✓ {}字段 {} 已写入 {}", prefix, field, str_value)
        except Exception as exc:
            logger.debug("{}字段 {} 写入失败: {}", prefix, field, exc)


def _match_candidate(candidates: list[dict[str, Any]], keywords: list[str]) -> Locator | None:
    """在候选列表中按关键字查找未使用的输入框."""

    for candidate in candidates:
        if candidate.get("used"):
            continue
        label: str = candidate.get("label", "")
        if any(keyword in label for keyword in keywords):
            candidate["used"] = True
            return candidate["locator"]
    return None


async def _first_visible(candidates: list[Locator | None], timeout: int = 1_000) -> Locator | None:
    """返回第一个可见的候选定位器."""

    valid_candidates: list[tuple[Locator, int]] = []
    fallback_timeout = max(timeout // 4, 200)

    for candidate in candidates:
        if candidate is None:
            continue
        try:
            if not await candidate.count():
                continue
        except Exception:
            continue
        locator = candidate.first
        wait_timeout = timeout if not valid_candidates else fallback_timeout
        valid_candidates.append((locator, wait_timeout))

    if not valid_candidates:
        return None

    tasks = [
        asyncio.create_task(_wait_for_visibility(locator, wait_timeout))
        for locator, wait_timeout in valid_candidates
    ]

    try:
        for task in asyncio.as_completed(tasks):
            result = await task
            if result is not None:
                for pending in tasks:
                    if not pending.done():
                        pending.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                return result
        await asyncio.gather(*tasks, return_exceptions=True)
        return None
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()


def _normalize_input_url(raw_text: str) -> str:
    """清理输入文本并确保返回可用 URL(必要时对路径做编码)."""
    from urllib.parse import quote, urlparse, urlunparse

    if not raw_text:
        return ""

    parts = [line.strip() for line in raw_text.splitlines() if line.strip()]
    cleaned = ""
    for part in parts:
        if part.lower().startswith("url"):
            continue
        cleaned = part
        break
    cleaned = cleaned or raw_text.strip()

    try:
        parsed = urlparse(cleaned)
        path = parsed.path

        if path.isascii():
            logger.debug("URL 路径已符合 ASCII: {}", cleaned)
            return cleaned

        encoded_path = quote(path, safe="/:@!$&'()*+,;=")
        encoded_url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                encoded_path,
                parsed.params,
                parsed.query,
                parsed.fragment,
            )
        )
        logger.debug("URL 路径已编码: {} -> {}", cleaned, encoded_url)
        return encoded_url
    except Exception as exc:
        logger.warning("URL 清洗失败, 使用原始值: {}", exc)
        return cleaned


def _sanitize_media_identifier(raw: str) -> str:
    """将型号标识转为可用于媒体文件名的安全字符串."""

    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw.strip())
    return safe.strip("_")


# 资源加载等待超时配置
RESOURCE_LOAD_TIMEOUT_MS = 5000  # 资源加载最长等待 5 秒
RESOURCE_LOAD_CHECK_INTERVAL_MS = 200  # 检测间隔 200ms


async def _wait_for_size_chart_loaded(
    page: Page,
    size_group: Locator,
    timeout_ms: int = RESOURCE_LOAD_TIMEOUT_MS,
) -> bool:
    """等待尺寸图资源加载完成.

    通过检测尺寸图区域内的图片元素是否完成加载来判断。

    Args:
        page: Playwright 页面对象
        size_group: 尺寸图分组定位器
        timeout_ms: 超时时间(毫秒)

    Returns:
        bool: True 表示加载完成,False 表示超时
    """
    logger.debug("等待尺寸图资源加载...")
    waiter = PageWaiter(page)

    try:
        # 首先等待 DOM 稳定
        await waiter.wait_for_dom_stable(timeout_ms=min(1000, timeout_ms // 3))

        # 检测尺寸图区域内的图片是否加载完成
        images = size_group.locator("img")
        img_count = await images.count()

        if img_count == 0:
            logger.debug("尺寸图区域未发现图片元素,跳过等待")
            return True

        # 等待图片加载完成
        deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
        while asyncio.get_running_loop().time() < deadline:
            all_loaded = True
            for i in range(img_count):
                img = images.nth(i)
                try:
                    # 检查图片是否已加载完成
                    is_loaded = await img.evaluate(
                        """
                        (img) => {
                            // 检查 naturalWidth/naturalHeight 判断是否已加载
                            if (img.complete && img.naturalWidth > 0) {
                                return true;
                            }
                            // 检查 src 是否为有效 URL
                            const src = img.src || img.getAttribute('src') || '';
                            if (!src || src.startsWith('data:') || src.includes('placeholder')) {
                                return true;  // 占位图视为已加载
                            }
                            return false;
                        }
                        """
                    )
                    if not is_loaded:
                        all_loaded = False
                        break
                except Exception:
                    continue

            if all_loaded:
                logger.debug("✓ 尺寸图资源加载完成")
                return True

            await asyncio.sleep(RESOURCE_LOAD_CHECK_INTERVAL_MS / 1000)

        logger.debug("尺寸图资源加载超时,继续后续流程")
        return False

    except Exception as exc:
        logger.debug("等待尺寸图加载异常: {}", exc)
        return False


async def _wait_for_video_loaded(
    page: Page,
    video_group: Locator,
    timeout_ms: int = RESOURCE_LOAD_TIMEOUT_MS,
) -> bool:
    """等待视频资源加载完成.

    通过检测视频区域内的缩略图或视频元素是否加载来判断。

    Args:
        page: Playwright 页面对象
        video_group: 视频分组定位器
        timeout_ms: 超时时间(毫秒)

    Returns:
        bool: True 表示加载完成,False 表示超时
    """
    logger.debug("等待视频资源加载...")
    waiter = PageWaiter(page)

    try:
        # 首先等待 DOM 稳定
        await waiter.wait_for_dom_stable(timeout_ms=min(1000, timeout_ms // 3))

        deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
        while asyncio.get_running_loop().time() < deadline:
            # 检测视频区域是否有有效内容
            has_content = await video_group.evaluate(
                """
                (node) => {
                    if (!node) return false;

                    // 检查 iframe 是否有有效 src
                    const iframe = node.querySelector('iframe');
                    if (iframe) {
                        const src = iframe.src || iframe.getAttribute('src') || '';
                        if (src && !src.startsWith('about:blank') && !/\\/.*\\/empty/i.test(src)) {
                            return true;
                        }
                    }

                    // 检查 video 元素
                    const video = node.querySelector('video');
                    if (video) {
                        const src = video.currentSrc || video.src || video.getAttribute('src') || '';
                        if (src && video.readyState >= 1) {
                            return true;  // HAVE_METADATA 或更高状态
                        }
                    }

                    // 检查缩略图是否加载
                    const imgs = node.querySelectorAll('img');
                    for (const img of imgs) {
                        const src = img.src || img.getAttribute('src') || '';
                        if (src && !src.includes('placeholder') && !src.includes('add') &&
                            !src.includes('plus') && !src.includes('empty')) {
                            if (img.complete && img.naturalWidth > 0) {
                                return true;
                            }
                        }
                    }

                    // 检查是否有 video-wrap 的特殊状态类
                    const wrap = node.querySelector('.video-wrap');
                    if (wrap) {
                        const classList = Array.from(wrap.classList || []);
                        if (classList.some(cls => /has|exist|uploaded|filled|active/.test(cls))) {
                            return true;
                        }
                    }

                    return false;
                }
                """
            )

            if has_content:
                logger.debug("✓ 视频资源加载完成")
                return True

            await asyncio.sleep(RESOURCE_LOAD_CHECK_INTERVAL_MS / 1000)

        logger.debug("视频资源加载超时,继续后续流程")
        return False

    except Exception as exc:
        logger.debug("等待视频加载异常: {}", exc)
        return False


async def _close_prompt_dialog(page: Page, *, timeout_ms: int | None = None) -> None:
    """如果存在提示弹窗则关闭,以防阻塞后续步骤."""

    prompt = page.get_by_role("dialog", name=re.compile("提示"))
    try:
        if await prompt.count():
            close_btn = prompt.get_by_label("关闭此对话框")
            if await close_btn.count():
                await close_btn.first.click()
                with contextlib.suppress(Exception):
                    await prompt.wait_for(
                        state="hidden",
                        timeout=timeout_ms or DEFAULT_PRIMARY_TIMEOUT_MS,
                    )
    except Exception:
        pass


async def _acknowledge_prompt(
    page: Page,
    *,
    name_pattern: str = "提示",
    button_names: Sequence[str] = ("确定", "确认"),
    timeout_ms: int = VIDEO_UPLOAD_TIMEOUT_MS,
) -> None:
    """点击提示弹窗中的确认按钮."""

    # 已注释,不再主动确认提示弹窗
    return


async def _click_dialog_close_icon(page: Page, dialog: Locator) -> bool:
    """尝试点击弹窗右上角的关闭按钮."""

    close_candidates = [
        dialog.get_by_label("关闭此对话框"),
        dialog.locator("[aria-label='关闭']"),
        dialog.locator("[aria-label='Close']"),
        dialog.locator(".el-dialog__headerbtn"),
        dialog.locator(".jx-dialog__headerbtn"),
        dialog.locator("button:has-text('x')"),
        dialog.locator("button:has-text('关闭')"),
    ]

    for candidate in close_candidates:
        try:
            if await candidate.count():
                await candidate.first.click()
                return True
        except Exception as exc:
            logger.debug("关闭弹窗按钮点击失败: {}", exc)

    try:
        await page.keyboard.press("Escape")
        return True
    except Exception as exc:
        logger.debug("发送 Escape 关闭弹窗失败: {}", exc)
        return False


async def _ensure_dialog_closed(
    page: Page,
    *,
    name_pattern: str,
    dialog: Locator | None = None,
    timeout_ms: int = VIDEO_UPLOAD_TIMEOUT_MS,
) -> None:
    """确保指定名称的对话框关闭."""

    target_dialog = dialog or page.get_by_role("dialog", name=re.compile(name_pattern))
    if not await target_dialog.count():
        return

    try:
        await target_dialog.wait_for(state="hidden", timeout=timeout_ms)
        return
    except Exception:
        logger.debug("弹窗在 {}ms 内未关闭,尝试点击叉叉", timeout_ms)

    await _click_dialog_close_icon(page, target_dialog)

    try:
        await target_dialog.wait_for(state="hidden", timeout=timeout_ms)
    except Exception:
        await _capture_html(page, "data/debug/html/dialog_not_closed.html")


async def _capture_html(page: Page, path: str) -> None:
    """写出当前页面 HTML,便于调试."""

    try:
        html = await page.content()
        target = Path(__file__).resolve().parents[2] / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        logger.debug("已写出调试 HTML: {}", target)
    except Exception as exc:
        logger.warning("写出调试 HTML 失败: {}", exc)


async def upload_size_chart_via_url(page: Page, image_url: str) -> bool:
    """公开的尺寸图上传入口,供其他模块复用."""

    return await _upload_size_chart_via_url(page, image_url)


async def upload_product_video_via_url(page: Page, video_url: str) -> bool | None:
    """公开的产品视频上传入口,供其他模块复用."""

    return await _upload_product_video_via_url(page, video_url)


async def _wait_for_dialog(
    page: Page, *, name_pattern: str, timeout_ms: int = VIDEO_UPLOAD_TIMEOUT_MS
) -> Locator | None:
    """等待并返回匹配名称的 dialog."""

    dialog = page.get_by_role("dialog", name=re.compile(name_pattern))
    try:
        await dialog.wait_for(state="visible", timeout=timeout_ms)
        return dialog
    except Exception:
        await _capture_html(page, f"data/debug/html/dialog_missing_{name_pattern}.html")
        return None
