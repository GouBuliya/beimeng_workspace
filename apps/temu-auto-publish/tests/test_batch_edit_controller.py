"""
@PURPOSE: BatchEditController 批量编辑控制器测试
@OUTLINE:
  - TestPriceCalculator: 价格计算器测试(纯逻辑)
  - TestPriceResult: 价格结果模型测试(纯逻辑)
  - TestRandomDataGenerator: 随机数据生成器测试(纯逻辑)
  - TestBatchEditControllerInit: 控制器初始化测试
  - TestBatchEditControllerSteps: 批量编辑步骤测试(使用Mock)
@DEPENDENCIES:
  - 内部: data_processor.price_calculator, data_processor.random_generator
  - 内部: browser.batch_edit.controller
  - 外部: pytest, pytest-asyncio
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.data_processor.price_calculator import PriceCalculator, PriceResult
from src.data_processor.random_generator import RandomDataGenerator


# ============================================================
# PriceResult 模型测试
# ============================================================
class TestPriceResult:
    """价格结果模型测试"""

    def test_calculate_default_multipliers(self):
        """测试默认倍率计算"""
        result = PriceResult.calculate(150.0)

        assert result.cost_price == 150.0
        assert result.suggested_price == 1500.0  # 150 x 10
        assert result.supply_price == 1125.0  # 150 x 7.5
        assert result.real_supply_price == 375.0  # 150 x 2.5
        assert result.suggested_multiplier == 10.0
        assert result.supply_multiplier == 7.5

    def test_calculate_custom_multipliers(self):
        """测试自定义倍率计算"""
        result = PriceResult.calculate(100.0, suggested_multiplier=8.0, supply_multiplier=6.0)

        assert result.cost_price == 100.0
        assert result.suggested_price == 800.0  # 100 x 8
        assert result.supply_price == 600.0  # 100 x 6
        assert result.suggested_multiplier == 8.0
        assert result.supply_multiplier == 6.0

    def test_calculate_zero_cost(self):
        """测试零成本计算"""
        result = PriceResult.calculate(0.0)

        assert result.cost_price == 0.0
        assert result.suggested_price == 0.0
        assert result.supply_price == 0.0

    def test_calculate_decimal_cost(self):
        """测试小数成本计算"""
        result = PriceResult.calculate(99.99)

        assert result.cost_price == 99.99
        assert result.suggested_price == 999.9  # 99.99 x 10
        assert result.supply_price == 749.92  # 99.99 x 7.5 = 749.925, rounded to 749.92

    def test_calculate_large_cost(self):
        """测试大金额成本计算"""
        result = PriceResult.calculate(10000.0)

        assert result.suggested_price == 100000.0
        assert result.supply_price == 75000.0


# ============================================================
# PriceCalculator 测试
# ============================================================
class TestPriceCalculator:
    """价格计算器测试"""

    def test_init_default(self):
        """测试默认初始化"""
        calc = PriceCalculator()

        assert calc.suggested_multiplier == 10.0
        assert calc.supply_multiplier == 7.5

    def test_init_custom_multipliers(self):
        """测试自定义倍率初始化"""
        calc = PriceCalculator(suggested_multiplier=12.0, supply_multiplier=8.0)

        assert calc.suggested_multiplier == 12.0
        assert calc.supply_multiplier == 8.0

    def test_calculate_suggested_price(self):
        """测试建议售价计算"""
        calc = PriceCalculator()

        assert calc.calculate_suggested_price(100) == 1000.0
        assert calc.calculate_suggested_price(150) == 1500.0
        assert calc.calculate_suggested_price(200) == 2000.0

    def test_calculate_supply_price(self):
        """测试供货价计算"""
        calc = PriceCalculator()

        assert calc.calculate_supply_price(100) == 750.0
        assert calc.calculate_supply_price(150) == 1125.0
        assert calc.calculate_supply_price(200) == 1500.0

    def test_calculate_real_supply_price(self):
        """测试真实供货价计算"""
        calc = PriceCalculator()

        assert calc.calculate_real_supply_price(100) == 250.0
        assert calc.calculate_real_supply_price(150) == 375.0
        assert calc.calculate_real_supply_price(200) == 500.0

    def test_calculate_supply_price_for_publish(self):
        """测试发布供货价计算"""
        calc = PriceCalculator()

        # 应与 calculate_supply_price 相同
        assert calc.calculate_supply_price_for_publish(150) == calc.calculate_supply_price(150)

    def test_calculate_batch(self):
        """测试批量价格计算"""
        calc = PriceCalculator()
        costs = [100, 150, 200]

        results = calc.calculate_batch(costs)

        assert len(results) == 3
        assert results[0].cost_price == 100
        assert results[1].cost_price == 150
        assert results[2].cost_price == 200
        assert results[0].suggested_price == 1000.0
        assert results[1].suggested_price == 1500.0
        assert results[2].suggested_price == 2000.0

    def test_calculate_batch_empty(self):
        """测试空列表批量计算"""
        calc = PriceCalculator()

        results = calc.calculate_batch([])

        assert results == []

    def test_get_price_breakdown(self):
        """测试价格明细"""
        calc = PriceCalculator()

        breakdown = calc.get_price_breakdown(150.0)

        assert "成本价" in breakdown
        assert breakdown["成本价"] == 150.0
        assert "建议售价(SOP步骤7.14)" in breakdown
        assert breakdown["建议售价(SOP步骤7.14)"] == 1500.0
        assert "妙手供货价(SOP步骤9)" in breakdown
        assert breakdown["妙手供货价(SOP步骤9)"] == 1125.0

    def test_calculate_with_rounding(self):
        """测试价格四舍五入"""
        calc = PriceCalculator()

        # 测试会产生多位小数的情况
        result = calc.calculate_suggested_price(33.33)

        assert result == 333.3  # 33.33 x 10, rounded to 2 decimal places


# ============================================================
# RandomDataGenerator 测试
# ============================================================
class TestRandomDataGenerator:
    """随机数据生成器测试"""

    def test_init_default(self):
        """测试默认初始化"""
        gen = RandomDataGenerator()

        assert gen.weight_min == 5000
        assert gen.weight_max == 9999
        assert gen.dimension_min == 50
        assert gen.dimension_max == 99

    def test_init_custom_ranges(self):
        """测试自定义范围初始化"""
        gen = RandomDataGenerator(
            weight_min=1000,
            weight_max=2000,
            dimension_min=10,
            dimension_max=50,
        )

        assert gen.weight_min == 1000
        assert gen.weight_max == 2000
        assert gen.dimension_min == 10
        assert gen.dimension_max == 50

    def test_init_with_seed(self):
        """测试带种子初始化(可重现)"""
        gen1 = RandomDataGenerator(seed=42)
        gen2 = RandomDataGenerator(seed=42)

        # 相同种子应产生相同结果
        weight1 = gen1.generate_weight()
        weight2 = gen2.generate_weight()

        assert weight1 == weight2

    def test_generate_weight_range(self):
        """测试重量生成范围"""
        gen = RandomDataGenerator(seed=123)

        for _ in range(100):
            weight = gen.generate_weight()
            assert 5000 <= weight <= 9999

    def test_generate_weight_kg(self):
        """测试重量千克转换"""
        gen = RandomDataGenerator(seed=456)

        for _ in range(10):
            weight_kg = gen.generate_weight_kg()
            assert 5.0 <= weight_kg <= 10.0

    def test_generate_dimensions_range(self):
        """测试尺寸生成范围"""
        gen = RandomDataGenerator(seed=789)

        for _ in range(100):
            length, width, height = gen.generate_dimensions()
            assert 50 <= length <= 99
            assert 50 <= width <= 99
            assert 50 <= height <= 99

    def test_generate_dimensions_order(self):
        """测试尺寸顺序: 长 > 宽 > 高"""
        gen = RandomDataGenerator(seed=101)

        for _ in range(100):
            length, width, height = gen.generate_dimensions()
            assert length > width > height

    def test_generate_packaging_dimensions(self):
        """测试外包装尺寸生成"""
        gen = RandomDataGenerator(seed=202)

        length, width, height = gen.generate_packaging_dimensions()

        # 外包装尺寸应该满足长>宽>高
        assert length > width > height
        # 外包装通常比商品大5-10cm
        assert length >= 55

    def test_generate_batch_data(self):
        """测试批量数据生成"""
        gen = RandomDataGenerator(seed=303)

        data_list = gen.generate_batch_data(count=20)

        assert len(data_list) == 20
        for i, data in enumerate(data_list):
            assert data["index"] == i + 1
            assert "weight" in data
            assert "weight_kg" in data
            assert "dimensions" in data
            assert "dimensions_tuple" in data
            assert 5000 <= data["weight"] <= 9999
            assert data["dimensions"]["length"] > data["dimensions"]["width"]
            assert data["dimensions"]["width"] > data["dimensions"]["height"]

    def test_generate_batch_data_default_count(self):
        """测试批量数据默认数量"""
        gen = RandomDataGenerator(seed=404)

        data_list = gen.generate_batch_data()

        assert len(data_list) == 20  # 默认 SOP 规定的 20 条

    def test_validate_dimensions_valid(self):
        """测试有效尺寸验证"""
        gen = RandomDataGenerator()

        assert gen.validate_dimensions(80, 60, 50) is True
        assert gen.validate_dimensions(99, 70, 51) is True

    def test_validate_dimensions_invalid_order(self):
        """测试无效顺序验证"""
        gen = RandomDataGenerator()

        # 长 < 宽
        assert gen.validate_dimensions(50, 60, 40) is False
        # 宽 < 高
        assert gen.validate_dimensions(80, 50, 60) is False
        # 相等值
        assert gen.validate_dimensions(70, 70, 70) is False

    def test_validate_dimensions_out_of_range(self):
        """测试超出范围验证"""
        gen = RandomDataGenerator()

        # 超出最大值
        assert gen.validate_dimensions(100, 80, 60) is False
        # 低于最小值
        assert gen.validate_dimensions(80, 60, 40) is False


# ============================================================
# BatchEditController 初始化测试
# ============================================================
class TestBatchEditControllerInit:
    """BatchEditController 初始化测试"""

    @pytest.fixture
    def temp_selector_file(self, tmp_path):
        """创建临时选择器配置文件"""
        selector_config = {
            "smart_locator_config": {
                "timeout_per_selector": 3000,
                "retry_count": 2,
                "wait_after_action_ms": 100,
            },
            "batch_edit": {
                "step_02_english_title": {
                    "enabled": True,
                    "input": "input.english-title",
                },
                "step_09_weight": {
                    "enabled": True,
                    "input": ["input.weight", "input[name='weight']"],
                },
                "step_10_dimensions": {
                    "enabled": True,
                    "length_input": "input.length",
                    "width_input": "input.width",
                    "height_input": "input.height",
                },
                "step_14_suggested_price": {
                    "enabled": True,
                    "input": "input.price",
                },
                "navigation": {
                    "preview_button": "button:has-text('预览')",
                    "save_button": "button:has-text('保存')",
                },
            },
        }
        selector_file = tmp_path / "test_selectors.json"
        selector_file.write_text(json.dumps(selector_config))
        return str(selector_file)

    def test_init_default(self, temp_selector_file):
        """测试默认初始化"""
        from src.browser.batch_edit.controller import BatchEditController

        with patch.object(BatchEditController, "_load_selectors", return_value={"batch_edit": {}}):
            controller = BatchEditController(selector_path=temp_selector_file)

            assert controller.BATCH_SIZE == 20
            assert controller.price_calculator is not None
            assert controller.random_generator is not None

    def test_init_with_options(self, temp_selector_file):
        """测试带选项初始化"""
        from src.browser.batch_edit.controller import BatchEditController

        with patch.object(BatchEditController, "_load_selectors", return_value={"batch_edit": {}}):
            controller = BatchEditController(
                selector_path=temp_selector_file,
                outer_package_image="/path/to/image.jpg",
                manual_file_path="/path/to/manual.pdf",
                collection_owner="test_owner",
            )

            assert controller.outer_package_image == "/path/to/image.jpg"
            assert controller.manual_file_path == "/path/to/manual.pdf"
            assert controller.collection_owner == "test_owner"

    def test_build_wait_strategy_default(self, temp_selector_file):
        """测试默认等待策略构建"""
        from src.browser.batch_edit.controller import BatchEditController

        with patch.object(BatchEditController, "_load_selectors", return_value={"batch_edit": {}}):
            controller = BatchEditController(selector_path=temp_selector_file)
            strategy = controller._build_wait_strategy(None)

            # 检查默认值
            assert strategy.wait_after_action_ms == 120
            assert strategy.dom_stable_checks == 3

    def test_build_wait_strategy_custom(self, temp_selector_file):
        """测试自定义等待策略构建"""
        from src.browser.batch_edit.controller import BatchEditController

        with patch.object(BatchEditController, "_load_selectors", return_value={"batch_edit": {}}):
            controller = BatchEditController(selector_path=temp_selector_file)
            config = {
                "wait_after_action_ms": 200,
                "dom_stable_checks": 5,
                "retry_initial_delay_ms": 150,
            }
            strategy = controller._build_wait_strategy(config)

            assert strategy.wait_after_action_ms == 200
            assert strategy.dom_stable_checks == 5
            assert strategy.retry_initial_delay_ms == 150

    def test_load_selectors_success(self, temp_selector_file):
        """测试选择器加载成功"""
        from src.browser.batch_edit.controller import BatchEditController

        controller = BatchEditController(selector_path=temp_selector_file)

        assert "batch_edit" in controller.selectors
        assert "step_02_english_title" in controller.selectors["batch_edit"]

    def test_load_selectors_file_not_found(self, tmp_path):
        """测试选择器文件不存在"""
        from src.browser.batch_edit.controller import BatchEditController

        non_existent = str(tmp_path / "non_existent.json")

        # 应该返回空字典而不是抛出异常
        controller = BatchEditController(selector_path=non_existent)

        assert controller.selectors == {}


# ============================================================
# BatchEditController 步骤测试 (使用 Mock)
# ============================================================
class TestBatchEditControllerSteps:
    """BatchEditController 步骤测试"""

    @pytest.fixture
    def mock_page(self):
        """创建 Mock 页面"""
        page = AsyncMock()
        page.url = "https://test.com/batch-edit"
        page.title = AsyncMock(return_value="批量编辑")

        # Mock locator
        mock_locator = AsyncMock()
        mock_locator.first = MagicMock(return_value=mock_locator)
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_locator.press = AsyncMock()
        mock_locator.is_visible = AsyncMock(return_value=True)
        mock_locator.count = AsyncMock(return_value=1)

        page.locator = MagicMock(return_value=mock_locator)
        page.screenshot = AsyncMock()

        return page

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.batch_edit.controller import BatchEditController

        selector_config = {
            "smart_locator_config": {},
            "batch_edit": {
                "step_02_english_title": {"enabled": True, "input": "input.english"},
                "step_09_weight": {"enabled": True, "input": ["input.weight"]},
                "step_10_dimensions": {
                    "enabled": True,
                    "length_input": "input.length",
                    "width_input": "input.width",
                    "height_input": "input.height",
                },
                "step_14_suggested_price": {"enabled": True, "input": "input.price"},
                "navigation": {},
            },
        }
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps(selector_config))

        return BatchEditController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_step_01_modify_title(self, controller, mock_page):
        """测试步骤1: 修改标题(跳过)"""
        result = await controller.step_01_modify_title(mock_page)

        # 步骤1应该直接返回 True (跳过)
        assert result is True

    @pytest.mark.asyncio
    async def test_step_03_category_attrs(self, controller, mock_page):
        """测试步骤3: 类目属性"""
        result = await controller.step_03_category_attrs(mock_page)

        # 当前实现返回 True (待完善)
        assert result is True

    @pytest.mark.asyncio
    async def test_step_05_packaging(self, controller, mock_page):
        """测试步骤5: 包装信息"""
        result = await controller.step_05_packaging(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_step_06_origin(self, controller, mock_page):
        """测试步骤6: 产地信息"""
        result = await controller.step_06_origin(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_step_11_sku(self, controller, mock_page):
        """测试步骤11: SKU"""
        result = await controller.step_11_sku(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_step_12_sku_category(self, controller, mock_page):
        """测试步骤12: SKU类目"""
        result = await controller.step_12_sku_category(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_step_18_manual_upload(self, controller, mock_page):
        """测试步骤18: 手动上传"""
        result = await controller.step_18_manual_upload(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_select_all_products(self, controller, mock_page):
        """测试全选商品"""
        # Mock waiter
        with patch.object(controller, "_build_waiter") as mock_waiter_builder:
            mock_waiter = AsyncMock()
            mock_waiter.wait_for_dom_stable = AsyncMock()
            mock_waiter_builder.return_value = mock_waiter

            result = await controller.select_all_products(mock_page)

            assert result is True

    @pytest.mark.asyncio
    async def test_enter_batch_edit_mode_with_batch_url(self, controller, mock_page):
        """测试进入批量编辑模式(URL包含batch)"""
        mock_page.url = "https://test.com/batch"

        with patch.object(controller, "_build_waiter") as mock_waiter_builder:
            mock_waiter = AsyncMock()
            mock_waiter.wait_for_dom_stable = AsyncMock()
            mock_waiter_builder.return_value = mock_waiter

            result = await controller.enter_batch_edit_mode(mock_page)

            assert result is True

    @pytest.mark.asyncio
    async def test_enter_batch_edit_mode_with_batch_title(self, controller, mock_page):
        """测试进入批量编辑模式(标题包含批量)"""
        mock_page.url = "https://test.com/other"
        mock_page.title = AsyncMock(return_value="批量编辑页面")

        with patch.object(controller, "_build_waiter") as mock_waiter_builder:
            mock_waiter = AsyncMock()
            mock_waiter.wait_for_dom_stable = AsyncMock()
            mock_waiter_builder.return_value = mock_waiter

            result = await controller.enter_batch_edit_mode(mock_page)

            assert result is True


# ============================================================
# BatchEditController 完整流程测试
# ============================================================
class TestBatchEditControllerFlow:
    """BatchEditController 完整流程测试"""

    @pytest.fixture
    def mock_page(self):
        """创建完整 Mock 页面"""
        page = AsyncMock()
        page.url = "https://test.com/batch"
        page.title = AsyncMock(return_value="批量编辑")

        mock_locator = AsyncMock()
        mock_locator.first = MagicMock(return_value=mock_locator)
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_locator.press = AsyncMock()
        mock_locator.is_visible = AsyncMock(return_value=True)
        mock_locator.count = AsyncMock(return_value=0)

        page.locator = MagicMock(return_value=mock_locator)
        page.screenshot = AsyncMock()

        return page

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.batch_edit.controller import BatchEditController

        selector_config = {
            "smart_locator_config": {},
            "batch_edit": {"navigation": {}},
        }
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps(selector_config))

        return BatchEditController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_batch_edit_wrong_count_warning(self, controller, mock_page):
        """测试批量编辑数量不符合预期时的警告"""
        products_data = [{"cost": 150.0} for _ in range(10)]  # 只有 10 条，不是 20

        # Mock 所有步骤返回成功
        with (
            patch.object(controller, "select_all_products", return_value=True),
            patch.object(controller, "enter_batch_edit_mode", return_value=True),
            patch.object(controller, "execute_batch_edit_steps", return_value=True),
            patch.object(controller, "save_batch_edit", return_value=True),
        ):
            result = await controller.batch_edit(mock_page, products_data)

            assert result is True  # 仍然执行成功

    @pytest.mark.asyncio
    async def test_batch_edit_select_all_fails(self, controller, mock_page):
        """测试全选失败"""
        products_data = [{"cost": 150.0} for _ in range(20)]

        with patch.object(controller, "select_all_products", return_value=False):
            result = await controller.batch_edit(mock_page, products_data)

            assert result is False

    @pytest.mark.asyncio
    async def test_batch_edit_enter_mode_fails(self, controller, mock_page):
        """测试进入批量编辑模式失败"""
        products_data = [{"cost": 150.0} for _ in range(20)]

        with (
            patch.object(controller, "select_all_products", return_value=True),
            patch.object(controller, "enter_batch_edit_mode", return_value=False),
        ):
            result = await controller.batch_edit(mock_page, products_data)

            assert result is False

    @pytest.mark.asyncio
    async def test_batch_edit_steps_fail(self, controller, mock_page):
        """测试执行步骤失败"""
        products_data = [{"cost": 150.0} for _ in range(20)]

        with (
            patch.object(controller, "select_all_products", return_value=True),
            patch.object(controller, "enter_batch_edit_mode", return_value=True),
            patch.object(controller, "execute_batch_edit_steps", return_value=False),
        ):
            result = await controller.batch_edit(mock_page, products_data)

            assert result is False

    @pytest.mark.asyncio
    async def test_batch_edit_save_fails(self, controller, mock_page):
        """测试保存失败"""
        products_data = [{"cost": 150.0} for _ in range(20)]

        with (
            patch.object(controller, "select_all_products", return_value=True),
            patch.object(controller, "enter_batch_edit_mode", return_value=True),
            patch.object(controller, "execute_batch_edit_steps", return_value=True),
            patch.object(controller, "save_batch_edit", return_value=False),
        ):
            result = await controller.batch_edit(mock_page, products_data)

            assert result is False

    @pytest.mark.asyncio
    async def test_batch_edit_success(self, controller, mock_page):
        """测试批量编辑成功"""
        products_data = [{"cost": 150.0} for _ in range(20)]

        with (
            patch.object(controller, "select_all_products", return_value=True),
            patch.object(controller, "enter_batch_edit_mode", return_value=True),
            patch.object(controller, "execute_batch_edit_steps", return_value=True),
            patch.object(controller, "save_batch_edit", return_value=True),
        ):
            result = await controller.batch_edit(mock_page, products_data)

            assert result is True

    @pytest.mark.asyncio
    async def test_batch_edit_exception_handling(self, controller, mock_page):
        """测试异常处理"""
        products_data = [{"cost": 150.0} for _ in range(20)]

        with patch.object(controller, "select_all_products", side_effect=Exception("Test error")):
            result = await controller.batch_edit(mock_page, products_data)

            assert result is False
            mock_page.screenshot.assert_called_once()


# ============================================================
# BatchEditController 性能追踪测试
# ============================================================
class TestBatchEditControllerPerfTracking:
    """性能追踪测试"""

    @pytest.fixture
    def controller_with_tracker(self, tmp_path):
        """创建带性能追踪器的控制器"""
        from src.browser.batch_edit.controller import BatchEditController

        selector_config = {"smart_locator_config": {}, "batch_edit": {}}
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps(selector_config))

        mock_tracker = MagicMock()
        mock_tracker.operation = MagicMock()

        return BatchEditController(selector_path=str(selector_file), perf_tracker=mock_tracker)

    @pytest.mark.asyncio
    async def test_track_operation_with_tracker(self, controller_with_tracker):
        """测试有性能追踪器时的操作追踪"""
        ctx_manager = await controller_with_tracker._track_operation("test_op")

        # 应该返回追踪器的上下文管理器
        controller_with_tracker._perf_tracker.operation.assert_called_once_with("test_op")

    @pytest.mark.asyncio
    async def test_track_operation_without_tracker(self, tmp_path):
        """测试无性能追踪器时的操作追踪"""
        from src.browser.batch_edit.controller import BatchEditController

        selector_config = {"smart_locator_config": {}, "batch_edit": {}}
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps(selector_config))

        controller = BatchEditController(selector_path=str(selector_file))

        # 应该返回空的上下文管理器
        ctx_manager = await controller._track_operation("test_op")

        # 验证可以正常使用
        async with ctx_manager:
            pass  # 不应抛出异常
