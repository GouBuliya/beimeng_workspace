"""
@PURPOSE: 使用 PyInstaller 打包 TemuWebPanel 安装器 (生成桌面快捷方式)
@OUTLINE:
  - 依赖 dist/TemuWebPanel.exe 作为负载
  - 将 installer/install_temu_web_panel.py 打包为 TemuWebPanelInstaller.exe
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

import typer
from PyInstaller.__main__ import run as pyinstaller_run

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
APP_ROOT: Final[Path] = REPO_ROOT / "apps" / "temu-auto-publish"
DIST_DIR: Final[Path] = REPO_ROOT / "dist"
MAIN_EXE: Final[Path] = DIST_DIR / "TemuWebPanel.exe"
INSTALLER_ENTRY: Final[Path] = APP_ROOT / "installer" / "install_temu_web_panel.py"
DEFAULT_NAME: Final[str] = "TemuWebPanelInstaller"


def _data_arg() -> str:
    return f"{MAIN_EXE}{os.pathsep}payload"


def _build_args(name: str, clean: bool) -> list[str]:
    args = [
        str(INSTALLER_ENTRY),
        f"--name={name}",
        f"--paths={REPO_ROOT}",
        "--onefile",
    ]
    if clean:
        args.append("--clean")
    args.append(f"--add-data={_data_arg()}")
    return args


def build(
    name: str = typer.Option(DEFAULT_NAME, help="输出安装器名称"),
    clean: bool = typer.Option(True, "--clean/--no-clean", help="构建前清理缓存"),
) -> None:
    """构建 Temu Web Panel 安装器."""

    if not MAIN_EXE.exists():
        raise typer.Exit(f"缺少 {MAIN_EXE.name}, 请先运行 build_windows_exe.py")
    if not INSTALLER_ENTRY.exists():
        raise typer.Exit(f"安装器入口不存在: {INSTALLER_ENTRY}")

    typer.echo(f"开始构建 {name}, 负载来自 {MAIN_EXE}")
    pyinstaller_run(_build_args(name=name, clean=clean))
    typer.echo(f"构建完成, 安装器位于 {DIST_DIR}")


if __name__ == "__main__":
    typer.run(build)









