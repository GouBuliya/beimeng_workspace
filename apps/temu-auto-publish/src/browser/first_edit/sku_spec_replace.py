"""
@PURPOSE: 处理首次编辑场景下的规格单位填写与 SKU 规格选项替换,提升鲁棒性与校验能力
@OUTLINE:
  - 定位常量与候选选择器: 规格输入,添加/删除按钮,定位重试参数
  - 规格值准备: _normalize_spec_values, _prepare_spec_values, _snapshot_spec_values
  - 定位与等待: _wait_for_count_change, _locate_first_spec_input, _locate_spec_option_inputs 等
  - 规格填充流程: _cleanup_excess_options_core, _fill_spec_values_core, _replace_sku_spec_options_core
  - Mixin 及独立函数入口: FirstEditSkuSpecReplaceMixin, replace_sku_spec_options 等
@DEPENDENCIES:
  - 内部: .base.FirstEditBase, .retry.first_edit_step_retry, ...utils.selector_race.TIMEOUTS
  - 外部: playwright.async_api.Page, loguru.logger
@GOTCHAS:
  - 规格数据缺失会回退到页面现有值;如仍为空则写入占位值并提示人工确认
  - 多策略定位附带重试,若选择器漂移需及时更新候选列表
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import NamedTuple

from loguru import logger
from playwright.async_api import Locator, Page

from ...utils.selector_race import TIMEOUTS
from .base import FirstEditBase
from .retry import first_edit_step_retry


class SpecLocatorResult(NamedTuple):
    """规格输入定位结果."""

    inputs: Locator
    selector: str
    strategy: str


SPEC_OPTION_INPUT_CANDIDATES: list[tuple[str, str]] = [
    ("placeholder-strict", "input[placeholder='请输入选项名称']"),
    ("placeholder-fuzzy", "input[placeholder*='选项'][type='text']"),
    ("placeholder-spec-value", "input[placeholder*='规格值'], input[placeholder*='属性值']"),
    ("sale-attribute-inner", ".sale-attribute-list input.jx-input__inner"),
    ("data-test", "input[data-testid*='spec'], input[data-test*='spec']"),
    ("role-textbox", "[role='textbox'][aria-label*='选项']"),
    ("generic-text", ".sale-attribute-list input[type='text']:not([placeholder*='规格名称'])"),
    (
        "aria-fallback",
        (
            "xpath=//input[@type='text' and (contains(@placeholder,'选项') or "
            "contains(@aria-label,'选项'))]"
        ),
    ),
]

ADD_OPTION_BUTTON_CANDIDATES: list[tuple[str, str]] = [
    ("text-add", "button:has-text('添加选项')"),
    ("text-add-spec", "button:has-text('添加规格'), button:has-text('新增选项')"),
    ("sale-attribute-button", ".sale-attribute-list button.jx-button"),
    ("button-generic", ".sale-attribute-list button[type='button']"),
    ("aria-add", "[aria-label*='添加规格'], [aria-label*='添加选项']"),
]

DELETE_ICON_RELATIVE_CANDIDATES: list[str] = [
    (
        "xpath=ancestor::div[contains(@class,'jx-input-group')]"
        "//div[contains(@class,'jx-input-group__append')]"
        "//i[contains(@class,'jx-icon')]"
    ),
    "css=.. >> .jx-input-group__append .jx-icon",
    "css=.. >> .. >> .jx-input-group__append .jx-icon",
    "css=.. >> button:has-text('删除')",
    "css=.. >> .. >> button:has-text('删除')",
    "css=.. >> button:has-text('移除')",
]

SPEC_COLUMN_SELECTOR = ".sale-attribute-form-item"
SPEC_LIST_SELECTOR = ".sale-attribute-list"

MAX_SPEC_OPTIONS = 20
DEFAULT_SPEC_VALUE = "默认"
LOCATE_MAX_ATTEMPTS = 3
LOCATE_BASE_INTERVAL = 0.2
LOCATE_MAX_INTERVAL = 0.6


async def _wait_for_count_change(
    locator: Locator,
    expected_count: int,
    *,
    timeout_ms: int = TIMEOUTS.SLOW,
    poll_interval: float = 0.05,
    max_interval: float = 0.15,
) -> bool:
    """智能等待元素数量变化(指数退避轮询).

    Args:
        locator: 需要观察的定位器.
        expected_count: 期望的数量.
        timeout_ms: 等待超时时间(毫秒).
        poll_interval: 初始轮询间隔秒.
        max_interval: 最大轮询间隔秒.

    Returns:
        在超时前数量匹配返回 True,否则返回 False.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + (timeout_ms / 1_000)
    interval = poll_interval

    while loop.time() < deadline:
        try:
            current = await locator.count()
            if current == expected_count:
                return True
        except Exception as exc:  # pragma: no cover - UI 不稳定时的兜底
            logger.debug("等待数量变化时捕获异常,继续轮询: {}", exc)
        await asyncio.sleep(interval)
        interval = min(interval * 1.5, max_interval)
    return False


def _normalize_spec_values(spec_array: Sequence[str]) -> list[str]:
    """清洗规格列表,去除空值并保留顺序."""
    normalized: list[str] = []
    for raw in spec_array:
        value = (raw or "").strip()
        if value:
            normalized.append(value)
    return normalized


def _prepare_spec_values(
    spec_array: Sequence[str],
    existing_values: Sequence[str] | None = None,
    *,
    max_options: int = MAX_SPEC_OPTIONS,
) -> tuple[list[str], bool]:
    """规格值预处理:去空,去重,截断并兜底.

    Args:
        spec_array: 原始规格值列表.
        existing_values: 页面当前已有的规格值(用于兜底).
        max_options: 最大允许规格数.

    Returns:
        (规格值列表, 是否使用兜底数据).
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in spec_array:
        value = (raw or "").strip()
        if not value or value in seen:
            continue
        cleaned.append(value)
        seen.add(value)

    if len(cleaned) > max_options:
        logger.warning("规格值数量 {} 超过上限 {},将截断", len(cleaned), max_options)
        cleaned = cleaned[:max_options]

    if cleaned:
        return cleaned, False

    fallback = [value.strip() for value in (existing_values or []) if value.strip()]
    if fallback:
        logger.warning("规格数据缺失,使用页面现有规格兜底: {}", fallback)
        return fallback, True

    logger.warning("规格数据缺失且页面为空,使用占位规格兜底: {}", DEFAULT_SPEC_VALUE)
    return [DEFAULT_SPEC_VALUE], True


async def _locate_with_candidates(
    page: Page,
    candidates: list[tuple[str, str]],
    *,
    timeout_ms: int,
    desc: str,
    max_attempts: int = LOCATE_MAX_ATTEMPTS,
) -> tuple[Locator, str, str] | None:
    """多候选定位器探测,带重试."""
    interval = LOCATE_BASE_INTERVAL
    for attempt in range(1, max_attempts + 1):
        for strategy, selector in candidates:
            locator = page.locator(selector)
            try:
                count = await locator.count()
                if count:
                    await locator.first.wait_for(state="visible", timeout=timeout_ms)
                    if attempt > 1:
                        logger.debug("{}策略第 {} 次重试命中: {}", desc, attempt, strategy)
                    else:
                        logger.debug("{}策略命中: {}", desc, strategy)
                    return locator, selector, strategy
            except Exception as exc:
                logger.debug("{}策略 {} 失败: {}", desc, strategy, exc)
        if attempt < max_attempts:
            await asyncio.sleep(interval)
            interval = min(interval * 1.5, LOCATE_MAX_INTERVAL)
    logger.error("{}全部候选未命中", desc)
    return None


async def _locate_first_spec_input(
    page: Page,
    *,
    timeout_ms: int = TIMEOUTS.SLOW,
) -> Locator | None:
    """定位第一个规格名称(规格单位)输入框."""
    sale_attr_scope = page.locator(SPEC_LIST_SELECTOR).first
    candidates = [
        sale_attr_scope.locator("input[placeholder='请输入规格名称']"),
        sale_attr_scope.locator(
            "input[placeholder*='规格'][type='text']:not([placeholder*='选项'])"
        ),
        sale_attr_scope.locator(".jx-input-group__prepend input"),
        page.get_by_role("textbox", name="规格单位"),
        page.get_by_role("textbox", name="规格名称"),
        page.get_by_role("textbox", name="规格名"),
        page.locator("input[placeholder*='规格单位']"),
        page.locator("input[aria-label*='规格单位']"),
        page.locator("input[aria-label*='规格名称']"),
        page.locator("[data-testid*='spec-name'], [data-test*='spec-name']"),
    ]
    await page.wait_for_load_state("domcontentloaded")

    for candidate in candidates:
        try:
            if await candidate.count():
                target = candidate.first
                await target.wait_for(state="visible", timeout=timeout_ms)
                return target
        except Exception:
            continue

    try:
        raw_inputs = sale_attr_scope.locator("input.jx-input__inner")
        if await raw_inputs.count():
            fallback = raw_inputs.first
            placeholder = (await fallback.get_attribute("placeholder") or "").strip()
            if "选项" not in placeholder:
                return fallback
    except Exception:
        return None

    return None


@first_edit_step_retry(max_attempts=3)
async def fill_first_spec_unit(
    page: Page,
    spec_unit: str | None,
    timeout: int = TIMEOUTS.SLOW,
) -> bool:
    """将规格单位填入第一个规格名称输入框."""
    unit_text = (spec_unit or "").strip()
    if not unit_text:
        logger.info("规格单位为空,跳过规格名称填写")
        return True

    try:
        target_input = await _locate_first_spec_input(page, timeout_ms=timeout)
        if target_input is None:
            logger.error("未找到第一个规格输入框,无法写入规格单位")
            return False
        await page.wait_for_load_state("domcontentloaded")

        await target_input.scroll_into_view_if_needed()
        await target_input.click()
        try:
            await target_input.press("ControlOrMeta+a")
        except Exception:
            logger.debug("快捷键全选规格单位失败,改用直接覆盖填充")
        await target_input.fill("")
        await target_input.fill(unit_text)

        logger.success("规格单位已写入第一个规格输入框: {}", unit_text)
        return True
    except Exception as exc:
        logger.error("填写规格单位失败: {}", exc)
        return False


async def _locate_spec_option_inputs(page: Page, timeout_ms: int) -> SpecLocatorResult | None:
    """尝试使用多候选选择器定位规格选项输入框列."""
    await page.wait_for_load_state("domcontentloaded")
    located = await _locate_with_candidates(
        page,
        SPEC_OPTION_INPUT_CANDIDATES,
        timeout_ms=timeout_ms,
        desc="规格输入框定位",
    )
    if located is None:
        return None
    locator, selector, strategy = located
    return SpecLocatorResult(locator, selector, strategy)


async def _locate_add_button(page: Page, timeout_ms: int) -> tuple[Locator, str] | None:
    """尝试定位“添加选项”按钮."""
    await page.wait_for_load_state("domcontentloaded")
    located = await _locate_with_candidates(
        page,
        ADD_OPTION_BUTTON_CANDIDATES,
        timeout_ms=timeout_ms,
        desc="添加选项按钮定位",
    )
    if located is None:
        return None
    locator, _, strategy = located
    return locator, strategy


async def _locate_delete_button(input_el: Locator, timeout_ms: int) -> Locator | None:
    """基于输入框向上查找删除图标,支持重试与多个候选定位."""
    try:
        await input_el.first.wait_for(state="attached", timeout=timeout_ms)
    except Exception:
        logger.debug("等待规格输入可用失败,直接尝试定位删除按钮")
    interval = LOCATE_BASE_INTERVAL
    for attempt in range(1, LOCATE_MAX_ATTEMPTS + 1):
        for selector in DELETE_ICON_RELATIVE_CANDIDATES:
            candidate = input_el.locator(selector)
            try:
                if await candidate.count():
                    await candidate.first.wait_for(state="visible", timeout=timeout_ms)
                    return candidate.first
            except Exception as exc:
                logger.debug("删除按钮候选 {} 失败: {}", selector, exc)
        if attempt < LOCATE_MAX_ATTEMPTS:
            await asyncio.sleep(interval)
            interval = min(interval * 1.5, LOCATE_MAX_INTERVAL)
    return None


async def _snapshot_spec_values(inputs: Locator) -> list[str]:
    """读取当前所有规格输入框的值(去除首尾空白)."""
    values: list[str] = []
    count = await inputs.count()
    for index in range(count):
        try:
            value = (await inputs.nth(index).input_value()).strip()
        except Exception as exc:  # pragma: no cover - UI 并发导致的兜底
            logger.debug("读取规格输入框第 {} 项失败: {}", index + 1, exc)
            value = ""
        values.append(value)
    return values


async def _cleanup_spec_columns(page: Page, timeout: int) -> None:
    """仅保留首个规格列,删除多余的规格列."""
    await page.wait_for_load_state("domcontentloaded")
    spec_columns = page.locator(SPEC_COLUMN_SELECTOR)
    spec_column_count = await spec_columns.count()
    if spec_column_count <= 1:
        return

    logger.info("检测到 {} 个规格列,开始删除多余规格列", spec_column_count)
    for index in range(spec_column_count - 1, 0, -1):
        column = spec_columns.nth(index)
        header = column.locator(SPEC_LIST_SELECTOR).first
        icon_candidates = header.locator("i.jx-icon")
        trash_icons = icon_candidates.filter(has=header.locator("path[d*='256H96']"))
        delete_icon = trash_icons.first if await trash_icons.count() else icon_candidates.first

        if await delete_icon.count() == 0:
            logger.warning("第 {} 个规格列未找到删除按钮,跳过", index + 1)
            continue

        current_columns = await spec_columns.count()
        await delete_icon.click()
        removed = await _wait_for_count_change(
            spec_columns, current_columns - 1, timeout_ms=timeout
        )
        if not removed:
            logger.warning("等待删除规格列超时,列数未达到预期")


async def _cleanup_excess_options_core(page: Page, timeout: int) -> SpecLocatorResult:
    """清理多余规格选项,仅保留前两个输入框,并返回输入框定位器."""
    await page.wait_for_load_state("domcontentloaded")
    await _cleanup_spec_columns(page, timeout)

    located = await _locate_spec_option_inputs(page, timeout_ms=timeout)
    if located is None:
        raise RuntimeError("未找到规格选项输入框,无法执行清理")
    option_inputs, selector_used, strategy = located

    count = await option_inputs.count()
    logger.debug("当前规格选项数量: {} (策略: {})", count, strategy)

    if count <= 2:
        logger.info("规格选项数量 <= 2,无需清理")
        return located

    delete_count = count - 2
    logger.info("需要删除 {} 个多余选项", delete_count)

    for index in range(count - 1, 1, -1):
        target_input = option_inputs.nth(index)
        delete_btn = await _locate_delete_button(target_input, timeout_ms=timeout)
        if delete_btn is None:
            logger.warning("第 {} 个选项未找到删除按钮,跳过", index + 1)
            continue

        current_count = await option_inputs.count()
        await delete_btn.click()
        decreased = await _wait_for_count_change(
            option_inputs, current_count - 1, timeout_ms=timeout
        )
        if not decreased:
            logger.warning("删除第 {} 个选项后数量未按预期减少", index + 1)

    remaining = await page.locator(selector_used).count()
    logger.info("清理完成,剩余选项数量: {}", remaining)
    return SpecLocatorResult(page.locator(selector_used), selector_used, strategy)


async def _clear_trailing_inputs(inputs: Locator, start_index: int) -> None:
    """清空多余输入框,避免遗留旧值影响幂等."""
    count = await inputs.count()
    if count:
        await inputs.first.wait_for(state="visible", timeout=TIMEOUTS.NORMAL)
    for index in range(start_index, count):
        try:
            await inputs.nth(index).fill("")
        except Exception as exc:
            logger.debug("清空第 {} 个多余规格值失败: {}", index + 1, exc)


async def _verify_spec_values(inputs: Locator, expected: list[str]) -> bool:
    """写入后校验规格值,必要时尝试补写一次."""
    count = await inputs.count()
    if count:
        await inputs.first.wait_for(state="visible", timeout=TIMEOUTS.NORMAL)
    actual = [value for value in await _snapshot_spec_values(inputs) if value]
    if actual == expected:
        return True

    logger.warning("规格值校验未通过,预期 {} 实际 {},尝试补写一次", expected, actual)
    for index, spec_value in enumerate(expected):
        try:
            target_input = inputs.nth(index)
            await target_input.click()
            await target_input.fill("")
            await target_input.fill(spec_value)
        except Exception as exc:
            logger.debug("补写第 {} 个规格值失败: {}", index + 1, exc)

    actual_after = [value for value in await _snapshot_spec_values(inputs) if value]
    if actual_after != expected:
        logger.error("规格值校验失败,预期 {} 实际 {}", expected, actual_after)
        return False
    return True


async def _fill_spec_values_core(
    page: Page,
    spec_array: list[str],
    timeout: int,
) -> bool:
    """填充规格值到输入框,必要时动态添加输入框并校验写入结果."""
    await page.wait_for_load_state("domcontentloaded")
    located = await _locate_spec_option_inputs(page, timeout_ms=timeout)
    if located is None:
        logger.error("填充规格值失败: 未找到规格选项输入框")
        return False

    _, selector_used, _ = located
    add_btn_located = await _locate_add_button(page, timeout_ms=timeout)

    for index, spec_value in enumerate(spec_array):
        inputs = page.locator(selector_used)
        input_count = await inputs.count()

        if index < input_count:
            target_input = inputs.nth(index)
        else:
            if add_btn_located is None:
                logger.error("添加选项按钮未找到,无法创建新的规格输入框")
                return False
            add_btn, strategy = add_btn_located
            current_count = input_count
            await add_btn.first.click()
            created = await _wait_for_count_change(inputs, current_count + 1, timeout_ms=timeout)
            if not created:
                logger.error("点击添加选项按钮失败,输入框数量未增加(策略: {})", strategy)
                return False
            inputs = page.locator(selector_used)
            count_after = await inputs.count()
            target_input = inputs.nth(count_after - 1)

        await target_input.click()
        await target_input.fill("")
        await target_input.fill(spec_value)
        logger.debug("已填入规格值 [{}] -> {}", index + 1, spec_value)

    await _clear_trailing_inputs(page.locator(selector_used), len(spec_array))
    verified = await _verify_spec_values(page.locator(selector_used), spec_array)
    if verified:
        logger.success("规格值填充完成,共填入 {} 个规格", len(spec_array))
    return verified


async def _replace_sku_spec_options_core(
    page: Page,
    spec_array: list[str],
    timeout: int,
) -> bool:
    """替换规格选项的核心流程(清理 + 填充 + 幂等判断 + 校验)."""
    await page.wait_for_load_state("domcontentloaded")
    located = await _locate_spec_option_inputs(page, timeout_ms=timeout)
    existing_values: list[str] = []
    if located:
        option_inputs, _, strategy = located
        existing_values = [value for value in await _snapshot_spec_values(option_inputs) if value]
        if existing_values:
            logger.debug("读取到页面现有规格值(策略: {}): {}", strategy, existing_values)

    normalized_spec = _normalize_spec_values(spec_array)
    prepared_spec, used_fallback = _prepare_spec_values(normalized_spec, existing_values)

    if existing_values and existing_values == prepared_spec:
        logger.info("当前规格与目标一致,跳过覆盖")
        return True

    await _cleanup_excess_options_core(page, timeout)
    success = await _fill_spec_values_core(page, prepared_spec, timeout)
    if success and used_fallback:
        logger.warning("规格值使用兜底数据写入,请人工确认: {}", prepared_spec)
    return success


class FirstEditSkuSpecReplaceMixin(FirstEditBase):
    """封装首次编辑流程中的 SKU 规格选项替换操作."""

    @first_edit_step_retry(max_attempts=3)
    async def fill_first_spec_unit(
        self,
        page: Page,
        spec_unit: str | None,
        timeout: int = TIMEOUTS.SLOW,
    ) -> bool:
        """将规格单位填入第一个规格名称输入框."""
        await page.wait_for_load_state("domcontentloaded")
        return await fill_first_spec_unit(page, spec_unit, timeout)

    @first_edit_step_retry(max_attempts=3)
    async def replace_sku_spec_options(
        self,
        page: Page,
        spec_array: list[str],
        timeout: int = 3000,
    ) -> bool:
        """替换销售属性列表中的规格选项."""
        try:
            await page.wait_for_load_state("domcontentloaded")
            success = await _replace_sku_spec_options_core(page, spec_array, timeout)
            if success:
                logger.success(
                    "SKU 规格选项替换完成, 共填入 {} 个规格",
                    len(_normalize_spec_values(spec_array)),
                )
            else:
                logger.error("SKU 规格选项替换失败")
            return success
        except Exception as exc:
            logger.error("替换 SKU 规格选项异常: {}", exc)
            return False

    @first_edit_step_retry(max_attempts=3)
    async def _cleanup_excess_options(self, page: Page, timeout: int = TIMEOUTS.SLOW) -> None:
        """清理多余选项,保留前 2 个."""
        await page.wait_for_load_state("domcontentloaded")
        await _cleanup_excess_options_core(page, timeout)

    @first_edit_step_retry(max_attempts=3)
    async def _fill_spec_values(
        self,
        page: Page,
        spec_array: list[str],
        timeout: int = TIMEOUTS.SLOW,
    ) -> bool:
        """填充规格值到输入框."""
        await page.wait_for_load_state("domcontentloaded")
        return await _fill_spec_values_core(page, _normalize_spec_values(spec_array), timeout)


# ============ 独立公共函数(供 first_edit_dialog_codegen 调用)============


@first_edit_step_retry(max_attempts=3)
async def replace_sku_spec_options(
    page: Page,
    spec_array: list[str],
    timeout: int = 3000,
) -> bool:
    """替换销售属性列表中的规格选项(独立函数版本)."""
    try:
        await page.wait_for_load_state("domcontentloaded")
        success = await _replace_sku_spec_options_core(page, spec_array, timeout)
        if success:
            logger.success(
                "SKU 规格选项替换完成, 共填入 {} 个规格",
                len(_normalize_spec_values(spec_array)),
            )
        else:
            logger.error("SKU 规格选项替换失败")
        return success
    except Exception as exc:
        logger.error("替换 SKU 规格选项异常: {}", exc)
        return False


@first_edit_step_retry(max_attempts=3)
async def _cleanup_excess_options_standalone(page: Page, timeout: int = TIMEOUTS.SLOW) -> None:
    """清理多余选项,保留前 2 个(独立函数版本,智能等待)."""
    await page.wait_for_load_state("domcontentloaded")
    await _cleanup_excess_options_core(page, timeout)


@first_edit_step_retry(max_attempts=3)
async def _fill_spec_values_standalone(
    page: Page,
    spec_array: list[str],
    timeout: int = TIMEOUTS.SLOW,
) -> bool:
    """填充规格值到输入框(独立函数版本,智能等待)."""
    await page.wait_for_load_state("domcontentloaded")
    return await _fill_spec_values_core(page, _normalize_spec_values(spec_array), timeout)
