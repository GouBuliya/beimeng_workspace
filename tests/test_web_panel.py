"""
@PURPOSE: 覆盖 Web Panel FastAPI 接口的关键路径
@OUTLINE:
  - DummyManager: 伪造的 WorkflowTaskManager
  - test_run_with_upload: 验证上传文件即可启动任务
  - test_run_without_payload: 验证缺少文件时报错
  - test_logs_endpoint: 验证日志接口格式
"""

# ruff: noqa: E402

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "temu-auto-publish"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from web_panel.api import create_app  # type: ignore[import-not-found]
from web_panel.models import (  # type: ignore[import-not-found]
    LogChunk,
    RunState,
    RunStatus,
    WorkflowOptions,
)


class DummyManager:
    """最小化的任务管理器, 便于注入到 FastAPI."""

    def __init__(self) -> None:
        self.started_with: WorkflowOptions | None = None
        self.return_status = RunStatus(state=RunState.RUNNING, message="mock-run")

    def start(self, options: WorkflowOptions) -> RunStatus:
        self.started_with = options
        return self.return_status

    def status(self) -> RunStatus:
        return RunStatus(state=RunState.IDLE, message="idle")

    def logs(self, after: int = -1) -> list[LogChunk]:
        return [LogChunk(index=0, timestamp=0.0, level="INFO", message="ready")]


@pytest.mark.asyncio
async def test_run_with_upload(tmp_path) -> None:
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/run",
            files={"selection_file": ("demo.xlsx", b"content", "application/vnd.ms-excel")},
            data={"collection_owner": "Tester(account)"},
        )

    assert response.status_code == 200
    assert manager.started_with is not None
    assert manager.started_with.selection_path.exists()
    assert manager.started_with.use_codegen_batch_edit is True
    assert manager.started_with.collection_owner == "Tester(account)"


@pytest.mark.asyncio
async def test_run_without_payload() -> None:
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/run",
            data={"collection_owner": "Tester(account)"},
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_logs_endpoint() -> None:
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/logs")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["level"] == "INFO"


@pytest.mark.asyncio
async def test_env_settings_update(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    monkeypatch.setenv("TEMU_WEB_PANEL_ENV", str(env_file))
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        load_resp = await client.get("/api/env-settings")
        assert load_resp.status_code == 200
        assert any(field["key"] == "MIAOSHOU_USERNAME" for field in load_resp.json())

        payload = {
            "entries": {
                "MIAOSHOU_USERNAME": "tester",
                "MIAOSHOU_PASSWORD": "secret123",
            }
        }
        save_resp = await client.post("/api/env-settings", json=payload)
        assert save_resp.status_code == 200
        content = env_file.read_text(encoding="utf-8")
        assert "MIAOSHOU_USERNAME='tester'" in content
        assert "MIAOSHOU_PASSWORD='secret123'" in content


@pytest.mark.asyncio
async def test_env_settings_validation(tmp_path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    monkeypatch.setenv("TEMU_WEB_PANEL_ENV", str(env_file))
    manager = DummyManager()
    app = create_app(task_manager=manager)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/env-settings",
            json={"entries": {"MIAOSHOU_USERNAME": "", "MIAOSHOU_PASSWORD": ""}},
        )
        assert resp.status_code == 400
