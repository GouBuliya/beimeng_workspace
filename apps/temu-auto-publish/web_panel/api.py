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
@GOTCHAS:
  - 认证已集成远程认证服务器,需要配置 AUTH_SERVER_URL 环境变量
  - 支持本地密码模式(fallback)和远程认证模式
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from loguru import logger
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from .auth_client import get_auth_client

# 版本号从顶层包获取
try:
    from .. import __version__
except ImportError:
    # 如果相对导入失败，直接读取版本文件
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from __init__ import __version__
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

# ========== 日志文件配置 ==========
APP_ROOT = Path(__file__).resolve().parents[1]
_LOG_DIR = APP_ROOT / "data" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# 添加日志文件输出（按日期轮转）
_log_file = _LOG_DIR / "web_panel_{time:YYYY-MM-DD}.log"
logger.add(
    str(_log_file),
    rotation="00:00",  # 每天午夜轮转
    retention="30 days",  # 保留 30 天
    compression="zip",  # 压缩旧日志
    encoding="utf-8",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
)
logger.info(f"日志文件已配置: {_LOG_DIR}")

TEMPLATE_DIR = APP_ROOT / "web_panel" / "templates"
DEFAULT_SELECTION = APP_ROOT / "data" / "input" / "10月新品可上架.csv"
SELECTOR_FILE = APP_ROOT / "config" / "miaoshou_selectors_v2.json"
SESSION_KEY = "web_panel_user"
SESSION_TOKEN_KEY = "web_panel_token"
SESSION_USERNAME_KEY = "web_panel_username"


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

    def _get_current_user(request: Request) -> dict[str, Any] | None:
        """获取当前登录用户信息."""
        if not _is_authenticated(request):
            return None
        return {
            "username": request.session.get(SESSION_USERNAME_KEY, ""),
            "token": request.session.get(SESSION_TOKEN_KEY, ""),
        }

    async def admin_guard(request: Request) -> None:
        if not _is_authenticated(request):
            raise HTTPException(status_code=401, detail="需要登录")

        # 验证令牌是否仍然有效
        token = request.session.get(SESSION_TOKEN_KEY)
        if token:
            auth_client = get_auth_client()
            result = await auth_client.verify_token(token)
            if not result.valid:
                # 令牌失效(可能被其他设备登录踢出)
                request.session.clear()
                raise HTTPException(
                    status_code=401, detail=result.message or "会话已失效,请重新登录"
                )

    def _login_template(request: Request, *, error: str | None = None) -> HTMLResponse:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": error,
                "use_remote_auth": True,
            },
            status_code=401 if error else 200,
        )

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        if not _is_authenticated(request):
            return RedirectResponse("/login", status_code=303)
        username = request.session.get(SESSION_USERNAME_KEY, "用户")
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "fields": FORM_FIELDS,
                "env_fields": env_metadata,
                "username": username,
                "version": __version__,
            },
        )

    @app.get("/api/version")
    async def get_version() -> dict[str, str]:
        """获取系统版本号."""
        return {"version": __version__}

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request) -> HTMLResponse:
        if _is_authenticated(request):
            return RedirectResponse("/", status_code=303)
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "use_remote_auth": True},
        )

    @app.post("/login", response_class=HTMLResponse)
    async def login_action(
        request: Request,
        username: str = Form(default=""),
        password: str = Form(...),
    ) -> HTMLResponse:
        # 使用远程认证服务器
        auth_client = get_auth_client()

        # 检查认证服务器是否可用
        if not await auth_client.health_check():
            logger.error("认证服务器不可用")
            return _login_template(request, error="认证服务器不可用,请联系管理员")

        # 远程登录
        token_data = await auth_client.login(username.strip(), password.strip())
        if token_data:
            request.session[SESSION_KEY] = True
            request.session[SESSION_TOKEN_KEY] = token_data.access_token
            request.session[SESSION_USERNAME_KEY] = username.strip()
            logger.info(f"用户远程登录成功: {username}")
            return RedirectResponse("/", status_code=303)
        return _login_template(request, error="用户名或密码错误")

    @app.post("/logout")
    async def logout(request: Request) -> RedirectResponse:
        # 通知认证服务器登出
        token = request.session.get(SESSION_TOKEN_KEY)
        if token:
            auth_client = get_auth_client()
            await auth_client.logout(token)

        request.session.clear()
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
        only_stage4_publish: str | None = Form(default="off"),
        single_run: str | None = Form(default="on"),
        publish_close_retry: str | None = Form(default="5"),
        publish_repeat_count: str | None = Form(default="1"),
        start_round: str | None = Form(default="1"),
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
        only_claim_flag = _to_bool(only_claim)
        only_stage4_flag = _to_bool(only_stage4_publish)
        if only_stage4_flag and only_claim_flag:
            raise HTTPException(status_code=400, detail="“仅认领”与“仅发布”不可同时启用")

        close_retry = _coerce_int(publish_close_retry, default=5, min_value=1, max_value=10)
        repeat_count = _coerce_int(publish_repeat_count, default=1, min_value=1, max_value=10)
        execution_round = _coerce_int(start_round, default=1, min_value=1, max_value=100)
        _persist_publish_preferences(repeat_count, close_retry)

        options = WorkflowOptions(
            selection_path=resolved_path,
            collection_owner=owner_value,
            headless_mode=_normalize_choice(headless_mode),
            use_ai_titles=_to_bool(use_ai_titles),
            skip_first_edit=_to_bool(skip_first_edit),
            only_claim=only_claim_flag,
            only_stage4_publish=only_stage4_flag,
            outer_package_image=outer_package_image,
            manual_file=manual_file_path,
            single_run=_to_bool(single_run),
            start_round=execution_round,
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
            media_type="text/csv",
            filename="10月新品可上架.csv",
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
            labels = ",".join(missing)
            raise HTTPException(status_code=400, detail=f"以下配置不能为空: {labels}")
        persist_env_settings(payload.entries)
        return {"ok": True}

    # ==================== 管理员后台 API ====================

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_page(request: Request, _: None = Depends(admin_guard)) -> HTMLResponse:
        """管理员后台页面."""
        username = request.session.get(SESSION_USERNAME_KEY, "")
        return templates.TemplateResponse(
            "admin.html",
            {"request": request, "username": username},
        )

    @app.get("/api/admin/users")
    async def get_users(
        request: Request,
        _: None = Depends(admin_guard),
        skip: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=1000),
    ) -> dict[str, Any]:
        """获取用户列表(代理到认证服务器)."""
        token = request.session.get(SESSION_TOKEN_KEY)
        if not token:
            raise HTTPException(status_code=401, detail="未登录")

        import httpx

        auth_client = get_auth_client()
        async with httpx.AsyncClient(base_url=auth_client.base_url, timeout=10.0) as client:
            response = await client.get(
                "/users",
                params={"skip": skip, "limit": limit},
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 403:
                raise HTTPException(status_code=403, detail="需要管理员权限")
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="请求失败")
            return response.json()

    @app.post("/api/admin/users")
    async def create_user(
        request: Request,
        user_data: dict[str, Any],
        _: None = Depends(admin_guard),
    ) -> dict[str, Any]:
        """创建用户(代理到认证服务器)."""
        token = request.session.get(SESSION_TOKEN_KEY)
        if not token:
            raise HTTPException(status_code=401, detail="未登录")

        import httpx

        auth_client = get_auth_client()
        async with httpx.AsyncClient(base_url=auth_client.base_url, timeout=10.0) as client:
            response = await client.post(
                "/users",
                json=user_data,
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 403:
                raise HTTPException(status_code=403, detail="需要管理员权限")
            if response.status_code == 400:
                raise HTTPException(
                    status_code=400, detail=response.json().get("detail", "请求失败")
                )
            if response.status_code != 201:
                raise HTTPException(status_code=response.status_code, detail="请求失败")
            return response.json()

    @app.put("/api/admin/users/{user_id}")
    async def update_user(
        request: Request,
        user_id: str,
        user_data: dict[str, Any],
        _: None = Depends(admin_guard),
    ) -> dict[str, Any]:
        """更新用户(代理到认证服务器)."""
        token = request.session.get(SESSION_TOKEN_KEY)
        if not token:
            raise HTTPException(status_code=401, detail="未登录")

        import httpx

        auth_client = get_auth_client()
        async with httpx.AsyncClient(base_url=auth_client.base_url, timeout=10.0) as client:
            response = await client.put(
                f"/users/{user_id}",
                json=user_data,
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 403:
                raise HTTPException(status_code=403, detail="需要管理员权限")
            if response.status_code == 400:
                raise HTTPException(
                    status_code=400, detail=response.json().get("detail", "请求失败")
                )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="用户不存在")
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="请求失败")
            return response.json()

    @app.delete("/api/admin/users/{user_id}")
    async def delete_user(
        request: Request,
        user_id: str,
        _: None = Depends(admin_guard),
    ) -> dict[str, Any]:
        """删除用户(代理到认证服务器)."""
        token = request.session.get(SESSION_TOKEN_KEY)
        if not token:
            raise HTTPException(status_code=401, detail="未登录")

        import httpx

        auth_client = get_auth_client()
        async with httpx.AsyncClient(base_url=auth_client.base_url, timeout=10.0) as client:
            response = await client.delete(
                f"/users/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 403:
                raise HTTPException(status_code=403, detail="需要管理员权限")
            if response.status_code == 400:
                raise HTTPException(
                    status_code=400, detail=response.json().get("detail", "请求失败")
                )
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="用户不存在")
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="请求失败")
            return response.json()

    @app.post("/api/admin/users/{user_id}/force-logout")
    async def force_logout_user(
        request: Request,
        user_id: str,
        _: None = Depends(admin_guard),
    ) -> dict[str, Any]:
        """强制用户下线(代理到认证服务器)."""
        token = request.session.get(SESSION_TOKEN_KEY)
        if not token:
            raise HTTPException(status_code=401, detail="未登录")

        import httpx

        auth_client = get_auth_client()
        async with httpx.AsyncClient(base_url=auth_client.base_url, timeout=10.0) as client:
            response = await client.post(
                f"/users/{user_id}/force-logout",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code == 403:
                raise HTTPException(status_code=403, detail="需要管理员权限")
            if response.status_code == 404:
                raise HTTPException(status_code=404, detail="用户不存在")
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="请求失败")
            return response.json()

    @app.get("/api/admin/auth-server-health")
    async def check_auth_server_health(
        _: None = Depends(admin_guard),
    ) -> dict[str, Any]:
        """检查认证服务器健康状态."""
        auth_client = get_auth_client()
        is_healthy = await auth_client.health_check()
        return {
            "healthy": is_healthy,
            "server_url": auth_client.base_url,
        }

    @app.post("/api/clear-cookies")
    async def clear_cookies(
        admin: None = Depends(admin_guard),
    ) -> dict[str, Any]:
        """清除浏览器 Cookie/Storage State 文件.

        清除后首次运行任务时，脚本会自动检测到 Cookie 失效，
        并执行完整的登录流程（自动输入用户名和密码）。
        """
        # 需要清除的文件列表
        cookie_files = [
            # Playwright storage state 文件
            APP_ROOT / "data" / "browser" / "storage_state.json",
            APP_ROOT / "playwright-recordings" / "miaoshou-storage.json",
            # CookieManager 管理的 cookie 文件
            APP_ROOT / "data" / "temp" / "miaoshou_cookies.json",
            APP_ROOT / "data" / "temp" / "miaoshou_cookies.json.meta.json",
            # Temu cookie 文件
            APP_ROOT / "data" / "input" / "temu_cookies.json",
        ]

        cleared_files: list[str] = []
        errors: list[str] = []

        for path in cookie_files:
            if path.exists():
                try:
                    path.unlink()
                    cleared_files.append(path.name)
                    logger.info(f"已清除 Cookie 文件: {path}")
                except Exception as exc:
                    errors.append(f"{path.name}: {exc}")
                    logger.error(f"清除 Cookie 文件失败: {path}, 错误: {exc}")

        if errors:
            raise HTTPException(
                status_code=500,
                detail=f"部分文件清除失败: {'; '.join(errors)}",
            )

        return {
            "ok": True,
            "cleared_files": cleared_files,
            "message": f"已清除 {len(cleared_files)} 个 Cookie 文件，下次运行将自动重新登录"
            if cleared_files
            else "无需清除（Cookie 文件不存在）",
        }

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


def _coerce_int(
    value: str | None,
    *,
    default: int,
    min_value: int,
    max_value: int,
) -> int:
    try:
        parsed = int(str(value).strip())
        if parsed < min_value:
            return min_value
        if parsed > max_value:
            return max_value
        return parsed
    except Exception:
        return default


def _persist_publish_preferences(repeat_per_batch: int, close_retry: int) -> None:
    """将 Web 端配置写入选择器文件, 供发布控制器读取."""

    try:
        if not SELECTOR_FILE.exists():
            logger.warning("选择器配置文件不存在,跳过发布参数写入: {}", SELECTOR_FILE)
            return

        data = json.loads(SELECTOR_FILE.read_text(encoding="utf-8"))
        publish_cfg = data.get("publish") or {}
        publish_confirm_cfg = data.get("publish_confirm") or {}

        publish_cfg["repeat_per_batch"] = repeat_per_batch
        publish_confirm_cfg["close_retry"] = close_retry

        data["publish"] = publish_cfg
        data["publish_confirm"] = publish_confirm_cfg

        SELECTOR_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(
            f"已更新发布配置: repeat_per_batch={repeat_per_batch}, "
            f"close_retry={close_retry} -> {SELECTOR_FILE}"
        )
    except Exception as exc:  # pragma: no cover - 运行时保护
        logger.warning("更新发布配置失败: {}", exc)
