"""
@PURPOSE: 批量编辑增强工具模块（重试、性能监控、错误处理）
@OUTLINE:
  - def retry_on_failure(): 重试装饰器（指数退避策略）
  - class PerformanceMonitor: 性能监控上下文管理器
  - class StepValidator: 步骤验证器（前置/后置检查）
  - def enhanced_error_handler(): 增强错误处理装饰器
@GOTCHAS:
  - 重试装饰器必须在async函数上使用
  - 性能监控应该在步骤最外层使用
  - 日志格式要统一
@DEPENDENCIES:
  - 外部: loguru, playwright
@RELATED: batch_edit_controller.py
@CHANGELOG:
  - 2025-10-31: 创建批量编辑增强工具模块
"""

import asyncio
import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import Callable, Optional

from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout


def retry_on_failure(
    max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: tuple = (Exception,)
):
    """重试装饰器（指数退避策略）.

    为批量编辑步骤提供自动重试能力，增强稳定性。

    Args:
        max_retries: 最大重试次数（默认3次）
        delay: 初始延迟时间（秒，默认1.0）
        backoff: 退避倍率（默认2.0，每次重试延迟翻倍）
        exceptions: 需要捕获的异常类型元组

    Returns:
        装饰后的异步函数

    Examples:
        >>> @retry_on_failure(max_retries=3, delay=1.0)
        >>> async def unreliable_step(page: Page) -> bool:
        >>>     await page.click("button")
        >>>     return True
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries):
                try:
                    result = await func(*args, **kwargs)
                    if attempt > 0:
                        logger.success(f"   ✓ {func.__name__} 重试成功 (第 {attempt + 1} 次尝试)")
                    return result

                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"   ⚠️ {func.__name__} 失败 "
                            f"(尝试 {attempt + 1}/{max_retries}): {str(e)[:100]}"
                        )
                        logger.info(f"   💤 等待 {current_delay:.1f}秒后重试...")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"   ❌ {func.__name__} 失败 (已达最大重试次数 {max_retries}): {e}"
                        )

            # 所有重试都失败
            raise last_exception

        return wrapper

    return decorator


@asynccontextmanager
async def performance_monitor(step_name: str, warn_threshold: float = 10.0):
    """性能监控上下文管理器.

    监控步骤执行时间，记录性能指标，超时告警。

    Args:
        step_name: 步骤名称
        warn_threshold: 告警阈值（秒）

    Yields:
        None（用于with语句）

    Examples:
        >>> async with performance_monitor("步骤7.3：类目属性"):
        >>>     await some_operation()
        >>>     # 自动记录耗时
    """
    start_time = time.time()
    logger.debug(f"⏱️  {step_name} 开始执行")

    try:
        yield
    finally:
        elapsed = time.time() - start_time

        if elapsed > warn_threshold:
            logger.warning(f"⏱️  {step_name} 完成 (耗时: {elapsed:.2f}秒 ⚠️ 超时)")
        else:
            logger.info(f"⏱️  {step_name} 完成 (耗时: {elapsed:.2f}秒)")


async def take_error_screenshot(page: Page, step_name: str) -> Optional[str]:
    """拍摄错误截图.

    Args:
        page: 页面对象
        step_name: 步骤名称

    Returns:
        截图文件路径，如果失败返回None

    Examples:
        >>> path = await take_error_screenshot(page, "step_03")
        >>> logger.error(f"错误截图: {path}")
    """
    try:
        timestamp = int(time.time())
        safe_step_name = step_name.replace(" ", "_").replace(":", "_")
        screenshot_path = f"data/temp/error_{safe_step_name}_{timestamp}.png"

        await page.screenshot(path=screenshot_path)
        logger.info(f"   📸 错误截图已保存: {screenshot_path}")
        return screenshot_path

    except Exception as e:
        logger.warning(f"   ⚠️ 保存错误截图失败: {e}")
        return None


def enhanced_error_handler(step_name: str):
    """增强错误处理装饰器.

    为步骤添加增强的错误处理逻辑：
    - 区分不同类型的异常
    - 自动拍摄错误截图
    - 记录详细的错误上下文

    Args:
        step_name: 步骤名称

    Returns:
        装饰后的异步函数

    Examples:
        >>> @enhanced_error_handler("步骤7.3")
        >>> async def step_03_category_attrs(self, page: Page) -> bool:
        >>>     # 步骤逻辑
        >>>     pass
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 尝试获取page参数
            page = None
            if len(args) > 1 and hasattr(args[1], "screenshot"):
                page = args[1]
            elif "page" in kwargs:
                page = kwargs["page"]

            try:
                return await func(*args, **kwargs)

            except PlaywrightTimeout as e:
                logger.error(f"   ❌ {step_name} - 超时错误: 元素加载时间过长或选择器不正确")
                if page:
                    await take_error_screenshot(page, func.__name__)
                raise

            except ConnectionError as e:
                logger.error(f"   ❌ {step_name} - 网络错误: {e}")
                raise

            except Exception as e:
                error_type = type(e).__name__
                logger.error(f"   ❌ {step_name} - 未预期错误 ({error_type}): {str(e)[:200]}")
                if page:
                    await take_error_screenshot(page, func.__name__)
                raise

        return wrapper

    return decorator


class StepValidator:
    """步骤验证器（前置/后置检查）.

    用于验证步骤执行前后的状态，确保流程正确性。

    Examples:
        >>> validator = StepValidator()
        >>> await validator.check_page_loaded(page)
        True
    """

    @staticmethod
    async def check_page_loaded(page: Page, timeout: int = 5000) -> bool:
        """检查页面是否加载完成.

        Args:
            page: 页面对象
            timeout: 超时时间（毫秒）

        Returns:
            是否加载完成
        """
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=timeout)
            logger.debug("   ✓ 页面加载完成")
            return True
        except PlaywrightTimeout:
            logger.warning("   ⚠️ 页面加载超时")
            return False

    @staticmethod
    async def check_element_visible(
        page: Page, selector: str, timeout: int = 5000, description: str = "元素"
    ) -> bool:
        """检查元素是否可见.

        Args:
            page: 页面对象
            selector: 选择器
            timeout: 超时时间（毫秒）
            description: 元素描述（用于日志）

        Returns:
            是否可见
        """
        try:
            element = page.locator(selector).first
            await element.wait_for(state="visible", timeout=timeout)
            logger.debug(f"   ✓ {description}可见")
            return True
        except PlaywrightTimeout:
            logger.warning(f"   ⚠️ {description}不可见或加载超时")
            return False

    @staticmethod
    async def check_element_count(
        page: Page, selector: str, expected_count: int, description: str = "元素"
    ) -> bool:
        """检查元素数量是否符合预期.

        Args:
            page: 页面对象
            selector: 选择器
            expected_count: 期望数量
            description: 元素描述

        Returns:
            是否符合预期
        """
        actual_count = await page.locator(selector).count()
        if actual_count == expected_count:
            logger.debug(f"   ✓ {description}数量正确: {actual_count}")
            return True
        else:
            logger.warning(
                f"   ⚠️ {description}数量不符: 期望 {expected_count}, 实际 {actual_count}"
            )
            return False


# 通用选择器库（用于缺失选择器的临时fallback）


class GenericSelectors:
    """通用选择器库.

    为缺少具体选择器的步骤提供通用fallback选择器。
    """

    @staticmethod
    def button(text: str) -> list[str]:
        """按钮选择器（多fallback）.

        Args:
            text: 按钮文本

        Returns:
            选择器列表
        """
        return [
            f"button:has-text('{text}')",
            f"button:contains('{text}')",
            f"[role='button']:has-text('{text}')",
            f"a:has-text('{text}')",
            f".btn:has-text('{text}')",
        ]

    @staticmethod
    def input(keyword: str) -> list[str]:
        """输入框选择器.

        Args:
            keyword: 关键词

        Returns:
            选择器列表
        """
        return [
            f"input[placeholder*='{keyword}']",
            f"input[name*='{keyword}']",
            f"input[aria-label*='{keyword}']",
            f"textarea[placeholder*='{keyword}']",
        ]

    @staticmethod
    def select(keyword: str) -> list[str]:
        """下拉框选择器.

        Args:
            keyword: 关键词

        Returns:
            选择器列表
        """
        return [
            f"select[name*='{keyword}']",
            f"[role='combobox']:has-text('{keyword}')",
            f".select:has-text('{keyword}')",
            f"[aria-label*='{keyword}']",
        ]

    @staticmethod
    def checkbox(keyword: str = "") -> list[str]:
        """复选框选择器.

        Args:
            keyword: 关键词（可选）

        Returns:
            选择器列表
        """
        if keyword:
            return [
                f"input[type='checkbox'][aria-label*='{keyword}']",
                f"input[type='checkbox'][name*='{keyword}']",
                f"[role='checkbox']:has-text('{keyword}')",
            ]
        else:
            return [
                "input[type='checkbox']",
                "[role='checkbox']",
            ]

    @staticmethod
    async def try_click_with_fallbacks(
        page: Page, selectors: list[str], description: str = "元素", timeout: int = 3000
    ) -> bool:
        """尝试使用fallback选择器点击元素.

        Args:
            page: 页面对象
            selectors: 选择器列表（按优先级）
            description: 元素描述
            timeout: 单个选择器的超时时间（毫秒）

        Returns:
            是否点击成功
        """
        for i, selector in enumerate(selectors):
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=timeout):
                    await element.click(timeout=timeout)
                    logger.debug(f"   ✓ {description}点击成功 (使用选择器 #{i + 1})")
                    return True
            except Exception as e:
                logger.debug(f"   → 选择器 #{i + 1} 失败: {str(e)[:50]}")
                continue

        logger.warning(f"   ⚠️ {description}点击失败 (所有{len(selectors)}个选择器都失败)")
        return False


# 导出所有工具
__all__ = [
    "retry_on_failure",
    "performance_monitor",
    "enhanced_error_handler",
    "take_error_screenshot",
    "StepValidator",
    "GenericSelectors",
]
