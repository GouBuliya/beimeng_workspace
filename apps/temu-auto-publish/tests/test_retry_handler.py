"""
@PURPOSE: 测试 RetryHandler 重试处理器
@OUTLINE:
  - TestRetryableErrors: 测试可重试错误类
  - TestNonRetryableErrors: 测试不可重试错误类
  - TestRetryConfig: 测试重试配置
  - TestRetryHandler: 测试重试处理器主类
  - TestRetryWithBackoffDecorator: 测试重试装饰器
  - TestCreateRetryHandler: 测试便捷创建函数
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.core.retry_handler
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.retry_handler import (
    ConfigurationError,
    ElementNotFoundError,
    NetworkError,
    NonRetryableError,
    RetryableError,
    RetryConfig,
    RetryHandler,
    TimeoutError,
    ValidationError,
    create_retry_handler,
    retry_with_backoff,
)


class TestRetryableErrors:
    """测试可重试错误类"""

    def test_retryable_error_base(self):
        """测试可重试错误基类"""
        error = RetryableError("Base retryable error")
        assert isinstance(error, Exception)
        assert str(error) == "Base retryable error"

    def test_network_error(self):
        """测试网络错误"""
        error = NetworkError("Connection refused")
        assert isinstance(error, RetryableError)
        assert isinstance(error, Exception)

    def test_element_not_found_error(self):
        """测试元素未找到错误"""
        error = ElementNotFoundError("Button not found")
        assert isinstance(error, RetryableError)

    def test_timeout_error(self):
        """测试超时错误"""
        error = TimeoutError("Operation timed out")
        assert isinstance(error, RetryableError)


class TestNonRetryableErrors:
    """测试不可重试错误类"""

    def test_non_retryable_error_base(self):
        """测试不可重试错误基类"""
        error = NonRetryableError("Fatal error")
        assert isinstance(error, Exception)

    def test_validation_error(self):
        """测试验证错误"""
        error = ValidationError("Invalid input")
        assert isinstance(error, NonRetryableError)
        assert not isinstance(error, RetryableError)

    def test_configuration_error(self):
        """测试配置错误"""
        error = ConfigurationError("Missing config")
        assert isinstance(error, NonRetryableError)


class TestRetryConfig:
    """测试重试配置"""

    def test_default_config(self):
        """测试默认配置"""
        config = RetryConfig()

        assert config.enabled is True
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.backoff_factor == 2.0
        assert config.max_delay == 60.0

    def test_custom_config(self):
        """测试自定义配置"""
        config = RetryConfig(
            enabled=True, max_attempts=5, initial_delay=0.5, backoff_factor=1.5, max_delay=30.0
        )

        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.backoff_factor == 1.5
        assert config.max_delay == 30.0

    def test_get_delay_exponential_backoff(self):
        """测试指数退避延迟计算"""
        config = RetryConfig(initial_delay=1.0, backoff_factor=2.0, max_delay=60.0)

        # 第1次尝试: 1.0 * 2^0 = 1.0
        assert config.get_delay(1) == 1.0

        # 第2次尝试: 1.0 * 2^1 = 2.0
        assert config.get_delay(2) == 2.0

        # 第3次尝试: 1.0 * 2^2 = 4.0
        assert config.get_delay(3) == 4.0

        # 第4次尝试: 1.0 * 2^3 = 8.0
        assert config.get_delay(4) == 8.0

    def test_get_delay_respects_max_delay(self):
        """测试延迟不超过最大值"""
        config = RetryConfig(initial_delay=10.0, backoff_factor=3.0, max_delay=30.0)

        # 第3次尝试: 10 * 3^2 = 90，但最大30
        assert config.get_delay(3) == 30.0

    def test_retryable_exceptions_default(self):
        """测试默认可重试异常"""
        config = RetryConfig()

        assert RetryableError in config.retryable_exceptions
        assert ConnectionError in config.retryable_exceptions
        assert TimeoutError in config.retryable_exceptions


class TestRetryHandler:
    """测试重试处理器主类"""

    @pytest.fixture
    def handler(self):
        """创建默认重试处理器"""
        config = RetryConfig(
            max_attempts=3,
            initial_delay=0.01,  # 快速测试
            backoff_factor=2.0,
        )
        return RetryHandler(config)

    @pytest.mark.asyncio
    async def test_execute_success_first_try(self, handler):
        """测试首次执行成功"""
        mock_func = AsyncMock(return_value="success")

        result = await handler.execute(mock_func)

        assert result == "success"
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_retry_then_success(self, handler):
        """测试重试后成功"""
        mock_func = AsyncMock(
            side_effect=[NetworkError("First failure"), NetworkError("Second failure"), "success"]
        )

        result = await handler.execute(mock_func)

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_all_retries_fail(self, handler):
        """测试所有重试都失败"""
        mock_func = AsyncMock(side_effect=NetworkError("Always fails"))

        with pytest.raises(NetworkError, match="Always fails"):
            await handler.execute(mock_func)

        assert mock_func.call_count == 3  # max_attempts

    @pytest.mark.asyncio
    async def test_execute_non_retryable_error(self, handler):
        """测试不可重试错误立即失败"""
        mock_func = AsyncMock(side_effect=ValidationError("Invalid data"))

        with pytest.raises(ValidationError, match="Invalid data"):
            await handler.execute(mock_func)

        assert mock_func.call_count == 1  # 不重试

    @pytest.mark.asyncio
    async def test_execute_with_args_and_kwargs(self, handler):
        """测试传递参数"""
        mock_func = AsyncMock(return_value="done")

        result = await handler.execute(mock_func, "arg1", "arg2", key1="value1")

        assert result == "done"
        mock_func.assert_called_once_with("arg1", "arg2", key1="value1")

    @pytest.mark.asyncio
    async def test_execute_with_cleanup_func(self, handler):
        """测试带清理函数的重试"""
        cleanup_called = []

        async def cleanup():
            cleanup_called.append(True)

        mock_func = AsyncMock(
            side_effect=[NetworkError("Fail 1"), NetworkError("Fail 2"), "success"]
        )

        result = await handler.execute(mock_func, cleanup_func=cleanup)

        assert result == "success"
        # 清理函数应该在每次重试前调用（共2次）
        assert len(cleanup_called) == 2

    @pytest.mark.asyncio
    async def test_execute_disabled_retry(self):
        """测试禁用重试"""
        config = RetryConfig(enabled=False)
        handler = RetryHandler(config)

        mock_func = AsyncMock(side_effect=NetworkError("Should not retry"))

        with pytest.raises(NetworkError):
            await handler.execute(mock_func)

        assert mock_func.call_count == 1


class TestRetryWithBackoffDecorator:
    """测试重试装饰器"""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """测试装饰器正常执行"""
        call_count = 0

        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_retry(self):
        """测试装饰器重试"""
        call_count = 0

        @retry_with_backoff(max_attempts=3, initial_delay=0.01)
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("Temporary failure")
            return "success"

        result = await flaky_func()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_decorator_max_retries_exceeded(self):
        """测试装饰器超过最大重试次数"""

        @retry_with_backoff(max_attempts=2, initial_delay=0.01)
        async def always_fails():
            raise RetryableError("Always fails")

        with pytest.raises(RetryableError):
            await always_fails()

    @pytest.mark.asyncio
    async def test_decorator_with_custom_exceptions(self):
        """测试装饰器自定义异常"""
        call_count = 0

        @retry_with_backoff(max_attempts=3, initial_delay=0.01, retryable_exceptions=(ValueError,))
        async def custom_exception_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Custom error")
            return "success"

        result = await custom_exception_func()

        assert result == "success"
        assert call_count == 2


class TestCreateRetryHandler:
    """测试便捷创建函数"""

    def test_create_default_handler(self):
        """测试创建默认处理器"""
        handler = create_retry_handler()

        assert isinstance(handler, RetryHandler)
        assert handler.config.max_attempts == 3
        assert handler.config.backoff_factor == 2.0

    def test_create_custom_handler(self):
        """测试创建自定义处理器"""
        handler = create_retry_handler(max_attempts=5, backoff_factor=1.5)

        assert handler.config.max_attempts == 5
        assert handler.config.backoff_factor == 1.5

    @pytest.mark.asyncio
    async def test_created_handler_works(self):
        """测试创建的处理器正常工作"""
        handler = create_retry_handler(max_attempts=2)

        mock_func = AsyncMock(return_value="result")
        result = await handler.execute(mock_func)

        assert result == "result"


class TestRetryHandlerEdgeCases:
    """测试边界情况"""

    @pytest.mark.asyncio
    async def test_single_attempt(self):
        """测试只尝试一次"""
        config = RetryConfig(max_attempts=1, initial_delay=0.01)
        handler = RetryHandler(config)

        mock_func = AsyncMock(side_effect=NetworkError("Fail"))

        with pytest.raises(NetworkError):
            await handler.execute(mock_func)

        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_sync_cleanup_function(self):
        """测试同步清理函数"""
        cleanup_called = []

        def sync_cleanup():
            cleanup_called.append(True)

        config = RetryConfig(max_attempts=2, initial_delay=0.01)
        handler = RetryHandler(config)

        mock_func = AsyncMock(side_effect=[NetworkError("Fail"), "success"])

        result = await handler.execute(mock_func, cleanup_func=sync_cleanup)

        assert result == "success"
        assert len(cleanup_called) == 1

    @pytest.mark.asyncio
    async def test_cleanup_function_failure(self):
        """测试清理函数失败不影响重试"""

        async def failing_cleanup():
            raise Exception("Cleanup failed")

        config = RetryConfig(max_attempts=2, initial_delay=0.01)
        handler = RetryHandler(config)

        mock_func = AsyncMock(side_effect=[NetworkError("Fail"), "success"])

        # 清理失败不应影响重试
        result = await handler.execute(mock_func, cleanup_func=failing_cleanup)

        assert result == "success"
