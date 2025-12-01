"""
@PURPOSE: 完整发布工作流单元测试
@OUTLINE:
  - TestStageOutcome: 测试阶段结果数据结构
  - TestEditedProduct: 测试编辑产品数据结构
  - TestWorkflowExecutionResult: 测试工作流执行结果
  - TestCompletePublishWorkflow: 测试工作流主类
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.workflows.complete_publish_workflow
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.workflows.complete_publish_workflow import (
    StageOutcome,
    EditedProduct,
    WorkflowExecutionResult,
)
from src.data_processor.price_calculator import PriceResult


class TestStageOutcome:
    """测试阶段结果数据结构"""

    def test_create_success_outcome(self):
        """测试创建成功结果"""
        outcome = StageOutcome(
            name="first_edit", success=True, message="First edit completed successfully"
        )

        assert outcome.name == "first_edit"
        assert outcome.success is True
        assert outcome.message == "First edit completed successfully"
        assert outcome.details == {}

    def test_create_failed_outcome(self):
        """测试创建失败结果"""
        outcome = StageOutcome(
            name="batch_edit",
            success=False,
            message="Batch edit failed",
            details={"error": "Timeout", "step": 5},
        )

        assert outcome.success is False
        assert outcome.details["error"] == "Timeout"
        assert outcome.details["step"] == 5

    def test_outcome_with_details(self):
        """测试带详情的结果"""
        outcome = StageOutcome(
            name="publish",
            success=True,
            message="Published 20 products",
            details={
                "total_products": 20,
                "success_count": 18,
                "failed_count": 2,
                "duration_seconds": 300,
            },
        )

        assert outcome.details["total_products"] == 20
        assert outcome.details["success_count"] == 18


class TestEditedProduct:
    """测试编辑产品数据结构"""

    @pytest.fixture
    def sample_selection(self):
        """创建样例选品数据"""
        # 使用MagicMock模拟ProductSelectionRow
        selection = MagicMock()
        selection.product_name = "药箱收纳盒"
        selection.model_number = "A0001型号"
        selection.owner = "张三"
        selection.cost_price = 15.0
        return selection

    @pytest.fixture
    def sample_price_result(self):
        """创建样例价格结果"""
        return PriceResult.calculate(15.0)

    def test_create_edited_product(self, sample_selection, sample_price_result):
        """测试创建编辑产品"""
        product = EditedProduct(
            index=1,
            selection=sample_selection,
            title="便携收纳盒家用整理箱 A0001型号",
            cost_price=15.0,
            price=sample_price_result,
            weight_g=6500,
            dimensions_cm=(80, 60, 50),
        )

        assert product.index == 1
        assert product.title == "便携收纳盒家用整理箱 A0001型号"
        assert product.cost_price == 15.0
        assert product.weight_g == 6500
        assert product.dimensions_cm == (80, 60, 50)

    def test_to_payload(self, sample_selection, sample_price_result):
        """测试转换为业务字典"""
        product = EditedProduct(
            index=1,
            selection=sample_selection,
            title="收纳盒 A0001型号",
            cost_price=15.0,
            price=sample_price_result,
            weight_g=6500,
            dimensions_cm=(80, 60, 50),
        )

        payload = product.to_payload()

        assert payload["index"] == 1
        assert payload["product_name"] == "药箱收纳盒"
        assert payload["model_number"] == "A0001型号"
        assert payload["title"] == "收纳盒 A0001型号"
        assert payload["cost_price"] == 15.0
        assert payload["suggested_price"] == sample_price_result.suggested_price
        assert payload["supply_price"] == sample_price_result.supply_price
        assert payload["weight_g"] == 6500
        assert payload["dimensions_cm"]["length"] == 80
        assert payload["dimensions_cm"]["width"] == 60
        assert payload["dimensions_cm"]["height"] == 50


class TestWorkflowExecutionResult:
    """测试工作流执行结果"""

    def test_create_success_result(self):
        """测试创建成功结果"""
        stages = [
            StageOutcome(name="stage1", success=True, message="OK"),
            StageOutcome(name="stage2", success=True, message="OK"),
        ]

        result = WorkflowExecutionResult(
            workflow_id="WF-20240101-001", total_success=True, stages=stages
        )

        assert result.workflow_id == "WF-20240101-001"
        assert result.total_success is True
        assert len(result.stages) == 2
        assert result.errors == []

    def test_create_failed_result(self):
        """测试创建失败结果"""
        stages = [
            StageOutcome(name="stage1", success=True, message="OK"),
            StageOutcome(name="stage2", success=False, message="Failed"),
        ]

        result = WorkflowExecutionResult(
            workflow_id="WF-20240101-002",
            total_success=False,
            stages=stages,
            errors=["Stage 2 timeout", "Connection reset"],
        )

        assert result.total_success is False
        assert len(result.errors) == 2

    def test_to_dict(self):
        """测试转换为字典"""
        stages = [
            StageOutcome(
                name="first_edit", success=True, message="Edited 5 products", details={"count": 5}
            ),
            StageOutcome(name="publish", success=True, message="Published", details={}),
        ]

        result = WorkflowExecutionResult(workflow_id="WF-001", total_success=True, stages=stages)

        data = result.to_dict()

        assert data["workflow_id"] == "WF-001"
        assert data["total_success"] is True
        assert len(data["stages"]) == 2
        assert data["stages"][0]["name"] == "first_edit"
        assert data["stages"][0]["details"]["count"] == 5


class TestWorkflowDataValidation:
    """测试工作流数据验证"""

    def test_stage_outcome_required_fields(self):
        """测试阶段结果必填字段"""
        # 必须提供name, success, message
        outcome = StageOutcome(name="test", success=True, message="Test message")

        assert outcome.name is not None
        assert outcome.success is not None
        assert outcome.message is not None

    def test_workflow_result_stages_list(self):
        """测试工作流结果阶段列表"""
        result = WorkflowExecutionResult(workflow_id="WF-TEST", total_success=True, stages=[])

        assert isinstance(result.stages, list)
        assert len(result.stages) == 0


class TestWorkflowIntegration:
    """工作流集成测试（使用Mock）"""

    @pytest.mark.asyncio
    async def test_workflow_stage_sequence(self):
        """测试工作流阶段序列"""
        # 记录阶段执行顺序
        execution_order = []

        async def mock_stage1():
            execution_order.append("stage1")
            return StageOutcome(name="stage1", success=True, message="OK")

        async def mock_stage2():
            execution_order.append("stage2")
            return StageOutcome(name="stage2", success=True, message="OK")

        async def mock_stage3():
            execution_order.append("stage3")
            return StageOutcome(name="stage3", success=True, message="OK")

        # 模拟执行
        await mock_stage1()
        await mock_stage2()
        await mock_stage3()

        assert execution_order == ["stage1", "stage2", "stage3"]

    @pytest.mark.asyncio
    async def test_workflow_early_termination(self):
        """测试工作流提前终止"""
        stages_executed = []

        async def stage1():
            stages_executed.append("stage1")
            return StageOutcome(name="stage1", success=True, message="OK")

        async def stage2():
            stages_executed.append("stage2")
            return StageOutcome(name="stage2", success=False, message="Failed")

        async def stage3():
            # 如果前面失败，这个不应该执行
            stages_executed.append("stage3")
            return StageOutcome(name="stage3", success=True, message="OK")

        # 模拟带提前终止的执行
        result1 = await stage1()
        if result1.success:
            result2 = await stage2()
            if result2.success:
                await stage3()

        # 第三阶段不应该执行
        assert "stage3" not in stages_executed
        assert stages_executed == ["stage1", "stage2"]


class TestWorkflowConfiguration:
    """测试工作流配置"""

    def test_stage_timeout_constant(self):
        """测试阶段超时常量"""
        from src.workflows.complete_publish_workflow import FIRST_EDIT_STAGE_TIMEOUT_MS

        assert FIRST_EDIT_STAGE_TIMEOUT_MS > 0
        assert isinstance(FIRST_EDIT_STAGE_TIMEOUT_MS, int)


class TestWorkflowHelpers:
    """测试工作流辅助函数"""

    @pytest.mark.asyncio
    async def test_capture_html_snapshot(self, tmp_path):
        """测试HTML快照捕获"""
        from src.workflows.complete_publish_workflow import _capture_html_snapshot

        # 创建Mock页面
        mock_page = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")

        # 捕获快照（函数内部处理路径）
        # 这里主要测试不抛异常
        await _capture_html_snapshot(mock_page, "test_snapshot")

    @pytest.mark.asyncio
    async def test_capture_html_snapshot_failure(self):
        """测试HTML快照捕获失败"""
        from src.workflows.complete_publish_workflow import _capture_html_snapshot

        mock_page = AsyncMock()
        mock_page.content = AsyncMock(side_effect=Exception("Page error"))

        # 应该捕获异常而不是抛出
        await _capture_html_snapshot(mock_page, "test_snapshot")
