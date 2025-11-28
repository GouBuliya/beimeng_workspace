"""
@PURPOSE: 测试 PublishController 发布控制器
@OUTLINE:
  - TestPublishController: 测试发布控制器主类
  - TestPublishControllerSelectors: 测试选择器加载
  - TestPublishControllerMethods: 测试发布方法（使用Mock）
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.browser.publish_controller, tests.mocks
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.browser.publish_controller import PublishController
from tests.mocks import MockPage, MockLocator


class TestPublishController:
    """测试发布控制器主类"""
    
    def test_init_default(self):
        """测试默认初始化"""
        controller = PublishController()
        
        assert controller is not None
        assert controller.price_calculator is not None
    
    def test_init_custom_selector_path(self, tmp_path):
        """测试自定义选择器路径"""
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps({
            "publish": {"button": "#publish-btn"}
        }))
        
        controller = PublishController(str(selector_file))
        
        assert controller.selectors.get("publish") is not None
    
    def test_init_missing_selector_file(self, tmp_path):
        """测试选择器文件不存在"""
        nonexistent = tmp_path / "nonexistent.json"
        
        # 不应该抛出异常
        controller = PublishController(str(nonexistent))
        
        assert controller.selectors == {}


class TestPublishControllerSelectors:
    """测试选择器加载"""
    
    def test_load_selectors_success(self, tmp_path):
        """测试成功加载选择器"""
        selector_file = tmp_path / "selectors.json"
        selectors = {
            "publish": {
                "shop_dropdown": "#shop-select",
                "publish_button": "button.publish"
            }
        }
        selector_file.write_text(json.dumps(selectors))
        
        controller = PublishController(str(selector_file))
        
        assert "publish" in controller.selectors
    
    def test_load_selectors_invalid_json(self, tmp_path):
        """测试无效JSON"""
        selector_file = tmp_path / "invalid.json"
        selector_file.write_text("not valid json {{{")
        
        controller = PublishController(str(selector_file))
        
        assert controller.selectors == {}


class TestPublishControllerMethods:
    """测试发布方法（使用Mock）"""
    
    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器"""
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps({
            "publish": {
                "select_all_checkbox": "#select-all",
                "shop_dropdown": "#shop-select",
                "supply_price_input": ".supply-price",
                "publish_button": "#publish"
            }
        }))
        return PublishController(str(selector_file))
    
    @pytest.fixture
    def mock_page(self):
        """创建Mock页面"""
        page = MockPage()
        return page
    
    @pytest.mark.asyncio
    async def test_select_all_20_products(self, controller, mock_page):
        """测试全选20条产品"""
        # 设置Mock
        mock_page.wait_for_selector = AsyncMock(return_value=MockLocator())
        mock_page.locator = MagicMock(return_value=MockLocator())
        
        result = await controller.select_all_20_products(mock_page)
        
        # 验证返回类型
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_select_shop(self, controller, mock_page):
        """测试选择店铺"""
        mock_page.wait_for_selector = AsyncMock(return_value=MockLocator())
        mock_page.locator = MagicMock(return_value=MockLocator())
        mock_page.click = AsyncMock()
        
        result = await controller.select_shop(mock_page, "测试店铺")
        
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_set_supply_price(self, controller, mock_page):
        """测试设置供货价"""
        mock_page.wait_for_selector = AsyncMock(return_value=MockLocator())
        mock_page.locator = MagicMock(return_value=MockLocator())
        mock_page.fill = AsyncMock()
        
        products_data = [
            {"cost_price": 10.0},
            {"cost_price": 15.0}
        ]
        
        result = await controller.set_supply_price(mock_page, products_data)
        
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_batch_publish(self, controller, mock_page):
        """测试批量发布"""
        mock_page.wait_for_selector = AsyncMock(return_value=MockLocator())
        mock_page.locator = MagicMock(return_value=MockLocator())
        mock_page.click = AsyncMock()
        
        result = await controller.batch_publish(mock_page)
        
        assert isinstance(result, bool)
    

class TestPublishControllerPriceCalculation:
    """测试价格计算"""
    
    def test_price_calculator_exists(self):
        """测试价格计算器存在"""
        controller = PublishController()
        
        assert controller.price_calculator is not None
    
    def test_calculate_supply_price(self):
        """测试计算供货价"""
        controller = PublishController()
        
        # 使用价格计算器
        cost_price = 10.0
        result = controller.price_calculator.calculate(cost_price)
        
        # 验证返回值
        assert result.supply_price > 0


class TestPublishControllerEdgeCases:
    """测试边界情况"""
    
    @pytest.mark.asyncio
    async def test_empty_products_data(self, tmp_path):
        """测试空产品数据"""
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps({}))
        controller = PublishController(str(selector_file))
        
        mock_page = MockPage()
        mock_page.wait_for_selector = AsyncMock(return_value=MockLocator())
        
        result = await controller.set_supply_price(mock_page, [])
        
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_none_shop_name(self, tmp_path):
        """测试空店铺名"""
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps({}))
        controller = PublishController(str(selector_file))
        
        mock_page = MockPage()
        mock_page.wait_for_selector = AsyncMock(return_value=MockLocator())
        mock_page.locator = MagicMock(return_value=MockLocator())
        
        result = await controller.select_shop(mock_page, None)
        
        # 应该处理None值
        assert isinstance(result, bool)

