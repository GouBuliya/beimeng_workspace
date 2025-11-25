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

import os
import platform
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

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
SESSION_KEY = "web_panel_admin"
DEFAULT_ADMIN_PASSWORD = "bm123456789"


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
    admin_password = os.environ.get("WEB_PANEL_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)
    session_secret = os.environ.get("WEB_PANEL_SESSION_SECRET", "temu-web-panel-session")
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret,
        https_only=False,
        same_site="lax",
        max_age=60 * 60 * 8,
    )

    def _is_authenticated(request: Request) -> bool:
        return bool(request.session.get(SESSION_KEY))

    def admin_guard(request: Request) -> None:
        if not _is_authenticated(request):
            raise HTTPException(status_code=401, detail="需要管理员密码")

    def _login_template(request: Request, *, error: str | None = None) -> HTMLResponse:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": error,
            },
            status_code=401 if error else 200,
        )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        if not _is_authenticated(request):
            return RedirectResponse("/login", status_code=303)
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "fields": FORM_FIELDS,
                "env_fields": env_metadata,
            },
        )

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request) -> HTMLResponse:
        if _is_authenticated(request):
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse("login.html", {"request": request})

    @app.post("/login", response_class=HTMLResponse)
    async def login_action(request: Request, password: str = Form(...)) -> HTMLResponse:
        if password.strip() == admin_password:
            request.session[SESSION_KEY] = True
            return RedirectResponse("/", status_code=303)
        return _login_template(request, error="管理员密码错误")

    @app.post("/logout")
    async def logout(request: Request) -> RedirectResponse:
        request.session.pop(SESSION_KEY, None)
        return RedirectResponse("/login", status_code=303)

    @app.post("/api/run", response_model=RunStatus)
    async def run_workflow(
        admin: None = Depends(admin_guard),
        selection_file: UploadFile | None = File(default=None),
        selection_path: str | None = Form(default=None),
        collection_owner: str = Form(...),
        outer_package_file: UploadFile | None = File(default=None),
        outer_package_path: str | None = Form(default=None),
        manual_file: UploadFile | None = File(default=None),
        manual_path: str | None = Form(default=None),
        headless_mode: str = Form(default="auto"),
        use_ai_titles: str | None = Form(default="off"),
        skip_first_edit: str | None = Form(default="off"),
        only_claim: str | None = Form(default="off"),
    ) -> RunStatus:
        resolved_path = await _resolve_selection_path(store, selection_file, selection_path)
        owner_value = (collection_owner or "").strip()
        if not owner_value:
            raise HTTPException(status_code=400, detail="妙手创建人员不能为空")
        outer_package_image = await _resolve_optional_asset(
            store,
            upload=outer_package_file,
            provided_path=outer_package_path,
            field_label="外包装图片",
            subdir="packaging",
            suffixes=(".png", ".jpg", ".jpeg", ".webp"),
            default_suffix=".png",
        )
        manual_file_path = await _resolve_optional_asset(
            store,
            upload=manual_file,
            provided_path=manual_path,
            field_label="说明书文件",
            subdir="manual",
            suffixes=(".pdf",),
            default_suffix=".pdf",
        )
        options = WorkflowOptions(
            selection_path=resolved_path,
            collection_owner=owner_value,
            headless_mode=_normalize_choice(headless_mode),
            use_ai_titles=_to_bool(use_ai_titles),
            skip_first_edit=_to_bool(skip_first_edit),
            only_claim=_to_bool(only_claim),
            outer_package_image=outer_package_image,
            manual_file=manual_file_path,
        )
        try:
            status = manager.start(options)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return status

    @app.get("/api/status", response_model=RunStatus)
    async def get_status(admin: None = Depends(admin_guard)) -> RunStatus:
        return manager.status()

    @app.get("/api/logs")
    async def get_logs(
        admin: None = Depends(admin_guard),
        after: int = Query(default=-1, ge=-1),
    ) -> list[dict[str, Any]]:
        chunks = manager.logs(after=after)
        return [chunk.model_dump() for chunk in chunks]

    @app.get("/api/fields")
    async def get_fields(admin: None = Depends(admin_guard)) -> list[dict[str, Any]]:
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
    async def health(admin: None = Depends(admin_guard)) -> HealthStatus:
        selection_dir = (DEFAULT_SELECTION.parent).resolve()
        return HealthStatus(
            ok=True,
            platform=platform.platform(),
            selection_dir=str(selection_dir),
            playwright_profile=str(APP_ROOT / "playwright-recordings" / "miaoshou-storage.json"),
        )

    @app.get("/downloads/sample-selection")
    async def download_sample(admin: None = Depends(admin_guard)) -> FileResponse:
        if not DEFAULT_SELECTION.exists():
            raise HTTPException(status_code=404, detail="示例文件缺失, 请联系开发者")
        return FileResponse(
            path=DEFAULT_SELECTION,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="Temu选品表示例.xlsx",
        )

    @app.get("/api/env-settings")
    async def get_env_settings(admin: None = Depends(admin_guard)) -> list[dict[str, Any]]:
        return build_env_payload()

    @app.post("/api/env-settings")
    async def update_env_settings(
        payload: EnvSettingsRequest,
        admin: None = Depends(admin_guard),
    ) -> dict[str, bool]:
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
        try:
            return store.store(
                selection_file.filename,
                selection_file.file,
                suffix_whitelist=(".xlsx", ".xls", ".csv"),
                default_suffix=".xlsx",
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if selection_path:
        candidate = Path(selection_path).expanduser()
        if not candidate.exists():
            raise HTTPException(status_code=400, detail="给定的选品表路径不存在")
        return candidate

    raise HTTPException(status_code=400, detail="请上传选品表或填写路径")


async def _resolve_optional_asset(
    store: SelectionFileStore,
    *,
    upload: UploadFile | None,
    provided_path: str | None,
    field_label: str,
    subdir: str,
    suffixes: tuple[str, ...],
    default_suffix: str,
) -> Path | None:
    """根据上传文件或路径解析可选资产."""

    if upload is not None and upload.filename:
        try:
            return store.store(
                upload.filename,
                upload.file,
                suffix_whitelist=suffixes,
                default_suffix=default_suffix,
                subdir=subdir,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"{field_label}: {exc}") from exc

    if provided_path:
        candidate = Path(provided_path).expanduser()
        if not candidate.exists():
            raise HTTPException(status_code=400, detail=f"{field_label} 路径不存在")
        return candidate

    return None


def _to_bool(value: str | None) -> bool:
    return value not in (None, "", "off", "false", "False", "0")


def _normalize_choice(value: str) -> str:
    if value in {"auto", "on", "off"}:
        return value
    return "auto"
