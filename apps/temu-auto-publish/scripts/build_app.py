"""
@PURPOSE: 跨平台构建脚本，支持 Windows/macOS/Linux 打包 Temu Web Panel
@OUTLINE:
  - Typer CLI: build 命令
  - _build_args(): 动态组装 PyInstaller 参数（自动适配当前平台）
  - _get_platform_suffix(): 获取平台后缀用于产物命名
@DEPENDENCIES:
  - 外部: typer, PyInstaller
"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Final

import typer

# 动态计算路径（支持 CI 环境）
SCRIPT_DIR: Final[Path] = Path(__file__).resolve().parent
APP_ROOT: Final[Path] = SCRIPT_DIR.parent
REPO_ROOT: Final[Path] = APP_ROOT.parents[1]
ENTRY_FILE: Final[Path] = SCRIPT_DIR / "start_web_panel_entry.py"
DEFAULT_NAME: Final[str] = "TemuWebPanel"

app = typer.Typer(help="跨平台构建 Temu Web Panel 可执行文件")


def _get_platform_suffix() -> str:
    """获取平台后缀用于产物命名."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        return "windows-x64"
    elif system == "darwin":
        # macOS: 区分 Intel 和 Apple Silicon
        if machine in ("arm64", "aarch64"):
            return "macos-arm64"
        return "macos-x64"
    elif system == "linux":
        if machine in ("arm64", "aarch64"):
            return "linux-arm64"
        return "linux-x64"
    return f"{system}-{machine}"


def _get_executable_ext() -> str:
    """获取可执行文件扩展名."""
    return ".exe" if platform.system().lower() == "windows" else ""


def _data_arg(source: Path, target: str) -> str:
    """生成 PyInstaller --add-data 参数."""
    return f"{source}{os.pathsep}{target}"


def _build_args(name: str, clean: bool, onefile: bool, console: bool) -> list[str]:
    """组装 PyInstaller 构建参数."""
    assets = [
        _data_arg(APP_ROOT / "web_panel" / "templates", "web_panel/templates"),
        _data_arg(APP_ROOT / "config", "config"),
        _data_arg(APP_ROOT / "web_panel" / "fields.py", "web_panel"),
    ]
    hidden_imports = [
        "web_panel.api",
        "web_panel.service",
        "web_panel.cli",
        "src.workflows.complete_publish_workflow",
        "itsdangerous",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
    ]

    args = [
        str(ENTRY_FILE),
        f"--name={name}",
        f"--paths={REPO_ROOT}",
        f"--paths={APP_ROOT}",
        f"--paths={APP_ROOT / 'src'}",
        "--copy-metadata=playwright",
        "--copy-metadata=playwright_stealth",
        "--collect-all=playwright",
        "--collect-all=playwright_stealth",
        "--collect-submodules=src",
        "--collect-submodules=web_panel",
        f"--distpath={APP_ROOT / 'dist'}",
        f"--workpath={APP_ROOT / 'build'}",
        f"--specpath={APP_ROOT}",
    ]

    for hidden in hidden_imports:
        args.append(f"--hidden-import={hidden}")

    if clean:
        args.append("--clean")

    if onefile:
        args.append("--onefile")

    if not console:
        args.append("--windowed")

    for asset in assets:
        args.append(f"--add-data={asset}")

    return args


@app.command()
def build(
    name: str = typer.Option(DEFAULT_NAME, "--name", "-n", help="输出可执行文件名称"),
    clean: bool = typer.Option(True, "--clean/--no-clean", help="构建前清理缓存"),
    onefile: bool = typer.Option(True, "--onefile/--no-onefile", help="输出单文件"),
    console: bool = typer.Option(True, "--console/--no-console", help="显示控制台窗口"),
    with_suffix: bool = typer.Option(False, "--with-suffix", help="在文件名添加平台后缀"),
) -> None:
    """构建 Temu Web Panel 可执行文件.

    支持 Windows、macOS、Linux 三大平台，自动检测当前系统。

    示例:
        uv run python scripts/build_app.py build
        uv run python scripts/build_app.py build --name MyApp --with-suffix
    """
    # 延迟导入，避免在非构建场景下加载 PyInstaller
    from PyInstaller.__main__ import run as pyinstaller_run

    if not ENTRY_FILE.exists():
        typer.echo(f"❌ 入口脚本不存在: {ENTRY_FILE}", err=True)
        raise typer.Exit(1)

    # 构建文件名
    final_name = name
    if with_suffix:
        final_name = f"{name}-{_get_platform_suffix()}"

    typer.echo(f"🔨 开始构建 {final_name}")
    typer.echo(f"   平台: {platform.system()} ({platform.machine()})")
    typer.echo(f"   Python: {sys.version.split()[0]}")
    typer.echo(f"   单文件: {onefile}")
    typer.echo(f"   清理缓存: {clean}")

    args = _build_args(name=final_name, clean=clean, onefile=onefile, console=console)
    pyinstaller_run(args)

    # 输出产物路径
    ext = _get_executable_ext()
    output_path = APP_ROOT / "dist" / f"{final_name}{ext}"
    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        typer.echo("✅ 构建完成!")
        typer.echo(f"   产物: {output_path}")
        typer.echo(f"   大小: {size_mb:.1f} MB")
    else:
        typer.echo(f"⚠️ 构建完成，但未找到预期产物: {output_path}")


@app.command()
def info() -> None:
    """显示当前平台信息."""
    typer.echo(f"系统: {platform.system()}")
    typer.echo(f"架构: {platform.machine()}")
    typer.echo(f"平台后缀: {_get_platform_suffix()}")
    typer.echo(f"可执行文件扩展名: {_get_executable_ext() or '(无)'}")
    typer.echo(f"Python 版本: {sys.version}")
    typer.echo(f"项目根目录: {REPO_ROOT}")
    typer.echo(f"应用根目录: {APP_ROOT}")
    typer.echo(f"入口文件: {ENTRY_FILE}")


if __name__ == "__main__":
    app()
