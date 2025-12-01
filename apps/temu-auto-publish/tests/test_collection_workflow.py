"""
@PURPOSE: 测试 workflows/collection_workflow.py 商品采集工作流
@OUTLINE:
  - class TestCollectionResult: 测试采集结果数据结构
  - class TestCollectionWorkflowInit: 测试工作流初始化
  - class TestCollectionWorkflowExecute: 测试执行流程
  - class TestCollectionWorkflowHelpers: 测试辅助方法
  - class TestCollectionWorkflowExport: 测试导出功能
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.workflows.collection_workflow
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCollectionResult:
    """测试 CollectionResult 数据结构."""

    @pytest.fixture
    def mock_product(self):
        """创建模拟产品数据."""
        product = MagicMock()
        product.owner = "测试员"
        product.product_name = "药箱收纳盒"
        product.model_number = "ABC123"
        product.color_spec = "白色"
        product.collect_count = 5
        return product

    def test_success_result(self, mock_product) -> None:
        """测试成功的采集结果."""
        from src.workflows.collection_workflow import CollectionResult

        collected_links = [
            {"url": "https://temu.com/1", "title": "商品1"},
            {"url": "https://temu.com/2", "title": "商品2"},
        ]

        result = CollectionResult(
            product=mock_product,
            collected_links=collected_links,
            success=True,
        )

        assert result.success is True
        assert result.error is None
        assert len(result.collected_links) == 2
        assert result.product == mock_product
        assert result.timestamp is not None

    def test_failed_result(self, mock_product) -> None:
        """测试失败的采集结果."""
        from src.workflows.collection_workflow import CollectionResult

        result = CollectionResult(
            product=mock_product,
            collected_links=[],
            success=False,
            error="搜索失败，未找到商品",
        )

        assert result.success is False
        assert result.error == "搜索失败，未找到商品"
        assert len(result.collected_links) == 0

    def test_to_dict(self, mock_product) -> None:
        """测试转换为字典."""
        from src.workflows.collection_workflow import CollectionResult

        collected_links = [{"url": "https://temu.com/1", "title": "商品1"}]

        result = CollectionResult(
            product=mock_product,
            collected_links=collected_links,
            success=True,
        )

        result_dict = result.to_dict()

        assert result_dict["product"]["owner"] == "测试员"
        assert result_dict["product"]["product_name"] == "药箱收纳盒"
        assert result_dict["product"]["model_number"] == "ABC123"
        assert result_dict["success"] is True
        assert len(result_dict["collected_links"]) == 1
        assert "timestamp" in result_dict


class TestCollectionWorkflowInit:
    """测试 CollectionWorkflow 初始化."""

    def test_default_init(self) -> None:
        """测试默认初始化."""
        with patch("src.workflows.collection_workflow.CollectionController"):
            from src.workflows.collection_workflow import CollectionWorkflow

            workflow = CollectionWorkflow()

            assert workflow.collection_ctrl is not None
            assert workflow.table_reader is not None
            assert workflow.output_dir.exists() or not workflow.output_dir.exists()

    def test_custom_output_dir(self, tmp_path) -> None:
        """测试自定义输出目录."""
        with patch("src.workflows.collection_workflow.CollectionController"):
            from src.workflows.collection_workflow import CollectionWorkflow

            output_dir = tmp_path / "custom_output"
            workflow = CollectionWorkflow(output_dir=str(output_dir))

            assert workflow.output_dir == output_dir
            assert output_dir.exists()

    def test_controller_instances(self) -> None:
        """测试控制器实例创建."""
        with patch("src.workflows.collection_workflow.CollectionController") as mock_ctrl:
            from src.workflows.collection_workflow import CollectionWorkflow

            workflow = CollectionWorkflow()

            mock_ctrl.assert_called_once()
            assert workflow.collection_ctrl == mock_ctrl.return_value


class TestCollectionWorkflowExecute:
    """测试 CollectionWorkflow 执行流程."""

    @pytest.fixture
    def mock_workflow(self, tmp_path):
        """创建模拟工作流."""
        with patch("src.workflows.collection_workflow.CollectionController"):
            from src.workflows.collection_workflow import CollectionWorkflow

            workflow = CollectionWorkflow(output_dir=str(tmp_path))
            workflow.collection_ctrl = MagicMock()
            workflow.table_reader = MagicMock()

            return workflow

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        return page

    @pytest.fixture
    def sample_products(self):
        """创建示例产品列表."""
        product1 = MagicMock()
        product1.owner = "测试员"
        product1.product_name = "药箱收纳盒"
        product1.model_number = "ABC123"
        product1.color_spec = "白色"
        product1.collect_count = 3

        product2 = MagicMock()
        product2.owner = "测试员"
        product2.product_name = "手机支架"
        product2.model_number = "DEF456"
        product2.color_spec = "黑色"
        product2.collect_count = 2

        return [product1, product2]

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_workflow, mock_page, sample_products, tmp_path
    ) -> None:
        """测试成功执行采集流程."""
        # Setup mocks
        mock_workflow.table_reader.read_excel = MagicMock(return_value=sample_products)
        mock_workflow.collection_ctrl.visit_store = AsyncMock(return_value=True)
        mock_workflow.collection_ctrl.search_products = AsyncMock(return_value=True)
        mock_workflow.collection_ctrl.collect_links = AsyncMock(
            return_value=[
                {"url": "https://temu.com/1", "title": "商品1", "price": "10.00"},
                {"url": "https://temu.com/2", "title": "商品2", "price": "15.00"},
            ]
        )

        result = await mock_workflow.execute(
            mock_page,
            selection_table_path="data/selection.xlsx",
            save_report=False,
        )

        assert result["summary"]["total_products"] == 2
        assert result["summary"]["success"] == 2
        assert result["summary"]["failed"] == 0
        mock_workflow.collection_ctrl.visit_store.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_empty_products(self, mock_workflow, mock_page) -> None:
        """测试空产品列表."""
        mock_workflow.table_reader.read_excel = MagicMock(return_value=[])

        result = await mock_workflow.execute(
            mock_page,
            selection_table_path="data/selection.xlsx",
            save_report=False,
        )

        assert result["summary"]["total_products"] == 0
        assert result["products"] == []

    @pytest.mark.asyncio
    async def test_execute_visit_store_failure(
        self, mock_workflow, mock_page, sample_products
    ) -> None:
        """测试访问店铺失败."""
        mock_workflow.table_reader.read_excel = MagicMock(return_value=sample_products)
        mock_workflow.collection_ctrl.visit_store = AsyncMock(return_value=False)

        with pytest.raises(RuntimeError, match="无法访问Temu店铺"):
            await mock_workflow.execute(
                mock_page,
                selection_table_path="data/selection.xlsx",
            )

    @pytest.mark.asyncio
    async def test_execute_skip_visit_store(
        self, mock_workflow, mock_page, sample_products
    ) -> None:
        """测试跳过访问店铺."""
        mock_workflow.table_reader.read_excel = MagicMock(return_value=sample_products)
        mock_workflow.collection_ctrl.search_products = AsyncMock(return_value=True)
        mock_workflow.collection_ctrl.collect_links = AsyncMock(
            return_value=[{"url": "https://temu.com/1", "title": "商品"}]
        )

        result = await mock_workflow.execute(
            mock_page,
            selection_table_path="data/selection.xlsx",
            skip_visit_store=True,
            save_report=False,
        )

        mock_workflow.collection_ctrl.visit_store.assert_not_called()
        assert result["summary"]["total_products"] == 2

    @pytest.mark.asyncio
    async def test_execute_search_failure(
        self, mock_workflow, mock_page, sample_products
    ) -> None:
        """测试搜索失败."""
        mock_workflow.table_reader.read_excel = MagicMock(return_value=sample_products)
        mock_workflow.collection_ctrl.visit_store = AsyncMock(return_value=True)
        mock_workflow.collection_ctrl.search_products = AsyncMock(return_value=False)

        result = await mock_workflow.execute(
            mock_page,
            selection_table_path="data/selection.xlsx",
            save_report=False,
        )

        assert result["summary"]["failed"] == 2
        assert result["summary"]["success"] == 0

    @pytest.mark.asyncio
    async def test_execute_collect_no_links(
        self, mock_workflow, mock_page, sample_products
    ) -> None:
        """测试采集无链接."""
        mock_workflow.table_reader.read_excel = MagicMock(return_value=sample_products)
        mock_workflow.collection_ctrl.visit_store = AsyncMock(return_value=True)
        mock_workflow.collection_ctrl.search_products = AsyncMock(return_value=True)
        mock_workflow.collection_ctrl.collect_links = AsyncMock(return_value=[])

        result = await mock_workflow.execute(
            mock_page,
            selection_table_path="data/selection.xlsx",
            save_report=False,
        )

        assert result["summary"]["failed"] == 2
        assert result["summary"]["total_links"] == 0

    @pytest.mark.asyncio
    async def test_execute_exception_in_collection(
        self, mock_workflow, mock_page, sample_products
    ) -> None:
        """测试采集过程中异常."""
        mock_workflow.table_reader.read_excel = MagicMock(return_value=sample_products)
        mock_workflow.collection_ctrl.visit_store = AsyncMock(return_value=True)
        mock_workflow.collection_ctrl.search_products = AsyncMock(
            side_effect=[Exception("网络错误"), True]
        )
        mock_workflow.collection_ctrl.collect_links = AsyncMock(
            return_value=[{"url": "https://temu.com/1", "title": "商品"}]
        )

        result = await mock_workflow.execute(
            mock_page,
            selection_table_path="data/selection.xlsx",
            save_report=False,
        )

        # 第一个产品失败，第二个成功
        assert result["summary"]["success"] == 1
        assert result["summary"]["failed"] == 1

    @pytest.mark.asyncio
    async def test_execute_read_excel_failure(self, mock_workflow, mock_page) -> None:
        """测试读取Excel失败."""
        mock_workflow.table_reader.read_excel = MagicMock(
            side_effect=FileNotFoundError("文件不存在")
        )

        with pytest.raises(FileNotFoundError):
            await mock_workflow.execute(
                mock_page,
                selection_table_path="data/nonexistent.xlsx",
            )

    @pytest.mark.asyncio
    async def test_execute_save_report(
        self, mock_workflow, mock_page, sample_products, tmp_path
    ) -> None:
        """测试保存报告."""
        mock_workflow.table_reader.read_excel = MagicMock(return_value=sample_products)
        mock_workflow.collection_ctrl.visit_store = AsyncMock(return_value=True)
        mock_workflow.collection_ctrl.search_products = AsyncMock(return_value=True)
        mock_workflow.collection_ctrl.collect_links = AsyncMock(
            return_value=[{"url": "https://temu.com/1", "title": "商品"}]
        )

        result = await mock_workflow.execute(
            mock_page,
            selection_table_path="data/selection.xlsx",
            save_report=True,
        )

        assert result["report_file"] is not None
        assert Path(result["report_file"]).exists()


class TestCollectionWorkflowHelpers:
    """测试 CollectionWorkflow 辅助方法."""

    @pytest.fixture
    def mock_workflow(self, tmp_path):
        """创建模拟工作流."""
        with patch("src.workflows.collection_workflow.CollectionController"):
            from src.workflows.collection_workflow import CollectionWorkflow

            return CollectionWorkflow(output_dir=str(tmp_path))

    @pytest.fixture
    def sample_results(self):
        """创建示例结果列表."""
        from src.workflows.collection_workflow import CollectionResult

        product1 = MagicMock()
        product1.owner = "测试员"
        product1.product_name = "产品1"
        product1.model_number = "A001"
        product1.color_spec = "白色"
        product1.collect_count = 3

        product2 = MagicMock()
        product2.owner = "测试员"
        product2.product_name = "产品2"
        product2.model_number = "A002"
        product2.color_spec = "黑色"
        product2.collect_count = 2

        result1 = CollectionResult(
            product=product1,
            collected_links=[
                {"url": "https://temu.com/1", "title": "商品1", "price": "10.00"},
                {"url": "https://temu.com/2", "title": "商品2", "price": "15.00"},
            ],
            success=True,
        )

        result2 = CollectionResult(
            product=product2,
            collected_links=[],
            success=False,
            error="搜索失败",
        )

        return [result1, result2]

    def test_generate_summary(self, mock_workflow, sample_results) -> None:
        """测试生成汇总统计."""
        summary = mock_workflow._generate_summary(sample_results)

        assert summary["total_products"] == 2
        assert summary["success"] == 1
        assert summary["failed"] == 1
        assert summary["success_rate"] == 50.0
        assert summary["total_links"] == 2
        assert summary["average_links_per_product"] == 2.0

    def test_generate_summary_all_success(self, mock_workflow) -> None:
        """测试全部成功的汇总."""
        from src.workflows.collection_workflow import CollectionResult

        product = MagicMock()
        product.owner = "测试员"
        product.product_name = "产品"
        product.model_number = "A001"
        product.color_spec = "白色"
        product.collect_count = 3

        results = [
            CollectionResult(
                product=product,
                collected_links=[{"url": "https://temu.com/1", "title": "商品"}],
                success=True,
            )
            for _ in range(5)
        ]

        summary = mock_workflow._generate_summary(results)

        assert summary["success"] == 5
        assert summary["failed"] == 0
        assert summary["success_rate"] == 100.0

    def test_generate_summary_all_failed(self, mock_workflow) -> None:
        """测试全部失败的汇总."""
        from src.workflows.collection_workflow import CollectionResult

        product = MagicMock()
        product.owner = "测试员"
        product.product_name = "产品"
        product.model_number = "A001"
        product.color_spec = "白色"
        product.collect_count = 3

        results = [
            CollectionResult(
                product=product,
                collected_links=[],
                success=False,
                error="失败",
            )
            for _ in range(3)
        ]

        summary = mock_workflow._generate_summary(results)

        assert summary["success"] == 0
        assert summary["failed"] == 3
        assert summary["success_rate"] == 0.0
        assert summary["average_links_per_product"] == 0

    def test_generate_summary_empty(self, mock_workflow) -> None:
        """测试空结果的汇总."""
        summary = mock_workflow._generate_summary([])

        assert summary["total_products"] == 0
        assert summary["success_rate"] == 0

    def test_save_report(self, mock_workflow, sample_results, tmp_path) -> None:
        """测试保存报告."""
        import json

        summary = {"total_products": 2, "success": 1, "failed": 1}

        report_file = mock_workflow.save_report(sample_results, summary)

        assert Path(report_file).exists()

        with open(report_file, encoding="utf-8") as f:
            report_data = json.load(f)

        assert "timestamp" in report_data
        assert report_data["summary"] == summary
        assert len(report_data["results"]) == 2


class TestCollectionWorkflowExport:
    """测试导出功能."""

    @pytest.fixture
    def mock_workflow(self, tmp_path):
        """创建模拟工作流."""
        with patch("src.workflows.collection_workflow.CollectionController"):
            from src.workflows.collection_workflow import CollectionWorkflow

            return CollectionWorkflow(output_dir=str(tmp_path))

    @pytest.fixture
    def sample_results(self):
        """创建示例结果列表."""
        from src.workflows.collection_workflow import CollectionResult

        product1 = MagicMock()
        product1.owner = "测试员"
        product1.product_name = "产品1"
        product1.model_number = "A001"
        product1.color_spec = "白色"
        product1.collect_count = 3

        return [
            CollectionResult(
                product=product1,
                collected_links=[
                    {"url": "https://temu.com/1", "title": "商品1", "price": "10.00"},
                    {"url": "https://temu.com/2", "title": "商品2", "price": "15.00"},
                ],
                success=True,
            )
        ]

    def test_export_links_default_file(
        self, mock_workflow, sample_results, tmp_path
    ) -> None:
        """测试默认文件路径导出."""
        output_file = mock_workflow.export_links_for_miaoshou(sample_results)

        assert Path(output_file).exists()
        assert "miaoshou_links" in output_file

        with open(output_file, encoding="utf-8") as f:
            content = f.read()

        assert "产品1" in content
        assert "https://temu.com/1" in content
        assert "https://temu.com/2" in content

    def test_export_links_custom_file(
        self, mock_workflow, sample_results, tmp_path
    ) -> None:
        """测试自定义文件路径导出."""
        custom_file = str(tmp_path / "custom_export.txt")
        output_file = mock_workflow.export_links_for_miaoshou(
            sample_results, output_file=custom_file
        )

        assert output_file == custom_file
        assert Path(custom_file).exists()

    def test_export_links_skip_failed(self, mock_workflow, tmp_path) -> None:
        """测试跳过失败的结果."""
        from src.workflows.collection_workflow import CollectionResult

        product = MagicMock()
        product.owner = "测试员"
        product.product_name = "失败产品"
        product.model_number = "FAIL"
        product.color_spec = "白色"
        product.collect_count = 3

        results = [
            CollectionResult(
                product=product,
                collected_links=[],
                success=False,
                error="搜索失败",
            )
        ]

        output_file = mock_workflow.export_links_for_miaoshou(results)

        with open(output_file, encoding="utf-8") as f:
            content = f.read()

        # 失败的产品不应该出现在导出文件中（除了注释部分）
        assert "失败产品" not in content or "## 产品:" not in content.split("失败产品")[0]


class TestCollectionWorkflowIntegration:
    """集成测试."""

    @pytest.mark.asyncio
    async def test_full_workflow_mock(self, tmp_path) -> None:
        """测试完整工作流（模拟）."""
        with patch("src.workflows.collection_workflow.CollectionController"):
            from src.workflows.collection_workflow import CollectionWorkflow

            workflow = CollectionWorkflow(output_dir=str(tmp_path))

            # Mock all components
            product = MagicMock()
            product.owner = "测试员"
            product.product_name = "测试产品"
            product.model_number = "TEST001"
            product.color_spec = "测试"
            product.collect_count = 2

            workflow.table_reader.read_excel = MagicMock(return_value=[product])
            workflow.collection_ctrl.visit_store = AsyncMock(return_value=True)
            workflow.collection_ctrl.search_products = AsyncMock(return_value=True)
            workflow.collection_ctrl.collect_links = AsyncMock(
                return_value=[
                    {"url": "https://temu.com/1", "title": "商品1", "price": "10.00"}
                ]
            )

            page = MagicMock()

            result = await workflow.execute(
                page,
                selection_table_path="test.xlsx",
                save_report=True,
            )

            assert result["summary"]["success"] == 1
            assert result["summary"]["total_links"] == 1
            assert result["report_file"] is not None


class TestModuleExports:
    """测试模块导出."""

    def test_collection_result_import(self) -> None:
        """测试 CollectionResult 可导入."""
        from src.workflows.collection_workflow import CollectionResult

        assert CollectionResult is not None

    def test_collection_workflow_import(self) -> None:
        """测试 CollectionWorkflow 可导入."""
        from src.workflows.collection_workflow import CollectionWorkflow

        assert CollectionWorkflow is not None
