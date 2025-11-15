"""
@PURPOSE: 通过 PyInstaller 打包 Temu Web Panel, 生成 Windows 可执行文件
@OUTLINE:
  - Typer CLI: build 命令
  - _build_args(): 组装 PyInstaller 所需参数
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

import typer
from PyInstaller.__main__ import run as pyinstaller_run

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
ENTRY_FILE: Final[Path] = REPO_ROOT / "apps" / "temu-auto-publish" / "start_web_panel_entry.py"
DEFAULT_NAME: Final[str] = "TemuWebPanel"


def _data_arg(source: Path, target: str) -> str:
    return f"{source}{os.pathsep}{target}"


def _build_args(name: str, clean: bool, onefile: bool) -> list[str]:
    assets = [
        _data_arg(
            REPO_ROOT / "apps" / "temu-auto-publish" / "web_panel" / "templates",
            "web_panel/templates",
        ),
        _data_arg(
            REPO_ROOT / "apps" / "temu-auto-publish" / "web_panel" / "fields.py",
            "web_panel",
        ),
        _data_arg(
            REPO_ROOT / "apps" / "temu-auto-publish" / "data" / "input" / "selection.xlsx",
            "data/input",
        ),
    ]
    args = [
        str(ENTRY_FILE),
        f"--name={name}",
        "--hidden-import=web_panel.api",
        "--hidden-import=web_panel.service",
        "--hidden-import=web_panel.cli",
    ]
    if clean:
        args.append("--clean")
    if onefile:
        args.append("--onefile")
    for asset in assets:
        args.append(f"--add-data={asset}")
    return args


def build(
    name: str = typer.Option(DEFAULT_NAME, help="输出 exe 名称"),
    clean: bool = typer.Option(True, "--clean/--no-clean", help="构建前清理缓存"),
    onefile: bool = typer.Option(True, "--onefile/--no-onefile", help="是否输出单文件"),
) -> None:
    """运行 PyInstaller 生成 exe."""

    if not ENTRY_FILE.exists():
        raise typer.Exit(f"入口脚本不存在: {ENTRY_FILE}")
    typer.echo(f"开始构建 {name} (onefile={onefile}, clean={clean})")
    pyinstaller_run(_build_args(name=name, clean=clean, onefile=onefile))
    typer.echo("构建完成, 产物位于 dist/ 目录")


if __name__ == "__main__":
    typer.run(build)
