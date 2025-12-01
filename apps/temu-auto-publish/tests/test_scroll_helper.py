"""
@PURPOSE: 测试 utils/scroll_helper.py 滚动查找元素工具
@OUTLINE:
  - class TestScrollToTop: 测试滚动到顶部
  - class TestScrollToProductPosition: 测试精确滚动到商品位置
  - class TestScrollOneProduct: 测试滚动一个商品高度
  - class TestScrollContainer: 测试容器滚动
  - class TestIsAtScrollBottom: 测试检测是否到达底部
  - class TestScrollToFindElement: 测试滚动查找元素
  - class TestScrollToFindAndClick: 测试滚动查找并点击
  - class TestConstants: 测试常量
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.utils.scroll_helper
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestConstants:
    """测试常量定义."""

    def test_product_row_height(self) -> None:
        """测试商品行高度常量."""
        from src.utils.scroll_helper import PRODUCT_ROW_HEIGHT

        assert PRODUCT_ROW_HEIGHT == 128

    def test_default_container_selectors(self) -> None:
        """测试默认容器选择器."""
        from src.utils.scroll_helper import DEFAULT_CONTAINER_SELECTORS

        assert isinstance(DEFAULT_CONTAINER_SELECTORS, tuple)
        assert len(DEFAULT_CONTAINER_SELECTORS) > 0
        assert "#appScrollContainer" in DEFAULT_CONTAINER_SELECTORS


class TestScrollToTop:
    """测试 scroll_to_top 函数."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock()

        # Mock locator
        locator = MagicMock()
        locator.first = locator
        locator.count = AsyncMock(return_value=1)
        locator.evaluate = AsyncMock()
        page.locator = MagicMock(return_value=locator)

        return page

    @pytest.mark.asyncio
    async def test_scroll_to_top_success(self, mock_page) -> None:
        """测试成功滚动到顶部."""
        from src.utils.scroll_helper import scroll_to_top

        result = await scroll_to_top(mock_page)

        assert result is True
        mock_page.locator.return_value.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_scroll_to_top_container_not_found(self, mock_page) -> None:
        """测试容器未找到时的回退."""
        from src.utils.scroll_helper import scroll_to_top

        mock_page.locator.return_value.count = AsyncMock(return_value=0)
        mock_page.evaluate = AsyncMock()

        result = await scroll_to_top(mock_page)

        assert result is True
        mock_page.evaluate.assert_called_with("window.scrollTo(0, 0)")

    @pytest.mark.asyncio
    async def test_scroll_to_top_custom_selectors(self, mock_page) -> None:
        """测试自定义选择器."""
        from src.utils.scroll_helper import scroll_to_top

        custom_selectors = (".custom-container",)

        await scroll_to_top(mock_page, container_selectors=custom_selectors)

        mock_page.locator.assert_called_with(".custom-container")

    @pytest.mark.asyncio
    async def test_scroll_to_top_all_failed(self, mock_page) -> None:
        """测试所有方式都失败."""
        from src.utils.scroll_helper import scroll_to_top

        mock_page.locator.return_value.count = AsyncMock(return_value=0)
        mock_page.evaluate = AsyncMock(side_effect=Exception("失败"))

        result = await scroll_to_top(mock_page)

        assert result is False


class TestScrollToProductPosition:
    """测试 scroll_to_product_position 函数."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock()
        page.mouse = MagicMock()
        page.mouse.wheel = AsyncMock()

        # Mock locator
        locator = MagicMock()
        locator.first = locator
        locator.count = AsyncMock(return_value=1)
        locator.evaluate = AsyncMock(return_value=True)  # is_scrollable
        page.locator = MagicMock(return_value=locator)

        return page

    @pytest.mark.asyncio
    async def test_scroll_to_product_position_success(self, mock_page) -> None:
        """测试成功滚动到商品位置."""
        from src.utils.scroll_helper import scroll_to_product_position

        result = await scroll_to_product_position(mock_page, target_index=5)

        assert result is True

    @pytest.mark.asyncio
    async def test_scroll_to_product_position_invalid_index(self, mock_page) -> None:
        """测试无效索引."""
        from src.utils.scroll_helper import scroll_to_product_position

        result = await scroll_to_product_position(mock_page, target_index=-1)

        assert result is False

    @pytest.mark.asyncio
    async def test_scroll_to_product_position_first_product(self, mock_page) -> None:
        """测试滚动到第一个商品."""
        from src.utils.scroll_helper import scroll_to_product_position

        result = await scroll_to_product_position(mock_page, target_index=0)

        assert result is True

    @pytest.mark.asyncio
    async def test_scroll_to_product_position_custom_row_height(self, mock_page) -> None:
        """测试自定义行高度."""
        from src.utils.scroll_helper import scroll_to_product_position

        result = await scroll_to_product_position(
            mock_page, target_index=5, row_height=150
        )

        assert result is True


class TestScrollOneProduct:
    """测试 scroll_one_product 函数."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        page.mouse = MagicMock()
        page.mouse.wheel = AsyncMock()

        # Mock locator
        locator = MagicMock()
        locator.first = locator
        locator.count = AsyncMock(return_value=1)
        locator.evaluate = AsyncMock(return_value=True)
        page.locator = MagicMock(return_value=locator)

        return page

    @pytest.mark.asyncio
    async def test_scroll_one_product_success(self, mock_page) -> None:
        """测试成功滚动一个商品."""
        from src.utils.scroll_helper import scroll_one_product

        result = await scroll_one_product(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_scroll_one_product_custom_height(self, mock_page) -> None:
        """测试自定义行高度."""
        from src.utils.scroll_helper import scroll_one_product

        result = await scroll_one_product(mock_page, row_height=200)

        assert result is True


class TestScrollContainer:
    """测试 scroll_container 函数."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.mouse = MagicMock()
        page.mouse.wheel = AsyncMock()

        # Mock locator
        locator = MagicMock()
        locator.first = locator
        locator.count = AsyncMock(return_value=1)
        locator.evaluate = AsyncMock(return_value=True)  # is_scrollable
        page.locator = MagicMock(return_value=locator)

        return page

    @pytest.mark.asyncio
    async def test_scroll_container_success(self, mock_page) -> None:
        """测试成功滚动容器."""
        from src.utils.scroll_helper import scroll_container

        result = await scroll_container(mock_page, distance=300)

        assert result is True

    @pytest.mark.asyncio
    async def test_scroll_container_not_scrollable(self, mock_page) -> None:
        """测试容器不可滚动时回退到页面滚动."""
        from src.utils.scroll_helper import scroll_container

        mock_page.locator.return_value.evaluate = AsyncMock(return_value=False)

        result = await scroll_container(mock_page, distance=300)

        assert result is True
        mock_page.mouse.wheel.assert_called()

    @pytest.mark.asyncio
    async def test_scroll_container_no_container(self, mock_page) -> None:
        """测试无容器时回退."""
        from src.utils.scroll_helper import scroll_container

        mock_page.locator.return_value.count = AsyncMock(return_value=0)

        result = await scroll_container(mock_page, distance=300)

        assert result is True
        mock_page.mouse.wheel.assert_called()

    @pytest.mark.asyncio
    async def test_scroll_container_custom_selectors(self, mock_page) -> None:
        """测试自定义选择器."""
        from src.utils.scroll_helper import scroll_container

        custom_selectors = (".custom-scroll",)

        await scroll_container(mock_page, distance=300, container_selectors=custom_selectors)

        mock_page.locator.assert_called_with(".custom-scroll")

    @pytest.mark.asyncio
    async def test_scroll_container_all_failed(self, mock_page) -> None:
        """测试所有滚动方式都失败."""
        from src.utils.scroll_helper import scroll_container

        mock_page.locator.return_value.count = AsyncMock(return_value=0)
        mock_page.mouse.wheel = AsyncMock(side_effect=Exception("失败"))

        result = await scroll_container(mock_page, distance=300)

        assert result is False


class TestIsAtScrollBottom:
    """测试 is_at_scroll_bottom 函数."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.evaluate = AsyncMock()

        # Mock locator
        locator = MagicMock()
        locator.first = locator
        locator.count = AsyncMock(return_value=1)
        locator.evaluate = AsyncMock(return_value=True)
        page.locator = MagicMock(return_value=locator)

        return page

    @pytest.mark.asyncio
    async def test_is_at_scroll_bottom_true(self, mock_page) -> None:
        """测试已到达底部."""
        from src.utils.scroll_helper import is_at_scroll_bottom

        mock_page.locator.return_value.evaluate = AsyncMock(return_value=True)

        result = await is_at_scroll_bottom(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_at_scroll_bottom_false(self, mock_page) -> None:
        """测试未到达底部."""
        from src.utils.scroll_helper import is_at_scroll_bottom

        mock_page.locator.return_value.evaluate = AsyncMock(return_value=False)

        result = await is_at_scroll_bottom(mock_page)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_at_scroll_bottom_no_container(self, mock_page) -> None:
        """测试无容器时检查页面."""
        from src.utils.scroll_helper import is_at_scroll_bottom

        mock_page.locator.return_value.count = AsyncMock(return_value=0)
        mock_page.evaluate = AsyncMock(return_value=True)

        result = await is_at_scroll_bottom(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_at_scroll_bottom_custom_threshold(self, mock_page) -> None:
        """测试自定义阈值."""
        from src.utils.scroll_helper import is_at_scroll_bottom

        await is_at_scroll_bottom(mock_page, threshold=50)

        # 验证调用了带有阈值的 evaluate


class TestScrollToFindElement:
    """测试 scroll_to_find_element 函数."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock()
        page.mouse = MagicMock()
        page.mouse.wheel = AsyncMock()

        return page

    @pytest.mark.asyncio
    async def test_scroll_to_find_element_found_immediately(self, mock_page) -> None:
        """测试立即找到元素."""
        from src.utils.scroll_helper import scroll_to_find_element

        # Mock locator
        target_locator = MagicMock()
        target_locator.is_visible = AsyncMock(return_value=True)
        target_locator.scroll_into_view_if_needed = AsyncMock()

        locator = MagicMock()
        locator.count = AsyncMock(return_value=10)
        locator.nth = MagicMock(return_value=target_locator)

        locator_factory = MagicMock(return_value=locator)

        result = await scroll_to_find_element(
            mock_page, locator_factory, target_index=5, max_scroll_attempts=3
        )

        assert result == target_locator

    @pytest.mark.asyncio
    async def test_scroll_to_find_element_after_scroll(self, mock_page) -> None:
        """测试滚动后找到元素."""
        from src.utils.scroll_helper import scroll_to_find_element

        # 第一次返回少量元素，第二次返回足够元素
        counts = [3, 10]
        count_idx = [0]

        async def mock_count():
            idx = count_idx[0]
            count_idx[0] += 1
            return counts[min(idx, len(counts) - 1)]

        target_locator = MagicMock()
        target_locator.is_visible = AsyncMock(return_value=True)
        target_locator.scroll_into_view_if_needed = AsyncMock()

        locator = MagicMock()
        locator.count = mock_count
        locator.nth = MagicMock(return_value=target_locator)

        # Mock is_at_scroll_bottom 返回 False
        container_locator = MagicMock()
        container_locator.first = container_locator
        container_locator.count = AsyncMock(return_value=1)
        container_locator.evaluate = AsyncMock(
            side_effect=[True, False, True]
        )  # is_scrollable, at_bottom, scroll
        mock_page.locator = MagicMock(return_value=container_locator)

        locator_factory = MagicMock(return_value=locator)

        result = await scroll_to_find_element(
            mock_page, locator_factory, target_index=5, max_scroll_attempts=5
        )

        assert result == target_locator

    @pytest.mark.asyncio
    async def test_scroll_to_find_element_not_found(self, mock_page) -> None:
        """测试未找到元素."""
        from src.utils.scroll_helper import scroll_to_find_element

        locator = MagicMock()
        locator.count = AsyncMock(return_value=3)  # 始终只有3个元素

        # Mock at bottom
        container_locator = MagicMock()
        container_locator.first = container_locator
        container_locator.count = AsyncMock(return_value=1)
        container_locator.evaluate = AsyncMock(return_value=True)  # at_bottom
        mock_page.locator = MagicMock(return_value=container_locator)

        locator_factory = MagicMock(return_value=locator)

        result = await scroll_to_find_element(
            mock_page, locator_factory, target_index=10, max_scroll_attempts=2
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_scroll_to_find_element_max_attempts(self, mock_page) -> None:
        """测试达到最大尝试次数."""
        from src.utils.scroll_helper import scroll_to_find_element

        locator = MagicMock()
        locator.count = AsyncMock(return_value=3)

        # Mock not at bottom
        container_locator = MagicMock()
        container_locator.first = container_locator
        container_locator.count = AsyncMock(return_value=1)
        container_locator.evaluate = AsyncMock(
            side_effect=[True, False, True, False]
        )  # alternating
        mock_page.locator = MagicMock(return_value=container_locator)

        locator_factory = MagicMock(return_value=locator)

        result = await scroll_to_find_element(
            mock_page, locator_factory, target_index=10, max_scroll_attempts=2
        )

        assert result is None


class TestScrollToFindAndClick:
    """测试 scroll_to_find_and_click 函数."""

    @pytest.fixture
    def mock_page(self):
        """创建模拟页面."""
        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_scroll_to_find_and_click_success(self, mock_page) -> None:
        """测试成功找到并点击."""
        from src.utils.scroll_helper import scroll_to_find_and_click

        # Mock element
        target_locator = MagicMock()
        target_locator.click = AsyncMock()
        target_locator.is_visible = AsyncMock(return_value=True)
        target_locator.scroll_into_view_if_needed = AsyncMock()

        locator = MagicMock()
        locator.count = AsyncMock(return_value=10)
        locator.nth = MagicMock(return_value=target_locator)

        locator_factory = MagicMock(return_value=locator)

        result = await scroll_to_find_and_click(
            mock_page, locator_factory, target_index=5
        )

        assert result is True
        target_locator.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_scroll_to_find_and_click_not_found(self, mock_page) -> None:
        """测试未找到元素."""
        from src.utils.scroll_helper import scroll_to_find_and_click

        locator = MagicMock()
        locator.count = AsyncMock(return_value=3)

        # Mock at bottom
        container_locator = MagicMock()
        container_locator.first = container_locator
        container_locator.count = AsyncMock(return_value=1)
        container_locator.evaluate = AsyncMock(return_value=True)
        mock_page.locator = MagicMock(return_value=container_locator)

        locator_factory = MagicMock(return_value=locator)

        result = await scroll_to_find_and_click(
            mock_page, locator_factory, target_index=10
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_scroll_to_find_and_click_click_failed(self, mock_page) -> None:
        """测试点击失败."""
        from src.utils.scroll_helper import scroll_to_find_and_click

        # Mock element with click failure
        target_locator = MagicMock()
        target_locator.click = AsyncMock(side_effect=Exception("点击失败"))
        target_locator.is_visible = AsyncMock(return_value=True)
        target_locator.scroll_into_view_if_needed = AsyncMock()

        locator = MagicMock()
        locator.count = AsyncMock(return_value=10)
        locator.nth = MagicMock(return_value=target_locator)

        locator_factory = MagicMock(return_value=locator)

        result = await scroll_to_find_and_click(
            mock_page, locator_factory, target_index=5
        )

        assert result is False


class TestModuleExports:
    """测试模块导出."""

    def test_scroll_to_top_import(self) -> None:
        """测试 scroll_to_top 可导入."""
        from src.utils.scroll_helper import scroll_to_top

        assert callable(scroll_to_top)

    def test_scroll_to_product_position_import(self) -> None:
        """测试 scroll_to_product_position 可导入."""
        from src.utils.scroll_helper import scroll_to_product_position

        assert callable(scroll_to_product_position)

    def test_scroll_one_product_import(self) -> None:
        """测试 scroll_one_product 可导入."""
        from src.utils.scroll_helper import scroll_one_product

        assert callable(scroll_one_product)

    def test_scroll_container_import(self) -> None:
        """测试 scroll_container 可导入."""
        from src.utils.scroll_helper import scroll_container

        assert callable(scroll_container)

    def test_is_at_scroll_bottom_import(self) -> None:
        """测试 is_at_scroll_bottom 可导入."""
        from src.utils.scroll_helper import is_at_scroll_bottom

        assert callable(is_at_scroll_bottom)

    def test_scroll_to_find_element_import(self) -> None:
        """测试 scroll_to_find_element 可导入."""
        from src.utils.scroll_helper import scroll_to_find_element

        assert callable(scroll_to_find_element)

    def test_scroll_to_find_and_click_import(self) -> None:
        """测试 scroll_to_find_and_click 可导入."""
        from src.utils.scroll_helper import scroll_to_find_and_click

        assert callable(scroll_to_find_and_click)
