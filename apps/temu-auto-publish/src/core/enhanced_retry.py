"""
@PURPOSE: 增强的重试机制 - 提供智能重试策略、恢复动作和详细指标
@OUTLINE:
  - @dataclass RetryPolicy: 可配置的重试策略
  - @dataclass RetryResult: 重试执行结果
  - class EnhancedRetryHandler: 增强的重试处理器
  - def smart_retry(): 智能重试装饰器
  - def create_step_retry_policy(): 创建步骤级重试策略
  - def create_stage_retry_policy(): 创建阶段级重试策略
@GOTCHAS:
  - 重试次数过多会显著增加执行时间
  - 需要区分可重试和不可重试错误
  - 恢复动作本身也可能失败
@DEPENDENCIES:
  - 外部: loguru, asyncio
  - 内部: retry_handler.py (继承基础错误类型)
"""

from __future__ import annotations

import asyncio
import functools
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Awaitable,
    Callable,
    ParamSpec,
    TypeVar,
    Generic,
)

from loguru import logger

# 从现有模块导入基础错误类型
from .retry_handler import (
    RetryableError,
    NetworkError,
    ElementNotFoundError,
    TimeoutError as RetryTimeoutError,
    NonRetryableError,
    ValidationError,
    ConfigurationError,
)

# 类型变量
P = ParamSpec("P")
R = TypeVar("R")


class RetryOutcome(str, Enum):
    """重试结果枚举"""
    
    SUCCESS = "success"  # 成功（可能经过重试）
    EXHAUSTED = "exhausted"  # 重试次数耗尽
    NON_RETRYABLE = "non_retryable"  # 遇到不可重试错误
    CANCELLED = "cancelled"  # 被取消


@dataclass
class RetryPolicy:
    """可配置的重试策略
    
    支持:
    - 指数退避
    - 自定义重试条件
    - 重试前恢复动作
    - 抖动(jitter)避免雪崩
    
    Examples:
        >>> policy = RetryPolicy(max_attempts=3, backoff_factor=2.0)
        >>> policy.get_delay(1)  # 首次重试延迟
        0.5
        >>> policy.get_delay(2)  # 第二次重试延迟
        1.0
    """
    
    # 基础配置
    max_attempts: int = 3
    initial_delay_ms: int = 500
    backoff_factor: float = 2.0
    max_delay_ms: int = 10_000
    
    # 可重试的异常类型
    retryable_exceptions: tuple[type[Exception], ...] = (
        RetryableError,
        NetworkError,
        ElementNotFoundError,
        RetryTimeoutError,
        ConnectionError,
        asyncio.TimeoutError,
    )
    
    # 不可重试的异常类型（优先级高于retryable）
    non_retryable_exceptions: tuple[type[Exception], ...] = (
        NonRetryableError,
        ValidationError,
        ConfigurationError,
        KeyboardInterrupt,
        SystemExit,
    )
    
    # 智能重试触发条件：(异常, 当前尝试次数) -> 是否继续重试
    should_retry: Callable[[Exception, int], bool] | None = None
    
    # 重试前的恢复动作（异步）
    pre_retry_action: Callable[[], Awaitable[None]] | None = None
    
    # 是否添加随机抖动（避免多实例同时重试）
    jitter: bool = True
    jitter_factor: float = 0.1  # 抖动范围：delay * (1 ± jitter_factor)
    
    # 是否在最后一次失败后仍执行恢复动作
    recovery_on_final_failure: bool = False
    
    def get_delay(self, attempt: int) -> float:
        """计算第N次重试的延迟时间（秒）
        
        Args:
            attempt: 当前尝试次数（从1开始）
            
        Returns:
            延迟时间（秒）
        """
        delay_ms = self.initial_delay_ms * (self.backoff_factor ** (attempt - 1))
        delay_ms = min(delay_ms, self.max_delay_ms)
        
        # 添加随机抖动
        if self.jitter:
            import random
            jitter_range = delay_ms * self.jitter_factor
            delay_ms += random.uniform(-jitter_range, jitter_range)
        
        return max(delay_ms, 0) / 1000
    
    def is_retryable(self, exc: Exception, attempt: int) -> bool:
        """判断异常是否可重试
        
        Args:
            exc: 异常对象
            attempt: 当前尝试次数
            
        Returns:
            是否应该重试
        """
        # 先检查不可重试类型
        if isinstance(exc, self.non_retryable_exceptions):
            return False
        
        # 再检查可重试类型
        if not isinstance(exc, self.retryable_exceptions):
            return False
        
        # 检查是否超过最大次数
        if attempt >= self.max_attempts:
            return False
        
        # 自定义条件检查
        if self.should_retry is not None:
            return self.should_retry(exc, attempt)
        
        return True


@dataclass
class RetryResult(Generic[R]):
    """重试执行结果
    
    包含执行结果、重试统计和错误信息。
    """
    
    outcome: RetryOutcome
    value: R | None = None
    total_attempts: int = 0
    total_delay_ms: float = 0.0
    errors: list[dict[str, Any]] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now().isoformat())
    end_time: str | None = None
    
    @property
    def success(self) -> bool:
        """是否成功"""
        return self.outcome == RetryOutcome.SUCCESS
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "outcome": self.outcome.value,
            "success": self.success,
            "total_attempts": self.total_attempts,
            "total_delay_ms": round(self.total_delay_ms, 2),
            "errors": self.errors,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


class EnhancedRetryHandler:
    """增强的重试处理器
    
    特点:
    1. 支持异步恢复动作
    2. 详细的执行指标
    3. 智能退避策略
    4. 可配置的重试条件
    
    Examples:
        >>> handler = EnhancedRetryHandler(RetryPolicy(max_attempts=3))
        >>> result = await handler.execute(some_async_func, arg1, arg2)
        >>> if result.success:
        ...     print(f"成功，共尝试 {result.total_attempts} 次")
    """
    
    def __init__(self, policy: RetryPolicy | None = None):
        """初始化处理器
        
        Args:
            policy: 重试策略，默认使用 RetryPolicy()
        """
        self.policy = policy or RetryPolicy()
        self._metrics: dict[str, Any] = {
            "total_executions": 0,
            "successful_executions": 0,
            "total_retries": 0,
            "total_failures": 0,
        }
    
    async def execute(
        self,
        func: Callable[P, Awaitable[R]],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> RetryResult[R]:
        """执行函数并在失败时重试
        
        Args:
            func: 要执行的异步函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            RetryResult 包含执行结果和统计信息
        """
        result = RetryResult[R](
            outcome=RetryOutcome.EXHAUSTED,
            total_attempts=0,
        )
        
        self._metrics["total_executions"] += 1
        last_exception: Exception | None = None
        
        for attempt in range(1, self.policy.max_attempts + 1):
            result.total_attempts = attempt
            
            try:
                logger.debug(
                    f"执行 {func.__name__} (尝试 {attempt}/{self.policy.max_attempts})"
                )
                
                value = await func(*args, **kwargs)
                
                result.outcome = RetryOutcome.SUCCESS
                result.value = value
                result.end_time = datetime.now().isoformat()
                
                if attempt > 1:
                    logger.success(
                        f"✓ {func.__name__} 重试成功 (第{attempt}次尝试)"
                    )
                
                self._metrics["successful_executions"] += 1
                return result
                
            except Exception as exc:
                last_exception = exc
                error_info = {
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "timestamp": datetime.now().isoformat(),
                    "traceback": traceback.format_exc() if attempt == self.policy.max_attempts else None,
                }
                result.errors.append(error_info)
                
                # 检查是否为不可重试错误
                if isinstance(exc, self.policy.non_retryable_exceptions):
                    logger.error(f"✗ 不可重试错误: {exc}")
                    result.outcome = RetryOutcome.NON_RETRYABLE
                    result.end_time = datetime.now().isoformat()
                    self._metrics["total_failures"] += 1
                    raise
                
                # 检查是否应该重试
                if not self.policy.is_retryable(exc, attempt):
                    if attempt >= self.policy.max_attempts:
                        logger.error(
                            f"✗ {func.__name__} 重试次数耗尽 ({attempt}次)"
                        )
                    else:
                        logger.error(f"✗ 不满足重试条件: {exc}")
                    break
                
                # 执行重试
                self._metrics["total_retries"] += 1
                delay = self.policy.get_delay(attempt)
                result.total_delay_ms += delay * 1000
                
                logger.warning(
                    f"⚠ {func.__name__} 失败 (尝试 {attempt}/{self.policy.max_attempts}): {exc}"
                )
                logger.info(f"  等待 {delay:.2f}秒 后重试...")
                
                # 执行恢复动作
                if self.policy.pre_retry_action is not None:
                    try:
                        logger.debug("执行重试前恢复动作...")
                        await self.policy.pre_retry_action()
                    except Exception as recovery_error:
                        logger.warning(f"恢复动作失败: {recovery_error}")
                
                await asyncio.sleep(delay)
        
        # 所有重试都失败
        result.outcome = RetryOutcome.EXHAUSTED
        result.end_time = datetime.now().isoformat()
        self._metrics["total_failures"] += 1
        
        # 最终失败后的恢复动作
        if self.policy.recovery_on_final_failure and self.policy.pre_retry_action:
            try:
                await self.policy.pre_retry_action()
            except Exception:
                pass
        
        if last_exception:
            raise last_exception
        
        return result
    
    def get_metrics(self) -> dict[str, Any]:
        """获取执行指标"""
        return self._metrics.copy()
    
    def reset_metrics(self) -> None:
        """重置执行指标"""
        self._metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "total_retries": 0,
            "total_failures": 0,
        }


def smart_retry(
    policy: RetryPolicy | None = None,
    *,
    max_attempts: int | None = None,
    initial_delay_ms: int | None = None,
    backoff_factor: float | None = None,
    retryable_exceptions: tuple[type[Exception], ...] | None = None,
    pre_retry_action: Callable[[], Awaitable[None]] | None = None,
):
    """智能重试装饰器
    
    支持通过参数或 RetryPolicy 配置重试行为。
    
    Args:
        policy: 完整的重试策略（优先级最高）
        max_attempts: 最大尝试次数
        initial_delay_ms: 初始延迟（毫秒）
        backoff_factor: 退避因子
        retryable_exceptions: 可重试的异常类型
        pre_retry_action: 重试前的恢复动作
        
    Returns:
        装饰器函数
        
    Examples:
        >>> @smart_retry(max_attempts=3)
        ... async def fetch_data():
        ...     # 可能失败的操作
        ...     pass
        
        >>> @smart_retry(RetryPolicy(max_attempts=5, backoff_factor=1.5))
        ... async def another_operation():
        ...     pass
    """
    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            # 构建策略
            effective_policy = policy or RetryPolicy()
            
            # 覆盖单独指定的参数
            if max_attempts is not None:
                effective_policy.max_attempts = max_attempts
            if initial_delay_ms is not None:
                effective_policy.initial_delay_ms = initial_delay_ms
            if backoff_factor is not None:
                effective_policy.backoff_factor = backoff_factor
            if retryable_exceptions is not None:
                effective_policy.retryable_exceptions = retryable_exceptions
            if pre_retry_action is not None:
                effective_policy.pre_retry_action = pre_retry_action
            
            handler = EnhancedRetryHandler(effective_policy)
            result = await handler.execute(func, *args, **kwargs)
            
            if result.success:
                return result.value  # type: ignore
            
            # 如果失败，异常已经在 execute 中抛出
            # 这里只是为了类型检查
            raise RuntimeError(f"重试失败: {result.errors[-1] if result.errors else '未知错误'}")
        
        return wrapper
    
    return decorator


def create_step_retry_policy(
    pre_retry_action: Callable[[], Awaitable[None]] | None = None,
) -> RetryPolicy:
    """创建步骤级重试策略（轻量级，快速重试）
    
    适用于单个UI操作步骤，如点击按钮、填写表单等。
    
    Args:
        pre_retry_action: 重试前的恢复动作
        
    Returns:
        配置好的 RetryPolicy
    """
    return RetryPolicy(
        max_attempts=2,
        initial_delay_ms=300,
        backoff_factor=1.5,
        max_delay_ms=1000,
        pre_retry_action=pre_retry_action,
        jitter=True,
        jitter_factor=0.2,
    )


def create_stage_retry_policy(
    pre_retry_action: Callable[[], Awaitable[None]] | None = None,
) -> RetryPolicy:
    """创建阶段级重试策略（较重，有恢复动作）
    
    适用于完整的工作流阶段，如"首次编辑"、"批量编辑"等。
    
    Args:
        pre_retry_action: 重试前的恢复动作（如刷新页面）
        
    Returns:
        配置好的 RetryPolicy
    """
    return RetryPolicy(
        max_attempts=3,
        initial_delay_ms=1000,
        backoff_factor=2.0,
        max_delay_ms=10000,
        pre_retry_action=pre_retry_action,
        jitter=True,
        jitter_factor=0.1,
        recovery_on_final_failure=True,
    )


def create_network_retry_policy() -> RetryPolicy:
    """创建网络操作重试策略
    
    适用于网络请求、页面导航等操作。
    
    Returns:
        配置好的 RetryPolicy
    """
    return RetryPolicy(
        max_attempts=4,
        initial_delay_ms=500,
        backoff_factor=2.0,
        max_delay_ms=15000,
        retryable_exceptions=(
            NetworkError,
            ConnectionError,
            asyncio.TimeoutError,
            RetryTimeoutError,
        ),
        jitter=True,
        jitter_factor=0.3,
    )


# 导出
__all__ = [
    "RetryPolicy",
    "RetryResult",
    "RetryOutcome",
    "EnhancedRetryHandler",
    "smart_retry",
    "create_step_retry_policy",
    "create_stage_retry_policy",
    "create_network_retry_policy",
    # 重新导出基础错误类型
    "RetryableError",
    "NetworkError",
    "ElementNotFoundError",
    "RetryTimeoutError",
    "NonRetryableError",
    "ValidationError",
    "ConfigurationError",
]


