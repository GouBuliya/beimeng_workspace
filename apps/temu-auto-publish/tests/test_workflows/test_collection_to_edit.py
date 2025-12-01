"""
@PURPOSE: 测试 workflows/collection_to_edit_workflow.py 采集到编辑集成工作流
@OUTLINE:
  - class TestCollectionToEditWorkflowInit: 初始化测试
  - class TestStages: 各阶段测试
  - class TestFullExecution: 完整执行测试
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.workflows.collection_to_edit_workflow
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCollectionToEditWorkflowInit:
    """测试 CollectionToEditWorkflow 初始化."""

    def test_default_initialization(self) -> None:
        """测试默认初始化."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow()

            assert workflow.use_ai_titles is True
            assert workflow.debug_mode is False
            assert workflow.output_dir is not None

    def test_custom_initialization(self, tmp_path: Path) -> None:
        """测试自定义初始化."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            output_dir = tmp_path / "custom_output"
            workflow = CollectionToEditWorkflow(
                use_ai_titles=False,
                output_dir=str(output_dir),
                debug_mode=True,
            )

            assert workflow.use_ai_titles is False
            assert workflow.debug_mode is True
            assert workflow.output_dir == output_dir

    def test_output_dir_created(self, tmp_path: Path) -> None:
        """测试输出目录自动创建."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            output_dir = tmp_path / "new_output" / "nested"
            workflow = CollectionToEditWorkflow(output_dir=str(output_dir))

            assert output_dir.exists()


class TestStages:
    """测试各阶段方法."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        # Mock context
        context = MagicMock()
        new_page = MagicMock()
        new_page.goto = AsyncMock()
        new_page.wait_for_timeout = AsyncMock()
        new_page.close = AsyncMock()
        context.new_page = AsyncMock(return_value=new_page)
        page.context = context

        return page

    @pytest.fixture
    def sample_products(self):
        """创建示例产品数据."""
        product1 = MagicMock()
        product1.product_name = "药箱收纳盒"
        product1.model_number = "YX001"
        product1.cost_price = 10.0
        product1.color_spec = "白色"
        product1.collect_count = 5

        product2 = MagicMock()
        product2.product_name = "手机支架"
        product2.model_number = "SJ002"
        product2.cost_price = 5.0
        product2.color_spec = "黑色"
        product2.collect_count = 3

        return [product1, product2]

    @pytest.mark.asyncio
    async def test_stage_collect_from_temu(self, mock_page, sample_products) -> None:
        """测试阶段1: Temu采集."""
        with (
            patch(
                "src.workflows.collection_to_edit_workflow.CollectionController"
            ) as mock_collection_cls,
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            mock_collection = MagicMock()
            mock_collection.search_products = AsyncMock(return_value=True)
            mock_collection.collect_links = AsyncMock(return_value=[{"url": "https://temu.com/1"}])
            mock_collection_cls.return_value = mock_collection

            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow()
            result = await workflow._stage_collect_from_temu(mock_page, sample_products)

            assert result["success"] is True
            assert result["success_count"] > 0
            assert len(result["collected_links"]) > 0

    @pytest.mark.asyncio
    async def test_stage_collect_from_temu_failure(self, mock_page, sample_products) -> None:
        """测试阶段1失败场景."""
        with (
            patch(
                "src.workflows.collection_to_edit_workflow.CollectionController"
            ) as mock_collection_cls,
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            mock_collection = MagicMock()
            mock_collection.search_products = AsyncMock(return_value=False)
            mock_collection_cls.return_value = mock_collection

            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow()
            result = await workflow._stage_collect_from_temu(mock_page, sample_products)

            assert result["success"] is False
            assert result["failed_count"] > 0

    @pytest.mark.asyncio
    async def test_stage_add_to_miaoshou(self, mock_page) -> None:
        """测试阶段2: 添加到妙手."""
        with (
            patch(
                "src.workflows.collection_to_edit_workflow.CollectionController"
            ) as mock_collection_cls,
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            mock_collection = MagicMock()
            mock_collection.add_to_miaoshou_collection_box = AsyncMock(
                return_value={
                    "success": True,
                    "success_count": 2,
                    "total": 2,
                }
            )
            mock_collection_cls.return_value = mock_collection

            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow()
            urls = ["https://temu.com/1", "https://temu.com/2"]
            result = await workflow._stage_add_to_miaoshou(mock_page, urls)

            assert result["success"] is True
            assert result["success_count"] == 2

    @pytest.mark.asyncio
    async def test_stage_navigate_to_collection_box(self, mock_page) -> None:
        """测试阶段3: 导航到采集箱."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch(
                "src.workflows.collection_to_edit_workflow.MiaoshouController"
            ) as mock_miaoshou_cls,
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            mock_miaoshou = MagicMock()
            mock_miaoshou.navigate_and_filter_collection_box = AsyncMock(return_value=True)
            mock_miaoshou_cls.return_value = mock_miaoshou

            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow()
            result = await workflow._stage_navigate_to_collection_box(
                mock_page, filter_by_user="测试用户"
            )

            assert result["success"] is True
            assert result["filter_by_user"] == "测试用户"

    @pytest.mark.asyncio
    async def test_stage_verify_collection(self, mock_page) -> None:
        """测试阶段4: 验证采集结果."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch(
                "src.workflows.collection_to_edit_workflow.MiaoshouController"
            ) as mock_miaoshou_cls,
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            mock_miaoshou = MagicMock()
            mock_miaoshou.verify_collected_products = AsyncMock(
                return_value={"success": True, "verified_count": 5}
            )
            mock_miaoshou_cls.return_value = mock_miaoshou

            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow()
            result = await workflow._stage_verify_collection(
                mock_page,
                expected_count=5,
                product_keywords=["产品1", "产品2"],
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_stage_first_edit(self, mock_page, sample_products) -> None:
        """测试阶段5: 首次编辑."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch(
                "src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"
            ) as mock_five_cls,
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            mock_five = MagicMock()
            mock_five.execute = AsyncMock(return_value={"success": True, "edited_count": 2})
            mock_five_cls.return_value = mock_five

            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow()
            result = await workflow._stage_first_edit(
                mock_page, sample_products, skip_temu_collection=True
            )

            assert result["edited_count"] == 2


class TestFullExecution:
    """测试完整执行流程."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        context = MagicMock()
        new_page = MagicMock()
        new_page.goto = AsyncMock()
        new_page.wait_for_timeout = AsyncMock()
        new_page.close = AsyncMock()
        context.new_page = AsyncMock(return_value=new_page)
        page.context = context

        return page

    @pytest.fixture
    def sample_products(self):
        """创建示例产品数据."""
        product = MagicMock()
        product.product_name = "测试产品"
        product.model_number = "TEST001"
        product.cost_price = 10.0
        product.color_spec = "红色"
        product.collect_count = 5
        return [product]

    @pytest.mark.asyncio
    async def test_execute_simplified_mode(self, mock_page, sample_products, tmp_path) -> None:
        """测试简化模式执行."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch(
                "src.workflows.collection_to_edit_workflow.MiaoshouController"
            ) as mock_miaoshou_cls,
            patch(
                "src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"
            ) as mock_five_cls,
            patch(
                "src.workflows.collection_to_edit_workflow.SelectionTableReader"
            ) as mock_reader_cls,
        ):
            # Setup mocks
            mock_reader = MagicMock()
            mock_reader.read_excel = MagicMock(return_value=sample_products)
            mock_reader_cls.return_value = mock_reader

            mock_miaoshou = MagicMock()
            mock_miaoshou.navigate_and_filter_collection_box = AsyncMock(return_value=True)
            mock_miaoshou.verify_collected_products = AsyncMock(return_value={"success": True})
            mock_miaoshou_cls.return_value = mock_miaoshou

            mock_five = MagicMock()
            mock_five.execute = AsyncMock(return_value={"success": True, "edited_count": 1})
            mock_five_cls.return_value = mock_five

            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow(output_dir=str(tmp_path))
            result = await workflow.execute(
                mock_page,
                selection_table_path="test.xlsx",
                skip_temu_collection=True,  # 简化模式
                enable_validation=True,
            )

            assert result["success"] is True
            assert result["stages"]["stage1"]["skipped"] is True
            assert result["stages"]["stage2"]["skipped"] is True
            assert result["stages"]["stage3"]["success"] is True
            assert result["summary"]["edited_products"] == 1

    @pytest.mark.asyncio
    async def test_execute_empty_products(self, mock_page, tmp_path) -> None:
        """测试空产品列表."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch(
                "src.workflows.collection_to_edit_workflow.SelectionTableReader"
            ) as mock_reader_cls,
        ):
            mock_reader = MagicMock()
            mock_reader.read_excel = MagicMock(return_value=[])  # 空列表
            mock_reader_cls.return_value = mock_reader

            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow(output_dir=str(tmp_path))
            result = await workflow.execute(
                mock_page,
                selection_table_path="test.xlsx",
            )

            assert result["success"] is False
            assert "没有有效产品" in str(result["errors"])

    @pytest.mark.asyncio
    async def test_execute_stage3_failure(self, mock_page, sample_products, tmp_path) -> None:
        """测试阶段3失败."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch(
                "src.workflows.collection_to_edit_workflow.MiaoshouController"
            ) as mock_miaoshou_cls,
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch(
                "src.workflows.collection_to_edit_workflow.SelectionTableReader"
            ) as mock_reader_cls,
        ):
            mock_reader = MagicMock()
            mock_reader.read_excel = MagicMock(return_value=sample_products)
            mock_reader_cls.return_value = mock_reader

            mock_miaoshou = MagicMock()
            mock_miaoshou.navigate_and_filter_collection_box = AsyncMock(
                return_value=False  # 导航失败
            )
            mock_miaoshou_cls.return_value = mock_miaoshou

            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow(output_dir=str(tmp_path))
            result = await workflow.execute(
                mock_page,
                selection_table_path="test.xlsx",
                skip_temu_collection=True,
            )

            assert result["success"] is False
            assert "阶段3失败" in str(result["errors"])


class TestHelperMethods:
    """测试辅助方法."""

    def test_save_intermediate_result(self, tmp_path) -> None:
        """测试保存中间结果."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow(output_dir=str(tmp_path))
            result = {"test_key": "test_value"}

            filepath = workflow._save_intermediate_result("test_stage", result)

            assert Path(filepath).exists()
            assert "test_stage" in filepath

    def test_save_final_report(self, tmp_path) -> None:
        """测试保存最终报告."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow(output_dir=str(tmp_path))
            result = {
                "success": True,
                "summary": {"total": 5},
            }

            filepath = workflow._save_final_report(result)

            assert Path(filepath).exists()
            assert "collection_to_edit_report" in filepath

    def test_display_final_summary(self, tmp_path) -> None:
        """测试显示最终总结."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow(output_dir=str(tmp_path))
            result = {
                "success": True,
                "summary": {
                    "total_products": 5,
                    "collected_products": 5,
                    "added_to_miaoshou": 5,
                    "edited_products": 5,
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                },
                "errors": [],
            }

            # 不应抛出异常
            workflow._display_final_summary(result)

    def test_display_final_summary_with_errors(self, tmp_path) -> None:
        """测试显示带错误的最终总结."""
        with (
            patch("src.workflows.collection_to_edit_workflow.CollectionController"),
            patch("src.workflows.collection_to_edit_workflow.MiaoshouController"),
            patch("src.workflows.collection_to_edit_workflow.FiveToTwentyWorkflow"),
            patch("src.workflows.collection_to_edit_workflow.SelectionTableReader"),
        ):
            from src.workflows.collection_to_edit_workflow import CollectionToEditWorkflow

            workflow = CollectionToEditWorkflow(output_dir=str(tmp_path))
            result = {
                "success": False,
                "summary": {
                    "total_products": 5,
                    "collected_products": 0,
                    "added_to_miaoshou": 0,
                    "edited_products": 0,
                    "start_time": datetime.now().isoformat(),
                    "end_time": datetime.now().isoformat(),
                },
                "errors": ["错误1", "错误2"],
            }

            # 不应抛出异常
            workflow._display_final_summary(result)
