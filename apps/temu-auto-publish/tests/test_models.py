"""
@PURPOSE: 测试 models 模块的数据模型（result.py 和 task.py）
@OUTLINE:
  - class TestBrowserResult: 浏览器操作结果基类测试
  - class TestSearchResult: 搜索结果测试
  - class TestEditResult: 编辑结果测试
  - class TestPublishResult: 发布结果测试
  - class TestProductInput: 产品输入数据测试
  - class TestTaskProduct: 任务产品数据测试
  - class TestTaskData: 任务数据测试
@DEPENDENCIES:
  - 外部: pytest, pydantic
  - 内部: src.models.result, src.models.task
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.result import (
    BrowserResult,
    EditResult,
    PublishResult,
    SearchResult,
)
from src.models.task import (
    ProductInput,
    TaskData,
    TaskProduct,
)


class TestBrowserResult:
    """测试 BrowserResult 基类."""

    def test_create_success_result(self) -> None:
        """测试创建成功状态的结果."""
        result = BrowserResult(
            task_id="task_001",
            operation="search",
            status="success",
            result={"found": 10},
            execution_time=1.5,
        )
        assert result.task_id == "task_001"
        assert result.operation == "search"
        assert result.status == "success"
        assert result.result == {"found": 10}
        assert result.execution_time == 1.5
        assert result.error_message is None

    def test_create_failed_result(self) -> None:
        """测试创建失败状态的结果."""
        result = BrowserResult(
            task_id="task_002",
            operation="edit",
            status="failed",
            error_message="Element not found",
            screenshot_path="/tmp/error.png",  # nosec B108 - 测试用临时路径
        )
        assert result.status == "failed"
        assert result.error_message == "Element not found"
        assert result.screenshot_path == "/tmp/error.png"  # nosec B108 - 测试断言

    def test_default_values(self) -> None:
        """测试默认值设置."""
        result = BrowserResult(
            task_id="task_003",
            operation="publish",
            status="pending",
        )
        assert result.result == {}
        assert result.execution_time == 0.0
        assert result.logs == []
        assert result.error_message is None
        assert result.screenshot_path is None
        # completed_at 应该是当前时间的 ISO 格式
        assert result.completed_at is not None

    def test_result_with_logs(self) -> None:
        """测试带日志的结果."""
        logs = ["Step 1 completed", "Step 2 completed", "Done"]
        result = BrowserResult(
            task_id="task_004",
            operation="search",
            status="success",
            logs=logs,
        )
        assert len(result.logs) == 3
        assert "Step 1 completed" in result.logs

    def test_result_serialization(self) -> None:
        """测试结果序列化为字典."""
        result = BrowserResult(
            task_id="task_005",
            operation="search",
            status="success",
        )
        data = result.model_dump()
        assert isinstance(data, dict)
        assert data["task_id"] == "task_005"
        assert data["operation"] == "search"

    def test_result_from_dict(self) -> None:
        """测试从字典创建结果."""
        data = {
            "task_id": "task_006",
            "operation": "edit",
            "status": "success",
            "result": {"edited": True},
        }
        result = BrowserResult.model_validate(data)
        assert result.task_id == "task_006"
        assert result.result == {"edited": True}


class TestSearchResult:
    """测试 SearchResult 搜索采集结果."""

    def test_create_search_result(self) -> None:
        """测试创建搜索结果."""
        result = SearchResult(
            product_id="P001",
            keyword="智能手表",
            count=5,
            status="success",
        )
        assert result.product_id == "P001"
        assert result.keyword == "智能手表"
        assert result.count == 5

    def test_search_result_with_links(self) -> None:
        """测试带链接的搜索结果."""
        links = [
            {"url": "https://example.com/1", "title": "商品1"},
            {"url": "https://example.com/2", "title": "商品2"},
        ]
        result = SearchResult(
            product_id="P002",
            keyword="手机壳",
            links=links,
            count=2,
        )
        assert len(result.links) == 2
        assert result.links[0]["url"] == "https://example.com/1"

    def test_default_values(self) -> None:
        """测试默认值."""
        result = SearchResult(product_id="P003", keyword="测试")
        assert result.links == []
        assert result.count == 0
        assert result.status == "pending"


class TestEditResult:
    """测试 EditResult 编辑结果."""

    def test_create_edit_result(self) -> None:
        """测试创建编辑结果."""
        result = EditResult(
            product_id="P001",
            claimed_ids=["ID001", "ID002"],
            images_confirmed=True,
            saved=True,
            status="success",
        )
        assert result.product_id == "P001"
        assert len(result.claimed_ids) == 2
        assert result.images_confirmed is True
        assert result.saved is True

    def test_edit_result_with_changes(self) -> None:
        """测试带修改记录的编辑结果."""
        changes = {
            "title": {"old": "旧标题", "new": "新标题"},
            "price": {"old": "100", "new": "150"},
        }
        result = EditResult(
            product_id="P002",
            changes=changes,
        )
        assert "title" in result.changes
        assert result.changes["title"]["new"] == "新标题"

    def test_edit_result_failed(self) -> None:
        """测试失败的编辑结果."""
        result = EditResult(
            product_id="P003",
            status="failed",
            error_message="保存超时",
        )
        assert result.status == "failed"
        assert result.error_message == "保存超时"


class TestPublishResult:
    """测试 PublishResult 发布结果."""

    def test_create_publish_result(self) -> None:
        """测试创建发布结果."""
        result = PublishResult(
            product_id="P001",
            total_published=5,
            success_count=4,
            failed_count=1,
            status="partial",
        )
        assert result.product_id == "P001"
        assert result.total_published == 5
        assert result.success_count == 4
        assert result.failed_count == 1

    def test_publish_result_with_items(self) -> None:
        """测试带商品列表的发布结果."""
        items = [
            {"id": "ITEM001", "status": "success"},
            {"id": "ITEM002", "status": "failed", "error": "库存不足"},
        ]
        result = PublishResult(
            product_id="P002",
            items=items,
            total_published=2,
        )
        assert len(result.items) == 2
        assert result.items[1]["error"] == "库存不足"

    def test_default_values(self) -> None:
        """测试默认值."""
        result = PublishResult(product_id="P003")
        assert result.items == []
        assert result.total_published == 0
        assert result.success_count == 0
        assert result.failed_count == 0
        assert result.status == "pending"


class TestProductInput:
    """测试 ProductInput 选品表数据模型."""

    def test_create_product_input(self) -> None:
        """测试创建产品输入."""
        product = ProductInput(
            name="智能手表运动防水",
            cost_price=150.00,
            category="电子产品/智能穿戴",
            keyword="智能手表",
        )
        assert product.name == "智能手表运动防水"
        assert product.cost_price == 150.0
        assert product.category == "电子产品/智能穿戴"

    def test_price_rounding(self) -> None:
        """测试价格自动四舍五入到2位小数."""
        product = ProductInput(
            name="测试商品",
            cost_price=99.999,
            category="测试",
            keyword="测试",
        )
        assert product.cost_price == 100.0

    def test_invalid_price(self) -> None:
        """测试无效价格验证."""
        with pytest.raises(ValidationError):
            ProductInput(
                name="测试商品",
                cost_price=-10,  # 价格必须大于0
                category="测试",
                keyword="测试",
            )

    def test_empty_name(self) -> None:
        """测试空名称验证."""
        with pytest.raises(ValidationError):
            ProductInput(
                name="",  # 名称不能为空
                cost_price=100,
                category="测试",
                keyword="测试",
            )

    def test_default_notes(self) -> None:
        """测试备注默认值."""
        product = ProductInput(
            name="测试商品",
            cost_price=100,
            category="测试",
            keyword="测试",
        )
        assert product.notes == ""


class TestTaskProduct:
    """测试 TaskProduct 任务产品数据模型."""

    def test_create_task_product(self) -> None:
        """测试创建任务产品."""
        product = TaskProduct(
            id="P001",
            keyword="智能手表",
            original_name="智能手表运动防水",
            ai_title="【热销】智能手表运动防水蓝牙通话",
            cost_price=150.00,
            suggested_price=1125.00,  # 150 * 7.5
            supply_price=1500.00,  # 150 * 10
            category="电子产品/智能穿戴",
        )
        assert product.id == "P001"
        assert product.suggested_price == 1125.0
        assert product.supply_price == 1500.0

    def test_invalid_id_format(self) -> None:
        """测试无效ID格式验证."""
        with pytest.raises(ValidationError):
            TaskProduct(
                id="001",  # 必须是 P001 格式
                keyword="测试",
                original_name="测试",
                ai_title="测试",
                cost_price=100,
                suggested_price=750,
                supply_price=1000,
                category="测试",
            )

    def test_search_count_bounds(self) -> None:
        """测试采集数量边界."""
        # 有效范围 1-10
        product = TaskProduct(
            id="P001",
            keyword="测试",
            original_name="测试",
            ai_title="测试",
            cost_price=100,
            suggested_price=750,
            supply_price=1000,
            category="测试",
            search_count=10,
        )
        assert product.search_count == 10

        # 超出范围应报错
        with pytest.raises(ValidationError):
            TaskProduct(
                id="P001",
                keyword="测试",
                original_name="测试",
                ai_title="测试",
                cost_price=100,
                suggested_price=750,
                supply_price=1000,
                category="测试",
                search_count=15,  # 超出最大值10
            )

    def test_default_values(self) -> None:
        """测试默认值."""
        product = TaskProduct(
            id="P001",
            keyword="测试",
            original_name="测试",
            ai_title="测试",
            cost_price=100,
            suggested_price=750,
            supply_price=1000,
            category="测试",
        )
        assert product.status == "pending"
        assert product.collected_links == []
        assert product.claimed_ids == []
        assert product.edit_result is None
        assert product.publish_result is None
        assert product.search_count == 5


class TestTaskData:
    """测试 TaskData 任务数据模型."""

    @pytest.fixture
    def sample_products(self) -> list[TaskProduct]:
        """创建示例产品列表."""
        return [
            TaskProduct(
                id="P001",
                keyword="手表",
                original_name="智能手表",
                ai_title="智能手表 AI",
                cost_price=100,
                suggested_price=750,
                supply_price=1000,
                category="电子",
                status="pending",
            ),
            TaskProduct(
                id="P002",
                keyword="手机壳",
                original_name="手机壳",
                ai_title="手机壳 AI",
                cost_price=50,
                suggested_price=375,
                supply_price=500,
                category="配件",
                status="success",
            ),
            TaskProduct(
                id="P003",
                keyword="耳机",
                original_name="蓝牙耳机",
                ai_title="蓝牙耳机 AI",
                cost_price=80,
                suggested_price=600,
                supply_price=800,
                category="电子",
                status="failed",
            ),
        ]

    def test_create_task_data(self, sample_products: list[TaskProduct]) -> None:
        """测试创建任务数据."""
        task = TaskData(
            task_id="20251201_120000",
            created_at=datetime.now().isoformat(),
            products=sample_products,
        )
        assert task.task_id == "20251201_120000"
        assert len(task.products) == 3

    def test_update_statistics(self, sample_products: list[TaskProduct]) -> None:
        """测试统计信息更新."""
        task = TaskData(
            task_id="20251201_120000",
            created_at=datetime.now().isoformat(),
            products=sample_products,
        )
        task.update_statistics()

        assert task.statistics["total"] == 3
        assert task.statistics["pending"] == 1
        assert task.statistics["success"] == 1
        assert task.statistics["failed"] == 1
        assert task.statistics["processing"] == 0

    def test_empty_task(self) -> None:
        """测试空任务."""
        task = TaskData(
            task_id="20251201_120000",
            created_at=datetime.now().isoformat(),
        )
        assert task.products == []
        task.update_statistics()
        assert task.statistics["total"] == 0

    def test_default_status(self) -> None:
        """测试默认状态."""
        task = TaskData(
            task_id="20251201_120000",
            created_at=datetime.now().isoformat(),
        )
        assert task.status == "pending"

    def test_serialization(self, sample_products: list[TaskProduct]) -> None:
        """测试序列化."""
        task = TaskData(
            task_id="20251201_120000",
            created_at="2025-12-01T12:00:00",
            products=sample_products,
        )
        data = task.model_dump()

        assert isinstance(data, dict)
        assert data["task_id"] == "20251201_120000"
        assert len(data["products"]) == 3
        assert isinstance(data["products"][0], dict)

    def test_from_dict(self) -> None:
        """测试从字典创建."""
        data = {
            "task_id": "20251201_130000",
            "created_at": "2025-12-01T13:00:00",
            "status": "processing",
            "products": [
                {
                    "id": "P001",
                    "keyword": "测试",
                    "original_name": "测试商品",
                    "ai_title": "AI 标题",
                    "cost_price": 100,
                    "suggested_price": 750,
                    "supply_price": 1000,
                    "category": "测试类目",
                }
            ],
        }
        task = TaskData.model_validate(data)

        assert task.task_id == "20251201_130000"
        assert task.status == "processing"
        assert len(task.products) == 1
        assert task.products[0].id == "P001"
