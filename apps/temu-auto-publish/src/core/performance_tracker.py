"""
@PURPOSE: 性能追踪器核心模块 - 提供层级化的性能监控能力
@OUTLINE:
  - class ExecutionStatus: 执行状态枚举
  - class ActionMetrics: Action 级别指标(最细粒度)
  - class OperationMetrics: Operation 级别指标
  - class StageMetrics: Stage 级别指标
  - class WorkflowMetrics: Workflow 级别指标(根节点)
  - class PerformanceTracker: 核心追踪器类
  - get_tracker(): 获取全局追踪器实例
  - reset_tracker(): 重置全局追踪器
  - track_operation(): Operation 装饰器
  - track_action(): Action 装饰器
@GOTCHAS:
  - PerformanceTracker 是单例模式,使用 get_tracker() 获取
  - 必须先调用 start_workflow() 才能使用 stage/operation/action
  - 装饰器会自动检测同步/异步函数
@DEPENDENCIES:
  - 内部: 无
  - 外部: pydantic, loguru
"""

from __future__ import annotations

import asyncio
import functools
import time
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from loguru import logger
from pydantic import BaseModel, Field, computed_field

# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Any])


class ExecutionStatus(str, Enum):
    """执行状态枚举"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActionMetrics(BaseModel):
    """Action 级别指标 - 代表原子操作(最细粒度)

    例如: 点击按钮,填写表单,等待元素等
    """

    id: str = Field(default_factory=lambda: f"act_{uuid.uuid4().hex[:8]}")
    name: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: datetime | None = None
    end_time: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    parent_operation_id: str | None = None

    @computed_field
    @property
    def duration_ms(self) -> float | None:
        """持续时间(毫秒)"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None

    @computed_field
    @property
    def duration_s(self) -> float | None:
        """持续时间(秒),保留2位小数"""
        if self.duration_ms is not None:
            return round(self.duration_ms / 1000, 2)
        return None


class OperationMetrics(BaseModel):
    """Operation 级别指标 - 代表业务操作

    例如: 编辑单个产品,执行一个批量编辑步骤
    包含多个 Actions
    """

    id: str = Field(default_factory=lambda: f"op_{uuid.uuid4().hex[:8]}")
    name: str
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: datetime | None = None
    end_time: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    actions: list[ActionMetrics] = Field(default_factory=list)
    parent_stage_id: str | None = None

    @computed_field
    @property
    def duration_ms(self) -> float | None:
        """持续时间(毫秒)"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None

    @computed_field
    @property
    def duration_s(self) -> float | None:
        """持续时间(秒),保留2位小数"""
        if self.duration_ms is not None:
            return round(self.duration_ms / 1000, 2)
        return None

    @computed_field
    @property
    def action_count(self) -> int:
        """Action 数量"""
        return len(self.actions)


class StageMetrics(BaseModel):
    """Stage 级别指标 - 代表工作流阶段

    例如: 首次编辑阶段,认领阶段,批量编辑阶段
    包含多个 Operations
    """

    id: str = Field(default_factory=lambda: f"stg_{uuid.uuid4().hex[:8]}")
    name: str
    display_name: str  # 用于显示的友好名称
    order: int = 0  # 阶段顺序
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: datetime | None = None
    end_time: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    operations: list[OperationMetrics] = Field(default_factory=list)
    parent_workflow_id: str | None = None

    @computed_field
    @property
    def duration_ms(self) -> float | None:
        """持续时间(毫秒)"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None

    @computed_field
    @property
    def duration_s(self) -> float | None:
        """持续时间(秒),保留2位小数"""
        if self.duration_ms is not None:
            return round(self.duration_ms / 1000, 2)
        return None

    @computed_field
    @property
    def operation_count(self) -> int:
        """Operation 数量"""
        return len(self.operations)


class WorkflowMetrics(BaseModel):
    """Workflow 级别指标 - 代表完整工作流执行(根节点)

    例如: temu_publish 完整发布工作流
    包含多个 Stages
    """

    id: str = Field(
        default_factory=lambda: f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )
    name: str = "temu_publish"
    status: ExecutionStatus = ExecutionStatus.PENDING
    start_time: datetime | None = None
    end_time: datetime | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    stages: list[StageMetrics] = Field(default_factory=list)

    @computed_field
    @property
    def duration_ms(self) -> float | None:
        """持续时间(毫秒)"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None

    @computed_field
    @property
    def duration_s(self) -> float | None:
        """持续时间(秒),保留2位小数"""
        if self.duration_ms is not None:
            return round(self.duration_ms / 1000, 2)
        return None

    @computed_field
    @property
    def stage_count(self) -> int:
        """Stage 数量"""
        return len(self.stages)

    def calculate_percentages(self) -> dict[str, float]:
        """计算各阶段时间占比

        Returns:
            dict[str, float]: 阶段名称 -> 占比百分比
        """
        if self.duration_ms is None or self.duration_ms == 0:
            return {}
        result = {}
        for stage in self.stages:
            if stage.duration_ms is not None:
                percentage = (stage.duration_ms / self.duration_ms) * 100
                result[stage.name] = round(percentage, 2)
        return result

    def get_summary(self) -> dict[str, Any]:
        """获取汇总数据

        Returns:
            dict: 包含总耗时,各阶段耗时和占比的汇总信息
        """
        percentages = self.calculate_percentages()
        stages_summary = []
        for stage in sorted(self.stages, key=lambda s: s.order):
            stage_info = {
                "name": stage.name,
                "display_name": stage.display_name,
                "order": stage.order,
                "duration_s": stage.duration_s,
                "percentage": percentages.get(stage.name, 0),
                "status": stage.status.value,
                "operation_count": stage.operation_count,
            }
            stages_summary.append(stage_info)

        return {
            "workflow_id": self.id,
            "total_duration_s": self.duration_s,
            "status": self.status.value,
            "stage_count": self.stage_count,
            "stages": stages_summary,
            "percentages": percentages,
        }


class PerformanceTracker:
    """性能追踪器 - 统一的性能监控入口

    提供三种使用方式:
    1. 上下文管理器: async with tracker.stage("name"):
    2. 装饰器: @tracker.track_operation("name")
    3. 显式调用: tracker.start_workflow(); tracker.end_workflow()

    Example:
        >>> tracker = PerformanceTracker()
        >>> tracker.start_workflow("my_workflow")
        >>> async with tracker.stage("stage1", "第一阶段", order=1):
        ...     async with tracker.operation("op1"):
        ...         await some_async_task()
        >>> tracker.end_workflow(success=True)
        >>> print(tracker.to_json())
    """

    def __init__(self, workflow_name: str = "temu_publish"):
        """初始化性能追踪器

        Args:
            workflow_name: 工作流名称
        """
        self.workflow_name = workflow_name
        self.workflow: WorkflowMetrics | None = None
        self._current_stage: StageMetrics | None = None
        self._current_operation: OperationMetrics | None = None
        self._current_action: ActionMetrics | None = None
        self._perf_counters: dict[str, float] = {}  # 高精度计时器

    # ========== Workflow 级别 ==========

    def start_workflow(self, workflow_id: str | None = None) -> str:
        """开始工作流追踪

        Args:
            workflow_id: 可选的工作流ID,不提供则自动生成

        Returns:
            str: 工作流ID
        """
        if workflow_id:
            self.workflow = WorkflowMetrics(id=workflow_id, name=self.workflow_name)
        else:
            self.workflow = WorkflowMetrics(name=self.workflow_name)

        self.workflow.status = ExecutionStatus.RUNNING
        self.workflow.start_time = datetime.now()
        self._perf_counters["workflow"] = time.perf_counter()

        logger.info(f"[Performance] 工作流开始: {self.workflow.id}")
        return self.workflow.id

    def end_workflow(self, success: bool = True, error: str | None = None) -> None:
        """结束工作流追踪

        Args:
            success: 是否成功
            error: 错误信息(如果失败)
        """
        if not self.workflow:
            logger.warning("[Performance] 未找到活跃的工作流")
            return

        self.workflow.end_time = datetime.now()
        self.workflow.status = ExecutionStatus.SUCCESS if success else ExecutionStatus.FAILED
        if error:
            self.workflow.error = error

        # 计算精确耗时
        if "workflow" in self._perf_counters:
            elapsed = time.perf_counter() - self._perf_counters["workflow"]
            logger.info(
                f"[Performance] 工作流结束: {self.workflow.id} - "
                f"耗时: {elapsed:.2f}s - 状态: {self.workflow.status.value}"
            )

    # ========== Stage 级别 ==========

    @asynccontextmanager
    async def stage(self, name: str, display_name: str, order: int = 0):
        """Stage 级别的异步上下文管理器

        Args:
            name: 阶段名称(用于标识,如 "stage1_first_edit")
            display_name: 显示名称(用于报告,如 "首次编辑")
            order: 阶段顺序(用于排序)

        Example:
            >>> async with tracker.stage("stage1", "首次编辑", order=1):
            ...     await do_first_edit()
        """
        if not self.workflow:
            logger.warning("[Performance] 未找到活跃的工作流,请先调用 start_workflow()")
            yield
            return

        stage = StageMetrics(
            name=name,
            display_name=display_name,
            order=order,
            parent_workflow_id=self.workflow.id,
        )
        stage.status = ExecutionStatus.RUNNING
        stage.start_time = datetime.now()
        self._current_stage = stage
        self._perf_counters[f"stage_{name}"] = time.perf_counter()

        logger.info(f"[Performance] ▶ Stage {order}: {display_name}")

        try:
            yield stage
            stage.status = ExecutionStatus.SUCCESS
        except Exception as e:
            stage.status = ExecutionStatus.FAILED
            stage.error = str(e)
            raise
        finally:
            stage.end_time = datetime.now()
            elapsed = time.perf_counter() - self._perf_counters.get(f"stage_{name}", 0)
            logger.info(f"[Performance]   └─ {display_name} 完成 ({elapsed:.2f}s)")
            self.workflow.stages.append(stage)
            self._current_stage = None

    @contextmanager
    def stage_sync(self, name: str, display_name: str, order: int = 0):
        """Stage 级别的同步上下文管理器"""
        if not self.workflow:
            logger.warning("[Performance] 未找到活跃的工作流")
            yield
            return

        stage = StageMetrics(
            name=name,
            display_name=display_name,
            order=order,
            parent_workflow_id=self.workflow.id,
        )
        stage.status = ExecutionStatus.RUNNING
        stage.start_time = datetime.now()
        self._current_stage = stage
        self._perf_counters[f"stage_{name}"] = time.perf_counter()

        logger.info(f"[Performance] ▶ Stage {order}: {display_name}")

        try:
            yield stage
            stage.status = ExecutionStatus.SUCCESS
        except Exception as e:
            stage.status = ExecutionStatus.FAILED
            stage.error = str(e)
            raise
        finally:
            stage.end_time = datetime.now()
            elapsed = time.perf_counter() - self._perf_counters.get(f"stage_{name}", 0)
            logger.info(f"[Performance]   └─ {display_name} 完成 ({elapsed:.2f}s)")
            self.workflow.stages.append(stage)
            self._current_stage = None

    # ========== Operation 级别 ==========

    @asynccontextmanager
    async def operation(self, name: str, **metadata):
        """Operation 级别的异步上下文管理器

        Args:
            name: 操作名称
            **metadata: 附加元数据

        Example:
            >>> async with tracker.operation("edit_product_1", product_id=123):
            ...     await edit_product()
        """
        if not self._current_stage:
            logger.debug(f"[Performance] 未在 Stage 内,跳过 Operation 记录: {name}")
            yield
            return

        op = OperationMetrics(
            name=name,
            metadata=metadata,
            parent_stage_id=self._current_stage.id,
        )
        op.status = ExecutionStatus.RUNNING
        op.start_time = datetime.now()
        self._current_operation = op
        self._perf_counters[f"op_{name}"] = time.perf_counter()

        logger.debug(f"[Performance]   ├─ {name}")

        try:
            yield op
            op.status = ExecutionStatus.SUCCESS
        except Exception as e:
            op.status = ExecutionStatus.FAILED
            op.error = str(e)
            raise
        finally:
            op.end_time = datetime.now()
            elapsed = time.perf_counter() - self._perf_counters.get(f"op_{name}", 0)
            logger.info(f"[Performance]   ├─ {name} ({elapsed:.2f}s)")
            self._current_stage.operations.append(op)
            self._current_operation = None

    @contextmanager
    def operation_sync(self, name: str, **metadata):
        """Operation 级别的同步上下文管理器"""
        if not self._current_stage:
            logger.debug(f"[Performance] 未在 Stage 内,跳过 Operation 记录: {name}")
            yield
            return

        op = OperationMetrics(
            name=name,
            metadata=metadata,
            parent_stage_id=self._current_stage.id,
        )
        op.status = ExecutionStatus.RUNNING
        op.start_time = datetime.now()
        self._current_operation = op
        self._perf_counters[f"op_{name}"] = time.perf_counter()

        logger.debug(f"[Performance]   ├─ {name}")

        try:
            yield op
            op.status = ExecutionStatus.SUCCESS
        except Exception as e:
            op.status = ExecutionStatus.FAILED
            op.error = str(e)
            raise
        finally:
            op.end_time = datetime.now()
            elapsed = time.perf_counter() - self._perf_counters.get(f"op_{name}", 0)
            logger.info(f"[Performance]   ├─ {name} ({elapsed:.2f}s)")
            self._current_stage.operations.append(op)
            self._current_operation = None

    def track_operation(self, name: str, **metadata) -> Callable[[F], F]:
        """Operation 级别的装饰器

        Args:
            name: 操作名称
            **metadata: 附加元数据

        Example:
            >>> @tracker.track_operation("batch_edit")
            ... async def batch_edit(self):
            ...     pass
        """

        def decorator(func: F) -> F:
            if asyncio.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    async with self.operation(name, **metadata):
                        return await func(*args, **kwargs)

                return async_wrapper  # type: ignore
            else:

                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.operation_sync(name, **metadata):
                        return func(*args, **kwargs)

                return sync_wrapper  # type: ignore

        return decorator

    # ========== Action 级别 ==========

    @asynccontextmanager
    async def action(self, name: str, **metadata):
        """Action 级别的异步上下文管理器

        Args:
            name: 动作名称
            **metadata: 附加元数据

        Example:
            >>> async with tracker.action("click_submit_button"):
            ...     await page.click("#submit")
        """
        if not self._current_operation:
            logger.debug(f"[Performance] 未在 Operation 内,跳过 Action 记录: {name}")
            yield
            return

        act = ActionMetrics(
            name=name,
            metadata=metadata,
            parent_operation_id=self._current_operation.id,
        )
        act.status = ExecutionStatus.RUNNING
        act.start_time = datetime.now()
        self._current_action = act
        self._perf_counters[f"act_{name}"] = time.perf_counter()

        try:
            yield act
            act.status = ExecutionStatus.SUCCESS
        except Exception as e:
            act.status = ExecutionStatus.FAILED
            act.error = str(e)
            raise
        finally:
            act.end_time = datetime.now()
            elapsed = time.perf_counter() - self._perf_counters.get(f"act_{name}", 0)
            logger.debug(f"[Performance]   │  ├─ {name} ({elapsed:.3f}s)")
            self._current_operation.actions.append(act)
            self._current_action = None

    @contextmanager
    def action_sync(self, name: str, **metadata):
        """Action 级别的同步上下文管理器"""
        if not self._current_operation:
            logger.debug(f"[Performance] 未在 Operation 内,跳过 Action 记录: {name}")
            yield
            return

        act = ActionMetrics(
            name=name,
            metadata=metadata,
            parent_operation_id=self._current_operation.id,
        )
        act.status = ExecutionStatus.RUNNING
        act.start_time = datetime.now()
        self._current_action = act
        self._perf_counters[f"act_{name}"] = time.perf_counter()

        try:
            yield act
            act.status = ExecutionStatus.SUCCESS
        except Exception as e:
            act.status = ExecutionStatus.FAILED
            act.error = str(e)
            raise
        finally:
            act.end_time = datetime.now()
            elapsed = time.perf_counter() - self._perf_counters.get(f"act_{name}", 0)
            logger.debug(f"[Performance]   │  ├─ {name} ({elapsed:.3f}s)")
            self._current_operation.actions.append(act)
            self._current_action = None

    def track_action(self, name: str, **metadata) -> Callable[[F], F]:
        """Action 级别的装饰器

        Args:
            name: 动作名称
            **metadata: 附加元数据

        Example:
            >>> @tracker.track_action("step_01_title")
            ... async def step_01_title(self):
            ...     pass
        """

        def decorator(func: F) -> F:
            if asyncio.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    async with self.action(name, **metadata):
                        return await func(*args, **kwargs)

                return async_wrapper  # type: ignore
            else:

                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.action_sync(name, **metadata):
                        return func(*args, **kwargs)

                return sync_wrapper  # type: ignore

        return decorator

    # ========== 数据导出 ==========

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式

        Returns:
            dict: 完整的工作流指标数据
        """
        if not self.workflow:
            return {}
        return self.workflow.model_dump(mode="json")

    def to_json(self, indent: int = 2) -> str:
        """转换为 JSON 字符串

        Args:
            indent: 缩进空格数

        Returns:
            str: JSON 格式的指标数据
        """
        if not self.workflow:
            return "{}"
        return self.workflow.model_dump_json(indent=indent)

    def save_to_file(self, path: Path | None = None) -> Path:
        """保存到文件

        Args:
            path: 文件路径,不提供则使用默认路径

        Returns:
            Path: 保存的文件路径
        """
        if not self.workflow:
            raise ValueError("没有可保存的工作流数据")

        if path is None:
            # 默认保存到 data/metrics/ 目录
            metrics_dir = Path(__file__).parent.parent.parent / "data" / "metrics"
            metrics_dir.mkdir(parents=True, exist_ok=True)
            path = metrics_dir / f"{self.workflow.id}.json"

        path.write_text(self.to_json(), encoding="utf-8")
        logger.info(f"[Performance] 指标已保存到: {path}")
        return path

    def get_summary(self) -> dict[str, Any]:
        """获取汇总数据

        Returns:
            dict: 汇总信息,包含各阶段耗时和占比
        """
        if not self.workflow:
            return {}
        return self.workflow.get_summary()

    def reset(self) -> None:
        """重置追踪器状态"""
        self.workflow = None
        self._current_stage = None
        self._current_operation = None
        self._current_action = None
        self._perf_counters.clear()


# ========== 全局单例 ==========

_global_tracker: PerformanceTracker | None = None


def get_tracker(workflow_name: str = "temu_publish") -> PerformanceTracker:
    """获取全局性能追踪器实例

    Args:
        workflow_name: 工作流名称

    Returns:
        PerformanceTracker: 全局追踪器实例
    """
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = PerformanceTracker(workflow_name)
    return _global_tracker


def reset_tracker(workflow_name: str = "temu_publish") -> PerformanceTracker:
    """重置全局性能追踪器

    Args:
        workflow_name: 工作流名称

    Returns:
        PerformanceTracker: 新的追踪器实例
    """
    global _global_tracker
    _global_tracker = PerformanceTracker(workflow_name)
    return _global_tracker


# ========== 便捷装饰器(使用全局追踪器)==========


def track_operation(name: str, **metadata) -> Callable[[F], F]:
    """便捷的 Operation 装饰器(使用全局追踪器)

    Example:
        >>> @track_operation("my_operation")
        ... async def my_func():
        ...     pass
    """
    return get_tracker().track_operation(name, **metadata)


def track_action(name: str, **metadata) -> Callable[[F], F]:
    """便捷的 Action 装饰器(使用全局追踪器)

    Example:
        >>> @track_action("my_action")
        ... async def my_func():
        ...     pass
    """
    return get_tracker().track_action(name, **metadata)
