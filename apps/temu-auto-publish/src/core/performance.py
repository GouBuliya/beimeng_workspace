"""
@PURPOSE: 性能分析装饰器 - 用于检测函数执行时间并记录到日志
@OUTLINE:
  - def profile(threshold_ms): 性能分析装饰器
    - 支持同步和异步函数
    - 可配置超时阈值（默认3000ms）
    - 记录执行时间和异常信息
@USAGE:
  @profile()
  def sync_function():
      pass
  
  @profile(threshold_ms=5000)
  async def async_function():
      pass
@DEPENDENCIES:
  - 外部: loguru
  - 内部: 无
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any, Callable, ParamSpec, TypeVar

from loguru import logger

# Type variables for preserving function signatures
P = ParamSpec("P")
T = TypeVar("T")

# Default threshold in milliseconds
DEFAULT_THRESHOLD_MS = 3000


def profile(
    threshold_ms: int = DEFAULT_THRESHOLD_MS,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """性能分析装饰器 - 检测函数执行时间并记录到日志。
    
    日志格式：
    - 正常: [Performance] Function: <function_name> - Duration: <duration>ms
    - 超时警告: [Performance] Function: <function_name> - Duration: <duration>ms - Warning: Slow execution
    - 异常: [Performance] Function: <function_name> - Duration: <duration>ms - Exception: <exception>
    
    Args:
        threshold_ms: 超时阈值（毫秒），超过此时间会记录警告。默认3000ms。
        
    Returns:
        装饰后的函数
        
    Examples:
        >>> @profile()
        ... def my_function():
        ...     time.sleep(0.1)
        ...     return "done"
        >>> my_function()
        'done'
        
        >>> @profile(threshold_ms=1000)
        ... async def my_async_function():
        ...     await asyncio.sleep(0.1)
        ...     return "done"
        >>> await my_async_function()
        'done'
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                func_name = func.__qualname__
                start_time = time.perf_counter()
                exception_info: str | None = None
                
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    exception_info = f"{type(e).__name__}: {e}"
                    raise
                finally:
                    end_time = time.perf_counter()
                    duration_ms = (end_time - start_time) * 1000
                    _log_performance(func_name, duration_ms, threshold_ms, exception_info)
            
            return async_wrapper  # type: ignore
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
                func_name = func.__qualname__
                start_time = time.perf_counter()
                exception_info: str | None = None
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    exception_info = f"{type(e).__name__}: {e}"
                    raise
                finally:
                    end_time = time.perf_counter()
                    duration_ms = (end_time - start_time) * 1000
                    _log_performance(func_name, duration_ms, threshold_ms, exception_info)
            
            return sync_wrapper  # type: ignore
    
    return decorator


def _log_performance(
    func_name: str,
    duration_ms: float,
    threshold_ms: int,
    exception_info: str | None,
) -> None:
    """记录性能日志。
    
    Args:
        func_name: 函数名称
        duration_ms: 执行时间（毫秒）
        threshold_ms: 超时阈值（毫秒）
        exception_info: 异常信息（如果有）
    """
    duration_rounded = round(duration_ms, 2)
    
    if exception_info:
        # 异常情况
        logger.error(
            f"[Performance] Function: {func_name} - "
            f"Duration: {duration_rounded}ms - "
            f"Exception: {exception_info}"
        )
    elif duration_ms > threshold_ms:
        # 超时警告
        logger.warning(
            f"[Performance] Function: {func_name} - "
            f"Duration: {duration_rounded}ms - "
            f"Warning: Slow execution (threshold: {threshold_ms}ms)"
        )
    else:
        # 正常情况
        logger.info(
            f"[Performance] Function: {func_name} - "
            f"Duration: {duration_rounded}ms"
        )


# 导出
__all__ = [
    "profile",
    "DEFAULT_THRESHOLD_MS",
]

