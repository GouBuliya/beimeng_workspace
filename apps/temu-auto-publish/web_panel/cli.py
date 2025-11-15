"""
@PURPOSE: 为 Temu Web Panel 提供 Typer CLI, 实现一键安装与启动
@OUTLINE:
  - install: 通过 uv sync 安装依赖
  - start: 启动 FastAPI Web Panel 并自动打开浏览器
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import threading
import time
from pathlib import Path

import typer
import uvicorn

APP = typer.Typer(help="Temu Web Panel 控制台")
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PORT = 8765


def _import_create_app():
    """兼容直接运行文件与包内运行的导入逻辑."""

    try:  # 优先按包模式导入
        from .api import create_app as factory  # type: ignore[import-not-found]
        return factory
    except ImportError:
        panel_dir = Path(__file__).resolve().parent
        package_root = panel_dir.parent
        for path in (package_root, panel_dir):
            candidate = str(path)
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
        module = importlib.import_module("web_panel.api")
        return module.create_app  # type: ignore[attr-defined]


create_app = _import_create_app()


@APP.command()
def install() -> None:
    """执行 uv sync, 确保依赖齐全."""

    typer.secho("🚀 正在安装 Temu Web Panel 依赖 (uv sync)...", fg=typer.colors.CYAN)
    command = ["uv", "sync", "--group", "temu", "--group", "web"]
    try:
        subprocess.run(command, cwd=REPO_ROOT, check=True)
        typer.secho("✅ 依赖安装完成, 可以继续 start 命令", fg=typer.colors.GREEN)
    except FileNotFoundError as exc:
        raise typer.Exit("未检测到 uv 命令, 请参考 https://docs.astral.sh/uv/install/") from exc
    except subprocess.CalledProcessError as exc:
        raise typer.Exit(f"uv sync 失败, 请检查网络或依赖: {exc}") from exc


@APP.command()
def start(
    host: str = typer.Option("127.0.0.1", help="监听地址, 默认仅本机可访问"),
    port: int = typer.Option(DEFAULT_PORT, help="监听端口"),
    auto_open: bool = typer.Option(True, help="启动后自动打开浏览器"),
) -> None:
    """启动 Web Panel, 提供图形化发布体验."""

    url = f"http://{host}:{port}"
    typer.secho(f"🌐 即将启动 Temu Web Panel -> {url}", fg=typer.colors.CYAN)
    app_instance = create_app()
    config = uvicorn.Config(app_instance, host=host, port=port, reload=False)
    server = uvicorn.Server(config)

    if auto_open:
        typer.secho("⏳ 请稍等, 即将打开浏览器窗口...", fg=typer.colors.MAGENTA)

        def _open_browser() -> None:
            time.sleep(1.2)
            typer.launch(url)

        threading.Thread(target=_open_browser, daemon=True).start()

    try:
        server.run()
    except Exception as exc:  # pragma: no cover - 服务器异常
        typer.secho(f"❌ 启动失败: {exc}", fg=typer.colors.RED)
        raise typer.Exit(1) from exc


def main() -> None:
    """控制台入口."""

    APP()


if __name__ == "__main__":
    main()
