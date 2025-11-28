from __future__ import annotations

import io
import sys
from concurrent.futures import Future
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import re
import threading

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "temu-auto-publish"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from web_panel.models import RunState, WorkflowOptions  # noqa: E402
from web_panel.service import (  # noqa: E402
    SelectionFileStore,
    SelectionTableEmptyError,
    SelectionTableFormatError,
    WorkflowTaskManager,
)
import web_panel.service as service  # noqa: E402


class SyncExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def submit(self, func, *args, **kwargs):
        fut: Future = Future()
        try:
            result = func(*args, **kwargs)
            fut.set_result(result)
        except Exception as exc:  # pragma: no cover - Future captures path
            fut.set_exception(exc)
        self.calls.append((func, args, kwargs))
        return fut


def _make_options(tmp_path, **overrides) -> WorkflowOptions:
    selection = tmp_path / "selection.xlsx"
    selection.write_text("demo")
    return WorkflowOptions(
        selection_path=selection,
        collection_owner=" Tester(account) ",
        headless_mode=overrides.get("headless_mode", "auto"),
        use_ai_titles=overrides.get("use_ai_titles", False),
        skip_first_edit=overrides.get("skip_first_edit", False),
        only_claim=overrides.get("only_claim", False),
        only_stage4_publish=overrides.get("only_stage4_publish", False),
        outer_package_image=overrides.get("outer_package_image"),
        manual_file=overrides.get("manual_file"),
        single_run=overrides.get("single_run", True),
    )


def test_selection_file_store_behaviour(tmp_path):
    store = SelectionFileStore(base_dir=tmp_path / "uploads")
    stored = store.store("demo.xlsx", io.BytesIO(b"hello"))
    assert stored.exists()
    assert stored.suffix == ".xlsx"
    assert stored.parent == tmp_path / "uploads"

    class NoSeekStream:
        def __init__(self, payload: bytes):
            self._buf = io.BytesIO(payload)

        def read(self, size: int = -1) -> bytes:
            return self._buf.read(size)

        def seek(self, offset: int, whence: int = 0):
            raise OSError("no seek")

    nested = store.store(
        "nested.csv",
        NoSeekStream(b"payload"),
        suffix_whitelist=(".csv",),
        default_suffix=".csv",
        subdir="nested",
    )
    assert nested.parent.name == "nested"
    assert nested.read_bytes() == b"payload"

    with pytest.raises(ValueError):
        store.store("bad.txt", io.BytesIO(b"x"), suffix_whitelist=(".xlsx",))

    safe_stem = SelectionFileStore._build_safe_stem("中文 文件?.xlsx")
    assert re.match(r"[a-z0-9_-]+_\d{8}_\d{6}$", safe_stem)


def test_workflow_options_kwargs(tmp_path):
    selection = tmp_path / "selection.xlsx"
    selection.write_text("demo")

    auto = WorkflowOptions(selection_path=selection, collection_owner="Owner", headless_mode="auto")
    assert auto.as_workflow_kwargs()["headless"] is None

    on = auto.model_copy(update={"headless_mode": "on"})
    assert on.as_workflow_kwargs()["headless"] is False

    off = auto.model_copy(
        update={
            "headless_mode": "off",
            "outer_package_image": selection,
            "manual_file": selection,
            "collection_owner": " Owner ",
        }
    )
    kwargs_off = off.as_workflow_kwargs()
    assert kwargs_off["headless"] is True
    assert kwargs_off["outer_package_image"].endswith("selection.xlsx")
    assert kwargs_off["collection_owner"] == "Owner"


def test_manager_start_and_failure_paths(tmp_path):
    manager = WorkflowTaskManager()
    manager._lock = threading.RLock()
    manager._executor = SyncExecutor()

    options = _make_options(tmp_path)

    class DummyResult:
        def __init__(self, success: bool = True) -> None:
            self.workflow_id = "wf-1"
            self.total_success = success
            self.errors: list[str] = [] if success else ["bad"]

    manager._execute_workflow = lambda *_, **__: DummyResult()  # type: ignore[assignment]
    start_status = manager.start(options)
    assert start_status.state in {RunState.RUNNING, RunState.SUCCESS}
    manager._future.result()
    assert manager.status().state == RunState.SUCCESS
    assert manager._log_sink_id is None

    manager._execute_workflow = lambda *_, **__: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[assignment]
    start_status = manager.start(options)
    assert start_status.state in {RunState.RUNNING, RunState.FAILED}
    manager._future.result()
    assert manager.status().state == RunState.FAILED
    assert manager.status().last_error == "boom"

    manager._status.state = RunState.RUNNING
    with pytest.raises(RuntimeError):
        manager.start(options)


def test_manager_run_continuous_success_and_errors(tmp_path, monkeypatch):
    manager = WorkflowTaskManager()
    manager._executor = SyncExecutor()
    manager._status.state = RunState.IDLE

    def fake_execute(*_, **__):
        result = SimpleNamespace()
        result.workflow_id = "wf-cont"
        result.total_success = True
        result.errors = []
        return result

    manager._execute_workflow = fake_execute  # type: ignore[assignment]

    class SingleBatchQueue:
        def __init__(self, *_args, **_kwargs) -> None:
            self.calls = 0

        def pop_next_batch(self, *_args, **_kwargs):
            if self.calls == 0:
                self.calls += 1
                return SimpleNamespace(rows=[1, 2, 3], size=3)
            raise SelectionTableEmptyError("empty")

        def return_batch(self, _rows) -> None:
            self.returned = True

        def archive_batch(self, rows, suffix: str) -> None:
            self.archived = (tuple(rows), suffix)

    monkeypatch.setattr("web_panel.service.SelectionTableQueue", SingleBatchQueue)
    manager._run_workflow(_make_options(tmp_path, single_run=False))
    status = manager.status()
    assert status.state == RunState.SUCCESS
    assert "循环模式完成" in status.message

    class FormatErrorQueue:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def pop_next_batch(self, *_args, **_kwargs):
            raise SelectionTableFormatError("format bad")

    monkeypatch.setattr("web_panel.service.SelectionTableQueue", FormatErrorQueue)
    manager._run_workflow(_make_options(tmp_path, single_run=False))
    assert manager.status().state == RunState.FAILED
    assert "format bad" in manager.status().last_error

    class FailResult:
        def __init__(self) -> None:
            self.workflow_id = "wf-fail"
            self.total_success = False
            self.errors = ["err"]

    class FailingQueue:
        def __init__(self, *_args, **_kwargs) -> None:
            self.rows = [1]

        def pop_next_batch(self, *_args, **_kwargs):
            return SimpleNamespace(rows=self.rows, size=len(self.rows))

        def return_batch(self, rows) -> None:
            self.returned = tuple(rows)

        def archive_batch(self, rows, suffix: str) -> None:
            self.archive = (tuple(rows), suffix)

    manager._execute_workflow = lambda *_, **__: FailResult()  # type: ignore[assignment]
    monkeypatch.setattr("web_panel.service.SelectionTableQueue", FailingQueue)
    manager._run_workflow(_make_options(tmp_path, single_run=False))
    assert manager.status().state == RunState.FAILED


def test_logs_and_status_are_copied():
    manager = WorkflowTaskManager()
    now = datetime.now(timezone.utc)
    message = SimpleNamespace(
        record={"time": now, "level": SimpleNamespace(name="INFO"), "message": "hello"}
    )
    manager._on_log(message)

    assert manager.logs(after=-1)[0].message == "hello"
    assert manager.logs(after=0) == []

    status_copy = manager.status()
    assert status_copy is not manager._status
    assert status_copy.state == RunState.IDLE


def test_resolve_upload_dir_when_frozen(tmp_path, monkeypatch):
    monkeypatch.setattr(service.sys, "frozen", True, raising=False)
    monkeypatch.setattr(service.Path, "home", staticmethod(lambda: tmp_path))
    path = service._resolve_upload_dir()
    assert path == tmp_path / "TemuWebPanel" / "input"
    assert path.exists()


def test_execute_workflow_invokes_workflow_class(tmp_path, monkeypatch):
    manager = WorkflowTaskManager()
    captured: dict[str, object] = {}

    class DummyWorkflow:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

        def execute(self) -> str:
            return "done"

    monkeypatch.setattr(service, "CompletePublishWorkflow", DummyWorkflow)
    result = manager._execute_workflow(
        _make_options(tmp_path), selection_rows_override=["row"]
    )
    assert result == "done"
    assert captured["selection_rows_override"] == ["row"]
    assert captured["selection_table"]


def test_continuous_return_batch_on_exception(tmp_path, monkeypatch):
    manager = WorkflowTaskManager()
    manager._lock = threading.RLock()
    manager._execute_workflow = lambda *_, **__: (_ for _ in ()).throw(ValueError("fail"))  # type: ignore[assignment]

    class RaisingQueue:
        def __init__(self, *_args, **_kwargs) -> None:
            self.returned = False

        def pop_next_batch(self, *_args, **_kwargs):
            return SimpleNamespace(rows=[1], size=1)

        def return_batch(self, rows) -> None:
            self.returned = True

        def archive_batch(self, rows, suffix: str) -> None:
            self.archived = suffix

    queue = RaisingQueue()
    monkeypatch.setattr("web_panel.service.SelectionTableQueue", lambda *_: queue)
    manager._run_workflow(_make_options(tmp_path, single_run=False))
    assert queue.returned is True
    assert manager.status().state == RunState.FAILED


def test_create_task_manager_factory():
    assert isinstance(service.create_task_manager(), WorkflowTaskManager)
