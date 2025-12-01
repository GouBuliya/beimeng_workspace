"""
@PURPOSE: CLI 调试命令 - 管理调试功能
@OUTLINE:
  - debug_app: Typer 调试命令组
  - enable(): 启用调试
  - disable(): 禁用调试
  - screenshot(): 手动截图
  - list(): 列出调试文件
  - clean(): 清理调试文件
@DEPENDENCIES:
  - 内部: src.utils.debug_helper
  - 外部: typer, rich
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from config.settings import settings

debug_app = typer.Typer(
    name="debug",
    help="调试功能管理",
)

console = Console()


@debug_app.command("enable")
def enable(
    all: bool = typer.Option(False, "--all", help="启用所有调试功能"),
    screenshot: bool = typer.Option(False, "--screenshot", help="启用截图"),
    html: bool = typer.Option(False, "--html", help="启用HTML保存"),
    timing: bool = typer.Option(False, "--timing", help="启用计时"),
):
    """启用调试功能.

    Examples:
        temu-auto-publish debug enable --all
        temu-auto-publish debug enable --screenshot --timing
    """
    console.print("\n[bold blue]🐛 启用调试[/bold blue]\n")

    if all:
        settings.debug.enabled = True
        settings.debug.auto_screenshot = True
        settings.debug.auto_save_html = True
        settings.debug.enable_timing = True
        console.print("[green]✓[/green] 已启用所有调试功能")
    else:
        if screenshot:
            settings.debug.auto_screenshot = True
            console.print("[green]✓[/green] 已启用自动截图")
        if html:
            settings.debug.auto_save_html = True
            console.print("[green]✓[/green] 已启用HTML保存")
        if timing:
            settings.debug.enable_timing = True
            console.print("[green]✓[/green] 已启用计时")

    console.print("\n[yellow]⚠[/yellow] 调试功能会影响性能，生产环境请谨慎使用")


@debug_app.command("disable")
def disable():
    """禁用调试功能.

    Examples:
        temu-auto-publish debug disable
    """
    console.print("\n[bold blue]🐛 禁用调试[/bold blue]\n")

    settings.debug.enabled = False
    settings.debug.auto_screenshot = False
    settings.debug.auto_save_html = False
    settings.debug.enable_timing = False

    console.print("[green]✓[/green] 已禁用调试功能")


@debug_app.command("list")
def list_debug_files(
    limit: int = typer.Option(20, "--limit", "-n", help="显示数量"),
):
    """列出调试文件.

    Examples:
        temu-auto-publish debug list
        temu-auto-publish debug list -n 50
    """
    console.print("\n[bold blue]📁 调试文件[/bold blue]\n")

    debug_dir = settings.get_absolute_path(settings.debug.debug_dir)

    if not debug_dir.exists():
        console.print("[yellow]⚠[/yellow] 调试目录不存在")
        return

    # 获取所有调试文件
    files = sorted(debug_dir.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]

    if not files:
        console.print("[yellow]⚠[/yellow] 暂无调试文件")
        return

    # 创建表格
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("文件名", style="cyan")
    table.add_column("类型")
    table.add_column("大小", justify="right")
    table.add_column("修改时间")

    total_size = 0

    for file_path in files:
        file_size = file_path.stat().st_size
        total_size += file_size

        # 格式化大小
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"

        # 修改时间
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        time_str = mtime.strftime("%Y-%m-%d %H:%M:%S")

        table.add_row(file_path.name[:50], file_path.suffix[1:].upper(), size_str, time_str)

    console.print(table)

    # 总计
    if total_size < 1024 * 1024:
        total_str = f"{total_size / 1024:.1f} KB"
    else:
        total_str = f"{total_size / (1024 * 1024):.1f} MB"

    console.print(f"\n共 {len(files)} 个文件，总大小: {total_str}")


@debug_app.command("clean")
def clean(
    days: int = typer.Option(7, "--days", help="保留天数"),
    force: bool = typer.Option(False, "--force", help="强制删除（不确认）"),
):
    """清理旧的调试文件.

    Examples:
        temu-auto-publish debug clean --days 7
        temu-auto-publish debug clean --force
    """
    console.print("\n[bold blue]🧹 清理调试文件[/bold blue]\n")

    debug_dir = settings.get_absolute_path(settings.debug.debug_dir)

    if not debug_dir.exists():
        console.print("[yellow]⚠[/yellow] 调试目录不存在")
        return

    from datetime import datetime, timedelta

    cutoff_time = datetime.now() - timedelta(days=days)

    # 查找要删除的文件
    files_to_delete = [
        f for f in debug_dir.glob("*.*") if datetime.fromtimestamp(f.stat().st_mtime) < cutoff_time
    ]

    if not files_to_delete:
        console.print(f"[green]✓[/green] 没有超过 {days} 天的文件需要清理")
        return

    # 确认
    if not force:
        console.print(f"将删除 {len(files_to_delete)} 个文件（超过 {days} 天）")
        confirm = typer.confirm("确认删除？")
        if not confirm:
            console.print("已取消")
            return

    # 删除
    deleted = 0
    for file_path in files_to_delete:
        try:
            file_path.unlink()
            deleted += 1
        except Exception as e:
            console.print(f"[red]✗[/red] 删除失败: {file_path.name} - {e}")

    console.print(f"[green]✓[/green] 已删除 {deleted} 个文件")
