from __future__ import annotations

import io
import sys
from pathlib import Path
import importlib

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "apps" / "temu-auto-publish"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

cfg_settings = importlib.import_module("config.settings")  # noqa: E402
common_config = importlib.import_module("packages.common.config")  # noqa: E402
common_logger = importlib.import_module("packages.common.logger")  # noqa: E402


def test_settings_validation_and_masking():
    with pytest.raises(ValueError):
        cfg_settings.Settings.validate_environment("invalid")

    settings = cfg_settings.Settings().model_copy(
        update={"temu_password": "secret", "miaoshou_password": "pwd"}
    )
    masked = settings.to_dict()
    assert masked["temu_password"] == "***"
    assert masked["miaoshou_password"] == "***"


def test_load_environment_config_variants(tmp_path, monkeypatch):
    fake_module = tmp_path / "fake_settings.py"
    fake_module.write_text("# stub")
    env_dir = tmp_path / "environments"
    env_dir.mkdir()

    (env_dir / "loop.yaml").write_text("loop.yaml")
    (env_dir / "missing_alias.yaml").write_text("")
    (env_dir / "blank_alias.yaml").write_text('""')
    (env_dir / "list.yaml").write_text("- item")
    (env_dir / "base.yaml").write_text("key: value")
    (env_dir / "alias_source.yaml").write_text("base")

    monkeypatch.setattr(cfg_settings, "__file__", str(fake_module))

    with pytest.raises(ValueError):
        cfg_settings.load_environment_config("loop")

    with pytest.raises(FileNotFoundError):
        cfg_settings.load_environment_config("absent")

    assert cfg_settings.load_environment_config("missing_alias") == {}

    with pytest.raises(ValueError):
        cfg_settings.load_environment_config("blank_alias")

    with pytest.raises(TypeError):
        cfg_settings.load_environment_config("list")

    alias_loaded = cfg_settings.load_environment_config("alias_source")
    assert alias_loaded["key"] == "value"


def test_create_settings_reads_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setattr(cfg_settings.Settings, "ensure_directories", lambda self: None)
    created = cfg_settings.create_settings()
    assert created.environment == "development"


class DemoConfig(common_config.BaseAppConfig):
    foo: str = "bar"


def test_base_app_config_save_and_load(tmp_path):
    config = DemoConfig(log_level="DEBUG", debug=True, foo="baz")

    json_file = tmp_path / "config.json"
    config.save_to_file(json_file)
    loaded = DemoConfig.from_file(json_file)
    assert loaded.foo == "baz"
    assert loaded.log_level == "DEBUG"

    yaml_file = tmp_path / "config.yaml"
    config.save_to_file(yaml_file)
    loaded_yaml = DemoConfig.from_file(yaml_file)
    assert loaded_yaml.debug is True

    with pytest.raises(ValueError):
        config.save_to_file(tmp_path / "config.txt")
    with pytest.raises(ValueError):
        DemoConfig.from_file(tmp_path / "config.txt")


def test_logger_helpers(monkeypatch, tmp_path):
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    log = common_logger.setup_logger("demo", level="INFO", format_string="{message}|{extra[name]}")
    log.info("hello")
    output = stderr.getvalue()
    assert "hello" in output and "demo" in output

    log_file = tmp_path / "app.log"
    file_logger = common_logger.setup_file_logger(
        "file", log_file=str(log_file), level="INFO", rotation="1 day", retention="1 day"
    )
    file_logger.error("boom")
    assert "boom" in log_file.read_text(encoding="utf-8")


def test_logger_default_format(monkeypatch):
    stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", stderr)
    logger_obj = common_logger.setup_logger("default-demo")
    logger_obj.warning("default message")
    assert "default message" in stderr.getvalue()
