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
from typing import Any

from loguru import logger

try:  # pragma: no cover - optional dependency
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]

from config.settings import settings

from ..browser.batch_edit_codegen import run_batch_edit
from ..browser.batch_edit_controller_v2 import BatchEditController
from ..browser.first_edit_codegen import open_edit_dialog_codegen
from ..browser.first_edit_controller import FirstEditController
from ..browser.login_controller import LoginController
from ..browser.miaoshou_controller import MiaoshouController
from ..browser.publish_controller import PublishController
from ..data_processor.ai_title_generator import AITitleGenerator
from ..data_processor.price_calculator import PriceCalculator, PriceResult
from ..data_processor.product_data_reader import ProductDataReader
from ..data_processor.selection_table_reader import ProductSelectionRow, SelectionTableReader


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


class CompletePublishWorkflow:
    """Temu 商品发布完整工作流 (SOP 步骤 1-11)."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        selection_table: Path | str | None = None,
        use_ai_titles: bool = True,
        use_codegen_batch_edit: bool = True,
        use_codegen_first_edit: bool = False,
    ) -> None:
        """初始化工作流控制器.

        Args:
            headless: 浏览器是否使用无头模式; None 时读取配置文件.
            selection_table: 选品表路径, 默认读取 data/input/selection.xlsx.
            use_ai_titles: 是否启用 AI 生成标题 (失败时自动回退).
            use_codegen_batch_edit: 是否使用 codegen 录制的批量编辑模块 (默认 True).
        """

        if load_dotenv:  # pragma: no cover - 环境可选
            load_dotenv()

        self.settings = settings
        self.use_ai_titles = use_ai_titles
        self.use_codegen_batch_edit = use_codegen_batch_edit
        self.use_codegen_first_edit = use_codegen_first_edit
        self.collect_count = max(1, min(self.settings.business.collect_count, 5))
        self.claim_times = max(1, self.settings.business.claim_count)
        self.headless = headless if headless is not None else self.settings.browser.headless

        self.selection_table_path = (
            Path(selection_table)
            if selection_table
            else Path(self.settings.data_input_dir) / "selection.xlsx"
        )

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

            stage1, edited_products = await self._stage_first_edit(
                page,
                miaoshou_ctrl,
                first_edit_ctrl,
                selection_rows,
            )
            stages.append(stage1)
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

        original_titles: list[str] = []
        for index in range(len(selections)):
            opened = await open_edit_dialog(index)
            if not opened:
                original_titles.append(selections[index].product_name)
                continue

            await first_edit_ctrl.wait_for_dialog(page)
            title = await first_edit_ctrl.get_original_title(page)
            original_titles.append(title or selections[index].product_name)
            await first_edit_ctrl.close_dialog(page)
            await page.wait_for_timeout(400)

        ai_generator = AITitleGenerator()
        edited_products: list[EditedProduct] = []
        step_errors: list[str] = []

        for index, selection in enumerate(selections[: self.collect_count]):
            opened = await open_edit_dialog(index)
            if not opened:
                step_errors.append(f"第{index + 1}个商品编辑弹窗打开失败")
                continue

            await first_edit_ctrl.wait_for_dialog(page)
            category_ok, category_name = await first_edit_ctrl.check_category(page)
            if not category_ok:
                logger.warning("类目疑似不合规: %s", category_name)

            model_suffix = f"{selection.model_number}型号"
            new_title = await self._generate_title(
                ai_generator,
                original_titles,
                model_suffix,
                index,
            )

            cost_price = self._resolve_cost_price(selection)
            price_result = self.price_calculator.calculate_batch([cost_price])[0]

            weight_g = self._resolve_weight(selection)
            dimensions = self._resolve_dimensions(selection)

            try:
                if self.use_codegen_first_edit:
                    # 使用 codegen 录制的弹窗填写逻辑
                    from ..browser.first_edit_dialog_codegen import fill_first_edit_dialog_codegen

                    payload = {
                        "title": new_title,
                        "origin": "Guangdong,China",
                        "product_use": "多用途",
                        "shape": "矩形",
                        "material": "塑料",
                        "closure_type": "磁性",
                        "style": "现代",
                        "brand_name": "佰森物语",
                        "product_number": selection.model_number or f"RC{index:07d}",
                        "price": price_result.real_supply_price,
                        "stock": 500,
                        "weight_g": weight_g,
                        "length_cm": dimensions[0],
                        "width_cm": dimensions[1],
                        "height_cm": dimensions[2],
                    }

                    edit_success = await fill_first_edit_dialog_codegen(page, payload)
                else:
                    # 使用原有的 FirstEditController
                    edit_success = await first_edit_ctrl.complete_first_edit(
                        page=page,
                        title=new_title,
                        price=price_result.real_supply_price,
                        stock=500,
                        weight=weight_g,
                        dimensions=dimensions,
                    )

                if not edit_success:
                    step_errors.append(f"第{index + 1}个商品首次编辑未完成")
                    continue

                edited_products.append(
                    EditedProduct(
                        index=index,
                        selection=selection,
                        title=new_title,
                        cost_price=cost_price,
                        price=price_result,
                        weight_g=weight_g,
                        dimensions_cm=dimensions,
                    )
                )
            except Exception as exc:
                step_errors.append(f"第{index + 1}个商品编辑异常: {exc}")
            finally:
                await page.wait_for_timeout(600)

        success = len(edited_products) == self.collect_count and not step_errors
        message = (
            f"完成首次编辑 {len(edited_products)}/{self.collect_count} 条"
            if success
            else "部分首次编辑失败, 详见 details.errors"
        )
        details = {
            "owner": staff_name,
            "edited_products": [prod.to_payload() for prod in edited_products],
            "errors": step_errors,
        }

        return StageOutcome("stage1_first_edit", success, message, details), edited_products

    async def _stage_claim_products(
        self,
        page,
        miaoshou_ctrl: MiaoshouController,
        edited_products: Sequence[EditedProduct],
    ) -> StageOutcome:
        """阶段 2: 5 条链接 x 4 次认领."""

        if not edited_products:
            return StageOutcome(
                name="stage2_claim",
                success=False,
                message="无可认领的商品数据",
                details={},
            )

        await miaoshou_ctrl.switch_tab(page, "all")
        claim_results: list[bool] = []

        for product in edited_products:
            success = await miaoshou_ctrl.claim_product_multiple_times(
                page,
                product_index=product.index,
                times=self.claim_times,
            )
            claim_results.append(success)

        expected_total = len(edited_products) * self.claim_times
        verify_success = await miaoshou_ctrl.verify_claim_success(
            page,
            expected_count=expected_total,
        )

        overall_success = all(claim_results) and verify_success
        message = (
            f"认领成功 {expected_total} 次" if overall_success else "认领结果存在异常, 详见 details"
        )

        details = {
            "claim_results": claim_results,
            "expected_total": expected_total,
            "verify_success": verify_success,
        }

        return StageOutcome("stage2_claim", overall_success, message, details)

    async def _stage_batch_edit(
        self,
        page,
        batch_edit_ctrl: BatchEditController,
        edited_products: Sequence[EditedProduct],
    ) -> StageOutcome:
        """阶段 3: Temu 全托管批量编辑 18 步."""

        reference = edited_products[0] if edited_products else None

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
                    Path(self.settings.data_input_dir) / "超多小语种版说明书(1).pdf"
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
        else:
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

        rows: list[ProductSelectionRow] = []
        if self.selection_table_path.exists():
            try:
                rows = self.selection_reader.read_excel(str(self.selection_table_path))
            except Exception as exc:
                logger.warning("读取选品表失败, 使用默认数据: %s", exc)

        if not rows:
            logger.warning("未找到有效选品表, 使用默认占位数据")
            rows = [
                ProductSelectionRow(
                    owner="自动化账号",
                    product_name=f"标准测试商品{i + 1}",
                    model_number=f"A{i + 101:04d}",
                    color_spec="标准",
                    collect_count=self.collect_count,
                    cost_price=20.0,
                )
                for i in range(self.collect_count)
            ]

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

    async def _generate_title(
        self,
        generator: AITitleGenerator,
        original_titles: Sequence[str],
        model_suffix: str,
        product_index: int,
    ) -> str:
        """调用AI或回退方案生成新标题."""

        try:
            titles = await generator.generate_titles(
                list(original_titles),
                model_number=model_suffix,
                use_ai=self.use_ai_titles,
            )
            if titles:
                idx = product_index if product_index < len(titles) else 0
                return titles[idx]
        except Exception as exc:
            logger.warning("AI 生成标题失败, 使用降级方案: %s", exc)

        fallback_source = (
            original_titles[product_index]
            if product_index < len(original_titles)
            else original_titles[0]
        )
        return f"{fallback_source} {model_suffix}"

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


__all__ = [
    "CompletePublishWorkflow",
    "EditedProduct",
    "StageOutcome",
    "WorkflowExecutionResult",
]
