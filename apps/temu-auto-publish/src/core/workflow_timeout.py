"""
@PURPOSE: 工作流超时控制器 - 为各阶段提供超时保护,防止工作流卡死
@OUTLINE:
  - class WorkflowTimeoutError: 工作流超时异常
  - @asynccontextmanager with_stage_timeout(): 阶段超时上下文管理器
  - DEFAULT_STAGE_TIMEOUTS: 默认超时配置(保守模式:总计60分钟)
  - get_timeout_config(): 获取超时配置
@GOTCHAS:
  - 超时后会触发 on_timeout 回调,用于紧急清理
  - 超时时间可通过配置文件覆盖
@DEPENDENCIES:
  - 外部: asyncio
"""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger


class WorkflowTimeoutError(Exception):
    """工作流超时错误.

    Attributes:
        stage: 超时的阶段名称
        timeout_seconds: 超时时间(秒)
        started_at: 阶段开始时间
    """

    def __init__(self, stage: str, timeout_seconds: float, started_at: datetime | None = None):
        self.stage = stage
        self.timeout_seconds = timeout_seconds
        self.started_at = started_at or datetime.now()
        super().__init__(f"工作流阶段 '{stage}' 执行超时 ({timeout_seconds}s)")


@dataclass
class TimeoutConfig:
    """超时配置.

    Attributes:
        stage1_first_edit: 首次编辑超时(秒)
        stage2_claim: 认领超时(秒)
        stage3_batch_edit: 批量编辑超时(秒)
        stage4_publish: 发布超时(秒)
        workflow_total: 工作流总超时(秒)
    """

    stage1_first_edit: int = 900  # 15分钟(保守配置)
    stage2_claim: int = 600  # 10分钟
    stage3_batch_edit: int = 1200  # 20分钟
    stage4_publish: int = 600  # 10分钟
    workflow_total: int = 3600  # 60分钟总超时

    def get(self, stage_name: str, default: int = 600) -> int:
        """获取指定阶段的超时时间."""
        mapping = {
            "stage1_first_edit": self.stage1_first_edit,
            "stage2_claim": self.stage2_claim,
            "stage3_batch_edit": self.stage3_batch_edit,
            "stage4_publish": self.stage4_publish,
            "workflow_total": self.workflow_total,
        }
        return mapping.get(stage_name, default)


# 默认超时配置(保守模式)
DEFAULT_STAGE_TIMEOUTS = TimeoutConfig()


def get_timeout_config(custom_config: dict[str, int] | None = None) -> TimeoutConfig:
    """获取超时配置.

    Args:
        custom_config: 自定义配置字典,可覆盖默认值

    Returns:
        TimeoutConfig 实例
    """
    if custom_config is None:
        return DEFAULT_STAGE_TIMEOUTS

    return TimeoutConfig(
        stage1_first_edit=custom_config.get(
            "stage1_first_edit", DEFAULT_STAGE_TIMEOUTS.stage1_first_edit
        ),
        stage2_claim=custom_config.get("stage2_claim", DEFAULT_STAGE_TIMEOUTS.stage2_claim),
        stage3_batch_edit=custom_config.get(
            "stage3_batch_edit", DEFAULT_STAGE_TIMEOUTS.stage3_batch_edit
        ),
        stage4_publish=custom_config.get("stage4_publish", DEFAULT_STAGE_TIMEOUTS.stage4_publish),
        workflow_total=custom_config.get("workflow_total", DEFAULT_STAGE_TIMEOUTS.workflow_total),
    )


@asynccontextmanager
async def with_stage_timeout(
    stage_name: str,
    timeout_seconds: float,
    on_timeout: Callable[[], Awaitable[Any] | Any] | None = None,
):
    """阶段超时上下文管理器.

    在指定时间内未完成则抛出 WorkflowTimeoutError.

    Args:
        stage_name: 阶段名称(用于日志和错误信息)
        timeout_seconds: 超时时间(秒)
        on_timeout: 超时时的回调函数(可选),用于紧急清理

    Raises:
        WorkflowTimeoutError: 超时时抛出

    Examples:
        >>> async with with_stage_timeout("stage1_first_edit", 600):
        ...     await do_first_edit()

        >>> async with with_stage_timeout("stage1", 600, on_timeout=cleanup):
        ...     await do_work()
    """
    started_at = datetime.now()
    logger.info(f"[TIMEOUT] 阶段 '{stage_name}' 开始执行,超时限制: {timeout_seconds}s")

    try:
        async with asyncio.timeout(timeout_seconds):
            yield
        elapsed = (datetime.now() - started_at).total_seconds()
        logger.debug(f"[TIMEOUT] 阶段 '{stage_name}' 完成,耗时: {elapsed:.1f}s")
    except TimeoutError:
        elapsed = (datetime.now() - started_at).total_seconds()
        logger.error(
            f"[TIMEOUT] 阶段 '{stage_name}' 执行超时!"
            f"限制: {timeout_seconds}s, 实际耗时: {elapsed:.1f}s"
        )

        # 执行超时回调
        if on_timeout is not None:
            try:
                logger.info(f"[TIMEOUT] 执行阶段 '{stage_name}' 的超时清理回调")
                if asyncio.iscoroutinefunction(on_timeout):
                    await on_timeout()
                else:
                    on_timeout()
            except Exception as e:
                logger.warning(f"[TIMEOUT] 超时清理回调执行失败: {e}")

        raise WorkflowTimeoutError(stage_name, timeout_seconds, started_at)


async def run_with_workflow_timeout(
    workflow_func: Callable[..., Awaitable[Any]],
    *args,
    timeout_seconds: float = 3600,
    on_timeout: Callable[[], Awaitable[Any] | Any] | None = None,
    **kwargs,
) -> Any:
    """带总超时的工作流执行器.

    Args:
        workflow_func: 工作流异步函数
        *args: 传递给工作流的位置参数
        timeout_seconds: 总超时时间(秒),默认 3600s(1小时)
        on_timeout: 超时回调函数
        **kwargs: 传递给工作流的关键字参数

    Returns:
        工作流函数的返回值

    Raises:
        WorkflowTimeoutError: 总超时时抛出

    Examples:
        >>> result = await run_with_workflow_timeout(
        ...     my_workflow,
        ...     page,
        ...     config,
        ...     timeout_seconds=1800,
        ...     on_timeout=lambda: browser.close()
        ... )
    """
    async with with_stage_timeout("workflow_total", timeout_seconds, on_timeout):
        return await workflow_func(*args, **kwargs)


# 便捷函数:创建带超时的阶段装饰器
def timeout_stage(
    stage_name: str,
    timeout_config: TimeoutConfig | None = None,
    on_timeout: Callable[[], Awaitable[Any] | Any] | None = None,
):
    """创建带超时的阶段装饰器.

    Args:
        stage_name: 阶段名称
        timeout_config: 超时配置,默认使用 DEFAULT_STAGE_TIMEOUTS
        on_timeout: 超时回调函数

    Returns:
        装饰器函数

    Examples:
        >>> @timeout_stage("stage1_first_edit")
        ... async def do_first_edit(page, products):
        ...     ...
    """
    config = timeout_config or DEFAULT_STAGE_TIMEOUTS

    def decorator(func: Callable[..., Awaitable[Any]]):
        async def wrapper(*args, **kwargs):
            timeout_seconds = config.get(stage_name)
            async with with_stage_timeout(stage_name, timeout_seconds, on_timeout):
                return await func(*args, **kwargs)

        return wrapper

    return decorator
