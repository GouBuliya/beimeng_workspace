"""
@PURPOSE: 断点恢复管理器 - 支持工作流失败后从断点恢复
@OUTLINE:
  - @dataclass WorkflowCheckpoint: 工作流检查点数据结构
  - class CheckpointManager: 断点管理器
    - async def save_checkpoint(): 保存检查点
    - async def load_checkpoint(): 加载检查点
    - def should_skip_stage(): 判断是否跳过已完成阶段
    - async def mark_stage_complete(): 标记阶段完成
    - async def mark_stage_failed(): 标记阶段失败
    - async def clear_checkpoint(): 清除检查点
    - def get_resume_info(): 获取恢复信息
@GOTCHAS:
  - 检查点文件需要定期清理
  - 断点恢复依赖数据的可序列化
  - 并发访问需要考虑锁机制
@DEPENDENCIES:
  - 外部: loguru
  - 内部: 无
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


@dataclass
class StageCheckpoint:
    """单个阶段的检查点数据"""

    name: str
    status: str  # pending, in_progress, completed, failed
    start_time: str | None = None
    end_time: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    retry_count: int = 0


@dataclass
class WorkflowCheckpoint:
    """工作流检查点

    包含工作流的完整状态信息,用于失败后恢复.

    Attributes:
        workflow_id: 工作流唯一标识
        workflow_type: 工作流类型(如 "complete_publish")
        current_stage: 当前执行的阶段名称
        stages: 各阶段的检查点数据
        global_data: 跨阶段共享的数据
        retry_count: 整体重试次数
        last_error: 最后一次错误信息
        created_at: 创建时间
        updated_at: 最后更新时间
    """

    workflow_id: str
    workflow_type: str = "complete_publish"
    current_stage: str = ""
    stages: dict[str, StageCheckpoint] = field(default_factory=dict)
    global_data: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    last_error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def completed_stages(self) -> list[str]:
        """已完成的阶段列表"""
        return [name for name, stage in self.stages.items() if stage.status == "completed"]

    @property
    def failed_stages(self) -> list[str]:
        """失败的阶段列表"""
        return [name for name, stage in self.stages.items() if stage.status == "failed"]

    @property
    def is_resumable(self) -> bool:
        """是否可以恢复"""
        # 有完成的阶段且有未完成的阶段
        return bool(self.completed_stages) and bool(
            set(self.stages.keys()) - set(self.completed_stages)
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化的字典"""
        data = asdict(self)
        # 手动处理嵌套的 dataclass
        data["stages"] = {name: asdict(stage) for name, stage in self.stages.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowCheckpoint:
        """从字典创建实例"""
        # 处理嵌套的 stages
        stages_data = data.pop("stages", {})
        stages = {name: StageCheckpoint(**stage_data) for name, stage_data in stages_data.items()}
        return cls(stages=stages, **data)


class CheckpointManager:
    """断点管理器 - 支持工作流失败后从断点恢复

    功能:
    1. 自动保存检查点到磁盘
    2. 支持从检查点恢复
    3. 跟踪各阶段执行状态
    4. 管理跨阶段共享数据

    Examples:
        >>> manager = CheckpointManager("workflow_12345")
        >>> await manager.save_checkpoint("stage1", {"products": [...]})
        >>>
        >>> # 恢复时
        >>> checkpoint = await manager.load_checkpoint()
        >>> if checkpoint and checkpoint.is_resumable:
        ...     logger.info(f"从 {checkpoint.current_stage} 恢复")
    """

    CHECKPOINT_DIR = Path("data/checkpoints")
    CHECKPOINT_RETENTION_HOURS = 24  # 检查点保留时间

    def __init__(
        self,
        workflow_id: str,
        workflow_type: str = "complete_publish",
        checkpoint_dir: Path | str | None = None,
    ):
        """初始化检查点管理器

        Args:
            workflow_id: 工作流唯一标识
            workflow_type: 工作流类型
            checkpoint_dir: 检查点存储目录(可选)
        """
        self.workflow_id = workflow_id
        self.workflow_type = workflow_type

        if checkpoint_dir:
            self.checkpoint_dir = Path(checkpoint_dir)
        else:
            self.checkpoint_dir = self.CHECKPOINT_DIR

        self.checkpoint_file = self.checkpoint_dir / f"{workflow_id}.json"
        self.checkpoint: WorkflowCheckpoint | None = None
        self._lock = asyncio.Lock()

    async def save_checkpoint(
        self,
        stage: str,
        stage_data: dict[str, Any] | None = None,
        *,
        status: str = "in_progress",
        global_data: dict[str, Any] | None = None,
    ) -> None:
        """保存检查点

        Args:
            stage: 阶段名称
            stage_data: 阶段相关数据
            status: 阶段状态 (pending, in_progress, completed, failed)
            global_data: 跨阶段共享数据(会合并到现有数据)
        """
        async with self._lock:
            # 初始化或更新检查点
            if self.checkpoint is None:
                self.checkpoint = WorkflowCheckpoint(
                    workflow_id=self.workflow_id,
                    workflow_type=self.workflow_type,
                )

            # 更新当前阶段
            self.checkpoint.current_stage = stage
            self.checkpoint.updated_at = datetime.now().isoformat()

            # 创建或更新阶段检查点
            if stage not in self.checkpoint.stages:
                self.checkpoint.stages[stage] = StageCheckpoint(
                    name=stage,
                    status=status,
                    start_time=datetime.now().isoformat(),
                )

            stage_checkpoint = self.checkpoint.stages[stage]
            stage_checkpoint.status = status

            if stage_data:
                stage_checkpoint.data.update(stage_data)

            if status in ("completed", "failed"):
                stage_checkpoint.end_time = datetime.now().isoformat()

            # 更新全局数据
            if global_data:
                self.checkpoint.global_data.update(global_data)

            # 写入磁盘
            await self._write_checkpoint()

            logger.debug(f"检查点已保存: {stage} ({status})")

    async def mark_stage_complete(
        self,
        stage: str,
        stage_data: dict[str, Any] | None = None,
    ) -> None:
        """标记阶段完成

        Args:
            stage: 阶段名称
            stage_data: 阶段产出数据
        """
        await self.save_checkpoint(stage, stage_data, status="completed")
        logger.info(f"✓ 阶段完成: {stage}")

    async def mark_stage_failed(
        self,
        stage: str,
        error: str | Exception,
    ) -> None:
        """标记阶段失败

        Args:
            stage: 阶段名称
            error: 错误信息或异常
        """
        async with self._lock:
            if self.checkpoint is None:
                await self.save_checkpoint(stage, status="failed")

            error_str = str(error)
            self.checkpoint.last_error = error_str

            if stage in self.checkpoint.stages:
                self.checkpoint.stages[stage].status = "failed"
                self.checkpoint.stages[stage].error = error_str
                self.checkpoint.stages[stage].end_time = datetime.now().isoformat()

            await self._write_checkpoint()

        logger.error(f"✗ 阶段失败: {stage} - {error_str}")

    async def increment_retry(self, stage: str | None = None) -> int:
        """增加重试计数

        Args:
            stage: 阶段名称(为空则增加全局计数)

        Returns:
            当前重试次数
        """
        async with self._lock:
            if self.checkpoint is None:
                return 0

            if stage and stage in self.checkpoint.stages:
                self.checkpoint.stages[stage].retry_count += 1
                count = self.checkpoint.stages[stage].retry_count
            else:
                self.checkpoint.retry_count += 1
                count = self.checkpoint.retry_count

            await self._write_checkpoint()
            return count

    async def load_checkpoint(self) -> WorkflowCheckpoint | None:
        """加载检查点

        Returns:
            检查点数据,如果不存在则返回 None
        """
        if not self.checkpoint_file.exists():
            logger.debug(f"检查点文件不存在: {self.checkpoint_file}")
            return None

        try:
            async with self._lock:
                data = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
                self.checkpoint = WorkflowCheckpoint.from_dict(data)

                logger.info(
                    f"已加载检查点: {self.workflow_id}, "
                    f"当前阶段: {self.checkpoint.current_stage}, "
                    f"已完成: {self.checkpoint.completed_stages}"
                )

                return self.checkpoint
        except json.JSONDecodeError as e:
            logger.error(f"检查点文件格式错误: {e}")
            return None
        except Exception as e:
            logger.error(f"加载检查点失败: {e}")
            return None

    def should_skip_stage(self, stage: str) -> bool:
        """判断是否跳过已完成的阶段

        Args:
            stage: 阶段名称

        Returns:
            是否应该跳过
        """
        if self.checkpoint is None:
            return False

        return stage in self.checkpoint.completed_stages

    def get_stage_data(self, stage: str) -> dict[str, Any]:
        """获取阶段数据

        Args:
            stage: 阶段名称

        Returns:
            阶段数据字典
        """
        if self.checkpoint is None:
            return {}

        if stage not in self.checkpoint.stages:
            return {}

        return self.checkpoint.stages[stage].data.copy()

    def get_global_data(self) -> dict[str, Any]:
        """获取全局共享数据

        Returns:
            全局数据字典
        """
        if self.checkpoint is None:
            return {}

        return self.checkpoint.global_data.copy()

    def get_resume_info(self) -> dict[str, Any]:
        """获取恢复信息摘要

        Returns:
            恢复信息字典
        """
        if self.checkpoint is None:
            return {
                "has_checkpoint": False,
                "resumable": False,
            }

        return {
            "has_checkpoint": True,
            "resumable": self.checkpoint.is_resumable,
            "workflow_id": self.checkpoint.workflow_id,
            "current_stage": self.checkpoint.current_stage,
            "completed_stages": self.checkpoint.completed_stages,
            "failed_stages": self.checkpoint.failed_stages,
            "retry_count": self.checkpoint.retry_count,
            "last_error": self.checkpoint.last_error,
            "created_at": self.checkpoint.created_at,
            "updated_at": self.checkpoint.updated_at,
        }

    async def clear_checkpoint(self) -> bool:
        """清除检查点

        Returns:
            是否成功清除
        """
        async with self._lock:
            try:
                if self.checkpoint_file.exists():
                    self.checkpoint_file.unlink()
                self.checkpoint = None
                logger.info(f"检查点已清除: {self.workflow_id}")
                return True
            except Exception as e:
                logger.error(f"清除检查点失败: {e}")
                return False

    async def _write_checkpoint(self) -> None:
        """写入检查点到磁盘"""
        if self.checkpoint is None:
            return

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        try:
            content = json.dumps(
                self.checkpoint.to_dict(),
                ensure_ascii=False,
                indent=2,
            )
            self.checkpoint_file.write_text(content, encoding="utf-8")
        except Exception as e:
            logger.error(f"写入检查点失败: {e}")

    @classmethod
    async def cleanup_old_checkpoints(
        cls,
        checkpoint_dir: Path | None = None,
        retention_hours: int | None = None,
    ) -> int:
        """清理过期的检查点文件

        Args:
            checkpoint_dir: 检查点目录
            retention_hours: 保留时间(小时)

        Returns:
            清理的文件数量
        """
        target_dir = checkpoint_dir or cls.CHECKPOINT_DIR
        retention = retention_hours or cls.CHECKPOINT_RETENTION_HOURS

        if not target_dir.exists():
            return 0

        cutoff_time = datetime.now().timestamp() - (retention * 3600)
        cleaned = 0

        for checkpoint_file in target_dir.glob("*.json"):
            try:
                if checkpoint_file.stat().st_mtime < cutoff_time:
                    checkpoint_file.unlink()
                    cleaned += 1
                    logger.debug(f"已清理过期检查点: {checkpoint_file.name}")
            except Exception as e:
                logger.warning(f"清理检查点失败 {checkpoint_file}: {e}")

        if cleaned > 0:
            logger.info(f"已清理 {cleaned} 个过期检查点")

        return cleaned

    @classmethod
    def list_checkpoints(
        cls,
        checkpoint_dir: Path | None = None,
    ) -> list[dict[str, Any]]:
        """列出所有检查点

        Args:
            checkpoint_dir: 检查点目录

        Returns:
            检查点信息列表
        """
        target_dir = checkpoint_dir or cls.CHECKPOINT_DIR

        if not target_dir.exists():
            return []

        checkpoints = []

        for checkpoint_file in target_dir.glob("*.json"):
            try:
                data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
                checkpoints.append(
                    {
                        "file": checkpoint_file.name,
                        "workflow_id": data.get("workflow_id"),
                        "workflow_type": data.get("workflow_type"),
                        "current_stage": data.get("current_stage"),
                        "updated_at": data.get("updated_at"),
                        "size_bytes": checkpoint_file.stat().st_size,
                    }
                )
            except Exception as e:
                logger.warning(f"读取检查点信息失败 {checkpoint_file}: {e}")

        return sorted(checkpoints, key=lambda x: x.get("updated_at", ""), reverse=True)


# 便捷函数
def get_checkpoint_manager(
    workflow_id: str,
    workflow_type: str = "complete_publish",
) -> CheckpointManager:
    """获取检查点管理器实例

    Args:
        workflow_id: 工作流唯一标识
        workflow_type: 工作流类型

    Returns:
        CheckpointManager 实例
    """
    return CheckpointManager(workflow_id, workflow_type)


# 导出
__all__ = [
    "CheckpointManager",
    "StageCheckpoint",
    "WorkflowCheckpoint",
    "get_checkpoint_manager",
]
