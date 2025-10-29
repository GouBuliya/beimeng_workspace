"""Hello CLI - 示例命令行工具

这是一个展示最佳实践的 CLI 应用示例。

Examples:
    基础使用::

        $ python -m apps.cli.hello greet World
        Hello, World!

    JSON 输出::

        $ python -m apps.cli.hello greet World --format json
        {"message": "Hello, World!", "timestamp": "2025-10-29T12:00:00Z"}
"""

import json
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
import yaml
from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from rich.console import Console

app = typer.Typer(
    name="hello",
    help="简单的 CLI 问候工具",
    add_completion=False,
)
console = Console()


class OutputFormat(str, Enum):
    """输出格式枚举"""

    TEXT = "text"
    JSON = "json"


class HelloConfig(BaseSettings):
    """Hello CLI 配置

    Attributes:
        greeting: 默认问候语
        log_level: 日志级别
    """

    model_config = SettingsConfigDict(
        env_prefix="HELLO_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    greeting: str = Field(default="Hello", description="默认问候语")
    log_level: str = Field(default="INFO", description="日志级别")


def load_config(config_path: Optional[Path] = None) -> HelloConfig:
    """加载配置

    Args:
        config_path: 配置文件路径（可选）

    Returns:
        配置对象

    Raises:
        FileNotFoundError: 配置文件不存在
        ValueError: 配置文件格式错误
    """
    if config_path:
        if not config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_path}")

        try:
            with open(config_path) as f:
                config_data = yaml.safe_load(f)
                return HelloConfig(**config_data)
        except Exception as e:
            raise ValueError(f"配置文件格式错误: {e}") from e

    return HelloConfig()


def greet_user(name: str, greeting: str = "Hello") -> str:
    """生成问候消息

    Args:
        name: 要问候的名字
        greeting: 问候语

    Returns:
        问候消息字符串

    Examples:
        >>> greet_user("World")
        'Hello, World!'
        >>> greet_user("世界", "你好")
        '你好, 世界!'
    """
    return f"{greeting}, {name}!"


@app.command()
def greet(
    name: str = typer.Argument(..., help="要问候的名字"),
    greeting: Optional[str] = typer.Option(None, "--greeting", "-g", help="问候语"),
    output_format: OutputFormat = typer.Option(
        OutputFormat.TEXT,
        "--format",
        "-f",
        help="输出格式",
    ),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="配置文件路径",
        exists=True,
        dir_okay=False,
    ),
) -> None:
    """问候指定的人

    Args:
        name: 要问候的名字
        greeting: 自定义问候语（可选）
        output_format: 输出格式（text 或 json）
        config_path: 配置文件路径（可选）
    """
    try:
        # 加载配置
        config = load_config(config_path)
        logger.configure(handlers=[{"sink": "stderr", "level": config.log_level}])

        # 使用命令行参数或配置文件中的问候语
        final_greeting = greeting or config.greeting

        # 生成问候消息
        message = greet_user(name, final_greeting)
        timestamp = datetime.now(timezone.utc).isoformat()

        logger.debug(f"生成问候消息: {message}")

        # 输出结果
        if output_format == OutputFormat.JSON:
            result = {"message": message, "timestamp": timestamp}
            console.print_json(json.dumps(result, ensure_ascii=False))
        else:
            console.print(message)

    except Exception as e:
        logger.error(f"执行失败: {e}")
        raise typer.Exit(code=1) from e


@app.command()
def version() -> None:
    """显示版本信息"""
    console.print("hello-cli v0.1.0")


if __name__ == "__main__":
    app()

