"""
@PURPOSE: 测试 core/performance_reporter.py 性能报告生成器
@OUTLINE:
  - class TestFormatDuration: 测试时间格式化
  - class TestCreateProgressBar: 测试进度条创建
  - class TestConsoleReporter: 测试控制台报告器
@DEPENDENCIES:
  - 外部: pytest
  - 内部: src.core.performance_reporter
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest


class TestFormatDuration:
    """测试 format_duration 函数."""

    def test_none_returns_na(self) -> None:
        """测试 None 返回 N/A."""
        from src.core.performance_reporter import format_duration

        assert format_duration(None) == "N/A"

    def test_seconds_less_than_60(self) -> None:
        """测试小于 60 秒的格式化."""
        from src.core.performance_reporter import format_duration

        assert format_duration(1.23) == "1.23s"
        assert format_duration(30.00) == "30.00s"
        assert format_duration(59.99) == "59.99s"

    def test_seconds_between_60_and_3600(self) -> None:
        """测试 1 分钟到 1 小时之间的格式化."""
        from src.core.performance_reporter import format_duration

        result = format_duration(90)
        assert "1m" in result
        assert "30" in result

        result = format_duration(150)
        assert "2m" in result
        assert "30" in result

    def test_seconds_more_than_3600(self) -> None:
        """测试超过 1 小时的格式化."""
        from src.core.performance_reporter import format_duration

        result = format_duration(3660)  # 1 小时 1 分钟
        assert "1h" in result
        assert "1m" in result

        result = format_duration(7200)  # 2 小时
        assert "2h" in result
        assert "0m" in result

    def test_zero_seconds(self) -> None:
        """测试 0 秒."""
        from src.core.performance_reporter import format_duration

        assert format_duration(0) == "0.00s"


class TestCreateProgressBar:
    """测试 create_progress_bar 函数."""

    def test_zero_percent(self) -> None:
        """测试 0% 进度条."""
        from src.core.performance_reporter import create_progress_bar

        bar = create_progress_bar(0, width=10)
        assert bar == "░" * 10

    def test_100_percent(self) -> None:
        """测试 100% 进度条."""
        from src.core.performance_reporter import create_progress_bar

        bar = create_progress_bar(100, width=10)
        assert bar == "█" * 10

    def test_50_percent(self) -> None:
        """测试 50% 进度条."""
        from src.core.performance_reporter import create_progress_bar

        bar = create_progress_bar(50, width=10)
        assert bar == "█████░░░░░"

    def test_negative_percent(self) -> None:
        """测试负数百分比被修正为 0."""
        from src.core.performance_reporter import create_progress_bar

        bar = create_progress_bar(-10, width=10)
        assert bar == "░" * 10

    def test_over_100_percent(self) -> None:
        """测试超过 100% 被修正为 100%."""
        from src.core.performance_reporter import create_progress_bar

        bar = create_progress_bar(150, width=10)
        assert bar == "█" * 10

    def test_custom_width(self) -> None:
        """测试自定义宽度."""
        from src.core.performance_reporter import create_progress_bar

        bar = create_progress_bar(50, width=20)
        assert len(bar) == 20
        assert bar.count("█") == 10
        assert bar.count("░") == 10


class TestConsoleReporter:
    """测试 ConsoleReporter 类."""

    @pytest.fixture
    def mock_tracker(self):
        """创建模拟的性能追踪器."""
        tracker = MagicMock()

        # 创建模拟的工作流
        workflow = MagicMock()
        workflow.id = "test_workflow_123"
        workflow.name = "测试工作流"
        workflow.duration_s = 120.5
        workflow.status = MagicMock()
        workflow.status.value = "success"
        workflow.stage_count = 3
        workflow.error = None
        workflow.start_time = datetime(2025, 1, 1, 10, 0, 0)
        workflow.end_time = datetime(2025, 1, 1, 10, 2, 0)

        # 创建模拟的阶段
        stage1 = MagicMock()
        stage1.name = "stage1"
        stage1.display_name = "阶段1"
        stage1.order = 1
        stage1.duration_s = 30.0
        stage1.operation_count = 5
        stage1.status = MagicMock()
        stage1.status.value = "success"
        stage1.operations = []

        stage2 = MagicMock()
        stage2.name = "stage2"
        stage2.display_name = "阶段2"
        stage2.order = 2
        stage2.duration_s = 60.0
        stage2.operation_count = 10
        stage2.status = MagicMock()
        stage2.status.value = "success"
        stage2.operations = []

        stage3 = MagicMock()
        stage3.name = "stage3"
        stage3.display_name = "阶段3"
        stage3.order = 3
        stage3.duration_s = 30.5
        stage3.operation_count = 3
        stage3.status = MagicMock()
        stage3.status.value = "failed"
        stage3.operations = []

        workflow.stages = [stage1, stage2, stage3]
        tracker.workflow = workflow

        # 设置 get_summary 返回值
        tracker.get_summary.return_value = {
            "stages": [
                {
                    "name": "stage1",
                    "display_name": "阶段1",
                    "duration_s": 30.0,
                    "status": "success",
                    "operation_count": 5,
                },
                {
                    "name": "stage2",
                    "display_name": "阶段2",
                    "duration_s": 60.0,
                    "status": "success",
                    "operation_count": 10,
                },
                {
                    "name": "stage3",
                    "display_name": "阶段3",
                    "duration_s": 30.5,
                    "status": "failed",
                    "operation_count": 3,
                },
            ],
            "percentages": {
                "stage1": 24.9,
                "stage2": 49.8,
                "stage3": 25.3,
            },
        }

        return tracker

    def test_init(self, mock_tracker) -> None:
        """测试初始化."""
        from src.core.performance_reporter import ConsoleReporter

        reporter = ConsoleReporter(mock_tracker)
        assert reporter.tracker == mock_tracker

    def test_print_header(self, mock_tracker, capsys) -> None:
        """测试打印报告头部."""
        from src.core.performance_reporter import ConsoleReporter

        reporter = ConsoleReporter(mock_tracker)
        reporter.print_header("测试标题")

        captured = capsys.readouterr()
        assert "测试标题" in captured.out
        assert "═" in captured.out

    def test_print_workflow_start(self, mock_tracker, capsys) -> None:
        """测试打印工作流开始信息."""
        from src.core.performance_reporter import ConsoleReporter

        reporter = ConsoleReporter(mock_tracker)
        reporter.print_workflow_start()

        captured = capsys.readouterr()
        assert "工作流开始" in captured.out
        assert "test_workflow_123" in captured.out

    def test_print_workflow_start_no_workflow(self, capsys) -> None:
        """测试没有工作流时不打印."""
        from src.core.performance_reporter import ConsoleReporter

        tracker = MagicMock()
        tracker.workflow = None

        reporter = ConsoleReporter(tracker)
        reporter.print_workflow_start()

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_summary(self, mock_tracker, capsys) -> None:
        """测试打印工作流汇总报告."""
        from src.core.performance_reporter import ConsoleReporter

        reporter = ConsoleReporter(mock_tracker)
        reporter.print_summary()

        captured = capsys.readouterr()
        assert "性能报告" in captured.out
        assert "工作流ID" in captured.out
        assert "test_workflow_123" in captured.out
        assert "总耗时" in captured.out
        assert "阶段1" in captured.out
        assert "阶段2" in captured.out
        assert "阶段3" in captured.out

    def test_print_summary_no_workflow(self, capsys) -> None:
        """测试没有工作流时的汇总."""
        from src.core.performance_reporter import ConsoleReporter

        tracker = MagicMock()
        tracker.workflow = None

        reporter = ConsoleReporter(tracker)
        reporter.print_summary()

        # 应该只有警告日志,没有输出

    def test_print_summary_with_error(self, mock_tracker, capsys) -> None:
        """测试带错误信息的汇总."""
        from src.core.performance_reporter import ConsoleReporter

        mock_tracker.workflow.error = "测试错误信息"

        reporter = ConsoleReporter(mock_tracker)
        reporter.print_summary()

        captured = capsys.readouterr()
        assert "错误" in captured.out
        assert "测试错误信息" in captured.out

    def test_print_stage_summary(self, mock_tracker, capsys) -> None:
        """测试打印单个阶段汇总."""
        from src.core.performance_reporter import ConsoleReporter

        reporter = ConsoleReporter(mock_tracker)
        reporter.print_stage_summary("stage1")

        captured = capsys.readouterr()
        assert "阶段1" in captured.out

    def test_print_stage_summary_not_found(self, mock_tracker) -> None:
        """测试打印不存在的阶段."""
        from src.core.performance_reporter import ConsoleReporter

        reporter = ConsoleReporter(mock_tracker)
        # 不应抛出异常
        reporter.print_stage_summary("nonexistent_stage")

    def test_print_stage_summary_no_workflow(self) -> None:
        """测试没有工作流时打印阶段汇总."""
        from src.core.performance_reporter import ConsoleReporter

        tracker = MagicMock()
        tracker.workflow = None

        reporter = ConsoleReporter(tracker)
        # 不应抛出异常
        reporter.print_stage_summary("stage1")

    def test_get_detailed_report(self, mock_tracker) -> None:
        """测试获取详细报告."""
        from src.core.performance_reporter import ConsoleReporter

        reporter = ConsoleReporter(mock_tracker)
        report = reporter.get_detailed_report()

        assert "workflow" in report
        assert report["workflow"]["id"] == "test_workflow_123"
        assert report["workflow"]["status"] == "success"
        assert "summary" in report
        assert "stages" in report
        assert len(report["stages"]) == 3

    def test_get_detailed_report_no_workflow(self) -> None:
        """测试没有工作流时获取空报告."""
        from src.core.performance_reporter import ConsoleReporter

        tracker = MagicMock()
        tracker.workflow = None

        reporter = ConsoleReporter(tracker)
        report = reporter.get_detailed_report()

        assert report == {}

    def test_print_operation_breakdown(self, mock_tracker, capsys) -> None:
        """测试打印操作耗时细分."""
        from src.core.performance_reporter import ConsoleReporter

        # 添加一些操作
        op1 = MagicMock()
        op1.name = "操作1"
        op1.duration_s = 10.0

        op2 = MagicMock()
        op2.name = "操作2"
        op2.duration_s = 20.0

        mock_tracker.workflow.stages[0].operations = [op1, op2]

        reporter = ConsoleReporter(mock_tracker)
        reporter.print_operation_breakdown()

        captured = capsys.readouterr()
        assert "操作耗时排行" in captured.out

    def test_print_operation_breakdown_no_workflow(self) -> None:
        """测试没有工作流时打印操作细分."""
        from src.core.performance_reporter import ConsoleReporter

        tracker = MagicMock()
        tracker.workflow = None

        reporter = ConsoleReporter(tracker)
        # 不应抛出异常
        reporter.print_operation_breakdown()


class TestConsoleReporterWithOperations:
    """测试带有操作详情的报告."""

    @pytest.fixture
    def tracker_with_operations(self):
        """创建带有操作详情的追踪器."""
        tracker = MagicMock()

        workflow = MagicMock()
        workflow.id = "test_123"
        workflow.name = "测试"
        workflow.duration_s = 100.0
        workflow.status = MagicMock()
        workflow.status.value = "success"
        workflow.stage_count = 1
        workflow.error = None
        workflow.start_time = datetime.now()
        workflow.end_time = datetime.now()

        # 创建操作
        action1 = MagicMock()
        action1.name = "动作1"
        action1.status = MagicMock()
        action1.status.value = "success"
        action1.duration_s = 5.0
        action1.metadata = {}

        action2 = MagicMock()
        action2.name = "动作2"
        action2.status = MagicMock()
        action2.status.value = "failed"
        action2.duration_s = 3.0
        action2.metadata = {}

        operation = MagicMock()
        operation.name = "操作1"
        operation.status = MagicMock()
        operation.status.value = "success"
        operation.duration_s = 10.0
        operation.metadata = {"key": "value"}
        operation.actions = [action1, action2]

        stage = MagicMock()
        stage.name = "stage1"
        stage.display_name = "阶段1"
        stage.order = 1
        stage.status = MagicMock()
        stage.status.value = "success"
        stage.duration_s = 50.0
        stage.operation_count = 1
        stage.operations = [operation]

        workflow.stages = [stage]
        tracker.workflow = workflow
        tracker.get_summary.return_value = {
            "stages": [
                {
                    "name": "stage1",
                    "display_name": "阶段1",
                    "duration_s": 50.0,
                    "status": "success",
                    "operation_count": 1,
                }
            ],
            "percentages": {"stage1": 100.0},
        }

        return tracker

    def test_print_stage_summary_with_operations(self, tracker_with_operations, capsys) -> None:
        """测试打印带有操作详情的阶段汇总."""
        from src.core.performance_reporter import ConsoleReporter

        reporter = ConsoleReporter(tracker_with_operations)
        reporter.print_stage_summary("stage1")

        captured = capsys.readouterr()
        assert "阶段1" in captured.out
        assert "操作详情" in captured.out
        assert "操作1" in captured.out
        assert "动作1" in captured.out
        assert "动作2" in captured.out

    def test_get_detailed_report_with_operations(self, tracker_with_operations) -> None:
        """测试获取带有操作详情的报告."""
        from src.core.performance_reporter import ConsoleReporter

        reporter = ConsoleReporter(tracker_with_operations)
        report = reporter.get_detailed_report()

        assert len(report["stages"]) == 1
        stage = report["stages"][0]
        assert len(stage["operations"]) == 1
        op = stage["operations"][0]
        assert op["name"] == "操作1"
        assert len(op["actions"]) == 2


class TestModuleExports:
    """测试模块导出."""

    def test_format_duration_callable(self) -> None:
        """测试 format_duration 可调用."""
        from src.core.performance_reporter import format_duration

        assert callable(format_duration)

    def test_create_progress_bar_callable(self) -> None:
        """测试 create_progress_bar 可调用."""
        from src.core.performance_reporter import create_progress_bar

        assert callable(create_progress_bar)

    def test_console_reporter_class(self) -> None:
        """测试 ConsoleReporter 类存在."""
        from src.core.performance_reporter import ConsoleReporter

        assert ConsoleReporter is not None

    def test_separator_constants(self) -> None:
        """测试分隔符常量."""
        from src.core.performance_reporter import ConsoleReporter

        assert len(ConsoleReporter.SEPARATOR) == 60
        assert len(ConsoleReporter.THIN_SEPARATOR) == 60
