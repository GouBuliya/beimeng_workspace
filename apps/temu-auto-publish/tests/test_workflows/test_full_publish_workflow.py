"""
@PURPOSE: 测试 workflows/full_publish_workflow.py 完整发布工作流
@OUTLINE:
  - class TestFullPublishWorkflow: 完整发布工作流测试
  - 测试采集,发布,错误处理等场景
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.workflows.full_publish_workflow
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFullPublishWorkflow:
    """测试 FullPublishWorkflow 类."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        return page

    @pytest.fixture
    def sample_products(self):
        """创建示例产品数据."""
        return [
            {
                "keyword": "药箱收纳盒",
                "collect_count": 5,
                "cost": 10.0,
                "stock": 100,
            },
            {
                "keyword": "手机支架",
                "collect_count": 3,
                "cost": 5.0,
                "stock": 200,
            },
        ]

    def test_workflow_initialization(self) -> None:
        """测试工作流初始化."""
        with (
            patch("src.workflows.full_publish_workflow.CollectionController") as mock_collection,
            patch("src.workflows.full_publish_workflow.CompletePublishWorkflow") as mock_publish,
        ):
            from src.workflows.full_publish_workflow import FullPublishWorkflow

            workflow = FullPublishWorkflow()

            assert workflow.collection_ctrl is not None
            assert workflow.publish_workflow is not None
            mock_collection.assert_called_once()
            mock_publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_full_workflow_success(self, mock_page, sample_products) -> None:
        """测试完整工作流成功执行."""
        with (
            patch(
                "src.workflows.full_publish_workflow.CollectionController"
            ) as mock_collection_cls,
            patch(
                "src.workflows.full_publish_workflow.CompletePublishWorkflow"
            ) as mock_publish_cls,
        ):
            # 设置 Mock
            mock_collection = MagicMock()
            mock_collection.visit_store = AsyncMock(return_value=True)
            mock_collection.search_and_collect = AsyncMock(
                return_value=[
                    {"url": "https://example.com/1", "title": "商品1"},
                    {"url": "https://example.com/2", "title": "商品2"},
                ]
            )
            mock_collection_cls.return_value = mock_collection

            mock_publish = MagicMock()
            mock_publish.execute = AsyncMock(
                return_value={"status": "success", "published_count": 2}
            )
            mock_publish_cls.return_value = mock_publish

            from src.workflows.full_publish_workflow import FullPublishWorkflow

            workflow = FullPublishWorkflow()

            result = await workflow.execute(
                mock_page,
                sample_products,
                enable_batch_edit=True,
                enable_publish=False,
            )

            assert result["status"] == "success"
            assert result["total_products"] == 2
            assert len(result["collection_results"]) == 2

    @pytest.mark.asyncio
    async def test_execute_visit_store_failure(self, mock_page, sample_products) -> None:
        """测试访问店铺失败时抛出异常."""
        with (
            patch(
                "src.workflows.full_publish_workflow.CollectionController"
            ) as mock_collection_cls,
            patch("src.workflows.full_publish_workflow.CompletePublishWorkflow"),
        ):
            mock_collection = MagicMock()
            mock_collection.visit_store = AsyncMock(return_value=False)
            mock_collection_cls.return_value = mock_collection

            from src.workflows.full_publish_workflow import FullPublishWorkflow

            workflow = FullPublishWorkflow()

            with pytest.raises(Exception) as exc_info:
                await workflow.execute(mock_page, sample_products)

            assert "访问店铺失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_collection_failure_skips_product(
        self, mock_page, sample_products
    ) -> None:
        """测试采集失败时跳过该产品."""
        with (
            patch(
                "src.workflows.full_publish_workflow.CollectionController"
            ) as mock_collection_cls,
            patch(
                "src.workflows.full_publish_workflow.CompletePublishWorkflow"
            ) as mock_publish_cls,
        ):
            mock_collection = MagicMock()
            mock_collection.visit_store = AsyncMock(return_value=True)
            # 第一个产品采集失败,第二个成功
            mock_collection.search_and_collect = AsyncMock(
                side_effect=[
                    [],  # 第一个产品采集失败
                    [{"url": "https://example.com/1", "title": "商品1"}],  # 第二个成功
                ]
            )
            mock_collection_cls.return_value = mock_collection

            mock_publish = MagicMock()
            mock_publish.execute = AsyncMock(return_value={"status": "success"})
            mock_publish_cls.return_value = mock_publish

            from src.workflows.full_publish_workflow import FullPublishWorkflow

            workflow = FullPublishWorkflow()

            result = await workflow.execute(mock_page, sample_products)

            # 只有一个产品采集成功
            assert result["collected_count"] == 1
            assert len(result["collection_results"]) == 1

    @pytest.mark.asyncio
    async def test_execute_with_shop_name(self, mock_page, sample_products) -> None:
        """测试带店铺名称的执行."""
        with (
            patch(
                "src.workflows.full_publish_workflow.CollectionController"
            ) as mock_collection_cls,
            patch(
                "src.workflows.full_publish_workflow.CompletePublishWorkflow"
            ) as mock_publish_cls,
        ):
            mock_collection = MagicMock()
            mock_collection.visit_store = AsyncMock(return_value=True)
            mock_collection.search_and_collect = AsyncMock(
                return_value=[{"url": "https://example.com/1", "title": "商品1"}]
            )
            mock_collection_cls.return_value = mock_collection

            mock_publish = MagicMock()
            mock_publish.execute = AsyncMock(return_value={"status": "success"})
            mock_publish_cls.return_value = mock_publish

            from src.workflows.full_publish_workflow import FullPublishWorkflow

            workflow = FullPublishWorkflow()

            await workflow.execute(
                mock_page,
                sample_products,
                enable_publish=True,
                shop_name="测试店铺",
            )

            # 验证店铺名称传递给发布工作流
            mock_publish.execute.assert_called_once()
            call_args = mock_publish.execute.call_args
            assert call_args.kwargs["shop_name"] == "测试店铺"

    @pytest.mark.asyncio
    async def test_execute_exception_handling(self, mock_page, sample_products) -> None:
        """测试异常处理."""
        with (
            patch(
                "src.workflows.full_publish_workflow.CollectionController"
            ) as mock_collection_cls,
            patch("src.workflows.full_publish_workflow.CompletePublishWorkflow"),
        ):
            mock_collection = MagicMock()
            mock_collection.visit_store = AsyncMock(side_effect=Exception("网络错误"))
            mock_collection_cls.return_value = mock_collection

            from src.workflows.full_publish_workflow import FullPublishWorkflow

            workflow = FullPublishWorkflow()

            with pytest.raises(Exception) as exc_info:
                await workflow.execute(mock_page, sample_products)

            assert "网络错误" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_collected_links_added_to_product(self, mock_page, sample_products) -> None:
        """测试采集链接添加到产品数据中."""
        with (
            patch(
                "src.workflows.full_publish_workflow.CollectionController"
            ) as mock_collection_cls,
            patch(
                "src.workflows.full_publish_workflow.CompletePublishWorkflow"
            ) as mock_publish_cls,
        ):
            collected_links = [
                {"url": "https://example.com/1", "title": "商品1"},
                {"url": "https://example.com/2", "title": "商品2"},
            ]

            mock_collection = MagicMock()
            mock_collection.visit_store = AsyncMock(return_value=True)
            mock_collection.search_and_collect = AsyncMock(return_value=collected_links)
            mock_collection_cls.return_value = mock_collection

            mock_publish = MagicMock()
            mock_publish.execute = AsyncMock(return_value={"status": "success"})
            mock_publish_cls.return_value = mock_publish

            from src.workflows.full_publish_workflow import FullPublishWorkflow

            workflow = FullPublishWorkflow()

            # 使用单个产品测试
            single_product = [sample_products[0]]
            await workflow.execute(mock_page, single_product)

            # 验证链接被添加到产品数据中
            assert "collected_links" in single_product[0]
            assert len(single_product[0]["collected_links"]) == 2
            assert "collected_info" in single_product[0]


class TestFullPublishWorkflowIntegration:
    """完整发布工作流集成测试."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_workflow_execution(self) -> None:
        """集成测试 - 需要真实浏览器环境."""
        pytest.skip("需要真实浏览器环境")
