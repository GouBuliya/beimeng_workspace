"""
@PURPOSE: Claim workflow utilities for the Miaoshou controller.
@OUTLINE:
  - class MiaoshouClaimMixin: DOM-driven selection, claim actions, verification helpers
    - async def refresh_collection_box(): 导航并确保列表可见
    - async def select_products_for_claim(): 勾选表格前 N 条商品
    - async def _resolve_checkbox_locator(): 复用勾选候选定位器并返回可点击元素
    - async def _click_claim_button_in_row_by_js(): 复用首次编辑定位逻辑点击行内认领按钮
    - async def claim_products_by_row_js(): 使用 JS 定位逻辑逐行认领商品
    - async def _ensure_claim_button_visible(): 确保认领按钮可见并返回定位器
    - async def _find_clickable_in_scopes(): 在 Page/Frame 中定位可交互按钮
    - async def _click_claim_confirmation_button(): 在认领弹窗中定位并点击确认按钮
    - async def claim_selected_products_to_temu(): 使用 DOM 操作执行认领
    - async def claim_products_via_api(): 使用 API 直接认领产品（绕过浏览器）
    - async def claim_specific_products_via_api(): 使用 API 认领指定产品列表
@DEPENDENCIES:
  - 内部: .api_client.MiaoshouApiClient (API 认领)
"""

import re
import time
from collections.abc import Sequence
from contextlib import suppress
from typing import Any, ClassVar

from loguru import logger
from playwright.async_api import Frame, Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ...core.retry_handler import SessionExpiredError
from ...utils.page_load_decorator import (
    PAGE_TIMEOUTS,
    LoadState,
    ensure_page_loaded,
)
from ...utils.page_waiter import PageWaiter
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
    _ROW_HEIGHT: ClassVar[int] = 119
    _ROW_CHECKBOX_SELECTOR: ClassVar[str] = ".is-fixed-left.is-selection-column .jx-checkbox"
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
            logger.debug(f"Refreshing collection box page at {self._COLLECTION_BOX_URL}")
            # 添加超时保护,避免无限等待
            await page.goto(
                self._COLLECTION_BOX_URL,
                wait_until="domcontentloaded",
                timeout=30_000,  # 30秒超时
            )
            # 性能优化:networkidle 改为短等待,避免长时间阻塞
            # 原因:networkidle 可能永远无法触发,且大部分情况下 domcontentloaded 已足够
            with suppress(Exception):
                await page.wait_for_timeout(300)
            logger.debug("Collection box page refreshed successfully")
        except Exception as exc:
            logger.warning(f"Failed to refresh collection box page: {exc}")

        await self._wait_for_rows(page)

        if filter_owner:
            logger.info("尝试按负责人筛选:{}", filter_owner)
            try:
                filtered = await self.filter_and_search(page, filter_owner)
                if not filtered:
                    logger.warning("负责人筛选逻辑返回 False:{}", filter_owner)
                await self._wait_for_rows(page)
            except Exception as exc:
                logger.warning("负责人筛选失败({}): {}", filter_owner, exc)

    async def _wait_for_rows(self, page: Page, *, timeout: int = 1_000) -> bool:
        """Wait until the collection box table rows are rendered.

        性能优化:timeout 从 1500ms 减少到 1000ms
        """
        rows = page.locator(self._ROW_SELECTOR)
        try:
            await rows.first.wait_for(state="visible", timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            logger.warning(f"Product rows did not become visible within {timeout}ms")
            return False

    async def _wait_for_dropdown_state(
        self,
        page: Page,
        selectors: str,
        *,
        state: str = "visible",
        timeout: int = 250,
    ) -> None:
        """Wait for dropdown containers matching ``selectors`` to reach ``state``.

        性能优化:timeout 从 400ms 减少到 250ms
        """
        dropdown = page.locator(selectors)
        with suppress(Exception):
            await dropdown.first.wait_for(state=state, timeout=timeout)

    async def _wait_for_select_dropdown(
        self,
        page: Page,
        *,
        state: str = "visible",
        timeout: int = 250,
    ) -> None:
        await self._wait_for_dropdown_state(
            page, self._SELECT_DROPDOWN_LOCATOR, state=state, timeout=timeout
        )

    async def _wait_for_claim_dropdown(
        self,
        page: Page,
        *,
        state: str = "visible",
        timeout: int = 250,
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
                logger.debug(f"Row index {idx} exceeds available rows {available}")
                continue
            resolved.append(idx)
        return resolved

    _PAGE_SIZE: ClassVar[int] = 20  # 每页显示商品数量

    async def _jump_to_page_for_claim(self, page: Page, target_page: int) -> bool:
        """跳转到指定页码(用于认领流程).

        Args:
            page: Playwright 页面对象
            target_page: 目标页码(从1开始)

        Returns:
            是否成功跳转
        """
        if target_page <= 1:
            return True

        waiter = PageWaiter(page)

        selectors = [
            'input.jx-input__inner[type="number"][aria-label="页"]',
            'input.jx-input__inner[type="number"][aria-label]',
            'input[type="number"][aria-label="页"]',
            'input[type="number"][aria-label]',
            '.jx-pagination__goto input[type="number"]',
        ]
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                if await locator.count() == 0:
                    continue
                await locator.click()
                await locator.fill(str(target_page))
                with suppress(Exception):
                    await locator.press("Enter")
                await waiter.wait_for_dom_stable(timeout_ms=800)
                with suppress(Exception):
                    await self._wait_for_rows(page)
                logger.info("认领流程:已跳转到第 {} 页", target_page)
                return True
            except Exception as exc:
                logger.debug("翻页失败 selector={}: {}", selector, exc)

        logger.warning("认领流程:无法跳转到第 {} 页", target_page)
        return False

    async def select_products_for_claim(
        self,
        page: Page,
        count: int = 5,
        indexes: Sequence[int] | None = None,
        *,
        enable_scroll: bool = False,  # 默认禁用滚动,使用直接定位
    ) -> bool:
        """Select the first ``count`` products before starting a claim batch.

        支持跨页勾选:当索引超过每页容量(20条)时自动翻页.
        1. 按页码分组目标索引
        2. 对每页:先翻页,再用页内相对索引勾选
        3. 获取所有可见行(translateY >= 0)
        4. 按 translateY 排序得到视觉顺序
        5. 直接点击目标行的复选框

        Args:
            page: Active Playwright page instance.
            count: Number of products to select.
            indexes: Specific indexes to select (optional, 绝对索引).
            enable_scroll: 是否启用滚动(默认禁用)

        Returns:
            True when all target products were selected, otherwise False.
        """
        waiter = PageWaiter(page)
        logger.info(f"Selecting up to {count} product rows (direct locate)")

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

        # 按页码分组索引
        page_groups: dict[int, list[int]] = {}
        for idx in target_indexes:
            target_page = idx // self._PAGE_SIZE + 1
            page_relative_idx = idx % self._PAGE_SIZE
            if target_page not in page_groups:
                page_groups[target_page] = []
            page_groups[target_page].append(page_relative_idx)

        logger.info(f"索引按页分组: {page_groups}")

        current_page = 1
        selected = 0

        # 按页码顺序处理
        for target_page in sorted(page_groups.keys()):
            page_relative_indexes = page_groups[target_page]

            # 如果需要翻页
            if target_page != current_page:
                logger.info(f"需要跳转到第 {target_page} 页(当前第 {current_page} 页)")
                if await self._jump_to_page_for_claim(page, target_page):
                    current_page = target_page
                else:
                    logger.error(f"翻页到第 {target_page} 页失败")
                    return False

            # 使用页内相对索引勾选
            logger.info(f"第 {target_page} 页,勾选页内索引: {page_relative_indexes}")
            page_selected = await self._select_checkboxes_by_js(page, page_relative_indexes)
            selected += page_selected

            if page_selected != len(page_relative_indexes):
                logger.warning(
                    f"第 {target_page} 页勾选不完整: {page_selected}/{len(page_relative_indexes)}"
                )
                # 如果启用滚动,尝试滚动方式补充勾选
                if enable_scroll:
                    for rel_idx in page_relative_indexes[page_selected:]:
                        from ...utils.scroll_helper import scroll_to_product_position

                        await scroll_to_product_position(page, target_index=rel_idx)
                        await waiter.wait_for_dom_stable(timeout_ms=500)
                        if await self._click_checkbox_by_js(page, 0):
                            selected += 1
                        else:
                            logger.error(
                                f"Failed to toggle checkbox for page-relative index {rel_idx}"
                            )

        if selected == len(target_indexes):
            logger.success(f"Selected {selected}/{len(target_indexes)} rows for claim")
            return True

        logger.warning(f"勾选不完整: {selected}/{len(target_indexes)}")
        return selected == len(target_indexes)

    async def _select_checkboxes_by_js(self, page: Page, indexes: list[int]) -> int:
        """使用 JavaScript 批量勾选复选框(带自动滚动).

        【第五轮重构】复用 _click_claim_button_in_row_by_js 的定位逻辑，
        确保与首次编辑的定位方式完全一致。

        Args:
            page: Playwright 页面对象
            indexes: 目标索引列表(全局索引)

        Returns:
            成功勾选的数量
        """
        selected = 0
        for idx in indexes:
            result = await self._click_claim_button_in_row_by_js(page, idx, target="checkbox")
            if result.get("success"):
                selected += 1
                logger.debug(f"✓ 复选框勾选成功: index={idx}")
            else:
                logger.warning(f"✗ 复选框勾选失败: index={idx}, error={result.get('error')}")
        return selected

    async def _select_checkboxes_by_js_legacy(self, page: Page, indexes: list[int]) -> int:
        """【已废弃】旧版批量勾选复选框逻辑，保留以备回滚."""
        try:
            js_code = """
            async (indexes) => {
                const MAX_SCROLL_ATTEMPTS = 8;
                const DEFAULT_ROW_HEIGHT = 128;  // 默认值,会被动态检测覆盖

                // 【第四轮修复】虚拟列表顶部偏移补偿
                // 虚拟列表上方有固定元素（表头等），导致 translateY 与实际行索引有偏移
                const TOP_OFFSET_ROWS = 2;

                // 检查是否为 page-mode(页面级滚动)
                const recycleScroller = document.querySelector('.vue-recycle-scroller');
                const isPageMode = recycleScroller && recycleScroller.classList.contains('page-mode');

                // 获取所有可见行
                // 关键修复: 只选择包含复选框的行,因为 pro-virtual-table
                // 可能有两个独立的虚拟滚动容器(固定列和主内容区)
                const getVisibleRows = () => {
                    const rows = document.querySelectorAll('.vue-recycle-scroller__item-view');
                    const visibleRows = [];
                    rows.forEach(row => {
                        // 只选择包含复选框的行
                        const hasCheckbox = row.querySelector('.is-selection-column') !== null ||
                                          row.querySelector('.jx-checkbox') !== null;
                        if (!hasCheckbox) return;

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

                // 动态检测实际行高(通过测量相邻行的Y差值)
                const detectRowHeight = () => {
                    const visibleRows = getVisibleRows();
                    if (visibleRows.length >= 2) {
                        // 计算相邻行之间的Y差值
                        const diffs = [];
                        for (let i = 1; i < visibleRows.length; i++) {
                            const diff = visibleRows[i].y - visibleRows[i-1].y;
                            if (diff > 50 && diff < 300) {  // 合理范围内的差值
                                diffs.push(diff);
                            }
                        }
                        if (diffs.length > 0) {
                            // 取中位数作为行高(更稳定)
                            diffs.sort((a, b) => a - b);
                            const median = diffs[Math.floor(diffs.length / 2)];
                            return median;
                        }
                    }
                    // 尝试从第一行的boundingClientRect获取高度
                    if (visibleRows.length >= 1) {
                        const rect = visibleRows[0].row.getBoundingClientRect();
                        if (rect.height > 50 && rect.height < 300) {
                            return rect.height;
                        }
                    }
                    return DEFAULT_ROW_HEIGHT;
                };

                // 检测实际行高
                const ROW_HEIGHT = detectRowHeight();

                // 查找所有可能的滚动容器
                const findAllScrollContainers = () => {
                    const containers = [];

                    // 1. 尝试找 .main-container 或类似的容器
                    const mainContainer = document.querySelector('.main-container') ||
                                         document.querySelector('.app-main') ||
                                         document.querySelector('.el-main') ||
                                         document.querySelector('[class*="main"]');
                    if (mainContainer && mainContainer.scrollHeight > mainContainer.clientHeight) {
                        containers.push(mainContainer);
                    }

                    // 2. 从 recycleScroller 向上查找所有可滚动容器
                    if (recycleScroller) {
                        let parent = recycleScroller.parentElement;
                        while (parent && parent !== document.body && parent !== document.documentElement) {
                            const style = window.getComputedStyle(parent);
                            const overflowY = style.overflowY;
                            if ((overflowY === 'auto' || overflowY === 'scroll' || overflowY === 'overlay') &&
                                parent.scrollHeight > parent.clientHeight) {
                                if (!containers.includes(parent)) {
                                    containers.push(parent);
                                }
                            }
                            parent = parent.parentElement;
                        }
                    }

                    return containers;
                };

                // 滚动所有可能的容器
                const scrollAllContainers = async (delta) => {
                    const containers = findAllScrollContainers();

                    // 同时滚动所有容器
                    for (const container of containers) {
                        const oldScrollTop = container.scrollTop;
                        container.scrollTop += delta;
                        // 触发 scroll 事件
                        container.dispatchEvent(new Event('scroll', { bubbles: true }));
                    }

                    // 也尝试滚动 window
                    window.scrollBy({ top: delta, behavior: 'instant' });

                    // 模拟 wheel 事件(某些虚拟滚动库依赖此事件)
                    if (recycleScroller) {
                        const wheelEvent = new WheelEvent('wheel', {
                            deltaY: delta,
                            deltaMode: 0,
                            bubbles: true
                        });
                        recycleScroller.dispatchEvent(wheelEvent);
                    }

                    await new Promise(r => setTimeout(r, 400));
                };

                let selected = 0;
                const results = [];
                let debugInfo = { containers: findAllScrollContainers().length, detectedRowHeight: ROW_HEIGHT };

                // 根据可见行推断索引的辅助函数
                // 【第四轮修复】减去顶部偏移后再计算索引
                const TOP_OFFSET_Y = TOP_OFFSET_ROWS * ROW_HEIGHT;
                const inferRowIndex = (y) => {
                    return Math.round((y - TOP_OFFSET_Y) / ROW_HEIGHT);
                };

                for (const idx of indexes) {
                    // 【第四轮修复】加上顶部偏移
                    const targetTranslateY = idx * ROW_HEIGHT + TOP_OFFSET_Y;
                    let targetRow = null;
                    let matchedY = -1;
                    let attempts = 0;
                    let lastMaxY = -1;
                    let scrolledTotal = 0;

                    // 循环滚动直到目标行可见
                    while (!targetRow && attempts < MAX_SCROLL_ATTEMPTS) {
                        const visibleRows = getVisibleRows();

                        if (visibleRows.length === 0) {
                            attempts++;
                            await scrollAllContainers(ROW_HEIGHT * 3);
                            continue;
                        }

                        // 方法1: 基于Y坐标精确匹配(容差为行高的70%)
                        for (const item of visibleRows) {
                            const diff = Math.abs(item.y - targetTranslateY);
                            if (diff < ROW_HEIGHT * 0.7) {
                                targetRow = item.row;
                                matchedY = item.y;
                                break;
                            }
                        }

                        // 方法2: 基于推断索引匹配(更健壮的匹配方式)
                        if (!targetRow) {
                            for (const item of visibleRows) {
                                const inferredIdx = inferRowIndex(item.y);
                                if (inferredIdx === idx) {
                                    targetRow = item.row;
                                    matchedY = item.y;
                                    break;
                                }
                            }
                        }

                        if (targetRow) break;

                        // 目标行不可见,需要滚动
                        const maxVisibleY = Math.max(...visibleRows.map(r => r.y));
                        const minVisibleY = Math.min(...visibleRows.map(r => r.y));

                        if (targetTranslateY > maxVisibleY) {
                            // 目标在下方,向下滚动
                            let scrollAmount;
                            if (maxVisibleY === lastMaxY) {
                                // 滚动卡住,尝试更大的滚动量
                                scrollAmount = ROW_HEIGHT * 5;
                            } else {
                                scrollAmount = targetTranslateY - maxVisibleY + ROW_HEIGHT * 3;
                            }
                            await scrollAllContainers(scrollAmount);
                            scrolledTotal += scrollAmount;
                            lastMaxY = maxVisibleY;
                        } else if (targetTranslateY < minVisibleY) {
                            // 目标在上方,向上滚动
                            const scrollAmount = targetTranslateY - minVisibleY - ROW_HEIGHT * 2;
                            await scrollAllContainers(scrollAmount);
                            scrolledTotal += scrollAmount;
                        } else {
                            // 目标应该在范围内但没找到,微调
                            await scrollAllContainers(ROW_HEIGHT);
                            scrolledTotal += ROW_HEIGHT;
                        }

                        attempts++;
                    }

                    if (!targetRow) {
                        const finalVisibleRows = getVisibleRows();
                        results.push({
                            idx,
                            success: false,
                            error: 'Target row not found after scroll attempts',
                            visibleYs: finalVisibleRows.map(r => r.y),
                            inferredIdxs: finalVisibleRows.map(r => inferRowIndex(r.y)),
                            targetY: targetTranslateY,
                            detectedRowHeight: ROW_HEIGHT,
                            attempts,
                            scrolledTotal
                        });
                        continue;
                    }

                    // 在行内精确查找复选框(固定左侧选择列)
                    const checkbox = targetRow.querySelector('.is-selection-column .jx-checkbox__inner') ||
                                    targetRow.querySelector('.is-selection-column .jx-checkbox') ||
                                    targetRow.querySelector('.jx-checkbox__inner');

                    if (checkbox) {
                        checkbox.click();
                        selected++;
                        results.push({ idx, success: true, matchedY, attempts });
                    } else {
                        results.push({ idx, success: false, error: 'Checkbox not found', matchedY, attempts });
                    }
                }

                return { selected, isPageMode, results, debugInfo };
            }
            """
            result = await page.evaluate(js_code, indexes)
            selected = result.get("selected", 0)
            is_page_mode = result.get("isPageMode", False)
            debug_info = result.get("debugInfo", {})
            detected_row_height = debug_info.get("detectedRowHeight", "unknown")
            logger.debug(
                f"JS 批量勾选完成: {selected}/{len(indexes)}, "
                f"page-mode={is_page_mode}, 检测行高={detected_row_height}px"
            )

            # 输出失败项的详细信息
            for r in result.get("results", []):
                if not r.get("success"):
                    logger.debug(
                        f"  索引 {r.get('idx')} 失败: {r.get('error')}, "
                        f"目标Y={r.get('targetY')}, 检测行高={r.get('detectedRowHeight')}px, "
                        f"可见Y={r.get('visibleYs')}, 推断索引={r.get('inferredIdxs')}"
                    )

            return selected
        except Exception as exc:
            logger.debug(f"JS 批量勾选异常: {exc}")
            return 0

    async def _click_checkbox_by_js(self, page: Page, index: int) -> bool:
        """使用 JavaScript 滚动到目标位置并点击复选框.

        【第五轮重构】复用 _click_claim_button_in_row_by_js 的定位逻辑。
        """
        result = await self._click_claim_button_in_row_by_js(page, index, target="checkbox")
        return result.get("success", False)

    async def _click_claim_button_in_row_by_js(
        self,
        page: Page,
        index: int,
        *,
        target: str = "claim_button",
    ) -> dict[str, Any]:
        """使用 JavaScript 直接定位并点击行内目标元素(认领按钮或复选框).

        【第四轮重构】直接复用首次编辑的视觉位置定位逻辑:
        - 使用 getBoundingClientRect() 获取视觉位置
        - 使用 TOP_OFFSET_ROWS = 2 补偿顶部偏移
        - 使用 viewportStartIndex 和 firstFullyVisibleArrayIndex 定位

        Args:
            page: Playwright 页面对象
            index: 目标商品索引(全局索引,0-based)
            target: "claim_button" 或 "checkbox"

        Returns:
            包含操作结果的字典: {success, error?, scrollerInfo, matchedTop, ...}
        """
        try:
            js_code = """
            async ({ index, target }) => {
                const ROW_HEIGHT = 128;

                // 【第四轮修复】虚拟列表顶部偏移补偿（与首次编辑保持一致）
                const TOP_OFFSET_ROWS = 2;

                // 获取滚动容器
                const recycleScroller = document.querySelector('.vue-recycle-scroller');
                const isPageMode = recycleScroller && recycleScroller.classList.contains('page-mode');

                // 计算目标滚动位置
                const targetScrollTop = index * ROW_HEIGHT;

                let scrollerInfo = '';
                let actualScrollTop = 0;

                // 【第五轮修复】完全复制 navigation.py 的滚动逻辑
                if (isPageMode) {
                    scrollerInfo = 'page-mode';
                    let scrollParent = recycleScroller.parentElement;
                    let foundScrollable = false;

                    while (scrollParent && scrollParent !== document.body) {
                        const style = window.getComputedStyle(scrollParent);
                        const overflowY = style.overflowY;
                        if ((overflowY === 'auto' || overflowY === 'scroll') &&
                            scrollParent.scrollHeight > scrollParent.clientHeight) {
                            scrollParent.scrollTop = targetScrollTop;
                            await new Promise(r => setTimeout(r, 800));
                            actualScrollTop = scrollParent.scrollTop;
                            scrollerInfo = `parent: ${scrollParent.className.split(' ')[0] || scrollParent.tagName}`;
                            foundScrollable = true;
                            break;
                        }
                        scrollParent = scrollParent.parentElement;
                    }

                    if (!foundScrollable) {
                        window.scrollTo({ top: targetScrollTop, behavior: 'instant' });
                        await new Promise(r => setTimeout(r, 800));
                        actualScrollTop = window.scrollY || document.documentElement.scrollTop;
                        scrollerInfo = 'window';
                    }
                } else {
                    if (recycleScroller) {
                        recycleScroller.scrollTop = targetScrollTop;
                        await new Promise(r => setTimeout(r, 800));
                        actualScrollTop = recycleScroller.scrollTop;
                        scrollerInfo = 'vue-recycle-scroller';
                    }
                }

                // ========== 【第四轮重构】使用视觉位置定位（与首次编辑完全一致）==========

                // 【第五轮修复】直接使用所有行，不进行过滤（与 navigation.py 一致）
                const rows = Array.from(
                    document.querySelectorAll('.vue-recycle-scroller__item-view')
                );

                if (rows.length === 0) {
                    return {
                        success: false,
                        error: '没有找到商品行元素',
                        scrollerInfo,
                        isPageMode,
                        targetScrollTop,
                        actualScrollTop
                    };
                }

                // 【关键】使用视觉位置排序（getBoundingClientRect），而非 translateY
                const visibleRows = rows.map(row => {
                    const rect = row.getBoundingClientRect();
                    return {
                        row,
                        top: rect.top,
                        bottom: rect.bottom
                    };
                }).filter(r => {
                    // 过滤视口内的行（包括部分可见的）
                    return r.bottom > 0 && r.top < window.innerHeight + ROW_HEIGHT;
                }).sort((a, b) => a.top - b.top);  // 按视觉位置排序

                if (visibleRows.length === 0) {
                    return {
                        success: false,
                        error: '视口内没有可见的商品行',
                        scrollerInfo,
                        isPageMode,
                        targetScrollTop,
                        actualScrollTop,
                        totalRows: rows.length
                    };
                }

                // 【第四轮修复】修正虚拟列表顶部偏移
                const viewportStartIndex = Math.floor(actualScrollTop / ROW_HEIGHT) - TOP_OFFSET_ROWS;

                // 找到第一个完全可见的行（top >= 0）
                const firstFullyVisibleArrayIndex = visibleRows.findIndex(r => r.top >= 0);

                if (firstFullyVisibleArrayIndex === -1) {
                    return {
                        success: false,
                        error: '没有完全可见的行（所有行 top < 0）',
                        scrollerInfo,
                        isPageMode,
                        targetScrollTop,
                        actualScrollTop,
                        allTops: visibleRows.map(r => Math.round(r.top))
                    };
                }

                // 目标行在可见行数组中的索引 = (目标索引 - 视口起始索引) + 缓冲行数量
                const targetArrayIndex = (index - viewportStartIndex) + firstFullyVisibleArrayIndex;

                // 调试信息（与 navigation.py 一致）
                const debugInfo = {
                    topOffsetRows: TOP_OFFSET_ROWS,
                    viewportStartIndex,
                    firstFullyVisibleArrayIndex,
                    targetArrayIndex,
                    visibleRowCount: visibleRows.length,
                    actualScrollTop,
                    firstRowTop: Math.round(visibleRows[0].top),
                    firstFullyVisibleTop: Math.round(visibleRows[firstFullyVisibleArrayIndex].top),
                    allTops: visibleRows.map(r => Math.round(r.top))
                };

                // 边界检查
                if (targetArrayIndex < 0) {
                    return {
                        success: false,
                        error: `目标行在视口上方: targetArrayIndex=${targetArrayIndex} < 0`,
                        scrollerInfo,
                        isPageMode,
                        targetScrollTop,
                        ...debugInfo
                    };
                }

                if (targetArrayIndex >= visibleRows.length) {
                    return {
                        success: false,
                        error: `目标行在视口下方: targetArrayIndex=${targetArrayIndex} >= visibleRows=${visibleRows.length}`,
                        scrollerInfo,
                        isPageMode,
                        targetScrollTop,
                        ...debugInfo
                    };
                }

                // 定位目标行
                const targetRow = visibleRows[targetArrayIndex].row;
                const matchedTop = visibleRows[targetArrayIndex].top;

                // 如果只需要点击复选框,直接处理后返回
                if (target === 'checkbox') {
                    // 【第十二轮修复】点击 label 元素而不是空的 span
                    // .jx-checkbox__inner 是空的视觉样式 span，可能没有点击事件
                    // 应该点击 label.jx-checkbox 来触发复选框

                    // 获取行内的复选框 label 元素（排除表头）
                    const allCheckboxLabels = Array.from(
                        document.querySelectorAll('.vue-recycle-scroller__item-view label.jx-checkbox')
                    );

                    if (allCheckboxLabels.length === 0) {
                        return {
                            success: false,
                            error: 'No checkbox labels found on page',
                            scrollerInfo,
                            matchedTop: Math.round(matchedTop),
                            ...debugInfo
                        };
                    }

                    // 按视觉位置排序，与 visibleRows 使用相同的逻辑
                    const visibleCheckboxes = allCheckboxLabels.map(label => {
                        const rect = label.getBoundingClientRect();
                        return { label, top: rect.top };
                    }).filter(c => {
                        // 使用与 visibleRows 相同的过滤条件
                        return c.top > -ROW_HEIGHT && c.top < window.innerHeight + ROW_HEIGHT;
                    }).sort((a, b) => a.top - b.top);

                    const cbDebugInfo = {
                        ...debugInfo,
                        totalCheckboxes: allCheckboxLabels.length,
                        visibleCbCount: visibleCheckboxes.length,
                        matchedTop: Math.round(matchedTop),
                        cbTops: visibleCheckboxes.map(c => Math.round(c.top))
                    };

                    // 用相同的 targetArrayIndex 取复选框
                    if (targetArrayIndex < 0 || targetArrayIndex >= visibleCheckboxes.length) {
                        return {
                            success: false,
                            error: `Checkbox index out of range: ${targetArrayIndex} (0-${visibleCheckboxes.length-1})`,
                            scrollerInfo,
                            ...cbDebugInfo
                        };
                    }

                    const targetCheckbox = visibleCheckboxes[targetArrayIndex];

                    try {
                        // 点击 label 触发复选框
                        targetCheckbox.label.click();
                        return {
                            success: true,
                            scrollerInfo,
                            matchedTop: Math.round(matchedTop),
                            cbTop: Math.round(targetCheckbox.top),
                            cbArrayIndex: targetArrayIndex,
                            matchMethod: 'checkbox-label-click',
                            ...cbDebugInfo
                        };
                    } catch (e) {
                        return {
                            success: false,
                            error: 'Checkbox label click failed: ' + e.message,
                            scrollerInfo,
                            matchedTop: Math.round(matchedTop),
                            ...cbDebugInfo
                        };
                    }
                }

                // 在行内查找"认领到"按钮
                // 选择器优先级:包含"认领到"文本的按钮
                const claimBtnSelectors = [
                    'button.jx-button.is-text span:has-text("认领到")',
                    'button.pro-button.is-text',
                    'button[aria-haspopup="menu"]',
                    '.jx-tooltip__trigger.pro-button',
                ];

                let claimBtn = null;

                // 方法1: 通过文本内容查找
                const allButtons = targetRow.querySelectorAll('button');
                for (const btn of allButtons) {
                    const text = btn.textContent || '';
                    if (text.includes('认领到')) {
                        claimBtn = btn;
                        break;
                    }
                }

                // 方法2: 通过选择器查找
                if (!claimBtn) {
                    for (const selector of claimBtnSelectors) {
                        try {
                            const found = targetRow.querySelector(selector);
                            if (found) {
                                claimBtn = found.closest('button') || found;
                                break;
                            }
                        } catch (e) {}
                    }
                }

                if (!claimBtn) {
                    return {
                        success: false,
                        error: 'Claim button not found in target row',
                        scrollerInfo,
                        matchedTop: Math.round(matchedTop),
                        buttonsFound: allButtons.length,
                        ...debugInfo
                    };
                }

                // 获取按钮关联的下拉菜单 ID(通过 aria-controls 属性)
                const ariaControls = claimBtn.getAttribute('aria-controls');

                // 模拟鼠标悬浮在"认领到"按钮上(hover 触发下拉菜单)
                const hoverEvents = ['mouseenter', 'mouseover', 'pointerenter'];
                for (const eventType of hoverEvents) {
                    const event = new MouseEvent(eventType, {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    claimBtn.dispatchEvent(event);
                }

                // 等待下拉菜单出现(hover 触发需要时间)
                await new Promise(r => setTimeout(r, 600));

                // 优先通过 aria-controls 关联的 ID 查找下拉菜单
                let dropdown = null;

                if (ariaControls) {
                    // 通过 ID 精确定位关联的下拉菜单
                    dropdown = document.getElementById(ariaControls);
                    if (dropdown && dropdown.offsetParent === null) {
                        // 菜单存在但不可见,再等待一下
                        await new Promise(r => setTimeout(r, 400));
                        dropdown = document.getElementById(ariaControls);
                    }
                }

                // 如果通过 aria-controls 找不到,使用备用选择器
                if (!dropdown || dropdown.offsetParent === null) {
                    const dropdownSelectors = [
                        '.el-dropdown-menu:not([style*="display: none"])',
                        '.jx-dropdown-menu:not([style*="display: none"])',
                        '.pro-dropdown__menu:not([style*="display: none"])',
                        '[role="menu"][aria-hidden="false"]',
                        '.jx-popper[aria-hidden="false"]',
                    ];

                    for (const selector of dropdownSelectors) {
                        const found = document.querySelector(selector);
                        if (found && found.offsetParent !== null) {
                            dropdown = found;
                            break;
                        }
                    }
                }

                // 如果仍未出现,下拉可能需要点击触发,尝试点击后再查找
                if (!dropdown || dropdown.offsetParent === null) {
                    try {
                        claimBtn.click();
                        await new Promise(r => setTimeout(r, 500));
                    } catch (e) {}

                    const clickDropdownSelectors = [
                        '.el-dropdown-menu:not([style*="display: none"])',
                        '.jx-dropdown-menu:not([style*="display: none"])',
                        '.pro-dropdown__menu:not([style*="display: none"])',
                        '[role="menu"][aria-hidden="false"]',
                        '.jx-popper[aria-hidden="false"]',
                    ];

                    for (const selector of clickDropdownSelectors) {
                        const found = document.querySelector(selector);
                        if (found && found.offsetParent !== null) {
                            dropdown = found;
                            break;
                        }
                    }
                }

                if (!dropdown) {
                    return {
                        success: false,
                        error: 'Dropdown menu not found after clicking claim button',
                        scrollerInfo,
                        matchedTop: Math.round(matchedTop),
                        claimBtnClicked: true,
                        ariaControls: ariaControls || 'none',
                        ...debugInfo
                    };
                }

                // 点击下拉菜单的第一个选项(应该是 "Temu全托管" 之类的)
                const optionSelectors = [
                    '.el-dropdown-menu__item',
                    '.jx-dropdown-menu__item',
                    '[role="menuitem"]',
                    'li',
                ];

                let firstOption = null;
                for (const selector of optionSelectors) {
                    const options = dropdown.querySelectorAll(selector);
                    if (options.length > 0) {
                        firstOption = options[0];
                        break;
                    }
                }

                if (!firstOption) {
                    return {
                        success: false,
                        error: 'No option found in dropdown menu',
                        scrollerInfo,
                        matchedTop: Math.round(matchedTop),
                        claimBtnClicked: true,
                        dropdownFound: true,
                        dropdownId: dropdown.id || 'unknown',
                        ...debugInfo
                    };
                }

                // 点击第一个选项
                firstOption.click();

                return {
                    success: true,
                    scrollerInfo,
                    isPageMode,
                    targetScrollTop,
                    actualScrollTop,
                    matchedTop: Math.round(matchedTop),
                    matchMethod: 'visual-position',
                    optionText: firstOption.textContent?.trim() || '',
                    ...debugInfo
                };
            }
            """

            result = await page.evaluate(js_code, {"index": index, "target": target})

            if result.get("success"):
                if target == "checkbox":
                    logger.success(
                        f"✓ [视觉位置定位] 勾选成功, index={index}, "
                        f"topOffset={result.get('topOffsetRows')}行, "
                        f"viewportStartIndex={result.get('viewportStartIndex')}, "
                        f"bufferRows={result.get('firstFullyVisibleArrayIndex')}, "
                        f"targetArrayIndex={result.get('targetArrayIndex')}, "
                        f"可见行数={result.get('visibleRowCount')}, "
                        f"matchedTop={result.get('matchedTop')}px"
                    )
                else:
                    logger.success(
                        f"✓ [视觉位置定位] 认领按钮成功, index={index}, "
                        f"topOffset={result.get('topOffsetRows')}行, "
                        f"viewportStartIndex={result.get('viewportStartIndex')}, "
                        f"matchedTop={result.get('matchedTop')}px, "
                        f"选项={result.get('optionText')}"
                    )
            else:
                logger.warning(
                    f"[视觉位置定位] 操作失败: {result.get('error')}, "
                    f"index={index}, topOffset={result.get('topOffsetRows')}行, "
                    f"viewportStartIndex={result.get('viewportStartIndex')}, "
                    f"bufferRows={result.get('firstFullyVisibleArrayIndex')}, "
                    f"targetArrayIndex={result.get('targetArrayIndex')}, "
                    f"可见行数={result.get('visibleRowCount')}, "
                    f"tops={result.get('allTops')}"
                )

            return result

        except Exception as exc:
            logger.warning(f"JS 点击认领按钮异常: {exc}")
            return {"success": False, "error": str(exc)}

    async def claim_products_by_row_js(
        self,
        page: Page,
        indexes: Sequence[int],
        *,
        repeat_per_product: int = 5,
    ) -> tuple[int, int, int]:
        """使用 JS 定位逻辑逐行认领商品.

        复用首次编辑的定位逻辑,对每个索引:
        1. 滚动到目标行
        2. 点击该行的"认领到"按钮
        3. 选择下拉菜单第一项
        4. 重复 repeat_per_product 次

        Args:
            page: Playwright 页面对象
            indexes: 要认领的商品索引列表
            repeat_per_product: 每个商品点击认领的次数(默认5次)

        Returns:
            (成功商品数, 失败商品数, 成功点击总数) 元组
        """
        success_count = 0
        fail_count = 0
        total_click_success = 0
        waiter = PageWaiter(page)

        async def _wait_for_virtual_list_ready() -> bool:
            """等待虚拟滚动列表重新加载完成."""
            for _ in range(10):  # 最多等待 5 秒
                try:
                    has_rows = await page.evaluate("""
                        () => {
                            const rows = document.querySelectorAll('.vue-recycle-scroller__item-view');
                            let visibleCount = 0;
                            rows.forEach(row => {
                                const style = row.getAttribute('style') || '';
                                const match = style.match(/translateY\\((-?\\d+(?:\\.\\d+)?)\\s*(?:px)?\\s*\\)/);
                                if (match && parseFloat(match[1]) >= 0) visibleCount++;
                            });
                            return visibleCount > 0;
                        }
                    """)
                    if has_rows:
                        return True
                except Exception:
                    pass
                await waiter.wait_for_dom_stable(timeout_ms=500)
            return False

        for idx in indexes:
            logger.info(f"正在认领索引 {idx} 的商品(共 {repeat_per_product} 次)...")
            product_success = 0
            current_idx = idx

            for click_num in range(repeat_per_product):
                # 每次点击前确保虚拟列表已加载
                if click_num > 0 and not await _wait_for_virtual_list_ready():
                    logger.warning(f"索引 {idx} 第 {click_num + 1} 次: 虚拟列表未就绪,尝试继续")

                result = await self._click_claim_button_in_row_by_js(page, current_idx)

                if result.get("success"):
                    product_success += 1
                    total_click_success += 1
                    logger.debug(
                        f"索引 {idx} 第 {click_num + 1}/{repeat_per_product} 次认领成功, "
                        f"选项={result.get('optionText')}"
                    )
                    await waiter.wait_for_dom_stable(timeout_ms=800)
                    # 认领后行可能移除,后续固定使用首行索引防止漂移
                    current_idx = 0
                else:
                    logger.warning(
                        f"索引 {idx} 第 {click_num + 1}/{repeat_per_product} 次认领失败: "
                        f"{result.get('error')}"
                    )
                    await waiter.wait_for_dom_stable(timeout_ms=500)
                    await _wait_for_virtual_list_ready()
                    # 失败后同样使用首行索引尝试
                    current_idx = 0

            if product_success == repeat_per_product:
                success_count += 1
                logger.success(
                    f"✓ 索引 {idx} 认领完成: {product_success}/{repeat_per_product} 次成功"
                )
            else:
                fail_count += 1
                logger.error(
                    f"✗ 索引 {idx} 认领未达标: {product_success}/{repeat_per_product} 次成功"
                )

            # 每个商品处理完后,等待页面稳定再处理下一个
            await _wait_for_virtual_list_ready()

        logger.info(
            f"批量认领完成: 成功商品={success_count}, 失败商品={fail_count}, "
            f"成功点击总数={total_click_success}, 每商品点击={repeat_per_product}次"
        )
        return success_count, fail_count, total_click_success

    async def select_products_by_row_js(
        self,
        page: Page,
        indexes: Sequence[int],
    ) -> tuple[int, int]:
        """使用 JS 逐行勾选复选框(复用行定位逻辑)."""

        success_count = 0
        fail_count = 0
        waiter = PageWaiter(page)

        async def _wait_for_virtual_list_ready() -> bool:
            for _ in range(10):
                try:
                    has_rows = await page.evaluate("""
                        () => {
                            const rows = document.querySelectorAll('.vue-recycle-scroller__item-view');
                            let visibleCount = 0;
                            rows.forEach(row => {
                                const style = row.getAttribute('style') || '';
                                const match = style.match(/translateY\\((-?\\d+(?:\\.\\d+)?)\\s*(?:px)?\\s*\\)/);
                                if (match && parseFloat(match[1]) >= 0) visibleCount++;
                            });
                            return visibleCount > 0;
                        }
                    """)
                    if has_rows:
                        return True
                except Exception:
                    pass
                await waiter.wait_for_dom_stable(timeout_ms=300)
            return False

        for idx in indexes:
            logger.info(f"勾选索引 {idx} 的商品复选框...")
            selected = False
            index_not_found = False  # 标记索引是否不存在于页面中

            for attempt in range(2):
                if attempt > 0:
                    await _wait_for_virtual_list_ready()
                result = await self._click_claim_button_in_row_by_js(
                    page,
                    idx,  # 始终使用原始索引，不要重置
                    target="checkbox",
                )
                if result.get("success"):
                    selected = True
                    break
                # 检查是否因为索引不存在而失败
                error_msg = result.get("error", "")
                if "not found in visible rows" in error_msg:
                    index_not_found = True
                    logger.info(f"索引 {idx} 不存在于页面中，已到达列表末尾")
                    break
                logger.warning(f"索引 {idx} 第 {attempt + 1} 次勾选失败: {error_msg}")
                await waiter.wait_for_dom_stable(timeout_ms=300)

            if selected:
                success_count += 1
            elif index_not_found:
                # 索引不存在，提前终止勾选循环
                logger.info(f"检测到列表末尾，提前终止勾选。已成功勾选 {success_count} 个")
                break
            else:
                fail_count += 1

            await _wait_for_virtual_list_ready()

        logger.info(f"复选框勾选完成: 成功={success_count}, 失败={fail_count}")
        return success_count, fail_count

    async def _find_row_by_translate_y(self, page: Page, index: int):
        """通过 translateY 值定位 vue-recycle-scroller 中的行.

        vue-recycle-scroller 使用 transform: translateY(N*ROW_HEIGHT) 来定位行.
        滚动后,目标行的 translateY 应该接近 0(在视口顶部).

        Args:
            page: Playwright 页面对象
            index: 目标商品索引

        Returns:
            找到的行 Locator,或 None
        """
        import re

        try:
            virtual_rows = page.locator(self._VIRTUAL_ROW_SELECTOR)
            count = await virtual_rows.count()
            logger.debug(f"虚拟滚动行总数: {count}")

            if count == 0:
                return None

            # 找到 translateY 最小且 >= 0 的行(视口中的第一行)
            min_translate_y = float("inf")
            target_row = None

            for i in range(count):
                row = virtual_rows.nth(i)
                try:
                    style = await row.get_attribute("style") or ""
                    # 解析 translateY 值
                    match = re.search(r"translateY\((-?\d+(?:\.\d+)?)\s*(?:px)?\s*\)", style)
                    translate_y = float(match.group(1)) if match else -9999

                    # 跳过被回收的行(translateY = -9999px)
                    if translate_y < 0:
                        continue

                    # 找 translateY 最小的行
                    if translate_y < min_translate_y:
                        min_translate_y = translate_y
                        target_row = row
                except Exception:
                    continue

            if target_row:
                logger.debug(f"找到目标行,translateY={min_translate_y}px")
                return target_row.locator(self._ROW_SELECTOR).first

            return None
        except Exception as exc:
            logger.debug(f"通过 translateY 定位失败: {exc}")
            return None

    async def _find_first_visible_row(self, page: Page):
        """找到视口内的第一个可见行."""
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
            logger.debug("Unable to hover selection cell directly; fallback to row hover")
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

    @ensure_page_loaded(LoadState.DOMCONTENTLOADED, PAGE_TIMEOUTS.FAST)
    async def _click_claim_confirmation_button(self, page: Page) -> bool:
        """Attempt to click the visible confirmation button after the claim dialog appears.

        Args:
            page: Active Playwright page instance.

        Returns:
            True if a visible confirmation button was clicked successfully, otherwise False.
        """

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
                logger.debug(f"确认弹窗 wrapper[{wrapper_idx}] 可见性检查失败: {exc}")

        for scope_name, scope in candidate_scopes:
            scope_candidates: list[tuple[str, Locator]] = []

            if hasattr(scope, "get_by_role"):
                with suppress(Exception):
                    exact_confirm = scope.get_by_role("button", name="确定", exact=True)
                    scope_candidates.append(("role=button(name='确定', exact=True)", exact_confirm))
                with suppress(Exception):
                    fuzzy_confirm = scope.get_by_role("button", name="确定", exact=False)
                    scope_candidates.append(("role=button(name~='确定')", fuzzy_confirm))
                with suppress(Exception):
                    confirm_trimmed = scope.locator("button").filter(
                        has_text=re.compile(r"\s*确定\s*")
                    )
                    scope_candidates.append(("button:trimmed-text='确定'", confirm_trimmed))

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
                        f"确认弹窗候选按钮定位异常: scope={scope_name} selector={selector} error={exc}"
                    )
                    continue

                if count == 0:
                    continue

                logger.debug(
                    f"确认弹窗候选按钮: scope={scope_name} selector={selector} count={count}"
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

                    with suppress(Exception):
                        await button.scroll_into_view_if_needed()

                    try:
                        if not await button.is_enabled():
                            logger.debug(
                                f"确认弹窗按钮不可用: scope={scope_name} "
                                f"selector={selector} index={idx} text={text}"
                            )
                            continue
                    except Exception as exc:
                        logger.debug(
                            f"确认弹窗按钮可用性检查失败: scope={scope_name} "
                            f"selector={selector} index={idx} error={exc}"
                        )

                    try:
                        await button.click(force=True)
                        logger.debug(
                            f"认领确认按钮通过 {selector} (scope={scope_name} "
                            f"index={idx} text={text}) 点击成功"
                        )
                        return True
                    except Exception as exc:
                        logger.debug(
                            f"点击确认按钮失败: scope={scope_name} selector={selector} "
                            f"index={idx} text={text} error={exc}"
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
                                    spans_locator = page.locator("span").filter(
                                        has_text=dropdown_text
                                    )
                                    if await spans_locator.count():
                                        temu_option = spans_locator.first
                                        logger.debug(
                                            f"通过 span.filter(has_text='{dropdown_text}') 获取到 Temu 下拉项"
                                        )
                                        break
                                for frame in page.frames:
                                    with suppress(Exception):
                                        frame_spans = frame.locator("span").filter(
                                            has_text=dropdown_text
                                        )
                                        if await frame_spans.count():
                                            temu_option = frame_spans.first
                                            logger.debug(
                                                f"通过 frame span.filter(has_text='{dropdown_text}') 获取到 Temu 下拉项 "
                                                f"(frame={frame.url})"
                                            )
                                            break
                                if temu_option is not None:
                                    break
                            if temu_option is not None:
                                break

                            logger.debug(
                                "未立即找到下拉菜单项,尝试第 {} 次点击按钮展开", attempt + 1
                            )
                            await claim_button.click(force=True)
                            await self._wait_for_claim_dropdown(page, state="visible", timeout=300)

                    if temu_option is None:
                        raise RuntimeError("未找到'Temu全托管'菜单项")

                    await temu_option.click(force=True)
                    await self._wait_for_claim_dropdown(page, state="hidden", timeout=300)
                    temu_destination_selected = True
                else:
                    logger.debug("Temu全托管已在首次迭代选定,跳过下拉菜单点击")
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
                logger.warning(f"认领流程已成功执行 {success_count}/{repeat} 次,仍有部分尝试失败")
            else:
                logger.success("简化版认领流程执行完成")
            return True

        if last_error is None:
            logger.error(f"认领流程在连续 {repeat} 次尝试后仍未成功: 未知错误")
        else:
            logger.error(f"认领流程在连续 {repeat} 次尝试后仍未成功: {last_error}")
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

        # 提取所有进度选择器用于 _progress_completed 函数
        progress_selectors = [".el-progress__text"]

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
                                f"认领进度弹窗 wrapper 可见: selector={selector} index={idx}"
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

            # 尝试关闭弹窗,最多重试3次
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
                        await page.wait_for_selector(
                            button_selector, state="visible", timeout=1_000
                        )
                    close_button = await self._locate_progress_close_button(dialog)
                    if close_button is None:
                        close_button = await self._locate_progress_close_button(page)

                if close_button is None:
                    logger.debug(
                        f"认领进度弹窗无法定位'关闭'按钮 "
                        f"progress_ready={progress_ready} attempt={attempt + 1}/{max_retries}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    return False

                with suppress(Exception):
                    await close_button.scroll_into_view_if_needed()
                with suppress(Exception):
                    await close_button.hover()

                try:
                    await close_button.click(force=True)
                except Exception as exc:
                    logger.debug(
                        f"点击认领进度弹窗关闭按钮失败 attempt={attempt + 1}/{max_retries}: {exc}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    return False

                dialog_closed = False
                try:
                    await dialog.wait_for(state="hidden", timeout=1_200)
                    dialog_closed = True
                except PlaywrightTimeoutError:
                    logger.debug("认领进度弹窗未立即隐藏,尝试等待 DOM 移除")
                    with suppress(PlaywrightTimeoutError):
                        await dialog.wait_for(state="detached", timeout=1_000)
                        dialog_closed = True

                if dialog_closed:
                    logger.debug("认领进度弹窗关闭成功 attempt={}/{}", attempt + 1, max_retries)
                    return True

                logger.debug(
                    "认领进度弹窗关闭失败,准备重试 attempt={}/{}", attempt + 1, max_retries
                )

            logger.debug("认领进度弹窗关闭失败,已达最大重试次数")
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
                        f"认领进度弹窗关闭按钮通过 role 定位成功: name={role_name} aria-label={acc_name}"
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
                logger.debug("定位到关闭按钮但不属于批量认领弹窗,跳过")
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
        logger.info(f"Verifying claim result, expecting at least {expected_count} items")

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
                f"Claim verification failed: claimed={claimed_count} expected>={expected_count}"
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
                    logger.warning(
                        "User filter could not be applied via selectors, trying fallback"
                    )
                    filter_applied = await fallback_apply_user_filter(page, filter_by_user)
                    if not filter_applied:
                        logger.warning(
                            "Fallback user filter also failed, continuing without filter"
                        )
            else:
                logger.info("Step 2: skip user filter")

            logger.info(f"Step 3: switch to tab {switch_to_tab}")
            await self._wait_for_table_refresh(page)

            # 等待可能的tab容器出现
            try:
                await page.wait_for_selector(
                    "button, [role='tab'], .jx-radio-button, .jx-tabs__item",
                    state="visible",
                    timeout=1_500,
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
        except SessionExpiredError:
            # Session expired exception needs to propagate up for re-login handling
            raise
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
                            f"找到下拉菜单项: selector={selector}, index={idx}, text={await target.inner_text()}"
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
                        f"通过 get_by_label('认领到') 定位到 Temu 选项: pattern={pattern.pattern}"
                    )
                    return candidate.first
        except Exception as exc:
            logger.debug(f"通过 label 定位 Temu 选项失败: {exc}")

        return None

    # ==================== API-based Claim Methods ====================

    async def claim_products_via_api(
        self,
        page: Page,
        *,
        count: int = 10,
        platform: str = "pddkj",
        owner_account: str | None = None,
    ) -> dict[str, Any]:
        """使用 API 直接认领产品（绕过浏览器虚拟列表定位）.

        这是浏览器自动化认领的替代方案，直接调用后端 API：
        - 更快速：无需操作 DOM
        - 更稳定：避免虚拟列表定位问题
        - 支持批量：一次请求认领多个产品

        Args:
            page: Playwright 页面对象（用于获取 Cookie）
            count: 要认领的产品数量
            platform: 平台代码 ("pddkj" = Temu全托管)
            owner_account: 创建人员筛选

        Returns:
            包含认领结果的字典:
            - success: 是否成功
            - claimed_count: 认领数量
            - message: 结果消息
            - detail_ids: 认领的产品 ID 列表

        Examples:
            >>> result = await controller.claim_products_via_api(page, count=5)
            >>> print(f"成功认领 {result['claimed_count']} 个产品")
        """
        from .api_client import MiaoshouApiClient

        try:
            # 从页面上下文获取 cookies
            context = page.context
            client = await MiaoshouApiClient.from_playwright_context(context)

            async with client:
                result = await client.claim_unclaimed_products(
                    count=count,
                    platform=platform,
                    owner_account=owner_account,
                )

            if result.get("success"):
                logger.success(f"API 认领完成: {result.get('claimed_count', 0)} 个产品")
            else:
                logger.warning(f"API 认领失败: {result.get('message', '未知错误')}")

            return result

        except Exception as exc:
            logger.error(f"API 认领异常: {exc}")
            return {
                "success": False,
                "message": str(exc),
                "claimed_count": 0,
            }

    async def claim_specific_products_via_api(
        self,
        page: Page,
        *,
        detail_ids: list[str],
        platform: str = "pddkj",
    ) -> dict[str, Any]:
        """使用 API 认领指定的产品列表.

        Args:
            page: Playwright 页面对象（用于获取 Cookie）
            detail_ids: 采集箱产品 ID 列表
            platform: 平台代码

        Returns:
            API 响应结果

        Examples:
            >>> result = await controller.claim_specific_products_via_api(
            ...     page,
            ...     detail_ids=["3049643700", "3049643667"]
            ... )
        """
        from .api_client import MiaoshouApiClient

        try:
            context = page.context
            client = await MiaoshouApiClient.from_playwright_context(context)

            async with client:
                api_result = await client.claim_products(
                    detail_ids=detail_ids,
                    platform=platform,
                )

            # 兼容两种响应格式
            success = api_result.get("result") == "success" or api_result.get("code") == 0
            if success:
                logger.success(f"API 认领成功: {len(detail_ids)} 个产品")
            else:
                logger.warning(f"API 认领失败: {api_result.get('message')}")

            return {
                "success": success,
                "message": api_result.get("message", ""),
                "claimed_count": len(detail_ids) if success else 0,
                "detail_ids": detail_ids,
                "api_response": api_result,
            }

        except Exception as exc:
            logger.error(f"API 认领异常: {exc}")
            return {
                "success": False,
                "message": str(exc),
                "claimed_count": 0,
            }

    async def extract_product_ids_from_dom(
        self,
        page: Page,
        *,
        count: int = 10,
    ) -> list[str]:
        """从页面 DOM 中提取产品 ID 列表.

        在 DOM 筛选人员后调用此方法，从当前页面提取产品 ID。
        支持虚拟列表滚动加载，确保能提取足够数量的产品ID。

        Args:
            page: Playwright 页面对象
            count: 需要提取的产品数量

        Returns:
            产品 ID 列表
        """
        row_height = 128  # 虚拟列表每行高度
        max_scroll_attempts = 20  # 最大滚动次数，防止无限循环
        scroll_step = row_height * 5  # 每次滚动5行的高度

        try:
            # 收集所有产品ID（通过滚动虚拟列表）
            all_ids: list[str] = []
            seen_ids: set[str] = set()

            logger.info(f"开始滚动虚拟列表提取产品 ID，目标数量: {count}")

            # 首先检测滚动容器
            scroller_info = await page.evaluate(
                """() => {
                    // 查找 vue-recycle-scroller 及其可滚动的父元素
                    const scroller = document.querySelector('.vue-recycle-scroller');
                    if (!scroller) return { found: false };

                    // 检查 scroller 本身
                    const scrollerInfo = {
                        scrollHeight: scroller.scrollHeight,
                        clientHeight: scroller.clientHeight,
                        canScroll: scroller.scrollHeight > scroller.clientHeight + 10
                    };

                    // 向上查找可滚动的父元素
                    let parent = scroller.parentElement;
                    let scrollableParent = null;
                    let depth = 0;
                    while (parent && depth < 10) {
                        if (parent.scrollHeight > parent.clientHeight + 10) {
                            const style = window.getComputedStyle(parent);
                            const overflow = style.overflowY;
                            if (overflow === 'auto' || overflow === 'scroll') {
                                scrollableParent = {
                                    tagName: parent.tagName,
                                    className: parent.className.slice(0, 50),
                                    scrollHeight: parent.scrollHeight,
                                    clientHeight: parent.clientHeight,
                                    depth: depth
                                };
                                break;
                            }
                        }
                        parent = parent.parentElement;
                        depth++;
                    }

                    return {
                        found: true,
                        scroller: scrollerInfo,
                        scrollableParent
                    };
                }"""
            )

            logger.debug(f"滚动容器检测: {scroller_info}")

            for scroll_attempt in range(max_scroll_attempts):
                # 从当前可见行提取产品ID
                result = await page.evaluate(
                    """() => {
                        const ids = [];
                        const debug = { rowCount: 0, scrollTop: 0 };

                        const scroller = document.querySelector('.vue-recycle-scroller');
                        if (scroller) {
                            debug.scrollTop = scroller.scrollTop;
                        }

                        const rows = document.querySelectorAll('.vue-recycle-scroller__item-view');
                        debug.rowCount = rows.length;

                        for (const row of rows) {
                            const text = row.textContent || '';
                            const match = text.match(/采集箱产品ID[：:]\\s*(\\d+)/);
                            if (match && match[1]) {
                                ids.push(match[1]);
                            }
                        }

                        return { ids, debug };
                    }"""
                )

                new_ids = result.get("ids", [])
                debug_info = result.get("debug", {})

                # 添加新发现的ID
                added_count = 0
                for pid in new_ids:
                    if pid not in seen_ids:
                        seen_ids.add(pid)
                        all_ids.append(pid)
                        added_count += 1

                logger.debug(
                    f"滚动 {scroll_attempt + 1}: "
                    f"行数={debug_info.get('rowCount')}, "
                    f"scrollTop={debug_info.get('scrollTop')}, "
                    f"新增={added_count}, "
                    f"累计={len(all_ids)}"
                )

                # 检查是否已收集足够数量
                if len(all_ids) >= count:
                    logger.info(f"已收集到足够的产品 ID: {len(all_ids)} >= {count}")
                    break

                # 滚动虚拟列表加载更多 - 尝试多种滚动方式
                scroll_result = await page.evaluate(
                    """(scrollStep) => {
                        // 查找可滚动的容器
                        const scroller = document.querySelector('.vue-recycle-scroller');
                        if (!scroller) return { scrolled: false, reason: 'no_scroller' };

                        // 方法1: 尝试滚动 scroller 本身
                        let targetElement = scroller;
                        let maxScroll = scroller.scrollHeight - scroller.clientHeight;

                        // 如果 scroller 不可滚动，查找可滚动的父元素
                        if (maxScroll <= 10) {
                            let parent = scroller.parentElement;
                            let depth = 0;
                            while (parent && depth < 10) {
                                const parentMax = parent.scrollHeight - parent.clientHeight;
                                if (parentMax > 10) {
                                    const style = window.getComputedStyle(parent);
                                    if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
                                        targetElement = parent;
                                        maxScroll = parentMax;
                                        break;
                                    }
                                }
                                parent = parent.parentElement;
                                depth++;
                            }
                        }

                        const oldScrollTop = targetElement.scrollTop;

                        // 检查是否已到底部
                        if (oldScrollTop >= maxScroll - 10) {
                            return {
                                scrolled: false,
                                reason: 'at_bottom',
                                maxScroll,
                                oldScrollTop,
                                element: targetElement.className.slice(0, 30)
                            };
                        }

                        // 执行滚动
                        targetElement.scrollTop = Math.min(oldScrollTop + scrollStep, maxScroll);

                        return {
                            scrolled: true,
                            oldScrollTop,
                            newScrollTop: targetElement.scrollTop,
                            maxScroll,
                            element: targetElement.className.slice(0, 30)
                        };
                    }""",
                    scroll_step,
                )

                if not scroll_result.get("scrolled"):
                    reason = scroll_result.get("reason", "unknown")
                    logger.debug(
                        f"停止滚动: {reason}, "
                        f"maxScroll={scroll_result.get('maxScroll')}, "
                        f"scrollTop={scroll_result.get('oldScrollTop')}, "
                        f"element={scroll_result.get('element')}"
                    )
                    break
                else:
                    logger.debug(
                        f"滚动成功: {scroll_result.get('oldScrollTop')} -> "
                        f"{scroll_result.get('newScrollTop')} / {scroll_result.get('maxScroll')}, "
                        f"element={scroll_result.get('element')}"
                    )

                # 等待虚拟列表更新DOM
                await page.wait_for_timeout(300)

            logger.info(f"从 DOM 提取到 {len(all_ids)} 个产品 ID")
            if all_ids:
                logger.debug(f"产品 ID 列表: {all_ids[:10]}...")

            # 滚动回顶部，恢复初始状态
            await page.evaluate(
                """() => {
                    const scroller = document.querySelector('.vue-recycle-scroller');
                    if (!scroller) return;

                    // 重置 scroller
                    scroller.scrollTop = 0;

                    // 也重置可能的父滚动容器
                    let parent = scroller.parentElement;
                    let depth = 0;
                    while (parent && depth < 10) {
                        if (parent.scrollTop > 0) {
                            parent.scrollTop = 0;
                        }
                        parent = parent.parentElement;
                        depth++;
                    }
                }"""
            )
            await page.wait_for_timeout(200)

            return all_ids[:count] if len(all_ids) > count else all_ids

        except Exception as exc:
            logger.error(f"从 DOM 提取产品 ID 失败: {exc}")
            return []
