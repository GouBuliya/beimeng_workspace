from __future__ import annotations

import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "temu-auto-publish"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from web_panel import env_settings  # noqa: E402


def test_resolve_env_file_with_override(tmp_path, monkeypatch):
    env_file = tmp_path / ".env.override"
    monkeypatch.setenv("TEMU_WEB_PANEL_ENV", str(env_file))
    path = env_settings.resolve_env_file()
    assert path == env_file
    assert path.exists()


def test_resolve_env_file_when_frozen(tmp_path, monkeypatch):
    monkeypatch.delenv("TEMU_WEB_PANEL_ENV", raising=False)
    monkeypatch.setattr(env_settings.sys, "frozen", True, raising=False)
    monkeypatch.setattr(env_settings.Path, "home", staticmethod(lambda: tmp_path))
    path = env_settings.resolve_env_file()
    assert path == tmp_path / "TemuWebPanel" / ".env"
    assert path.exists()


def test_build_env_payload_and_validation(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    monkeypatch.setenv("TEMU_WEB_PANEL_ENV", str(env_file))
    env_file.write_text("MIAOSHOU_USERNAME=demo\n")

    payload = env_settings.build_env_payload()
    payload_by_key = {entry["key"]: entry for entry in payload}
    assert payload_by_key["MIAOSHOU_USERNAME"]["value"] == "demo"
    assert payload_by_key["MIAOSHOU_PASSWORD"]["value"] == ""

    missing = env_settings.validate_required({"MIAOSHOU_PASSWORD": ""})
    assert missing == ["妙手密码"]

    still_missing = env_settings.validate_required(
        {"MIAOSHOU_USERNAME": "demo", "MIAOSHOU_PASSWORD": "secret"}
    )
    assert still_missing == []


def test_persist_env_settings_skips_none(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    monkeypatch.setenv("TEMU_WEB_PANEL_ENV", str(env_file))
    env_settings.persist_env_settings({"MIAOSHOU_USERNAME": "tester", "MIAOSHOU_PASSWORD": None})

    values = dotenv_values(env_file)
    assert values["MIAOSHOU_USERNAME"] == "tester"
    assert "MIAOSHOU_PASSWORD" not in values
