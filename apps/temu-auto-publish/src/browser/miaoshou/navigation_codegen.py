from __future__ import annotations

import re
from contextlib import suppress

from loguru import logger
from playwright.async_api import Locator, Page

TAB_LABELS = {
    "all": ("全部", "All", "ALL"),
    "unclaimed": ("未认领", "Unclaimed"),
    "claimed": ("已认领", "Claimed"),
    "failed": ("失败", "Failed"),
}


def _label_variants(tab_name: str) -> list[str]:
    """Return all label variants for a logical tab name."""

    labels = TAB_LABELS.get(tab_name)
    if labels is None:
        return [tab_name]
    if isinstance(labels, str):
        labels = (labels,)

    variants: list[str] = []
    for label in labels:
        if not label:
            continue
        for variant in {label, label.upper(), label.lower()}:
            if variant not in variants:
                variants.append(variant)
    return variants or [tab_name]


async def _wait_for_dropdown_visibility(
    page: Page, state: str = "visible", timeout: int = 800
) -> None:
    """等待通用下拉组件达到指定状态."""

    dropdown = page.locator(
        ".jx-select-dropdown, .jx-popper, [role='listbox'], .el-select-dropdown, .ant-select-dropdown"
    )
    with suppress(Exception):
        await dropdown.first.wait_for(state=state, timeout=timeout)


async def _wait_for_search_completion(page: Page, timeout: int = 3_000) -> None:
    """等待表格刷新完成."""

    with suppress(Exception):
        await page.wait_for_load_state("networkidle", timeout=timeout)
    with suppress(Exception):
        await page.wait_for_function(
            "() => document.querySelectorAll('.pro-virtual-table__row-body').length > 0",
            timeout=timeout,
        )


async def _wait_for_tab_activation(page: Page, label: str, timeout: int = 3_000) -> None:
    """等待指定标签被激活."""

    activation_script = """
        (text) => {
            const tabs = Array.from(
                document.querySelectorAll('[role="tab"], .jx-tabs__item, .jx-radio-button, .pro-tabs__item')
            );
            const target = tabs.find(el => (el.textContent || '').trim().includes(text));
            if (!target) return false;
            const ariaSelected = target.getAttribute('aria-selected');
            const className = target.className || '';
            return ariaSelected === 'true' || /is-active|active/.test(className);
        }
    """
    with suppress(Exception):
        await page.wait_for_function(activation_script, label, timeout=timeout)
    await _wait_for_search_completion(page, timeout=timeout)


async def _click_search_button_candidates(page: Page) -> bool:
    """点击搜索按钮候选集合."""

    search_button_candidates = [
        page.locator("button:has-text('搜索')"),
        page.get_by_role("button", name="搜索"),
        page.locator("button:has-text('Search')"),
        page.get_by_role("button", name="Search"),
        page.locator("button:has-text('查询')"),
        page.locator("button:has-text('GO')"),
    ]

    for candidate in search_button_candidates:
        try:
            if await candidate.count():
                await candidate.first.click()
                await _wait_for_search_completion(page)
                logger.success("Search triggered via locator: {}", candidate)
                return True
        except Exception:
            continue

    logger.warning("Search button not clickable via known candidates")
    return False


async def fallback_apply_user_filter(page: Page, staff_name: str) -> bool:
    """Best-effort user filter using recorded selectors (用于兼容旧环境)."""

    logger.info("Fallback: applying user filter via recorded selectors -> {}", staff_name)

    input_candidates = [
        page.get_by_placeholder("请输入创建人员", exact=False),
        page.get_by_placeholder("请输入创建人", exact=False),
        page.get_by_placeholder("请输入负责人", exact=False),
        page.get_by_placeholder("请输入妙手", exact=False),
        page.get_by_placeholder("请输入姓名", exact=False),
        page.get_by_label("妙手创建人员", exact=False),
        page.get_by_label("创建人员", exact=False),
        page.get_by_label("创建人", exact=False),
        page.get_by_label("负责人", exact=False),
        page.get_by_placeholder("Creator", exact=False),
        page.get_by_placeholder("Created by", exact=False),
        page.get_by_placeholder("Owner", exact=False),
        page.get_by_placeholder("Responsible", exact=False),
        page.locator("label:has-text('创建人员') + .el-select input"),
        page.locator("label:has-text('创建人') + .el-select input"),
        page.locator("label:has-text('负责人') + .el-select input"),
        page.locator("label:has-text('妙手') + .el-select input"),
        page.locator("label:has-text('Creator') + .el-select input"),
        page.locator("label:has-text('Created by') + .el-select input"),
        page.locator(".el-select:has-text('创建人员') input"),
        page.locator(".pro-form-item:has-text('创建人') input"),
        page.locator(".pro-form-item:has-text('负责人') input"),
        page.locator(".pro-form-item:has-text('妙手') input"),
        page.locator(".pro-form-item:has-text('Creator') input"),
        page.locator(".jx-form-item:has-text('创建人') input"),
        page.locator(".jx-form-item:has-text('负责人') input"),
        page.locator(".jx-form-item:has-text('妙手') input"),
        page.locator(".jx-form-item:has-text('Creator') input"),
        page.locator(".jx-select:has-text('创建人') input"),
        page.locator(".jx-select:has-text('负责人') input"),
        page.locator(".jx-select:has-text('Creator') input"),
        page.locator(".pro-select:has-text('创建人') input"),
        page.locator(".pro-select:has-text('负责人') input"),
        page.locator(".pro-select:has-text('Creator') input"),
        page.locator("xpath=//*[contains(normalize-space(),'创建人')]/following::input[1]"),
        page.locator("xpath=//*[contains(normalize-space(),'负责人')]/following::input[1]"),
        page.locator("xpath=//*[contains(normalize-space(),'妙手')]/following::input[1]"),
        page.locator("xpath=//*[contains(normalize-space(),'Creator')]/following::input[1]"),
        page.locator("input[placeholder*='创建人']"),
        page.locator("input[placeholder*='创建人员']"),
        page.locator("input[placeholder*='负责人']"),
        page.locator("input[placeholder*='妙手']"),
        page.locator("input[placeholder*='请选择或输入搜索']"),
        page.locator("input[placeholder*='姓名']"),
        page.locator("input[placeholder*='Creator']"),
        page.locator("input[placeholder*='Created']"),
        page.locator("input[placeholder*='Owner']"),
        page.locator("input[placeholder*='Responsible']"),
        page.locator("input[aria-label*='创建']"),
        page.locator("input[aria-label*='负责人']"),
        page.locator("textarea[placeholder*='创建人']"),
        page.locator("textarea[placeholder*='负责人']"),
    ]

    combobox_candidates = [
        page.get_by_role("combobox", name="创建人", exact=False),
        page.get_by_role("combobox", name="创建人员", exact=False),
        page.get_by_role("combobox", name="负责人", exact=False),
        page.get_by_role("combobox", name="妙手", exact=False),
        page.get_by_role("combobox", name="Creator", exact=False),
        page.get_by_role("combobox", name="Created by", exact=False),
        page.locator(".pro-form-item:has-text('创建人') [role='combobox']"),
        page.locator(".pro-form-item:has-text('负责人') [role='combobox']"),
        page.locator(".pro-form-item:has-text('Creator') [role='combobox']"),
        page.locator(".jx-select:has-text('创建人')"),
        page.locator(".jx-select:has-text('负责人')"),
        page.locator(".jx-select:has-text('Creator')"),
        page.locator(".pro-select:has-text('创建人')"),
        page.locator(".pro-select:has-text('负责人')"),
        page.locator(".pro-select:has-text('Creator')"),
    ]

    container_candidates = [
        page.locator(".pro-form-item:has-text('创建人')"),
        page.locator(".jx-form-item:has-text('创建人')"),
        page.locator(".pro-form-item:has-text('负责人')"),
        page.locator(".jx-form-item:has-text('负责人')"),
        page.locator(".pro-form-item:has-text('妙手')"),
        page.locator(".jx-form-item:has-text('妙手')"),
        page.locator(".pro-form-item:has-text('Creator')"),
        page.locator(".jx-form-item:has-text('Creator')"),
        page.locator(
            "xpath=//label[contains(normalize-space(),'创建人')]/ancestor::*[contains(@class,'form-item')][1]"
        ),
        page.locator(
            "xpath=//label[contains(normalize-space(),'负责人')]/ancestor::*[contains(@class,'form-item')][1]"
        ),
        page.locator(
            "xpath=//label[contains(normalize-space(),'妙手')]/ancestor::*[contains(@class,'form-item')][1]"
        ),
        page.locator(
            "xpath=//label[contains(normalize-space(),'Creator')]/ancestor::*[contains(@class,'form-item')][1]"
        ),
    ]

    target_input: Locator | None = None
    for candidate in input_candidates:
        try:
            if await candidate.count() > 0:
                target_input = candidate.first
                break
        except Exception:
            continue

    if target_input is None:
        for container in container_candidates:
            try:
                if await container.count() == 0:
                    continue
                trigger = container.locator(
                    ".jx-select, .pro-select, .el-select, [role='combobox'], .jx-select__tags"
                ).first
                if await trigger.count() == 0:
                    continue
                await trigger.click()
                await _wait_for_dropdown_visibility(page, state="visible")
                combo_input = trigger.locator("input:not([type='hidden'])").first
                if await combo_input.count() > 0:
                    target_input = combo_input
                    break
            except Exception:
                continue

    if target_input is None:
        for candidate in combobox_candidates:
            try:
                if await candidate.count() > 0:
                    target_input = candidate.first.locator("input")
                    if await target_input.count() == 0:
                        target_input = candidate.first
                    break
            except Exception:
                continue

    if target_input is None:
        logger.warning("Fallback user filter: no input field found, trying direct search")
        return await _click_search_button_candidates(page)

    try:
        await target_input.click()
        with suppress(Exception):
            await target_input.fill("")
        try:
            await target_input.type(staff_name, delay=60)
        except Exception:
            await page.keyboard.insert_text(staff_name)
        await _wait_for_dropdown_visibility(page, state="visible")
    except Exception as exc:
        logger.error("Fallback user filter: unable to type staff name ({})", exc)
        return False

    option_selectors = [
        f"li:has-text('{staff_name}')",
        f".el-select-dropdown__item:has-text('{staff_name}')",
        f".ant-select-dropdown-menu-item:has-text('{staff_name}')",
        f".jx-select-dropdown__item:has-text('{staff_name}')",
        f".pro-select-dropdown__item:has-text('{staff_name}')",
        f"[role='option']:has-text('{staff_name}')",
    ]
    option_clicked = False
    for selector in option_selectors:
        locator = page.locator(selector)
        try:
            if await locator.count():
                await locator.first.click()
                option_clicked = True
                break
        except Exception:
            continue

    if not option_clicked:
        logger.warning("Fallback user filter: option not found, continue without strict match")
        with suppress(Exception):
            await target_input.press("Enter")

    return await _click_search_button_candidates(page)


async def fallback_switch_tab(page: Page, tab_name: str) -> bool:
    """Fallback tab switch using deterministic locator strategy."""

    labels = _label_variants(tab_name)
    logger.warning(f"🔍 Fallback tab switch DEBUG: looking for labels {labels}")

    # 调试:输出页面内所有可能的 tab 相关元素
    try:
        all_buttons = await page.locator("button").all()
        logger.warning(f"🔍 Found {len(all_buttons)} buttons on page")
        for i, btn in enumerate(all_buttons[:20]):  # 只显示前20个
            try:
                text = await btn.inner_text()
                if text.strip():
                    logger.warning(f"  Button[{i}]: {text.strip()}")
            except:
                pass

        all_tabs = await page.locator(
            "[role='tab'], .jx-tabs__item, .jx-radio-button, [class*='tab']"
        ).all()
        logger.warning(f"🔍 Found {len(all_tabs)} tab-like elements")
        for i, tab in enumerate(all_tabs[:20]):
            try:
                text = await tab.inner_text()
                classes = await tab.get_attribute("class")
                logger.warning(f"  Tab[{i}]: text='{text.strip()}' class='{classes}'")
            except:
                pass
    except Exception as e:
        logger.warning(f"Debug info collection failed: {e}")

    for label in labels:
        regex_label = re.escape(label)
        locator_candidates = [
            f".jx-radio-button:has-text('{label}')",
            f".jx-tabs__item:has-text('{label}')",
            f".pro-tabs__item:has-text('{label}')",
            f".el-tabs__item:has-text('{label}')",
            f".ant-tabs-tab:has-text('{label}')",
            f"[role='tab']:has-text('{label}')",
            f"button:has-text('{label}')",
            f"span:has-text('{label}')",
            f"div[class*='tab']:has-text('{label}')",
            f"li[class*='tab']:has-text('{label}')",
            f"text=/{regex_label}.*\\(/",
            f"xpath=//div[contains(@class,'tab') or contains(@class,'radio')]//*[contains(normalize-space(), '{label}')]",
            f"xpath=//span[contains(normalize-space(), '{label} (')]",
        ]

        for candidate in locator_candidates:
            locator = page.locator(candidate)
            if await _click_candidate(locator):
                logger.success("Fallback tab switch succeeded via locator {}", candidate)
                await _wait_for_tab_activation(page, label)
                return True

    # Final attempt with broader text search (录制法)
    locator_factories = [
        lambda text: page.get_by_role("tab", name=text, exact=False),
        lambda text: page.get_by_text(text, exact=False),
        lambda text: page.locator(f"//span[contains(normalize-space(), '{text}')]"),
        lambda text: page.locator(f"//div[contains(@class,'tab')][contains(., '{text}')]"),
    ]

    for variant in labels:
        for factory in locator_factories:
            locator = factory(variant)
            if await _click_candidate(locator):
                logger.success("Fallback tab switch succeeded via recorded selectors")
                await _wait_for_tab_activation(page, variant)
                return True

    logger.error("Fallback tab switch failed for labels: {}", labels)
    return False


async def _click_candidate(locator: Locator) -> bool:
    try:
        if await locator.count() == 0:
            return False
        target = locator.first
        with suppress(Exception):
            await target.scroll_into_view_if_needed()
        await target.wait_for(state="visible", timeout=2_000)
        await target.click()
        return True
    except Exception:
        return False
