"""
@PURPOSE: batch_edit_helpers 模块的完整单元测试
@OUTLINE:
  - TestRetryOnFailure: retry_on_failure 装饰器测试
  - TestPerformanceMonitor: performance_monitor 上下文管理器测试
  - TestTakeErrorScreenshot: take_error_screenshot 函数测试
  - TestEnhancedErrorHandler: enhanced_error_handler 装饰器测试
  - TestStepValidator: StepValidator 类测试
  - TestGenericSelectors: GenericSelectors 类测试
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.utils.batch_edit_helpers
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest


# ==================== retry_on_failure 装饰器测试 ====================
class TestRetryOnFailure:
    """retry_on_failure 装饰器测试"""

    @pytest.mark.asyncio
    async def test_success_first_try(self):
        """测试第一次尝试成功"""
        from src.utils.batch_edit_helpers import retry_on_failure

        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self):
        """测试重试后成功"""
        from src.utils.batch_edit_helpers import retry_on_failure

        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01, backoff=1.0)
        async def retry_success_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"

        result = await retry_success_func()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_all_retries_fail(self):
        """测试所有重试都失败"""
        from src.utils.batch_edit_helpers import retry_on_failure

        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01, backoff=1.0)
        async def always_fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent error")

        with pytest.raises(ValueError, match="Permanent error"):
            await always_fail_func()

        assert call_count == 3

    @pytest.mark.asyncio
    async def test_specific_exception_types(self):
        """测试只捕获特定异常类型"""
        from src.utils.batch_edit_helpers import retry_on_failure

        call_count = 0

        @retry_on_failure(max_retries=3, delay=0.01, exceptions=(ValueError,))
        async def specific_exception_func():
            nonlocal call_count
            call_count += 1
            raise TypeError("Not caught")

        with pytest.raises(TypeError):
            await specific_exception_func()

        # TypeError 不会重试,只调用一次
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """测试指数退避"""
        from src.utils.batch_edit_helpers import retry_on_failure

        start_time = time.time()
        call_times = []

        @retry_on_failure(max_retries=3, delay=0.05, backoff=2.0)
        async def backoff_func():
            call_times.append(time.time() - start_time)
            if len(call_times) < 3:
                raise ValueError("Retry needed")
            return "done"

        await backoff_func()

        # 检查调用间隔大致符合退避策略
        assert len(call_times) == 3
        # 第二次调用应该在 ~0.05s 后
        # 第三次调用应该在 ~0.15s 后 (0.05 + 0.1)
        assert call_times[1] - call_times[0] >= 0.04  # 允许一些误差
        assert call_times[2] - call_times[1] >= 0.08

    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self):
        """测试保留函数元数据"""
        from src.utils.batch_edit_helpers import retry_on_failure

        @retry_on_failure(max_retries=2)
        async def documented_func():
            """This is a docstring."""
            return True

        assert documented_func.__name__ == "documented_func"
        assert "docstring" in documented_func.__doc__


# ==================== performance_monitor 上下文管理器测试 ====================
class TestPerformanceMonitor:
    """performance_monitor 上下文管理器测试"""

    @pytest.mark.asyncio
    async def test_normal_execution(self):
        """测试正常执行"""
        from src.utils.batch_edit_helpers import performance_monitor

        async with performance_monitor("测试步骤", warn_threshold=10.0):
            await asyncio.sleep(0.01)

        # 应该正常完成,不抛出异常

    @pytest.mark.asyncio
    async def test_slow_execution_warning(self):
        """测试慢执行警告"""
        from src.utils.batch_edit_helpers import performance_monitor

        # 设置很低的阈值来触发警告
        async with performance_monitor("慢步骤", warn_threshold=0.001):
            await asyncio.sleep(0.01)

        # 应该记录警告日志但不抛出异常

    @pytest.mark.asyncio
    async def test_exception_in_context(self):
        """测试上下文中的异常"""
        from src.utils.batch_edit_helpers import performance_monitor

        with pytest.raises(ValueError):
            async with performance_monitor("异常步骤"):
                raise ValueError("Test error")

        # 即使有异常,finally 块也应该执行记录耗时


# ==================== take_error_screenshot 函数测试 ====================
class TestTakeErrorScreenshot:
    """take_error_screenshot 函数测试"""

    @pytest.mark.asyncio
    async def test_screenshot_success(self):
        """测试截图成功"""
        from src.utils.batch_edit_helpers import take_error_screenshot

        page = MagicMock()
        page.screenshot = AsyncMock()

        result = await take_error_screenshot(page, "test_step")

        assert result is not None
        assert "error_test_step" in result
        assert result.endswith(".png")
        page.screenshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_screenshot_failure(self):
        """测试截图失败"""
        from src.utils.batch_edit_helpers import take_error_screenshot

        page = MagicMock()
        page.screenshot = AsyncMock(side_effect=Exception("Screenshot failed"))

        result = await take_error_screenshot(page, "test_step")

        assert result is None

    @pytest.mark.asyncio
    async def test_step_name_sanitization(self):
        """测试步骤名称清理"""
        from src.utils.batch_edit_helpers import take_error_screenshot

        page = MagicMock()
        page.screenshot = AsyncMock()

        result = await take_error_screenshot(page, "步骤 3: 类目属性")

        assert result is not None
        assert " " not in result or "_" in result  # 空格应被替换
        assert ":" not in result or "_" in result  # 冒号应被替换


# ==================== enhanced_error_handler 装饰器测试 ====================
class TestEnhancedErrorHandler:
    """enhanced_error_handler 装饰器测试"""

    @pytest.mark.asyncio
    async def test_success_execution(self):
        """测试成功执行"""
        from src.utils.batch_edit_helpers import enhanced_error_handler

        @enhanced_error_handler("测试步骤")
        async def success_func(page):
            return "success"

        page = MagicMock()
        result = await success_func(page)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self):
        """测试超时错误处理"""
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from src.utils.batch_edit_helpers import enhanced_error_handler

        @enhanced_error_handler("超时步骤")
        async def timeout_func(page):
            raise PlaywrightTimeout("Element not found")

        page = MagicMock()
        page.screenshot = AsyncMock()

        with pytest.raises(PlaywrightTimeout):
            await timeout_func(page)

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """测试网络错误处理"""
        from src.utils.batch_edit_helpers import enhanced_error_handler

        @enhanced_error_handler("网络步骤")
        async def network_func(page):
            raise ConnectionError("Network failure")

        page = MagicMock()

        with pytest.raises(ConnectionError):
            await network_func(page)

    @pytest.mark.asyncio
    async def test_general_exception_handling(self):
        """测试一般异常处理"""
        from src.utils.batch_edit_helpers import enhanced_error_handler

        @enhanced_error_handler("一般步骤")
        async def general_error_func(page):
            raise RuntimeError("Something went wrong")

        page = MagicMock()
        page.screenshot = AsyncMock()

        with pytest.raises(RuntimeError):
            await general_error_func(page)

    @pytest.mark.asyncio
    async def test_page_from_kwargs(self):
        """测试从 kwargs 获取 page"""
        from src.utils.batch_edit_helpers import enhanced_error_handler

        @enhanced_error_handler("kwargs步骤")
        async def kwargs_func(**kwargs):
            raise ValueError("Test error")

        page = MagicMock()
        page.screenshot = AsyncMock()

        with pytest.raises(ValueError):
            await kwargs_func(page=page)

    @pytest.mark.asyncio
    async def test_no_page_available(self):
        """测试无 page 参数"""
        from src.utils.batch_edit_helpers import enhanced_error_handler

        @enhanced_error_handler("无page步骤")
        async def no_page_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await no_page_func()


# ==================== StepValidator 类测试 ====================
class TestStepValidator:
    """StepValidator 类测试"""

    @pytest.mark.asyncio
    async def test_check_page_loaded_success(self):
        """测试页面加载成功"""
        from src.utils.batch_edit_helpers import StepValidator

        page = MagicMock()
        page.wait_for_load_state = AsyncMock()

        result = await StepValidator.check_page_loaded(page)

        assert result is True
        page.wait_for_load_state.assert_called_with("domcontentloaded", timeout=5000)

    @pytest.mark.asyncio
    async def test_check_page_loaded_timeout(self):
        """测试页面加载超时"""
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from src.utils.batch_edit_helpers import StepValidator

        page = MagicMock()
        page.wait_for_load_state = AsyncMock(side_effect=PlaywrightTimeout("Timeout"))

        result = await StepValidator.check_page_loaded(page)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_element_visible_success(self):
        """测试元素可见"""
        from src.utils.batch_edit_helpers import StepValidator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.wait_for = AsyncMock()
        page.locator.return_value.first = mock_element

        result = await StepValidator.check_element_visible(page, ".button")

        assert result is True
        mock_element.wait_for.assert_called_with(state="visible", timeout=5000)

    @pytest.mark.asyncio
    async def test_check_element_visible_timeout(self):
        """测试元素不可见超时"""
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from src.utils.batch_edit_helpers import StepValidator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.wait_for = AsyncMock(side_effect=PlaywrightTimeout("Timeout"))
        page.locator.return_value.first = mock_element

        result = await StepValidator.check_element_visible(page, ".hidden")

        assert result is False

    @pytest.mark.asyncio
    async def test_check_element_count_match(self):
        """测试元素数量匹配"""
        from src.utils.batch_edit_helpers import StepValidator

        page = MagicMock()
        page.locator.return_value.count = AsyncMock(return_value=5)

        result = await StepValidator.check_element_count(page, ".item", 5)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_element_count_mismatch(self):
        """测试元素数量不匹配"""
        from src.utils.batch_edit_helpers import StepValidator

        page = MagicMock()
        page.locator.return_value.count = AsyncMock(return_value=3)

        result = await StepValidator.check_element_count(page, ".item", 5)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_element_count_with_description(self):
        """测试带描述的元素数量检查"""
        from src.utils.batch_edit_helpers import StepValidator

        page = MagicMock()
        page.locator.return_value.count = AsyncMock(return_value=10)

        result = await StepValidator.check_element_count(page, ".product", 10, description="商品")

        assert result is True


# ==================== GenericSelectors 类测试 ====================
class TestGenericSelectors:
    """GenericSelectors 类测试"""

    def test_button_selectors(self):
        """测试按钮选择器生成"""
        from src.utils.batch_edit_helpers import GenericSelectors

        selectors = GenericSelectors.button("提交")

        assert isinstance(selectors, list)
        assert len(selectors) >= 3
        assert any("提交" in s for s in selectors)
        assert any("button" in s for s in selectors)

    def test_input_selectors(self):
        """测试输入框选择器生成"""
        from src.utils.batch_edit_helpers import GenericSelectors

        selectors = GenericSelectors.input("用户名")

        assert isinstance(selectors, list)
        assert len(selectors) >= 2
        assert any("用户名" in s for s in selectors)
        assert any("input" in s or "textarea" in s for s in selectors)

    def test_select_selectors(self):
        """测试下拉框选择器生成"""
        from src.utils.batch_edit_helpers import GenericSelectors

        selectors = GenericSelectors.select("类别")

        assert isinstance(selectors, list)
        assert len(selectors) >= 2
        assert any("类别" in s for s in selectors)

    def test_checkbox_selectors_with_keyword(self):
        """测试带关键词的复选框选择器"""
        from src.utils.batch_edit_helpers import GenericSelectors

        selectors = GenericSelectors.checkbox("同意")

        assert isinstance(selectors, list)
        assert len(selectors) >= 2
        assert any("同意" in s for s in selectors)
        assert any("checkbox" in s for s in selectors)

    def test_checkbox_selectors_without_keyword(self):
        """测试不带关键词的复选框选择器"""
        from src.utils.batch_edit_helpers import GenericSelectors

        selectors = GenericSelectors.checkbox()

        assert isinstance(selectors, list)
        assert len(selectors) >= 1
        assert any("checkbox" in s for s in selectors)

    @pytest.mark.asyncio
    async def test_try_click_with_fallbacks_success(self):
        """测试 fallback 点击成功"""
        from src.utils.batch_edit_helpers import GenericSelectors

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.click = AsyncMock()
        page.locator.return_value.first = mock_element

        selectors = [".btn1", ".btn2", ".btn3"]
        result = await GenericSelectors.try_click_with_fallbacks(page, selectors, "按钮")

        assert result is True
        mock_element.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_click_with_fallbacks_second_selector(self):
        """测试使用第二个选择器成功"""
        from src.utils.batch_edit_helpers import GenericSelectors

        page = MagicMock()

        # 第一个选择器不可见
        mock_element1 = MagicMock()
        mock_element1.is_visible = AsyncMock(return_value=False)

        # 第二个选择器可见
        mock_element2 = MagicMock()
        mock_element2.is_visible = AsyncMock(return_value=True)
        mock_element2.click = AsyncMock()

        page.locator.return_value.first = mock_element1

        def locator_side_effect(selector):
            mock = MagicMock()
            if selector == ".btn1":
                mock.first = mock_element1
            else:
                mock.first = mock_element2
            return mock

        page.locator.side_effect = locator_side_effect

        selectors = [".btn1", ".btn2"]
        result = await GenericSelectors.try_click_with_fallbacks(page, selectors, "按钮")

        assert result is True
        mock_element2.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_click_with_fallbacks_all_fail(self):
        """测试所有 fallback 都失败"""
        from src.utils.batch_edit_helpers import GenericSelectors

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(return_value=False)
        page.locator.return_value.first = mock_element

        selectors = [".btn1", ".btn2"]
        result = await GenericSelectors.try_click_with_fallbacks(
            page, selectors, "按钮", timeout=100
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_try_click_with_fallbacks_exception(self):
        """测试点击时异常"""
        from src.utils.batch_edit_helpers import GenericSelectors

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.is_visible = AsyncMock(side_effect=Exception("Error"))
        page.locator.return_value.first = mock_element

        selectors = [".btn1"]
        result = await GenericSelectors.try_click_with_fallbacks(
            page, selectors, "按钮", timeout=100
        )

        assert result is False


# ==================== 模块导出测试 ====================
class TestModuleExports:
    """模块导出测试"""

    def test_all_exports_available(self):
        """测试所有导出可用"""
        from src.utils.batch_edit_helpers import (
            GenericSelectors,
            StepValidator,
            enhanced_error_handler,
            performance_monitor,
            retry_on_failure,
            take_error_screenshot,
        )

        assert callable(retry_on_failure)
        assert callable(performance_monitor)
        assert callable(enhanced_error_handler)
        assert callable(take_error_screenshot)
        assert StepValidator is not None
        assert GenericSelectors is not None

    def test_all_list_complete(self):
        """测试 __all__ 列表完整"""
        from src.utils import batch_edit_helpers

        expected = [
            "retry_on_failure",
            "performance_monitor",
            "enhanced_error_handler",
            "take_error_screenshot",
            "StepValidator",
            "GenericSelectors",
        ]

        for name in expected:
            assert name in batch_edit_helpers.__all__
