"""
@PURPOSE: FastAPI 背后的工作流调度与文件存储服务
@OUTLINE:
  - SelectionFileStore: 负责持久化上传的选品表
  - WorkflowTaskManager: 管理 Temu 工作流运行、状态与日志
  - create_task_manager(): 工厂函数, 供 API 层复用
"""

from __future__ import annotations

import re
import sys
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import BinaryIO

from loguru import logger
from src.workflows.complete_publish_workflow import CompletePublishWorkflow

from .models import LogChunk, RunState, RunStatus, WorkflowOptions

APP_ROOT = Path(__file__).resolve().parents[1]


def _resolve_upload_dir() -> Path:
    if getattr(sys, "frozen", False):
        base_dir = Path.home() / "TemuWebPanel" / "input"
    else:
        base_dir = APP_ROOT / "data" / "input" / "web_panel"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


UPLOAD_DIR = _resolve_upload_dir()


class SelectionFileStore:
    """负责管理 Web Panel 上传的选品表文件."""

    def __init__(self, base_dir: Path = UPLOAD_DIR) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store(self, filename: str | None, stream: BinaryIO) -> Path:
        """保存上传的文件并返回最终路径."""

        safe_stem = self._build_safe_stem(filename)
        suffix = Path(filename or "").suffix or ".xlsx"
        target = self.base_dir / f"{safe_stem}{suffix}"
        stream.seek(0)
        with target.open("wb") as buffer:
            chunk = stream.read(1024 * 1024)
            while chunk:
                buffer.write(chunk)
                chunk = stream.read(1024 * 1024)
        logger.info("已保存上传的选品表: %s", target)
        return target

    @staticmethod
    def _build_safe_stem(filename: str | None) -> str:
        stem = Path(filename or "selection").stem or "selection"
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", stem).lower()
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return f"{stem}_{timestamp}"


class WorkflowTaskManager:
    """管理 Temu 完整工作流的运行状态."""

    def __init__(self) -> None:
        self._status = RunStatus()
        self._logs: deque[LogChunk] = deque(maxlen=2000)
        self._log_index = 0
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="temu-web")
        self._future: Future | None = None
        self._log_sink_id: int | None = None

    def start(self, options: WorkflowOptions) -> RunStatus:
        """启动新的工作流运行."""

        with self._lock:
            if self._status.state == RunState.RUNNING:
                raise RuntimeError("已有任务正在运行, 请稍候再试")

            self._status = RunStatus(
                state=RunState.RUNNING,
                message="正在准备浏览器, 请稍等...",
                workflow_id=None,
                started_at=time.time(),
                finished_at=None,
                last_error=None,
            )
            self._logs.clear()
            self._log_index = 0
            self._attach_log_sink()
            self._future = self._executor.submit(self._run_workflow, options)
            return self._status

    def status(self) -> RunStatus:
        """返回当前状态."""

        with self._lock:
            return RunStatus(**self._status.model_dump())

    def logs(self, *, after: int = -1) -> list[LogChunk]:
        """返回指定游标之后的日志."""

        with self._lock:
            return [log for log in self._logs if log.index > after]

    def _run_workflow(self, options: WorkflowOptions) -> None:
        logger.info("Web Panel 启动 Temu 工作流")
        try:
            workflow = CompletePublishWorkflow(**options.as_workflow_kwargs())
            result = workflow.execute()
            self._mark_success(
                workflow_id=result.workflow_id,
                total_success=result.total_success,
                errors=result.errors,
            )
        except Exception as exc:  # pragma: no cover - 运行时错误
            logger.exception("Temu 工作流运行失败: %s", exc)
            self._mark_failure(str(exc))
        finally:
            self._detach_log_sink()

    def _mark_success(self, workflow_id: str, total_success: bool, errors: list[str]) -> None:
        message = "全部步骤完成" if total_success else "流程结束, 但存在告警"
        error_msg = "; ".join(errors) if errors else None
        with self._lock:
            self._status = RunStatus(
                state=RunState.SUCCESS if total_success else RunState.FAILED,
                message=message,
                workflow_id=workflow_id,
                started_at=self._status.started_at,
                finished_at=time.time(),
                last_error=error_msg,
            )

    def _mark_failure(self, error: str) -> None:
        with self._lock:
            self._status = RunStatus(
                state=RunState.FAILED,
                message="运行失败, 请查看日志",
                workflow_id=self._status.workflow_id,
                started_at=self._status.started_at,
                finished_at=time.time(),
                last_error=error,
            )

    def _attach_log_sink(self) -> None:
        if self._log_sink_id is None:
            self._log_sink_id = logger.add(self._on_log, level="INFO")

    def _detach_log_sink(self) -> None:
        if self._log_sink_id is not None:
            logger.remove(self._log_sink_id)
            self._log_sink_id = None

    def _on_log(self, message) -> None:  # type: ignore[override]
        record = message.record
        log_chunk = LogChunk(
            index=self._log_index,
            timestamp=record["time"].timestamp(),
            level=record["level"].name,
            message=record["message"],
        )
        with self._lock:
            self._logs.append(log_chunk)
            self._log_index += 1


def create_task_manager() -> WorkflowTaskManager:
    """创建默认的 WorkflowTaskManager."""

    return WorkflowTaskManager()
