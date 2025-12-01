"""
@PURPOSE: FirstEdit 首次编辑模块测试
@OUTLINE:
  - TestFirstEditBase: 基础类测试(选择器加载)
  - TestFirstEditTitle: 标题操作测试
  - TestFirstEditWorkflow: 完整工作流测试
@DEPENDENCIES:
  - 内部: browser.first_edit
  - 外部: pytest, pytest-asyncio
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# FirstEditBase 测试
# ============================================================
class TestFirstEditBase:
    """FirstEditBase 基础类测试"""

    @pytest.fixture
    def temp_selector_file(self, tmp_path):
        """创建临时选择器配置文件"""
        selector_config = {
            "first_edit_dialog": {
                "title_input": [
                    "input.title",
                    "input[name='title']",
                ],
                "price_input": "input.price",
                "stock_input": "input.stock",
                "navigation": {
                    "basic_info": "text='基本信息'",
                    "logistics": "text='物流信息'",
                },
            },
            "smart_locator_config": {
                "timeout_per_selector": 3000,
            },
        }
        selector_file = tmp_path / "test_selectors.json"
        selector_file.write_text(json.dumps(selector_config))
        return str(selector_file)

    def test_init_default(self):
        """测试默认初始化"""
        from src.browser.first_edit.base import FirstEditBase

        with patch.object(FirstEditBase, "_load_selectors", return_value={}):
            base = FirstEditBase()

            assert base.selectors == {}
            assert base._resolver is None

    def test_init_with_selector_path(self, temp_selector_file):
        """测试指定选择器路径初始化"""
        from src.browser.first_edit.base import FirstEditBase

        base = FirstEditBase(selector_path=temp_selector_file)

        assert "first_edit_dialog" in base.selectors
        assert "title_input" in base.selectors["first_edit_dialog"]

    def test_load_selectors_success(self, temp_selector_file):
        """测试选择器加载成功"""
        from src.browser.first_edit.base import FirstEditBase

        base = FirstEditBase(selector_path=temp_selector_file)

        assert base.selectors["first_edit_dialog"]["price_input"] == "input.price"

    def test_load_selectors_file_not_found(self, tmp_path):
        """测试选择器文件不存在"""
        from src.browser.first_edit.base import FirstEditBase

        non_existent = str(tmp_path / "non_existent.json")
        base = FirstEditBase(selector_path=non_existent)

        # 应该返回空字典而不是抛出异常
        assert base.selectors == {}

    def test_get_resolver_creates_new(self, temp_selector_file):
        """测试获取选择器解析器(首次创建)"""
        from src.browser.first_edit.base import FirstEditBase

        base = FirstEditBase(selector_path=temp_selector_file)
        mock_page = MagicMock()

        resolver = base._get_resolver(mock_page)

        assert resolver is not None
        assert base._resolver is resolver

    def test_get_resolver_reuses_existing(self, temp_selector_file):
        """测试获取选择器解析器(复用已有)"""
        from src.browser.first_edit.base import FirstEditBase

        base = FirstEditBase(selector_path=temp_selector_file)
        mock_page = MagicMock()

        resolver1 = base._get_resolver(mock_page)
        resolver2 = base._get_resolver(mock_page)

        assert resolver1 is resolver2

    def test_get_resolver_creates_new_for_different_page(self, temp_selector_file):
        """测试不同页面创建新的解析器"""
        from src.browser.first_edit.base import FirstEditBase

        base = FirstEditBase(selector_path=temp_selector_file)
        mock_page1 = MagicMock()
        mock_page2 = MagicMock()

        resolver1 = base._get_resolver(mock_page1)
        resolver2 = base._get_resolver(mock_page2)

        assert resolver1 is not resolver2

    @pytest.mark.asyncio
    async def test_find_visible_element_found(self, temp_selector_file):
        """测试查找可见元素成功"""
        from src.browser.first_edit.base import FirstEditBase

        base = FirstEditBase(selector_path=temp_selector_file)

        # 创建 mock page 和 locator
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.nth = MagicMock(return_value=mock_locator)
        mock_locator.is_visible = AsyncMock(return_value=True)

        mock_page = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)

        result = await base.find_visible_element(
            mock_page,
            ["selector1", "selector2"],
            timeout_ms=1000,
            context_name="test",
        )

        assert result is mock_locator

    @pytest.mark.asyncio
    async def test_find_visible_element_not_found(self, temp_selector_file):
        """测试查找可见元素失败"""
        from src.browser.first_edit.base import FirstEditBase

        base = FirstEditBase(selector_path=temp_selector_file)

        # 创建 mock page 和不可见的 locator
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.nth = MagicMock(return_value=mock_locator)
        mock_locator.is_visible = AsyncMock(return_value=False)

        mock_page = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)

        result = await base.find_visible_element(
            mock_page,
            ["selector1"],
            timeout_ms=1000,
            context_name="test",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_find_visible_element_with_nth(self, temp_selector_file):
        """测试查找第N个元素"""
        from src.browser.first_edit.base import FirstEditBase

        base = FirstEditBase(selector_path=temp_selector_file)

        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=3)  # 有3个元素
        mock_locator.nth = MagicMock(return_value=mock_locator)
        mock_locator.is_visible = AsyncMock(return_value=True)

        mock_page = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)

        result = await base.find_visible_element(
            mock_page,
            ["selector1"],
            timeout_ms=1000,
            context_name="test",
            nth=2,  # 获取第3个元素
        )

        assert result is mock_locator
        mock_locator.nth.assert_called_with(2)

    @pytest.mark.asyncio
    async def test_find_visible_element_nth_out_of_range(self, temp_selector_file):
        """测试第N个元素超出范围"""
        from src.browser.first_edit.base import FirstEditBase

        base = FirstEditBase(selector_path=temp_selector_file)

        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=2)  # 只有2个元素
        mock_locator.nth = MagicMock(return_value=mock_locator)

        mock_page = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)

        result = await base.find_visible_element(
            mock_page,
            ["selector1"],
            timeout_ms=1000,
            context_name="test",
            nth=5,  # 超出范围
        )

        assert result is None


# ============================================================
# FirstEditTitleMixin 测试
# ============================================================
class TestFirstEditTitle:
    """FirstEditTitleMixin 标题操作测试"""

    @pytest.fixture
    def mock_page(self):
        """创建 Mock 页面"""
        page = AsyncMock()

        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.nth = MagicMock(return_value=mock_locator)
        mock_locator.is_visible = AsyncMock(return_value=True)
        mock_locator.input_value = AsyncMock(return_value="原始标题")
        mock_locator.fill = AsyncMock()

        page.locator = MagicMock(return_value=mock_locator)
        page.wait_for_load_state = AsyncMock()

        return page

    @pytest.fixture
    def title_mixin(self, tmp_path):
        """创建 FirstEditTitleMixin 实例"""
        from src.browser.first_edit.title import FirstEditTitleMixin

        selector_config = {
            "first_edit_dialog": {
                "title_input": ["input.title"],
            },
        }
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps(selector_config))

        return FirstEditTitleMixin(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_locate_title_input_success(self, title_mixin, mock_page):
        """测试定位标题输入框成功"""
        result = await title_mixin._locate_title_input(mock_page)

        assert result is not None

    @pytest.mark.asyncio
    async def test_locate_title_input_not_found(self, title_mixin):
        """测试定位标题输入框失败"""
        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=0)

        mock_page.locator = MagicMock(return_value=mock_locator)

        result = await title_mixin._locate_title_input(mock_page)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_original_title_success(self, title_mixin, mock_page):
        """测试获取原始标题成功"""
        result = await title_mixin.get_original_title(mock_page)

        assert result == "原始标题"

    @pytest.mark.asyncio
    async def test_get_original_title_empty(self, title_mixin):
        """测试获取原始标题为空"""
        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=0)

        mock_page.locator = MagicMock(return_value=mock_locator)
        mock_page.wait_for_load_state = AsyncMock()

        result = await title_mixin.get_original_title(mock_page, max_retries=1)

        assert result == ""

    @pytest.mark.asyncio
    async def test_edit_title_success(self, title_mixin, mock_page):
        """测试编辑标题成功"""
        mock_locator = mock_page.locator.return_value
        # 模拟填充后返回新标题
        mock_locator.input_value = AsyncMock(return_value="新标题")

        result = await title_mixin.edit_title(mock_page, "新标题")

        assert result is True
        mock_locator.fill.assert_called_with("新标题")

    @pytest.mark.asyncio
    async def test_edit_title_mismatch(self, title_mixin, mock_page):
        """测试编辑标题后不匹配(重试装饰器会抛出异常)"""
        mock_locator = mock_page.locator.return_value
        # 模拟填充后返回不同的标题
        mock_locator.input_value = AsyncMock(return_value="不同的标题")

        # edit_title 有重试装饰器，返回 False 时会抛出 RuntimeError
        # 注意: RuntimeError 不在 retryable_exceptions 列表中，所以不会重试，直接抛出
        with pytest.raises(RuntimeError, match="edit_title returned False"):
            await title_mixin.edit_title(mock_page, "新标题")

        # 验证调用次数: RuntimeError 不可重试，所以只调用 1 次
        assert mock_locator.fill.call_count == 1

    @pytest.mark.asyncio
    async def test_edit_title_input_not_found(self, title_mixin):
        """测试编辑标题时输入框不存在(重试装饰器会抛出异常)"""
        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=0)

        mock_page.locator = MagicMock(return_value=mock_locator)

        # edit_title 有重试装饰器，返回 False 时会抛出 RuntimeError
        with pytest.raises(RuntimeError, match="edit_title returned False"):
            await title_mixin.edit_title(mock_page, "新标题")

    @pytest.mark.asyncio
    async def test_append_model_to_title_success(self, title_mixin, mock_page):
        """测试追加型号到标题成功"""
        mock_locator = mock_page.locator.return_value
        # 第一次调用返回原始标题，第二次返回拼接后的标题
        mock_locator.input_value = AsyncMock(side_effect=["原始标题", "原始标题 A0001"])

        result = await title_mixin.append_model_to_title(mock_page, "A0001")

        assert result is True
        mock_locator.fill.assert_called_with("原始标题 A0001")

    @pytest.mark.asyncio
    async def test_append_model_to_title_mismatch(self, title_mixin, mock_page):
        """测试追加型号后不匹配(重试装饰器会抛出异常)"""
        mock_locator = mock_page.locator.return_value
        mock_locator.input_value = AsyncMock(side_effect=["原始标题", "错误的标题"])

        # append_model_to_title 有重试装饰器，返回 False 时会抛出 RuntimeError
        with pytest.raises(RuntimeError, match="append_model_to_title returned False"):
            await title_mixin.append_model_to_title(mock_page, "A0001")

    @pytest.mark.asyncio
    async def test_edit_title_with_ai_delegates(self, title_mixin, mock_page):
        """测试 edit_title_with_ai 委托给 append_model_to_title"""
        mock_locator = mock_page.locator.return_value
        mock_locator.input_value = AsyncMock(side_effect=["原始标题", "原始标题 A0002"])

        result = await title_mixin.edit_title_with_ai(
            mock_page,
            product_index=0,
            all_original_titles=["标题1", "标题2"],
            model_number="A0002",
            use_ai=True,
        )

        assert result is True


# ============================================================
# FirstEditWorkflowMixin 测试
# ============================================================
class TestFirstEditWorkflow:
    """FirstEditWorkflowMixin 工作流测试"""

    @pytest.fixture
    def mock_page(self):
        """创建 Mock 页面"""
        page = AsyncMock()
        page.wait_for_load_state = AsyncMock()

        mock_locator = AsyncMock()
        mock_locator.click = AsyncMock()

        page.locator = MagicMock(return_value=mock_locator)

        return page

    @pytest.fixture
    def workflow_mixin(self, tmp_path):
        """创建 workflow mixin 实例"""
        # 需要使用完整的 FirstEditController 因为它组合了所有 mixin
        from src.browser.first_edit.controller import FirstEditController

        selector_config = {
            "first_edit_dialog": {
                "title_input": ["input.title"],
                "navigation": {
                    "basic_info": "text='基本信息'",
                    "logistics": "text='物流信息'",
                },
            },
        }
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps(selector_config))

        return FirstEditController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_complete_first_edit_all_success(self, workflow_mixin, mock_page):
        """测试完整首次编辑流程成功"""
        # Mock 所有方法返回成功
        with (
            patch.object(workflow_mixin, "edit_title", return_value=True),
            patch.object(workflow_mixin, "set_sku_price", return_value=True),
            patch.object(workflow_mixin, "set_sku_stock", return_value=True),
            patch.object(
                workflow_mixin, "set_package_weight_in_logistics", return_value=True
            ),
            patch.object(
                workflow_mixin, "set_package_dimensions_in_logistics", return_value=True
            ),
            patch.object(workflow_mixin, "save_changes", return_value=True),
            patch.object(workflow_mixin, "close_dialog", return_value=True),
        ):
            result = await workflow_mixin.complete_first_edit(
                mock_page,
                title="测试标题",
                price=100.0,
                stock=50,
                weight=5.0,
                dimensions=(80, 60, 40),
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_complete_first_edit_title_fails(self, workflow_mixin, mock_page):
        """测试标题设置失败"""
        with patch.object(workflow_mixin, "edit_title", return_value=False):
            result = await workflow_mixin.complete_first_edit(
                mock_page,
                title="测试标题",
                price=100.0,
                stock=50,
                weight=5.0,
                dimensions=(80, 60, 40),
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_complete_first_edit_price_fails(self, workflow_mixin, mock_page):
        """测试价格设置失败"""
        with (
            patch.object(workflow_mixin, "edit_title", return_value=True),
            patch.object(workflow_mixin, "set_sku_price", return_value=False),
        ):
            result = await workflow_mixin.complete_first_edit(
                mock_page,
                title="测试标题",
                price=100.0,
                stock=50,
                weight=5.0,
                dimensions=(80, 60, 40),
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_complete_first_edit_stock_fails(self, workflow_mixin, mock_page):
        """测试库存设置失败"""
        with (
            patch.object(workflow_mixin, "edit_title", return_value=True),
            patch.object(workflow_mixin, "set_sku_price", return_value=True),
            patch.object(workflow_mixin, "set_sku_stock", return_value=False),
        ):
            result = await workflow_mixin.complete_first_edit(
                mock_page,
                title="测试标题",
                price=100.0,
                stock=50,
                weight=5.0,
                dimensions=(80, 60, 40),
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_complete_first_edit_weight_fails_continues(
        self, workflow_mixin, mock_page
    ):
        """测试重量设置失败但继续执行"""
        with (
            patch.object(workflow_mixin, "edit_title", return_value=True),
            patch.object(workflow_mixin, "set_sku_price", return_value=True),
            patch.object(workflow_mixin, "set_sku_stock", return_value=True),
            patch.object(
                workflow_mixin, "set_package_weight_in_logistics", return_value=False
            ),
            patch.object(
                workflow_mixin, "set_package_dimensions_in_logistics", return_value=True
            ),
            patch.object(workflow_mixin, "save_changes", return_value=True),
            patch.object(workflow_mixin, "close_dialog", return_value=True),
        ):
            result = await workflow_mixin.complete_first_edit(
                mock_page,
                title="测试标题",
                price=100.0,
                stock=50,
                weight=5.0,
                dimensions=(80, 60, 40),
            )

            # 重量设置失败不影响整体流程
            assert result is True

    @pytest.mark.asyncio
    async def test_complete_first_edit_dimensions_fails_continues(
        self, workflow_mixin, mock_page
    ):
        """测试尺寸设置失败但继续执行"""
        with (
            patch.object(workflow_mixin, "edit_title", return_value=True),
            patch.object(workflow_mixin, "set_sku_price", return_value=True),
            patch.object(workflow_mixin, "set_sku_stock", return_value=True),
            patch.object(
                workflow_mixin, "set_package_weight_in_logistics", return_value=True
            ),
            patch.object(
                workflow_mixin, "set_package_dimensions_in_logistics", return_value=False
            ),
            patch.object(workflow_mixin, "save_changes", return_value=True),
            patch.object(workflow_mixin, "close_dialog", return_value=True),
        ):
            result = await workflow_mixin.complete_first_edit(
                mock_page,
                title="测试标题",
                price=100.0,
                stock=50,
                weight=5.0,
                dimensions=(80, 60, 40),
            )

            # 尺寸设置失败不影响整体流程
            assert result is True

    @pytest.mark.asyncio
    async def test_complete_first_edit_save_fails(self, workflow_mixin, mock_page):
        """测试保存失败"""
        with (
            patch.object(workflow_mixin, "edit_title", return_value=True),
            patch.object(workflow_mixin, "set_sku_price", return_value=True),
            patch.object(workflow_mixin, "set_sku_stock", return_value=True),
            patch.object(
                workflow_mixin, "set_package_weight_in_logistics", return_value=True
            ),
            patch.object(
                workflow_mixin, "set_package_dimensions_in_logistics", return_value=True
            ),
            patch.object(workflow_mixin, "save_changes", return_value=False),
        ):
            result = await workflow_mixin.complete_first_edit(
                mock_page,
                title="测试标题",
                price=100.0,
                stock=50,
                weight=5.0,
                dimensions=(80, 60, 40),
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_complete_first_edit_close_fails_continues(
        self, workflow_mixin, mock_page
    ):
        """测试关闭弹窗失败但继续执行"""
        with (
            patch.object(workflow_mixin, "edit_title", return_value=True),
            patch.object(workflow_mixin, "set_sku_price", return_value=True),
            patch.object(workflow_mixin, "set_sku_stock", return_value=True),
            patch.object(
                workflow_mixin, "set_package_weight_in_logistics", return_value=True
            ),
            patch.object(
                workflow_mixin, "set_package_dimensions_in_logistics", return_value=True
            ),
            patch.object(workflow_mixin, "save_changes", return_value=True),
            patch.object(workflow_mixin, "close_dialog", return_value=False),
        ):
            result = await workflow_mixin.complete_first_edit(
                mock_page,
                title="测试标题",
                price=100.0,
                stock=50,
                weight=5.0,
                dimensions=(80, 60, 40),
            )

            # 关闭弹窗失败不影响整体流程
            assert result is True

    @pytest.mark.asyncio
    async def test_complete_first_edit_exception_handling(
        self, workflow_mixin, mock_page
    ):
        """测试异常处理"""
        with patch.object(
            workflow_mixin, "edit_title", side_effect=Exception("Test error")
        ):
            result = await workflow_mixin.complete_first_edit(
                mock_page,
                title="测试标题",
                price=100.0,
                stock=50,
                weight=5.0,
                dimensions=(80, 60, 40),
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_complete_first_edit_dimensions_value_error(
        self, workflow_mixin, mock_page
    ):
        """测试尺寸验证错误"""
        with (
            patch.object(workflow_mixin, "edit_title", return_value=True),
            patch.object(workflow_mixin, "set_sku_price", return_value=True),
            patch.object(workflow_mixin, "set_sku_stock", return_value=True),
            patch.object(
                workflow_mixin, "set_package_weight_in_logistics", return_value=True
            ),
            patch.object(
                workflow_mixin,
                "set_package_dimensions_in_logistics",
                side_effect=ValueError("Invalid dimensions"),
            ),
            patch.object(workflow_mixin, "save_changes", return_value=True),
            patch.object(workflow_mixin, "close_dialog", return_value=True),
        ):
            result = await workflow_mixin.complete_first_edit(
                mock_page,
                title="测试标题",
                price=100.0,
                stock=50,
                weight=5.0,
                dimensions=(80, 60, 40),
            )

            # ValueError 被捕获，流程继续
            assert result is True


# ============================================================
# FirstEditController 集成测试
# ============================================================
class TestFirstEditControllerIntegration:
    """FirstEditController 集成测试"""

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.first_edit.controller import FirstEditController

        selector_config = {
            "first_edit_dialog": {
                "title_input": ["input.title"],
                "navigation": {},
            },
        }
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps(selector_config))

        return FirstEditController(selector_path=str(selector_file))

    def test_controller_inherits_all_mixins(self, controller):
        """测试控制器继承所有 Mixin"""
        # 检查是否有各个 Mixin 的方法
        assert hasattr(controller, "edit_title")  # TitleMixin
        assert hasattr(controller, "set_sku_price")  # SkuMixin
        assert hasattr(controller, "save_changes")  # DialogMixin
        assert hasattr(controller, "complete_first_edit")  # WorkflowMixin
        assert hasattr(controller, "find_visible_element")  # Base

    def test_controller_has_selectors(self, controller):
        """测试控制器有选择器配置"""
        assert controller.selectors is not None
        assert "first_edit_dialog" in controller.selectors


# ============================================================
# Title Input Selectors 测试
# ============================================================
class TestTitleInputSelectors:
    """测试标题输入框选择器列表"""

    def test_title_input_selectors_defined(self):
        """测试标题选择器列表已定义"""
        from src.browser.first_edit.title import TITLE_INPUT_SELECTORS

        assert len(TITLE_INPUT_SELECTORS) >= 3
        assert any("产品标题" in s for s in TITLE_INPUT_SELECTORS)

    def test_title_input_selectors_format(self):
        """测试标题选择器格式正确"""
        from src.browser.first_edit.title import TITLE_INPUT_SELECTORS

        for selector in TITLE_INPUT_SELECTORS:
            assert isinstance(selector, str)
            assert len(selector) > 0


# ============================================================
# TIMEOUTS 常量测试
# ============================================================
class TestTimeouts:
    """测试超时常量"""

    def test_timeouts_defined(self):
        """测试超时常量已定义"""
        from src.browser.first_edit.base import TIMEOUTS

        assert hasattr(TIMEOUTS, "FAST")
        assert hasattr(TIMEOUTS, "NORMAL")
        assert hasattr(TIMEOUTS, "SLOW")

    def test_timeouts_values(self):
        """测试超时值合理"""
        from src.browser.first_edit.base import TIMEOUTS

        assert TIMEOUTS.FAST < TIMEOUTS.NORMAL
        assert TIMEOUTS.NORMAL < TIMEOUTS.SLOW
        assert TIMEOUTS.FAST > 0
