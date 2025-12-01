"""
@PURPOSE: 使用 Codegen 录制逻辑填写首次编辑弹窗中的基础规格字段
@OUTLINE:
  - def smart_retry(): 智能重试装饰器,用于关键操作的自动重试
  - async def fill_first_edit_dialog_codegen(): 主函数,填写弹窗内所有字段
  - (步骤0) 规格名称填写 + SKU规格替换: 通过 payload.spec_unit 与 payload.spec_array 传入
  - async def _fill_title(): 填写产品标题
  - async def _fill_basic_specs(): 填写价格/库存/重量/尺寸等基础字段
  - async def _upload_size_chart_via_url(): 使用网络图片URL上传尺寸图
  - async def _upload_product_video_via_url(): 使用网络视频URL上传产品视频
  - async def _handle_existing_video_prompt(): 处理已有视频的删除确认提示
  - async def _click_save(): 点击保存修改按钮
@GOTCHAS:
  - 避免使用动态 ID 选择器(如 #jx-id-6368-578)
  - 优先使用 get_by_label、get_by_role、get_by_placeholder 等稳定定位器
  - 跳过图片/视频上传部分,由 FirstEditController 的 upload_* 方法处理
  - 尺寸图上传仅支持网络图片URL,需确保外链可直接访问
@DEPENDENCIES:
  - 外部: playwright, loguru
@RELATED: first_edit_controller.py, first_edit_codegen.py, batch_edit_codegen.py
"""

from __future__ import annotations

import asyncio
import os
import re
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional, Sequence, TypeVar
from urllib.parse import urljoin

from loguru import logger
from playwright.async_api import Locator, Page

from ..core.performance import profile
from .first_edit.sku_spec_replace import fill_first_spec_unit, replace_sku_spec_options
from .first_edit.retry import first_edit_step_retry

# 激进优化: 进一步最小化超时时间
DEFAULT_PRIMARY_TIMEOUT_MS = 200     # 激进: 300 -> 200
FALLBACK_TIMEOUT_MS = 80             # 激进: 100 -> 80
VARIANT_ROW_SCOPE_SELECTOR = (
    ".pro-virtual-scroll__row.pro-virtual-table__row, .pro-virtual-table__row"
)
DEFAULT_VIDEO_BASE_URL = os.getenv(
    "VIDEO_BASE_URL", "https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/video/"
).strip()
VIDEO_UPLOAD_TIMEOUT_MS = 200        # 激进: 300 -> 200

FIELD_KEYWORDS: dict[str, list[str]] = {
    "price": ["建议售价", "售价", "price"],
    "supply_price": ["供货价", "供货价格", "supply price"],
    "source_price": ["货源价", "来源价格", "采购价", "source price"],
    "stock": ["库存", "数量", "stock"],
}

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


@profile()
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
        # 弹窗加载需要足够时间，不能过于激进
        await page.wait_for_selector(".jx-overlay-dialog", state="visible", timeout=3000)
        logger.success("✓ 编辑弹窗已加载")

        # 0. 填写规格名称/规格单位（如果提供了 spec_unit）
        spec_unit = (payload.get("spec_unit") or "").strip()
        if not spec_unit:
            specs_payload = payload.get("specs") or []
            if specs_payload and isinstance(specs_payload, list):
                first_spec = specs_payload[0] or {}
                spec_unit = str(first_spec.get("name") or "").strip()

        if spec_unit:
            unit_success = await fill_first_spec_unit(page, spec_unit)
            if not unit_success:
                logger.warning("⚠️ 规格单位填写失败，继续后续流程")

        # 0. 替换 SKU 规格选项（如果提供了 spec_array）
        spec_array = payload.get("spec_array") or payload.get("sku_spec_array")
        if spec_array:
            spec_success = await replace_sku_spec_options(page, spec_array)
            if not spec_success:
                logger.warning("⚠️ SKU 规格替换失败，继续后续流程")

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

        # 5. 上传尺寸图（仅支持网络图片URL）
        size_chart_image_url = (payload.get("size_chart_image_url") or "").strip()
        if size_chart_image_url:
            logger.info("开始通过网络图片上传尺寸图...")
            upload_success = await _upload_size_chart_via_url(page, size_chart_image_url)
            if upload_success:
                logger.success("✓ 尺寸图上传成功（网络图片）")
            else:
                logger.warning("⚠️ 尺寸图网络图片上传失败，继续后续流程")
        else:
            logger.warning("⚠️ 未提供尺寸图URL，跳过尺寸图上传")

        # 6. 上传产品视频（仅支持网络视频URL）
        product_video_url = (payload.get("product_video_url") or "").strip()
        if not product_video_url:
            fallback_video_url = _fallback_video_url_from_payload(payload)
            if fallback_video_url:
                product_video_url = fallback_video_url
                logger.info("未提供视频URL，使用 OSS 默认视频: {}", product_video_url)
            else:
                logger.warning("⚠️ 未提供有效视频URL，跳过视频上传")

        if product_video_url:
            logger.info("开始通过网络视频上传产品视频...")
            video_result = await _upload_product_video_via_url(page, product_video_url)
            if video_result is True:
                logger.success("✓ 产品视频上传成功（网络视频）")
            elif video_result is None:
                logger.info("已存在产品视频，跳过上传步骤。")
            else:
                logger.warning("⚠️ 产品视频网络上传失败，继续后续流程")
        else:
            logger.warning("⚠️ 未提供视频URL，跳过视频上传")

        # 注意：SKU 图片同步已移至 workflow 层的 post_fill_hook 统一处理，避免重复上传

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
    """填写价格、库存、重量、尺寸等基础字段."""

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
        logger.error("✗ 未找到规格行，无法填写多规格数据")
        return False

    for index, variant in enumerate(variants):
        if index >= row_count:
            logger.warning("⚠️ 规格行数量不足，忽略多余的规格数据 (row={})", index + 1)
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

                await _wait_button_completion(save_btn)

                toast = page.locator(".jx-message--success, .el-message--success")
                try:
                    await toast.wait_for(state="visible", timeout=100)   # 极速: 300 -> 100
                    await toast.wait_for(state="hidden", timeout=200)    # 极速: 500 -> 200
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
        logger.info("未提供尺寸图URL，跳过网络图片上传")
        return False

    logger.debug("使用网络图片上传尺寸图: {}", image_url[:120])

    try:
        normalized_url = _normalize_input_url(image_url)
        if not normalized_url:
            logger.warning("提供的尺寸图URL无效，跳过上传: {}", image_url)
            return False

        size_group = page.get_by_role("group", name="尺寸图表 :", exact=True)
        if not await size_group.count():
            logger.warning("未找到尺寸图 group")
            await _capture_html(page, "data/debug/html/size_chart_missing_group.html")
            return False

        await size_group.scroll_into_view_if_needed()

        try:
            thumbnails = size_group.get_by_role("img")
            thumb_count = await thumbnails.count()
            if thumb_count:
                target_index = min(4, max(thumb_count - 1, 0))
                await thumbnails.nth(target_index).click()
        except Exception as exc:
            logger.debug("点击尺寸图缩略图失败: {}", exc)

        upload_btn = page.get_by_text("使用网络图片", exact=True)
        await upload_btn.wait_for(state="visible", timeout=1500)
        await upload_btn.click()

        url_input = page.get_by_role(
            "textbox", name="请输入图片链接，若要输入多个链接，请以回车换行", exact=True
        )
        await url_input.wait_for(state="visible", timeout=1500) 
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

        confirm_btn = page.get_by_role("button", name="确定")
        await confirm_btn.wait_for(state="visible", timeout=1500) 
        await confirm_btn.click()

        await _ensure_dialog_closed(
            page,
            name_pattern="上传图片",
            timeout_ms=VIDEO_UPLOAD_TIMEOUT_MS,
        )
        await _close_prompt_dialog(page, timeout_ms=VIDEO_UPLOAD_TIMEOUT_MS)
        logger.success("✓ 尺寸图已上传（网络图片）: {}", normalized_url[:120])
        return True

    except Exception as exc:
        logger.warning("网络图片上传尺寸图失败: {}", exc)
        await _capture_html(page, "data/debug/html/size_chart_exception.html")
        return False


@smart_retry(max_attempts=2, delay=0.5)
async def _upload_product_video_via_url(page: Page, video_url: str) -> bool | None:
    """通过网络视频URL上传产品视频.

    Returns:
        bool | None: 上传成功返回 True，出现错误返回 False，若检测到已有视频并跳过返回 None。
    """

    if not video_url:
        logger.info("未提供视频URL，跳过网络视频上传")
        return False

    normalized_url = _normalize_input_url(video_url)
    if not normalized_url:
        logger.warning("提供的视频URL无效，跳过上传: {}", video_url)
        return False

    logger.debug("使用网络视频上传产品视频: {}", normalized_url[:120])

    try:
        dialog = page.get_by_role("dialog")
        if await dialog.count():
            try:
                await dialog.first.evaluate("el => { el.scrollTop = 0; }")
            except Exception:
                pass

        video_group = page.get_by_role("group", name="产品视频 :", exact=True)
        if not await video_group.count():
            logger.warning("未找到产品视频分组，跳过视频上传")
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
                    logger.info("检测到已有产品视频，跳过上传步骤。")
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

        explicit_network_option = page.get_by_text("网络上传", exact=True)
        try:
            await explicit_network_option.wait_for(state="visible", timeout=2000) 
            await explicit_network_option.click()
            logger.debug("已通过显式文本点击『网络上传』")
        except Exception:
            raise

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

        # 取消勾选"同时保存图片到妙手图片空间"（视频上传弹窗）
        try:
            scope = video_dialog if video_dialog is not None else page
            save_to_space_checkbox = scope.get_by_text("同时保存图片到妙手图片空间", exact=True)
            if await save_to_space_checkbox.count():
                await save_to_space_checkbox.click()
                logger.debug("已取消勾选『同时保存图片到妙手图片空间』")
        except Exception as exc:
            logger.debug("取消勾选保存到图片空间失败（可能已取消勾选）: {}", exc)

        confirm_btn = (
            video_dialog.get_by_role("button", name="确定")
            if video_dialog is not None
            else page.get_by_role("button", name="确定")
        )

        if not await confirm_btn.count():
            logger.warning("未找到视频上传确认按钮")
            await _capture_html(page, "data/debug/html/video_missing_confirm.html")
            return False

        await confirm_btn.last.click()

        await _ensure_dialog_closed(
            page,
            name_pattern="上传视频",
            dialog=video_dialog,
            timeout_ms=VIDEO_UPLOAD_TIMEOUT_MS,
        )
        await _close_prompt_dialog(page, timeout_ms=VIDEO_UPLOAD_TIMEOUT_MS)
        logger.success("✓ 产品视频已上传（网络视频）: {}", normalized_url[:120])
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

    # 已注释逻辑，不再自动确认删除
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
    """返回第一个可见元素，首个候选使用较长超时，后续快速失败."""

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
    """等待单个定位器可见，失败时返回 None."""

    try:
        await locator.wait_for(state="visible", timeout=timeout)
        return locator
    except Exception:
        return None


async def _wait_button_completion(button: Locator, timeout_ms: int = 1_000) -> None:
    """等待按钮被禁用或从页面移除，用于确认操作完成."""

    end_time = asyncio.get_running_loop().time() + timeout_ms / 1_000
    poll_interval = 0.1

    while asyncio.get_running_loop().time() < end_time:
        try:
            if not await button.count():
                return
            if await button.is_disabled():
                return
        except Exception:
            return
        await asyncio.sleep(poll_interval)


async def _collect_input_candidates(
    scope: Locator, *, exclude_selector: str | None = None
) -> list[dict[str, Any]]:
    """收集范围内的输入框候选，提取标识文本用于关键字匹配."""

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
    """清理输入文本并确保返回可用 URL（必要时对路径做编码）。"""
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
    """将型号标识转为可用于媒体文件名的安全字符串。"""

    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", raw.strip())
    return safe.strip("_")


async def _close_prompt_dialog(page: Page, *, timeout_ms: Optional[int] = None) -> None:
    """如果存在提示弹窗则关闭，以防阻塞后续步骤."""

    prompt = page.get_by_role("dialog", name=re.compile("提示"))
    try:
        if await prompt.count():
            close_btn = prompt.get_by_label("关闭此对话框")
            if await close_btn.count():
                await close_btn.first.click()
                try:
                    await prompt.wait_for(
                        state="hidden",
                        timeout=timeout_ms or DEFAULT_PRIMARY_TIMEOUT_MS,
                    )
                except Exception:
                    pass
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

    # 已注释，不再主动确认提示弹窗
    return


async def _click_dialog_close_icon(page: Page, dialog: Locator) -> bool:
    """尝试点击弹窗右上角的关闭按钮."""

    close_candidates = [
        dialog.get_by_label("关闭此对话框"),
        dialog.locator("[aria-label='关闭']"),
        dialog.locator("[aria-label='Close']"),
        dialog.locator(".el-dialog__headerbtn"),
        dialog.locator(".jx-dialog__headerbtn"),
        dialog.locator("button:has-text('×')"),
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
    dialog: Optional[Locator] = None,
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
    """写出当前页面 HTML，便于调试。"""

    try:
        html = await page.content()
        target = Path(__file__).resolve().parents[2] / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8")
        logger.debug("已写出调试 HTML: {}", target)
    except Exception as exc:
        logger.warning("写出调试 HTML 失败: {}", exc)


async def upload_size_chart_via_url(page: Page, image_url: str) -> bool:
    """公开的尺寸图上传入口，供其他模块复用。"""

    return await _upload_size_chart_via_url(page, image_url)


async def upload_product_video_via_url(page: Page, video_url: str) -> bool | None:
    """公开的产品视频上传入口，供其他模块复用。"""

    return await _upload_product_video_via_url(page, video_url)


async def _wait_for_dialog(
    page: Page, *, name_pattern: str, timeout_ms: int = VIDEO_UPLOAD_TIMEOUT_MS
) -> Optional[Locator]:
    """等待并返回匹配名称的 dialog."""

    dialog = page.get_by_role("dialog", name=re.compile(name_pattern))
    try:
        await dialog.wait_for(state="visible", timeout=timeout_ms)
        return dialog
    except Exception:
        await _capture_html(page, f"data/debug/html/dialog_missing_{name_pattern}.html")
        return None
