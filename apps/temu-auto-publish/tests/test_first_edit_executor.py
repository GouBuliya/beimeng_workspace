"""
@PURPOSE: first_edit_executor.py 单元测试
@OUTLINE:
  - TestFirstEditPayload: 数据模型测试
  - TestFirstEditExecutorInit: 初始化测试
  - TestFirstEditExecutorApply: apply 方法测试
  - TestFirstEditExecutorFillWithRetry: 重试逻辑测试
  - TestFirstEditExecutorEnsureInjector: 注入脚本测试
@DEPENDENCIES:
  - 内部: browser.first_edit_executor
  - 外部: pytest, pytest-asyncio
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import sys

import pytest

# 在导入 first_edit_executor 之前，先 mock tenacity
mock_tenacity = MagicMock()


class MockRetryError(Exception):
    """Mock RetryError for testing"""

    def __init__(self, last_attempt=None):
        self.last_attempt = last_attempt


mock_tenacity.RetryError = MockRetryError
mock_tenacity.retry = lambda **kwargs: lambda f: f  # 装饰器返回原函数
mock_tenacity.stop_after_attempt = MagicMock(return_value=MagicMock())
mock_tenacity.wait_exponential = MagicMock(return_value=MagicMock())
sys.modules["tenacity"] = mock_tenacity

from src.browser.first_edit_executor import FirstEditExecutor, FirstEditPayload

RetryError = MockRetryError


# ============================================================
# FirstEditPayload 测试
# ============================================================
class TestFirstEditPayload:
    """FirstEditPayload 数据模型测试"""

    def test_basic_creation(self):
        """测试基础创建"""
        payload = FirstEditPayload(
            title="Test Title",
            product_number="PN123",
            price=99.0,
            supply_price=50.0,
            source_price=30.0,
            stock=100,
            weight_g=500,
            length_cm=10,
            width_cm=20,
            height_cm=15,
        )

        assert payload.title == "Test Title"
        assert payload.product_number == "PN123"
        assert payload.price == 99.0
        assert payload.stock == 100

    def test_default_values(self):
        """测试默认值"""
        payload = FirstEditPayload(
            title="Test",
            product_number="PN",
            price=10.0,
            supply_price=5.0,
            source_price=3.0,
            stock=10,
            weight_g=100,
            length_cm=5,
            width_cm=5,
            height_cm=5,
        )

        assert payload.supplier_link == ""
        assert payload.specs is None
        assert payload.variants is None

    def test_with_optional_fields(self):
        """测试可选字段"""
        payload = FirstEditPayload(
            title="Test",
            product_number="PN",
            price=10.0,
            supply_price=5.0,
            source_price=3.0,
            stock=10,
            weight_g=100,
            length_cm=5,
            width_cm=5,
            height_cm=5,
            supplier_link="https://example.com",
            specs=[{"name": "Color", "value": "Red"}],
            variants=[{"sku": "SKU1", "price": 10.0}],
        )

        assert payload.supplier_link == "https://example.com"
        assert len(payload.specs) == 1
        assert len(payload.variants) == 1

    def test_to_dict_basic(self):
        """测试 to_dict 基础转换"""
        payload = FirstEditPayload(
            title="Test",
            product_number="PN",
            price=10.0,
            supply_price=5.0,
            source_price=3.0,
            stock=10,
            weight_g=100,
            length_cm=5,
            width_cm=8,
            height_cm=12,
        )

        result = payload.to_dict()

        assert result["title"] == "Test"
        assert result["price"] == 10.0
        assert result["specs"] == []
        assert result["variants"] == []
        assert result["dimensions_cm"] == {"length": 5, "width": 8, "height": 12}

    def test_to_dict_with_specs_and_variants(self):
        """测试 to_dict 包含 specs 和 variants"""
        specs = [{"name": "Size", "value": "L"}]
        variants = [{"sku": "V1"}]
        payload = FirstEditPayload(
            title="Test",
            product_number="PN",
            price=10.0,
            supply_price=5.0,
            source_price=3.0,
            stock=10,
            weight_g=100,
            length_cm=5,
            width_cm=5,
            height_cm=5,
            specs=specs,
            variants=variants,
        )

        result = payload.to_dict()

        assert result["specs"] == specs
        assert result["variants"] == variants

    def test_slots_enabled(self):
        """测试 slots 已启用"""
        payload = FirstEditPayload(
            title="Test",
            product_number="PN",
            price=10.0,
            supply_price=5.0,
            source_price=3.0,
            stock=10,
            weight_g=100,
            length_cm=5,
            width_cm=5,
            height_cm=5,
        )

        with pytest.raises(AttributeError):
            payload.new_attr = "value"


# ============================================================
# FirstEditExecutor 初始化测试
# ============================================================
class TestFirstEditExecutorInit:
    """FirstEditExecutor 初始化测试"""

    @pytest.fixture
    def mock_controller(self):
        """创建模拟 controller"""
        return MagicMock()

    def test_init_with_defaults(self, mock_controller):
        """测试默认参数初始化"""
        executor = FirstEditExecutor(mock_controller)

        assert executor._controller is mock_controller
        assert executor._injector_loaded is False
        assert executor._injector_path.name == "first_edit_inject.js"
        assert "debug" in str(executor._debug_dir)

    def test_init_with_custom_paths(self, mock_controller, tmp_path):
        """测试自定义路径初始化"""
        injector = tmp_path / "custom_inject.js"
        debug_dir = tmp_path / "custom_debug"

        executor = FirstEditExecutor(
            mock_controller,
            injector_path=injector,
            debug_dir=debug_dir,
        )

        assert executor._injector_path == injector
        assert executor._debug_dir == debug_dir


# ============================================================
# FirstEditExecutor.apply 测试
# ============================================================
class TestFirstEditExecutorApply:
    """FirstEditExecutor.apply 方法测试"""

    @pytest.fixture
    def mock_controller(self):
        """创建模拟 controller"""
        controller = MagicMock()
        controller.wait_for_dialog = AsyncMock()
        controller.save_changes = AsyncMock(return_value=True)
        controller.close_dialog = AsyncMock()
        return controller

    @pytest.fixture
    def mock_page(self):
        """创建模拟 Page"""
        page = MagicMock()
        page.evaluate = AsyncMock(return_value={"success": True})
        page.add_script_tag = AsyncMock()
        page.pause = AsyncMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html></html>")
        return page

    @pytest.fixture
    def sample_payload(self):
        """创建示例 payload"""
        return FirstEditPayload(
            title="Test Product",
            product_number="PN123",
            price=99.0,
            supply_price=50.0,
            source_price=30.0,
            stock=100,
            weight_g=500,
            length_cm=10,
            width_cm=20,
            height_cm=15,
        )

    @pytest.fixture
    def executor_with_mock_injector(self, mock_controller, tmp_path):
        """创建带 mock 注入脚本的 executor"""
        injector = tmp_path / "inject.js"
        injector.write_text("// mock script")
        return FirstEditExecutor(
            mock_controller,
            injector_path=injector,
            debug_dir=tmp_path / "debug",
        )

    @pytest.mark.asyncio
    async def test_apply_success(
        self, mock_controller, mock_page, sample_payload, executor_with_mock_injector
    ):
        """测试成功应用"""
        result = await executor_with_mock_injector.apply(mock_page, sample_payload)

        assert result is True
        mock_controller.wait_for_dialog.assert_called_once()
        mock_controller.save_changes.assert_called_once()
        mock_controller.close_dialog.assert_called()

    @pytest.mark.asyncio
    async def test_apply_with_post_fill_hook_success(
        self, mock_controller, mock_page, sample_payload, executor_with_mock_injector
    ):
        """测试带 post_fill_hook 成功"""
        hook = AsyncMock(return_value=True)

        result = await executor_with_mock_injector.apply(
            mock_page, sample_payload, post_fill_hook=hook
        )

        assert result is True
        hook.assert_called_once_with(mock_page)

    @pytest.mark.asyncio
    async def test_apply_with_post_fill_hook_failure(
        self, mock_controller, mock_page, sample_payload, executor_with_mock_injector
    ):
        """测试 post_fill_hook 返回失败但继续执行"""
        hook = AsyncMock(return_value=False)

        result = await executor_with_mock_injector.apply(
            mock_page, sample_payload, post_fill_hook=hook
        )

        # hook 失败不影响整体结果
        assert result is True

    @pytest.mark.asyncio
    async def test_apply_with_post_fill_hook_exception(
        self, mock_controller, mock_page, sample_payload, executor_with_mock_injector
    ):
        """测试 post_fill_hook 抛出异常"""
        hook = AsyncMock(side_effect=Exception("hook error"))

        result = await executor_with_mock_injector.apply(
            mock_page, sample_payload, post_fill_hook=hook
        )

        # hook 异常不影响整体结果
        assert result is True

    @pytest.mark.asyncio
    async def test_apply_injection_failure(
        self, mock_controller, mock_page, sample_payload, executor_with_mock_injector
    ):
        """测试注入失败"""
        mock_page.evaluate = AsyncMock(return_value={"success": False, "error": "test"})

        result = await executor_with_mock_injector.apply(mock_page, sample_payload)

        assert result is False
        mock_controller.close_dialog.assert_called()

    @pytest.mark.asyncio
    async def test_apply_save_failure(
        self, mock_controller, mock_page, sample_payload, executor_with_mock_injector
    ):
        """测试保存失败"""
        mock_controller.save_changes = AsyncMock(return_value=False)

        result = await executor_with_mock_injector.apply(mock_page, sample_payload)

        assert result is False
        mock_controller.close_dialog.assert_called()

    @pytest.mark.asyncio
    async def test_apply_retry_error(
        self, mock_controller, mock_page, sample_payload, executor_with_mock_injector
    ):
        """测试重试错误"""
        # 模拟 _fill_with_retry 抛出 RetryError
        with patch.object(
            executor_with_mock_injector,
            "_fill_with_retry",
            AsyncMock(side_effect=RetryError(None)),
        ):
            result = await executor_with_mock_injector.apply(mock_page, sample_payload)

        assert result is False
        mock_controller.close_dialog.assert_called()

    @pytest.mark.asyncio
    async def test_apply_general_exception(
        self, mock_controller, mock_page, sample_payload, executor_with_mock_injector
    ):
        """测试一般异常"""
        with patch.object(
            executor_with_mock_injector,
            "_fill_with_retry",
            AsyncMock(side_effect=RuntimeError("unexpected error")),
        ):
            result = await executor_with_mock_injector.apply(mock_page, sample_payload)

        assert result is False
        mock_controller.close_dialog.assert_called()


# ============================================================
# FirstEditExecutor._ensure_injector 测试
# ============================================================
class TestFirstEditExecutorEnsureInjector:
    """_ensure_injector 方法测试"""

    @pytest.fixture
    def mock_controller(self):
        return MagicMock()

    @pytest.fixture
    def mock_page(self):
        page = MagicMock()
        page.add_script_tag = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_ensure_injector_success(self, mock_controller, mock_page, tmp_path):
        """测试成功注入脚本"""
        injector = tmp_path / "inject.js"
        injector.write_text("console.log('injected')")

        executor = FirstEditExecutor(mock_controller, injector_path=injector)
        await executor._ensure_injector(mock_page)

        assert executor._injector_loaded is True
        mock_page.add_script_tag.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_injector_file_not_found(self, mock_controller, mock_page, tmp_path):
        """测试注入脚本不存在"""
        injector = tmp_path / "nonexistent.js"

        executor = FirstEditExecutor(mock_controller, injector_path=injector)

        with pytest.raises(FileNotFoundError):
            await executor._ensure_injector(mock_page)


# ============================================================
# 边界情况测试
# ============================================================
class TestFirstEditExecutorEdgeCases:
    """边界情况测试"""

    def test_payload_with_zero_values(self):
        """测试零值 payload"""
        payload = FirstEditPayload(
            title="",
            product_number="",
            price=0.0,
            supply_price=0.0,
            source_price=0.0,
            stock=0,
            weight_g=0,
            length_cm=0,
            width_cm=0,
            height_cm=0,
        )

        result = payload.to_dict()

        assert result["price"] == 0.0
        assert result["stock"] == 0
        assert result["dimensions_cm"]["length"] == 0

    def test_payload_with_unicode(self):
        """测试中文标题"""
        payload = FirstEditPayload(
            title="测试产品🎉",
            product_number="PN中文",
            price=99.99,
            supply_price=50.0,
            source_price=30.0,
            stock=100,
            weight_g=500,
            length_cm=10,
            width_cm=20,
            height_cm=15,
        )

        result = payload.to_dict()

        assert result["title"] == "测试产品🎉"
        assert result["product_number"] == "PN中文"

    def test_payload_with_large_values(self):
        """测试大数值"""
        payload = FirstEditPayload(
            title="Large Product",
            product_number="PN999999",
            price=999999.99,
            supply_price=500000.0,
            source_price=300000.0,
            stock=1000000,
            weight_g=100000,
            length_cm=1000,
            width_cm=1000,
            height_cm=1000,
        )

        result = payload.to_dict()

        assert result["price"] == 999999.99
        assert result["stock"] == 1000000
