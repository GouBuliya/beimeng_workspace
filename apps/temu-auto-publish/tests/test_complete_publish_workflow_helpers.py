"""
@PURPOSE: CompletePublishWorkflow 辅助方法单元测试
@OUTLINE:
  - TestStageOutcome: 阶段结果 dataclass 测试
  - TestEditedProduct: 编辑产品 dataclass 测试
  - TestWorkflowExecutionResult: 工作流结果 dataclass 测试
  - TestAppendTitleSuffix: 标题后缀处理测试
  - TestResolveHelpers: 解析辅助方法测试
  - TestFinalizeSelectionRows: 选品数据截取测试
  - TestBuildHelpers: 构造辅助方法测试
@DEPENDENCIES:
  - 内部: workflows.complete_publish_workflow
  - 外部: pytest, unittest.mock
"""

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock, patch

import pytest

from src.data_processor.price_calculator import PriceResult
from src.data_processor.selection_table_reader import ProductSelectionRow
from src.workflows.complete_publish_workflow import (
    CompletePublishWorkflow,
    EditedProduct,
    StageOutcome,
    WorkflowExecutionResult,
)


# ============================================================
# StageOutcome dataclass 测试
# ============================================================
class TestStageOutcome:
    """StageOutcome dataclass 测试"""

    def test_basic_creation(self):
        """测试基本创建"""
        outcome = StageOutcome(
            name="stage1_first_edit",
            success=True,
            message="编辑完成",
        )

        assert outcome.name == "stage1_first_edit"
        assert outcome.success is True
        assert outcome.message == "编辑完成"
        assert outcome.details == {}

    def test_creation_with_details(self):
        """测试带详情创建"""
        details = {"count": 5, "duration_ms": 1200}
        outcome = StageOutcome(
            name="stage2_claim",
            success=False,
            message="认领失败",
            details=details,
        )

        assert outcome.name == "stage2_claim"
        assert outcome.success is False
        assert outcome.message == "认领失败"
        assert outcome.details == {"count": 5, "duration_ms": 1200}

    def test_slots_enabled(self):
        """测试 slots 已启用（不能添加新属性）"""
        outcome = StageOutcome(name="test", success=True, message="ok")

        with pytest.raises(AttributeError):
            outcome.new_attr = "value"


# ============================================================
# EditedProduct dataclass 测试
# ============================================================
class TestEditedProduct:
    """EditedProduct dataclass 测试"""

    @pytest.fixture
    def mock_selection(self):
        """创建 mock 选品行"""
        selection = MagicMock(spec=ProductSelectionRow)
        selection.product_name = "测试商品"
        selection.model_number = "ABC123"
        selection.owner = "张三"
        return selection

    @pytest.fixture
    def mock_price_result(self):
        """创建 mock 价格结果"""
        return PriceResult(
            cost_price=25.0,
            suggested_price=99.0,
            supply_price=74.25,
            real_supply_price=74.25,
        )

    @pytest.fixture
    def edited_product(self, mock_selection, mock_price_result):
        """创建 EditedProduct 实例"""
        return EditedProduct(
            index=0,
            selection=mock_selection,
            title="测试商品 ABC123",
            cost_price=25.0,
            price=mock_price_result,
            weight_g=500,
            dimensions_cm=(30, 20, 10),
        )

    def test_basic_creation(self, edited_product):
        """测试基本创建"""
        assert edited_product.index == 0
        assert edited_product.title == "测试商品 ABC123"
        assert edited_product.cost_price == 25.0
        assert edited_product.weight_g == 500
        assert edited_product.dimensions_cm == (30, 20, 10)

    def test_to_payload(self, edited_product):
        """测试 to_payload 方法"""
        payload = edited_product.to_payload()

        assert payload["index"] == 0
        assert payload["product_name"] == "测试商品"
        assert payload["model_number"] == "ABC123"
        assert payload["owner"] == "张三"
        assert payload["title"] == "测试商品 ABC123"
        assert payload["cost_price"] == 25.0
        assert payload["suggested_price"] == 99.0
        assert payload["supply_price"] == 74.25
        assert payload["real_supply_price"] == 74.25
        assert payload["weight_g"] == 500
        assert payload["dimensions_cm"] == {"length": 30, "width": 20, "height": 10}

    def test_to_payload_dimensions_order(self, edited_product):
        """测试 to_payload 尺寸顺序正确"""
        payload = edited_product.to_payload()
        dims = payload["dimensions_cm"]

        assert "length" in dims
        assert "width" in dims
        assert "height" in dims
        assert dims["length"] == 30
        assert dims["width"] == 20
        assert dims["height"] == 10


# ============================================================
# WorkflowExecutionResult dataclass 测试
# ============================================================
class TestWorkflowExecutionResult:
    """WorkflowExecutionResult dataclass 测试"""

    def test_basic_creation(self):
        """测试基本创建"""
        result = WorkflowExecutionResult(
            workflow_id="wf_123",
            total_success=True,
            stages=[],
        )

        assert result.workflow_id == "wf_123"
        assert result.total_success is True
        assert result.stages == []
        assert result.errors == []

    def test_creation_with_stages_and_errors(self):
        """测试带阶段和错误创建"""
        stages = [
            StageOutcome("stage1", True, "成功"),
            StageOutcome("stage2", False, "失败"),
        ]
        errors = ["连接超时", "认领失败"]

        result = WorkflowExecutionResult(
            workflow_id="wf_456",
            total_success=False,
            stages=stages,
            errors=errors,
        )

        assert result.workflow_id == "wf_456"
        assert result.total_success is False
        assert len(result.stages) == 2
        assert len(result.errors) == 2

    def test_to_dict_empty_stages(self):
        """测试 to_dict 空阶段"""
        result = WorkflowExecutionResult(
            workflow_id="wf_789",
            total_success=True,
            stages=[],
        )

        data = result.to_dict()

        assert data["workflow_id"] == "wf_789"
        assert data["total_success"] is True
        assert data["stages"] == []
        assert data["errors"] == []

    def test_to_dict_with_stages(self):
        """测试 to_dict 带阶段"""
        stages = [
            StageOutcome("stage1", True, "完成", {"count": 5}),
            StageOutcome("stage2", False, "失败", {"error": "timeout"}),
        ]

        result = WorkflowExecutionResult(
            workflow_id="wf_abc",
            total_success=False,
            stages=stages,
            errors=["发生错误"],
        )

        data = result.to_dict()

        assert data["workflow_id"] == "wf_abc"
        assert data["total_success"] is False
        assert len(data["stages"]) == 2
        assert data["stages"][0]["name"] == "stage1"
        assert data["stages"][0]["success"] is True
        assert data["stages"][0]["message"] == "完成"
        assert data["stages"][0]["details"] == {"count": 5}
        assert data["stages"][1]["name"] == "stage2"
        assert data["stages"][1]["success"] is False
        assert data["stages"][1]["details"] == {"error": "timeout"}
        assert data["errors"] == ["发生错误"]


# ============================================================
# _append_title_suffix 静态方法测试
# ============================================================
class TestAppendTitleSuffix:
    """_append_title_suffix 静态方法测试"""

    def test_basic_append(self):
        """测试基本追加"""
        result = CompletePublishWorkflow._append_title_suffix("测试商品", "ABC123")

        assert result == "测试商品 ABC123"

    def test_empty_suffix(self):
        """测试空后缀"""
        result = CompletePublishWorkflow._append_title_suffix("测试商品", "")

        assert result == "测试商品"

    def test_whitespace_suffix(self):
        """测试空白后缀"""
        result = CompletePublishWorkflow._append_title_suffix("测试商品", "   ")

        assert result == "测试商品"

    def test_suffix_already_in_title(self):
        """测试后缀已在标题中"""
        result = CompletePublishWorkflow._append_title_suffix("测试商品 ABC123", "ABC123")

        assert result == "测试商品 ABC123"

    def test_suffix_substring_in_title(self):
        """测试后缀是标题子串"""
        result = CompletePublishWorkflow._append_title_suffix("商品ABC123款", "ABC123")

        assert result == "商品ABC123款"

    def test_strip_whitespace(self):
        """测试去除空白"""
        result = CompletePublishWorkflow._append_title_suffix("  测试商品  ", "  ABC123  ")

        assert result == "测试商品 ABC123"

    def test_none_like_suffix(self):
        """测试 None 类似后缀"""
        result = CompletePublishWorkflow._append_title_suffix("测试商品", "")

        assert result == "测试商品"


# ============================================================
# _resolve_* 辅助方法测试
# ============================================================
class TestResolveHelpers:
    """解析辅助方法测试"""

    @pytest.fixture
    def mock_workflow(self, tmp_path):
        """创建 mock 工作流实例"""
        with patch("src.workflows.complete_publish_workflow.LoginController"):
            with patch("src.workflows.complete_publish_workflow.get_checkpoint_manager"):
                workflow = CompletePublishWorkflow(
                    selection_table=None,
                    headless=True,
                )
                # Mock 产品数据读取器
                workflow.product_reader = MagicMock()
                workflow.price_calculator = MagicMock()
                return workflow

    def test_resolve_cost_price_from_selection(self, mock_workflow):
        """测试从选品获取成本价"""
        selection = MagicMock(spec=ProductSelectionRow)
        selection.cost_price = 35.5

        result = mock_workflow._resolve_cost_price(selection)

        assert result == 35.5

    def test_resolve_cost_price_from_product_reader(self, mock_workflow):
        """测试从产品读取器获取成本价"""
        selection = MagicMock(spec=ProductSelectionRow)
        selection.cost_price = None
        selection.product_name = "测试商品"
        mock_workflow.product_reader.get_cost_price.return_value = 42.0

        result = mock_workflow._resolve_cost_price(selection)

        assert result == 42.0
        mock_workflow.product_reader.get_cost_price.assert_called_with("测试商品")

    def test_resolve_cost_price_default(self, mock_workflow):
        """测试默认成本价"""
        selection = MagicMock(spec=ProductSelectionRow)
        selection.cost_price = None
        selection.product_name = "测试商品"
        mock_workflow.product_reader.get_cost_price.return_value = None

        result = mock_workflow._resolve_cost_price(selection)

        assert result == 20.0

    def test_resolve_weight_from_product_reader(self, mock_workflow):
        """测试从产品读取器获取重量"""
        selection = MagicMock(spec=ProductSelectionRow)
        selection.product_name = "测试商品"
        mock_workflow.product_reader.get_weight.return_value = 800

        result = mock_workflow._resolve_weight(selection)

        assert result == 800

    def test_resolve_weight_random(self, mock_workflow):
        """测试随机生成重量"""
        selection = MagicMock(spec=ProductSelectionRow)
        selection.product_name = "测试商品"
        mock_workflow.product_reader.get_weight.return_value = None

        with patch(
            "src.workflows.complete_publish_workflow.ProductDataReader.generate_random_weight",
            return_value=550,
        ):
            result = mock_workflow._resolve_weight(selection)

        assert result == 550

    def test_resolve_dimensions_from_product_reader(self, mock_workflow):
        """测试从产品读取器获取尺寸"""
        selection = MagicMock(spec=ProductSelectionRow)
        selection.product_name = "测试商品"
        mock_workflow.product_reader.get_dimensions.return_value = {
            "length": 30,
            "width": 20,
            "height": 15,
        }

        result = mock_workflow._resolve_dimensions(selection)

        assert result == (30, 20, 15)

    def test_resolve_dimensions_random(self, mock_workflow):
        """测试随机生成尺寸"""
        selection = MagicMock(spec=ProductSelectionRow)
        selection.product_name = "测试商品"
        mock_workflow.product_reader.get_dimensions.return_value = None

        with patch(
            "src.workflows.complete_publish_workflow.ProductDataReader.generate_random_dimensions",
            return_value={"length": 25, "width": 18, "height": 12},
        ):
            result = mock_workflow._resolve_dimensions(selection)

        assert result == (25, 18, 12)


# ============================================================
# _finalize_selection_rows 测试
# ============================================================
class TestFinalizeSelectionRows:
    """_finalize_selection_rows 方法测试"""

    @pytest.fixture
    def mock_workflow(self):
        """创建 mock 工作流"""
        with patch("src.workflows.complete_publish_workflow.LoginController"):
            with patch("src.workflows.complete_publish_workflow.get_checkpoint_manager"):
                workflow = CompletePublishWorkflow(
                    selection_table=None,
                    headless=True,
                    execution_round=1,
                )
                # 手动设置 collect_count（它从 settings 读取）
                workflow.collect_count = 5
                workflow._selection_rows_override = None
                return workflow

    @pytest.fixture
    def mock_rows(self):
        """创建 mock 选品行列表"""
        rows = []
        for i in range(10):
            row = MagicMock(spec=ProductSelectionRow)
            row.owner = f"用户{i}"
            row.product_name = f"商品{i}"
            row.model_number = f"M{i:03d}"
            row.collect_count = 1
            row.cost_price = 20.0 + i
            rows.append(row)
        return rows

    def test_first_round_slice(self, mock_workflow, mock_rows):
        """测试第一轮截取"""
        mock_workflow.execution_round = 1
        mock_workflow.collect_count = 5

        result = mock_workflow._finalize_selection_rows(mock_rows)

        assert len(result) == 5
        assert result[0].product_name == "商品0"
        assert result[4].product_name == "商品4"

    def test_second_round_slice(self, mock_workflow, mock_rows):
        """测试第二轮截取"""
        mock_workflow.execution_round = 2
        mock_workflow.collect_count = 5

        result = mock_workflow._finalize_selection_rows(mock_rows)

        assert len(result) == 5
        assert result[0].product_name == "商品5"
        assert result[4].product_name == "商品9"

    def test_partial_data_warning(self, mock_workflow, mock_rows):
        """测试数据不足时"""
        mock_workflow.execution_round = 3
        mock_workflow.collect_count = 5

        result = mock_workflow._finalize_selection_rows(mock_rows)

        # 第三轮应该没有数据（10条数据，每轮5条，只有2轮）
        assert len(result) == 0

    def test_override_no_slice(self, mock_workflow, mock_rows):
        """测试外部注入数据不截取"""
        mock_workflow._selection_rows_override = mock_rows[:3]

        result = mock_workflow._finalize_selection_rows(mock_rows[:3])

        assert len(result) == 3


# ============================================================
# _build_placeholder_edits 和 _create_edited_product 测试
# ============================================================
class TestBuildHelpers:
    """构造辅助方法测试"""

    @pytest.fixture
    def mock_workflow(self):
        """创建 mock 工作流"""
        with patch("src.workflows.complete_publish_workflow.LoginController"):
            with patch("src.workflows.complete_publish_workflow.get_checkpoint_manager"):
                workflow = CompletePublishWorkflow(
                    selection_table=None,
                    headless=True,
                )
                # 手动设置 collect_count
                workflow.collect_count = 3
                # Mock 依赖
                workflow.product_reader = MagicMock()
                workflow.product_reader.get_cost_price.return_value = None
                workflow.product_reader.get_weight.return_value = None
                workflow.product_reader.get_dimensions.return_value = None

                workflow.price_calculator = MagicMock()
                workflow.price_calculator.calculate_batch.return_value = [
                    PriceResult(
                        cost_price=20.0,
                        suggested_price=79.0,
                        supply_price=59.25,
                        real_supply_price=59.25,
                    ),
                    PriceResult(
                        cost_price=25.0,
                        suggested_price=99.0,
                        supply_price=74.25,
                        real_supply_price=74.25,
                    ),
                    PriceResult(
                        cost_price=30.0,
                        suggested_price=119.0,
                        supply_price=89.25,
                        real_supply_price=89.25,
                    ),
                ]

                return workflow

    @pytest.fixture
    def mock_selections(self):
        """创建 mock 选品列表"""
        selections = []
        for i in range(3):
            sel = MagicMock(spec=ProductSelectionRow)
            sel.product_name = f"商品{i}"
            sel.model_number = f"M{i:03d}"
            sel.owner = f"用户{i}"
            sel.cost_price = 20.0 + i * 5
            selections.append(sel)
        return selections

    def test_build_placeholder_edits(self, mock_workflow, mock_selections):
        """测试构造占位编辑数据"""
        with patch(
            "src.workflows.complete_publish_workflow.ProductDataReader.generate_random_weight",
            return_value=500,
        ):
            with patch(
                "src.workflows.complete_publish_workflow.ProductDataReader.generate_random_dimensions",
                return_value={"length": 30, "width": 20, "height": 10},
            ):
                result = mock_workflow._build_placeholder_edits(mock_selections)

        assert len(result) == 3
        assert all(isinstance(ep, EditedProduct) for ep in result)
        assert result[0].index == 0
        assert result[1].index == 1
        assert result[2].index == 2

    def test_create_edited_product(self, mock_workflow, mock_selections):
        """测试创建单个 EditedProduct"""
        mock_workflow.price_calculator.calculate_batch.return_value = [
            PriceResult(
                cost_price=25.0,
                suggested_price=99.0,
                supply_price=74.25,
                real_supply_price=74.25,
            ),
        ]

        with patch(
            "src.workflows.complete_publish_workflow.ProductDataReader.generate_random_weight",
            return_value=600,
        ):
            with patch(
                "src.workflows.complete_publish_workflow.ProductDataReader.generate_random_dimensions",
                return_value={"length": 35, "width": 25, "height": 15},
            ):
                result = mock_workflow._create_edited_product(
                    mock_selections[0],
                    index=5,
                    title="自定义标题",
                )

        assert result.index == 5
        assert result.title == "自定义标题"
        assert result.weight_g == 600
        assert result.dimensions_cm == (35, 25, 15)


# ============================================================
# 边界情况测试
# ============================================================
class TestEdgeCases:
    """边界情况测试"""

    def test_stage_outcome_empty_details_immutable(self):
        """测试 StageOutcome 空详情是独立的"""
        outcome1 = StageOutcome("test1", True, "ok")
        outcome2 = StageOutcome("test2", True, "ok")

        # 修改 outcome1 的 details 不应影响 outcome2
        outcome1.details["key"] = "value"

        assert outcome1.details == {"key": "value"}
        assert outcome2.details == {}

    def test_workflow_result_errors_copy(self):
        """测试 WorkflowExecutionResult.to_dict 复制 errors"""
        errors = ["error1", "error2"]
        result = WorkflowExecutionResult(
            workflow_id="test",
            total_success=False,
            stages=[],
            errors=errors,
        )

        data = result.to_dict()
        data["errors"].append("error3")

        # 原始 errors 不应被修改
        assert len(result.errors) == 2

    def test_append_title_suffix_unicode(self):
        """测试 Unicode 标题处理"""
        result = CompletePublishWorkflow._append_title_suffix("日本进口商品🎁", "JP-001")

        assert result == "日本进口商品🎁 JP-001"

    def test_edited_product_zero_values(self):
        """测试 EditedProduct 零值"""
        selection = MagicMock(spec=ProductSelectionRow)
        selection.product_name = "测试"
        selection.model_number = ""
        selection.owner = ""

        price = PriceResult(
            cost_price=0.0,
            suggested_price=0.0,
            supply_price=0.0,
            real_supply_price=0.0,
        )

        product = EditedProduct(
            index=0,
            selection=selection,
            title="测试",
            cost_price=0.0,
            price=price,
            weight_g=0,
            dimensions_cm=(0, 0, 0),
        )

        payload = product.to_payload()

        assert payload["cost_price"] == 0.0
        assert payload["weight_g"] == 0
        assert payload["dimensions_cm"] == {"length": 0, "width": 0, "height": 0}
