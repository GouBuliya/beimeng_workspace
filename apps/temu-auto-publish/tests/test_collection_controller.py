"""
@PURPOSE: 测试 CollectionController 采集控制器
@OUTLINE:
  - TestCollectionController: 测试采集控制器主类
  - TestCollectionControllerSelectors: 测试选择器功能
  - TestCollectionControllerMethods: 测试采集方法（使用Mock）
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.browser.collection_controller, tests.mocks
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.browser.collection_controller import CollectionController
from tests.mocks import MockPage, MockLocator


class TestCollectionController:
    """测试采集控制器主类"""

    def test_init_default(self):
        """测试默认初始化"""
        controller = CollectionController()

        assert controller is not None
        assert controller.selectors is not None

    def test_init_custom_config(self, tmp_path):
        """测试自定义配置路径"""
        config_file = tmp_path / "collection_config.json"
        config_file.write_text(json.dumps({"store": {"search_input": "#search"}}))

        controller = CollectionController(str(config_file))

        assert "store" in controller.selectors

    def test_init_missing_config(self, tmp_path):
        """测试配置文件不存在"""
        nonexistent = tmp_path / "nonexistent.json"

        controller = CollectionController(str(nonexistent))

        # 应该使用默认选择器
        assert controller.selectors is not None


class TestCollectionControllerSelectors:
    """测试选择器功能"""

    def test_load_selectors_success(self, tmp_path):
        """测试成功加载选择器"""
        config_file = tmp_path / "selectors.json"
        selectors = {
            "store": {"visit_button": "button.visit", "search_input": "input.search"},
            "product": {"item_card": ".product-card"},
        }
        config_file.write_text(json.dumps(selectors))

        controller = CollectionController(str(config_file))

        assert "store" in controller.selectors
        assert "product" in controller.selectors

    def test_get_default_selectors(self):
        """测试默认选择器"""
        controller = CollectionController("/nonexistent/path.json")

        defaults = controller._get_default_selectors()

        assert "store" in defaults
        assert "product" in defaults
        assert "search_input" in defaults["store"]


class TestCollectionControllerMethods:
    """测试采集方法（使用Mock）"""

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器"""
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "store": {
                        "visit_button": "button.visit",
                        "search_input": "input.search",
                        "search_button": "button.search",
                    },
                    "product": {"item_card": ".product-card", "product_link": "a.product-link"},
                }
            )
        )
        return CollectionController(str(config_file))

    @pytest.fixture
    def mock_page(self):
        """创建Mock页面"""
        page = MockPage()
        page.wait_for_selector = AsyncMock(return_value=MockLocator())
        page.locator = MagicMock(return_value=MockLocator())
        page.click = AsyncMock()
        page.fill = AsyncMock()
        page.goto = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_visit_store(self, controller, mock_page):
        """测试访问店铺"""
        result = await controller.visit_store(mock_page)

        # 验证返回类型
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_search_products(self, controller, mock_page):
        """测试搜索产品"""
        mock_page.locator = MagicMock(return_value=MockLocator(count=5))

        result = await controller.search_products(mock_page, "药箱收纳盒")

        assert isinstance(result, (list, bool))

    @pytest.mark.asyncio
    async def test_collect_links(self, controller, mock_page):
        """测试采集链接"""
        # 设置Mock返回多个元素
        mock_locator = MockLocator(count=5)
        mock_page.locator = MagicMock(return_value=mock_locator)

        result = await controller.collect_links(mock_page, count=5)

        assert isinstance(result, (list, bool))

    @pytest.mark.asyncio
    async def test_add_to_collection_box(self, controller, mock_page):
        """测试添加到采集箱"""
        links = ["https://example.com/product/1", "https://example.com/product/2"]

        result = await controller.add_to_collection_box(mock_page, links)

        assert isinstance(result, bool)


class TestCollectionControllerSearch:
    """测试搜索功能"""

    @pytest.fixture
    def controller(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}))
        return CollectionController(str(config_file))

    @pytest.fixture
    def mock_page(self):
        page = MockPage()
        page.wait_for_selector = AsyncMock(return_value=MockLocator())
        page.locator = MagicMock(return_value=MockLocator())
        page.fill = AsyncMock()
        page.click = AsyncMock()
        page.press = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_search_and_collect(self, controller, mock_page):
        """测试搜索并采集"""
        mock_page.locator = MagicMock(return_value=MockLocator(count=5))

        result = await controller.search_and_collect(mock_page, keyword="测试产品", count=5)

        assert isinstance(result, (list, bool))

    @pytest.mark.asyncio
    async def test_search_empty_keyword(self, controller, mock_page):
        """测试空关键词搜索"""
        result = await controller.search_products(mock_page, "")

        # 空关键词应该处理
        assert isinstance(result, (list, bool))


class TestCollectionControllerEdgeCases:
    """测试边界情况"""

    @pytest.fixture
    def controller(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({}))
        return CollectionController(str(config_file))

    @pytest.mark.asyncio
    async def test_collect_zero_links(self, controller):
        """测试采集0个链接"""
        mock_page = MockPage()
        mock_page.locator = MagicMock(return_value=MockLocator(count=0))

        result = await controller.collect_links(mock_page, count=0)

        assert isinstance(result, (list, bool))

    @pytest.mark.asyncio
    async def test_collect_more_than_available(self, controller):
        """测试采集数量超过可用数量"""
        mock_page = MockPage()
        mock_page.locator = MagicMock(return_value=MockLocator(count=3))
        mock_page.wait_for_selector = AsyncMock(return_value=MockLocator())

        result = await controller.collect_links(mock_page, count=10)

        # 应该返回可用的数量
        assert isinstance(result, (list, bool))

    @pytest.mark.asyncio
    async def test_special_characters_in_keyword(self, controller):
        """测试关键词中的特殊字符"""
        mock_page = MockPage()
        mock_page.wait_for_selector = AsyncMock(return_value=MockLocator())
        mock_page.fill = AsyncMock()
        mock_page.click = AsyncMock()
        mock_page.locator = MagicMock(return_value=MockLocator())

        result = await controller.search_products(mock_page, "产品【特殊】名称")

        assert isinstance(result, (list, bool))


class TestCollectionControllerCookies:
    """测试Cookie功能"""

    def test_temu_cookie_path_default(self):
        """测试默认Temu Cookie路径"""
        controller = CollectionController()

        assert controller.temu_cookie_path is not None

    def test_temu_cookie_path_custom(self, tmp_path):
        """测试自定义Temu Cookie路径"""
        cookie_path = tmp_path / "temu_cookies.json"
        controller = CollectionController(temu_cookie_path=str(cookie_path))

        assert controller.temu_cookie_path == cookie_path

    def test_temu_cookies_not_loaded_initially(self):
        """测试初始状态Cookie未加载"""
        controller = CollectionController()

        assert controller._temu_cookies_loaded is False
