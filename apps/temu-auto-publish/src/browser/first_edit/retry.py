"""
@PURPOSE: 提供首次编辑流程的统一重试装饰器,封装重试策略与恢复动作
@OUTLINE:
  - def first_edit_step_retry(): 单步操作重试装饰器,可在布尔失败时触发重试
  - def first_edit_stage_retry(): 阶段级重试装饰器,适合整段流程包裹
  - def extract_page(): 从调用参数中提取 Playwright Page 对象
@DEPENDENCIES:
  - 内部: ...core.enhanced_retry.smart_retry, create_step_retry_policy, create_stage_retry_policy
  - 外部: playwright.async_api.Page, loguru.logger
@GOTCHAS:
  - 布尔返回 False 时会触发重试,确保调用者幂等
  - pre_retry_action 默认等待页面加载,若需要自定义恢复动作可传入工厂
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Awaitable, Callable, Iterable

from loguru import logger
from playwright.async_api import Page

from ...core.enhanced_retry import (
    RetryPolicy,
    create_stage_retry_policy,
    create_step_retry_policy,
)
from ...core.enhanced_retry import (
    smart_retry as enhanced_smart_retry,
)
from ...utils.page_waiter import PageWaiter


def extract_page(*args, **kwargs) -> Page | None:
    """从参数中提取 Page 对象."""

    for arg in args:
        if isinstance(arg, Page):
            return arg
    for value in kwargs.values():
        if isinstance(value, Page):
            return value
    return None


def _default_pre_retry_action(page: Page | None) -> Callable[[], Awaitable[None]]:
    """构建默认的重试前恢复动作."""

    async def _action() -> None:
        if page is None:
            return
        try:
            waiter = PageWaiter(page)
            await waiter.wait_for_dom_stable(timeout_ms=400)
            await waiter.wait_for_network_idle(timeout_ms=800)
        except Exception:
            # 恢复动作不应中断主流程
            logger.debug("重试前恢复动作忽略异常", exc_info=True)
            await asyncio.sleep(0.08)

    return _action


def _build_policy(
    *,
    base_policy: RetryPolicy,
    max_attempts: int,
    initial_delay_ms: int,
    backoff_factor: float,
    max_delay_ms: int | None,
    retryable_exceptions: Iterable[type[Exception]] | None,
    non_retryable_exceptions: Iterable[type[Exception]] | None,
) -> RetryPolicy:
    """基于基础策略覆写关键参数."""

    policy = base_policy
    policy.max_attempts = max_attempts
    policy.initial_delay_ms = initial_delay_ms
    policy.backoff_factor = backoff_factor
    if max_delay_ms is not None:
        policy.max_delay_ms = max_delay_ms
    if retryable_exceptions is not None:
        policy.retryable_exceptions = tuple(retryable_exceptions)
    if non_retryable_exceptions is not None:
        policy.non_retryable_exceptions = tuple(non_retryable_exceptions)
    return policy


def first_edit_step_retry(
    *,
    max_attempts: int = 3,
    initial_delay_ms: int = 320,
    backoff_factor: float = 1.6,
    max_delay_ms: int | None = 1500,
    retryable_exceptions: Iterable[type[Exception]] | None = None,
    non_retryable_exceptions: Iterable[type[Exception]] | None = None,
    pre_retry_action_factory: Callable[[Page | None], Callable[[], Awaitable[None]]] | None = None,
    retry_on_false: bool = True,
):
    """首次编辑单步操作重试装饰器."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            page = extract_page(*args, **kwargs)
            pre_action = (
                pre_retry_action_factory(page)
                if pre_retry_action_factory
                else _default_pre_retry_action(page)
            )
            policy = _build_policy(
                base_policy=create_step_retry_policy(pre_retry_action=pre_action),
                max_attempts=max_attempts,
                initial_delay_ms=initial_delay_ms,
                backoff_factor=backoff_factor,
                max_delay_ms=max_delay_ms,
                retryable_exceptions=retryable_exceptions,
                non_retryable_exceptions=non_retryable_exceptions,
            )

            @functools.wraps(func)
            async def wrapped(*inner_args, **inner_kwargs):
                result = await func(*inner_args, **inner_kwargs)
                if retry_on_false and isinstance(result, bool) and result is False:
                    raise RuntimeError(f"{func.__name__} returned False")
                return result

            return await enhanced_smart_retry(policy)(wrapped)(*args, **kwargs)

        return wrapper

    return decorator


def first_edit_stage_retry(
    *,
    max_attempts: int = 3,
    initial_delay_ms: int = 800,
    backoff_factor: float = 2.0,
    max_delay_ms: int | None = 10_000,
    pre_retry_action_factory: Callable[[Page | None], Callable[[], Awaitable[None]]] | None = None,
    retryable_exceptions: Iterable[type[Exception]] | None = None,
    non_retryable_exceptions: Iterable[type[Exception]] | None = None,
):
    """首次编辑阶段级重试装饰器."""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            page = extract_page(*args, **kwargs)
            pre_action = (
                pre_retry_action_factory(page)
                if pre_retry_action_factory
                else _default_pre_retry_action(page)
            )
            policy = _build_policy(
                base_policy=create_stage_retry_policy(pre_retry_action=pre_action),
                max_attempts=max_attempts,
                initial_delay_ms=initial_delay_ms,
                backoff_factor=backoff_factor,
                max_delay_ms=max_delay_ms,
                retryable_exceptions=retryable_exceptions,
                non_retryable_exceptions=non_retryable_exceptions,
            )
            return await enhanced_smart_retry(policy)(func)(*args, **kwargs)

        return wrapper

    return decorator


__all__ = ["extract_page", "first_edit_stage_retry", "first_edit_step_retry"]
