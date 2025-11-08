"""
@PURPOSE: 使用 Codegen 录制逻辑填写首次编辑弹窗中的基础规格字段
@OUTLINE:
  - def smart_retry(): 智能重试装饰器,用于关键操作的自动重试
  - async def fill_first_edit_dialog_codegen(): 主函数,填写弹窗内所有字段
  - async def _fill_title(): 填写产品标题
  - async def _fill_basic_specs(): 填写价格/库存/重量/尺寸等基础字段
  - async def _upload_size_chart_via_url(): 使用网络图片URL上传尺寸图
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
import re
from functools import wraps
from pathlib import Path
from typing import Any, Callable, TypeVar

from loguru import logger
from playwright.async_api import Locator, Page

DEFAULT_PRIMARY_TIMEOUT_MS = 2_000
FALLBACK_TIMEOUT_MS = 500
VARIANT_ROW_SCOPE_SELECTOR = (
    ".pro-virtual-scroll__row.pro-virtual-table__row, .pro-virtual-table__row"
)

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
            logger.warning("⚠️ 规格行数量不足，忽略多余的规格数据 (row=%s)", index + 1)
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
            logger.debug("规格行%s 未找到可用输入框", index + 1)
            continue

        await _assign_values_by_keywords(candidates, field_values, log_prefix=f"规格行{index + 1}")

    return True


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
            logger.debug("字段 %s 未能写入任何输入", field)
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
            logger.debug("✓ 字段 %s 已写入所有匹配输入", field)
        else:
            logger.debug("字段 %s 未能写入任何输入", field)


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

                await _wait_button_completion(save_btn)

                toast = page.locator(".jx-message--success, .el-message--success")
                try:
                    await toast.wait_for(state="visible", timeout=500)
                    await toast.wait_for(state="hidden", timeout=1_000)
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
async def _upload_size_chart_via_url(page: Page, image_url: str) -> bool:
    """通过网络图片URL上传尺寸图."""

    if not image_url:
        logger.info("未提供尺寸图URL，跳过网络图片上传")
        return False

    logger.debug("使用网络图片上传尺寸图: %s", image_url[:120])

    try:
        normalized_url = _normalize_size_chart_url(image_url)
        if not normalized_url:
            logger.warning("提供的尺寸图URL无效，跳过上传: %s", image_url)
            return False

        dialog = page.get_by_role("dialog")
        if await dialog.count() > 0:
            try:
                await dialog.first.evaluate("el => { el.scrollTop = el.scrollHeight; }")
            except Exception:
                pass

        size_chart_group = page.get_by_role("group", name=re.compile("尺寸图表")).first
        if await size_chart_group.count():
            await size_chart_group.scroll_into_view_if_needed()
            try:
                await size_chart_group.wait_for(state="visible", timeout=DEFAULT_PRIMARY_TIMEOUT_MS)
            except Exception:
                pass
            try:
                img_items = size_chart_group.get_by_role("img")
                img_count = await img_items.count()
                if img_count > 0:
                    await img_items.nth(min(4, img_count - 1)).click()
            except Exception as exc:
                logger.debug("尝试点击尺寸图缩略图失败: %s", exc)

        upload_btn = await _first_visible(
            [
                size_chart_group.get_by_text("使用网络图片", exact=False)
                if await size_chart_group.count()
                else None,
                page.get_by_text("使用网络图片", exact=False),
                page.get_by_role("button", name=re.compile("使用网络图片|网络图片")),
            ]
        )
        if upload_btn is None:
            logger.warning("未找到「使用网络图片」按钮")
            return False
        await upload_btn.click()

        url_input = await _first_visible(
            [
                page.get_by_role("textbox", name=re.compile("请输入图片链接")),
                page.locator("textarea[placeholder*='图片链接']"),
                page.locator("input[placeholder*='图片链接']"),
            ]
        )
        if url_input is None:
            logger.warning("未找到尺寸图URL输入框")
            return False

        await url_input.click()
        await url_input.press("ControlOrMeta+a")
        await url_input.fill(normalized_url)

        confirm_btn = await _first_visible(
            [
                page.get_by_role("button", name=re.compile("确定")),
                page.get_by_role("button", name=re.compile("确认")),
                page.locator(".jx-button--primary:has-text('确定')"),
            ]
        )
        if confirm_btn is None:
            logger.warning("未找到网络图片上传确认按钮")
            return False

        await confirm_btn.click()
        await page.wait_for_timeout(400)

        await _close_prompt_dialog(page)
        logger.success("✓ 尺寸图已上传（网络图片）: %s", normalized_url[:120])
        return True

    except Exception as exc:
        logger.warning("网络图片上传尺寸图失败: %s", exc)
        return False


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
            logger.debug("%s字段 %s 未找到匹配输入框", prefix, field)
            continue
        try:
            await locator.wait_for(state="visible", timeout=DEFAULT_PRIMARY_TIMEOUT_MS)
            await _set_input_value(locator, str_value)
            logger.debug("✓ %s字段 %s 已写入 %s", prefix, field, str_value)
        except Exception as exc:
            logger.debug("%s字段 %s 写入失败: %s", prefix, field, exc)


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


def _normalize_size_chart_url(image_url: str) -> str:
    """去除多余的标签和空行，确保为单个有效 URL."""

    if not image_url:
        return ""
    parts = [line.strip() for line in image_url.splitlines() if line.strip()]
    cleaned = ""
    for part in parts:
        if part.lower().startswith("url"):
            continue
        cleaned = part
        break
    cleaned = cleaned or image_url.strip()
    return cleaned


async def _close_prompt_dialog(page: Page) -> None:
    """如果存在提示弹窗则关闭，以防阻塞后续步骤."""

    prompt = page.get_by_role("dialog", name=re.compile("提示"))
    try:
        if await prompt.count():
            close_btn = prompt.get_by_label("关闭此对话框")
            if await close_btn.count():
                await close_btn.first.click()
                try:
                    await prompt.wait_for(state="hidden", timeout=DEFAULT_PRIMARY_TIMEOUT_MS)
                except Exception:
                    pass
    except Exception:
        pass
