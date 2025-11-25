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
from playwright.async_api import Page

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
                await page.wait_for_load_state("domcontentloaded", timeout=5_000)
                with suppress(Exception):
                    await page.wait_for_url(re.compile("common_collect_box"), timeout=15_000)
            else:
                logger.debug(f"Direct navigation to: {target_url}")
                try:
                    await page.goto(target_url, timeout=30_000)
                except Exception as exc:
                    logger.warning(
                        "Direct navigation failed (%s), retrying via sidebar", exc
                    )
                    return await self.navigate_to_collection_box(page, use_sidebar=True)

            await page.wait_for_load_state("domcontentloaded", timeout=5_000)

            if "common_collect_box/items" in page.url:
                logger.success("Navigation to shared collection box succeeded")
                logger.debug("Waiting for page to settle...")
                
                # 等待主要内容容器加载完成，而不是固定等待时间
                try:
                    logger.debug("Waiting for main content container...")
                    await page.wait_for_selector(
                        ".jx-main, .pro-layout-content, .main-content, [class*='content']",
                        state="visible",
                        timeout=10_000
                    )
                    logger.debug("Main content container loaded")
                    
                    # 等待tab或按钮元素出现
                    logger.debug("Waiting for interactive elements...")
                    await page.wait_for_selector(
                        "button, [role='tab'], .jx-radio-button, .jx-tabs__item, .jx-button",
                        state="visible",
                        timeout=10_000
                    )
                    logger.debug("Interactive elements loaded")
                except Exception as e:
                    logger.warning(f"Content wait timed out: {e}, waiting for network idle")
                    with suppress(Exception):
                        await page.wait_for_load_state("networkidle", timeout=5_000)
                
                await self._ensure_popups_closed(page)

                return True

            if not use_sidebar:
                logger.warning("Unexpected URL %s, retrying via sidebar navigation", page.url)
                return await self.navigate_to_collection_box(page, use_sidebar=True)

            logger.error("Navigation failed: unexpected URL %s", page.url)
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
        logger.info("Filtering and searching by staff: %s", staff_name or "(all)")

        try:
            collection_box_config = self.selectors.get("collection_box", {})
            search_box_config = collection_box_config.get("search_box", {})

            if staff_name:
                logger.debug("Selecting staff member: %s", staff_name)
                all_selects = page.locator(".jx-select, .el-select, .ant-select, .pro-select")
                select_count = await all_selects.count()
                logger.debug("Located %s select elements", select_count)

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
                                    logger.success("Staff member selected: %s", staff_name)
                                    break
                            except Exception as err:  # pragma: no cover - UI variance
                                logger.debug("Selector %s failed: %s", selector, err)
                                continue

                        if not staff_option_clicked:
                            logger.warning("Could not locate staff option: %s", staff_name)
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
                logger.warning("Search button not found with selector %s, skipping explicit search", search_btn_selector)
            else:
                await search_btn.click()
            await self._wait_for_table_refresh(page)

            logger.success("Filtering and search finished")
            return True
        except Exception as exc:
            logger.error(f"Filter/search failed: {exc}")
            return False

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
                "button[aria-label='关闭']",
                "button[aria-label='Close']",
            ]
            overlay_selector = ".jx-overlay-dialog, .el-dialog, [role='dialog']"
            header_close_selectors = [
                ".jx-dialog__headerbtn",
                ".el-dialog__headerbtn",
            ]

            for selector in popup_buttons:
                try:
                    locator = page.locator(selector)
                    if await locator.count() > 0:
                        logger.debug("Found popup button: %s", selector)
                        await locator.first.click(timeout=2_000)
                        await self._wait_for_message_box_dismissal(page)
                        logger.success("Popup closed via button: %s", selector)
                        return True
                except Exception:
                    continue

            dialogs = page.locator(overlay_selector)
            dialog_count = await dialogs.count()
            if dialog_count:
                for index in range(dialog_count - 1, -1, -1):
                    dialog = dialogs.nth(index)
                    for selector in header_close_selectors:
                        try:
                            btn = dialog.locator(selector)
                            if await btn.count() and await btn.first.is_visible(timeout=1_000):
                                logger.debug("Clicking dialog header close: %s (idx=%s)", selector, index)
                                await btn.first.click()
                                await self._wait_for_message_box_dismissal(page)
                                logger.success("Popup closed via header button")
                                return True
                        except Exception as exc:
                            logger.debug("Header close failed (%s): %s", selector, exc)

            # 针对 .jx-overlay-message-box（如“提示”“知道了”）的兜底处理
            message_box = page.locator(".jx-overlay-message-box:visible")
            msg_count = await message_box.count()
            if msg_count:
                logger.debug("Found overlay message box: count=%s", msg_count)
                close_candidates = [
                    ".jx-overlay-message-box button.jx-message-box__headerbtn",
                    ".jx-overlay-message-box button:has-text('确定')",
                    ".jx-overlay-message-box button:has-text('知道了')",
                    ".jx-overlay-message-box button:has-text('关闭')",
                    ".jx-overlay-message-box button[aria-label*='关闭']",
                ]
                for selector in close_candidates:
                    try:
                        btn = page.locator(selector).first
                        if await btn.count() and await btn.is_visible(timeout=500):
                            await btn.click(timeout=1_000)
                            await self._wait_for_message_box_dismissal(page)
                            logger.success("Overlay message box closed via %s", selector)
                            return True
                    except Exception:
                        continue
                with suppress(Exception):
                    await page.keyboard.press("Escape")
                    await self._wait_for_message_box_dismissal(page)
                    logger.success("Overlay message box dismissed via Escape")
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
        locator = page.locator(".jx-overlay-message-box, .jx-message-box, .el-message-box")
        try:
            await locator.first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass

    async def _wait_for_bulk_selection(self, page: Page, timeout: int = 2_000) -> None:
        """Wait for any checkbox to reflect the 'selected' state."""
        selection_locator = page.locator(
            ".jx-checkbox.is-checked, .el-checkbox.is-checked, .ant-checkbox-checked"
        )
        try:
            await selection_locator.first.wait_for(state="visible", timeout=timeout)
        except Exception:
            pass

    async def _wait_for_table_refresh(self, page: Page, timeout: int = 5_000) -> None:
        """Wait for the product table to update after actions such as search or tab switch."""
        table_locator = page.locator(
            ".pro-virtual-table, .vue-recycle-scroller, .jx-table, .pro-table"
        )
        with suppress(Exception):
            await table_locator.first.wait_for(state="visible", timeout=timeout)
        with suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=timeout)

    async def _wait_for_idle(self, page: Page, timeout_ms: int = 300) -> None:
        """Best-effort wait for the page to reach a steady (network idle) state."""
        with suppress(Exception):
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)

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

            logger.debug("Product counts: %s", counts)
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
                logger.warning("Unknown tab requested: %s", tab_name)

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
                    logger.success("Tab click succeeded via %s", selector)
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
                logger.debug("Applying title filter: %s", title)
                title_selector = search_config.get("product_title", "input[placeholder*='标题']")
                title_field = page.locator(title_selector)
                await title_field.fill(title)
                with suppress(Exception):
                    await title_field.blur()

            if source_id:
                logger.debug("Applying source ID filter: %s", source_id)
                id_selector = search_config.get("source_id", "input[placeholder*='ID']")
                source_field = page.locator(id_selector)
                await source_field.fill(source_id)
                with suppress(Exception):
                    await source_field.blur()

            if price_min is not None:
                logger.debug("Applying minimum price: %s", price_min)
                min_selector = search_config.get("source_price_min", "input[placeholder*='最低']")
                min_field = page.locator(min_selector)
                await min_field.fill(str(price_min))
                with suppress(Exception):
                    await min_field.blur()

            if price_max is not None:
                logger.debug("Applying maximum price: %s", price_max)
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
                    logger.success("Select all checkbox clicked via %s", selector)
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

    async def click_edit_product_by_index(self, page: Page, index: int) -> bool:
        """Click the edit button of a product at a specific index.

        Args:
            page: Active Playwright page instance.
            index: Zero-based index of the product in the grid.

        Returns:
            True when the edit button was clicked, otherwise False.
        """
        logger.info("Clicking edit button for product index %s", index)

        try:
            await self._ensure_popups_closed(page)

            if index < 0:
                logger.error("Product index must be non-negative")
                return False

            selectors = self._resolve_selectors(
                self.selectors.get("collection_box", {}).get("edit_button", {}),
                keys=["edit"],
                default=self._DEFAULT_EDIT_BUTTON_SELECTORS,
            )

            for selector in selectors:
                try:
                    buttons = page.locator(selector)
                    count = await buttons.count()
                    if count <= index:
                        continue

                    button = buttons.nth(index)
                    with suppress(Exception):
                        await button.scroll_into_view_if_needed()
                    await button.wait_for(state="visible", timeout=2_000)
                    await button.click()
                    logger.success("Edit button clicked using selector %s", selector)
                    return True
                except Exception as exc:
                    logger.debug("Edit selector %s failed: %s", selector, exc)
                    continue

            logger.error("No matching edit button found for index %s", index)
            return False
        except Exception as exc:
            logger.error(f"Failed to click edit button: {exc}")
            return False

