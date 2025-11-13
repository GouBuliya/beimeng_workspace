"""
@PURPOSE: 基于最新 SOP 的 Temu 发布工作流, 实现首次编辑、认领、批量编辑与发布全流程
@OUTLINE:
  - dataclass StageOutcome: 阶段执行结果
  - dataclass EditedProduct: 首次编辑阶段产物
  - dataclass WorkflowExecutionResult: 整体执行结果
  - class CompletePublishWorkflow: 工作流主体
      - execute(): 同步入口
      - _run(): 异步总控
      - _stage_first_edit(): 阶段 1 首次编辑
      - _stage_claim_products(): 阶段 2 认领
      - _stage_batch_edit(): 阶段 3 批量编辑 18 步
      - _stage_publish(): 阶段 4 选择店铺/供货价/发布
      - 若干辅助方法: 数据准备、标题生成、凭证/店铺解析
  - async def execute_complete_workflow(): 遗留兼容入口, 代理到 v1 工作流
@DEPENDENCIES:
  - 内部: browser.*, data_processor.*
  - 外部: playwright (runtime), loguru
@RELATED: legacy 目录中的历史工作流实现
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

from config.settings import settings

from ..browser.batch_edit_codegen import run_batch_edit
from ..browser.batch_edit_controller import BatchEditController
from ..browser.first_edit_codegen import open_edit_dialog_codegen
from ..browser.first_edit_controller import FirstEditController
from ..browser.first_edit_dialog_codegen import fill_first_edit_dialog_codegen
from ..browser.first_edit_executor import FirstEditExecutor, FirstEditPayload
from ..browser.login_controller import LoginController
from ..browser.miaoshou_controller import MiaoshouController
from ..browser.publish_controller import PublishController
from ..data_processor.price_calculator import PriceCalculator, PriceResult
from ..data_processor.product_data_reader import ProductDataReader
from ..data_processor.selection_table_reader import ProductSelectionRow, SelectionTableReader
from .legacy.complete_publish_workflow_v1 import (
    execute_complete_workflow as legacy_execute_complete_workflow,
)

if TYPE_CHECKING:
    from playwright.async_api import Page


@dataclass(slots=True)
class StageOutcome:
    """阶段执行结果数据结构."""

    name: str
    success: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EditedProduct:
    """首次编辑后用于后续阶段的数据载体."""

    index: int
    selection: ProductSelectionRow
    title: str
    cost_price: float
    price: PriceResult
    weight_g: int
    dimensions_cm: tuple[int, int, int]

    def to_payload(self) -> dict[str, Any]:
        """转换为可序列化的业务字典."""

        return {
            "index": self.index,
            "product_name": self.selection.product_name,
            "model_number": self.selection.model_number,
            "owner": self.selection.owner,
            "title": self.title,
            "cost_price": self.cost_price,
            "suggested_price": self.price.suggested_price,
            "supply_price": self.price.supply_price,
            "real_supply_price": self.price.real_supply_price,
            "weight_g": self.weight_g,
            "dimensions_cm": {
                "length": self.dimensions_cm[0],
                "width": self.dimensions_cm[1],
                "height": self.dimensions_cm[2],
            },
        }


@dataclass(slots=True)
class WorkflowExecutionResult:
    """整体工作流执行结果."""

    workflow_id: str
    total_success: bool
    stages: list[StageOutcome]
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为易于序列化的字典结构."""

        return {
            "workflow_id": self.workflow_id,
            "total_success": self.total_success,
            "errors": list(self.errors),
            "stages": [
                {
                    "name": stage.name,
                    "success": stage.success,
                    "message": stage.message,
                    "details": stage.details,
                }
                for stage in self.stages
            ],
        }


async def _capture_html_snapshot(page: Page, filename: str) -> None:
    """写出当前页面 HTML 方便排查复杂 UI 结构."""

    try:
        html = await page.content()
    except Exception as exc:  # pragma: no cover - 调试辅助
        logger.warning("获取页面 HTML 失败: %s", exc)
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_root = Path(__file__).resolve().parents[2] / "data" / "debug" / "html"
    target_root.mkdir(parents=True, exist_ok=True)
    target_file = target_root / f"{timestamp}_{filename}"
    try:
        target_file.write_text(html, encoding="utf-8")
        logger.debug("已写出调试 HTML: %s", target_file)
    except Exception as exc:  # pragma: no cover - IO 失败
        logger.warning("写出调试 HTML 失败: %s", exc)


class CompletePublishWorkflow:
    """Temu 商品发布完整工作流 (SOP 步骤 1-11)."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        selection_table: Path | str | None = None,
        use_ai_titles: bool = False,
        use_codegen_batch_edit: bool = True,
        use_codegen_first_edit: bool = False,
        skip_first_edit: bool = False,
        only_claim: bool = False,
    ) -> None:
        """初始化工作流控制器.

        Args:
            headless: 浏览器是否使用无头模式; None 时读取配置文件.
            selection_table: 选品表路径, 默认读取 data/input/selection.xlsx.
            use_ai_titles: 是否启用 AI 生成标题 (失败时自动回退).
            use_codegen_batch_edit: 是否使用 codegen 录制的批量编辑模块 (默认 True).
            skip_first_edit: 是否直接跳过首次编辑阶段.
        """

        if load_dotenv:  # pragma: no cover - 环境可选
            load_dotenv()

        self.settings = settings
        self.use_ai_titles = use_ai_titles
        self.use_codegen_batch_edit = use_codegen_batch_edit
        self.use_codegen_first_edit = use_codegen_first_edit
        self.skip_first_edit = skip_first_edit
        self.only_claim = only_claim
        self.collect_count = max(1, min(self.settings.business.collect_count, 5))
        self.claim_times = max(1, self.settings.business.claim_count)
        self.headless = headless if headless is not None else self.settings.browser.headless

        # 图片基础目录(从环境变量或配置读取, 默认为 data/input/10月新品可推)
        self.image_base_dir = self._resolve_image_base_dir()

        self.selection_table_path = Path(selection_table) if selection_table else None

        self.selection_reader = SelectionTableReader()
        self.product_reader = ProductDataReader()
        self.price_calculator = PriceCalculator(
            suggested_multiplier=self.settings.business.price_multiplier,
            supply_multiplier=self.settings.business.supply_price_multiplier,
        )

    def execute(self) -> WorkflowExecutionResult:
        """同步入口, 包装 asyncio 运行."""

        logger.info("启动 Temu 完整发布工作流 (SOTA 模式)")
        return asyncio.run(self._run())

    async def _run(self) -> WorkflowExecutionResult:
        workflow_id = f"temu_publish_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        stages: list[StageOutcome] = []
        errors: list[str] = []

        login_ctrl = LoginController()

        try:
            username, password = self._resolve_credentials()
            if not username or not password:
                raise RuntimeError("缺少登录凭证 (MIAOSHOU_USERNAME/MIAOSHOU_PASSWORD)")

            login_success = await login_ctrl.login(
                username=username,
                password=password,
                headless=self.headless,
            )
            if not login_success:
                raise RuntimeError("登录妙手ERP失败, 请检查账号密码或 Cookie")

            page = login_ctrl.browser_manager.page
            assert page is not None, "Playwright page 未初始化"

            miaoshou_ctrl = MiaoshouController()
            first_edit_ctrl = FirstEditController()
            batch_edit_ctrl = BatchEditController(page)
            publish_ctrl = PublishController()

            selection_rows = self._prepare_selection_rows()

            if self.only_claim:
                logger.info("仅认领模式: 跳过首次编辑阶段")
                edited_products = self._build_placeholder_edits(selection_rows)
                stage1 = StageOutcome(
                    name="stage1_first_edit",
                    success=True,
                    message="仅认领模式: 首次编辑已跳过",
                    details={
                        "skipped": True,
                        "edited_products": [prod.to_payload() for prod in edited_products],
                    },
                )
                stages.append(stage1)
            else:
                stage1, edited_products = await self._stage_first_edit(
                    page,
                    miaoshou_ctrl,
                    first_edit_ctrl,
                    selection_rows,
                )
                stages.append(stage1)
                stage1_errors = (
                    stage1.details.get("errors") if isinstance(stage1.details, dict) else None
                )
                logger.info(
                    "阶段1完成: success={success}, edited_products={count}, errors={errors}",
                    success=stage1.success,
                    count=len(edited_products),
                    errors=stage1_errors,
                )
                if not stage1.success:
                    errors.append(stage1.message)
                    return WorkflowExecutionResult(workflow_id, False, stages, errors)

            stage2 = await self._stage_claim_products(
                page,
                miaoshou_ctrl,
                edited_products,
            )
            stages.append(stage2)
            if not stage2.success:
                errors.append(stage2.message)
                return WorkflowExecutionResult(workflow_id, False, stages, errors)

            if self.only_claim:
                logger.info("仅认领模式: 停止后续批量编辑与发布阶段")
                stages.append(
                    StageOutcome(
                        name="stage3_batch_edit",
                        success=True,
                        message="仅认领模式: 批量编辑已跳过",
                        details={"skipped": True},
                    )
                )
                stages.append(
                    StageOutcome(
                        name="stage4_publish",
                        success=True,
                        message="仅认领模式: 发布阶段已跳过",
                        details={"skipped": True},
                    )
                )
                total_success = all(stage.success for stage in stages)
                return WorkflowExecutionResult(workflow_id, total_success, stages, errors)

            stage3 = await self._stage_batch_edit(
                page,
                batch_edit_ctrl,
                edited_products,
            )
            stages.append(stage3)
            if not stage3.success:
                errors.append(stage3.message)
                return WorkflowExecutionResult(workflow_id, False, stages, errors)

            stage4 = await self._stage_publish(
                page,
                publish_ctrl,
                edited_products,
            )
            stages.append(stage4)
            if not stage4.success:
                errors.append(stage4.message)

            total_success = stage4.success and all(stage.success for stage in stages)
            return WorkflowExecutionResult(workflow_id, total_success, stages, errors)

        finally:
            if login_ctrl.browser_manager and login_ctrl.browser_manager.browser:
                workflow_failed = errors or any(not stage.success for stage in stages)
                if workflow_failed:
                    logger.warning("检测到阶段失败，保留浏览器以便继续排查，未执行自动关闭。")
                else:
                    await login_ctrl.browser_manager.close()

    async def _stage_first_edit(
        self,
        page,
        miaoshou_ctrl: MiaoshouController,
        first_edit_ctrl: FirstEditController,
        selections: Sequence[ProductSelectionRow],
    ) -> tuple[StageOutcome, list[EditedProduct]]:
        """阶段 1: 妙手公用采集箱首次编辑流程."""

        if not selections:
            return (
                StageOutcome(
                    name="stage1_first_edit",
                    success=False,
                    message="未找到可用的选品数据",
                    details={},
                ),
                [],
            )

        staff_name = selections[0].owner
        staff_name = self._resolve_collection_owner(staff_name)

        if self.skip_first_edit:
            logger.info("首次编辑阶段被配置为跳过")
            placeholders = self._build_placeholder_edits(selections)
            details = {
                "owner": staff_name,
                "edited_products": [prod.to_payload() for prod in placeholders],
                "errors": [],
                "skipped": True,
            }
            return StageOutcome("stage1_first_edit", True, "首次编辑已跳过", details), placeholders

        navigation_success = await miaoshou_ctrl.navigate_and_filter_collection_box(
            page,
            filter_by_user=staff_name,
            switch_to_tab="all",
        )
        if not navigation_success:
            return (
                StageOutcome(
                    name="stage1_first_edit",
                    success=False,
                    message="导航或筛选妙手公用采集箱失败",
                    details={},
                ),
                [],
            )

        async def open_edit_dialog(index: int) -> bool:
            if self.use_codegen_first_edit:
                return await open_edit_dialog_codegen(page, index)
            return await miaoshou_ctrl.click_edit_product_by_index(page, index)

        errors: list[str] = []
        opened_any = False
        processed_products: list[EditedProduct] = []
        first_edit_executor = (
            FirstEditExecutor(first_edit_ctrl) if not self.use_codegen_first_edit else None
        )

        for index, selection in enumerate(selections[: self.collect_count]):
            opened = await open_edit_dialog(index)
            if not opened:
                errors.append(f"第{index + 1}个商品编辑弹窗打开失败")
                continue

            await first_edit_ctrl.wait_for_dialog(page)
            opened_any = True

            try:
                original_title = await first_edit_ctrl.get_original_title(page)
                base_title = original_title or selection.product_name
                payload_dict = self._build_first_edit_payload(selection, base_title)

                if self.use_codegen_first_edit:
                    success = await fill_first_edit_dialog_codegen(page, payload_dict)
                    if not success:
                        errors.append(f"第{index + 1}个商品首次编辑失败")
                        await first_edit_ctrl.close_dialog(page)
                        continue
                    processed_products.append(
                        self._create_edited_product(selection, index, payload_dict["title"])
                    )
                else:
                    assert first_edit_executor is not None
                    payload_model = FirstEditPayload(
                        title=payload_dict["title"],
                        product_number=payload_dict.get("product_number", ""),
                        price=float(payload_dict["price"]),
                        supply_price=float(payload_dict["supply_price"]),
                        source_price=float(
                            payload_dict.get("source_price", payload_dict["supply_price"])
                        ),
                        stock=int(payload_dict["stock"]),
                        weight_g=int(payload_dict["weight_g"]),
                        length_cm=int(payload_dict["length_cm"]),
                        width_cm=int(payload_dict["width_cm"]),
                        height_cm=int(payload_dict["height_cm"]),
                        supplier_link=str(payload_dict.get("supplier_link", "")),
                        specs=payload_dict.get("specs") or [],
                        variants=payload_dict.get("variants") or [],
                    )
                    success = await first_edit_executor.apply(page, payload_model)
                    if not success:
                        errors.append(f"第{index + 1}个商品首次编辑失败")
                        continue
                    processed_products.append(
                        self._create_edited_product(selection, index, payload_model.title)
                    )
            except Exception as exc:
                errors.append(f"第{index + 1}个商品标题更新异常: {exc}")
            finally:
                await first_edit_ctrl.close_dialog(page)
                # await page.wait_for_timeout(500)

        if not opened_any:
            message = "采集箱无可编辑商品,首次编辑阶段跳过"
            logger.warning(message)
            details = {
                "owner": staff_name,
                "edited_products": [],
                "errors": errors or ["未能打开任何首次编辑弹窗"],
                "skipped": True,
            }
            return StageOutcome("stage1_first_edit", True, message, details), []

        success = bool(processed_products)
        message = "完成首次编辑处理" if not errors else "首次编辑存在部分失败"
        details = {
            "owner": staff_name,
            "edited_products": [product.to_payload() for product in processed_products],
            "errors": errors,
        }

        return StageOutcome("stage1_first_edit", success, message, details), processed_products

    def _build_first_edit_payload(
        self,
        selection: ProductSelectionRow,
        base_title: str,
    ) -> dict[str, Any]:
        """根据选品和成本信息构造首次编辑 payload."""

        model_number = selection.model_number or ""
        new_title = self._append_title_suffix(base_title, model_number)

        cost_price = self._resolve_cost_price(selection)
        price_result = self.price_calculator.calculate_batch([cost_price])[0]
        weight_g = self._resolve_weight(selection)
        dimensions = self._resolve_dimensions(selection)
        stock = max(selection.collect_count * 20, 50)

        specs: list[dict[str, Any]] = []
        variants_payload: list[dict[str, Any]] = []

        if selection.spec_options:
            options = [option.strip() for option in selection.spec_options if option.strip()]
            if options:
                specs.append(
                    {
                        "name": selection.spec_unit or "规格",
                        "options": options,
                    }
                )

                for idx, option in enumerate(options):
                    variant_cost = cost_price
                    if selection.variant_costs and idx < len(selection.variant_costs):
                        variant_cost = float(selection.variant_costs[idx])

                    price_variant = self.price_calculator.calculate_batch([variant_cost])[0]
                    variants_payload.append(
                        {
                            "option": option,
                            "price": round(price_variant.suggested_price, 2),
                            "supply_price": round(price_variant.supply_price, 2),
                            "source_price": round(price_variant.real_supply_price, 2),
                            "stock": stock,
                        }
                    )

        payload: dict[str, Any] = {
            "title": new_title,
            "product_number": model_number,
            "price": round(price_result.suggested_price, 2),
            "supply_price": round(price_result.supply_price, 2),
            "source_price": round(price_result.real_supply_price, 2),
            "stock": stock,
            "weight_g": weight_g,
            "length_cm": dimensions[0],
            "width_cm": dimensions[1],
            "height_cm": dimensions[2],
            "supplier_link": "",
            "specs": specs,
            "variants": variants_payload,
        }

        if selection.size_chart_image_url:
            payload["size_chart_image_url"] = selection.size_chart_image_url
            logger.debug("添加尺寸图URL: %s", payload["size_chart_image_url"][:100])

        if getattr(selection, "product_video_url", None):
            payload["product_video_url"] = selection.product_video_url
            logger.debug("添加产品视频URL: %s", payload["product_video_url"][:100])

        return payload

    def _build_placeholder_edits(
        self, selections: Sequence[ProductSelectionRow]
    ) -> list[EditedProduct]:
        """根据选品表构造占位首次编辑结果."""

        placeholders: list[EditedProduct] = []
        for index, selection in enumerate(selections[: self.collect_count]):
            cost_price = self._resolve_cost_price(selection)
            price_result = self.price_calculator.calculate_batch([cost_price])[0]
            weight_g = self._resolve_weight(selection)
            dimensions = self._resolve_dimensions(selection)
            title = self._append_title_suffix(selection.product_name, selection.model_number or "")

            placeholders.append(
                EditedProduct(
                    index=index,
                    selection=selection,
                    title=title,
                    cost_price=cost_price,
                    price=price_result,
                    weight_g=weight_g,
                    dimensions_cm=dimensions,
                )
            )

        return placeholders

    def _create_edited_product(
        self,
        selection: ProductSelectionRow,
        index: int,
        title: str,
    ) -> EditedProduct:
        """构造用于后续阶段的 EditedProduct."""

        cost_price = self._resolve_cost_price(selection)
        price_result = self.price_calculator.calculate_batch([cost_price])[0]
        weight_g = self._resolve_weight(selection)
        dimensions = self._resolve_dimensions(selection)

        return EditedProduct(
            index=index,
            selection=selection,
            title=title,
            cost_price=cost_price,
            price=price_result,
            weight_g=weight_g,
            dimensions_cm=dimensions,
        )

    async def _stage_claim_products(
        self,
        page,
        miaoshou_ctrl: MiaoshouController,
        edited_products: Sequence[EditedProduct],
    ) -> StageOutcome:
        """阶段 2: 5 条链接 x 4 次认领."""

        if self.skip_first_edit:
            message = "首次编辑被跳过, 认领阶段随之跳过"
            logger.warning(message)
            return StageOutcome(
                name="stage2_claim",
                success=True,
                message=message,
                details={"skipped": True, "expected_total": 0},
            )

        if not edited_products:
            message = "首次编辑未产生可认领商品,认领阶段跳过"
            logger.warning(message)
            return StageOutcome(
                name="stage2_claim",
                success=True,
                message=message,
                details={"skipped": True, "expected_total": 0},
            )

        filter_owner: str | None = None
        if edited_products:
            owner_candidate = getattr(edited_products[0].selection, "owner", "") or ""
            try:
                filter_owner = self._resolve_collection_owner(owner_candidate)
            except RuntimeError as exc:
                logger.warning("Unable to resolve collection owner for claim stage: %s", exc)
                filter_owner = None

        await miaoshou_ctrl.refresh_collection_box(page)

        selection_count = min(len(edited_products), 5)
        target_indexes = [
            product.index for product in edited_products[:selection_count] if product.index >= 0
        ]
        if len(target_indexes) < selection_count:
            logger.warning(
                "Incomplete product index mapping detected, fallback to sequential selection",
            )
            target_indexes = list(range(selection_count))

        selection_ok = await miaoshou_ctrl.select_products_for_claim(
            page,
            selection_count,
            indexes=target_indexes,
        )
        if not selection_ok:
            message = "无法选择待认领商品"
            logger.error(message)
            return StageOutcome(
                name="stage2_claim",
                success=False,
                message=message,
                details={"selected": selection_count, "expected": selection_count},
            )

        claim_success = await miaoshou_ctrl.claim_selected_products_to_temu(
            page,
            repeat=self.claim_times,
        )
        if not claim_success:
            message = "认领脚本执行失败"
            logger.error(message)
            return StageOutcome(
                name="stage2_claim",
                success=False,
                message=message,
                details={"selected": selection_count, "expected": selection_count},
        )

        expected_total = selection_count * self.claim_times
        verify_success = await miaoshou_ctrl.verify_claim_success(
            page,
            expected_count=expected_total,
        )
        if not verify_success and claim_success:
            verify_success = await self._retry_claim_verification(
                page,
                miaoshou_ctrl,
                filter_owner,
                expected_total,
        )

        overall_success = claim_success and verify_success
        message = (
            f"认领成功 {expected_total} 次" if overall_success else "认领结果存在异常, 详见 details"
        )

        details = {
            "selected_count": selection_count,
            "claim_success": claim_success,
            "expected_total": expected_total,
            "verify_success": verify_success,
        }

        return StageOutcome("stage2_claim", overall_success, message, details)

    async def _retry_claim_verification(
        self,
        page,
        miaoshou_ctrl: MiaoshouController,
        filter_owner: str | None,
        expected_count: int,
    ) -> bool:
        """Retry claim verification by re-navigating to the claimed tab.

        Args:
            page: Active Playwright page instance.
            miaoshou_ctrl: Active Miaoshou controller.
            filter_owner: Owner filter applied during the initial navigation.
            expected_count: Expected claimed item count.

        Returns:
            True when the claimed count meets the expected threshold after re-navigation.
        """
        logger.info("Fallback: re-open claimed tab to verify claim results")

        try:
            await miaoshou_ctrl.navigate_and_filter_collection_box(
                page,
                filter_by_user=filter_owner,
                switch_to_tab="claimed",
            )
            counts = await miaoshou_ctrl.get_product_count(page)
            claimed_count = counts.get("claimed", 0)
            if claimed_count >= expected_count:
                logger.success(
                    "Fallback verification succeeded via re-navigation: claimed=%s expected>=%s",
                    claimed_count,
                    expected_count,
                )
                return True
            logger.warning(
                "Fallback verification mismatch after re-navigation: claimed=%s expected>=%s",
                claimed_count,
                expected_count,
            )
            return False
        except Exception as exc:
            logger.warning("Fallback claim verification failed: %s", exc)
            return False

    async def _stage_batch_edit(
        self,
        page,
        batch_edit_ctrl: BatchEditController,
        edited_products: Sequence[EditedProduct],
    ) -> StageOutcome:
        """阶段 3: Temu 全托管批量编辑 18 步."""

        if not edited_products:
            message = "无待批量编辑商品,批量编辑阶段跳过"
            logger.warning(message)
            return StageOutcome(
                name="stage3_batch_edit",
                success=True,
                message=message,
                details={"skipped": True},
            )

        reference = edited_products[0]

        if self.use_codegen_batch_edit:
            # 使用 codegen 录制的批量编辑模块(自带导航)
            logger.info("使用 Codegen 录制模块执行批量编辑 18 步")

            payload = {
                "category_path": ["收纳用品", "收纳篮、箱子、盒子", "盖式储物箱"],
                "category_attrs": {
                    "product_use": "多用途",
                    "shape": "其他形状",
                    "material": "其他材料",
                    "closure_type": "其他闭合类型",
                    "style": "当代",
                },
                "outer_package_image": "",  # 从空间选择,不需要本地路径
                "manual_file": str(
                    Path(self.settings.data_input_dir).parent / "manual" / "超多小语种版说明书.pdf"
                ),
            }

            batch_result = await run_batch_edit(page, payload)

            total = batch_result.get("total_steps", 18)
            success_steps = batch_result.get("completed_steps", 0)
            threshold = int(total * 0.9)
            overall_success = batch_result.get("success", False)

            message = (
                f"批量编辑成功 {success_steps}/{total} 步 (Codegen)"
                if overall_success
                else f"批量编辑仅成功 {success_steps}/{total} 步 (Codegen), 低于阈值 {threshold}"
            )

            return StageOutcome(
                name="stage3_batch_edit",
                success=overall_success,
                message=message,
                details=batch_result,
            )
        # 使用原有的批量编辑控制器(需要先导航)
        logger.info("使用原有批量编辑控制器执行 18 步")

        target_count = max(edited_products.__len__() * self.claim_times, 20)
        navigation_ok = await batch_edit_ctrl.navigate_to_batch_edit(select_count=target_count)
        if not navigation_ok:
            return StageOutcome(
                name="stage3_batch_edit",
                success=False,
                message="无法进入Temu全托管批量编辑页面",
                details={},
            )

        payload = {
            "product_name": reference.selection.product_name if reference else "",
            "cost_price": reference.cost_price if reference else 0.0,
            "weight": reference.weight_g if reference else 6000,
            "length": reference.dimensions_cm[0] if reference else 85,
            "width": reference.dimensions_cm[1] if reference else 60,
            "height": reference.dimensions_cm[2] if reference else 50,
        }

        batch_result = await batch_edit_ctrl.execute_all_steps(payload)

        total = batch_result.get("total", 18)
        success_steps = batch_result.get("success", 0)
        threshold = int(total * 0.9)
        overall_success = success_steps >= threshold
        message = (
            f"批量编辑成功 {success_steps}/{total} 步"
            if overall_success
            else f"批量编辑仅成功 {success_steps}/{total} 步, 低于阈值 {threshold}"
        )

        return StageOutcome(
            name="stage3_batch_edit",
            success=overall_success,
            message=message,
            details=batch_result,
        )

    async def _stage_publish(
        self,
        page,
        publish_ctrl: PublishController,
        edited_products: Sequence[EditedProduct],
    ) -> StageOutcome:
        """阶段 4: 选择店铺、设置供货价、批量发布."""

        if not edited_products:
            message = "无待发布商品,发布阶段跳过"
            logger.warning(message)
            return StageOutcome(
                name="stage4_publish",
                success=True,
                message=message,
                details={"skipped": True},
            )

        shop_name = self._resolve_shop_name(edited_products)
        costs = [{"cost": product.cost_price} for product in edited_products]

        selection_ok = await publish_ctrl.select_shop(page, shop_name)
        if not selection_ok:
            return StageOutcome(
                name="stage4_publish",
                success=False,
                message=f"选择店铺 {shop_name} 失败",
                details={},
            )

        set_price_ok = await publish_ctrl.set_supply_price(page, costs)
        publish_ok = await publish_ctrl.batch_publish(page)
        publish_result = await publish_ctrl.check_publish_result(page)

        success = bool(set_price_ok and publish_ok and publish_result.get("success", True))
        message = "批量发布完成" if success else "批量发布存在失败, 请检查发布记录"

        details = {
            "shop_name": shop_name,
            "set_price_success": set_price_ok,
            "publish_result": publish_result,
        }

        return StageOutcome("stage4_publish", success, message, details)

    def _prepare_selection_rows(self) -> list[ProductSelectionRow]:
        """读取/生成选品数据."""

        if not self.selection_table_path:
            raise RuntimeError("未指定选品表, 请通过 --input=路径 提供 Excel 文件")

        if not self.selection_table_path.exists():
            raise FileNotFoundError(
                f"选品表不存在: {self.selection_table_path}. 请确认路径是否正确"
            )

        try:
            rows: list[ProductSelectionRow] = self.selection_reader.read_excel(
                str(self.selection_table_path)
            )
            logger.info(
                "选品表已加载: {} (总计 {} 条)",
                self.selection_table_path,
                len(rows),
            )
        except Exception as exc:
            raise RuntimeError(f"读取选品表失败: {exc}") from exc

        if not rows:
            raise RuntimeError(f"选品表 {self.selection_table_path} 未包含有效数据, 无法继续执行")

        for idx, row in enumerate(rows[: self.collect_count], start=1):
            cost_value = float(row.cost_price) if row.cost_price else 0.0
            logger.info(
                "选品[{}]: 负责人={}, 商品={}, 型号={}, 采集数={}, 成本={:.2f}",
                idx,
                row.owner,
                row.product_name,
                row.model_number,
                row.collect_count,
                cost_value,
            )

        if len(rows) < self.collect_count:
            logger.warning(
                "选品数据仅有 %s 条, 低于预期 %s 条",
                len(rows),
                self.collect_count,
            )

        return list(rows[: self.collect_count])

    def _resolve_credentials(self) -> tuple[str, str]:
        """解析登录凭证."""

        username = (
            os.getenv("MIAOSHOU_USERNAME")
            or os.getenv("TEMU_USERNAME")
            or self.settings.temu_username
        )
        password = (
            os.getenv("MIAOSHOU_PASSWORD")
            or os.getenv("TEMU_PASSWORD")
            or self.settings.temu_password
        )
        return username or "", password or ""

    def _resolve_cost_price(self, selection: ProductSelectionRow) -> float:
        """根据选品或Excel推断成本价."""

        if selection.cost_price:
            return float(selection.cost_price)

        cost = self.product_reader.get_cost_price(selection.product_name)
        if cost:
            return float(cost)

        logger.warning("无法获取成本价, 使用默认 20.0 元")
        return 20.0

    def _resolve_weight(self, selection: ProductSelectionRow) -> int:
        """解析或生成重量 (克)."""

        weight = self.product_reader.get_weight(selection.product_name)
        if weight:
            return int(weight)
        return ProductDataReader.generate_random_weight()

    def _resolve_dimensions(self, selection: ProductSelectionRow) -> tuple[int, int, int]:
        """解析或生成尺寸 (长宽高, 厘米)."""

        dims = self.product_reader.get_dimensions(selection.product_name)
        if dims:
            return (
                int(dims["length"]),
                int(dims["width"]),
                int(dims["height"]),
            )
        random_dims = ProductDataReader.generate_random_dimensions()
        return (
            int(random_dims["length"]),
            int(random_dims["width"]),
            int(random_dims["height"]),
        )

    @staticmethod
    def _append_title_suffix(title: str, suffix: str) -> str:
        """确保标题末尾附加商品编号."""

        base = title.strip()
        normalized_suffix = suffix.strip()
        if not normalized_suffix:
            return base
        if normalized_suffix in base:
            return base
        return f"{base} {normalized_suffix}".strip()

    async def _update_title_only(self, page: Page, title: str) -> bool:
        """仅更新编辑弹窗中的标题字段."""

        selectors = [
            ".collect-box-editor-dialog-V2 input.jx-input__inner[type='text']",
            "input[placeholder*='标题']",
            "input[placeholder*='Title']",
        ]

        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() == 0:
                    continue

                await locator.wait_for(state="visible", timeout=2_000)
                await locator.click()
                await locator.fill("")
                await locator.press("ControlOrMeta+a")
                await locator.fill(title)
                logger.success("✓ 已更新标题: {}", title)
                # await page.wait_for_timeout(300)
                return True
            except Exception:
                continue

        logger.error("✗ 未能找到标题输入框, 无法更新标题")
        return False

    def _resolve_collection_owner(self, owner_value: str) -> str:
        """解析妙手采集箱筛选所需的创建人员显示名."""

        configured_owner = self.settings.business.collection_owner.strip()
        selection_owner = owner_value.strip()
        username = self.settings.miaoshou_username.strip()

        if configured_owner:
            owner = configured_owner
        elif selection_owner:
            owner = selection_owner
        else:
            owner = ""

        if not owner and username:
            owner = username

        if not owner:
            raise RuntimeError("无法解析妙手采集箱创建人员, 请检查配置或选品表")

        if "(" in owner and ")" in owner:
            return owner

        if username:
            return f"{owner}({username})"
        return owner

    def _resolve_image_base_dir(self) -> Path:
        """解析图片基础目录路径.

        优先级:
        1. 环境变量 IMAGE_BASE_DIR
        2. 配置文件中的路径
        3. 默认路径: data/input/10月新品可推

        Returns:
            图片基础目录的 Path 对象.
        """
        # 从环境变量读取
        env_dir = os.getenv("IMAGE_BASE_DIR")
        if env_dir:
            path = Path(env_dir)
            if not path.is_absolute():
                # 如果是相对路径, 相对于项目根目录
                path = self._get_project_root() / path
            return path

        # 使用默认路径
        default_dir = (
            self._get_project_root()
            / "apps"
            / "temu-auto-publish"
            / "data"
            / "input"
            / "10月新品可推"
        )
        return default_dir

    def _get_project_root(self) -> Path:
        """获取项目根目录."""
        # 从当前文件向上查找, 找到包含 pyproject.toml 的目录
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "pyproject.toml").exists():
                return parent
        # 如果找不到, 返回当前文件所在的上上上级目录(apps/temu-auto-publish/src -> apps/temu-auto-publish -> apps -> workspace)
        return Path(__file__).resolve().parents[3]

    def _resolve_shop_name(self, edited_products: Sequence[EditedProduct]) -> str:
        """解析发布店铺名称."""

        env_shop = os.getenv("MIAOSHOU_SHOP_NAME") or os.getenv("TEMU_SHOP_NAME")
        if env_shop:
            return env_shop

        workflow_shop = getattr(self.settings.workflow, "default_shop", None)
        if workflow_shop:
            return str(workflow_shop)

        if edited_products:
            return edited_products[0].selection.owner or "自动化店铺"

        return "自动化店铺"


async def execute_complete_workflow(
    page: Page,
    products_data: Sequence[dict[str, Any]],
    shop_name: str | None = None,
    enable_batch_edit: bool = True,
    enable_publish: bool = True,
) -> dict[str, Any]:
    """兼容旧接口的便捷函数, 代理到遗留工作流实现.

    Args:
        page: Playwright Page 对象(已登录并定位到采集箱)。
        products_data: 产品数据列表(至少 5 个产品字典)。
        shop_name: 发布店铺名称, 可选。
        enable_batch_edit: 是否执行批量编辑阶段。
        enable_publish: 是否执行发布阶段。

    Returns:
        遗留工作流返回的执行结果字典。
    """

    return await legacy_execute_complete_workflow(
        page=page,
        products_data=list(products_data),
        shop_name=shop_name,
        enable_batch_edit=enable_batch_edit,
        enable_publish=enable_publish,
    )


__all__ = [
    "CompletePublishWorkflow",
    "EditedProduct",
    "StageOutcome",
    "WorkflowExecutionResult",
    "execute_complete_workflow",
]
