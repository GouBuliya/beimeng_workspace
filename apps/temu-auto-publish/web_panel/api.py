"""
@PURPOSE: FastAPI 应用入口, 暴露 Web Panel 所需的 HTTP 接口
@OUTLINE:
  - create_app(): FastAPI 应用工厂
  - /: 渲染引导式页面
  - /api/run: 接收表单并启动 Temu 工作流
  - /api/status: 查询运行状态
  - /api/logs: 增量拉取日志
  - /api/fields: 返回表单元数据
  - /health: 环境自检
  - /downloads/sample-selection: 示例选品表下载
"""

# ruff: noqa: B008

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .env_settings import (
    ENV_FIELDS,
    build_env_payload,
    persist_env_settings,
    resolve_env_file,
    validate_required,
)
from .fields import FORM_FIELDS
from .models import HealthStatus, RunStatus, WorkflowOptions
from .service import SelectionFileStore, WorkflowTaskManager, create_task_manager

APP_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = APP_ROOT / "web_panel" / "templates"
DEFAULT_SELECTION = APP_ROOT / "data" / "input" / "selection.xlsx"


def create_app(task_manager: WorkflowTaskManager | None = None) -> FastAPI:
    """FastAPI 应用工厂."""

    app = FastAPI(title="Temu Web Panel", default_response_class=JSONResponse)
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
    store = SelectionFileStore()
    manager = task_manager or create_task_manager()
    env_metadata = [
        {
            "key": field.key,
            "label": field.label,
            "help_text": field.help_text,
            "required": field.required,
            "placeholder": field.placeholder,
            "secret": field.secret,
        }
        for field in ENV_FIELDS
    ]

    load_dotenv(resolve_env_file(), override=False)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "fields": FORM_FIELDS,
                "env_fields": env_metadata,
            },
        )

    @app.post("/api/run", response_model=RunStatus)
    async def run_workflow(
        selection_file: UploadFile | None = File(default=None),
        selection_path: str | None = Form(default=None),
        headless_mode: str = Form(default="auto"),
        use_ai_titles: str | None = Form(default="off"),
        use_codegen_first_edit: str | None = Form(default="on"),
        use_codegen_batch_edit: str | None = Form(default="on"),
        skip_first_edit: str | None = Form(default="off"),
        only_claim: str | None = Form(default="off"),
    ) -> RunStatus:
        resolved_path = await _resolve_selection_path(store, selection_file, selection_path)
        options = WorkflowOptions(
            selection_path=resolved_path,
            headless_mode=_normalize_choice(headless_mode),
            use_ai_titles=_to_bool(use_ai_titles),
            use_codegen_first_edit=_to_bool(use_codegen_first_edit),
            use_codegen_batch_edit=_to_bool(use_codegen_batch_edit),
            skip_first_edit=_to_bool(skip_first_edit),
            only_claim=_to_bool(only_claim),
        )
        try:
            status = manager.start(options)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return status

    @app.get("/api/status", response_model=RunStatus)
    async def get_status() -> RunStatus:
        return manager.status()

    @app.get("/api/logs")
    async def get_logs(after: int = Query(default=-1, ge=-1)) -> list[dict[str, Any]]:
        chunks = manager.logs(after=after)
        return [chunk.model_dump() for chunk in chunks]

    @app.get("/api/fields")
    async def get_fields() -> list[dict[str, Any]]:
        return [
            {
                "name": field.name,
                "label": field.label,
                "help_text": field.help_text,
                "kind": field.kind,
                "default": field.default,
                "placeholder": field.placeholder,
                "options": field.options,
                "required": field.required,
            }
            for field in FORM_FIELDS
        ]

    @app.get("/health", response_model=HealthStatus)
    async def health() -> HealthStatus:
        selection_dir = (DEFAULT_SELECTION.parent).resolve()
        return HealthStatus(
            ok=True,
            platform=platform.platform(),
            selection_dir=str(selection_dir),
            playwright_profile=str(APP_ROOT / "playwright-recordings" / "miaoshou-storage.json"),
        )

    @app.get("/downloads/sample-selection")
    async def download_sample() -> FileResponse:
        if not DEFAULT_SELECTION.exists():
            raise HTTPException(status_code=404, detail="示例文件缺失, 请联系开发者")
        return FileResponse(
            path=DEFAULT_SELECTION,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="Temu选品表示例.xlsx",
        )

    @app.get("/api/env-settings")
    async def get_env_settings() -> list[dict[str, Any]]:
        return build_env_payload()

    @app.post("/api/env-settings")
    async def update_env_settings(payload: EnvSettingsRequest) -> dict[str, bool]:
        missing = validate_required(payload.entries)
        if missing:
            labels = "、".join(missing)
            raise HTTPException(status_code=400, detail=f"以下配置不能为空: {labels}")
        persist_env_settings(payload.entries)
        return {"ok": True}

    return app


class EnvSettingsRequest(BaseModel):
    """env 设置提交载体."""

    entries: dict[str, str | None]


async def _resolve_selection_path(
    store: SelectionFileStore,
    selection_file: UploadFile | None,
    selection_path: str | None,
) -> Path:
    if selection_file is not None and selection_file.filename:
        return store.store(selection_file.filename, selection_file.file)

    if selection_path:
        candidate = Path(selection_path).expanduser()
        if not candidate.exists():
            raise HTTPException(status_code=400, detail="给定的选品表路径不存在")
        return candidate

    raise HTTPException(status_code=400, detail="请上传选品表或填写路径")


def _to_bool(value: str | None) -> bool:
    return value not in (None, "", "off", "false", "False", "0")


def _normalize_choice(value: str) -> str:
    if value in {"auto", "on", "off"}:
        return value
    return "auto"
