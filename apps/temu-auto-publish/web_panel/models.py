"""
@PURPOSE: 定义 Web Panel FastAPI 层的请求/响应模型
@OUTLINE:
  - RunState: 运行状态枚举
  - WorkflowOptions: Web 表单到工作流参数的映射
  - RunStatus: 当前任务状态信息
  - LogChunk: 日志片段
  - HealthStatus: 健康检查响应
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class RunState(str, Enum):
    """任务运行状态."""

    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class WorkflowOptions(BaseModel):
    """工作流参数配置."""

    selection_path: Path = Field(description="选品表的绝对路径")
    collection_owner: str = Field(min_length=1, description="妙手采集箱创建人员显示名")
    headless_mode: Literal["auto", "on", "off"] = Field(default="auto")
    use_ai_titles: bool = Field(default=False)
    use_ai_attrs: bool = Field(default=False, description="使用AI智能补全必填类目属性")
    skip_first_edit: bool = Field(default=False)
    only_claim: bool = Field(default=False)
    only_stage4_publish: bool = Field(default=False, description="仅运行阶段4发布")
    use_api_batch_edit: bool = Field(default=True, description="使用API方式执行批量编辑(默认开启)")
    use_api_first_edit: bool = Field(default=True, description="使用API方式执行首次编辑(默认开启)")
    outer_package_image: Path | None = Field(default=None, description="外包装图片文件路径")
    manual_file: Path | None = Field(default=None, description="产品说明书PDF路径")
    single_run: bool = Field(default=True, description="是否仅运行一次流程")
    start_round: int = Field(default=1, ge=1, description="起始轮次(模拟已运行次数,默认1)")
    bound_miaoshou_username: str | None = Field(
        default=None, description="后台绑定的妙手账号（用于验证）"
    )

    def as_workflow_kwargs(self) -> dict[str, object]:
        """转换为 CompletePublishWorkflow 所需的关键参数."""

        headless_value: bool | None
        if self.headless_mode == "auto":
            headless_value = None
        elif self.headless_mode == "on":
            headless_value = False  # "显示窗口"意味着 headless False
        else:
            headless_value = True

        return {
            "selection_table": self.selection_path,
            "headless": headless_value,
            "collection_owner": self.collection_owner.strip(),
            "use_ai_titles": self.use_ai_titles,
            "use_ai_attrs": self.use_ai_attrs,
            "skip_first_edit": self.skip_first_edit,
            "only_claim": self.only_claim,
            "only_stage4_publish": self.only_stage4_publish,
            "use_api_batch_edit": self.use_api_batch_edit,
            "use_api_first_edit": self.use_api_first_edit,
            "outer_package_image": str(self.outer_package_image)
            if self.outer_package_image
            else None,
            "manual_file": str(self.manual_file) if self.manual_file else None,
            "execution_round": self.start_round,
            "bound_miaoshou_username": self.bound_miaoshou_username,
        }


class CSVValidationErrorDetail(BaseModel):
    """CSV 验证错误详情."""

    row: int = Field(description="错误所在行号（从1开始）")
    column: int | None = Field(default=None, description="错误所在列号")
    column_name: str | None = Field(default=None, description="错误所在列名")
    error_type: str = Field(description="错误类型标识")
    message: str = Field(description="错误描述")
    context: str = Field(default="", description="错误上下文")


class RunStatus(BaseModel):
    """表示当前任务状态, 方便前端轮询."""

    state: RunState = Field(default=RunState.IDLE)
    message: str = Field(default="准备就绪")
    workflow_id: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    last_error: str | None = None
    csv_validation_errors: list[dict] | None = Field(
        default=None,
        description="CSV 验证错误详情列表（仅在 CSV 格式验证失败时有值）",
    )


class LogChunk(BaseModel):
    """日志切片, 便于前端增量拉取."""

    index: int
    timestamp: float
    level: str
    message: str


class HealthStatus(BaseModel):
    """健康检查响应."""

    ok: bool = True
    platform: str
    selection_dir: str
    playwright_profile: str | None = None
