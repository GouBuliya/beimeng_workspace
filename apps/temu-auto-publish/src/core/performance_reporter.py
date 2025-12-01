"""
@PURPOSE: 性能报告生成器 - 提供控制台美化输出和汇总报告
@OUTLINE:
  - class ConsoleReporter: 控制台报告器，提供实时输出和汇总报告
  - format_duration(): 格式化时间显示
  - create_progress_bar(): 创建进度条
@GOTCHAS:
  - 报告器需要绑定 PerformanceTracker 实例
  - print_summary() 应在工作流结束后调用
@DEPENDENCIES:
  - 内部: performance_tracker
  - 外部: loguru
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from .performance_tracker import PerformanceTracker


def format_duration(seconds: float | None) -> str:
    """格式化时间显示

    Args:
        seconds: 秒数

    Returns:
        str: 格式化后的时间字符串，如 "1.23s" 或 "2m 30s"
    """
    if seconds is None:
        return "N/A"

    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.1f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def create_progress_bar(percentage: float, width: int = 20) -> str:
    """创建进度条

    Args:
        percentage: 百分比 (0-100)
        width: 进度条宽度

    Returns:
        str: 进度条字符串，如 "████████░░░░░░░░░░░░"
    """
    if percentage < 0:
        percentage = 0
    if percentage > 100:
        percentage = 100

    filled = int(width * percentage / 100)
    empty = width - filled
    return "█" * filled + "░" * empty


class ConsoleReporter:
    """控制台报告器

    提供实时输出和工作流结束后的汇总报告。

    Example:
        >>> from .performance_tracker import PerformanceTracker
        >>> tracker = PerformanceTracker()
        >>> reporter = ConsoleReporter(tracker)
        >>> # 工作流执行...
        >>> reporter.print_summary()
    """

    SEPARATOR = "═" * 60
    THIN_SEPARATOR = "─" * 60

    def __init__(self, tracker: "PerformanceTracker"):
        """初始化报告器

        Args:
            tracker: 性能追踪器实例
        """
        self.tracker = tracker

    def print_header(self, title: str) -> None:
        """打印报告头部

        Args:
            title: 标题文本
        """
        print()
        print(self.SEPARATOR)
        print(f"  {title}")
        print(self.SEPARATOR)

    def print_workflow_start(self) -> None:
        """打印工作流开始信息"""
        if not self.tracker.workflow:
            return
        self.print_header(f"工作流开始: {self.tracker.workflow.id}")

    def print_summary(self) -> None:
        """打印工作流汇总报告

        在工作流结束后调用，显示：
        - 工作流基本信息
        - 各阶段耗时和占比
        - 进度条可视化
        """
        if not self.tracker.workflow:
            logger.warning("[Performance] 没有可用的工作流数据")
            return

        summary = self.tracker.get_summary()
        workflow = self.tracker.workflow

        # 报告头
        print()
        print(self.SEPARATOR)
        print("  性能报告")
        print(self.SEPARATOR)

        # 基本信息
        print(f"工作流ID: {workflow.id}")
        print(f"总耗时: {format_duration(workflow.duration_s)}")
        print(f"状态: {workflow.status.value}")
        print(f"阶段数: {workflow.stage_count}")

        if workflow.error:
            print(f"错误: {workflow.error}")

        # 阶段耗时分布
        print()
        print(self.THIN_SEPARATOR)
        print("阶段耗时分布:")
        print(self.THIN_SEPARATOR)

        stages = summary.get("stages", [])
        percentages = summary.get("percentages", {})

        # 计算最大名称长度用于对齐
        max_name_len = max((len(s.get("display_name", "")) for s in stages), default=10)

        for stage in stages:
            name = stage.get("display_name", "未知")
            duration = stage.get("duration_s")
            pct = percentages.get(stage.get("name", ""), 0)
            status = stage.get("status", "")
            op_count = stage.get("operation_count", 0)

            # 格式化输出
            duration_str = format_duration(duration)
            bar = create_progress_bar(pct)

            # 状态标记
            status_mark = "✓" if status == "success" else "✗" if status == "failed" else "○"

            print(
                f"  {status_mark} {name:<{max_name_len}}  "
                f"{duration_str:>10}  ({pct:>5.1f}%)  {bar}  "
                f"[{op_count} ops]"
            )

        # 底部
        print(self.SEPARATOR)
        print()

    def print_stage_summary(self, stage_name: str) -> None:
        """打印单个阶段的汇总信息

        Args:
            stage_name: 阶段名称
        """
        if not self.tracker.workflow:
            return

        for stage in self.tracker.workflow.stages:
            if stage.name == stage_name:
                print(f"\n{self.THIN_SEPARATOR}")
                print(f"阶段: {stage.display_name}")
                print(f"耗时: {format_duration(stage.duration_s)}")
                print(f"操作数: {stage.operation_count}")
                print(f"状态: {stage.status.value}")

                if stage.operations:
                    print("\n操作详情:")
                    for op in stage.operations:
                        status_mark = (
                            "✓" if op.status.value == "success" else "✗"
                        )
                        print(
                            f"  {status_mark} {op.name}: "
                            f"{format_duration(op.duration_s)}"
                        )
                        if op.actions:
                            for act in op.actions:
                                act_mark = (
                                    "✓" if act.status.value == "success" else "✗"
                                )
                                print(
                                    f"      {act_mark} {act.name}: "
                                    f"{format_duration(act.duration_s)}"
                                )

                print(self.THIN_SEPARATOR)
                return

        logger.warning(f"[Performance] 未找到阶段: {stage_name}")

    def get_detailed_report(self) -> dict[str, Any]:
        """获取详细报告数据

        Returns:
            dict: 包含完整层级结构的报告数据
        """
        if not self.tracker.workflow:
            return {}

        workflow = self.tracker.workflow
        summary = self.tracker.get_summary()

        report = {
            "workflow": {
                "id": workflow.id,
                "name": workflow.name,
                "status": workflow.status.value,
                "duration_s": workflow.duration_s,
                "start_time": workflow.start_time.isoformat() if workflow.start_time else None,
                "end_time": workflow.end_time.isoformat() if workflow.end_time else None,
                "error": workflow.error,
            },
            "summary": summary,
            "stages": [],
        }

        for stage in sorted(workflow.stages, key=lambda s: s.order):
            stage_data = {
                "name": stage.name,
                "display_name": stage.display_name,
                "order": stage.order,
                "status": stage.status.value,
                "duration_s": stage.duration_s,
                "percentage": summary.get("percentages", {}).get(stage.name, 0),
                "operations": [],
            }

            for op in stage.operations:
                op_data = {
                    "name": op.name,
                    "status": op.status.value,
                    "duration_s": op.duration_s,
                    "metadata": op.metadata,
                    "actions": [],
                }

                for act in op.actions:
                    act_data = {
                        "name": act.name,
                        "status": act.status.value,
                        "duration_s": act.duration_s,
                        "metadata": act.metadata,
                    }
                    op_data["actions"].append(act_data)

                stage_data["operations"].append(op_data)

            report["stages"].append(stage_data)

        return report

    def print_operation_breakdown(self) -> None:
        """打印操作耗时细分

        按耗时从高到低排序显示所有操作
        """
        if not self.tracker.workflow:
            return

        all_operations: list[tuple[str, str, float | None]] = []

        for stage in self.tracker.workflow.stages:
            for op in stage.operations:
                all_operations.append((stage.display_name, op.name, op.duration_s))

        # 按耗时排序
        all_operations.sort(key=lambda x: x[2] or 0, reverse=True)

        print(f"\n{self.THIN_SEPARATOR}")
        print("操作耗时排行 (Top 10):")
        print(self.THIN_SEPARATOR)

        for i, (stage_name, op_name, duration) in enumerate(all_operations[:10], 1):
            print(f"  {i:2}. [{stage_name}] {op_name}: {format_duration(duration)}")

        print(self.THIN_SEPARATOR)
