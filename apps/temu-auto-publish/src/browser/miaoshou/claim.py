"""
@PURPOSE: Claim workflow utilities for the Miaoshou controller.
@OUTLINE:
  - class MiaoshouClaimMixin: DOM-driven selection, claim actions, verification helpers
    - async def refresh_collection_box(): 导航并确保列表可见
    - async def select_products_for_claim(): 勾选表格前 N 条商品
    - async def _resolve_checkbox_locator(): 复用勾选候选定位器并返回可点击元素
    - async def _ensure_claim_button_visible(): 确保认领按钮可见并返回定位器
    - async def _find_clickable_in_scopes(): 在 Page/Frame 中定位可交互按钮
    - async def _click_claim_confirmation_button(): 在认领弹窗中定位并点击确认按钮
    - async def claim_selected_products_to_temu(): 使用 DOM 操作执行认领
"""

import re
import time
from collections.abc import Sequence
from contextlib import suppress
from typing import Any, ClassVar

from loguru import logger
from playwright.async_api import Frame, Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from .navigation import MiaoshouNavigationMixin
from .navigation_codegen import fallback_apply_user_filter, fallback_switch_tab


class MiaoshouClaimMixin(MiaoshouNavigationMixin):
    """Provide claim related helpers for Miaoshou workflows."""

    _COLLECTION_BOX_URL: ClassVar[str] = (
        "https://erp.91miaoshou.com/common_collect_box/items?tabPaneName=all"
    )
    _ROW_SELECTOR: ClassVar[str] = ".pro-virtual-table__row-body"
    # vue-recycle-scroller 虚拟滚动行选择器
    _VIRTUAL_ROW_SELECTOR: ClassVar[str] = ".vue-recycle-scroller__item-view"
    _ROW_HEIGHT: ClassVar[int] = 128
    _ROW_CHECKBOX_SELECTOR: ClassVar[str] = (
        ".is-fixed-left.is-selection-column .jx-checkbox"
    )
    _CHECKBOX_CANDIDATE_SELECTORS: ClassVar[tuple[str, ...]] = (
        "input[type='checkbox']",
        ".jx-checkbox__input",
        ".jx-checkbox__inner",
        ".jx-checkbox",
    )
    _CLAIM_PRIORITY_SELECTORS: ClassVar[tuple[str, ...]] = (
        "#jx-id-1917-80",
        "button.jx-button.jx-button--primary.jx-button--small:not(.is-text):has-text('认领到')",
        "button.pro-button:not(.is-text):has-text('认领到')",
        "xpath=//span[contains(normalize-space(), '认领到')]/ancestor::button[1]",
    )
    _CLAIM_FALLBACK_SELECTORS: ClassVar[tuple[str, ...]] = (
        "button:has-text('认领到')",
        "button:has-text('认领')",
        "[role='button']:has-text('认领到')",
        "[role='button']:has-text('认领')",
        "xpath=//button[contains(normalize-space(), '认领')]",
        "xpath=//*[contains(normalize-space(), '认领') and (@role='button' or contains(@class, 'button'))]",
    )
    _SELECT_DROPDOWN_LOCATOR: ClassVar[str] = (
        ".jx-select-dropdown, .jx-popper, [role='listbox'], .el-select-dropdown, .ant-select-dropdown"
    )
    _CLAIM_DROPDOWN_LOCATOR: ClassVar[str] = (
        ".el-dropdown-menu, .jx-dropdown-menu, .pro-dropdown__menu"
    )

    def __init__(
        self,
        *,
        selector_path: str = "config/miaoshou_selectors_v2.json",
        **kwargs: Any,
    ) -> None:
        """Initialise the claim mixin and load selector configuration."""

        super().__init__(selector_path=selector_path, **kwargs)

    async def refresh_collection_box(
        self,
        page: Page,
        *,
        filter_owner: str | None = None,
    ) -> None:
        """Refresh the Miaoshou collection box page and ensure rows are visible."""

        try:
            logger.debug(
                f"Refreshing collection box page at {self._COLLECTION_BOX_URL}"
            )
            await page.goto(self._COLLECTION_BOX_URL, wait_until="domcontentloaded")
            with suppress(Exception):
                await page.wait_for_load_state("networkidle", timeout=5_000)
        except Exception as exc:
            logger.warning(f"Failed to refresh collection box page: {exc}")

        await self._wait_for_rows(page)

        if filter_owner:
            logger.info("尝试按负责人筛选：{}", filter_owner)
            try:
                filtered = await self.filter_and_search(page, filter_owner)
                if not filtered:
                    logger.warning("负责人筛选逻辑返回 False：{}", filter_owner)
                await self._wait_for_rows(page)
            except Exception as exc:
                logger.warning("负责人筛选失败({}): {}", filter_owner, exc)

    async def _wait_for_rows(self, page: Page, *, timeout: int = 1_500) -> bool:
        """Wait until the collection box table rows are rendered."""

        rows = page.locator(self._ROW_SELECTOR)
        try:
            await rows.first.wait_for(state="visible", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            logger.warning(
                f"Product rows did not become visible within {timeout}ms"
            )
            return False

    async def _wait_for_dropdown_state(
        self,
        page: Page,
        selectors: str,
        *,
        state: str = "visible",
        timeout: int = 400,
    ) -> None:
        """Wait for dropdown containers matching ``selectors`` to reach ``state``."""

        dropdown = page.locator(selectors)
        with suppress(Exception):
            await dropdown.first.wait_for(state=state, timeout=timeout)

    async def _wait_for_select_dropdown(
        self,
        page: Page,
        *,
        state: str = "visible",
        timeout: int = 400,
    ) -> None:
        await self._wait_for_dropdown_state(
            page, self._SELECT_DROPDOWN_LOCATOR, state=state, timeout=timeout
        )

    async def _wait_for_claim_dropdown(
        self,
        page: Page,
        *,
        state: str = "visible",
        timeout: int = 400,
    ) -> None:
        await self._wait_for_dropdown_state(
            page, self._CLAIM_DROPDOWN_LOCATOR, state=state, timeout=timeout
        )

    @staticmethod
    def _resolve_target_indexes(
        count: int,
        indexes: Sequence[int] | None,
        available: int,
    ) -> list[int]:
        """Resolve a sorted list of row indexes that should be processed."""

        if indexes:
            candidates = sorted({idx for idx in indexes if idx is not None})
        else:
            candidates = list(range(count))

        resolved: list[int] = []
        for idx in candidates:
            if idx < 0:
                continue
            if idx >= available:
                logger.debug(
                    f"Row index {idx} exceeds available rows {available}"
                )
                continue
            resolved.append(idx)
        return resolved

    async def select_products_for_claim(
        self,
        page: Page,
        count: int = 5,
        indexes: Sequence[int] | None = None,
        *,
        enable_scroll: bool = True,
    ) -> bool:
        """Select the first ``count`` products before starting a claim batch.

        针对 vue-recycle-scroller 虚拟滚动列表的定位策略：
        1. DOM 元素会被回收，不可见的行设为 translateY(-9999px)
        2. 可见行通过 transform: translateY(N*128px) 定位
        3. 先滚动到目标位置，然后按 translateY 值找到正确的行

        Args:
            page: Active Playwright page instance.
            count: Number of products to select.
            indexes: Specific indexes to select (optional).
            enable_scroll: 是否启用滚动（默认启用）

        Returns:
            True when all target products were selected, otherwise False.
        """
        logger.info(f"Selecting up to {count} product rows (scroll={enable_scroll})")

        rows = page.locator(self._ROW_SELECTOR)
        if not await self._wait_for_rows(page):
            logger.error("Unable to locate any product rows for selection")
            return False

        available = await rows.count()
        if available == 0:
            logger.error("Product row count is zero, cannot proceed with selection")
            return False

        # 解析目标索引
        max_idx = max(indexes or [0]) + 1 if indexes else count
        target_indexes = self._resolve_target_indexes(count, indexes, max(available, max_idx))
        if not target_indexes:
            logger.warning(f"No valid row indexes resolved for selection, indexes={indexes}")
            return False

        logger.info(f"目标索引: {target_indexes}, 当前可见行数: {available}")

        selected = 0
        for idx in target_indexes:
            # 滚动到目标位置
            if enable_scroll:
                from ...utils.scroll_helper import scroll_to_product_position

                logger.info(f"滚动到商品 #{idx + 1} 的位置")
                await scroll_to_product_position(page, target_index=idx)
                await page.wait_for_timeout(500)

            # 核心：通过 translateY 值定位正确的行
            target_row = await self._find_row_by_translate_y(page, idx)
            if target_row:
                if await self._toggle_row_checkbox(page, target_row):
                    selected += 1
                    logger.debug(f"✓ 勾选商品 #{idx + 1} 成功 ({selected}/{len(target_indexes)})")
                    continue

            # 回退：找视口内的第一个可见行
            first_visible_row = await self._find_first_visible_row(page)
            if first_visible_row:
                if await self._toggle_row_checkbox(page, first_visible_row):
                    selected += 1
                    logger.debug(f"✓ 勾选商品 #{idx + 1} 成功 (回退) ({selected}/{len(target_indexes)})")
                    continue

            logger.error(f"Failed to toggle checkbox for product #{idx + 1}")
            return False

        logger.success(f"Selected {selected}/{len(target_indexes)} rows for claim")
        return selected == len(target_indexes)

    async def _find_row_by_translate_y(self, page: Page, index: int):
        """通过 translateY 值定位 vue-recycle-scroller 中的行。

        vue-recycle-scroller 使用 transform: translateY(N*128px) 来定位行。
        滚动后，目标行的 translateY 应该接近 0（在视口顶部）。

        Args:
            page: Playwright 页面对象
            index: 目标商品索引

        Returns:
            找到的行 Locator，或 None
        """
        import re

        try:
            virtual_rows = page.locator(self._VIRTUAL_ROW_SELECTOR)
            count = await virtual_rows.count()
            logger.debug(f"虚拟滚动行总数: {count}")

            if count == 0:
                return None

            # 找到 translateY 最小且 >= 0 的行（视口中的第一行）
            min_translate_y = float('inf')
            target_row = None

            for i in range(count):
                row = virtual_rows.nth(i)
                try:
                    style = await row.get_attribute("style") or ""
                    # 解析 translateY 值
                    match = re.search(r"translateY\((-?\d+(?:\.\d+)?)\s*(?:px)?\s*\)", style)
                    translate_y = float(match.group(1)) if match else -9999

                    # 跳过被回收的行（translateY = -9999px）
                    if translate_y < 0:
                        continue

                    # 找 translateY 最小的行
                    if translate_y < min_translate_y:
                        min_translate_y = translate_y
                        target_row = row
                except Exception:
                    continue

            if target_row:
                logger.debug(f"找到目标行，translateY={min_translate_y}px")
                return target_row.locator(self._ROW_SELECTOR).first

            return None
        except Exception as exc:
            logger.debug(f"通过 translateY 定位失败: {exc}")
            return None

    async def _find_first_visible_row(self, page: Page):
        """找到视口内的第一个可见行。"""
        try:
            rows = page.locator(self._ROW_SELECTOR)
            count = await rows.count()

            for i in range(min(count, 5)):
                row = rows.nth(i)
                try:
                    is_visible = await row.is_visible()
                    if is_visible:
                        box = await row.bounding_box()
                        if box and box["y"] >= 0:
                            return row
                except Exception:
                    continue

            return rows.first if count > 0 else None
        except Exception as exc:
            logger.debug(f"查找可见行失败: {exc}")
            return None

    async def _toggle_row_checkbox(self, page: Page, row: Locator) -> bool:
        """Toggle the checkbox contained within ``row`` via the pinned selection column."""

        selection_cell = row.locator(".is-fixed-left.is-selection-column").first
        if await selection_cell.count() == 0:
            logger.debug("Row does not expose a pinned selection cell")
            return False

        try:
            with suppress(Exception):
                await selection_cell.evaluate("el => el.scrollIntoView({ block: 'nearest' })")
            with suppress(Exception):
                await selection_cell.scroll_into_view_if_needed()
            await selection_cell.wait_for(state="visible", timeout=200)
        except PlaywrightTimeoutError:
            logger.debug("Selection cell did not become visible in time")
            return False
        except Exception as exc:
            logger.debug(f"Failed to prepare selection cell for interaction: {exc}")

        if not await self._hover_locator(page, selection_cell):
            logger.debug(
                "Unable to hover selection cell directly; fallback to row hover"
            )
            with suppress(Exception):
                await self._hover_locator(page, row)

        checkbox = await self._resolve_checkbox_locator(selection_cell)
        if checkbox is not None:
            try:
                await checkbox.click()
                return True
            except Exception as exc:
                logger.debug(f"Clicking checkbox candidate failed: {exc}")

        try:
            await selection_cell.click()
            return True
        except Exception as exc:
            logger.debug(f"Fallback click on selection cell failed: {exc}")
            return False

    async def _resolve_checkbox_locator(
        self,
        selection_cell: Locator,
        *,
        timeout: int = 300,
    ) -> Locator | None:
        """Return the first clickable checkbox locator inside ``selection_cell``."""

        candidates: list[Locator] = []
        if hasattr(selection_cell, "get_by_role"):
            with suppress(Exception):
                candidates.append(selection_cell.get_by_role("checkbox"))

        for selector in self._CHECKBOX_CANDIDATE_SELECTORS:
            with suppress(Exception):
                candidates.append(selection_cell.locator(selector))

        for locator in candidates:
            checkbox = await self._pick_clickable_candidate(locator, timeout=timeout)
            if checkbox is not None:
                return checkbox

        return None

    async def _hover_locator(self, page: Page, locator: Locator) -> bool:
        """Move mouse over ``locator`` using hover() and pointer fallback strategies."""

        try:
            await locator.hover()
            return True
        except Exception:
            bbox = None
            with suppress(Exception):
                bbox = await locator.bounding_box()
            if bbox is None:
                return False

            try:
                await page.mouse.move(
                    bbox["x"] + (bbox["width"] / 2),
                    bbox["y"] + min(bbox["height"] / 2, bbox["height"] - 2),
                )
                return True
            except Exception:
                return False

    async def _pick_clickable_candidate(
        self,
        locator: Locator,
        *,
        timeout: int = 300,
    ) -> Locator | None:
        """Return the first clickable element yielded by ``locator``."""

        try:
            count = await locator.count()
        except Exception:
            return None

        if count == 0:
            return None

        for idx in range(count):
            candidate = locator.nth(idx)
            try:
                await candidate.wait_for(state="attached", timeout=timeout)
                await candidate.wait_for(state="visible", timeout=timeout)
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue

            with suppress(Exception):
                await candidate.scroll_into_view_if_needed()

            try:
                if not await candidate.is_enabled():
                    continue
            except Exception:
                pass

            return candidate

        return None

    def _collect_operation_scopes(
        self,
        page: Page,
    ) -> list[tuple[str, Page | Frame]]:
        """Collect page-level scopes that should be searched for actionable buttons."""

        scopes: list[tuple[str, Page | Frame]] = [("page", page)]
        for idx, frame in enumerate(page.frames):
            label_suffix = frame.name or frame.url or "unnamed"
            scopes.append((f"frame[{idx}]::{label_suffix}", frame))

        return scopes

    async def _find_clickable_in_scopes(
        self,
        selectors: Sequence[str],
        scopes: Sequence[tuple[str, Page | Frame]],
        *,
        skip_table_rows: bool = True,
        timeout: int = 250,
    ) -> tuple[str, Locator] | None:
        """Return the first clickable locator resolved across ``scopes``."""

        for selector in selectors:
            for scope_name, scope in scopes:
                try:
                    locator = scope.locator(selector)
                except Exception:
                    continue

                candidate = await self._pick_clickable_candidate(
                    locator,
                    timeout=timeout,
                )
                if candidate is None:
                    continue

                if skip_table_rows and await self._is_table_row_descendant(candidate):
                    continue

                label = selector if scope_name == "page" else f"{selector} [scope={scope_name}]"
                return (label, candidate)

        return None

    async def _is_table_row_descendant(self, locator: Locator) -> bool:
        """Return whether ``locator`` is rendered inside a virtual table row."""

        try:
            return bool(
                await locator.evaluate(
                    "el => Boolean(el.closest('.pro-virtual-table__row, .pro-virtual-scroll__row'))"
                )
            )
        except Exception:
            return False

    async def _perform_claim_button_fallbacks(self, page: Page) -> None:
        """Execute lightweight fallbacks to surface the claim button."""

        with suppress(Exception):
            fallback_locator = page.locator("#jx-id-1917-80")
            if await fallback_locator.count():
                button = fallback_locator.first
                await button.hover()
                await button.click(force=True)

        with suppress(Exception):
            await page.evaluate("window.scrollTo(0, 0)")

        with suppress(Exception):
            await page.keyboard.press("Home")
        await self._wait_for_idle(page, timeout_ms=150)

    async def _ensure_claim_button_visible(
        self,
        page: Page,
        *,
        timeout: int = 2_500,
    ) -> Locator | None:
        """Ensure the claim dropdown button is visible and return its locator."""

        deadline = time.monotonic() + (timeout / 1_000)
        reported_frames = False

        while time.monotonic() < deadline:
            frames = page.frames

            if not reported_frames:
                frame_info = [{"name": frame.name, "url": frame.url} for frame in frames]
                logger.warning(f"认领页面 Frame 列表: {frame_info}")
                reported_frames = True

            scopes = self._collect_operation_scopes(page)

            priority_hit = await self._find_clickable_in_scopes(
                self._CLAIM_PRIORITY_SELECTORS,
                scopes,
            )
            if priority_hit is not None:
                selector_label, locator = priority_hit
                logger.debug(f"认领按钮定位成功: selector={selector_label}")
                return locator

            fallback_hit = await self._find_clickable_in_scopes(
                self._CLAIM_FALLBACK_SELECTORS,
                scopes,
            )
            if fallback_hit is not None:
                selector_label, locator = fallback_hit
                logger.debug(f"认领按钮定位成功: selector={selector_label}")
                return locator

            await self._perform_claim_button_fallbacks(page)

        try:
            snapshot = await page.locator("button").all_inner_texts()
            logger.warning(f"页面按钮文案快照: {snapshot[:30]}")
        except Exception as exc:
            logger.warning(f"无法获取页面按钮文案快照: {exc}")

        try:
            node_snap = await page.locator("text=认领到").evaluate_all(
                """els => els.slice(0, 5).map(el => ({
                    tag: el.tagName,
                    className: el.className,
                    role: el.getAttribute('role'),
                    parentTag: el.parentElement ? el.parentElement.tagName : null,
                    parentClass: el.parentElement ? el.parentElement.className : null,
                    closestButtonTag: (() => {
                        const target = el.closest('button, [role="button"], .jx-button, .pro-button, .el-button');
                        return target ? target.tagName : null;
                    })(),
                    closestButtonClass: (() => {
                        const target = el.closest('button, [role="button"], .jx-button, .pro-button, .el-button');
                        return target ? target.className : null;
                    })(),
                    html: el.outerHTML.slice(0, 200)
                }))"""
            )
            logger.warning(f"认领到节点快照: {node_snap}")
        except Exception as exc:
            logger.warning(f"无法获取认领到节点快照: {exc}")

        logger.error("认领按钮未在预期时间内变为可见")
        return None

    async def _click_claim_confirmation_button(self, page: Page) -> bool:
        """Attempt to click the visible confirmation button after the claim dialog appears.

        Args:
            page: Active Playwright page instance.

        Returns:
            True if a visible confirmation button was clicked successfully, otherwise False.
        """

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=1_500)
        except Exception as exc:
            logger.debug(f"等待认领确认弹窗 DOMContentLoaded 超时或失败，继续执行: {exc}")

        confirm_keywords: tuple[str, ...] = (
            "确定",
            "确认",
            "确认认领",
            "认领",
            "提交",
            "保存",
            "保存修改",
            "继续",
        )
        negative_keywords: tuple[str, ...] = (
            "取消",
            "关闭",
            "放弃",
            "返回",
            "否",
            "不上架",
        )

        raw_selectors = (
            ".el-message-box__btns button.el-button--primary",
            ".el-dialog__footer button.el-button--primary",
            ".jx-dialog__footer button.jx-button--primary",
            ".el-popconfirm__action button.el-button--primary",
            ".el-dialog__footer button",
            ".jx-dialog__footer button",
            ".el-message-box__btns button",
            ".el-popconfirm__action button",
            "button:has-text('确认认领')",
            "button:has-text('认领')",
            "button:has-text('确定')",
            "button:has-text('确认')",
            "button:has-text('提交')",
            "button:has-text('保存修改')",
            "button:has-text('保存')",
            "[role='button']:has-text('确认认领')",
            "[role='button']:has-text('认领')",
            "[role='button']:has-text('确定')",
            "[role='button']:has-text('确认')",
            "[role='button']:has-text('提交')",
            "[role='button']:has-text('保存修改')",
            "[role='button']:has-text('保存')",
            "button",
        )
        candidate_selectors = tuple(dict.fromkeys(raw_selectors))

        candidate_scopes: list[tuple[str, Any]] = [("page", page)]
        for frame_idx, frame in enumerate(page.frames):
            scope_label = f"frame[{frame_idx}]::{frame.url}"
            candidate_scopes.append((scope_label, frame))

        wrapper_selector = (
            ".el-dialog__wrapper, "
            ".el-message-box__wrapper, "
            ".jx-dialog__wrapper, "
            ".el-popconfirm, "
            "[role='dialog'], "
            "[role='alertdialog']"
        )
        wrappers = page.locator(wrapper_selector)
        try:
            wrapper_count = await wrappers.count()
        except Exception as exc:
            logger.debug(f"统计确认弹窗 wrapper 失败: {exc}")
            wrapper_count = 0

        for wrapper_idx in range(wrapper_count):
            wrapper = wrappers.nth(wrapper_idx)
            try:
                if await wrapper.is_visible():
                    candidate_scopes.append((f"wrapper[{wrapper_idx}]", wrapper))
            except Exception as exc:
                logger.debug(
                    "确认弹窗 wrapper[%s] 可见性检查失败: %s",
                    wrapper_idx,
                    exc,
                )

        for scope_name, scope in candidate_scopes:
            scope_candidates: list[tuple[str, Locator]] = []

            if hasattr(scope, "get_by_role"):
                with suppress(Exception):
                    exact_confirm = scope.get_by_role("button", name="确定", exact=True)
                    scope_candidates.append(
                        ("role=button(name='确定', exact=True)", exact_confirm)
                    )
                with suppress(Exception):
                    fuzzy_confirm = scope.get_by_role("button", name="确定", exact=False)
                    scope_candidates.append(
                        ("role=button(name~='确定')", fuzzy_confirm)
                    )
                with suppress(Exception):
                    confirm_trimmed = scope.locator("button").filter(
                        has_text=re.compile(r"\s*确定\s*")
                    )
                    scope_candidates.append(
                        ("button:trimmed-text='确定'", confirm_trimmed)
                    )

            for selector in candidate_selectors:
                scope_candidates.append((selector, scope.locator(selector)))

            if hasattr(scope, "get_by_role"):
                for keyword in confirm_keywords:
                    with suppress(Exception):
                        scope_candidates.append(
                            (
                                f"role=button(name~='{keyword}')",
                                scope.get_by_role("button", name=keyword, exact=False),
                            )
                        )

            for selector, buttons in scope_candidates:
                try:
                    count = await buttons.count()
                except Exception as exc:
                    logger.debug(
                        "确认弹窗候选按钮定位异常: scope=%s selector=%s error=%s",
                        scope_name,
                        selector,
                        exc,
                    )
                    continue

                if count == 0:
                    continue

                logger.debug(
                    "确认弹窗候选按钮: scope=%s selector=%s count=%s",
                    scope_name,
                    selector,
                    count,
                )

                for idx in range(count):
                    button = buttons.nth(idx)
                    try:
                        text = (await button.inner_text()).strip()
                    except Exception:
                        text = ""

                    if text and any(word in text for word in negative_keywords):
                        continue
                    if text and not any(word in text for word in confirm_keywords):
                        continue

                    try:
                        await button.scroll_into_view_if_needed()
                    except Exception:
                        pass

                    try:
                        if not await button.is_enabled():
                            logger.debug(
                                "确认弹窗按钮不可用: scope=%s selector=%s index=%s text=%s",
                                scope_name,
                                selector,
                                idx,
                                text,
                            )
                            continue
                    except Exception as exc:
                        logger.debug(
                            "确认弹窗按钮可用性检查失败: scope=%s selector=%s index=%s error=%s",
                            scope_name,
                            selector,
                            idx,
                            exc,
                        )

                    try:
                        await button.click(force=True)
                        logger.debug(
                            "认领确认按钮通过 %s (scope=%s index=%s text=%s) 点击成功",
                            selector,
                            scope_name,
                            idx,
                            text,
                        )
                        return True
                    except Exception as exc:
                        logger.debug(
                            "点击确认按钮失败: scope=%s selector=%s index=%s text=%s error=%s",
                            scope_name,
                            selector,
                            idx,
                            text,
                            exc,
                        )

        try:
            snapshot = await page.locator(
                ".el-message-box button, .el-dialog button, .jx-dialog button, .el-popconfirm button"
            ).all_inner_texts()
            logger.warning(f"确认弹窗按钮快照: {snapshot}")
            dialog_html = await wrappers.filter(has=page.locator("button")).first.inner_html()
            logger.debug(f"确认弹窗HTML: {dialog_html[:800]}")
        except Exception:
            pass

        logger.error("未能定位到可点击的认领确认按钮")
        return False

    async def claim_selected_products_to_temu(
        self,
        page: Page,
        repeat: int = 4,
    ) -> bool:
        """Execute the simplified Temu claim flow recorded via hover/click actions."""

        logger.info(f"执行简化版认领流程, 重复 {repeat} 次")

        last_error: Exception | None = None
        success_count = 0
        temu_destination_selected = False
        for iteration in range(repeat):
            logger.debug(f"认领迭代 {iteration + 1}/{repeat}")
            try:
                await self._wait_for_claim_dialog_close(page)
                await self._dismiss_known_popup_if_any(page)

                claim_button = await self._ensure_claim_button_visible(page)
                if claim_button is None:
                    raise RuntimeError("未能定位到'认领到'按钮")

                await claim_button.hover()
                await self._wait_for_idle(page, timeout_ms=150)
                with suppress(Exception):
                    fallback_claim_button = page.locator("#jx-id-1917-80")
                    if await fallback_claim_button.count():
                        await fallback_claim_button.first.hover()
                        await self._wait_for_idle(page, timeout_ms=150)
                        await fallback_claim_button.first.click(force=True)
                        await self._wait_for_claim_dropdown(page, state="visible", timeout=400)
                with suppress(Exception):
                    await claim_button.click(force=True)
                    await self._wait_for_claim_dropdown(page, state="visible", timeout=400)

                temu_option: Locator | None = None
                if not temu_destination_selected:
                    temu_option = await self._locate_temu_option_via_label(page)
                    if temu_option is None:
                        for attempt in range(3):
                            temu_option = await self._locate_dropdown_option(
                                page,
                                texts=("Temu全托管", "Temu 全托管", "Temu托管"),
                            )
                            if temu_option is not None:
                                break

                            for dropdown_text in ("Temu全托管", "Temu 全托管", "Temu托管"):
                                with suppress(Exception):
                                    spans_locator = page.locator("span").filter(has_text=dropdown_text)
                                    if await spans_locator.count():
                                        temu_option = spans_locator.first
                                        logger.debug(
                                            "通过 span.filter(has_text='%s') 获取到 Temu 下拉项",
                                            dropdown_text,
                                        )
                                        break
                                for frame in page.frames:
                                    with suppress(Exception):
                                        frame_spans = frame.locator("span").filter(has_text=dropdown_text)
                                        if await frame_spans.count():
                                            temu_option = frame_spans.first
                                            logger.debug(
                                                "通过 frame span.filter(has_text='%s') 获取到 Temu 下拉项 (frame=%s)",
                                                dropdown_text,
                                                frame.url,
                                            )
                                            break
                                if temu_option is not None:
                                    break
                            if temu_option is not None:
                                break

                            logger.debug("未立即找到下拉菜单项，尝试第 {} 次点击按钮展开", attempt + 1)
                            await claim_button.click(force=True)
                            await self._wait_for_claim_dropdown(page, state="visible", timeout=300)

                    if temu_option is None:
                        raise RuntimeError("未找到'Temu全托管'菜单项")

                    await temu_option.click(force=True)
                    await self._wait_for_claim_dropdown(page, state="hidden", timeout=300)
                    temu_destination_selected = True
                else:
                    logger.debug("Temu全托管已在首次迭代选定，跳过下拉菜单点击")
                    await self._wait_for_idle(page, timeout_ms=150)

                if not await self._click_claim_confirmation_button(page):
                    raise RuntimeError("未能在认领弹窗中点击确认按钮")

                if not await self._dismiss_claim_progress_dialog(page):
                    raise RuntimeError("认领进度弹窗未能正常关闭")

                if not await self._wait_for_claim_dialog_close(page):
                    raise RuntimeError("批量认领弹窗未在预期时间内关闭")

                logger.debug(f"认领流程第 {iteration + 1} 次执行完成")
                success_count += 1
                await self._wait_for_table_refresh(page)
            except Exception as exc:
                last_error = exc
                logger.error(f"认领流程第 {iteration + 1} 次执行失败: {exc}")
                await self._wait_for_idle(page, timeout_ms=400)

        if success_count > 0:
            if success_count < repeat:
                logger.warning(
                    "认领流程已成功执行 %s/%s 次，仍有部分尝试失败",
                    success_count,
                    repeat,
                )
            else:
                logger.success("简化版认领流程执行完成")
            return True

        if last_error is None:
            logger.error(f"认领流程在连续 {repeat} 次尝试后仍未成功: 未知错误")
        else:
            logger.error(
                f"认领流程在连续 {repeat} 次尝试后仍未成功: {last_error}"
            )
        return False

    async def _dismiss_claim_progress_dialog(self, page: Page) -> bool:
        """Close the claim progress dialog when it appears.

        Args:
            page: Active Playwright page instance.

        Returns:
            True if the progress dialog is absent or successfully closed,
            otherwise False.
        """

        if not hasattr(page, "get_by_role"):
            return True

        dialog_selectors = [
            "xpath=//*[contains(@class,'el-dialog__wrapper')][.//text()[contains(., '批量认领')]]",
            "xpath=//*[contains(@class,'el-dialog')][.//text()[contains(., '批量认领')]]",
            "xpath=//*[@role='dialog'][.//text()[contains(., '批量认领')]]",
        ]

        progress_selector_groups = [
            {
                "container": ".el-dialog__wrapper",
                "progress": [".el-progress__text", ".el-progress-bar__outer"],
            },
            {
                "container": ".el-dialog",
                "progress": [".el-progress__text", ".el-progress-bar__outer"],
            },
            {
                "container": "[role='dialog']",
                "progress": [".el-progress__text", ".el-progress-bar__outer"],
            },
        ]

        async def _dialog_locator() -> Locator | None:
            for selector in dialog_selectors:
                with suppress(Exception):
                    locator = page.locator(selector)
                    total = await locator.count()
                if not total:
                    continue

                for idx in range(total):
                    candidate = locator.nth(idx)
                    try:
                        if await candidate.is_visible():
                            logger.debug(
                                "认领进度弹窗 wrapper 可见: selector=%s index=%s",
                                selector,
                                idx,
                            )
                            return candidate
                    except Exception:
                        continue
            return None

        async def _progress_completed() -> bool:
            for selector in progress_selectors:
                with suppress(Exception):
                    locator = page.locator(selector)
                    if await locator.count():
                        text = (await locator.first.inner_text()).strip()
                        if text.endswith("%"):
                            text = text.rstrip("%").strip()
                        if text == "100":
                            return True
            return False

        try:
            dialog = await _dialog_locator()
            if dialog is None:
                return True

            try:
                await dialog.wait_for(state="visible", timeout=1_200)
            except PlaywrightTimeoutError as exc:
                logger.debug(f"认领进度弹窗未在预期时间内可见: {exc}")

            progress_ready = False
            try:
                await page.wait_for_function(
                    """
                    ({ groups, keyword }) => {
                        for (const group of groups) {
                            const containers = document.querySelectorAll(group.container);
                            for (const container of containers) {
                                const text = (container.textContent || '').trim();
                                if (!text.includes(keyword)) {
                                    continue;
                                }
                                for (const selector of group.progress) {
                                    const nodes = container.querySelectorAll(selector);
                                    for (const node of nodes) {
                                        const raw = (node.innerText || node.textContent || '').trim();
                                        if (!raw) {
                                            continue;
                                        }
                                        const numeric = Number(raw.replace('%', '').trim());
                                        if (!Number.isNaN(numeric) && numeric >= 100) {
                                            return true;
                                        }
                                    }
                                }
                            }
                        }
                        return false;
                    }
                    """,
                    arg={"groups": progress_selector_groups, "keyword": "批量认领"},
                    timeout=300,
                )
                progress_ready = True
            except PlaywrightTimeoutError:
                logger.debug("认领进度条未在预期时间显示完成状态")

            logger.debug("认领进度条状态: completed={}", progress_ready)

            # 尝试关闭弹窗，最多重试3次
            max_retries = 3
            for attempt in range(max_retries):
                close_button: Locator | None = await self._locate_progress_close_button(dialog)
                if close_button is None:
                    close_button = await self._locate_progress_close_button(page)

                if close_button is None:
                    button_selector = (
                        ".el-dialog__headerbtn, .jx-dialog__headerbtn, "
                        "button:has-text('关闭'), button:has-text('完成'), button[aria-label*='关闭']"
                    )
                    with suppress(Exception):
                        await page.wait_for_selector(button_selector, state="visible", timeout=1_000)
                    close_button = await self._locate_progress_close_button(dialog)
                    if close_button is None:
                        close_button = await self._locate_progress_close_button(page)

                if close_button is None:
                    logger.debug(
                        "认领进度弹窗无法定位'关闭'按钮 progress_ready=%s attempt=%d/%d",
                        progress_ready,
                        attempt + 1,
                        max_retries,
                    )
                    if attempt < max_retries - 1:
                        continue
                    return False

                try:
                    await close_button.scroll_into_view_if_needed()
                except Exception:
                    pass
                try:
                    await close_button.hover()
                except Exception:
                    pass

                try:
                    await close_button.click(force=True)
                except Exception as exc:
                    logger.debug(f"点击认领进度弹窗关闭按钮失败 attempt={attempt + 1}/{max_retries}: {exc}")
                    if attempt < max_retries - 1:
                        continue
                    return False

                dialog_closed = False
                try:
                    await dialog.wait_for(state="hidden", timeout=1_200)
                    dialog_closed = True
                except PlaywrightTimeoutError:
                    logger.debug("认领进度弹窗未立即隐藏，尝试等待 DOM 移除")
                    with suppress(PlaywrightTimeoutError):
                        await dialog.wait_for(state="detached", timeout=1_000)
                        dialog_closed = True
                
                if dialog_closed:
                    logger.debug("认领进度弹窗关闭成功 attempt={}/{}", attempt + 1, max_retries)
                    return True
                
                logger.debug("认领进度弹窗关闭失败，准备重试 attempt={}/{}", attempt + 1, max_retries)
            
            logger.debug("认领进度弹窗关闭失败，已达最大重试次数")
            return False
        except PlaywrightTimeoutError as exc:
            logger.debug(f"等待认领进度弹窗关闭时超时: {exc}")
        except Exception as exc:
            logger.debug(f"关闭认领进度弹窗失败: {exc}")
        return False

    async def _wait_for_claim_dialog_close(
        self,
        page: Page,
        timeout: int = 2_000,
    ) -> bool:
        """Wait until the batch claim dialog is dismissed."""

        dialog_selectors = [
            ".el-dialog__wrapper",
            ".el-dialog",
            "[role='dialog']",
        ]

        try:
            await page.wait_for_function(
                """
                ({ selectors, keyword }) => {
                    let found = false;
                    for (const selector of selectors) {
                        const nodes = document.querySelectorAll(selector);
                        for (const node of nodes) {
                            const text = (node.textContent || '').trim();
                            if (!text.includes(keyword)) {
                                continue;
                            }
                            found = true;
                            const visible = !!(node.offsetParent);
                            if (visible) {
                                return false;
                            }
                        }
                    }
                    return true;
                }
                """,
                arg={"selectors": dialog_selectors, "keyword": "批量认领"},
                timeout=timeout,
            )
            return True
        except PlaywrightTimeoutError:
            logger.debug("批量认领弹窗未能在预期时间内消失")
        return False

    async def _is_progress_dialog_descendant(self, element: Locator) -> bool:
        """Determine whether ``element`` belongs to the batch claim progress dialog."""

        try:
            return bool(
                await element.evaluate(
                    """el => {
                        const container = el.closest('.el-dialog__wrapper, .el-dialog, [role="dialog"]');
                        if (!container) {
                            return false;
                        }
                        const text = container.textContent || '';
                        return text.includes('批量认领');
                    }"""
                )
            )
        except Exception:
            return False

    async def _locate_progress_close_button(
        self,
        scope: Locator | Page | Frame,
    ) -> Locator | None:
        """Locate the visible '关闭' button within ``scope`` that belongs to the progress dialog."""

        if hasattr(scope, "get_by_role"):
            for role_name in ("关闭此对话框", "关闭"):
                try:
                    role_locator = scope.get_by_role("button", name=role_name, exact=False)
                except Exception:
                    continue

                button = await self._pick_visible_progress_button(role_locator)
                if button is not None:
                    try:
                        acc_name = await button.get_attribute("aria-label")
                    except Exception:
                        acc_name = None
                    logger.debug(
                        "认领进度弹窗关闭按钮通过 role 定位成功: name=%s aria-label=%s",
                        role_name,
                        acc_name,
                    )
                    return button

        candidate_selectors = (
            "button:has-text('关闭')",
            "button:has-text('关 闭')",
            ".el-dialog__footer button.el-button:has-text('关闭')",
            ".jx-dialog__footer button.jx-button:has-text('关闭')",
            ".el-dialog__headerbtn",
            "[aria-label='关闭此对话框']",
            "[aria-label='关闭当前对话框']",
            "[aria-label='关闭']",
            "[title='关闭']",
            "[data-test='close']",
            "[data-testid='close']",
            "button[aria-label*='关闭']",
        )

        for selector in candidate_selectors:
            locator: Locator | None = None
            try:
                locator = scope.locator(selector)
            except Exception:
                continue

            button = await self._pick_visible_progress_button(locator)
            if button is None:
                continue

            logger.debug("认领进度弹窗关闭按钮定位成功: selector={}", selector)
            return button

        return None

    async def _pick_visible_progress_button(self, locator: Locator) -> Locator | None:
        """Return the first visible button belonging to the progress dialog."""

        try:
            count = await locator.count()
        except Exception:
            return None

        if count == 0:
            return None

        for idx in range(count):
            button = locator.nth(idx)
            try:
                await button.wait_for(state="attached", timeout=200)
            except Exception:
                continue

            try:
                await button.wait_for(state="visible", timeout=300)
            except PlaywrightTimeoutError:
                with suppress(Exception):
                    await button.scroll_into_view_if_needed()
                if not await self._is_progress_dialog_descendant(button):
                    continue
                if not await button.is_enabled():
                    continue
                if not await button.is_visible():
                    continue
            except Exception:
                continue

            try:
                is_descendant = await self._is_progress_dialog_descendant(button)
            except Exception as exc:
                logger.debug(f"判定关闭按钮归属弹窗失败: {exc}")
                is_descendant = False
            if not is_descendant:
                logger.debug("定位到关闭按钮但不属于批量认领弹窗，跳过")
                continue

            return button

        return None

    async def _dismiss_known_popup_if_any(self, page: Page) -> None:
        """Dismiss the '我知道了' popup if it appears between iterations."""

        popup_button = page.get_by_role("button", name="我知道了")
        try:
            await popup_button.click(timeout=200)
            await self._wait_for_message_box_dismissal(page)
            logger.debug("已关闭'我知道了'弹窗")
        except PlaywrightTimeoutError:
            return
        except Exception as exc:
            logger.debug(f"关闭'我知道了'弹窗时出现异常: {exc}")

    async def verify_claim_success(self, page: Page, expected_count: int = 20) -> bool:
        """Verify that claimed items meet the expected count.

        Args:
            page: Active Playwright page instance.
            expected_count: Minimum number of claimed items required by SOP.

        Returns:
            True when claimed item count meets or exceeds ``expected_count``.
        """
        logger.info(
            f"Verifying claim result, expecting at least {expected_count} items"
        )

        try:
            await self.switch_tab(page, "claimed")
            await self._wait_for_table_refresh(page)

            counts = await self.get_product_count(page)
            claimed_count = counts.get("claimed", 0)

            if claimed_count >= expected_count:
                logger.success(
                    f"Claim verification succeeded: claimed={claimed_count} "
                    f"expected>={expected_count}"
                )
                return True

            logger.error(
                f"Claim verification failed: claimed={claimed_count} "
                f"expected>={expected_count}"
            )
            return False
        except Exception as exc:
            logger.error(f"Claim verification raised an error: {exc}")
            return False

    async def navigate_and_filter_collection_box(
        self,
        page: Page,
        filter_by_user: str | None = None,
        switch_to_tab: str = "all",
    ) -> bool:
        """Navigate to the collection box and apply optional filters.

        Args:
            page: Active Playwright page instance.
            filter_by_user: Optional user filter applied to the grid.
            switch_to_tab: Tab name to activate after navigation.

        Returns:
            True when the navigation workflow completed successfully, otherwise False.
        """
        logger.info("Starting full navigation workflow for collection box")

        try:
            logger.info("Step 1: navigate to shared collection box")
            if not await self.navigate_to_collection_box(page):
                logger.error("Navigation to collection box failed")
                return False
            logger.success("Navigation step completed")
            await self._wait_for_table_refresh(page)
            await self._ensure_popups_closed(page)

            if filter_by_user:
                logger.info(f"Step 2: apply user filter {filter_by_user}")
                user_filter_selectors = [
                    "input[placeholder*='创建人']",
                    "input[placeholder*='创建人员']",
                    "input[placeholder*='请输入创建']",
                    "label:has-text('创建人员') + .jx-select input",
                    "xpath=//label[contains(text(), '创建人员')]/following-sibling::*//input",
                    ".jx-select:has-text('创建人员') input",
                ]

                filter_applied = False
                for selector in user_filter_selectors:
                    try:
                        element = page.locator(selector).first
                        if await element.count() == 0:
                            continue

                        await element.click()
                        await element.fill("")
                        await element.type(filter_by_user, delay=80)
                        await self._wait_for_select_dropdown(page, state="visible")

                        option_locator = page.locator(
                            "li.el-select-dropdown__item",
                            has_text=filter_by_user,
                        )

                        if await option_locator.count():
                            await option_locator.first.click()
                            await self._wait_for_select_dropdown(page, state="hidden")

                            search_btn = page.locator("button:has-text('搜索')").first
                            if await search_btn.count():
                                await search_btn.click()
                                await self._wait_for_table_refresh(page)

                            filter_applied = True
                            logger.success(f"User filter applied: {filter_by_user}")
                            break
                    except Exception as exc:
                        logger.debug(f"User filter selector {selector} failed: {exc}")
                        continue

                if not filter_applied:
                    logger.warning("User filter could not be applied via selectors, trying fallback")
                    filter_applied = await fallback_apply_user_filter(page, filter_by_user)
                    if not filter_applied:
                        logger.warning("Fallback user filter also failed, continuing without filter")
            else:
                logger.info("Step 2: skip user filter")

            logger.info(f"Step 3: switch to tab {switch_to_tab}")
            await self._wait_for_table_refresh(page)
            
            # 等待可能的tab容器出现
            try:
                await page.wait_for_selector(
                    "button, [role='tab'], .jx-radio-button, .jx-tabs__item",
                    state="visible",
                    timeout=1_500
                )
                logger.debug("Tab elements detected on page")
            except Exception as e:
                logger.warning(f"Tab element wait timed out: {e}, continuing anyway...")
            
            if not await self.switch_tab(page, switch_to_tab):
                logger.error("Tab switch failed, attempting fallback")
                if not await fallback_switch_tab(page, switch_to_tab):
                    logger.error("Fallback tab switch failed")
                    return False
            logger.success("Tab switch complete")
            await self._wait_for_table_refresh(page)

            logger.info("Step 4: check product list")
            counts = await self.get_product_count(page)
            if counts[switch_to_tab] > 0:
                logger.success(
                    f"Product list ready: {counts[switch_to_tab]} items in tab {switch_to_tab}"
                )
            else:
                logger.warning(f"No items found in tab {switch_to_tab}")

            logger.info("Collection box navigation workflow completed")
            return True
        except Exception as exc:
            logger.error(f"Collection box workflow failed: {exc}")
            logger.exception("Detailed error")
            return False

    async def verify_collected_products(
        self,
        page: Page,
        expected_count: int,
        product_keywords: list[str] | None = None,
        check_details: bool = False,
    ) -> dict[str, Any]:
        """Verify collected products against expected count and optional keywords.

        Args:
            page: Active Playwright page instance.
            expected_count: Minimum acceptable product count.
            product_keywords: Optional keywords that should appear in product titles.
            check_details: Whether to inspect product detail rows for missing content.

        Returns:
            A dictionary describing verification results and detected issues.
        """
        logger.info(
            "Verifying collected products, "
            f"expected count={expected_count}, keywords={product_keywords}, "
            f"check_details={check_details}"
        )

        result: dict[str, Any] = {
            "success": False,
            "actual_count": 0,
            "missing_keywords": [],
            "detail_issues": [],
        }

        try:
            counts = await self.get_product_count(page)
            result["actual_count"] = counts.get("all", 0)

            if result["actual_count"] < expected_count:
                logger.warning(
                    "Collected products below expectation. "
                    f"actual={result['actual_count']} expected={expected_count}"
                )

            if product_keywords:
                logger.debug("Checking product titles for keywords")
                title_locator = page.locator(
                    ".pro-virtual-scroll__row .pro-virtual-table__cell--title",
                )
                titles = []
                total = await title_locator.count()
                for idx in range(total):
                    with suppress(Exception):
                        text = (await title_locator.nth(idx).inner_text()).strip()
                        if text:
                            titles.append(text)

                missing = []
                for keyword in product_keywords:
                    if not any(keyword in title for title in titles):
                        missing.append(keyword)

                result["missing_keywords"] = missing
                if missing:
                    logger.warning(f"Missing keywords in titles: {missing}")

            if check_details:
                logger.debug("Detail verification requested, iterating products...")
                detail_locator = page.locator(".pro-virtual-table__row")
                total_rows = await detail_locator.count()
                issues: list[str] = []

                for idx in range(total_rows):
                    row = detail_locator.nth(idx)
                    with suppress(Exception):
                        detail_text = (await row.inner_text()).strip()
                        if not detail_text:
                            issues.append(f"Row {idx + 1} has empty detail text")

                result["detail_issues"] = issues
                if issues:
                    logger.warning(f"Detail issues detected: {issues}")

            result["success"] = (
                result["actual_count"] >= expected_count
                and not result["missing_keywords"]
                and not result["detail_issues"]
            )

            logger.info(f"Collected product verification complete: {result}")
            return result
        except Exception as exc:
            logger.error(f"Failed to verify collected products: {exc}")
            result["error"] = str(exc)
            return result

    async def _locate_dropdown_option(
        self,
        page: Page,
        *,
        texts: tuple[str, ...],
        timeout: int = 1_500,
    ) -> Locator | None:
        """Locate a visible dropdown option matching any given text."""

        deadline = time.monotonic() + (timeout / 1_000)

        while time.monotonic() < deadline:
            frames = page.frames
            candidate_locators: list[tuple[str, Locator]] = []

            for text in texts:
                selectors = [
                    f".el-dropdown-menu__item:has-text('{text}')",
                    f".jx-dropdown-menu__item:has-text('{text}')",
                    f".pro-dropdown__item:has-text('{text}')",
                    f"span:has-text('{text}')",
                    f".el-dropdown-menu__item span:has-text('{text}')",
                    f".jx-dropdown-menu__item span:has-text('{text}')",
                    f"xpath=//span[contains(normalize-space(), '{text}')]",
                    f"text={text}",
                ]

                for selector in selectors:
                    candidate_locators.append((selector, page.locator(selector)))
                    for frame in frames:
                        frame_name = frame.name or "unnamed"
                        candidate_locators.append(
                            (f"{selector} [frame={frame_name}]", frame.locator(selector))
                        )

                candidate_locators.append(
                    (f"span.filter(has_text='{text}')", page.locator("span").filter(has_text=text))
                )
                for frame in frames:
                    frame_name = frame.name or "unnamed"
                    candidate_locators.append(
                        (
                            f"span.filter(has_text='{text}') [frame={frame_name}]",
                            frame.locator("span").filter(has_text=text),
                        )
                    )

            for selector, locator in candidate_locators:
                try:
                    count = await locator.count()
                except Exception:
                    continue
                if count == 0:
                    continue

                for idx in range(count):
                    target = locator.nth(idx)
                    try:
                        await target.wait_for(state="attached", timeout=150)
                        await target.wait_for(state="visible", timeout=150)
                        logger.debug(
                            "找到下拉菜单项: selector=%s, index=%s, text=%s",
                            selector,
                            idx,
                            await target.inner_text(),
                        )
                        return target
                    except Exception:
                        continue

            await self._wait_for_idle(page, timeout_ms=200)

        try:
            snapshot = await page.locator(".el-dropdown-menu__item").all_inner_texts()
            logger.warning(f"下拉菜单项快照: {snapshot[:20]}")
        except Exception:
            pass

        logger.error("未找到目标下拉菜单项: {}", texts)
        return None

    async def _locate_temu_option_via_label(self, page: Page) -> Locator | None:
        """Attempt to locate the Temu option via the '认领到' label dropdown."""

        if not hasattr(page, "get_by_label"):
            return None

        label_patterns = (
            re.compile(r"Temu\s*全托管", re.IGNORECASE),
            re.compile(r"Temu托管", re.IGNORECASE),
        )

        try:
            dropdown = page.get_by_label("认领到")
        except Exception as exc:
            logger.debug(f"通过 label('认领到') 获取下拉入口失败: {exc}")
            return None

        try:
            span_locator = dropdown.locator("span")
            for pattern in label_patterns:
                candidate = span_locator.filter(has_text=pattern)
                if await candidate.count():
                    logger.debug(
                        "通过 get_by_label('认领到') 定位到 Temu 选项: pattern=%s",
                        pattern.pattern,
                    )
                    return candidate.first
        except Exception as exc:
            logger.debug(f"通过 label 定位 Temu 选项失败: {exc}")

        return None
