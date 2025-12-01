"""
@PURPOSE: 测试 workflows/complete_publish_workflow.py 完整发布工作流
@OUTLINE:
  - class TestStageOutcome: 阶段执行结果数据结构测试
  - class TestEditedProduct: 编辑产品数据结构测试
  - class TestWorkflowExecutionResult: 工作流结果数据结构测试
  - class TestCompletePublishWorkflowInit: 工作流初始化测试
  - class TestCompletePublishWorkflowHelpers: 辅助方法测试
  - class TestCompletePublishWorkflowStages: 各阶段执行测试
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.workflows.complete_publish_workflow
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestStageOutcome:
    """测试 StageOutcome 数据结构."""

    def test_basic_initialization(self) -> None:
        """测试基本初始化."""
        from src.workflows.complete_publish_workflow import StageOutcome

        outcome = StageOutcome(
            name="stage1_first_edit",
            success=True,
            message="阶段完成",
        )

        assert outcome.name == "stage1_first_edit"
        assert outcome.success is True
        assert outcome.message == "阶段完成"
        assert outcome.details == {}

    def test_with_details(self) -> None:
        """测试带详情的初始化."""
        from src.workflows.complete_publish_workflow import StageOutcome

        details = {"edited_count": 5, "errors": []}
        outcome = StageOutcome(
            name="stage2_claim",
            success=False,
            message="认领失败",
            details=details,
        )

        assert outcome.name == "stage2_claim"
        assert outcome.success is False
        assert outcome.details == details
        assert outcome.details["edited_count"] == 5

    def test_slots_attribute(self) -> None:
        """测试 slots 属性限制."""
        from src.workflows.complete_publish_workflow import StageOutcome

        outcome = StageOutcome(name="test", success=True, message="ok")

        # 使用 slots 的 dataclass 不能动态添加属性
        with pytest.raises(AttributeError):
            outcome.new_attribute = "value"  # type: ignore


class TestEditedProduct:
    """测试 EditedProduct 数据结构."""

    @pytest.fixture
    def mock_selection(self):
        """创建模拟选品行."""
        selection = MagicMock()
        selection.product_name = "测试产品"
        selection.model_number = "ABC123"
        selection.owner = "测试员"
        selection.collect_count = 5
        selection.cost_price = 15.0
        return selection

    @pytest.fixture
    def mock_price_result(self):
        """创建模拟价格结果."""
        price = MagicMock()
        price.suggested_price = 50.0
        price.supply_price = 40.0
        price.real_supply_price = 35.0
        return price

    def test_basic_initialization(self, mock_selection, mock_price_result) -> None:
        """测试基本初始化."""
        from src.workflows.complete_publish_workflow import EditedProduct

        product = EditedProduct(
            index=0,
            selection=mock_selection,
            title="测试产品 ABC123",
            cost_price=15.0,
            price=mock_price_result,
            weight_g=500,
            dimensions_cm=(30, 20, 10),
        )

        assert product.index == 0
        assert product.title == "测试产品 ABC123"
        assert product.cost_price == 15.0
        assert product.weight_g == 500
        assert product.dimensions_cm == (30, 20, 10)

    def test_to_payload(self, mock_selection, mock_price_result) -> None:
        """测试转换为业务字典."""
        from src.workflows.complete_publish_workflow import EditedProduct

        product = EditedProduct(
            index=2,
            selection=mock_selection,
            title="测试产品 ABC123",
            cost_price=15.0,
            price=mock_price_result,
            weight_g=500,
            dimensions_cm=(30, 20, 10),
        )

        payload = product.to_payload()

        assert payload["index"] == 2
        assert payload["product_name"] == "测试产品"
        assert payload["model_number"] == "ABC123"
        assert payload["owner"] == "测试员"
        assert payload["title"] == "测试产品 ABC123"
        assert payload["cost_price"] == 15.0
        assert payload["suggested_price"] == 50.0
        assert payload["supply_price"] == 40.0
        assert payload["real_supply_price"] == 35.0
        assert payload["weight_g"] == 500
        assert payload["dimensions_cm"]["length"] == 30
        assert payload["dimensions_cm"]["width"] == 20
        assert payload["dimensions_cm"]["height"] == 10


class TestWorkflowExecutionResult:
    """测试 WorkflowExecutionResult 数据结构."""

    def test_basic_initialization(self) -> None:
        """测试基本初始化."""
        from src.workflows.complete_publish_workflow import (
            StageOutcome,
            WorkflowExecutionResult,
        )

        stages = [
            StageOutcome(name="stage1", success=True, message="ok"),
            StageOutcome(name="stage2", success=True, message="ok"),
        ]

        result = WorkflowExecutionResult(
            workflow_id="test_123",
            total_success=True,
            stages=stages,
        )

        assert result.workflow_id == "test_123"
        assert result.total_success is True
        assert len(result.stages) == 2
        assert result.errors == []

    def test_with_errors(self) -> None:
        """测试带错误的初始化."""
        from src.workflows.complete_publish_workflow import (
            StageOutcome,
            WorkflowExecutionResult,
        )

        stages = [
            StageOutcome(name="stage1", success=True, message="ok"),
            StageOutcome(name="stage2", success=False, message="失败"),
        ]

        result = WorkflowExecutionResult(
            workflow_id="test_456",
            total_success=False,
            stages=stages,
            errors=["认领失败", "网络超时"],
        )

        assert result.total_success is False
        assert len(result.errors) == 2
        assert "认领失败" in result.errors

    def test_to_dict(self) -> None:
        """测试转换为字典."""
        from src.workflows.complete_publish_workflow import (
            StageOutcome,
            WorkflowExecutionResult,
        )

        stages = [
            StageOutcome(
                name="stage1",
                success=True,
                message="完成",
                details={"count": 5},
            ),
        ]

        result = WorkflowExecutionResult(
            workflow_id="test_789",
            total_success=True,
            stages=stages,
            errors=["警告信息"],
        )

        result_dict = result.to_dict()

        assert result_dict["workflow_id"] == "test_789"
        assert result_dict["total_success"] is True
        assert len(result_dict["stages"]) == 1
        assert result_dict["stages"][0]["name"] == "stage1"
        assert result_dict["stages"][0]["details"]["count"] == 5
        assert result_dict["errors"] == ["警告信息"]


class TestCompletePublishWorkflowInit:
    """测试 CompletePublishWorkflow 初始化."""

    @pytest.fixture
    def mock_settings(self):
        """创建模拟配置."""
        with patch("src.workflows.complete_publish_workflow.settings") as mock:
            mock.browser.headless = True
            mock.browser.timeout = 30000
            mock.business.collect_count = 5
            mock.business.claim_count = 5
            mock.business.price_multiplier = 2.5
            mock.business.supply_price_multiplier = 2.0
            mock.business.collection_owner = ""
            mock.temu_username = ""
            mock.temu_password = ""
            mock.miaoshou_username = "test_user"
            yield mock

    def test_default_initialization(self, mock_settings) -> None:
        """测试默认初始化."""
        with patch("src.workflows.complete_publish_workflow.reset_tracker") as mock_tracker:
            mock_tracker.return_value = MagicMock()
            from src.workflows.complete_publish_workflow import CompletePublishWorkflow

            workflow = CompletePublishWorkflow()

            assert workflow.headless is True
            assert workflow.use_ai_titles is False
            assert workflow.use_codegen_batch_edit is False
            assert workflow.skip_first_edit is False
            assert workflow.only_claim is False
            assert workflow.only_stage4_publish is False
            assert workflow.execution_round == 1

    def test_custom_parameters(self, mock_settings) -> None:
        """测试自定义参数初始化."""
        with patch("src.workflows.complete_publish_workflow.reset_tracker") as mock_tracker:
            mock_tracker.return_value = MagicMock()
            from src.workflows.complete_publish_workflow import CompletePublishWorkflow

            workflow = CompletePublishWorkflow(
                headless=False,
                use_ai_titles=True,
                use_codegen_batch_edit=True,
                skip_first_edit=True,
                execution_round=3,
            )

            assert workflow.headless is False
            assert workflow.use_ai_titles is True
            assert workflow.use_codegen_batch_edit is True
            assert workflow.skip_first_edit is True
            assert workflow.execution_round == 3

    def test_only_claim_and_publish_conflict(self, mock_settings) -> None:
        """测试 only_claim 和 only_stage4_publish 冲突."""
        with patch("src.workflows.complete_publish_workflow.reset_tracker") as mock_tracker:
            mock_tracker.return_value = MagicMock()
            from src.workflows.complete_publish_workflow import CompletePublishWorkflow

            with pytest.raises(ValueError, match="不能同时为 True"):
                CompletePublishWorkflow(
                    only_claim=True,
                    only_stage4_publish=True,
                )

    def test_selection_table_path(self, mock_settings, tmp_path) -> None:
        """测试选品表路径设置."""
        with patch("src.workflows.complete_publish_workflow.reset_tracker") as mock_tracker:
            mock_tracker.return_value = MagicMock()
            from src.workflows.complete_publish_workflow import CompletePublishWorkflow

            selection_file = tmp_path / "selection.xlsx"
            workflow = CompletePublishWorkflow(
                selection_table=str(selection_file),
            )

            assert workflow.selection_table_path == selection_file

    def test_execution_round_minimum(self, mock_settings) -> None:
        """测试执行轮次最小值限制."""
        with patch("src.workflows.complete_publish_workflow.reset_tracker") as mock_tracker:
            mock_tracker.return_value = MagicMock()
            from src.workflows.complete_publish_workflow import CompletePublishWorkflow

            workflow = CompletePublishWorkflow(execution_round=-5)

            assert workflow.execution_round == 1

    def test_collect_count_bounds(self, mock_settings) -> None:
        """测试采集数量边界限制."""
        with patch("src.workflows.complete_publish_workflow.reset_tracker") as mock_tracker:
            mock_tracker.return_value = MagicMock()
            from src.workflows.complete_publish_workflow import CompletePublishWorkflow

            # 超过 5 时应被限制为 5
            mock_settings.business.collect_count = 10
            workflow = CompletePublishWorkflow()
            assert workflow.collect_count == 5

            # 低于 1 时应被设为 1
            mock_settings.business.collect_count = 0
            workflow2 = CompletePublishWorkflow()
            assert workflow2.collect_count == 1


class TestCompletePublishWorkflowHelpers:
    """测试 CompletePublishWorkflow 辅助方法."""

    @pytest.fixture
    def mock_workflow(self):
        """创建模拟工作流实例."""
        with (
            patch("src.workflows.complete_publish_workflow.settings") as mock_settings,
            patch("src.workflows.complete_publish_workflow.reset_tracker") as mock_tracker,
        ):
            mock_settings.browser.headless = True
            mock_settings.browser.timeout = 30000
            mock_settings.business.collect_count = 5
            mock_settings.business.claim_count = 5
            mock_settings.business.price_multiplier = 2.5
            mock_settings.business.supply_price_multiplier = 2.0
            mock_settings.business.collection_owner = ""
            mock_settings.temu_username = ""
            mock_settings.temu_password = ""
            mock_settings.miaoshou_username = "test_user"
            mock_tracker.return_value = MagicMock()

            from src.workflows.complete_publish_workflow import CompletePublishWorkflow

            return CompletePublishWorkflow()

    def test_append_title_suffix_with_suffix(self, mock_workflow) -> None:
        """测试标题添加后缀."""
        result = mock_workflow._append_title_suffix("测试产品", "ABC123")
        assert result == "测试产品 ABC123"

    def test_append_title_suffix_already_has_suffix(self, mock_workflow) -> None:
        """测试标题已包含后缀时不重复添加."""
        result = mock_workflow._append_title_suffix("测试产品 ABC123", "ABC123")
        assert result == "测试产品 ABC123"

    def test_append_title_suffix_empty_suffix(self, mock_workflow) -> None:
        """测试空后缀."""
        result = mock_workflow._append_title_suffix("测试产品", "")
        assert result == "测试产品"

    def test_append_title_suffix_whitespace(self, mock_workflow) -> None:
        """测试空白字符处理."""
        result = mock_workflow._append_title_suffix("  测试产品  ", "  ABC123  ")
        assert result == "测试产品 ABC123"

    def test_resolve_cost_price_from_selection(self, mock_workflow) -> None:
        """测试从选品行获取成本价."""
        selection = MagicMock()
        selection.cost_price = 25.5
        selection.product_name = "测试产品"

        result = mock_workflow._resolve_cost_price(selection)
        assert result == 25.5

    def test_resolve_cost_price_fallback_to_default(self, mock_workflow) -> None:
        """测试成本价回退到默认值."""
        selection = MagicMock()
        selection.cost_price = None
        selection.product_name = "未知产品"

        # Mock product_reader.get_cost_price 返回 None
        mock_workflow.product_reader.get_cost_price = MagicMock(return_value=None)

        result = mock_workflow._resolve_cost_price(selection)
        assert result == 20.0

    def test_resolve_weight_from_product_reader(self, mock_workflow) -> None:
        """测试从产品数据读取重量."""
        selection = MagicMock()
        selection.product_name = "测试产品"

        mock_workflow.product_reader.get_weight = MagicMock(return_value=600)

        result = mock_workflow._resolve_weight(selection)
        assert result == 600

    def test_resolve_weight_random_fallback(self, mock_workflow) -> None:
        """测试重量随机生成回退."""
        selection = MagicMock()
        selection.product_name = "未知产品"

        mock_workflow.product_reader.get_weight = MagicMock(return_value=None)

        result = mock_workflow._resolve_weight(selection)
        # 随机生成的重量应该在合理范围内
        assert isinstance(result, int)
        assert result > 0

    def test_resolve_dimensions_from_product_reader(self, mock_workflow) -> None:
        """测试从产品数据读取尺寸."""
        selection = MagicMock()
        selection.product_name = "测试产品"

        mock_workflow.product_reader.get_dimensions = MagicMock(
            return_value={"length": 30, "width": 20, "height": 10}
        )

        result = mock_workflow._resolve_dimensions(selection)
        assert result == (30, 20, 10)

    def test_resolve_dimensions_random_fallback(self, mock_workflow) -> None:
        """测试尺寸随机生成回退."""
        selection = MagicMock()
        selection.product_name = "未知产品"

        mock_workflow.product_reader.get_dimensions = MagicMock(return_value=None)

        result = mock_workflow._resolve_dimensions(selection)
        assert len(result) == 3
        assert all(isinstance(d, int) for d in result)

    def test_resolve_credentials_from_env(self, mock_workflow) -> None:
        """测试从环境变量获取凭证."""
        with patch.dict(
            "os.environ",
            {"MIAOSHOU_USERNAME": "env_user", "MIAOSHOU_PASSWORD": "env_pass"},
        ):
            username, password = mock_workflow._resolve_credentials()
            assert username == "env_user"
            assert password == "env_pass"

    def test_resolve_collection_owner_from_override(self, mock_workflow) -> None:
        """测试从 override 获取创建人员."""
        mock_workflow.collection_owner_override = "覆盖人员"
        mock_workflow.settings.miaoshou_username = "test_user"

        result = mock_workflow._resolve_collection_owner("原始人员")
        assert "覆盖人员" in result

    def test_resolve_collection_owner_raises_on_empty(self, mock_workflow) -> None:
        """测试无法解析创建人员时抛出异常."""
        mock_workflow.collection_owner_override = ""
        mock_workflow.settings.business.collection_owner = ""
        mock_workflow.settings.miaoshou_username = ""

        with pytest.raises(RuntimeError, match="无法解析妙手采集箱创建人员"):
            mock_workflow._resolve_collection_owner("")


class TestCompletePublishWorkflowBuildMethods:
    """测试 CompletePublishWorkflow 构建方法."""

    @pytest.fixture
    def mock_workflow(self):
        """创建模拟工作流实例."""
        with (
            patch("src.workflows.complete_publish_workflow.settings") as mock_settings,
            patch("src.workflows.complete_publish_workflow.reset_tracker") as mock_tracker,
        ):
            mock_settings.browser.headless = True
            mock_settings.browser.timeout = 30000
            mock_settings.business.collect_count = 5
            mock_settings.business.claim_count = 5
            mock_settings.business.price_multiplier = 2.5
            mock_settings.business.supply_price_multiplier = 2.0
            mock_settings.business.collection_owner = ""
            mock_settings.temu_username = ""
            mock_settings.temu_password = ""
            mock_settings.miaoshou_username = "test_user"
            mock_tracker.return_value = MagicMock()

            from src.workflows.complete_publish_workflow import CompletePublishWorkflow

            return CompletePublishWorkflow()

    def test_build_placeholder_edits(self, mock_workflow) -> None:
        """测试构建占位编辑产品."""
        mock_selection = MagicMock()
        mock_selection.product_name = "测试产品"
        mock_selection.model_number = "ABC123"
        mock_selection.owner = "测试员"
        mock_selection.collect_count = 5
        mock_selection.cost_price = 15.0
        mock_selection.spec_options = []
        mock_selection.variant_costs = []

        mock_workflow.product_reader.get_cost_price = MagicMock(return_value=None)
        mock_workflow.product_reader.get_weight = MagicMock(return_value=500)
        mock_workflow.product_reader.get_dimensions = MagicMock(
            return_value={"length": 30, "width": 20, "height": 10}
        )

        placeholders = mock_workflow._build_placeholder_edits([mock_selection])

        assert len(placeholders) == 1
        assert placeholders[0].index == 0
        assert placeholders[0].title == "测试产品 ABC123"
        assert placeholders[0].cost_price == 15.0

    def test_create_edited_product(self, mock_workflow) -> None:
        """测试创建编辑产品."""
        mock_selection = MagicMock()
        mock_selection.product_name = "测试产品"
        mock_selection.cost_price = 20.0

        mock_workflow.product_reader.get_weight = MagicMock(return_value=600)
        mock_workflow.product_reader.get_dimensions = MagicMock(
            return_value={"length": 40, "width": 30, "height": 20}
        )

        product = mock_workflow._create_edited_product(mock_selection, index=5, title="新标题")

        assert product.index == 5
        assert product.title == "新标题"
        assert product.cost_price == 20.0
        assert product.weight_g == 600
        assert product.dimensions_cm == (40, 30, 20)

    def test_build_first_edit_payload(self, mock_workflow) -> None:
        """测试构建首次编辑 payload."""
        mock_selection = MagicMock()
        mock_selection.product_name = "测试产品"
        mock_selection.model_number = "ABC123"
        mock_selection.cost_price = 15.0
        mock_selection.collect_count = 5
        mock_selection.spec_unit = "规格"
        mock_selection.spec_options = ["选项1", "选项2"]
        mock_selection.variant_costs = [15.0, 18.0]
        mock_selection.size_chart_image_url = None
        mock_selection.sku_image_urls = None
        mock_selection.product_video_url = None

        mock_workflow.product_reader.get_weight = MagicMock(return_value=500)
        mock_workflow.product_reader.get_dimensions = MagicMock(
            return_value={"length": 30, "width": 20, "height": 10}
        )

        payload = mock_workflow._build_first_edit_payload(mock_selection, "测试产品")

        assert payload["title"] == "测试产品 ABC123"
        assert payload["product_number"] == "ABC123"
        assert payload["weight_g"] == 500
        assert payload["length_cm"] == 30
        assert payload["width_cm"] == 20
        assert payload["height_cm"] == 10
        assert len(payload["specs"]) == 1
        assert len(payload["variants"]) == 2


class TestCompletePublishWorkflowStages:
    """测试 CompletePublishWorkflow 各阶段执行."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.locator = MagicMock(return_value=MagicMock(count=AsyncMock(return_value=0)))
        page.set_default_timeout = MagicMock()
        return page

    @pytest.fixture
    def mock_workflow_instance(self):
        """创建完整 mock 的工作流实例."""
        with (
            patch("src.workflows.complete_publish_workflow.settings") as mock_settings,
            patch("src.workflows.complete_publish_workflow.reset_tracker") as mock_tracker,
            patch("src.workflows.complete_publish_workflow.LoginController"),
            patch("src.workflows.complete_publish_workflow.MiaoshouController"),
            patch("src.workflows.complete_publish_workflow.FirstEditController"),
            patch("src.workflows.complete_publish_workflow.BatchEditController"),
            patch("src.workflows.complete_publish_workflow.PublishController"),
        ):
            mock_settings.browser.headless = True
            mock_settings.browser.timeout = 30000
            mock_settings.business.collect_count = 5
            mock_settings.business.claim_count = 5
            mock_settings.business.price_multiplier = 2.5
            mock_settings.business.supply_price_multiplier = 2.0
            mock_settings.business.collection_owner = "测试员"
            mock_settings.temu_username = "test_user"
            mock_settings.temu_password = "test_pass"
            mock_settings.miaoshou_username = "test_user"
            mock_tracker.return_value = MagicMock()
            mock_tracker.return_value.stage = MagicMock(
                return_value=MagicMock(
                    __aenter__=AsyncMock(),
                    __aexit__=AsyncMock(),
                )
            )
            mock_tracker.return_value.operation = MagicMock(
                return_value=MagicMock(
                    __aenter__=AsyncMock(),
                    __aexit__=AsyncMock(),
                )
            )

            from src.workflows.complete_publish_workflow import CompletePublishWorkflow

            return CompletePublishWorkflow()

    @pytest.mark.asyncio
    async def test_stage_first_edit_no_selections(self, mock_workflow_instance, mock_page) -> None:
        """测试首次编辑阶段无选品数据."""
        miaoshou_ctrl = MagicMock()
        first_edit_ctrl = MagicMock()

        outcome, products = await mock_workflow_instance._stage_first_edit(
            mock_page, miaoshou_ctrl, first_edit_ctrl, []
        )

        assert outcome.success is False
        assert "未找到可用的选品数据" in outcome.message
        assert products == []

    @pytest.mark.asyncio
    async def test_stage_first_edit_skip_configured(
        self, mock_workflow_instance, mock_page
    ) -> None:
        """测试首次编辑阶段配置跳过."""
        mock_workflow_instance.skip_first_edit = True
        mock_workflow_instance.settings.miaoshou_username = "test_user"

        mock_selection = MagicMock()
        mock_selection.product_name = "测试产品"
        mock_selection.model_number = "ABC123"
        mock_selection.owner = "测试员(test_user)"
        mock_selection.cost_price = 15.0
        mock_selection.spec_options = []
        mock_selection.variant_costs = []

        miaoshou_ctrl = MagicMock()
        miaoshou_ctrl.navigate_and_filter_collection_box = AsyncMock(return_value=True)
        first_edit_ctrl = MagicMock()

        # Mock product reader
        mock_workflow_instance.product_reader.get_weight = MagicMock(return_value=500)
        mock_workflow_instance.product_reader.get_dimensions = MagicMock(
            return_value={"length": 30, "width": 20, "height": 10}
        )

        outcome, _products = await mock_workflow_instance._stage_first_edit(
            mock_page, miaoshou_ctrl, first_edit_ctrl, [mock_selection]
        )

        assert outcome.success is True
        assert "已跳过" in outcome.message
        assert outcome.details["skipped"] is True

    @pytest.mark.asyncio
    async def test_stage_claim_products_skip_when_no_first_edit(
        self, mock_workflow_instance, mock_page
    ) -> None:
        """测试认领阶段跳过当首次编辑被跳过."""
        mock_workflow_instance.skip_first_edit = True

        miaoshou_ctrl = MagicMock()

        outcome = await mock_workflow_instance._stage_claim_products(mock_page, miaoshou_ctrl, [])

        assert outcome.success is True
        assert "跳过" in outcome.message
        assert outcome.details["skipped"] is True

    @pytest.mark.asyncio
    async def test_stage_claim_products_no_edited_products(
        self, mock_workflow_instance, mock_page
    ) -> None:
        """测试认领阶段无编辑产品."""
        mock_workflow_instance.skip_first_edit = False

        miaoshou_ctrl = MagicMock()

        outcome = await mock_workflow_instance._stage_claim_products(mock_page, miaoshou_ctrl, [])

        assert outcome.success is True
        assert "跳过" in outcome.message

    @pytest.mark.asyncio
    async def test_stage_batch_edit_no_products(self, mock_workflow_instance, mock_page) -> None:
        """测试批量编辑阶段无产品."""
        batch_edit_ctrl = MagicMock()

        outcome = await mock_workflow_instance._stage_batch_edit(mock_page, batch_edit_ctrl, [])

        assert outcome.success is True
        assert "跳过" in outcome.message
        assert outcome.details["skipped"] is True

    @pytest.mark.asyncio
    async def test_stage_publish_no_products(self, mock_workflow_instance, mock_page) -> None:
        """测试发布阶段无产品."""
        publish_ctrl = MagicMock()

        outcome = await mock_workflow_instance._stage_publish(mock_page, publish_ctrl, [])

        assert outcome.success is True
        assert "跳过" in outcome.message
        assert outcome.details["skipped"] is True

    @pytest.mark.asyncio
    async def test_stage_publish_shop_selection_failure(
        self, mock_workflow_instance, mock_page
    ) -> None:
        """测试发布阶段店铺选择失败."""
        mock_selection = MagicMock()
        mock_selection.owner = "测试店铺"
        mock_price = MagicMock()
        mock_price.suggested_price = 50.0
        mock_price.supply_price = 40.0
        mock_price.real_supply_price = 35.0

        from src.workflows.complete_publish_workflow import EditedProduct

        edited_product = EditedProduct(
            index=0,
            selection=mock_selection,
            title="测试产品",
            cost_price=15.0,
            price=mock_price,
            weight_g=500,
            dimensions_cm=(30, 20, 10),
        )

        publish_ctrl = MagicMock()
        publish_ctrl.select_shop = AsyncMock(return_value=False)

        outcome = await mock_workflow_instance._stage_publish(
            mock_page, publish_ctrl, [edited_product]
        )

        assert outcome.success is False
        assert "选择店铺" in outcome.message
        assert "失败" in outcome.message


class TestCompletePublishWorkflowExecution:
    """测试 CompletePublishWorkflow 整体执行."""

    @pytest.fixture
    def mock_all_dependencies(self):
        """Mock 所有外部依赖."""
        patches = {
            "settings": patch("src.workflows.complete_publish_workflow.settings"),
            "reset_tracker": patch("src.workflows.complete_publish_workflow.reset_tracker"),
            "get_tracker": patch("src.workflows.complete_publish_workflow.get_tracker"),
            "get_checkpoint_manager": patch(
                "src.workflows.complete_publish_workflow.get_checkpoint_manager"
            ),
            "LoginController": patch("src.workflows.complete_publish_workflow.LoginController"),
            "MiaoshouController": patch(
                "src.workflows.complete_publish_workflow.MiaoshouController"
            ),
            "FirstEditController": patch(
                "src.workflows.complete_publish_workflow.FirstEditController"
            ),
            "BatchEditController": patch(
                "src.workflows.complete_publish_workflow.BatchEditController"
            ),
            "PublishController": patch("src.workflows.complete_publish_workflow.PublishController"),
        }

        started = {}
        for name, p in patches.items():
            started[name] = p.start()

        # Configure settings mock
        started["settings"].browser.headless = True
        started["settings"].browser.timeout = 30000
        started["settings"].business.collect_count = 5
        started["settings"].business.claim_count = 5
        started["settings"].business.price_multiplier = 2.5
        started["settings"].business.supply_price_multiplier = 2.0
        started["settings"].business.collection_owner = "测试员"
        started["settings"].temu_username = "test_user"
        started["settings"].temu_password = "test_pass"
        started["settings"].miaoshou_username = "test_user"
        started["settings"].workflow.default_shop = "默认店铺"

        # Configure tracker mock
        tracker_mock = MagicMock()
        tracker_mock.stage = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(),
                __aexit__=AsyncMock(),
            )
        )
        tracker_mock.operation = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(),
                __aexit__=AsyncMock(),
            )
        )
        tracker_mock.start_workflow = MagicMock()
        tracker_mock.end_workflow = MagicMock()
        tracker_mock.save_to_file = MagicMock()
        started["reset_tracker"].return_value = tracker_mock

        # Configure checkpoint manager mock
        checkpoint_mock = MagicMock()
        checkpoint_mock.load_checkpoint = AsyncMock(return_value=None)
        checkpoint_mock.should_skip_stage = MagicMock(return_value=False)
        checkpoint_mock.mark_stage_complete = AsyncMock()
        checkpoint_mock.mark_stage_failed = AsyncMock()
        checkpoint_mock.clear_checkpoint = AsyncMock()
        started["get_checkpoint_manager"].return_value = checkpoint_mock

        yield started

        for p in patches.values():
            p.stop()

    def test_execute_sync_wrapper(self, mock_all_dependencies) -> None:
        """测试同步执行入口."""
        from src.workflows.complete_publish_workflow import CompletePublishWorkflow

        # Mock selection rows
        mock_selection = MagicMock()
        mock_selection.product_name = "测试产品"
        mock_selection.model_number = "ABC123"
        mock_selection.owner = "测试员(test_user)"
        mock_selection.cost_price = 15.0
        mock_selection.collect_count = 5
        mock_selection.spec_options = []
        mock_selection.variant_costs = []

        workflow = CompletePublishWorkflow(
            selection_rows_override=[mock_selection],
            skip_first_edit=True,
            only_claim=True,
        )

        # Mock login controller
        login_ctrl = mock_all_dependencies["LoginController"].return_value
        login_ctrl.login = AsyncMock(return_value=True)
        login_ctrl.dismiss_login_overlays = AsyncMock()
        login_ctrl._check_login_status = AsyncMock(return_value=False)

        browser_manager = MagicMock()
        mock_page = MagicMock()
        mock_page.wait_for_timeout = AsyncMock()
        mock_page.set_default_timeout = MagicMock()
        browser_manager.page = mock_page
        browser_manager.browser = MagicMock()
        login_ctrl.browser_manager = browser_manager

        # Mock miaoshou controller
        miaoshou_ctrl = mock_all_dependencies["MiaoshouController"].return_value
        miaoshou_ctrl.navigate_and_filter_collection_box = AsyncMock(return_value=True)
        miaoshou_ctrl.refresh_collection_box = AsyncMock()
        miaoshou_ctrl.select_products_by_row_js = AsyncMock(return_value=(5, 0))
        miaoshou_ctrl.claim_selected_products_to_temu = AsyncMock(return_value=True)
        miaoshou_ctrl.verify_claim_success = AsyncMock(return_value=True)

        # Mock product reader
        workflow.product_reader.get_weight = MagicMock(return_value=500)
        workflow.product_reader.get_dimensions = MagicMock(
            return_value={"length": 30, "width": 20, "height": 10}
        )

        # Execute (this will run asyncio.run internally)
        with patch("asyncio.run") as mock_run:
            mock_result = MagicMock()
            mock_result.workflow_id = "test_id"
            mock_result.total_success = True
            mock_result.stages = []
            mock_result.errors = []
            mock_run.return_value = mock_result

            result = workflow.execute()

            mock_run.assert_called_once()
            assert result.workflow_id == "test_id"


class TestCaptureHtmlSnapshot:
    """测试 HTML 快照捕获函数."""

    @pytest.mark.asyncio
    async def test_capture_html_snapshot_success(self, tmp_path) -> None:
        """测试成功捕获 HTML 快照."""
        from src.workflows.complete_publish_workflow import _capture_html_snapshot

        mock_page = MagicMock()
        mock_page.content = AsyncMock(return_value="<html><body>Test</body></html>")

        with patch("src.workflows.complete_publish_workflow.Path"):
            mock_target_root = tmp_path / "debug" / "html"
            mock_target_root.mkdir(parents=True, exist_ok=True)

            # 需要更复杂的 mock 设置来处理 Path 操作
            # 简化测试,只验证函数不抛出异常
            await _capture_html_snapshot(mock_page, "test.html")

    @pytest.mark.asyncio
    async def test_capture_html_snapshot_content_failure(self) -> None:
        """测试获取页面内容失败."""
        from src.workflows.complete_publish_workflow import _capture_html_snapshot

        mock_page = MagicMock()
        mock_page.content = AsyncMock(side_effect=Exception("Network error"))

        # 应该不抛出异常,只记录警告
        await _capture_html_snapshot(mock_page, "test.html")


class TestModuleExports:
    """测试模块导出."""

    def test_all_exports(self) -> None:
        """测试 __all__ 导出."""
        from src.workflows import complete_publish_workflow

        assert "CompletePublishWorkflow" in complete_publish_workflow.__all__
        assert "EditedProduct" in complete_publish_workflow.__all__
        assert "StageOutcome" in complete_publish_workflow.__all__
        assert "WorkflowExecutionResult" in complete_publish_workflow.__all__
        assert "execute_complete_workflow" in complete_publish_workflow.__all__

    def test_execute_complete_workflow_function(self) -> None:
        """测试兼容函数存在."""
        from src.workflows.complete_publish_workflow import execute_complete_workflow

        assert callable(execute_complete_workflow)
