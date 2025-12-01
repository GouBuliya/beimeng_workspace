from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from httpx import ASGITransport, AsyncClient

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "temu-auto-publish"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import web_panel.api as api
from web_panel.api import create_app
from web_panel.models import LogChunk, RunState, RunStatus, WorkflowOptions
from web_panel.service import SelectionFileStore

TEST_ADMIN_PASSWORD = "bm123456789"


async def login(client: AsyncClient) -> None:
    await client.post("/login", data={"password": TEST_ADMIN_PASSWORD})


class RecordingManager:
    def __init__(self) -> None:
        self.started_with: list[WorkflowOptions] = []
        self.status_value = RunStatus(state=RunState.RUNNING, message="running")
        self.logs_value = [LogChunk(index=0, timestamp=0.0, level="INFO", message="first")]
        self.to_raise: Exception | None = None

    def start(self, options: WorkflowOptions) -> RunStatus:
        if self.to_raise:
            raise self.to_raise
        self.started_with.append(options)
        return RunStatus(state=RunState.RUNNING, message="started")

    def status(self) -> RunStatus:
        return self.status_value

    def logs(self, after: int = -1) -> list[LogChunk]:
        return [chunk for chunk in self.logs_value if chunk.index > after]


@pytest.fixture
def app_factory(tmp_path, monkeypatch):
    class TempStore(SelectionFileStore):
        def __init__(self) -> None:  # pragma: no cover - tiny wrapper
            super().__init__(base_dir=tmp_path / "uploads")

    monkeypatch.setattr(api, "SelectionFileStore", TempStore)

    def _build(manager: RecordingManager | None = None):
        mgr = manager or RecordingManager()
        app = create_app(task_manager=mgr)
        transport = ASGITransport(app=app)
        return mgr, transport

    return _build


@pytest.mark.asyncio
async def test_login_and_logout_flow(app_factory):
    manager, transport = app_factory()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/login"

        wrong = await client.post("/login", data={"password": "bad"}, follow_redirects=False)
        assert wrong.status_code == 401

        ok = await client.post(
            "/login", data={"password": TEST_ADMIN_PASSWORD}, follow_redirects=False
        )
        assert ok.status_code == 303

        home = await client.get("/", follow_redirects=False)
        assert home.status_code == 200

        await client.post("/logout", follow_redirects=False)
        status = await client.get("/api/status")
        assert status.status_code == 401
        assert manager.started_with == []


@pytest.mark.asyncio
async def test_run_with_selection_path_and_blank_owner(app_factory, tmp_path):
    manager, transport = app_factory()
    selection = tmp_path / "selection.xlsx"
    selection.write_text("demo")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login(client)
        ok = await client.post(
            "/api/run",
            data={"collection_owner": "Tester(account)", "selection_path": str(selection)},
        )
        assert ok.status_code == 200
        assert manager.started_with and manager.started_with[0].selection_path == selection

        bad_owner = await client.post(
            "/api/run",
            data={"collection_owner": "", "selection_path": str(selection)},
        )
        assert bad_owner.status_code == 400


@pytest.mark.asyncio
async def test_run_conflicting_or_invalid_assets(app_factory, tmp_path):
    manager, transport = app_factory()

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login(client)
        conflict = await client.post(
            "/api/run",
            files={"selection_file": ("demo.csv", b"rows", "text/csv")},
            data={
                "collection_owner": "Tester(account)",
                "only_claim": "on",
                "only_stage4_publish": "on",
            },
        )
        assert conflict.status_code == 400

        await login(client)
        missing_manual = await client.post(
            "/api/run",
            files={"selection_file": ("demo.csv", b"rows", "text/csv")},
            data={
                "collection_owner": "Tester(account)",
                "manual_path": str(tmp_path / "absent.pdf"),
            },
        )
        assert missing_manual.status_code == 400
        assert "说明书文件" in missing_manual.json()["detail"]

        await login(client)
        bad_outer = await client.post(
            "/api/run",
            files={
                "selection_file": ("demo.csv", b"rows", "text/csv"),
                "outer_package_file": ("bad.txt", b"oops", "text/plain"),
            },
            data={"collection_owner": "Tester(account)"},
        )
        assert bad_outer.status_code == 400
        assert "外包装图片" in bad_outer.json()["detail"]


@pytest.mark.asyncio
async def test_run_normalizes_headless_mode(app_factory):
    manager, transport = app_factory()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login(client)
        resp = await client.post(
            "/api/run",
            files={"selection_file": ("demo.csv", b"rows", "text/csv")},
            data={"collection_owner": "Tester(account)", "headless_mode": "weird-value"},
        )
        assert resp.status_code == 200
        assert manager.started_with[0].headless_mode == "auto"


@pytest.mark.asyncio
async def test_status_fields_health_and_download_guarded(app_factory, tmp_path, monkeypatch):
    manager, transport = app_factory()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login(client)
        status = await client.get("/api/status")
        assert status.status_code == 200
        assert status.json()["state"] == RunState.RUNNING

        fields = await client.get("/api/fields")
        assert fields.status_code == 200
        assert any(field["name"] == "selection_file" for field in fields.json())

        health = await client.get("/health")
        assert health.status_code == 200
        assert health.json()["ok"] is True

        monkeypatch.setattr(api, "DEFAULT_SELECTION", tmp_path / "missing.xlsx")
        download = await client.get("/downloads/sample-selection")
        assert download.status_code == 404


@pytest.mark.asyncio
async def test_resolve_selection_path_variants(tmp_path):
    store = SelectionFileStore(base_dir=tmp_path)
    existing = tmp_path / "selection.xlsx"
    existing.write_text("demo")
    resolved = await api._resolve_selection_path(store, None, str(existing))
    assert resolved == existing

    with pytest.raises(HTTPException):
        await api._resolve_selection_path(store, None, str(tmp_path / "missing.xlsx"))

    upload = UploadFile(filename="bad.txt", file=io.BytesIO(b"oops"))
    with pytest.raises(HTTPException):
        await api._resolve_selection_path(store, upload, None)


@pytest.mark.asyncio
async def test_resolve_optional_asset_variants(tmp_path):
    store = SelectionFileStore(base_dir=tmp_path)
    asset = tmp_path / "manual.pdf"
    asset.write_bytes(b"content")
    resolved = await api._resolve_optional_asset(
        store,
        upload=None,
        provided_path=str(asset),
        field_label="说明书文件",
        subdir="manual",
        suffixes=(".pdf",),
        default_suffix=".pdf",
    )
    assert resolved == asset

    missing = await api._resolve_optional_asset(
        store,
        upload=None,
        provided_path=None,
        field_label="外包装图片",
        subdir="packaging",
        suffixes=(".png",),
        default_suffix=".png",
    )
    assert missing is None

    bad_upload = UploadFile(filename="bad.txt", file=io.BytesIO(b"oops"))
    with pytest.raises(HTTPException):
        await api._resolve_optional_asset(
            store,
            upload=bad_upload,
            provided_path=None,
            field_label="外包装图片",
            subdir="packaging",
            suffixes=(".png",),
            default_suffix=".png",
        )

    with pytest.raises(HTTPException):
        await api._resolve_optional_asset(
            store,
            upload=None,
            provided_path=str(tmp_path / "absent.png"),
            field_label="外包装图片",
            subdir="packaging",
            suffixes=(".png",),
            default_suffix=".png",
        )


def test_bool_and_choice_helpers():
    assert api._to_bool(None) is False
    assert api._to_bool("off") is False
    assert api._to_bool("ON") is True
    assert api._normalize_choice("on") == "on"
    assert api._normalize_choice("off") == "off"
    assert api._normalize_choice("auto") == "auto"
    assert api._normalize_choice("unknown") == "auto"


@pytest.mark.asyncio
async def test_login_page_without_auth(app_factory):
    _manager, transport = app_factory()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/login", follow_redirects=False)
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_page_redirects_when_authenticated(app_factory):
    manager, transport = app_factory()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login(client)
        resp = await client.get("/login", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"


@pytest.mark.asyncio
async def test_run_conflict_when_manager_busy(app_factory):
    manager, transport = app_factory()
    manager.to_raise = RuntimeError("busy")
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login(client)
        resp = await client.post(
            "/api/run",
            files={"selection_file": ("demo.csv", b"rows", "text/csv")},
            data={"collection_owner": "Tester(account)"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"] == "busy"


@pytest.mark.asyncio
async def test_download_sample_success(app_factory, tmp_path, monkeypatch):
    # 创建 CSV 文件以匹配 api.py 中的 media_type="text/csv"
    sample = tmp_path / "selection.csv"
    sample.write_text("demo")
    monkeypatch.setattr(api, "DEFAULT_SELECTION", sample)
    manager, transport = app_factory()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await login(client)
        resp = await client.get("/downloads/sample-selection")
        assert resp.status_code == 200
        # 验证返回的是 CSV 格式（匹配 api.py 中的定义）
        assert resp.headers["content-type"].startswith("text/csv")
