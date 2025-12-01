"""
@PURPOSE: CLI 监控命令 - 查看指标和生成报告
@OUTLINE:
  - monitor_app: Typer 监控命令组
  - stats(): 显示统计信息
  - report(): 生成报告
  - watch(): 实时监控(TODO)
@DEPENDENCIES:
  - 内部: src.core.performance_tracker
  - 外部: typer, rich
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import typer
from config.settings import settings
from loguru import logger
from rich.console import Console
from rich.table import Table

monitor_app = typer.Typer(
    name="monitor",
    help="监控和指标管理",
)

console = Console()


@monitor_app.command("stats")
def stats(
    last: str | None = typer.Option(None, "--last", help="时间范围(如: 1h, 24h, 7d)"),
    workflow_id: str | None = typer.Option(None, "--workflow", help="指定工作流ID"),
):
    """显示统计信息.

    Examples:
        temu-auto-publish monitor stats
        temu-auto-publish monitor stats --last 24h
        temu-auto-publish monitor stats --workflow workflow_abc123
    """
    console.print("\n[bold blue]📊 指标统计[/bold blue]\n")

    metrics_dir = settings.get_absolute_path(settings.metrics.storage_dir)

    if not metrics_dir.exists():
        console.print("[yellow]⚠[/yellow] 暂无指标数据")
        return

    # 加载指标文件
    metric_files = sorted(metrics_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not metric_files:
        console.print("[yellow]⚠[/yellow] 暂无指标数据")
        return

    # 过滤时间范围
    if last:
        cutoff_time = _parse_time_range(last)
        metric_files = [
            f for f in metric_files if datetime.fromtimestamp(f.stat().st_mtime) >= cutoff_time
        ]

    # 过滤工作流
    if workflow_id:
        metric_files = [f for f in metric_files if workflow_id in f.name]

    if not metric_files:
        console.print("[yellow]⚠[/yellow] 未找到符合条件的指标数据")
        return

    # 统计数据
    total_workflows = len(metric_files)
    total_success = 0
    total_failure = 0
    total_duration = 0.0

    stage_stats = {
        "stage1": {"count": 0, "success": 0, "total_duration": 0.0},
        "stage2": {"count": 0, "success": 0, "total_duration": 0.0},
        "stage3": {"count": 0, "success": 0, "total_duration": 0.0},
    }

    # 处理每个指标文件
    for metric_file in metric_files:
        try:
            data = json.loads(metric_file.read_text(encoding="utf-8"))

            # 工作流状态
            if data.get("status") == "success":
                total_success += 1
            else:
                total_failure += 1

            # 总耗时
            if data.get("duration"):
                total_duration += data["duration"]

            # 阶段统计
            for stage_name, stage_data in data.get("stages", {}).items():
                if stage_name in stage_stats:
                    stage_stats[stage_name]["count"] += 1
                    if stage_data.get("success"):
                        stage_stats[stage_name]["success"] += 1
                    if stage_data.get("duration"):
                        stage_stats[stage_name]["total_duration"] += stage_data["duration"]

        except Exception as e:
            logger.warning(f"读取指标文件失败: {e}")

    # 显示总体统计
    console.print("[bold]总体统计:[/bold]")
    console.print(f"  总工作流数: {total_workflows}")
    console.print(f"  成功: {total_success} ({total_success / total_workflows * 100:.1f}%)")
    console.print(f"  失败: {total_failure} ({total_failure / total_workflows * 100:.1f}%)")
    console.print(f"  平均耗时: {total_duration / total_workflows:.1f}秒")

    # 显示阶段统计
    console.print("\n[bold]阶段统计:[/bold]")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("阶段", style="cyan")
    table.add_column("执行次数", justify="right")
    table.add_column("成功率", justify="right")
    table.add_column("平均耗时", justify="right")

    for stage_name, stats in stage_stats.items():
        if stats["count"] > 0:
            success_rate = stats["success"] / stats["count"] * 100
            avg_duration = stats["total_duration"] / stats["count"]

            table.add_row(
                stage_name, str(stats["count"]), f"{success_rate:.1f}%", f"{avg_duration:.1f}s"
            )

    console.print(table)
    console.print(f"\n数据来源: {len(metric_files)} 个指标文件")


@monitor_app.command("report")
def report(
    output: Path = typer.Option(
        Path("data/reports/report.csv"), "--output", "-o", help="输出文件路径"
    ),
    format: str = typer.Option("csv", "--format", "-f", help="输出格式(csv/json)"),
    last: str | None = typer.Option(None, "--last", help="时间范围"),
):
    """生成指标报告.

    Examples:
        temu-auto-publish monitor report
        temu-auto-publish monitor report -o report.json -f json
        temu-auto-publish monitor report --last 7d
    """
    console.print("\n[bold blue]📄 生成报告[/bold blue]\n")

    metrics_dir = settings.get_absolute_path(settings.metrics.storage_dir)

    if not metrics_dir.exists():
        console.print("[red]✗[/red] 暂无指标数据")
        raise typer.Exit(1)

    # 加载指标文件
    metric_files = sorted(metrics_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not metric_files:
        console.print("[red]✗[/red] 暂无指标数据")
        raise typer.Exit(1)

    # 过滤时间范围
    if last:
        cutoff_time = _parse_time_range(last)
        metric_files = [
            f for f in metric_files if datetime.fromtimestamp(f.stat().st_mtime) >= cutoff_time
        ]

    # 收集数据
    report_data = []

    for metric_file in metric_files:
        try:
            data = json.loads(metric_file.read_text(encoding="utf-8"))
            report_data.append(data)
        except Exception as e:
            logger.warning(f"读取指标文件失败: {e}")

    # 导出
    output.parent.mkdir(parents=True, exist_ok=True)

    if format == "json":
        output.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
    elif format == "csv":
        import csv

        with output.open("w", newline="", encoding="utf-8") as f:
            if report_data:
                writer = csv.DictWriter(f, fieldnames=report_data[0].keys())
                writer.writeheader()
                writer.writerows(report_data)

    console.print(f"[green]✓[/green] 报告已生成: {output}")
    console.print(f"  包含 {len(report_data)} 条记录")


@monitor_app.command("watch")
def watch():
    """实时监控工作流执行.

    Examples:
        temu-auto-publish monitor watch
    """
    console.print("\n[bold blue]👁️  实时监控[/bold blue]\n")
    console.print("[yellow]⚠[/yellow] 此功能正在开发中...")

    # TODO: 实现实时监控
    # 1. 监听指标文件变化
    # 2. 实时显示执行进度
    # 3. 实时更新统计信息


# ========== 辅助函数 ==========


def _parse_time_range(time_str: str) -> datetime:
    """解析时间范围字符串.

    Args:
        time_str: 时间范围(如: 1h, 24h, 7d)

    Returns:
        截止时间
    """
    import re

    match = re.match(r"(\d+)([hd])", time_str)
    if not match:
        raise ValueError(f"无效的时间范围: {time_str}")

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "h":
        delta = timedelta(hours=value)
    elif unit == "d":
        delta = timedelta(days=value)
    else:
        raise ValueError(f"不支持的时间单位: {unit}")

    return datetime.now() - delta
