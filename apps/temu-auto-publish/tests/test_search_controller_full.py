"""
@PURPOSE: SearchController 搜索控制器完整测试
@OUTLINE:
  - TestSearchControllerInit: 初始化测试
  - TestSearchAndCollect: search_and_collect 方法测试
  - TestNavigateToSearch: _navigate_to_search 方法测试
  - TestInputAndSearch: _input_and_search 方法测试
  - TestWaitForResults: _wait_for_results 方法测试
  - TestExtractProducts: _extract_products 方法测试
  - TestEdgeCases: 边界情况测试
@DEPENDENCIES:
  - 内部: browser.search_controller
  - 外部: pytest, pytest-asyncio, unittest.mock
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.browser.search_controller import SearchController
from src.models.result import SearchResult


# ============================================================
# SearchController 初始化测试
# ============================================================
class TestSearchControllerInit:
    """SearchController 初始化测试"""

    def test_init_success(self):
        """测试正常初始化"""
        mock_browser_manager = MagicMock()

        controller = SearchController(mock_browser_manager)

        assert controller.browser_manager is mock_browser_manager
        assert controller.base_url == "https://seller.temu.com"

    def test_init_stores_browser_manager(self):
        """测试保存浏览器管理器引用"""
        mock_browser_manager = MagicMock()
        mock_browser_manager.page = MagicMock()

        controller = SearchController(mock_browser_manager)

        assert controller.browser_manager is mock_browser_manager


# ============================================================
# search_and_collect 测试
# ============================================================
class TestSearchAndCollect:
    """search_and_collect 方法测试"""

    @pytest.fixture
    def mock_browser_manager(self):
        """创建 mock 浏览器管理器"""
        manager = MagicMock()
        manager.page = MagicMock()
        manager.screenshot = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_search_and_collect_success(self, mock_browser_manager):
        """测试成功搜索采集"""
        controller = SearchController(mock_browser_manager)

        # Mock 所有内部方法
        controller._navigate_to_search = AsyncMock()
        controller._input_and_search = AsyncMock()
        controller._wait_for_results = AsyncMock()
        controller._extract_products = AsyncMock(
            return_value=[
                {"url": "http://example.com/1", "title": "Product 1", "price": "99"},
                {"url": "http://example.com/2", "title": "Product 2", "price": "199"},
            ]
        )

        result = await controller.search_and_collect("P001", "智能手表", 5)

        assert result.status == "success"
        assert result.count == 2
        assert len(result.links) == 2
        assert result.product_id == "P001"
        assert result.keyword == "智能手表"

    @pytest.mark.asyncio
    async def test_search_and_collect_no_browser(self, mock_browser_manager):
        """测试浏览器未启动"""
        mock_browser_manager.page = None
        controller = SearchController(mock_browser_manager)

        with pytest.raises(RuntimeError, match="浏览器未启动"):
            await controller.search_and_collect("P001", "智能手表", 5)

    @pytest.mark.asyncio
    async def test_search_and_collect_navigate_failure(self, mock_browser_manager):
        """测试导航失败"""
        controller = SearchController(mock_browser_manager)

        controller._navigate_to_search = AsyncMock(side_effect=Exception("导航失败"))

        result = await controller.search_and_collect("P001", "智能手表", 5)

        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_search_and_collect_search_failure(self, mock_browser_manager):
        """测试搜索失败"""
        controller = SearchController(mock_browser_manager)

        controller._navigate_to_search = AsyncMock()
        controller._input_and_search = AsyncMock(side_effect=Exception("搜索失败"))

        result = await controller.search_and_collect("P001", "智能手表", 5)

        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_search_and_collect_screenshot_called(self, mock_browser_manager):
        """测试成功后调用截图"""
        controller = SearchController(mock_browser_manager)

        controller._navigate_to_search = AsyncMock()
        controller._input_and_search = AsyncMock()
        controller._wait_for_results = AsyncMock()
        controller._extract_products = AsyncMock(return_value=[])

        await controller.search_and_collect("P001", "智能手表", 5)

        mock_browser_manager.screenshot.assert_called_once()


# ============================================================
# _navigate_to_search 测试
# ============================================================
class TestNavigateToSearch:
    """_navigate_to_search 方法测试"""

    @pytest.fixture
    def mock_browser_manager(self):
        """创建 mock 浏览器管理器"""
        manager = MagicMock()
        manager.page = AsyncMock()
        manager.page.goto = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_navigate_to_search_success(self, mock_browser_manager):
        """测试成功导航"""
        controller = SearchController(mock_browser_manager)

        with patch("src.browser.search_controller.PageWaiter") as MockPageWaiter:
            mock_waiter = MagicMock()
            mock_waiter.wait_for_dom_stable = AsyncMock()
            MockPageWaiter.return_value = mock_waiter

            await controller._navigate_to_search()

            mock_browser_manager.page.goto.assert_called_once()
            mock_waiter.wait_for_dom_stable.assert_called_once()

    @pytest.mark.asyncio
    async def test_navigate_to_correct_url(self, mock_browser_manager):
        """测试导航到正确 URL"""
        controller = SearchController(mock_browser_manager)

        with patch("src.browser.search_controller.PageWaiter") as MockPageWaiter:
            mock_waiter = MagicMock()
            mock_waiter.wait_for_dom_stable = AsyncMock()
            MockPageWaiter.return_value = mock_waiter

            await controller._navigate_to_search()

            call_args = mock_browser_manager.page.goto.call_args
            assert "seller.temu.com" in call_args[0][0]
            assert "search" in call_args[0][0]


# ============================================================
# _input_and_search 测试
# ============================================================
class TestInputAndSearch:
    """_input_and_search 方法测试"""

    @pytest.fixture
    def mock_browser_manager(self):
        """创建 mock 浏览器管理器"""
        manager = MagicMock()
        mock_page = MagicMock()
        mock_page.locator = MagicMock()
        manager.page = mock_page
        return manager

    @pytest.mark.asyncio
    async def test_input_and_search_with_button(self, mock_browser_manager):
        """测试有搜索按钮的情况"""
        controller = SearchController(mock_browser_manager)

        # Mock locator 链
        mock_input = MagicMock()
        mock_input.first = MagicMock()
        mock_input.first.clear = AsyncMock()
        mock_input.first.fill = AsyncMock()
        mock_input.first.press = AsyncMock()

        mock_button = MagicMock()
        mock_button.first = MagicMock()
        mock_button.first.click = AsyncMock()

        def locator_side_effect(selector):
            if "input" in selector:
                return mock_input
            else:
                return mock_button

        mock_browser_manager.page.locator.side_effect = locator_side_effect

        with patch("src.browser.search_controller.PageWaiter") as MockPageWaiter:
            mock_waiter = MagicMock()
            mock_waiter.wait_for_dom_stable = AsyncMock()
            MockPageWaiter.return_value = mock_waiter

            await controller._input_and_search("智能手表")

            mock_input.first.clear.assert_called_once()
            mock_input.first.fill.assert_called_once_with("智能手表")
            mock_button.first.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_input_and_search_fallback_to_enter(self, mock_browser_manager):
        """测试回退到按回车"""
        controller = SearchController(mock_browser_manager)

        # Mock locator 链
        mock_input = MagicMock()
        mock_input.first = MagicMock()
        mock_input.first.clear = AsyncMock()
        mock_input.first.fill = AsyncMock()
        mock_input.first.press = AsyncMock()

        mock_button = MagicMock()
        mock_button.first = MagicMock()
        mock_button.first.click = AsyncMock(side_effect=Exception("按钮不存在"))

        def locator_side_effect(selector):
            if "input" in selector:
                return mock_input
            else:
                return mock_button

        mock_browser_manager.page.locator.side_effect = locator_side_effect

        with patch("src.browser.search_controller.PageWaiter") as MockPageWaiter:
            mock_waiter = MagicMock()
            mock_waiter.wait_for_dom_stable = AsyncMock()
            MockPageWaiter.return_value = mock_waiter

            await controller._input_and_search("智能手表")

            mock_input.first.press.assert_called_once_with("Enter")


# ============================================================
# _wait_for_results 测试
# ============================================================
class TestWaitForResults:
    """_wait_for_results 方法测试"""

    @pytest.fixture
    def mock_browser_manager(self):
        """创建 mock 浏览器管理器"""
        manager = MagicMock()
        mock_page = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        manager.page = mock_page
        return manager

    @pytest.mark.asyncio
    async def test_wait_for_results_success(self, mock_browser_manager):
        """测试成功等待结果"""
        controller = SearchController(mock_browser_manager)

        with patch("src.browser.search_controller.PageWaiter") as MockPageWaiter:
            mock_waiter = MagicMock()
            mock_waiter.wait_for_dom_stable = AsyncMock()
            mock_waiter.wait_for_network_idle = AsyncMock()
            MockPageWaiter.return_value = mock_waiter

            with patch("src.browser.search_controller.wait_network_idle") as mock_wait_idle:
                mock_wait_idle.return_value = None

                await controller._wait_for_results()

                mock_browser_manager.page.wait_for_selector.assert_called_once()

    @pytest.mark.asyncio
    async def test_wait_for_results_timeout(self, mock_browser_manager):
        """测试等待超时"""
        mock_browser_manager.page.wait_for_selector = AsyncMock(
            side_effect=Exception("Timeout")
        )
        controller = SearchController(mock_browser_manager)

        with patch("src.browser.search_controller.PageWaiter") as MockPageWaiter:
            mock_waiter = MagicMock()
            MockPageWaiter.return_value = mock_waiter

            # 不应该抛出异常，只是记录警告
            await controller._wait_for_results()

    @pytest.mark.asyncio
    async def test_wait_for_results_custom_timeout(self, mock_browser_manager):
        """测试自定义超时"""
        controller = SearchController(mock_browser_manager)

        with patch("src.browser.search_controller.PageWaiter") as MockPageWaiter:
            mock_waiter = MagicMock()
            mock_waiter.wait_for_dom_stable = AsyncMock()
            mock_waiter.wait_for_network_idle = AsyncMock()
            MockPageWaiter.return_value = mock_waiter

            with patch("src.browser.search_controller.wait_network_idle"):
                await controller._wait_for_results(timeout=60000)

                call_args = mock_browser_manager.page.wait_for_selector.call_args
                assert call_args[1]["timeout"] == 60000


# ============================================================
# _extract_products 测试
# ============================================================
class TestExtractProducts:
    """_extract_products 方法测试"""

    @pytest.fixture
    def mock_browser_manager(self):
        """创建 mock 浏览器管理器"""
        manager = MagicMock()
        mock_page = MagicMock()
        mock_page.locator = MagicMock()
        manager.page = mock_page
        return manager

    @pytest.mark.asyncio
    async def test_extract_products_success(self, mock_browser_manager):
        """测试成功提取商品"""
        controller = SearchController(mock_browser_manager)

        # Mock 商品列表
        mock_items = MagicMock()
        mock_items.count = AsyncMock(return_value=3)

        # 创建单个商品 item 的 mock
        def create_item_mock(title, price, url):
            item = MagicMock()

            title_elem = MagicMock()
            title_elem.first = MagicMock()
            title_elem.first.count = AsyncMock(return_value=1)
            title_elem.first.text_content = AsyncMock(return_value=title)

            price_elem = MagicMock()
            price_elem.first = MagicMock()
            price_elem.first.count = AsyncMock(return_value=1)
            price_elem.first.text_content = AsyncMock(return_value=price)

            link_elem = MagicMock()
            link_elem.first = MagicMock()
            link_elem.first.count = AsyncMock(return_value=1)
            link_elem.first.get_attribute = AsyncMock(return_value=url)

            def locator_side_effect(selector):
                if "title" in selector.lower() or "h3" in selector or "h4" in selector:
                    return title_elem
                elif "price" in selector.lower():
                    return price_elem
                elif selector == "a":
                    return link_elem
                return MagicMock()

            item.locator = locator_side_effect
            return item

        items = [
            create_item_mock("商品1", "99元", "http://example.com/1"),
            create_item_mock("商品2", "199元", "http://example.com/2"),
            create_item_mock("商品3", "299元", "/product/3"),  # 相对链接
        ]

        mock_items.nth = lambda i: items[i]
        mock_browser_manager.page.locator.return_value = mock_items

        products = await controller._extract_products(3)

        assert len(products) == 3
        assert products[0]["title"] == "商品1"
        assert products[0]["price"] == "99元"
        # 第三个商品的相对链接应该被转换为绝对链接
        assert products[2]["url"].startswith("https://seller.temu.com")

    @pytest.mark.asyncio
    async def test_extract_products_empty_list(self, mock_browser_manager):
        """测试空商品列表"""
        controller = SearchController(mock_browser_manager)

        mock_items = MagicMock()
        mock_items.count = AsyncMock(return_value=0)
        mock_browser_manager.page.locator.return_value = mock_items

        products = await controller._extract_products(5)

        assert len(products) == 0

    @pytest.mark.asyncio
    async def test_extract_products_partial_data(self, mock_browser_manager):
        """测试部分数据缺失"""
        controller = SearchController(mock_browser_manager)

        mock_items = MagicMock()
        mock_items.count = AsyncMock(return_value=1)

        # 创建缺失数据的商品
        item = MagicMock()

        title_elem = MagicMock()
        title_elem.first = MagicMock()
        title_elem.first.count = AsyncMock(return_value=0)  # 没有标题

        price_elem = MagicMock()
        price_elem.first = MagicMock()
        price_elem.first.count = AsyncMock(return_value=0)  # 没有价格

        link_elem = MagicMock()
        link_elem.first = MagicMock()
        link_elem.first.count = AsyncMock(return_value=0)  # 没有链接

        def locator_side_effect(selector):
            if "title" in selector.lower() or "h3" in selector or "h4" in selector:
                return title_elem
            elif "price" in selector.lower():
                return price_elem
            elif selector == "a":
                return link_elem
            return MagicMock()

        item.locator = locator_side_effect
        mock_items.nth = lambda i: item
        mock_browser_manager.page.locator.return_value = mock_items

        products = await controller._extract_products(1)

        assert len(products) == 1
        assert products[0]["title"] == "未知标题"
        assert products[0]["price"] == "未知价格"

    @pytest.mark.asyncio
    async def test_extract_products_limits_count(self, mock_browser_manager):
        """测试限制采集数量"""
        controller = SearchController(mock_browser_manager)

        mock_items = MagicMock()
        mock_items.count = AsyncMock(return_value=10)  # 有10个商品

        def create_simple_item(index):
            item = MagicMock()

            elem = MagicMock()
            elem.first = MagicMock()
            elem.first.count = AsyncMock(return_value=1)
            elem.first.text_content = AsyncMock(return_value=f"商品{index}")
            elem.first.get_attribute = AsyncMock(return_value=f"http://example.com/{index}")

            item.locator = lambda _: elem
            return item

        mock_items.nth = lambda i: create_simple_item(i)
        mock_browser_manager.page.locator.return_value = mock_items

        products = await controller._extract_products(3)  # 只要3个

        assert len(products) == 3

    @pytest.mark.asyncio
    async def test_extract_products_handles_exception(self, mock_browser_manager):
        """测试异常处理"""
        controller = SearchController(mock_browser_manager)

        mock_items = MagicMock()
        mock_items.count = AsyncMock(side_effect=Exception("提取失败"))
        mock_browser_manager.page.locator.return_value = mock_items

        products = await controller._extract_products(5)

        assert len(products) == 0


# ============================================================
# 边界情况测试
# ============================================================
class TestEdgeCases:
    """边界情况测试"""

    def test_search_result_model(self):
        """测试 SearchResult 模型"""
        result = SearchResult(product_id="P001", keyword="测试")

        assert result.product_id == "P001"
        assert result.keyword == "测试"
        assert result.status == "pending"
        assert result.count == 0
        assert result.links == []

    def test_search_result_with_links(self):
        """测试 SearchResult 带链接"""
        links = [
            {"url": "http://example.com/1", "title": "Product 1"},
            {"url": "http://example.com/2", "title": "Product 2"},
        ]
        result = SearchResult(
            product_id="P001", keyword="测试", links=links, count=2, status="success"
        )

        assert result.count == 2
        assert len(result.links) == 2
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_search_with_empty_keyword(self):
        """测试空关键词搜索"""
        mock_browser_manager = MagicMock()
        mock_browser_manager.page = MagicMock()
        mock_browser_manager.screenshot = AsyncMock()

        controller = SearchController(mock_browser_manager)
        controller._navigate_to_search = AsyncMock()
        controller._input_and_search = AsyncMock()
        controller._wait_for_results = AsyncMock()
        controller._extract_products = AsyncMock(return_value=[])

        result = await controller.search_and_collect("P001", "", 5)

        assert result.keyword == ""
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_search_with_special_characters(self):
        """测试特殊字符关键词"""
        mock_browser_manager = MagicMock()
        mock_browser_manager.page = MagicMock()
        mock_browser_manager.screenshot = AsyncMock()

        controller = SearchController(mock_browser_manager)
        controller._navigate_to_search = AsyncMock()
        controller._input_and_search = AsyncMock()
        controller._wait_for_results = AsyncMock()
        controller._extract_products = AsyncMock(return_value=[])

        result = await controller.search_and_collect("P001", "智能手表 & 蓝牙耳机", 5)

        assert result.keyword == "智能手表 & 蓝牙耳机"
        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_search_with_zero_count(self):
        """测试采集数量为0"""
        mock_browser_manager = MagicMock()
        mock_browser_manager.page = MagicMock()
        mock_browser_manager.screenshot = AsyncMock()

        controller = SearchController(mock_browser_manager)
        controller._navigate_to_search = AsyncMock()
        controller._input_and_search = AsyncMock()
        controller._wait_for_results = AsyncMock()
        controller._extract_products = AsyncMock(return_value=[])

        result = await controller.search_and_collect("P001", "测试", 0)

        assert result.count == 0

    @pytest.mark.asyncio
    async def test_screenshot_failure_handled(self):
        """测试截图失败不影响主流程"""
        mock_browser_manager = MagicMock()
        mock_browser_manager.page = MagicMock()
        mock_browser_manager.screenshot = AsyncMock(side_effect=Exception("截图失败"))

        controller = SearchController(mock_browser_manager)
        controller._navigate_to_search = AsyncMock(side_effect=Exception("测试错误"))

        # 即使截图失败，也不应该抛出额外异常
        result = await controller.search_and_collect("P001", "测试", 5)

        assert result.status == "failed"
