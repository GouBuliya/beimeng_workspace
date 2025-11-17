"""
@PURPOSE: 管理 .env 配置字段, 提供读取/写入能力
@OUTLINE:
  - dataclass EnvField: 字段元数据
  - ENV_FIELDS: 受支持的字段列表
  - resolve_env_file(): 根据环境确定 .env 文件路径
  - load_env_values(): 读取当前值
  - build_env_payload(): 组合元数据 + 值
  - persist_env_settings(): 写入并刷新环境变量
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import dotenv_values, load_dotenv, set_key

APP_ROOT: Final[Path] = Path(__file__).resolve().parents[1]


@dataclass(slots=True, frozen=True)
class EnvField:
    """描述单个 .env 字段."""

    key: str
    label: str
    help_text: str
    required: bool = False
    placeholder: str | None = None
    default: str | None = None
    secret: bool = False


ENV_FIELDS: Final[tuple[EnvField, ...]] = (
    EnvField(
        key="MIAOSHOU_URL",
        label="妙手 ERP 地址",
        help_text="通常无需修改, 除非妙手域名发生变化。",
        default="https://erp.91miaoshou.com/sub_account/users",
    ),
    EnvField(
        key="MIAOSHOU_USERNAME",
        label="妙手账号",
        help_text="用于登录妙手 ERP 的子账号或主账号。",
        required=True,
    ),
    EnvField(
        key="MIAOSHOU_PASSWORD",
        label="妙手密码",
        help_text="与账号配套的登录密码。",
        required=True,
        secret=True,
    ),
    EnvField(
        key="DASHSCOPE_API_KEY",
        label="DashScope API Key",
        help_text="可选, 用于启用 AI 标题 (留空则关闭)。",
        secret=True,
    ),
    EnvField(
        key="OPENAI_MODEL",
        label="AI 模型",
        help_text="默认使用 `qwen3-vl-plus`, 如需其它模型可修改。",
        default="qwen3-vl-plus",
    ),
    EnvField(
        key="OPENAI_BASE_URL",
        label="AI 接口 Base URL",
        help_text="DashScope 模式一般无需调整。",
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
    ),
    EnvField(
        key="TEMU_SHOP_URL",
        label="Temu 店铺后台地址",
        help_text="需要自动发布到 Temu 时填写。",
        default="https://agentseller.temu.com/",
    ),
    EnvField(
        key="TEMU_USERNAME",
        label="Temu 账号",
        help_text="可选, 用于 Temu 后台操作。",
        default="tester",
    ),
    EnvField(
        key="TEMU_PASSWORD",
        label="Temu 密码",
        help_text="可选, 与 Temu 账号配套。",
        secret=True,
    ),
    EnvField(
        key="SIZE_CHART_BASE_URL",
        label="尺寸图 OSS 前缀",
        help_text="选品表未提供尺寸图时会用该前缀 + 文件名拼接。",
    ),
    EnvField(
        key="VIDEO_BASE_URL",
        label="视频 OSS 前缀",
        help_text="选品表未提供视频链接时使用。",
    ),
)


def resolve_env_file() -> Path:
    """定位 .env 文件路径."""

    env_override = os.getenv("TEMU_WEB_PANEL_ENV")
    if env_override:
        env_path = Path(env_override)
    elif getattr(sys, "frozen", False):
        env_path = Path.home() / "TemuWebPanel" / ".env"
    else:
        env_path = APP_ROOT / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        env_path.touch()
    return env_path


def load_env_values() -> dict[str, str]:
    """读取当前 .env 的键值."""

    env_path = resolve_env_file()
    values = dotenv_values(env_path)
    return {k: v for k, v in values.items() if v is not None}


def build_env_payload() -> list[dict[str, str | bool | None]]:
    """组合字段元数据与当前值."""

    current = load_env_values()
    payload: list[dict[str, str | bool | None]] = []
    for field in ENV_FIELDS:
        payload.append(
            {
                "key": field.key,
                "label": field.label,
                "help_text": field.help_text,
                "required": field.required,
                "placeholder": field.placeholder,
                "secret": field.secret,
                "value": current.get(field.key) or field.default or "",
            }
        )
    return payload


def validate_required(values: dict[str, str | None]) -> list[str]:
    """返回缺失的必填项标签."""

    merged = load_env_values()
    merged.update({k: (v or "").strip() for k, v in values.items()})
    missing: list[str] = []
    for field in ENV_FIELDS:
        if not field.required:
            continue
        candidate = merged.get(field.key) or field.default or ""
        if not candidate.strip():
            missing.append(field.label)
    return missing


def persist_env_settings(values: dict[str, str | None]) -> None:
    """写入 .env 并刷新当前进程的环境变量."""

    env_path = resolve_env_file()
    path_str = str(env_path)
    for key, value in values.items():
        if value is None:
            continue
        set_key(path_str, key, value)
    load_dotenv(env_path, override=True)
