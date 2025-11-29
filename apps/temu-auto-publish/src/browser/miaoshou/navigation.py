"""
@PURPOSE: Navigation and product selection helpers for the Miaoshou controller.
@OUTLINE:
  - class MiaoshouNavigationMixin: navigation, filtering, selection utilities
"""

from __future__ import annotations

import re
from contextlib import suppress
from typing import Any, ClassVar

from loguru import logger
from playwright.async_api import Frame, Page

from ...utils.page_load_decorator import (
    PAGE_TIMEOUTS,
    wait_dom_loaded,
    wait_network_idle,
)
from .base import MiaoshouControllerBase
from .navigation_codegen import fallback_apply_user_filter, fallback_switch_tab


class MiaoshouNavigationMixin(MiaoshouControllerBase):
    """Provide navigation, filtering and product selection helpers."""

    _TAB_LABEL_VARIANTS: ClassVar[dict[str, tuple[str, ...]]] = {
        "all": ("全部", "All", "ALL"),
        "unclaimed": ("未认领", "Unclaimed"),
        "claimed": ("已认领", "Claimed"),
        "failed": ("失败", "Failed"),
    }
    _DEFAULT_EDIT_BUTTON_SELECTORS: ClassVar[tuple[str, ...]] = (
        ".jx-button.jx-button--primary.jx-button--small.is-text.pro-button.J_collectBoxEdit",
        ".jx-button.jx-button--primary.jx-button--small.is-text.pro-button.J_commonCollectBoxEdit",
        "button:has-text('编辑')",
        "button:has-text('首次编辑')",
        "a:has-text('首次编辑')",
        "a:has-text('编辑')",
        "span:has-text('首次编辑')",
        "text='首次编辑'",
        "text='编辑'",
    )
    # 商品行选择器（用于基于行定位编辑按钮）
    _ROW_SELECTOR: ClassVar[str] = ".pro-virtual-table__row-body"
    # vue-recycle-scroller 虚拟滚动行选择器（包含 transform 信息）
    _VIRTUAL_ROW_SELECTOR: ClassVar[str] = ".vue-recycle-scroller__item-view"
    # 商品行高度（像素）
    _ROW_HEIGHT: ClassVar[int] = 128

    async def navigate_to_collection_box(self, page: Page, use_sidebar: bool = False) -> bool:
        """Navigate to the shared collection box page.

        Args:
            page: Active Playwright page instance.
            use_sidebar: Whether to navigate through the sidebar menu.

        Returns:
            True when navigation succeeds, otherwise False.
        """
        logger.info("Navigating to shared collection box...")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            target_url = collection_box_config.get(
                "url",
                "https://erp.91miaoshou.com/common_collect_box/items",
            )

            if use_sidebar:
                sidebar_config = self.selectors.get("sidebar_menu", {})
                collection_box_selector = sidebar_config.get(
                    "common_collection_box",
                    "menuitem:has-text('公用采集箱')",
                )

                logger.debug("Clicking sidebar entry for shared collection box...")
                await page.locator(collection_box_selector).click()
                # 激进优化: 5s -> 2s
                await wait_dom_loaded(page, 2_000, context=" [sidebar click]")
                with suppress(Exception):
                    # 激进优化: 15s -> 5s
                    await page.wait_for_url(re.compile("common_collect_box"), timeout=5_000)
            else:
                logger.debug(f"Direct navigation to: {target_url}")
                try:
                    # 激进优化: 30s -> 15s
                    await page.goto(target_url, timeout=15_000)
                except Exception as exc:
                    logger.warning(
                        "Direct navigation failed (%s), retrying via sidebar", exc
                    )
                    return await self.navigate_to_collection_box(page, use_sidebar=True)

            # 激进优化: 5s -> 2s
            await wait_dom_loaded(page, 2_000, context=" [navigation complete]")

            if "common_collect_box/items" in page.url:
                logger.success("Navigation to shared collection box succeeded")
                logger.debug("Waiting for page to settle...")
                
                # 激进优化: 合并两个等待，总超时 3s
                try:
                    logger.debug("Waiting for main content and interactive elements...")
                    await page.wait_for_selector(
                        ".jx-main, .pro-layout-content, button, [role='tab'], .jx-button",
                        state="visible",
                        timeout=3_000
                    )
                    logger.debug("Page elements loaded")
                except Exception as e:
                    logger.warning(f"Content wait timed out: {e}")
                    # 激进优化: 移除 networkidle 等待，直接继续
                
                await self._ensure_popups_closed(page)

                return True

            if not use_sidebar:
                logger.warning("Unexpected URL {}, retrying via sidebar navigation", page.url)
                return await self.navigate_to_collection_box(page, use_sidebar=True)

            logger.error("Navigation failed: unexpected URL {}", page.url)
            return False
        except Exception as exc:
            logger.error(f"Failed to navigate to collection box: {exc}")
            return False

    async def filter_and_search(self, page: Page, staff_name: str | None = None) -> bool:
        """Filter by staff member and trigger a search.

        Args:
            page: Active Playwright page instance.
            staff_name: Name of the staff member to filter by. Uses all records when ``None``.

        Returns:
            True when the filter and search were executed, otherwise False.
        """
        logger.info("Filtering and searching by staff: {}", staff_name or "(all)")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            search_box_config = collection_box_config.get("search_box", {})

            if staff_name:
                logger.debug("Selecting staff member: {}", staff_name)
                all_selects = page.locator(".jx-select, .el-select, .ant-select, .pro-select")
                select_count = await all_selects.count()
                logger.debug("Located {} select elements", select_count)

                primary_filter_ok = False
                if select_count >= 2:
                    staff_select = all_selects.nth(1)
                    logger.debug("Opening staff selector...")
                    await staff_select.click()
                    dropdown_locator = page.locator(
                        ".jx-select-dropdown, .jx-popper, [role='listbox'], .el-select-dropdown, .ant-select-dropdown"
                    )
                    with suppress(Exception):
                        await dropdown_locator.first.wait_for(state="visible", timeout=1_500)
                    dropdown_count = await dropdown_locator.count()

                    if dropdown_count == 0:
                        logger.warning("Dropdown for staff selection did not appear")
                    else:
                        logger.success("Staff dropdown displayed")

                        staff_option_selectors = [
                            f"li:has-text('{staff_name}')",
                            f".jx-select-dropdown__item:has-text('{staff_name}')",
                            f".el-select-dropdown__item:has-text('{staff_name}')",
                            f".ant-select-dropdown-menu-item:has-text('{staff_name}')",
                            f".jx-option:has-text('{staff_name}')",
                            f"[role='option']:has-text('{staff_name}')",
                            f"div:has-text('{staff_name}')",
                        ]

                        staff_option_clicked = False
                        for selector in staff_option_selectors:
                            try:
                                elements = await page.locator(selector).all()
                                if len(elements) > 0:
                                    logger.debug(
                                        "Found %s options for %s via %s",
                                        len(elements),
                                        staff_name,
                                        selector,
                                    )
                                    await elements[0].click()
                                    with suppress(Exception):
                                        await dropdown_locator.first.wait_for(state="hidden", timeout=1_500)
                                    staff_option_clicked = True
                                    logger.success("Staff member selected: {}", staff_name)
                                    break
                            except Exception as err:  # pragma: no cover - UI variance
                                logger.debug("Selector {} failed: {}", selector, err)
                                continue

                        if not staff_option_clicked:
                            logger.warning("Could not locate staff option: {}", staff_name)
                        else:
                            primary_filter_ok = True
                else:
                    logger.warning(
                        "Expected at least 2 select widgets for staff filter, got %s",
                        select_count,
                    )

                if not primary_filter_ok:
                    logger.warning(
                        "Primary staff filter strategy failed, trying fallback recorded selectors",
                    )
                    fallback_ok = await fallback_apply_user_filter(page, staff_name)
                    if fallback_ok:
                        logger.success("Fallback user filter completed (includes search)")
                        return True
                    logger.warning(
                        "Fallback recorded user filter also failed, proceeding without staff filter",
                    )

            logger.debug("Clicking search button...")
            search_btn_selector = search_box_config.get("search_btn", "button:has-text('搜索')")
            search_btn = page.locator(search_btn_selector).first
            if await search_btn.count() == 0:
                logger.warning("Search button not found with selector {}, skipping explicit search", search_btn_selector)
            else:
                await search_btn.click()
            await self._wait_for_table_refresh(page)

            logger.success("Filtering and search finished")
            return True
        except Exception as exc:
            logger.error(f"Filter/search failed: {exc}")
            return False

    def _collect_popup_scopes(self, page: Page) -> list[tuple[str, Page | Frame]]:
        """Collect the main page and child frames for popup detection."""

        scopes: list[tuple[str, Page | Frame]] = [("page", page)]
        try:
            for idx, frame in enumerate(page.frames):
                label = frame.name or frame.url or f"frame-{idx}"
                scopes.append((f"frame[{idx}]::{label}", frame))
        except Exception as exc:
            logger.debug(f"Enumerating popup scopes failed: {exc}")

        return scopes

    async def close_popup_if_exists(self, page: Page) -> bool:
        """Close known popups if they are currently visible.

        Args:
            page: Active Playwright page instance.

        Returns:
            True when a popup was closed, otherwise False.
        """
        try:
            popup_buttons = [
                "text='我知道了'",
                "text='知道了'",
                "text='确定'",
                "text='关闭'",
                "text='我已知晓'",
                "button:has-text('我已知晓')",
                "button[aria-label='关闭']",
                "button[aria-label='Close']",
            ]
            overlay_selector = ".jx-overlay-dialog, .el-dialog, [role='dialog']"
            header_close_selectors = [
                ".jx-dialog__headerbtn",
                ".el-dialog__headerbtn",
            ]
            scopes = self._collect_popup_scopes(page)

            for selector in popup_buttons:
                for scope_name, scope in scopes:
                    try:
                        locator = scope.locator(selector)
                        count = await locator.count()
                    except Exception as exc:
                        logger.debug("Popup selector {} failed in {}: {}", selector, scope_name, exc)
                        continue

                    if not count:
                        continue

                    try:
                        await locator.first.click(timeout=2_000)
                    except Exception as exc:
                        logger.debug("Click selector {} failed in {}: {}", selector, scope_name, exc)
                        continue

                    await self._wait_for_message_box_dismissal(page)
                    logger.success("Popup closed via button: {} ({})", selector, scope_name)
                    return True

            for scope_name, scope in scopes:
                try:
                    dialogs = scope.locator(overlay_selector)
                    dialog_count = await dialogs.count()
                except Exception as exc:
                    logger.debug("Enumerating dialogs failed in {}: {}", scope_name, exc)
                    continue

                if not dialog_count:
                    continue

                for index in range(dialog_count - 1, -1, -1):
                    dialog = dialogs.nth(index)
                    for selector in header_close_selectors:
                        try:
                            btn = dialog.locator(selector)
                            if await btn.count() and await btn.first.is_visible(timeout=1_000):
                                logger.debug(
                                    "Clicking dialog header close: %s (idx=%s, scope=%s)",
                                    selector,
                                    index,
                                    scope_name,
                                )
                                await btn.first.click()
                                await self._wait_for_message_box_dismissal(page)
                                logger.success("Popup closed via header button ({})", scope_name)
                                return True
                        except Exception as exc:
                            logger.debug("Header close failed ({}, scope={}): {}", selector, scope_name, exc)

            # 针对 .jx-overlay-message-box（如“提示”“知道了”）的兜底处理
            for scope_name, scope in scopes:
                try:
                    message_box = scope.locator(".jx-overlay-message-box:visible, .el-message-box:visible")
                    msg_count = await message_box.count()
                except Exception as exc:
                    logger.debug("Message box lookup failed in {}: {}", scope_name, exc)
                    continue

                if not msg_count:
                    continue

                logger.debug("Found overlay message box: count={}, scope={}", msg_count, scope_name)
                close_candidates = [
                    ".jx-overlay-message-box button.jx-message-box__headerbtn",
                    ".jx-overlay-message-box button:has-text('确定')",
                    ".jx-overlay-message-box button:has-text('知道了')",
                    ".jx-overlay-message-box button:has-text('关闭')",
                    ".jx-overlay-message-box button[aria-label*='关闭']",
                    ".el-message-box button:has-text('我已知晓')",
                    ".el-message-box button:has-text('确定')",
                ]
                for selector in close_candidates:
                    try:
                        btn = scope.locator(selector).first
                        if await btn.count() and await btn.is_visible(timeout=500):
                            await btn.click(timeout=1_000)
                            await self._wait_for_message_box_dismissal(page)
                            logger.success("Overlay message box closed via {} ({})", selector, scope_name)
                            return True
                    except Exception as exc:
                        logger.debug("Closing overlay via {} failed in {}: {}", selector, scope_name, exc)
                        continue
                with suppress(Exception):
                    await page.keyboard.press("Escape")
                    await self._wait_for_message_box_dismissal(page)
                    logger.success("Overlay message box dismissed via Escape ({})", scope_name)
                    return True

            logger.debug("No popup detected for closure")
            return False
        except Exception as exc:
            logger.warning(f"Popup closure encountered an error (ignored): {exc}")
            return False

    async def _ensure_popups_closed(self, page: Page, attempts: int = 4) -> None:
        """Best-effort dismissal of blocking popups（例如“我知道了”提示）."""

        for attempt in range(attempts):
            closed = await self.close_popup_if_exists(page)
            if not closed:
                if attempt == 0:
                    logger.debug("No blocking popup detected")
                break
            await self._wait_for_message_box_dismissal(page)

    async def _wait_for_message_box_dismissal(self, page: Page, timeout: int = 1_500) -> None:
        """Wait until transient message boxes are hidden."""
        selector = ".jx-overlay-message-box, .jx-message-box, .el-message-box"
        for _, scope in self._collect_popup_scopes(page):
            try:
                locator = scope.locator(selector)
                await locator.first.wait_for(state="hidden", timeout=timeout)
            except Exception:
                continue

    async def _wait_for_bulk_selection(self, page: Page, timeout: int = 800) -> None:
        """Wait for any checkbox to reflect the 'selected' state. 激进优化: 2000 -> 800"""
        selection_locator = page.locator(
            ".jx-checkbox.is-checked, .el-checkbox.is-checked, .ant-checkbox-checked"
        )
        try:
            await selection_locator.first.wait_for(state="visible", timeout=timeout)
        except Exception:
            pass

    async def _wait_for_table_refresh(self, page: Page, timeout: int = 2_000) -> None:
        """Wait for the product table to update. 激进优化: 5000 -> 2000, 移除 networkidle"""
        table_locator = page.locator(
            ".pro-virtual-table, .vue-recycle-scroller, .jx-table, .pro-table"
        )
        with suppress(Exception):
            await table_locator.first.wait_for(state="visible", timeout=timeout)
        # 激进优化: 移除 networkidle 等待

    async def _wait_for_idle(self, page: Page, timeout_ms: int = 100) -> None:
        """Best-effort wait for the page to reach a steady state. 激进优化: 300 -> 100"""
        await wait_network_idle(page, timeout_ms, context=" [idle wait]")

    async def get_product_count(self, page: Page) -> dict[str, int]:
        """Retrieve product counts for the different tabs.

        Args:
            page: Active Playwright page instance.

        Returns:
            A mapping from tab identifier to product count.
        """
        logger.debug("Fetching product counts from tab bar")

        try:
            tab_config = self.selectors.get("collection_box", {}).get("tabs", {})
            tab_selectors = self._resolve_selectors(
                tab_config,
                keys=["all", "unclaimed", "claimed", "failed"],
                default=[
                    ".jx-tabs__header .jx-tabs__item",
                    ".jx-tab-bar__item",
                    ".pro-tabs__item",
                    "[role='tab']",
                ],
            )

            counts = {"all": 0, "unclaimed": 0, "claimed": 0, "failed": 0}

            for selector in tab_selectors:
                try:
                    elements = page.locator(selector)
                    total = await elements.count()
                    for index in range(total):
                        text = await elements.nth(index).inner_text()
                        match = re.search(r"\((\d+)\)", text or "")
                        if not match:
                            continue
                        value = int(match.group(1))
                        lowered = text.lower()
                        if "全部" in text or "all" in lowered:
                            counts["all"] = max(counts["all"], value)
                        elif "未认领" in text or "unclaimed" in lowered:
                            counts["unclaimed"] = max(counts["unclaimed"], value)
                        elif "已认领" in text or "claimed" in lowered:
                            counts["claimed"] = max(counts["claimed"], value)
                        elif "失败" in text or "failed" in lowered:
                            counts["failed"] = max(counts["failed"], value)
                except Exception:
                    continue

            logger.debug("Product counts: {}", counts)
            return counts
        except Exception as exc:
            logger.error(f"Failed to fetch product counts: {exc}")
            return {"all": 0, "unclaimed": 0, "claimed": 0, "failed": 0}

    async def switch_tab(self, page: Page, tab_name: str) -> bool:
        """Switch to a target tab within the collection box.

        Args:
            page: Active Playwright page instance.
            tab_name: Name of the tab to activate. Supports ``all``, ``unclaimed``, ``claimed`` and ``failed``.

        Returns:
            True when the tab switch succeeded, otherwise False.
        """
        logger.info("Switching to tab: {}", tab_name)
        
        # 调试：输出当前页面URL和HTML快照
        logger.warning(f"🔍 DEBUG Current page URL: {page.url}")
        
        # 调试：尝试截图
        try:
            screenshot_path = f"data/temp/screenshots/debug_tab_switch_{tab_name}.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.warning(f"🔍 DEBUG Screenshot saved to: {screenshot_path}")
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")
            
        # 调试：输出页面上所有可能相关的元素
        try:
            all_text = await page.locator("body").inner_text()
            if "全部" in all_text:
                logger.warning("🔍 Found '全部' in page text")
            if "All" in all_text or "ALL" in all_text:
                logger.warning("🔍 Found 'All/ALL' in page text")
            
            # 检查所有可能的tab元素
            tab_candidates = await page.locator("button, [role='tab'], .jx-radio-button, .jx-tabs__item, [class*='tab']").all()
            logger.warning(f"🔍 Found {len(tab_candidates)} potential tab elements")
            for i, elem in enumerate(tab_candidates[:30]):
                try:
                    text = (await elem.inner_text()).strip()
                    tag = await elem.evaluate("el => el.tagName")
                    classes = await elem.get_attribute("class") or ""
                    if text:
                        logger.warning(f"  [{i}] <{tag}> class='{classes[:50]}...' text='{text[:30]}'")
                except:
                    pass
        except Exception as e:
            logger.warning(f"🔍 Element inspection failed: {e}")

        try:
            label_variants = self._TAB_LABEL_VARIANTS.get(tab_name, (tab_name,))
            normalized_labels = []
            for label in label_variants:
                if not label:
                    continue
                for variant in (label, label.upper(), label.lower()):
                    if variant not in normalized_labels:
                        normalized_labels.append(variant)

            tab_config = self.selectors.get("collection_box", {}).get("tabs", {})
            tab_mapping: dict[str, Any] = {
                "all": tab_config.get("all", []),
                "unclaimed": tab_config.get("unclaimed", []),
                "claimed": tab_config.get("claimed", []),
                "failed": tab_config.get("failed", []),
            }

            if tab_name not in tab_mapping:
                logger.warning("Unknown tab requested: {}", tab_name)

            default_selectors: list[str] = []
            for label in normalized_labels or [tab_name]:
                default_selectors.extend(
                    [
                        f".jx-tabs__item:has-text('{label}')",
                        f".pro-tabs__item:has-text('{label}')",
                        f".el-tabs__item:has-text('{label}')",
                        f".ant-tabs-tab:has-text('{label}')",
                        f"[role='tab']:has-text('{label}')",
                        f".jx-radio-button:has-text('{label}')",
                        f".pro-radio-button:has-text('{label}')",
                        f"button:has-text('{label}')",
                        f"span:has-text('{label}')",
                        f"div[class*='tab']:has-text('{label}')",
                        f"li[class*='tab']:has-text('{label}')",
                        f"text='{label}'",
                    ]
                )

            selectors = self._resolve_selectors(
                tab_mapping,
                keys=[tab_name],
                default=default_selectors,
            )

            clicked = False
            for selector in selectors:
                try:
                    candidate = page.locator(selector)
                    if await candidate.count() == 0:
                        continue

                    button = candidate.first
                    with suppress(Exception):
                        await button.scroll_into_view_if_needed()
                    await button.wait_for(state="visible", timeout=3_000)
                    button_text = (await button.inner_text()).strip()

                    if not self._tab_text_matches(button_text, normalized_labels or [tab_name]):
                        logger.debug(
                            "Selector %s did not match expected labels %s (found '%s')",
                            selector,
                            normalized_labels or [tab_name],
                            button_text,
                        )
                        continue

                    await button.click()
                    clicked = True
                    logger.success("Tab click succeeded via {}", selector)
                    break
                except Exception:
                    continue

            if not clicked:
                logger.error("Failed to switch to tab {}", tab_name)
                return False

            await self._wait_for_table_refresh(page)

            logger.success("Switched to tab {}", tab_name)
            return True
        except Exception as exc:
            logger.error(f"Switch tab error: {exc}")
            return False

    @staticmethod
    def _tab_text_matches(button_text: str, labels: list[str]) -> bool:
        """Check if the given button text contains any expected labels."""

        normalized_text = (button_text or "").strip().lower()
        for label in labels:
            if label and label.lower() in normalized_text:
                return True
        return False

    async def search_products(
        self,
        page: Page,
        title: str | None = None,
        source_id: str | None = None,
        price_min: float | None = None,
        price_max: float | None = None,
    ) -> bool:
        """Search products within the collection box.

        Args:
            page: Active Playwright page instance.
            title: Title filter applied via the search form.
            source_id: Source identifier filter.
            price_min: Minimum price filter.
            price_max: Maximum price filter.

        Returns:
            True when the search request completed, otherwise False.
        """
        logger.info("Searching products with provided filters...")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            search_config = collection_box_config.get("search_box", {})

            if title:
                logger.debug("Applying title filter: {}", title)
                title_selector = search_config.get("product_title", "input[placeholder*='标题']")
                title_field = page.locator(title_selector)
                await title_field.fill(title)
                with suppress(Exception):
                    await title_field.blur()

            if source_id:
                logger.debug("Applying source ID filter: {}", source_id)
                id_selector = search_config.get("source_id", "input[placeholder*='ID']")
                source_field = page.locator(id_selector)
                await source_field.fill(source_id)
                with suppress(Exception):
                    await source_field.blur()

            if price_min is not None:
                logger.debug("Applying minimum price: {}", price_min)
                min_selector = search_config.get("source_price_min", "input[placeholder*='最低']")
                min_field = page.locator(min_selector)
                await min_field.fill(str(price_min))
                with suppress(Exception):
                    await min_field.blur()

            if price_max is not None:
                logger.debug("Applying maximum price: {}", price_max)
                max_selector = search_config.get("source_price_max", "input[placeholder*='最高']")
                max_field = page.locator(max_selector)
                await max_field.fill(str(price_max))
                with suppress(Exception):
                    await max_field.blur()

            search_btn_selector = search_config.get("search_btn", "button:has-text('搜索')")
            await page.locator(search_btn_selector).click()
            await self._wait_for_table_refresh(page)

            logger.success("Search executed successfully")
            return True
        except Exception as exc:
            logger.error(f"Product search failed: {exc}")
            return False

    async def select_all_products(self, page: Page) -> bool:
        """Select all products on the current page.

        Args:
            page: Active Playwright page instance.

        Returns:
            True when the selection action succeeded, otherwise False.
        """
        logger.info("Selecting all products on the current page")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            pagination_config = collection_box_config.get("pagination", {})

            select_all_selectors = [
                ".jx-pagination__total .jx-checkbox__label",
                "label.jx-checkbox:has-text('全选')",
                ".jx-table__header .jx-checkbox__label",
                ".jx-checkbox:has-text('全选')",
                ".el-checkbox:has-text('全选')",
                ".ant-checkbox-wrapper:has-text('全选')",
                "label:has-text('全选')",
                ".jx-checkbox__inner",
                "text='全选'",
            ]
            select_all_selectors = self._resolve_selectors(
                pagination_config,
                keys=["select_all"],
                default=select_all_selectors,
            )

            clicked = False
            for selector in select_all_selectors:
                try:
                    button = page.locator(selector)
                    if await button.count() == 0:
                        continue
                    with suppress(Exception):
                        await button.first.scroll_into_view_if_needed()
                    await button.first.click()
                    clicked = True
                    logger.success("Select all checkbox clicked via {}", selector)
                    break
                except Exception:
                    continue

            if not clicked:
                logger.warning("Select all action did not find a matching checkbox")
                return False

            await self._wait_for_bulk_selection(page)
            return True
        except Exception as exc:
            logger.error(f"Failed to select all products: {exc}")
            return False

    async def click_edit_first_product(self, page: Page) -> bool:
        """Click the edit button on the first product.

        Args:
            page: Active Playwright page instance.

        Returns:
            True when the edit button was clicked, otherwise False.
        """
        return await self.click_edit_product_by_index(page, 0)

    async def click_edit_product_by_index(
        self,
        page: Page,
        index: int,
        *,
        enable_scroll: bool = True,  # 默认启用（JS 内部处理滚动）
    ) -> bool:
        """Click the edit button of a product at a specific index.

        通过 JavaScript 自动滚动到目标位置并点击编辑按钮：
        1. JS 滚动容器到 index * ROW_HEIGHT 位置
        2. 等待 DOM 更新（vue-recycle-scroller 重新渲染）
        3. 点击视口中第一行的编辑按钮

        Args:
            page: Active Playwright page instance.
            index: Zero-based index of the product in the grid (全局索引).
            enable_scroll: 保留参数，但 JS 内部会自动处理滚动

        Returns:
            True when the edit button was clicked, otherwise False.
        """
        logger.info("Clicking edit button for product index {} (JS auto-scroll)", index)

        try:
            await self._ensure_popups_closed(page)

            if index < 0:
                logger.error("Product index must be non-negative")
                return False

            # 使用 JavaScript 自动滚动到目标位置并点击
            clicked = await self._click_edit_button_by_js(page, index)
            if clicked:
                return True

            logger.error("No matching edit button found for index {}", index)
            return False
        except Exception as exc:
            logger.error(f"Failed to click edit button: {exc}")
            return False

    async def _click_edit_button_by_js(self, page: Page, index: int) -> bool:
        """使用 JavaScript 直接定位并点击第 index 个商品的编辑按钮。

        通过 JS 滚动页面/容器到目标位置，然后点击编辑按钮。
        支持 page-mode（页面级滚动）和容器级滚动两种模式。

        Args:
            page: Playwright 页面对象
            index: 目标商品索引（全局索引，0-based）

        Returns:
            是否成功点击
        """
        try:
            # JavaScript：滚动到目标位置，然后点击编辑按钮
            js_code = """
            async (index) => {
                const DEFAULT_ROW_HEIGHT = 128;
                
                // 检查是否为 page-mode（页面级滚动）
                const recycleScroller = document.querySelector('.vue-recycle-scroller');
                const isPageMode = recycleScroller && recycleScroller.classList.contains('page-mode');
                
                // 获取所有可见行的辅助函数
                const getVisibleRows = () => {
                    const rows = document.querySelectorAll('.vue-recycle-scroller__item-view');
                    const visibleRows = [];
                    rows.forEach(row => {
                        const style = row.getAttribute('style') || '';
                        const match = style.match(/translateY\\((-?\\d+(?:\\.\\d+)?)\\s*(?:px)?\\s*\\)/);
                        if (match) {
                            const y = parseFloat(match[1]);
                            if (y >= 0) visibleRows.push({ row, y });
                        }
                    });
                    visibleRows.sort((a, b) => a.y - b.y);
                    return visibleRows;
                };
                
                // 动态检测实际行高（通过测量相邻行的Y差值）
                const detectRowHeight = () => {
                    const visibleRows = getVisibleRows();
                    if (visibleRows.length >= 2) {
                        const diffs = [];
                        for (let i = 1; i < visibleRows.length; i++) {
                            const diff = visibleRows[i].y - visibleRows[i-1].y;
                            if (diff > 50 && diff < 300) diffs.push(diff);
                        }
                        if (diffs.length > 0) {
                            diffs.sort((a, b) => a - b);
                            return diffs[Math.floor(diffs.length / 2)];
                        }
                    }
                    if (visibleRows.length >= 1) {
                        const rect = visibleRows[0].row.getBoundingClientRect();
                        if (rect.height > 50 && rect.height < 300) return rect.height;
                    }
                    return DEFAULT_ROW_HEIGHT;
                };
                
                const ROW_HEIGHT = detectRowHeight();
                const targetScrollTop = index * ROW_HEIGHT;
                
                let scrollerInfo = '';
                let actualScrollTop = 0;
                
                if (isPageMode) {
                    // page-mode：滚动整个页面或找到真正的滚动父容器
                    scrollerInfo = 'page-mode';
                    
                    // 尝试找到有 overflow 的父容器
                    let scrollParent = recycleScroller.parentElement;
                    let foundScrollable = false;
                    
                    while (scrollParent && scrollParent !== document.body) {
                        const style = window.getComputedStyle(scrollParent);
                        const overflowY = style.overflowY;
                        if ((overflowY === 'auto' || overflowY === 'scroll') && 
                            scrollParent.scrollHeight > scrollParent.clientHeight) {
                            // 找到可滚动的父容器
                            scrollParent.scrollTop = targetScrollTop;
                            await new Promise(r => setTimeout(r, 500));
                            actualScrollTop = scrollParent.scrollTop;
                            scrollerInfo = `parent: ${scrollParent.className.split(' ')[0] || scrollParent.tagName}`;
                            foundScrollable = true;
                            break;
                        }
                        scrollParent = scrollParent.parentElement;
                    }
                    
                    // 如果没找到滚动父容器，滚动整个页面
                    if (!foundScrollable) {
                        window.scrollTo({ top: targetScrollTop, behavior: 'instant' });
                        await new Promise(r => setTimeout(r, 500));
                        actualScrollTop = window.scrollY || document.documentElement.scrollTop;
                        scrollerInfo = 'window';
                    }
                } else {
                    // 非 page-mode：滚动容器本身
                    if (recycleScroller) {
                        recycleScroller.scrollTop = targetScrollTop;
                        await new Promise(r => setTimeout(r, 500));
                        actualScrollTop = recycleScroller.scrollTop;
                        scrollerInfo = 'vue-recycle-scroller';
                    }
                }
                
                // 重新获取可见行（滚动后）
                const rows = document.querySelectorAll('.vue-recycle-scroller__item-view');
                const visibleRows = getVisibleRows();
                
                // 根据可见行推断索引的辅助函数
                const inferRowIndex = (y) => Math.round(y / ROW_HEIGHT);
                
                // 直接使用 index * ROW_HEIGHT 计算目标 translateY
                let targetRow = null;
                let targetTranslateY = index * ROW_HEIGHT;
                let matchedY = -1;
                
                // 方法1: 基于Y坐标匹配（容差为行高的70%）
                for (const item of visibleRows) {
                    const diff = Math.abs(item.y - targetTranslateY);
                    if (diff < ROW_HEIGHT * 0.7) {
                        targetRow = item.row;
                        matchedY = item.y;
                        break;
                    }
                }
                
                // 方法2: 基于推断索引匹配（更健壮的匹配方式）
                if (!targetRow) {
                    for (const item of visibleRows) {
                        const inferredIdx = inferRowIndex(item.y);
                        if (inferredIdx === index) {
                            targetRow = item.row;
                            matchedY = item.y;
                            break;
                        }
                    }
                }
                
                // 如果匹配失败，记录所有可见行的 Y 值用于调试
                if (!targetRow) {
                    return { 
                        success: false, 
                        error: `Target Y=${targetTranslateY} not found in visible rows`,
                        scrollerInfo,
                        isPageMode,
                        targetScrollTop,
                        actualScrollTop,
                        rowCount: rows.length,
                        visibleYs: visibleRows.map(r => r.y),
                        inferredIdxs: visibleRows.map(r => inferRowIndex(r.y)),
                        detectedRowHeight: ROW_HEIGHT
                    };
                }
                
                // 在行内查找编辑按钮（精确匹配 J_commonCollectBoxEdit）
                const editBtn = targetRow.querySelector('.J_commonCollectBoxEdit');
                
                if (!editBtn) {
                    return { 
                        success: false, 
                        error: 'Edit button (.J_commonCollectBoxEdit) not found in target row',
                        scrollerInfo,
                        matchedY
                    };
                }
                
                // 强制点击
                editBtn.click();
                
                return { 
                    success: true, 
                    scrollerInfo,
                    isPageMode,
                    targetScrollTop,
                    actualScrollTop,
                    targetTranslateY,
                    matchedY,
                    visibleCount: visibleRows.length
                };
            }
            """

            result = await page.evaluate(js_code, index)

            if result.get("success"):
                logger.success(
                    f"✓ JS 点击编辑按钮成功，索引={index}, 容器={result.get('scrollerInfo')}, "
                    f"page-mode={result.get('isPageMode')}, scrollTop={result.get('actualScrollTop')}px, "
                    f"匹配Y={result.get('matchedY')}px"
                )
                return True
            else:
                logger.warning(
                    f"JS 点击失败: {result.get('error')}, 容器={result.get('scrollerInfo')}, "
                    f"page-mode={result.get('isPageMode')}, 目标scrollTop={result.get('targetScrollTop')}, "
                    f"实际scrollTop={result.get('actualScrollTop')}, 行数={result.get('rowCount')}, "
                    f"可见Y值={result.get('visibleYs')}"
                )
                return False

        except Exception as exc:
            logger.warning(f"JS 点击异常: {exc}")
            return False

    async def _click_edit_button_in_row(
        self,
        page: Page,
        row,
        edit_selectors: tuple[str, ...],
        index: int,
    ) -> bool:
        """在指定的商品行内查找并点击编辑按钮。

        Args:
            page: Playwright 页面对象
            row: 商品行 Locator
            edit_selectors: 编辑按钮选择器列表
            index: 商品索引（用于日志）

        Returns:
            是否成功点击
        """
        try:
            # 先滚动到行可见
            with suppress(Exception):
                await row.scroll_into_view_if_needed()
            await page.wait_for_timeout(200)

            # 在行内查找编辑按钮
            for selector in edit_selectors:
                try:
                    # 在行内定位编辑按钮
                    button = row.locator(selector).first
                    if await button.count() == 0:
                        continue

                    await button.wait_for(state="visible", timeout=2_000)
                    await button.click()
                    logger.success(
                        "✓ 基于行定位成功点击编辑按钮，索引: {}, 选择器: {}",
                        index, selector
                    )
                    return True
                except Exception as exc:
                    logger.debug(f"行内编辑按钮 {selector} 点击失败: {exc}")
                    continue

            logger.debug(f"在行内未找到编辑按钮，索引: {index}")
            return False
        except Exception as exc:
            logger.debug(f"行内点击编辑按钮异常: {exc}")
            return False


