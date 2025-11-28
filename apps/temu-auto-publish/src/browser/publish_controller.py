""" 
@PURPOSE: 发布控制器，负责商品的发布流程（SOP步骤8-10）
@OUTLINE:
  - class PublishController: 发布控制器主类
  - async def select_all_20_products(): 全选20条产品
  - async def select_shop(): 选择店铺（SOP步骤8）
  - async def set_supply_price(): 设置供货价（SOP步骤9）
  - async def batch_publish(): 批量发布（SOP步骤10）
@GOTCHAS:
  - 批量发布需要2次确认
  - 供货价公式：真实供货价×3 = 成本×7.5
@TECH_DEBT:
  - TODO: 需要使用Playwright Codegen获取实际选择器
  - TODO: 添加发布失败的错误处理和重试机制
@DEPENDENCIES:
  - 内部: data_processor.price_calculator
  - 外部: playwright, loguru
@RELATED: miaoshou_controller.py, batch_edit_controller.py
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from ..data_processor.price_calculator import PriceCalculator
from ..utils.selector_race import TIMEOUTS


class PublishController:
    """发布控制器（SOP步骤8-10）.

    负责商品发布的完整流程：
    - 步骤8：选择店铺
    - 步骤9：设置供货价
    - 步骤10：批量发布（2次确认）

    Attributes:
        selectors: 选择器配置
        price_calculator: 价格计算器

    Examples:
        >>> ctrl = PublishController()
        >>> await ctrl.select_shop(page, "测试店铺")
        >>> await ctrl.set_supply_price(page, products_data)
        >>> await ctrl.batch_publish(page)
    """

    def __init__(self, selector_path: str = "config/miaoshou_selectors_v2.json"):
        """初始化发布控制器.

        Args:
            selector_path: 选择器配置文件路径
        """
        self.selector_path = Path(selector_path)
        self.selectors = self._load_selectors()
        self.price_calculator = PriceCalculator()
        self._publish_context_ready = False
        
        logger.info("发布控制器初始化（SOP步骤8-10）")

    def _load_selectors(self) -> dict:
        """加载选择器配置.

        Returns:
            选择器配置字典
        """
        try:
            if not self.selector_path.is_absolute():
                current_file = Path(__file__)
                project_root = current_file.parent.parent.parent
                selector_file = project_root / self.selector_path
            else:
                selector_file = self.selector_path

            with open(selector_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.debug(f"选择器配置已加载: {selector_file}")
                return config
        except Exception as e:
            logger.warning(f"加载选择器配置失败: {e}，将使用默认选择器")
            return {}

    def _invalidate_publish_context(self) -> None:
        """标记当前选中上下文失效."""

        self._publish_context_ready = False

    async def _ensure_publish_context(self, page: Page, *, force: bool = False) -> None:
        """复位到发布页 + 全选 20 条商品, 避免重复点击."""

        if self._publish_context_ready and not force:
            return

        await self._reset_to_all_tab(page)
        selected = await self.select_all_20_products(
            page,
            require_load_state=force or not self._publish_context_ready,
        )
        if not selected:
            raise RuntimeError("全选商品失败, 无法继续发布流程")
        self._publish_context_ready = True

    async def _click_first_available(
        self,
        page: Page,
        selectors: Sequence[str],
        *,
        visible_timeout_ms: int = 4_000,
        click_timeout_ms: int = 3_000,
    ) -> str | None:
        """尝试依次点击第一个可见的选择器."""

        last_error: Exception | None = None
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=visible_timeout_ms)
                await locator.click(timeout=click_timeout_ms)
                return selector
            except PlaywrightTimeoutError as exc:
                last_error = exc
                logger.debug(f"等待 selector={selector} 可见超时: {exc}")
            except Exception as exc:  # pragma: no cover - 运行时点击异常
                last_error = exc
                logger.debug(f"点击 selector={selector} 失败: {exc}")
        if last_error:
            logger.debug(f"所有选择器均不可用, 最后错误: {last_error}")
        return None

    async def select_all_20_products(
        self,
        page: Page,
        *,
        require_load_state: bool = True,
    ) -> bool:
        """全选20条产品（发布前准备）.

        Args:
            page: Playwright页面对象
            require_load_state: 是否等待页面加载完成

        Returns:
            是否成功全选

        Examples:
            >>> await ctrl.select_all_20_products(page)
            True
        """
        logger.info("全选20条产品...")
        if require_load_state:
            await page.wait_for_load_state("domcontentloaded")
        try:
            # 使用全选按钮
            collection_box_config = self.selectors.get("collection_box", {})
            pagination_config = collection_box_config.get("pagination", {})
            select_all_selector = pagination_config.get("select_all", "text='全选'")
            
            locator = page.locator(select_all_selector).first
            await locator.wait_for(state="visible", timeout=TIMEOUTS.SLOW)
            await locator.click()

            logger.success("✓ 已全选20条产品")
            self._publish_context_ready = True
            return True

        except Exception as e:
            logger.error(f"全选产品失败: {e}")
            self._invalidate_publish_context()
            return False

    async def _reset_to_all_tab(self, page: Page) -> None:
        """复位到「全部」TAB，确保后续操作在正确的列表."""
        temu_tabs = (
            self.selectors.get("temu_collect_box", {})
            .get("tabs", {})
            .get("all", [])
        )
        collection_tabs = (
            self.selectors.get("collection_box", {})
            .get("tabs", {})
            .get("all", [])
        )

        configured_selectors: List[str] = []
        for candidate in (temu_tabs, collection_tabs):
            if isinstance(candidate, str):
                configured_selectors.append(candidate)
            elif isinstance(candidate, list):
                configured_selectors.extend(candidate)

        fallback_selectors = [
            ".jx-radio-button:has-text('全部')",
            ".pro-radio-button:has-text('全部')",
            ".pro-tabs__item:has-text('全部')",
            "[role='tab']:has-text('全部')",
            "button:has-text('全部')",
            "span:has-text('全部')",
            "text=全部",
        ]

        tried_selectors = configured_selectors + fallback_selectors
        reset_clicked = None
        for selector in tried_selectors:
            try:
                locator = page.locator(selector)
                if await locator.count() == 0:
                    continue
                await locator.first.click()
                reset_clicked = selector
                break
            except Exception as exc:
                logger.debug(f"复位TAB选择器 {selector} 失败: {exc}")

        if reset_clicked:
            logger.info(f"已复位到「全部」TAB：{reset_clicked}")
        else:
            logger.warning("复位到「全部」TAB失败，未找到可用的TAB按钮")

    async def select_shop(self, page: Page, shop_name: Optional[str] = None) -> bool:
        """选择店铺（SOP步骤8）.

        Args:
            page: Playwright页面对象
            shop_name: 店铺名称（可选，None则选择第一个）

        Returns:
            是否选择成功

        Examples:
            >>> await ctrl.select_shop(page, "我的测试店铺")
            True
        """
        logger.info("=" * 60)
        logger.info("[SOP步骤8] 选择店铺")
        logger.info("=" * 60)

        try:
            await self._ensure_publish_context(page)
            # 注意：需要使用Codegen获取实际的选择器
            # 这里提供框架代码，实际选择器需要补充
            
            collection_box_config = self.selectors.get("collection_box", {})
            action_buttons = collection_box_config.get("action_buttons", {})
            
            # 1. 点击"选择店铺"按钮（或类似按钮）
            # TODO: 需要通过Codegen确认实际按钮文本和选择器
            select_shop_selector = (
                "xpath=/html/body/div[1]/section/div/div[4]/div/div[1]/button[2]"
            )
            
            logger.info("点击「选择店铺」按钮...")
            clicked = await self._click_first_available(
                page,
                [select_shop_selector],
                visible_timeout_ms=5_000,
            )
            if not clicked:
                raise RuntimeError("未能找到『选择店铺』按钮")

            # 2. 选择店铺
            normalized_name = (shop_name or "").strip()
            skip_specific_shop = normalized_name == "" or normalized_name.lower() in {"未指定", "all", "*"}

            if not skip_specific_shop:
                logger.info(f"选择店铺: {normalized_name}")
                shop_selector = f"text='{normalized_name}'"
                try:
                    target = page.locator(shop_selector)
                    if await target.count() == 0:
                        raise RuntimeError(f"未在弹窗中找到店铺: {normalized_name}")
                    await target.first.click()
                except Exception as exc:
                    logger.warning(
                        f"定位店铺 {normalized_name} 失败，尝试改为全选店铺: {exc}"
                    )
                    await self._select_all_shops(page)
            else:
                logger.info("未指定店铺，直接全选所有店铺")
                await self._select_all_shops(page)

            # 3. 确认选择
            await self._confirm_shop_selection(page)

            logger.success("✓ 店铺选择完成")
            return True

        except Exception as e:
            logger.error(f"选择店铺失败: {e}")
            self._invalidate_publish_context()
            logger.warning("⚠️  需要使用Codegen获取正确的选择器")
            return False

    async def _select_all_shops(self, page: Page) -> None:
        """在店铺弹窗中勾选“全选”复选框."""

        selectors = [
            "label.jx-checkbox.jx-checkbox--small.pro-checkbox-group-all-select.pro-checkbox",
            "label:has-text('全选')",
            "button:has-text('全选')",
            "text='全选'",
        ]

        for selector in selectors:
            locator = page.locator(selector)
            try:
                if await locator.count() == 0:
                    continue
                await locator.first.click()
                logger.success(f"✓ 已全选所有店铺 (selector={selector})")
                return
            except Exception as exc:
                logger.debug(f"尝试 selector={selector} 失败: {exc}")

        raise RuntimeError("未找到可用的“全选”选项，无法继续选择店铺")

    async def _confirm_shop_selection(self, page: Page) -> None:
        """点击店铺选择弹窗中的“确定/确认”按钮."""

        confirm_selectors = [
            "button.jx-button.jx-button--primary:has-text('确定')",
            "button.pro-button:has-text('确定')",
            "button:has-text('确认')",
            "div[role='dialog'] button.jx-button--primary",
            "footer button.jx-button--primary",
            "button[type='button']:has-text('确定')",
        ]

        last_error: Exception | None = None
        for selector in confirm_selectors:
            locator = page.locator(selector)
            try:
                if await locator.count() == 0:
                    continue
                button = locator.first
                if not await button.is_enabled():
                    continue
                await button.scroll_into_view_if_needed()
                await button.click(timeout=3_000)
                logger.success(f"✓ 点击店铺选择确认按钮 (selector={selector})")
                return
            except Exception as exc:
                last_error = exc
                logger.debug(
                    f"点击确认按钮失败 selector={selector}, err={exc}"
                )

        # fallback: 尝试按 Enter 或 Esc
        try:
            await page.keyboard.press("Enter")
            logger.info("已通过键盘 Enter 确认店铺选择")
            return
        except Exception:
            pass

        if last_error:
            raise last_error
        raise RuntimeError("未能找到“确定”按钮，无法确认店铺选择")

    async def set_supply_price(
        self,
        page: Page,
        products_data: List[Dict]
    ) -> bool:
        """设置供货价（SOP步骤9）.

        公式：
        - 真实供货价 = 成本 × 2.5（最低）
        - 妙手供货价 = 真实供货价 × 3 = 成本 × 7.5

        Args:
            page: Playwright页面对象
            products_data: 产品数据列表，每个包含cost字段

        Returns:
            是否设置成功

        Examples:
            >>> products = [{"cost": 10.0}, {"cost": 12.0}]
            >>> await ctrl.set_supply_price(page, products)
            True
        """
        logger.info("=" * 60)
        logger.info("[SOP步骤9] 设置供货价")
        logger.info("=" * 60)
            
        try:
            await self._reset_to_all_tab(page)
            logger.info("复位完成")
            #全选20条产品
            await self.select_all_20_products(page)
            logger.info("全选20条产品完成")
            #确保发布上下文
            await self._ensure_publish_context(page)
            # 1. 点击"设置供货价"按钮
            # TODO: 需要通过Codegen确认实际按钮文本和选择器
            set_price_btn_selector = "button:has-text('设置供货价'), button:has-text('供货价')"
            configured_set_price = (
                self.selectors.get("temu_collect_box", {})
                .get("action_buttons", {})
                .get("set_price")
            )
            set_price_candidates: list[str] = []
            if isinstance(configured_set_price, str):
                set_price_candidates.append(configured_set_price)
            elif isinstance(configured_set_price, Sequence):
                set_price_candidates.extend(configured_set_price)
            set_price_candidates.extend(
                [sel.strip() for sel in set_price_btn_selector.split(",")]
            )

            logger.info("点击「设置供货价」按钮...")
            clicked_btn = await self._click_first_available(
                page,
                set_price_candidates,
                visible_timeout_ms=5_000,
            )
            if not clicked_btn:
                raise RuntimeError("未能点击『设置供货价』按钮，请检查DOM结构")

            # 1.1 等待供货价弹窗出现，后续选择器都限定在弹窗内，避免误触
            dialog_candidates = [
                ".el-dialog__wrapper:visible",
                ".jx-dialog__wrapper:visible",
                ".el-dialog:visible",
                ".jx-dialog:visible",
                "[role='dialog']:visible",
            ]
            price_dialog = None
            for selector in dialog_candidates:
                dialog = page.locator(selector).filter(has_text="供货价")
                try:
                    await dialog.wait_for(state="visible", timeout=5_000)
                    price_dialog = dialog.first
                    break
                except Exception:
                    continue
            # 若未能定位到带“供货价”文本的弹窗，则回退到任意可见弹窗
            if price_dialog is None:
                for selector in dialog_candidates:
                    dialog = page.locator(selector)
                    try:
                        await dialog.wait_for(state="visible", timeout=3_000)
                        price_dialog = dialog.first
                        break
                    except Exception:
                        continue
            if price_dialog:
                logger.debug("供货价弹窗已就绪，开始选择公式模式")
            
            # 2. 选择“使用公式”
            logger.info("选择「使用公式」模式...")
            pricing_dialog_cfg = (
                self.selectors.get("temu_collect_box", {})
                .get("pricing_dialog", {})
            )
            configured_formula = pricing_dialog_cfg.get("use_formula")
            formula_locators: list[str] = []
            if isinstance(configured_formula, str):
                formula_locators.append(configured_formula)
            elif isinstance(configured_formula, Sequence):
                formula_locators.extend(configured_formula)
            formula_locators.extend(
                [
                    "label:has(span.jx-radio__label:has-text('使用公式'))",
                    "label:has-text('使用公式')",
                    ".jx-radio:has-text('使用公式')",
                    ".el-radio:has-text('使用公式')",
                    ".el-radio__label:has-text('使用公式')",
                    "[class*='radio'] span:has-text('使用公式')",
                    "[role='radio']:has-text('使用公式')",
                    "text=使用公式",
                ]
            )

            scopes = [price_dialog] if price_dialog is not None else [page]
            clicked_selector = None
            last_error = None
            for scope in scopes:
                clicked_selector = await self._click_first_available(
                    scope,  # type: ignore[arg-type]
                    formula_locators,
                    visible_timeout_ms=1_000,
                )
                if clicked_selector:
                    break
            if not clicked_selector:
                try:
                    # 最后兜底：直接根据文本查找并点击
                    fallback = (price_dialog or page).get_by_text("使用公式", exact=False).first
                    await fallback.click(timeout=1_000)
                    clicked_selector = "get_by_text('使用公式')"
                except Exception as exc:
                    last_error = exc
            if not clicked_selector:
                logger.debug(f"使用公式点击失败详细: {last_error}")
                raise RuntimeError("未能点击『使用公式』选项，请检查DOM结构")
            logger.info(f"使用公式选择器命中：{clicked_selector}")

            # 3. 点击“倍数”文本框并填写 3
            multiplier_locators = [
                "input[placeholder='倍数']",
                "xpath=//label[contains(.,'倍数')]/following::input[1]",
                "input[placeholder*='倍数']",
            ]
            multiplier_clicked = None
            multiplier_input = None
            for selector in multiplier_locators:
                try:
                    multiplier_input = page.locator(selector).first
                    await multiplier_input.wait_for(state="visible", timeout=3_000)
                    await multiplier_input.click()
                    multiplier_clicked = selector
                    break
                except Exception as exc:
                    logger.debug(f"倍数输入框选择器 {selector} 点击失败: {exc}")
            if not multiplier_clicked:
                raise RuntimeError("未能定位到『倍数』输入框，请检查DOM结构")

            await multiplier_input.fill("3")
            logger.info(f"倍数输入框选择器命中：{multiplier_clicked}")

            # 4. 点击“应用”按钮
            apply_clicked = await self._click_first_available(
                page,
                ["button:has-text('应用')"],
                visible_timeout_ms=3_000,
            )
            if not apply_clicked:
                raise RuntimeError("未能点击『应用』按钮，请检查DOM结构")

            # 5. 等待提示弹窗并关闭
            close_selectors = [
                "body > div:nth-child(25) > div > div > footer > button",
                "button:has-text('关闭')",
            ]
            close_clicked = None
            for selector in close_selectors:
                try:
                    locator = page.locator(selector).first
                    await locator.wait_for(state="visible", timeout=3_000)
                    await locator.click()
                    close_clicked = selector
                    break
                except Exception as exc:
                    logger.debug(f"关闭提示弹窗选择器 {selector} 失败: {exc}")
            if close_clicked:
                logger.info(f"已关闭提示弹窗：{close_clicked}")
            else:
                logger.warning("未能自动关闭提示弹窗，请确认页面状态")

            logger.success("✓ 供货价设置完成（使用公式倍数 3）")
            return True

        except Exception as e:
            logger.error(f"设置供货价失败: {e}")
            self._invalidate_publish_context()
            logger.warning("⚠️  需要使用Codegen获取正确的选择器")
            return False

    async def batch_publish(self, page: Page) -> bool:
        """批量发布（SOP步骤10）.

        需要2次确认：
        1. 第1次点击"批量发布"
        2. 第2次确认发布

        结果：20条 × 2次 = 40条产品

        Args:
            page: Playwright页面对象

        Returns:
            是否发布成功

        Examples:
            >>> await ctrl.batch_publish(page)
            True
        """
        logger.info("=" * 60)
        logger.info("[SOP步骤10] 批量发布（2次确认）")
        logger.info("=" * 60)
        try:
            publish_cfg = self.selectors.get("publish", {})
            repeat_cfg = publish_cfg.get("repeat_per_batch", 5)
            try:
                repeat_per_batch = int(repeat_cfg)
                if repeat_per_batch < 1:
                    repeat_per_batch = 5
                if repeat_per_batch > 10:
                    repeat_per_batch = 10  # 安全上限
            except Exception:
                repeat_per_batch = 5

            for round_idx in range(repeat_per_batch):
                logger.info(
                    ">>> 批量发布第 %s/%s 次（单批配置可在 selectors.publish.repeat_per_batch 调整）",
                    round_idx + 1,
                    repeat_per_batch,
                )
                await self._reset_to_all_tab(page)
                logger.info("复位完成")
                #全选20条产品
                await self._ensure_publish_context(page, force=True)

                # 1. 第1次：点击"批量发布"按钮
                publish_btn_selectors = [
                    "#appScrollContainer > div.sticky-operate-box.space-between > div > div:nth-child(1) > button:nth-child(1)",
                    "button:has-text('批量发布')",
                    "button:has-text('发布')",
                ]

                logger.info("[1/2] 点击「批量发布」按钮...")
                publish_clicked = await self._click_first_available(
                    page,
                    publish_btn_selectors,
                    visible_timeout_ms=500,
                )
                if not publish_clicked:
                    raise RuntimeError("未能点击「批量发布」按钮，请检查DOM结构")
                logger.info(f"批量发布按钮选择器命中：{publish_clicked}")

                # 1.2 等待弹窗出现并点击确认
                confirm_first_selectors = [
                    "button:has-text('知道了')",
                ]
                confirm_first_clicked = None
                for selector in confirm_first_selectors:
                    try:
                        locator = page.locator(selector).first
                        await locator.wait_for(state="visible", timeout=800)
                        await locator.click()
                        confirm_first_clicked = selector
                        break
                    except PlaywrightTimeoutError:
                        logger.debug(f"批量发布前置弹窗 {selector} 未在8秒内出现")
                    except Exception as exc:
                        logger.debug(
                            f"批量发布前置弹窗选择器 {selector} 点击失败: {exc}"
                        )
                if confirm_first_clicked:
                    logger.info(f"批量发布前置弹窗已关闭：{confirm_first_clicked}")
                else:
                    # 未检测到前置弹窗，可能页面已跳过该步骤，尝试等待后重试一次
                    logger.info("未检测到批量发布前置弹窗，等待后重试...")
                    await asyncio.sleep(0.5)
                    for retry_selector in confirm_first_selectors:
                        try:
                            locator = page.locator(retry_selector).first
                            await locator.wait_for(state="visible", timeout=500)
                            await locator.click()
                            confirm_first_clicked = retry_selector
                            logger.info(f"重试成功，已关闭前置弹窗：{retry_selector}")
                            break
                        except Exception:
                            pass
                    if not confirm_first_clicked:
                        logger.warning("前置弹窗仍未出现，继续执行后续步骤")

                # 1.5 点击“图片顺序随机打乱”
                shuffle_selectors = [
                    "button:has-text('图片顺序随机打乱')",
                    "label:has-text('图片顺序随机打乱')",
                    "text=图片顺序随机打乱",
                ]
                shuffle_clicked = await self._click_first_available(
                    page,
                    shuffle_selectors,
                    visible_timeout_ms=400,
                )
                if not shuffle_clicked:
                    logger.warning("未能点击「图片顺序随机打乱」，请确认页面状态")

                # 2. 第2次确认：确认发布
                confirm_publish_selectors = [
                    "body > div:nth-child(25) > div > div > footer > div > div.release-footer-wrapper__right > button.jx-button.jx-button--primary.jx-button--default.pro-button",
                    "button:has-text('确认发布')",
                ]

                close_retry_cfg = (
                    self.selectors.get("publish_confirm", {}).get("close_retry", 5)
                )
                try:
                    close_retry = int(close_retry_cfg)
                    if close_retry < 1:
                        close_retry = 5
                    if close_retry > 10:
                        close_retry = 10
                except Exception:
                    close_retry = 5

                close_button_selectors = [
                    "body > div:nth-child(34) > div > div > footer > button",
                    "/html/body/div[16]/div/div/footer/button",
                    "button:has-text('关闭')",
                ]

                logger.info("[2/2] 确认发布...")
                confirm_publish_clicked = await self._click_first_available(
                    page,
                    confirm_publish_selectors,
                    visible_timeout_ms=600,
                )
                if not confirm_publish_clicked:
                    raise RuntimeError("未能点击「确认发布」按钮，请检查DOM结构")
                logger.info(f"确认发布按钮选择器命中：{confirm_publish_clicked}")

                close_button = None
                for attempt in range(close_retry):
                    close_button = await self._click_first_available(
                        page,
                        close_button_selectors,
                        visible_timeout_ms=500,
                    )
                    if close_button:
                        logger.info(
                            "关闭按钮选择器命中：%s (attempt %s/%s)",
                            close_button,
                            attempt + 1,
                            close_retry,
                        )
                        break

                if not close_button:
                    raise RuntimeError("未能点击「关闭」按钮，请检查DOM结构")

            logger.success(
                "✓ 批量发布完成（单次20条，执行 %s 次，总计 %s 条）",
                repeat_per_batch,
                20 * repeat_per_batch,
            )
            return True

        except Exception as e:
            logger.error(f"批量发布失败: {e}")
            logger.warning("⚠️  需要使用Codegen获取正确的选择器")
            return False
        finally:
            # 批量发布会刷新列表，标记上下文失效
            self._invalidate_publish_context()


    async def execute_publish_workflow(
        self,
        page: Page,
        products_data: List[Dict],
        shop_name: Optional[str] = None
    ) -> Dict:
        """执行发布工作流（SOP步骤8-10）.

        Args:
            page: Playwright页面对象
            products_data: 产品数据列表
            shop_name: 店铺名称（可选）

        Returns:
            执行结果字典：{
                "success": bool,
                "shop_selected": bool,
                "price_set": bool,
                "published": bool,
            }

        Examples:
            >>> result = await ctrl.execute_publish_workflow(page, products_data, "测试店铺")
            >>> result["success"]
            True
        """
        logger.info("=" * 80)
        logger.info("开始执行发布工作流（SOP步骤8-10）")
        logger.info("=" * 80)

        result = {
            "success": False,
            "shop_selected": False,
            "price_set": False,
            "published": False,
            "publish_result": {},
        }

        try:
            # 1. 全选20条产品
            logger.info("\n[准备] 全选20条产品...")
            await self.select_all_20_products(page)

            # 2. 选择店铺（步骤8）
            logger.info("\n[步骤8] 选择店铺...")
            if await self.select_shop(page, shop_name):
                result["shop_selected"] = True

            # 3. 设置供货价（步骤9）
            logger.info("\n[步骤9] 设置供货价...")
            if await self.set_supply_price(page, products_data):
                result["price_set"] = True

            # 4. 批量发布（步骤10）
            logger.info("\n[步骤10] 批量发布...")
            if await self.batch_publish(page):
                result["published"] = True

            # 判断整体是否成功
            result["success"] = (
                result["shop_selected"] and
                result["price_set"] and
                result["published"]
            )
            result["publish_result"] = {
                "success_count": int(result["published"]) * 20,
                "fail_count": 0 if result["published"] else 20,
                "total_count": 20,
            }

            logger.info("\n" + "=" * 80)
            logger.info("发布工作流执行完成")
            logger.info(f"执行结果: {'✓ 成功' if result['success'] else '✗ 失败'}")
            logger.info("=" * 80)

            return result

        except Exception as e:
            logger.error(f"发布工作流执行失败: {e}")
            return result


# 测试代码
if __name__ == "__main__":
    # 这个控制器需要配合Page对象使用
    # 测试请在集成测试中进行
    pass
