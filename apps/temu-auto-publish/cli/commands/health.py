"""
@PURPOSE: CLI健康检查命令 - 检查系统各组件健康状态
@OUTLINE:
  - health_app: Typer健康检查命令组
  - check(): 执行健康检查
  - check_component(): 检查特定组件
@DEPENDENCIES:
  - 内部: src.core.health_checker
  - 外部: typer, rich
"""

import asyncio

import typer
from rich.console import Console
from rich.table import Table
from src.core.health_checker import get_health_checker

health_app = typer.Typer(
    name="health",
    help="健康检查和诊断",
)

console = Console()


@health_app.command("check")
def check(
    component: str | None = typer.Option(
        None,
        "--component",
        "-c",
        help="检查特定组件(browser/login/network/disk/memory/dependencies/config_files)",
    ),
    include_network: bool = typer.Option(True, "--network/--no-network", help="是否包含网络检查"),
    json_output: bool = typer.Option(False, "--json", help="以JSON格式输出"),
):
    """执行健康检查.

    Examples:
        # 全面健康检查
        temu-auto-publish health check

        # 检查特定组件
        temu-auto-publish health check --component browser

        # JSON格式输出
        temu-auto-publish health check --json
    """
    health_checker = get_health_checker()

    if component:
        # 检查特定组件
        result = asyncio.run(_check_component(health_checker, component))
    else:
        # 全面检查
        result = asyncio.run(health_checker.check_all(include_network=include_network))

    if json_output:
        import json

        console.print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _display_health_result(result, single_component=bool(component))


async def _check_component(health_checker, component: str):
    """检查特定组件.

    Args:
        health_checker: 健康检查器实例
        component: 组件名称

    Returns:
        检查结果
    """
    try:
        result = await health_checker.check_component(component)
        return result.to_dict()
    except ValueError as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1) from None


def _display_health_result(result, single_component: bool = False):
    """显示健康检查结果.

    Args:
        result: 检查结果
        single_component: 是否为单组件检查
    """
    console.print("\n[bold blue]🏥 健康检查结果[/bold blue]\n")

    if single_component:
        # 单组件检查结果
        _display_component_result(result)
    else:
        # 全面检查结果
        status = result.get("status", "unknown")
        summary = result.get("summary", {})

        # 显示总体状态
        status_icon = {"healthy": "✅", "degraded": "⚠️", "unhealthy": "❌"}.get(status, "❓")

        status_color = {"healthy": "green", "degraded": "yellow", "unhealthy": "red"}.get(
            status, "white"
        )

        console.print(
            f"[{status_color}]{status_icon} 总体状态: {status.upper()}[/{status_color}]\n"
        )

        # 显示统计
        console.print(f"检查项数: {summary.get('total_checks', 0)}")
        console.print(f"  ✓ 正常: {summary.get('ok_count', 0)}")
        console.print(f"  ⚠ 警告: {summary.get('warning_count', 0)}")
        console.print(f"  ✗ 错误: {summary.get('error_count', 0)}")
        console.print(f"\n检查时间: {summary.get('timestamp', '')}\n")

        # 显示详细检查结果
        checks = result.get("checks", {})
        if checks:
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("组件", style="cyan", width=20)
            table.add_column("状态", width=10)
            table.add_column("消息", no_wrap=False)

            for component, check in checks.items():
                status = check.get("status", "unknown")
                message = check.get("message", "")

                status_icon = {
                    "ok": "[green]✓[/green]",
                    "warning": "[yellow]⚠[/yellow]",
                    "error": "[red]✗[/red]",
                    "unknown": "[dim]?[/dim]",
                }.get(status, "?")

                table.add_row(component, status_icon, message)

            console.print(table)
            console.print()

            # 显示详细信息(仅错误和警告)
            for component, check in checks.items():
                if check.get("status") in ["error", "warning"]:
                    details = check.get("details", {})
                    if details:
                        console.print(f"\n[bold]{component} 详细信息:[/bold]")
                        for key, value in details.items():
                            console.print(f"  {key}: {value}")


def _display_component_result(result):
    """显示单组件检查结果.

    Args:
        result: 组件检查结果
    """
    component = result.get("component", "unknown")
    status = result.get("status", "unknown")
    message = result.get("message", "")
    details = result.get("details", {})
    timestamp = result.get("timestamp", "")

    # 状态图标和颜色
    status_icon = {"ok": "✅", "warning": "⚠️", "error": "❌", "unknown": "❓"}.get(status, "❓")

    status_color = {"ok": "green", "warning": "yellow", "error": "red", "unknown": "white"}.get(
        status, "white"
    )

    console.print(f"[bold]组件:[/bold] {component}")
    console.print(
        f"[bold]状态:[/bold] [{status_color}]{status_icon} {status.upper()}[/{status_color}]"
    )
    console.print(f"[bold]消息:[/bold] {message}")
    console.print(f"[bold]时间:[/bold] {timestamp}")

    if details:
        console.print("\n[bold]详细信息:[/bold]")
        for key, value in details.items():
            console.print(f"  {key}: {value}")


@health_app.command("components")
def list_components():
    """列出可检查的组件.

    Examples:
        temu-auto-publish health components
    """
    console.print("\n[bold blue]可检查的组件:[/bold blue]\n")

    components = {
        "browser": "浏览器状态(Playwright)",
        "login": "登录凭证和会话",
        "network": "网络连接",
        "disk": "磁盘空间",
        "memory": "内存使用",
        "dependencies": "Python依赖",
        "config_files": "配置文件",
    }

    for component, description in components.items():
        console.print(f"  [cyan]{component:20}[/cyan] {description}")

    console.print("\n使用方式:")
    console.print("  temu-auto-publish health check --component [组件名]")
