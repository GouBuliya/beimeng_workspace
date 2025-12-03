"""
@PURPOSE: FastAPI 背后的工作流调度与文件存储服务
@OUTLINE:
  - SelectionFileStore: 负责持久化上传的选品表
  - WorkflowTaskManager: 管理 Temu 工作流运行,状态与日志
  - create_task_manager(): 工厂函数, 供 API 层复用
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import sys
import threading
import time
from collections import deque
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import BinaryIO

from config.settings import settings
from loguru import logger
from src.browser.login_controller import LoginController
from src.data_processor.selection_table_queue import (
    SelectionTableEmptyError,
    SelectionTableFormatError,
    SelectionTableQueue,
)
from src.data_processor.selection_table_reader import ProductSelectionRow
from src.utils.selector_hit_recorder import export_selector_report
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
# 移除上限限制，一次性处理所有选品
DEFAULT_BATCH_SIZE = max(1, settings.business.collect_count)


class SelectionFileStore:
    """负责管理 Web Panel 上传的文件资产."""

    def __init__(self, base_dir: Path = UPLOAD_DIR) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        filename: str | None,
        stream: BinaryIO,
        suffix_whitelist: tuple[str, ...] | None = None,
        default_suffix: str = ".xlsx",
        subdir: str | None = None,
    ) -> Path:
        """保存上传的文件并返回最终路径."""

        safe_stem = self._build_safe_stem(filename)
        suffix = Path(filename or "").suffix or default_suffix
        suffix = suffix.lower()
        if suffix_whitelist and suffix not in suffix_whitelist:
            allowed = ", ".join(suffix_whitelist)
            raise ValueError(f"仅支持以下文件类型: {allowed}")

        target_dir = self.base_dir if subdir is None else self.base_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        target = target_dir / f"{safe_stem}{suffix}"
        with contextlib.suppress(AttributeError, OSError):
            stream.seek(0)

        with target.open("wb") as buffer:
            chunk = stream.read(1024 * 1024)
            while chunk:
                buffer.write(chunk)
                chunk = stream.read(1024 * 1024)
        logger.info("已保存上传文件: {}", target)
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
        # 全局复用的登录控制器,避免每次任务都重新登录
        self._login_ctrl: LoginController | None = None

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
        logger.info(
            f"Web Panel 启动 Temu 工作流 ({'单次模式' if options.single_run else '循环模式'})"
        )
        try:
            if options.single_run:
                self._run_single(options)
            else:
                self._run_continuous(options)
        except Exception as exc:  # pragma: no cover - 运行时错误
            logger.exception(f"Temu 工作流运行失败: {exc}")
            self._mark_failure(str(exc))
        finally:
            self._detach_log_sink()
            # 导出选择器命中报告
            try:
                export_selector_report("D:/codespace/beimeng_workspace/data/temp")
            except Exception as exc:
                logger.warning(f"导出选择器命中报告失败: {exc}")

    def _run_single(self, options: WorkflowOptions) -> None:
        """单次运行模式入口,使用 asyncio.run 包装异步流程."""
        asyncio.run(self._run_single_async(options))

    async def _run_single_async(self, options: WorkflowOptions) -> None:
        """单次运行模式的异步实现."""
        # 复用全局登录控制器,避免重复登录
        if self._login_ctrl is None:
            self._login_ctrl = LoginController()

        # 单次运行时使用配置的起始轮次
        result = await self._execute_workflow_async(
            options,
            execution_round=options.start_round,
            login_ctrl=self._login_ctrl,
        )
        self._mark_success(
            workflow_id=result.workflow_id,
            total_success=result.total_success,
            errors=result.errors,
        )

    def _run_continuous(self, options: WorkflowOptions) -> None:
        """循环运行模式入口,使用 asyncio.run 包装整个循环."""
        asyncio.run(self._run_continuous_async(options))

    async def _run_continuous_async(self, options: WorkflowOptions) -> None:
        """循环运行模式的异步实现,所有批次共享同一事件循环."""
        queue = SelectionTableQueue(options.selection_path)
        processed_batches = 0
        # 起始轮次偏移:支持从指定轮次开始(模拟已运行次数)
        start_round_offset = max(0, options.start_round - 1)
        last_workflow_id: str | None = None
        # 复用全局登录控制器,避免重复登录
        if self._login_ctrl is None:
            self._login_ctrl = LoginController()

        if start_round_offset > 0:
            logger.info(
                f"循环模式: 起始轮次={options.start_round},将跳过前 "
                f"{start_round_offset} 轮对应的选品数据",
            )

        while True:
            try:
                batch = queue.pop_next_batch(DEFAULT_BATCH_SIZE)
            except SelectionTableEmptyError as exc:
                logger.info("{}", exc)
                message = (
                    "循环模式结束, 未检测到待处理数据"
                    if processed_batches == 0
                    else f"循环模式完成, 成功批次 {processed_batches}"
                )
                self._mark_success(
                    workflow_id=last_workflow_id or "continuous",
                    total_success=True,
                    errors=[],
                    message=message,
                )
                return
            except SelectionTableFormatError as exc:
                logger.error("选品表格式异常: {}", exc)
                self._mark_failure(str(exc))
                return

            # 计算实际轮次 = 起始偏移 + 当前处理批次 + 1
            actual_round = start_round_offset + processed_batches + 1
            logger.info(
                f"循环模式: 开始处理批次 #{processed_batches + 1} "
                f"(实际轮次={actual_round}, 条目={batch.size})"
            )
            try:
                result = await self._execute_workflow_async(
                    options,
                    selection_rows_override=batch.rows,
                    execution_round=actual_round,
                    login_ctrl=self._login_ctrl,
                )
            except Exception:
                queue.return_batch(batch.rows)
                raise

            if result.total_success:
                processed_batches += 1
                last_workflow_id = result.workflow_id or last_workflow_id
                queue.archive_batch(batch.rows, suffix="success")

                # 批次成功后,导航回采集箱准备下一批次
                if queue.has_pending_rows() and self._login_ctrl:
                    await self._navigate_to_collect_box(self._login_ctrl)
            else:
                queue.return_batch(batch.rows)
                queue.archive_batch(batch.rows, suffix="failed")
                error_msg = "; ".join(result.errors) if result.errors else "批次执行存在失败"
                self._mark_failure(error_msg)
                return

    async def _navigate_to_collect_box(self, login_ctrl: LoginController) -> None:
        """批次之间导航回采集箱页面,重置页面状态."""
        target_url = "https://erp.91miaoshou.com/common_collect_box/items"
        page = login_ctrl.browser_manager.page
        if page is None:
            return

        try:
            logger.debug("导航回采集箱页面准备下一批次...")
            await page.goto(target_url, timeout=60_000)
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(500)
            logger.debug("已返回采集箱页面")
        except Exception as exc:
            logger.warning(f"导航回采集箱页面失败: {exc}")

    async def _execute_workflow_async(
        self,
        options: WorkflowOptions,
        *,
        selection_rows_override: Sequence[ProductSelectionRow] | None = None,
        execution_round: int | None = None,
        login_ctrl: LoginController | None = None,
    ):
        """异步执行工作流,供单次和循环模式共用."""
        workflow_kwargs = options.as_workflow_kwargs()
        if selection_rows_override is not None:
            workflow_kwargs["selection_rows_override"] = selection_rows_override
        if execution_round is not None:
            workflow_kwargs["execution_round"] = execution_round
        if login_ctrl is not None:
            workflow_kwargs["login_ctrl"] = login_ctrl
            # 复用登录控制器时,启用登录状态复用(第一次登录后后续流程不再重复登录)
            workflow_kwargs["reuse_existing_login"] = True
        workflow = CompletePublishWorkflow(**workflow_kwargs)
        return await workflow.execute_async()

    def _mark_success(
        self,
        workflow_id: str,
        total_success: bool,
        errors: list[str],
        *,
        message: str | None = None,
    ) -> None:
        final_message = message or ("全部步骤完成" if total_success else "流程结束, 但存在告警")
        error_msg = "; ".join(errors) if errors else None
        with self._lock:
            self._status = RunStatus(
                state=RunState.SUCCESS if total_success else RunState.FAILED,
                message=final_message,
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
