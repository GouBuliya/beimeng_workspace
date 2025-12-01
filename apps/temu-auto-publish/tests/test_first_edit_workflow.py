"""
@PURPOSE: 测试 first_edit/workflow.py 首次编辑工作流
@OUTLINE:
  - class TestFirstEditWorkflowMixin: 完整首次编辑流程测试
  - 测试流程编排,错误处理,步骤执行顺序
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.browser.first_edit.workflow, tests.mocks
"""

from unittest.mock import AsyncMock, patch

import pytest
from tests.mocks.browser_mock import MockLocator, MockPage


class TestFirstEditWorkflowMixin:
    """测试 FirstEditWorkflowMixin 类."""

    @pytest.fixture
    def mock_page(self) -> MockPage:
        """创建模拟页面."""
        page = MockPage(url="https://seller.temu.com/edit")
        # 设置常用选择器的模拟定位器
        page.set_mock_locator("text='基本信息'", MockLocator(is_visible=True))
        return page

    @pytest.fixture
    def workflow_mixin(self):
        """创建工作流混入实例.

        由于 FirstEditWorkflowMixin 是混入类,需要继承使用.
        这里使用 patch 来模拟其方法.
        """
        from src.browser.first_edit.workflow import FirstEditWorkflowMixin

        # 创建实例,使用临时配置路径
        with patch.object(
            FirstEditWorkflowMixin,
            "_load_selectors",
            return_value={"first_edit_dialog": {"navigation": {"basic_info": "text='基本信息'"}}},
        ):
            instance = FirstEditWorkflowMixin(selector_path="config/test.json")
            return instance

    @pytest.mark.asyncio
    async def test_complete_first_edit_success(self, workflow_mixin, mock_page: MockPage) -> None:
        """测试完整首次编辑流程成功."""
        # 模拟所有子方法成功
        workflow_mixin.edit_title = AsyncMock(return_value=True)
        workflow_mixin.set_sku_price = AsyncMock(return_value=True)
        workflow_mixin.set_sku_stock = AsyncMock(return_value=True)
        workflow_mixin.set_package_weight_in_logistics = AsyncMock(return_value=True)
        workflow_mixin.set_package_dimensions_in_logistics = AsyncMock(return_value=True)
        workflow_mixin.save_changes = AsyncMock(return_value=True)
        workflow_mixin.close_dialog = AsyncMock(return_value=True)

        result = await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        assert result is True
        workflow_mixin.edit_title.assert_called_once_with(mock_page, "测试标题")
        workflow_mixin.set_sku_price.assert_called_once_with(mock_page, 99.99)
        workflow_mixin.set_sku_stock.assert_called_once_with(mock_page, 100)
        workflow_mixin.set_package_weight_in_logistics.assert_called_once_with(mock_page, 0.5)
        workflow_mixin.set_package_dimensions_in_logistics.assert_called_once_with(
            mock_page, 10.0, 8.0, 5.0
        )
        workflow_mixin.save_changes.assert_called_once()
        workflow_mixin.close_dialog.assert_called_once_with(mock_page)

    @pytest.mark.asyncio
    async def test_complete_first_edit_title_failure(
        self, workflow_mixin, mock_page: MockPage
    ) -> None:
        """测试标题设置失败时流程中断."""
        workflow_mixin.edit_title = AsyncMock(return_value=False)
        workflow_mixin.set_sku_price = AsyncMock(return_value=True)

        result = await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        assert result is False
        workflow_mixin.edit_title.assert_called_once()
        # 标题失败后,后续步骤不应执行
        workflow_mixin.set_sku_price.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_first_edit_price_failure(
        self, workflow_mixin, mock_page: MockPage
    ) -> None:
        """测试价格设置失败时流程中断."""
        workflow_mixin.edit_title = AsyncMock(return_value=True)
        workflow_mixin.set_sku_price = AsyncMock(return_value=False)
        workflow_mixin.set_sku_stock = AsyncMock(return_value=True)

        result = await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        assert result is False
        workflow_mixin.edit_title.assert_called_once()
        workflow_mixin.set_sku_price.assert_called_once()
        workflow_mixin.set_sku_stock.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_first_edit_stock_failure(
        self, workflow_mixin, mock_page: MockPage
    ) -> None:
        """测试库存设置失败时流程中断."""
        workflow_mixin.edit_title = AsyncMock(return_value=True)
        workflow_mixin.set_sku_price = AsyncMock(return_value=True)
        workflow_mixin.set_sku_stock = AsyncMock(return_value=False)
        workflow_mixin.set_package_weight_in_logistics = AsyncMock(return_value=True)

        result = await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        assert result is False
        workflow_mixin.set_sku_stock.assert_called_once()
        workflow_mixin.set_package_weight_in_logistics.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_first_edit_weight_failure_continues(
        self, workflow_mixin, mock_page: MockPage
    ) -> None:
        """测试重量设置失败时流程继续(非致命错误)."""
        workflow_mixin.edit_title = AsyncMock(return_value=True)
        workflow_mixin.set_sku_price = AsyncMock(return_value=True)
        workflow_mixin.set_sku_stock = AsyncMock(return_value=True)
        workflow_mixin.set_package_weight_in_logistics = AsyncMock(return_value=False)  # 失败
        workflow_mixin.set_package_dimensions_in_logistics = AsyncMock(return_value=True)
        workflow_mixin.save_changes = AsyncMock(return_value=True)
        workflow_mixin.close_dialog = AsyncMock(return_value=True)

        result = await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        # 重量失败但流程应继续
        assert result is True
        workflow_mixin.set_package_dimensions_in_logistics.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_first_edit_dimensions_failure_continues(
        self, workflow_mixin, mock_page: MockPage
    ) -> None:
        """测试尺寸设置失败时流程继续(非致命错误)."""
        workflow_mixin.edit_title = AsyncMock(return_value=True)
        workflow_mixin.set_sku_price = AsyncMock(return_value=True)
        workflow_mixin.set_sku_stock = AsyncMock(return_value=True)
        workflow_mixin.set_package_weight_in_logistics = AsyncMock(return_value=True)
        workflow_mixin.set_package_dimensions_in_logistics = AsyncMock(return_value=False)  # 失败
        workflow_mixin.save_changes = AsyncMock(return_value=True)
        workflow_mixin.close_dialog = AsyncMock(return_value=True)

        result = await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        # 尺寸失败但流程应继续
        assert result is True
        workflow_mixin.save_changes.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_first_edit_dimensions_validation_error(
        self, workflow_mixin, mock_page: MockPage
    ) -> None:
        """测试尺寸验证失败时流程继续."""
        workflow_mixin.edit_title = AsyncMock(return_value=True)
        workflow_mixin.set_sku_price = AsyncMock(return_value=True)
        workflow_mixin.set_sku_stock = AsyncMock(return_value=True)
        workflow_mixin.set_package_weight_in_logistics = AsyncMock(return_value=True)
        workflow_mixin.set_package_dimensions_in_logistics = AsyncMock(
            side_effect=ValueError("尺寸超出范围")
        )
        workflow_mixin.save_changes = AsyncMock(return_value=True)
        workflow_mixin.close_dialog = AsyncMock(return_value=True)

        result = await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        # ValueError 被捕获,流程继续
        assert result is True

    @pytest.mark.asyncio
    async def test_complete_first_edit_save_failure(
        self, workflow_mixin, mock_page: MockPage
    ) -> None:
        """测试保存失败时流程中断."""
        workflow_mixin.edit_title = AsyncMock(return_value=True)
        workflow_mixin.set_sku_price = AsyncMock(return_value=True)
        workflow_mixin.set_sku_stock = AsyncMock(return_value=True)
        workflow_mixin.set_package_weight_in_logistics = AsyncMock(return_value=True)
        workflow_mixin.set_package_dimensions_in_logistics = AsyncMock(return_value=True)
        workflow_mixin.save_changes = AsyncMock(return_value=False)  # 失败
        workflow_mixin.close_dialog = AsyncMock(return_value=True)

        result = await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        assert result is False
        workflow_mixin.close_dialog.assert_not_called()

    @pytest.mark.asyncio
    async def test_complete_first_edit_close_failure_continues(
        self, workflow_mixin, mock_page: MockPage
    ) -> None:
        """测试关闭弹窗失败时流程仍然成功."""
        workflow_mixin.edit_title = AsyncMock(return_value=True)
        workflow_mixin.set_sku_price = AsyncMock(return_value=True)
        workflow_mixin.set_sku_stock = AsyncMock(return_value=True)
        workflow_mixin.set_package_weight_in_logistics = AsyncMock(return_value=True)
        workflow_mixin.set_package_dimensions_in_logistics = AsyncMock(return_value=True)
        workflow_mixin.save_changes = AsyncMock(return_value=True)
        workflow_mixin.close_dialog = AsyncMock(return_value=False)  # 失败

        result = await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        # 关闭失败但整体流程成功
        assert result is True

    @pytest.mark.asyncio
    async def test_complete_first_edit_exception_handling(
        self, workflow_mixin, mock_page: MockPage
    ) -> None:
        """测试异常处理."""
        workflow_mixin.edit_title = AsyncMock(side_effect=Exception("网络错误"))

        result = await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_step_execution_order(self, workflow_mixin, mock_page: MockPage) -> None:
        """测试步骤执行顺序."""
        call_order = []

        async def track_edit_title(*args):
            call_order.append("edit_title")
            return True

        async def track_set_price(*args):
            call_order.append("set_sku_price")
            return True

        async def track_set_stock(*args):
            call_order.append("set_sku_stock")
            return True

        async def track_set_weight(*args):
            call_order.append("set_package_weight")
            return True

        async def track_set_dimensions(*args):
            call_order.append("set_package_dimensions")
            return True

        async def track_save(*args, **kwargs):
            call_order.append("save_changes")
            return True

        async def track_close(*args):
            call_order.append("close_dialog")
            return True

        workflow_mixin.edit_title = track_edit_title
        workflow_mixin.set_sku_price = track_set_price
        workflow_mixin.set_sku_stock = track_set_stock
        workflow_mixin.set_package_weight_in_logistics = track_set_weight
        workflow_mixin.set_package_dimensions_in_logistics = track_set_dimensions
        workflow_mixin.save_changes = track_save
        workflow_mixin.close_dialog = track_close

        await workflow_mixin.complete_first_edit(
            page=mock_page,
            title="测试标题",
            price=99.99,
            stock=100,
            weight=0.5,
            dimensions=(10.0, 8.0, 5.0),
        )

        expected_order = [
            "edit_title",
            "set_sku_price",
            "set_sku_stock",
            "set_package_weight",
            "set_package_dimensions",
            "save_changes",
            "close_dialog",
        ]
        assert call_order == expected_order


class TestFirstEditBase:
    """测试 FirstEditBase 基类."""

    @pytest.fixture
    def mock_page(self) -> MockPage:
        """创建模拟页面."""
        return MockPage()

    def test_selector_loading_with_valid_path(self) -> None:
        """测试有效路径加载选择器."""
        from src.browser.first_edit.base import FirstEditBase

        # 使用实际的选择器文件
        base = FirstEditBase(selector_path="config/miaoshou_selectors_v2.json")
        # 如果文件存在,应该加载成功
        assert isinstance(base.selectors, dict)

    def test_selector_loading_with_invalid_path(self) -> None:
        """测试无效路径返回空字典."""
        from src.browser.first_edit.base import FirstEditBase

        base = FirstEditBase(selector_path="nonexistent/path.json")
        # 文件不存在应返回空字典
        assert base.selectors == {}

    @pytest.mark.asyncio
    async def test_find_visible_element_first_match(self, mock_page: MockPage) -> None:
        """测试顺序定位首个匹配元素."""
        from src.browser.first_edit.base import FirstEditBase

        with patch.object(FirstEditBase, "_load_selectors", return_value={}):
            base = FirstEditBase()

        # 设置第一个选择器可见
        mock_page.set_mock_locator("selector1", MockLocator(is_visible=True, count=1))
        mock_page.set_mock_locator("selector2", MockLocator(is_visible=True, count=1))

        result = await base.find_visible_element(
            mock_page, ["selector1", "selector2"], context_name="test"
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_find_visible_element_fallback(self, mock_page: MockPage) -> None:
        """测试首个不可见时回退到后续选择器."""
        from src.browser.first_edit.base import FirstEditBase

        with patch.object(FirstEditBase, "_load_selectors", return_value={}):
            base = FirstEditBase()

        # 第一个不可见,第二个可见
        mock_page.set_mock_locator("selector1", MockLocator(is_visible=False, count=1))
        mock_page.set_mock_locator("selector2", MockLocator(is_visible=True, count=1))

        result = await base.find_visible_element(
            mock_page, ["selector1", "selector2"], context_name="test"
        )

        # 应该找到第二个
        assert result is not None

    @pytest.mark.asyncio
    async def test_find_visible_element_none_found(self, mock_page: MockPage) -> None:
        """测试所有选择器都不匹配时返回 None."""
        from src.browser.first_edit.base import FirstEditBase

        with patch.object(FirstEditBase, "_load_selectors", return_value={}):
            base = FirstEditBase()

        # 所有都不可见
        mock_page.set_mock_locator("selector1", MockLocator(is_visible=False, count=0))
        mock_page.set_mock_locator("selector2", MockLocator(is_visible=False, count=0))

        result = await base.find_visible_element(
            mock_page, ["selector1", "selector2"], context_name="test"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_find_visible_element_with_nth(self, mock_page: MockPage) -> None:
        """测试使用 nth 参数定位第 n 个元素."""
        from src.browser.first_edit.base import FirstEditBase

        with patch.object(FirstEditBase, "_load_selectors", return_value={}):
            base = FirstEditBase()

        # 设置有多个匹配元素
        mock_page.set_mock_locator("selector1", MockLocator(is_visible=True, count=3))

        result = await base.find_visible_element(
            mock_page, ["selector1"], context_name="test", nth=1
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_find_visible_element_nth_out_of_range(self, mock_page: MockPage) -> None:
        """测试 nth 超出范围时跳过."""
        from src.browser.first_edit.base import FirstEditBase

        with patch.object(FirstEditBase, "_load_selectors", return_value={}):
            base = FirstEditBase()

        # 只有 1 个元素,但请求第 2 个
        mock_page.set_mock_locator("selector1", MockLocator(is_visible=True, count=1))

        result = await base.find_visible_element(
            mock_page, ["selector1"], context_name="test", nth=1
        )

        # 应该返回 None 因为 nth=1 但只有 1 个元素
        assert result is None
