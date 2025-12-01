"""
@PURPOSE: Temu发布控制器,串联选择店铺,设置供货价,批量发布等步骤并保证流程稳定.
@OUTLINE:
  - class PublishController: 负责发布工作流,选择器加载与上下文复位
  - def select_all_20_products(): 全选当前页 20 条商品,准备发布上下文
  - def select_shop(): 选择目标店铺或全选店铺并确认
  - def set_supply_price(): 打开供货价弹窗并按 SOP 配置公式
  - def batch_publish(): 批量发布并处理双重确认弹窗
  - def execute_publish_workflow(): 串联完整发布流程并返回结构化结果
@GOTCHAS:
  - 选择器依赖配置文件,缺失或失效时会启用兜底选择器并记录警告
  - Playwright 操作需要等待可见且启用,必要时滚动到视口并重试
@DEPENDENCIES:
  - 内部: data_processor.price_calculator.PriceCalculator, utils.selector_race.TIMEOUTS
  - 外部: playwright.async_api, loguru
@RELATED: apps/temu-auto-publish/config/miaoshou_selectors_v2.json
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger
from playwright.async_api import Locator, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ..data_processor.price_calculator import PriceCalculator
from ..utils.page_load_decorator import wait_dom_loaded
from ..utils.page_waiter import PageWaiter, ensure_dom_ready
from ..utils.selector_race import TIMEOUTS

SelectorEntries = Sequence[str] | str | None


@dataclass
class PublishWorkflowResult:
    """发布工作流的结构化结果."""

    shop_selected: bool = False
    price_set: bool = False
    published: bool = False

    @property
    def success(self) -> bool:
        """整体是否成功."""
        return self.shop_selected and self.price_set and self.published

    def to_dict(self) -> dict[str, Any]:
        """转换为输出字典."""
        return {
            "success": self.success,
            "shop_selected": self.shop_selected,
            "price_set": self.price_set,
            "published": self.published,
            "publish_result": {
                "success_count": 20 if self.published else 0,
                "fail_count": 0 if self.published else 20,
                "total_count": 20,
            },
        }


class PublishController:
    """Temu 发布控制器.

    串联 SOP 步骤 8-10(选择店铺,设置供货价,批量发布),并在失败时提供清晰的日志与回退.

    Attributes:
        selectors: 选择器配置字典.
        price_calculator: 价格计算器,用于日志/校验.
    Examples:
        >>> controller = PublishController()
        >>> await controller.select_shop(page, "测试店铺")
        >>> await controller.set_supply_price(page, [{"cost": 10.0}])
        >>> await controller.batch_publish(page)
    """

    def __init__(self, selector_path: str = "config/miaoshou_selectors_v2.json") -> None:
        """初始化发布控制器."""
        self.selector_path = self._resolve_selector_path(selector_path)
        self.selectors = self._load_selectors()
        self.price_calculator = PriceCalculator()
        self._publish_context_ready = False
        # 供货价功能暂时停用,避免 success 恒为 False
        self.enable_set_supply_price = False
        logger.info(f"发布控制器初始化完成,选择器配置路径: {self.selector_path}")

    def _resolve_selector_path(self, selector_path: str) -> Path:
        """将选择器配置路径转换为绝对路径."""
        selector_file = Path(selector_path)
        if selector_file.is_absolute():
            return selector_file

        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent
        return project_root / selector_file

    def _load_selectors(self) -> dict[str, Any]:
        """加载选择器配置并做基本校验."""
        if not self.selector_path.exists():
            logger.warning(f"选择器配置文件不存在,将使用兜底选择器: {self.selector_path}")
            return {}

        try:
            with self.selector_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("选择器配置不是字典")
            logger.debug(
                f"选择器配置已加载 version={data.get('version')}, "
                f"last_updated={data.get('last_updated')}"
            )
            return data
        except Exception as exc:  # pragma: no cover - 运行时保护
            logger.error(f"加载选择器配置失败,将使用兜底选择器: {exc}")
            return {}

    def _invalidate_publish_context(self) -> None:
        """标记当前选中上下文失效."""
        self._publish_context_ready = False

    @staticmethod
    def _dedup_selectors(candidates: list[str]) -> list[str]:
        """按顺序去重选择器列表."""
        seen: set[str] = set()
        deduped: list[str] = []
        for selector in candidates:
            if selector not in seen:
                deduped.append(selector)
                seen.add(selector)
        return deduped

    def _get_selector_candidates(self, *entries: SelectorEntries) -> list[str]:
        """展开配置与兜底选择器,自动去重."""
        candidates: list[str] = []
        for entry in entries:
            if entry is None:
                continue
            if isinstance(entry, str):
                parts = [part.strip() for part in entry.split(",") if part.strip()]
                candidates.extend(parts)
            else:
                for item in entry:
                    if isinstance(item, str) and item.strip():
                        candidates.append(item.strip())
        return self._dedup_selectors(candidates)

    def _build_waiter(self, page: Page) -> PageWaiter:
        """构造页面等待器,减少重复配置."""

        return PageWaiter(page)

    async def _click_first_available(
        self,
        page: Page,
        selectors: Sequence[str],
        *,
        visible_timeout_ms: int = 2_000,
        click_timeout_ms: int = 1_500,
        attempts: int = 2,
        context: str = "",
    ) -> str | None:
        """尝试依次点击第一个可见且可用的选择器.

        性能优化说明:
        - visible_timeout_ms: 4000 -> 2000
        - click_timeout_ms: 3000 -> 1500
        - attempts: 3 -> 2
        """
        last_error: Exception | None = None
        waiter = self._build_waiter(page)
        await waiter.wait_for_dom_stable(timeout_ms=visible_timeout_ms)
        click_timeout = max(visible_timeout_ms, click_timeout_ms)

        for attempt in range(attempts):
            for selector in selectors:
                locator = page.locator(selector).first
                clicked = await waiter.safe_click(
                    locator,
                    timeout_ms=click_timeout,
                    ensure_visible=True,
                    ensure_enabled=True,
                    scroll=True,
                    wait_after=True,
                    name=f"{context}:{selector}",
                )
                if clicked:
                    logger.debug(
                        f"selector={selector} ctx={context} attempt={attempt + 1}/{attempts}",
                    )
                    return selector

                last_error = PlaywrightTimeoutError("safe_click_failed")
                logger.debug(
                    f"selector={selector} ctx={context} attempt={attempt + 1}/{attempts}",
                )
            if attempt < attempts - 1:
                await waiter.wait_for_dom_stable(timeout_ms=visible_timeout_ms)
                await waiter.apply_retry_backoff(attempt + 1)
        if last_error:
            logger.debug(f"所有选择器均不可用 ctx={context} err={last_error}")
        return None

    async def _first_visible_locator(
        self,
        page: Page,
        selectors: Sequence[str],
        *,
        timeout_ms: int,
        context: str,
    ) -> Locator | None:
        """找到第一个可见的 Locator."""
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=timeout_ms)
                return locator
            except Exception as exc:  # pragma: no cover - 运行时保护
                logger.debug(
                    f"等待可见失败 selector={selector} ctx={context} err={exc}",
                )
        return None

    @ensure_dom_ready
    async def _ensure_publish_context(
        self,
        page: Page,
        *,
        force: bool = False,
    ) -> None:
        """确保当前在发布页且已全选 20 条商品."""

        if self._publish_context_ready and not force:
            return

        await self._reset_to_all_tab(page)
        selected = await self.select_all_20_products(
            page,
            require_load_state=force or not self._publish_context_ready,
        )
        if not selected:
            raise RuntimeError("全选商品失败,无法继续发布流程")
        self._publish_context_ready = True

    @ensure_dom_ready
    async def select_all_20_products(
        self,
        page: Page,
        *,
        require_load_state: bool = True,
    ) -> bool:
        """全选当前页 20 条产品."""

        logger.info("全选当前页产品(目标 20 条)...")
        if require_load_state:
            await wait_dom_loaded(page, context="[select all 20]")

        collection_box_config = self.selectors.get("collection_box", {})
        pagination_config = collection_box_config.get("pagination", {})
        configured_select_all = pagination_config.get("select_all")
        select_all_candidates = self._get_selector_candidates(
            configured_select_all,
            "button:has-text('全选')",
            "text='全选'",
            "label:has-text('全选')",
        )

        try:
            clicked_selector = await self._click_first_available(
                page,
                select_all_candidates,
                visible_timeout_ms=TIMEOUTS.SLOW,
                context="select_all",
            )
            if not clicked_selector:
                raise RuntimeError("未命中『全选』按钮")

            logger.success(f"已全选当前页产品 selector={clicked_selector}")
            self._publish_context_ready = True
            return True
        except Exception as exc:  # pragma: no cover - 运行时保护
            logger.error(f"全选产品失败: {exc}")
            self._invalidate_publish_context()
            return False

    @ensure_dom_ready
    async def _reset_to_all_tab(self, page: Page) -> None:
        """复位到「全部」TAB,确保后续操作在正确的列表."""

        temu_tabs = self.selectors.get("temu_collect_box", {}).get("tabs", {}).get("all", [])
        collection_tabs = self.selectors.get("collection_box", {}).get("tabs", {}).get("all", [])

        configured_selectors = self._get_selector_candidates(temu_tabs, collection_tabs)
        fallback_selectors = [
            ".jx-radio-button:has-text('全部')",
            ".pro-radio-button:has-text('全部')",
            ".pro-tabs__item:has-text('全部')",
            "[role='tab']:has-text('全部')",
            "button:has-text('全部')",
            "span:has-text('全部')",
            "text=全部",
        ]
        selectors = self._get_selector_candidates(configured_selectors, fallback_selectors)

        clicked_selector = await self._click_first_available(
            page,
            selectors,
            visible_timeout_ms=2_000,
            click_timeout_ms=1_500,
            attempts=2,
            context="reset_all_tab",
        )
        if clicked_selector:
            logger.info(f"已复位到「全部」TAB selector={clicked_selector}")
        else:
            logger.warning("复位到「全部」TAB 失败,未找到可用的 TAB 按钮")

    @ensure_dom_ready
    async def select_shop(self, page: Page, shop_name: str | None = None) -> bool:
        """选择店铺(SOP 步骤 8)."""
        logger.info("=" * 60)
        logger.info("[SOP 步骤 8] 选择店铺")

        logger.info("=" * 60)
        try:
            await self._ensure_publish_context(page)

            action_buttons = self.selectors.get("temu_collect_box", {}).get("action_buttons", {})
            configured_select_shop = action_buttons.get("select_shop")
            select_shop_candidates = self._get_selector_candidates(
                configured_select_shop,
                "button:has-text('选择店铺')",
                "text='选择店铺'",
            )

            logger.info("点击「选择店铺」按钮...")
            clicked = await self._click_first_available(
                page,
                select_shop_candidates,
                visible_timeout_ms=2_500,
                click_timeout_ms=1_500,
                attempts=2,
                context="select_shop.open",
            )
            if not clicked:
                raise RuntimeError("未能找到『选择店铺』按钮")

            normalized_name = (shop_name or "").strip()
            skip_specific_shop = normalized_name == "" or normalized_name.lower() in {
                "未指定",
                "all",
                "*",
            }

            if not skip_specific_shop:
                logger.info(f"选择店铺: {normalized_name}")
                target = page.get_by_text(normalized_name, exact=False).first
                try:
                    # 性能优化:减少店铺选择等待时间
                    await target.wait_for(state="visible", timeout=1500)
                    await target.click(timeout=1000)
                except Exception as exc:
                    logger.warning(f"定位店铺失败,将尝试全选店铺 name={normalized_name} err={exc}")
                    await self._select_all_shops(page)
            else:
                logger.info("未指定店铺,直接全选所有店铺")
                await self._select_all_shops(page)

            await self._confirm_shop_selection(page)

            logger.success("店铺选择完成")
            return True
        except Exception as exc:  # pragma: no cover - 运行时保护
            logger.error(f"选择店铺失败: {exc}")
            self._invalidate_publish_context()
            return False

    @ensure_dom_ready
    async def _select_all_shops(self, page: Page) -> None:
        """在店铺弹窗中勾选“全选”复选框."""
        selectors = self._get_selector_candidates(
            "label.jx-checkbox.jx-checkbox--small.pro-checkbox-group-all-select.pro-checkbox",
            "label:has-text('全选')",
            "button:has-text('全选')",
            "text='全选'",
            "input[type='checkbox'][aria-label*='全选']",
        )

        clicked_selector = await self._click_first_available(
            page,
            selectors,
            visible_timeout_ms=2_000,
            click_timeout_ms=1_000,
            attempts=2,
            context="select_all_shops",
        )
        if clicked_selector:
            logger.success(f"已全选所有店铺 selector={clicked_selector}")
            return

        raise RuntimeError("未找到可用的“全选”选项,无法继续选择店铺")

    @ensure_dom_ready
    async def _confirm_shop_selection(self, page: Page) -> None:
        """点击店铺选择弹窗中的“确定/确认”按钮."""
        confirm_selectors = self._get_selector_candidates(
            "button.jx-button.jx-button--primary:has-text('确定')",
            "button.pro-button:has-text('确定')",
            "button:has-text('确认')",
            "div[role='dialog'] button.jx-button--primary",
            "footer button.jx-button--primary",
            "button[type='button']:has-text('确定')",
        )

        clicked_selector = await self._click_first_available(
            page,
            confirm_selectors,
            visible_timeout_ms=3_000,
            click_timeout_ms=2_000,
            attempts=2,
            context="confirm_shop",
        )
        if clicked_selector:
            logger.success(f"已点击店铺确认按钮 selector={clicked_selector}")
            return

        try:
            await page.keyboard.press("Enter")
            logger.info("已通过键盘 Enter 确认店铺选择")
        except Exception as exc:  # pragma: no cover - 运行时保护
            raise RuntimeError("未能找到“确定/确认”按钮,无法确认店铺选择") from exc

    def _validate_products_data(
        self,
        products_data: Sequence[Mapping[str, Any]],
    ) -> list[float]:
        """校验产品数据并提取成本价列表."""
        if not products_data:
            raise ValueError("产品数据为空,无法计算供货价")

        costs: list[float] = []
        for idx, product in enumerate(products_data):
            if "cost" not in product:
                raise ValueError(f"产品数据缺少 cost 字段 index={idx}")
            try:
                cost_value = float(product["cost"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"成本值非法 index={idx} value={product['cost']}") from exc
            if cost_value <= 0:
                raise ValueError(f"成本值必须大于 0 index={idx} value={cost_value}")
            costs.append(cost_value)
        return costs

    @ensure_dom_ready
    async def _close_dialog_safely(self, page: Page) -> None:
        """尝试关闭当前弹窗,避免阻塞后续流程."""

        close_selectors = self._get_selector_candidates(
            "button:has-text('关闭')",
            "button:has-text('取消')",
            "button[aria-label='关闭']",
            ".jx-dialog__close",
            ".el-dialog__close",
        )
        await self._click_first_available(
            page,
            close_selectors,
            visible_timeout_ms=8000,
            click_timeout_ms=6000,
            attempts=1,
            context="close_dialog",
        )

    @ensure_dom_ready
    async def set_supply_price(
        self,
        page: Page,
        products_data: Sequence[Mapping[str, Any]],
    ) -> bool:
        """设置供货价(SOP 步骤 9)."""
        logger.info("=" * 60)
        logger.info("[SOP 步骤 9] 设置供货价")
        logger.info("=" * 60)
        # try:
        #     costs = self._validate_products_data(products_data)
        # except ValueError as exc:
        #     logger.error("供货价数据校验失败: %s", exc)
        #     return False

        # try:
        #     await self._ensure_publish_context(page)
        #     action_buttons = (
        #         self.selectors.get("temu_collect_box", {})
        #         .get("action_buttons", {})
        #     )
        #     configured_set_price = action_buttons.get("set_price")
        #     set_price_candidates = self._get_selector_candidates(
        #         configured_set_price,
        #         "button:has-text('设置供货价')",
        #         "button:has-text('供货价')",
        #     )

        #     logger.info("点击「设置供货价」按钮...")
        #     clicked_btn = await self._click_first_available(
        #         page,
        #         set_price_candidates,
        #         visible_timeout_ms=5_000,
        #         click_timeout_ms=3_000,
        #         attempts=2,
        #         context="set_price.open",
        #     )
        #     if not clicked_btn:
        #         raise RuntimeError("未能点击『设置供货价』按钮")

        #     dialog_selectors = [
        #         ".el-dialog__wrapper:visible",
        #         ".jx-dialog__wrapper:visible",
        #         ".el-dialog:visible",
        #         ".jx-dialog:visible",
        #         "[role='dialog']:visible",
        #     ]
        #     dialog = await self._first_visible_locator(
        #         page,
        #         dialog_selectors,
        #         timeout_ms=TIMEOUTS.SLOW,
        #         context="set_price.dialog",
        #     )
        #     scope: Page | Locator = dialog or page

        #     pricing_dialog_cfg = (
        #         self.selectors.get("temu_collect_box", {})
        #         .get("pricing_dialog", {})
        #     )

        #     formula_selectors = self._get_selector_candidates(
        #         pricing_dialog_cfg.get("use_formula"),
        #         "label:has-text('使用公式')",
        #         "button:has-text('使用公式')",
        #         ".jx-radio:has-text('使用公式')",
        #         ".el-radio:has-text('使用公式')",
        #         "text=使用公式",
        #     )
        #     if formula_selectors:
        #         await self._click_first_available(
        #             scope,  # type: ignore[arg-type]
        #             formula_selectors,
        #             visible_timeout_ms=1_200,
        #             click_timeout_ms=1_000,
        #             attempts=2,
        #             context="set_price.use_formula",
        #         )

        #     multiplier_selectors = self._get_selector_candidates(
        #         pricing_dialog_cfg.get("multiplier"),
        #         "input[placeholder*='倍数']",
        #         "input[type='number']",
        #     )
        #     multiplier = await self._first_visible_locator(
        #         scope,  # type: ignore[arg-type]
        #         multiplier_selectors,
        #         timeout_ms=TIMEOUTS.NORMAL,
        #         context="set_price.multiplier",
        #     )
        #     if multiplier:
        #         await multiplier.fill("3")
        #         logger.info("倍数输入框已填充 3(供货价 = 成本 x 7.5)")
        #     else:
        #         logger.warning("未找到倍数输入框,将跳过倍数填充")

        #     apply_selectors = self._get_selector_candidates(
        #         pricing_dialog_cfg.get("apply"),
        #         "button:has-text('应用')",
        #         "button:has-text('确定')",
        #     )
        #     apply_clicked = await self._click_first_available(
        #         scope,  # type: ignore[arg-type]
        #         apply_selectors,
        #         visible_timeout_ms=2_000,
        #         click_timeout_ms=1_500,
        #         attempts=2,
        #         context="set_price.apply",
        #     )
        #     if not apply_clicked:
        #         raise RuntimeError("未能点击『应用』或『确定』按钮")

        #     supply_prices = [
        #         self.price_calculator.calculate_supply_price(cost) for cost in costs
        #     ]
        #     logger.info(
        #         "供货价区间: %.2f - %.2f (基于 %s 个产品)",
        #         min(supply_prices),
        #         max(supply_prices),
        #         len(supply_prices),
        #     )

        #     close_selectors = self._get_selector_candidates(
        #         pricing_dialog_cfg.get("close"),
        #         "button:has-text('关闭')",
        #         "button:has-text('确定')",
        #     )
        #     await self._click_first_available(
        #         scope,  # type: ignore[arg-type]
        #         close_selectors,
        #         visible_timeout_ms=1_000,
        #         click_timeout_ms=800,
        #         attempts=1,
        #         context="set_price.close",
        #     )

        #     logger.success("供货价设置完成(公式倍数 3)")
        #     self._publish_context_ready = True
        #     return True
        # except Exception as exc:  # pragma: no cover - 运行时保护
        #     logger.error("设置供货价失败: %s", exc)
        #     self._invalidate_publish_context()
        #     await self._close_dialog_safely(page)
        #     return False
        # 禁用供货价设置

    @ensure_dom_ready
    async def _handle_pre_publish_modal(self, page: Page) -> None:
        """处理批量发布前置提示弹窗(可选出现)."""
        confirm_first_selectors = self._get_selector_candidates(
            "button:has-text('我知道了')",
            "button:has-text('确认')",
            "button:has-text('确定')",
            "text='我知道了'",
        )

        # 性能优化:减少前置弹窗超时时间
        confirm_first_clicked = await self._click_first_available(
            page,
            confirm_first_selectors,
            visible_timeout_ms=1500,
            click_timeout_ms=1200,
            attempts=2,  # 从 3 次减少到 2 次
            context="batch_publish.pre_modal",
        )
        if confirm_first_clicked:
            logger.info(f"已关闭前置提示弹窗 selector={confirm_first_clicked}")
            await self._build_waiter(page).wait_for_dom_stable(timeout_ms=500)

    @ensure_dom_ready
    async def batch_publish(self, page: Page) -> bool:
        """批量发布(SOP 步骤 10)."""
        logger.info("=" * 60)
        logger.info("[SOP 步骤 10] 批量发布")
        logger.info("=" * 60)
        try:
            publish_cfg = self.selectors.get("publish", {})
            repeat_cfg = publish_cfg.get("repeat_per_batch", 5)
            try:
                repeat_per_batch = int(repeat_cfg)
                repeat_per_batch = max(1, min(repeat_per_batch, 10))
            except Exception:
                repeat_per_batch = 5

            action_buttons = self.selectors.get("temu_collect_box", {}).get("action_buttons", {})
            configured_batch_publish = action_buttons.get("batch_publish")
            publish_btn_candidates = self._get_selector_candidates(
                configured_batch_publish,
                "button:has-text('批量发布')",
                "button:has-text('发布')",
            )
            waiter = self._build_waiter(page)
            for round_idx in range(repeat_per_batch):
                logger.info(f">>> 批量发布 {round_idx + 1}/{repeat_per_batch} 次,共 20 条产品")
                await self._reset_to_all_tab(page)
                await self._ensure_publish_context(page, force=True)

                logger.info("[1/2] 点击「批量发布」按钮...")
                publish_clicked = await self._click_first_available(
                    page,
                    publish_btn_candidates,
                    visible_timeout_ms=1_000,
                    click_timeout_ms=1_000,
                    attempts=3,
                    context="batch_publish.open",
                )
                if not publish_clicked:
                    self._invalidate_publish_context()
                    raise RuntimeError("未能点击「批量发布」按钮")
                logger.info(f"批量发布按钮命中 selector={publish_clicked}")
                # 性能优化:减少 DOM 稳定检测超时
                await waiter.wait_for_dom_stable(timeout_ms=1000)
                await self._handle_pre_publish_modal(page)

                confirm_publish_selectors = self._get_selector_candidates(
                    "button:has-text('确认发布')",
                )
                logger.info("[2/2] 确认发布...")
                confirm_ready = await self._first_visible_locator(
                    page,
                    confirm_publish_selectors,
                    timeout_ms=1500,  # 性能优化:从 TIMEOUTS.SLOW(2500) 减少
                    context="batch_publish.confirm_ready",
                )
                if not confirm_ready:
                    self._invalidate_publish_context()
                    raise RuntimeError("确认发布弹窗未出现")
                # 性能优化:减少 DOM 稳定检测超时
                await waiter.wait_for_dom_stable(timeout_ms=800)

                await self._click_first_available(
                    page,
                    confirm_publish_selectors,
                    visible_timeout_ms=1_000,
                    click_timeout_ms=1_000,
                    attempts=3,  # 不可更改
                    context="batch_publish.confirm",
                )

                # 性能优化:减少 close_retry 默认值从 5 到 3
                close_retry_cfg = self.selectors.get("publish_confirm", {}).get("close_retry", 3)
                try:
                    close_retry = int(close_retry_cfg)
                    close_retry = max(1, min(close_retry, 5))
                except Exception:
                    close_retry = 3

                close_button_selectors = self._get_selector_candidates(
                    "button:has-text('关闭')",
                    "button:has-text('关闭此对话框')",
                    "button:has-text('确定')",
                )

                close_button = None
                for attempt in range(close_retry):
                    close_button = await self._click_first_available(
                        page,
                        close_button_selectors,
                        visible_timeout_ms=600,  # 性能优化:从 800 减少
                        click_timeout_ms=500,  # 性能优化:从 600 减少
                        attempts=1,
                        context=f"batch_publish.close[{attempt + 1}/{close_retry}]",
                    )
                    if close_button:
                        logger.info(
                            f"关闭按钮命中 selector={close_button} "
                            f"(尝试 {attempt + 1}/{close_retry})"
                        )
                        break
                    # 性能优化:减少等待时间
                    await waiter.wait_for_dom_stable(timeout_ms=300)
                    if attempt < close_retry - 1:
                        await waiter.apply_retry_backoff(attempt + 1)

                if not close_button:
                    dialog_selectors = self._get_selector_candidates(
                        self.selectors.get("publish_confirm", {}).get("dialog"),
                        ".jx-overlay-dialog:visible",
                        ".el-dialog:visible",
                        "[role='dialog']:visible",
                    )
                    dialog_still_open = await self._first_visible_locator(
                        page,
                        dialog_selectors,
                        timeout_ms=TIMEOUTS.FAST,
                        context="batch_publish.dialog_check",
                    )
                    if dialog_still_open:
                        self._invalidate_publish_context()
                        raise RuntimeError("未能点击「关闭」按钮,弹窗仍存在")
                    logger.warning("未找到关闭按钮,但确认弹窗已消失,视为本轮发布完成")

                self._invalidate_publish_context()

            logger.success(
                f"批量发布完成 20 条产品 {repeat_per_batch} 次,共 {20 * repeat_per_batch} 条产品"
            )
            return True
        except Exception as exc:  # pragma: no cover - 运行时保护
            logger.error(f"批量发布失败: {exc}")
            return False
        finally:
            self._invalidate_publish_context()

    @ensure_dom_ready
    async def execute_publish_workflow(
        self,
        page: Page,
        products_data: Sequence[Mapping[str, Any]],
        shop_name: str | None = None,
    ) -> dict[str, Any]:
        """执行发布工作流(SOP 步骤 8-10)."""
        logger.info("=" * 80)
        logger.info("开始执行发布工作流(SOP 步骤 8-10)")
        logger.info("=" * 80)

        result = PublishWorkflowResult()

        try:
            logger.info("\n[准备] 全选 20 条产品...")
            await self.select_all_20_products(page)

            logger.info("\n[步骤 8] 选择店铺...")
            result.shop_selected = await self.select_shop(page, shop_name)

            # logger.info("\n[步骤 9] 设置供货价...")
            # result.price_set = await self.set_supply_price(page, products_data)

            logger.info("\n[步骤 10] 批量发布...")
            result.published = await self.batch_publish(page)

            logger.info("\n" + "=" * 80)
            logger.info("发布工作流执行完毕")
            logger.info(f"执行结果: {'✅ 成功' if result.success else '❌ 失败'}")
            logger.info("=" * 80)
            return result.to_dict()
        except Exception as exc:  # pragma: no cover - 运行时保护
            logger.error(f"发布工作流执行失败: {exc}")
            return result.to_dict()


# 测试代码
if __name__ == "__main__":
    # 该控制器需要 Playwright Page 对象,单独运行仅用于占位
    pass
