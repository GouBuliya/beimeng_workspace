"""
@PURPOSE: 提供页面加载等待装饰器，减少重复的 wait_for_load_state 调用
@OUTLINE:
  - class LoadState: 页面加载状态枚举
  - class PageLoadConfig: 装饰器配置
  - def ensure_page_loaded: 方法执行前等待页面加载的装饰器
  - def with_network_idle: 方法执行后等待网络空闲的装饰器
  - def with_page_stability: 组合装饰器，前后都等待
  - def _extract_page: 从参数中提取 Page 对象的辅助函数
@GOTCHAS:
  - 装饰器会尝试从多个位置提取 page 对象: self.page, page 参数
  - 所有超时异常都会被静默处理，不会中断流程
  - 支持异步方法
@DEPENDENCIES:
  - 外部: playwright.async_api, loguru
@RELATED: page_waiter.py, selector_race.py
"""

from __future__ import annotations

import functools
import inspect
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, ParamSpec, TypeVar

from loguru import logger
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


class LoadState(str, Enum):
    """页面加载状态类型."""

    DOMCONTENTLOADED = "domcontentloaded"
    NETWORKIDLE = "networkidle"
    LOAD = "load"


@dataclass(frozen=True)
class PageLoadTimeouts:
    """页面加载超时配置.

    可通过环境变量覆盖：
    - PAGE_LOAD_TIMEOUT_FAST: 快速加载超时 (默认 1500ms)
    - PAGE_LOAD_TIMEOUT_NORMAL: 默认加载超时 (默认 3000ms)
    - PAGE_LOAD_TIMEOUT_SLOW: 慢速加载超时 (默认 5000ms)
    - PAGE_LOAD_TIMEOUT_NETWORK: 网络空闲超时 (默认 5000ms)
    """

    FAST: int = int(os.environ.get("PAGE_LOAD_TIMEOUT_FAST", "1500"))
    NORMAL: int = int(os.environ.get("PAGE_LOAD_TIMEOUT_NORMAL", "3000"))
    SLOW: int = int(os.environ.get("PAGE_LOAD_TIMEOUT_SLOW", "5000"))
    NETWORK: int = int(os.environ.get("PAGE_LOAD_TIMEOUT_NETWORK", "5000"))


# 全局超时配置实例
PAGE_TIMEOUTS = PageLoadTimeouts()


@dataclass
class PageLoadConfig:
    """页面加载装饰器配置."""

    # 前置等待配置
    before_state: LoadState | None = LoadState.DOMCONTENTLOADED
    before_timeout_ms: int = PAGE_TIMEOUTS.FAST

    # 后置等待配置
    after_state: LoadState | None = None
    after_timeout_ms: int = PAGE_TIMEOUTS.NETWORK

    # 错误处理
    suppress_timeout: bool = True
    log_timeout: bool = True


# 默认配置实例
DEFAULT_CONFIG = PageLoadConfig()
DOM_ONLY_CONFIG = PageLoadConfig(
    before_state=LoadState.DOMCONTENTLOADED,
    before_timeout_ms=PAGE_TIMEOUTS.FAST,
    after_state=None,
)
NETWORK_IDLE_CONFIG = PageLoadConfig(
    before_state=LoadState.DOMCONTENTLOADED,
    before_timeout_ms=PAGE_TIMEOUTS.FAST,
    after_state=LoadState.NETWORKIDLE,
    after_timeout_ms=PAGE_TIMEOUTS.NETWORK,
)
FULL_LOAD_CONFIG = PageLoadConfig(
    before_state=LoadState.DOMCONTENTLOADED,
    before_timeout_ms=PAGE_TIMEOUTS.NORMAL,
    after_state=LoadState.NETWORKIDLE,
    after_timeout_ms=PAGE_TIMEOUTS.SLOW,
)


P = ParamSpec("P")
T = TypeVar("T")


def _extract_page(
    func: Callable[..., Any],
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> Page | None:
    """从函数参数中提取 Page 对象.

    尝试以下位置：
    1. kwargs['page']
    2. args 中的 Page 实例
    3. self.page (如果是方法)
    4. self._page (如果是方法)

    Args:
        func: 被装饰的函数
        args: 位置参数
        kwargs: 关键字参数

    Returns:
        Page 对象，如果找不到则返回 None
    """
    # 1. 检查 kwargs
    if "page" in kwargs and isinstance(kwargs["page"], Page):
        return kwargs["page"]

    # 2. 获取函数签名，定位 page 参数位置
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    # 查找 'page' 参数的位置
    if "page" in params:
        page_idx = params.index("page")
        # 如果是方法，需要跳过 self
        if params and params[0] == "self":
            page_idx -= 1
        if 0 <= page_idx < len(args) and isinstance(args[page_idx], Page):
            return args[page_idx]

    # 3. 遍历 args 查找 Page 实例
    for arg in args:
        if isinstance(arg, Page):
            return arg

    # 4. 检查 self.page 或 self._page
    if args and hasattr(args[0], "page"):
        page = getattr(args[0], "page")
        if isinstance(page, Page):
            return page
    if args and hasattr(args[0], "_page"):
        page = getattr(args[0], "_page")
        if isinstance(page, Page):
            return page

    return None


async def _wait_for_state(
    page: Page,
    state: LoadState,
    timeout_ms: int,
    *,
    suppress_timeout: bool = True,
    log_timeout: bool = True,
    context: str = "",
) -> bool:
    """等待页面加载状态.

    Args:
        page: Playwright Page 对象
        state: 要等待的加载状态
        timeout_ms: 超时时间（毫秒）
        suppress_timeout: 是否静默处理超时
        log_timeout: 是否记录超时日志
        context: 上下文信息（用于日志）

    Returns:
        True 如果成功，False 如果超时
    """
    try:
        await page.wait_for_load_state(state.value, timeout=timeout_ms)
        return True
    except PlaywrightTimeoutError:
        if log_timeout:
            logger.debug(f"等待 {state.value} 超时 ({timeout_ms}ms){context}，继续执行")
        if not suppress_timeout:
            raise
        return False
    except Exception as exc:
        if log_timeout:
            logger.debug(f"等待 {state.value} 失败{context}: {exc}")
        if not suppress_timeout:
            raise
        return False


def ensure_page_loaded(
    state: LoadState = LoadState.DOMCONTENTLOADED,
    timeout_ms: int = PAGE_TIMEOUTS.FAST,
    *,
    suppress_timeout: bool = True,
    log_timeout: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """装饰器：在方法执行前等待页面加载完成.

    Args:
        state: 要等待的加载状态
        timeout_ms: 超时时间（毫秒）
        suppress_timeout: 是否静默处理超时
        log_timeout: 是否记录超时日志

    Returns:
        装饰后的函数

    Example:
        @ensure_page_loaded()
        async def click_button(self, page: Page):
            ...

        @ensure_page_loaded(LoadState.NETWORKIDLE, timeout_ms=5000)
        async def wait_for_data(self, page: Page):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            page = _extract_page(func, args, kwargs)
            if page:
                await _wait_for_state(
                    page,
                    state,
                    timeout_ms,
                    suppress_timeout=suppress_timeout,
                    log_timeout=log_timeout,
                    context=f" [before {func.__name__}]",
                )
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def with_network_idle(
    timeout_ms: int = PAGE_TIMEOUTS.NETWORK,
    *,
    suppress_timeout: bool = True,
    log_timeout: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """装饰器：在方法执行后等待网络空闲.

    Args:
        timeout_ms: 超时时间（毫秒）
        suppress_timeout: 是否静默处理超时
        log_timeout: 是否记录超时日志

    Returns:
        装饰后的函数

    Example:
        @with_network_idle()
        async def submit_form(self, page: Page):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            result = await func(*args, **kwargs)
            page = _extract_page(func, args, kwargs)
            if page:
                await _wait_for_state(
                    page,
                    LoadState.NETWORKIDLE,
                    timeout_ms,
                    suppress_timeout=suppress_timeout,
                    log_timeout=log_timeout,
                    context=f" [after {func.__name__}]",
                )
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


def with_page_stability(
    config: PageLoadConfig | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """装饰器：在方法执行前后都等待页面稳定.

    Args:
        config: 页面加载配置，如果为 None 则使用默认配置

    Returns:
        装饰后的函数

    Example:
        @with_page_stability()
        async def complex_operation(self, page: Page):
            ...

        @with_page_stability(FULL_LOAD_CONFIG)
        async def heavy_operation(self, page: Page):
            ...
    """
    cfg = config or DEFAULT_CONFIG

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            page = _extract_page(func, args, kwargs)

            # 前置等待
            if page and cfg.before_state:
                await _wait_for_state(
                    page,
                    cfg.before_state,
                    cfg.before_timeout_ms,
                    suppress_timeout=cfg.suppress_timeout,
                    log_timeout=cfg.log_timeout,
                    context=f" [before {func.__name__}]",
                )

            result = await func(*args, **kwargs)

            # 后置等待
            if page and cfg.after_state:
                await _wait_for_state(
                    page,
                    cfg.after_state,
                    cfg.after_timeout_ms,
                    suppress_timeout=cfg.suppress_timeout,
                    log_timeout=cfg.log_timeout,
                    context=f" [after {func.__name__}]",
                )

            return result

        return wrapper  # type: ignore[return-value]

    return decorator


# 便捷装饰器别名
dom_loaded = ensure_page_loaded(LoadState.DOMCONTENTLOADED, PAGE_TIMEOUTS.FAST)
dom_loaded_slow = ensure_page_loaded(LoadState.DOMCONTENTLOADED, PAGE_TIMEOUTS.SLOW)
network_idle = with_network_idle(PAGE_TIMEOUTS.NETWORK)
full_stability = with_page_stability(FULL_LOAD_CONFIG)


async def wait_dom_loaded(
    page: Page,
    timeout_ms: int = PAGE_TIMEOUTS.FAST,
    *,
    context: str = "",
) -> bool:
    """等待 DOM 加载完成的便捷函数.

    Args:
        page: Playwright Page 对象
        timeout_ms: 超时时间（毫秒）
        context: 上下文信息（用于日志）

    Returns:
        True 如果成功，False 如果超时
    """
    return await _wait_for_state(
        page,
        LoadState.DOMCONTENTLOADED,
        timeout_ms,
        suppress_timeout=True,
        log_timeout=True,
        context=context,
    )


async def wait_network_idle(
    page: Page,
    timeout_ms: int = PAGE_TIMEOUTS.NETWORK,
    *,
    context: str = "",
) -> bool:
    """等待网络空闲的便捷函数.

    Args:
        page: Playwright Page 对象
        timeout_ms: 超时时间（毫秒）
        context: 上下文信息（用于日志）

    Returns:
        True 如果成功，False 如果超时
    """
    return await _wait_for_state(
        page,
        LoadState.NETWORKIDLE,
        timeout_ms,
        suppress_timeout=True,
        log_timeout=True,
        context=context,
    )


__all__ = [
    "LoadState",
    "PageLoadConfig",
    "PageLoadTimeouts",
    "PAGE_TIMEOUTS",
    "DEFAULT_CONFIG",
    "DOM_ONLY_CONFIG",
    "NETWORK_IDLE_CONFIG",
    "FULL_LOAD_CONFIG",
    "ensure_page_loaded",
    "with_network_idle",
    "with_page_stability",
    "dom_loaded",
    "dom_loaded_slow",
    "network_idle",
    "full_stability",
    "wait_dom_loaded",
    "wait_network_idle",
]

