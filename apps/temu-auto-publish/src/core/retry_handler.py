"""
@PURPOSE: 重试处理器 - 提供指数退避重试机制和错误分类
@OUTLINE:
  - class RetryableError: 可重试错误基类
  - class NetworkError: 网络错误
  - class ElementNotFoundError: 元素未找到错误
  - class TimeoutError: 超时错误
  - class NonRetryableError: 不可重试错误基类
  - class RetryConfig: 重试配置
  - class RetryHandler: 重试处理器
  - def retry_with_backoff(): 重试装饰器
@GOTCHAS:
  - 重试次数过多会导致执行时间过长
  - 需要区分可重试和不可重试错误
  - 重试前应该清理状态
@TECH_DEBT:
  - TODO: 添加重试策略自定义
  - TODO: 添加重试事件回调
@DEPENDENCIES:
  - 外部: loguru, asyncio
"""

import asyncio
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type

from loguru import logger


# ========== 错误分类 ==========


class RetryableError(Exception):
    """可重试错误基类."""

    pass


class NetworkError(RetryableError):
    """网络错误（可重试）."""

    pass


class ElementNotFoundError(RetryableError):
    """元素未找到错误（可重试）."""

    pass


class TimeoutError(RetryableError):
    """超时错误（可重试）."""

    pass


class NonRetryableError(Exception):
    """不可重试错误基类."""

    pass


class ValidationError(NonRetryableError):
    """验证错误（不可重试）."""

    pass


class ConfigurationError(NonRetryableError):
    """配置错误（不可重试）."""

    pass


# ========== 重试配置 ==========


@dataclass
class RetryConfig:
    """重试配置.

    Attributes:
        enabled: 是否启用重试
        max_attempts: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子
        max_delay: 最大延迟（秒）
        retryable_exceptions: 可重试的异常类型

    Examples:
        >>> config = RetryConfig(max_attempts=3, backoff_factor=2.0)
        >>> config.max_attempts
        3
    """

    enabled: bool = True
    max_attempts: int = 3
    initial_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 60.0
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        RetryableError,
        ConnectionError,
        TimeoutError,
    )

    def get_delay(self, attempt: int) -> float:
        """计算指数退避延迟.

        Args:
            attempt: 当前尝试次数（从1开始）

        Returns:
            延迟时间（秒）
        """
        delay = self.initial_delay * (self.backoff_factor ** (attempt - 1))
        return min(delay, self.max_delay)


# ========== 重试处理器 ==========


class RetryHandler:
    """重试处理器 - 统一管理重试逻辑.

    Examples:
        >>> handler = RetryHandler()
        >>> await handler.execute(some_async_func, arg1, arg2)
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        """初始化重试处理器.

        Args:
            config: 重试配置，默认使用 RetryConfig()
        """
        self.config = config or RetryConfig()

    async def execute(
        self, func: Callable, *args, cleanup_func: Optional[Callable] = None, **kwargs
    ) -> Any:
        """执行函数并在失败时重试.

        Args:
            func: 要执行的异步函数
            *args: 位置参数
            cleanup_func: 清理函数（重试前调用）
            **kwargs: 关键字参数

        Returns:
            函数执行结果

        Raises:
            最后一次失败的异常
        """
        if not self.config.enabled:
            return await func(*args, **kwargs)

        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(f"执行尝试 {attempt}/{self.config.max_attempts}: {func.__name__}")
                result = await func(*args, **kwargs)

                if attempt > 1:
                    logger.success(f"✓ 重试成功: {func.__name__} (第{attempt}次尝试)")

                return result

            except self.config.retryable_exceptions as e:
                last_exception = e

                if attempt < self.config.max_attempts:
                    delay = self.config.get_delay(attempt)
                    logger.warning(f"⚠️ 尝试 {attempt}/{self.config.max_attempts} 失败: {e}")
                    logger.info(f"  等待 {delay:.1f}秒 后重试...")

                    # 执行清理
                    if cleanup_func:
                        try:
                            if asyncio.iscoroutinefunction(cleanup_func):
                                await cleanup_func()
                            else:
                                cleanup_func()
                        except Exception as cleanup_error:
                            logger.warning(f"清理失败: {cleanup_error}")

                    await asyncio.sleep(delay)
                else:
                    logger.error(f"✗ 所有尝试均失败 ({self.config.max_attempts}次): {e}")

            except Exception as e:
                # 不可重试错误
                logger.error(f"✗ 不可重试错误: {e}")
                raise

        # 所有重试都失败
        raise last_exception


# ========== 装饰器 ==========


def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    cleanup_func: Optional[Callable] = None,
):
    """重试装饰器（支持指数退避）.

    Args:
        max_attempts: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子
        retryable_exceptions: 可重试的异常类型
        cleanup_func: 清理函数

    Returns:
        装饰器函数

    Examples:
        >>> @retry_with_backoff(max_attempts=3)
        ... async def fetch_data():
        ...     # 可能失败的操作
        ...     pass
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                initial_delay=initial_delay,
                backoff_factor=backoff_factor,
            )

            if retryable_exceptions:
                config.retryable_exceptions = retryable_exceptions

            handler = RetryHandler(config)
            return await handler.execute(func, *args, cleanup_func=cleanup_func, **kwargs)

        return wrapper

    return decorator


# 便捷函数
def create_retry_handler(max_attempts: int = 3, backoff_factor: float = 2.0) -> RetryHandler:
    """创建重试处理器（便捷方法）.

    Args:
        max_attempts: 最大重试次数
        backoff_factor: 退避因子

    Returns:
        配置好的重试处理器
    """
    config = RetryConfig(max_attempts=max_attempts, backoff_factor=backoff_factor)
    return RetryHandler(config)
