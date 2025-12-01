"""
@PURPOSE: 数据处理模块 Mock 类
@OUTLINE:
  - MockProductSelectionRow: 模拟产品选品行
  - MockSelectionTableReader: 模拟选品表读取器
  - MockProductDataReader: 模拟产品数据读取器
  - MockPriceCalculator: 模拟价格计算器
  - MockDataConverter: 模拟数据转换器
  - MockTitleGenerator: 模拟标题生成器
@DEPENDENCIES:
  - 外部: unittest.mock
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MockProductSelectionRow:
    """模拟产品选品行数据"""

    owner: str = "测试负责人"
    product_name: str = "测试产品"
    model_number: str = "A0001"
    color_spec: str | None = "白色"
    collect_count: int = 5
    cost_price: float | None = 15.0
    spec_unit: str | None = None
    spec_options: list[str] | None = None
    variant_costs: list[float] | None = None
    image_files: list[str] | None = None
    size_chart_image_url: str = "https://example.com/size-chart.jpg"
    product_video_url: str | None = None
    sku_image_urls: list[str] = field(default_factory=list)


class MockSelectionTableReader:
    """模拟 SelectionTableReader"""

    def __init__(self, products: list[MockProductSelectionRow] | None = None):
        self._products = products or self._default_products()
        self.read_count = 0

    def _default_products(self) -> list[MockProductSelectionRow]:
        """生成默认测试产品"""
        return [
            MockProductSelectionRow(
                owner="张三",
                product_name="药箱收纳盒",
                model_number=f"A{i:04d}",
                cost_price=10.0 + i * 2,
                collect_count=5,
            )
            for i in range(1, 6)
        ]

    def read_excel(
        self, file_path: str, sheet_name: int = 0, skip_rows: int = 0
    ) -> list[MockProductSelectionRow]:
        """模拟读取Excel"""
        self.read_count += 1
        return self._products

    def validate_row(self, row: dict) -> tuple[bool, str | None]:
        """模拟验证行数据"""
        if not row.get("product_name"):
            return False, "缺少产品名称"
        if not row.get("model_number"):
            return False, "缺少型号编号"
        return True, None

    def create_sample_excel(self, output_path: str, num_samples: int = 3) -> None:
        """模拟创建示例Excel"""
        pass


class MockProductDataReader:
    """模拟 ProductDataReader"""

    def __init__(self, products: list[dict] | None = None):
        self._products = products or self._default_products()

    def _default_products(self) -> list[dict]:
        """生成默认测试产品"""
        return [
            {
                "keyword": f"测试产品{i}",
                "model_number": f"A{i:04d}",
                "cost": 10.0 + i * 5,
                "stock": 100,
            }
            for i in range(1, 6)
        ]

    def read(self, file_path: str) -> list[dict]:
        """模拟读取产品数据"""
        return self._products

    def validate(self, data: list[dict]) -> tuple[bool, list[str]]:
        """模拟验证数据"""
        errors = []
        for i, item in enumerate(data):
            if not item.get("keyword"):
                errors.append(f"第{i + 1}行缺少keyword")
            if not item.get("model_number"):
                errors.append(f"第{i + 1}行缺少model_number")
        return len(errors) == 0, errors


@dataclass
class MockPriceResult:
    """模拟价格计算结果"""

    cost_price: float
    suggested_price: float
    supply_price: float
    profit_rate: float = 0.75


class MockPriceCalculator:
    """模拟 PriceCalculator"""

    def __init__(self, multiplier: float = 10.0):
        self._multiplier = multiplier

    def calculate(self, cost_price: float) -> MockPriceResult:
        """模拟计算价格"""
        suggested = round(cost_price * self._multiplier, 2)
        supply = round(suggested * 0.75, 2)
        return MockPriceResult(
            cost_price=cost_price, suggested_price=suggested, supply_price=supply
        )

    @staticmethod
    def calculate_static(cost_price: float) -> MockPriceResult:
        """静态方法计算价格"""
        suggested = round(cost_price * 10, 2)
        supply = round(suggested * 0.75, 2)
        return MockPriceResult(
            cost_price=cost_price, suggested_price=suggested, supply_price=supply
        )


class MockDataConverter:
    """模拟 DataConverter"""

    def __init__(self):
        self.conversion_count = 0

    def convert_to_workflow_format(self, data: list[dict]) -> list[dict]:
        """模拟转换为工作流格式"""
        self.conversion_count += 1
        return [
            {
                "index": i,
                "keyword": item.get("keyword", ""),
                "model_number": item.get("model_number", ""),
                "cost_price": item.get("cost", 0),
                "stock": item.get("stock", 100),
            }
            for i, item in enumerate(data)
        ]

    def convert_from_selection_table(self, products: list[MockProductSelectionRow]) -> list[dict]:
        """模拟从选品表转换"""
        self.conversion_count += 1
        return [
            {
                "keyword": p.product_name,
                "model_number": p.model_number,
                "cost_price": p.cost_price,
                "owner": p.owner,
            }
            for p in products
        ]


class MockTitleGenerator:
    """模拟 TitleGenerator"""

    def __init__(self, prefix: str = ""):
        self._prefix = prefix
        self.generated_titles: list[str] = []

    def generate(self, keyword: str, model_number: str) -> str:
        """模拟生成标题"""
        title = f"{self._prefix}{keyword} {model_number}".strip()
        self.generated_titles.append(title)
        return title

    async def generate_async(self, keyword: str, model_number: str) -> str:
        """异步版本生成标题"""
        return self.generate(keyword, model_number)

    def generate_english_title(self, chinese_title: str) -> str:
        """模拟生成英文标题"""
        # 简单模拟:将中文标题转换为英文
        return f"English Title for {chinese_title}"


class MockExcelReader:
    """模拟 Excel 读取器"""

    def __init__(self, data: list[list[Any]] | None = None):
        self._data = data or [
            ["关键词", "型号", "成本", "库存"],
            ["药箱收纳盒", "A0001", 15.0, 100],
            ["厨房收纳架", "A0002", 25.0, 50],
        ]

    def read(self, file_path: str, sheet_name: int = 0) -> list[list[Any]]:
        """模拟读取Excel"""
        return self._data

    def read_as_dict(self, file_path: str, sheet_name: int = 0) -> list[dict]:
        """模拟读取Excel为字典列表"""
        if len(self._data) < 2:
            return []
        headers = self._data[0]
        return [dict(zip(headers, row, strict=False)) for row in self._data[1:]]


class MockMetricsCollector:
    """模拟 MetricsCollector"""

    def __init__(self):
        self.workflows: dict[str, dict] = {}
        self.metrics: list[dict] = []
        self.counters: dict[str, float] = {}
        self.gauges: dict[str, float] = {}

    def start_workflow(self, workflow_id: str | None = None) -> str:
        """模拟开始工作流"""
        wid = workflow_id or f"mock_workflow_{len(self.workflows)}"
        self.workflows[wid] = {"status": "running", "stages": {}}
        return wid

    def end_workflow(self, workflow_id: str, status: str = "success") -> None:
        """模拟结束工作流"""
        if workflow_id in self.workflows:
            self.workflows[workflow_id]["status"] = status

    def record_stage(
        self, workflow_id: str, stage_name: str, duration: float, success: bool = True
    ) -> None:
        """模拟记录阶段"""
        if workflow_id in self.workflows:
            self.workflows[workflow_id]["stages"][stage_name] = {
                "duration": duration,
                "success": success,
            }

    def record_metric(self, name: str, value: float, **labels) -> None:
        """模拟记录指标"""
        self.metrics.append({"name": name, "value": value, "labels": labels})

    def increment(self, name: str, value: float = 1.0) -> None:
        """模拟递增计数器"""
        self.counters[name] = self.counters.get(name, 0) + value

    def get_statistics(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            "total_workflows": len(self.workflows),
            "total_metrics": len(self.metrics),
            "counters": self.counters,
            "gauges": self.gauges,
        }
