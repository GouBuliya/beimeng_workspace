from __future__ import annotations

import sys
from pathlib import Path
import types

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "temu-auto-publish"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import web_panel.cli as cli  # noqa: E402


def test_install_success_and_failures(monkeypatch):
    calls: list[tuple] = []

    def fake_run(cmd, cwd=None, check=False):
        calls.append((tuple(cmd), cwd, check))
        return cli.subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    cli.install()
    assert calls and calls[0][0][0] == "uv"

    monkeypatch.setattr(
        cli.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError())
    )
    with pytest.raises(cli.typer.Exit):
        cli.install()

    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(cli.subprocess.CalledProcessError(1, "uv")),
    )
    with pytest.raises(cli.typer.Exit):
        cli.install()


def test_start_invokes_uvicorn(monkeypatch):
    captured: dict[str, object] = {}

    class DummyServer:
        def __init__(self, config) -> None:
            captured["config"] = config

        def run(self) -> None:
            captured["ran"] = True

    class DummyConfig:
        def __init__(self, *args, **kwargs) -> None:
            captured["config_kwargs"] = kwargs

    monkeypatch.setattr(cli, "create_app", lambda: "app")
    monkeypatch.setattr(cli.uvicorn, "Config", DummyConfig)
    monkeypatch.setattr(cli.uvicorn, "Server", DummyServer)
    monkeypatch.setattr(cli.typer, "launch", lambda url: captured.setdefault("launch", url))
    monkeypatch.setattr(cli.time, "sleep", lambda *_: None)

    cli.start(host="0.0.0.0", port=1234, auto_open=True, access_log=True)

    assert captured["config_kwargs"]["host"] == "0.0.0.0"
    assert captured["launch"] == "http://0.0.0.0:1234"
    assert captured.get("ran") is True


def test_import_create_app_fallback(monkeypatch):
    dummy_module = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "web_panel.api", dummy_module)
    monkeypatch.setattr(
        cli.importlib,
        "import_module",
        lambda _name: types.SimpleNamespace(create_app=lambda: "fallback"),
    )
    factory = cli._import_create_app()
    assert factory() == "fallback"


def test_main_invokes_app(monkeypatch):
    called = {}
    monkeypatch.setattr(cli, "APP", lambda: called.setdefault("called", True))
    cli.main()
    assert called["called"] is True
