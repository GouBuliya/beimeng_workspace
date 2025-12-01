"""
@PURPOSE: 测试 PerformanceTracker 性能追踪器
@OUTLINE:
  - TestExecutionStatus: 测试执行状态枚举
  - TestActionMetrics: 测试 Action 级别指标
  - TestOperationMetrics: 测试 Operation 级别指标
  - TestStageMetrics: 测试 Stage 级别指标
  - TestWorkflowMetrics: 测试 Workflow 级别指标
  - TestPerformanceTracker: 测试性能追踪器主类
  - TestContextManagers: 测试上下文管理器
  - TestDecorators: 测试装饰器功能
  - TestGlobalTracker: 测试全局追踪器
  - TestConsoleReporter: 测试控制台报告器
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.core.performance_tracker, src.core.performance_reporter
"""

import asyncio
import json
import time
from datetime import datetime

import pytest
from src.core.performance_reporter import (
    ConsoleReporter,
    create_progress_bar,
    format_duration,
)
from src.core.performance_tracker import (
    ActionMetrics,
    ExecutionStatus,
    OperationMetrics,
    PerformanceTracker,
    StageMetrics,
    WorkflowMetrics,
    get_tracker,
    reset_tracker,
    track_action,
    track_operation,
)


class TestExecutionStatus:
    """测试执行状态枚举"""

    def test_status_values(self):
        """测试所有状态值存在"""
        assert ExecutionStatus.PENDING == "pending"
        assert ExecutionStatus.RUNNING == "running"
        assert ExecutionStatus.SUCCESS == "success"
        assert ExecutionStatus.FAILED == "failed"
        assert ExecutionStatus.SKIPPED == "skipped"

    def test_status_is_string_enum(self):
        """测试状态是字符串枚举"""
        assert isinstance(ExecutionStatus.PENDING.value, str)
        assert ExecutionStatus.PENDING.value == "pending"


class TestActionMetrics:
    """测试 Action 级别指标"""

    def test_create_action(self):
        """测试创建 Action 指标"""
        action = ActionMetrics(name="click_button")

        assert action.name == "click_button"
        assert action.status == ExecutionStatus.PENDING
        assert action.start_time is None
        assert action.end_time is None
        assert action.error is None
        assert action.id.startswith("act_")

    def test_action_with_metadata(self):
        """测试带元数据的 Action"""
        action = ActionMetrics(name="fill_input", metadata={"field": "title", "value": "test"})

        assert action.metadata["field"] == "title"
        assert action.metadata["value"] == "test"

    def test_action_duration_calculation(self):
        """测试 Action 耗时计算"""
        action = ActionMetrics(name="wait_element")
        action.start_time = datetime(2024, 1, 1, 10, 0, 0)
        action.end_time = datetime(2024, 1, 1, 10, 0, 1, 500000)  # 1.5秒后

        assert action.duration_ms == 1500.0
        assert action.duration_s == 1.5

    def test_action_duration_none_when_incomplete(self):
        """测试未完成时耗时为 None"""
        action = ActionMetrics(name="pending_action")
        action.start_time = datetime.now()

        assert action.duration_ms is None
        assert action.duration_s is None


class TestOperationMetrics:
    """测试 Operation 级别指标"""

    def test_create_operation(self):
        """测试创建 Operation 指标"""
        op = OperationMetrics(name="edit_product")

        assert op.name == "edit_product"
        assert op.status == ExecutionStatus.PENDING
        assert op.actions == []
        assert op.id.startswith("op_")

    def test_operation_action_count(self):
        """测试 Operation 的 Action 计数"""
        op = OperationMetrics(name="batch_step")
        op.actions.append(ActionMetrics(name="action1"))
        op.actions.append(ActionMetrics(name="action2"))

        assert op.action_count == 2

    def test_operation_duration(self):
        """测试 Operation 耗时计算"""
        op = OperationMetrics(name="process_item")
        op.start_time = datetime(2024, 1, 1, 10, 0, 0)
        op.end_time = datetime(2024, 1, 1, 10, 0, 5)  # 5秒后

        assert op.duration_ms == 5000.0
        assert op.duration_s == 5.0


class TestStageMetrics:
    """测试 Stage 级别指标"""

    def test_create_stage(self):
        """测试创建 Stage 指标"""
        stage = StageMetrics(name="stage1_first_edit", display_name="首次编辑", order=1)

        assert stage.name == "stage1_first_edit"
        assert stage.display_name == "首次编辑"
        assert stage.order == 1
        assert stage.operations == []
        assert stage.id.startswith("stg_")

    def test_stage_operation_count(self):
        """测试 Stage 的 Operation 计数"""
        stage = StageMetrics(name="batch_edit", display_name="批量编辑", order=3)
        stage.operations.append(OperationMetrics(name="op1"))
        stage.operations.append(OperationMetrics(name="op2"))
        stage.operations.append(OperationMetrics(name="op3"))

        assert stage.operation_count == 3


class TestWorkflowMetrics:
    """测试 Workflow 级别指标"""

    def test_create_workflow(self):
        """测试创建 Workflow 指标"""
        workflow = WorkflowMetrics(name="temu_publish")

        assert workflow.name == "temu_publish"
        assert workflow.status == ExecutionStatus.PENDING
        assert workflow.stages == []
        assert workflow.id.startswith("wf_")

    def test_workflow_stage_count(self):
        """测试 Workflow 的 Stage 计数"""
        workflow = WorkflowMetrics()
        workflow.stages.append(StageMetrics(name="stage1", display_name="阶段1", order=1))
        workflow.stages.append(StageMetrics(name="stage2", display_name="阶段2", order=2))

        assert workflow.stage_count == 2

    def test_workflow_calculate_percentages(self):
        """测试 Workflow 百分比计算"""
        workflow = WorkflowMetrics()
        workflow.start_time = datetime(2024, 1, 1, 10, 0, 0)
        workflow.end_time = datetime(2024, 1, 1, 10, 0, 10)  # 10秒

        stage1 = StageMetrics(name="stage1", display_name="阶段1", order=1)
        stage1.start_time = datetime(2024, 1, 1, 10, 0, 0)
        stage1.end_time = datetime(2024, 1, 1, 10, 0, 3)  # 3秒

        stage2 = StageMetrics(name="stage2", display_name="阶段2", order=2)
        stage2.start_time = datetime(2024, 1, 1, 10, 0, 3)
        stage2.end_time = datetime(2024, 1, 1, 10, 0, 10)  # 7秒

        workflow.stages = [stage1, stage2]

        percentages = workflow.calculate_percentages()

        assert percentages["stage1"] == 30.0
        assert percentages["stage2"] == 70.0

    def test_workflow_get_summary(self):
        """测试 Workflow 汇总数据"""
        workflow = WorkflowMetrics(name="test_workflow")
        workflow.status = ExecutionStatus.SUCCESS
        workflow.start_time = datetime(2024, 1, 1, 10, 0, 0)
        workflow.end_time = datetime(2024, 1, 1, 10, 1, 0)  # 60秒

        stage = StageMetrics(name="stage1", display_name="测试阶段", order=1)
        stage.status = ExecutionStatus.SUCCESS
        stage.start_time = datetime(2024, 1, 1, 10, 0, 0)
        stage.end_time = datetime(2024, 1, 1, 10, 1, 0)
        workflow.stages.append(stage)

        summary = workflow.get_summary()

        assert summary["workflow_id"] == workflow.id
        assert summary["total_duration_s"] == 60.0
        assert summary["status"] == "success"
        assert summary["stage_count"] == 1
        assert len(summary["stages"]) == 1


class TestPerformanceTracker:
    """测试性能追踪器主类"""

    def test_init(self):
        """测试初始化"""
        tracker = PerformanceTracker(workflow_name="test_workflow")

        assert tracker.workflow_name == "test_workflow"
        assert tracker.workflow is None

    def test_start_workflow(self):
        """测试开始工作流"""
        tracker = PerformanceTracker()
        workflow_id = tracker.start_workflow()

        assert tracker.workflow is not None
        assert tracker.workflow.status == ExecutionStatus.RUNNING
        assert tracker.workflow.start_time is not None
        assert workflow_id == tracker.workflow.id

    def test_start_workflow_with_custom_id(self):
        """测试使用自定义 ID 开始工作流"""
        tracker = PerformanceTracker()
        workflow_id = tracker.start_workflow("custom_wf_001")

        assert workflow_id == "custom_wf_001"
        assert tracker.workflow.id == "custom_wf_001"

    def test_end_workflow_success(self):
        """测试成功结束工作流"""
        tracker = PerformanceTracker()
        tracker.start_workflow()
        time.sleep(0.01)
        tracker.end_workflow(success=True)

        assert tracker.workflow.status == ExecutionStatus.SUCCESS
        assert tracker.workflow.end_time is not None
        assert tracker.workflow.error is None

    def test_end_workflow_failed(self):
        """测试失败结束工作流"""
        tracker = PerformanceTracker()
        tracker.start_workflow()
        tracker.end_workflow(success=False, error="Something went wrong")

        assert tracker.workflow.status == ExecutionStatus.FAILED
        assert tracker.workflow.error == "Something went wrong"

    def test_end_workflow_without_start(self):
        """测试未开始时结束工作流"""
        tracker = PerformanceTracker()
        # 不应抛出异常
        tracker.end_workflow()
        assert tracker.workflow is None

    def test_to_dict(self):
        """测试转换为字典"""
        tracker = PerformanceTracker()
        tracker.start_workflow("test_id")
        tracker.end_workflow()

        data = tracker.to_dict()

        assert data["id"] == "test_id"
        assert data["name"] == "temu_publish"
        assert "status" in data

    def test_to_json(self):
        """测试转换为 JSON"""
        tracker = PerformanceTracker()
        tracker.start_workflow()
        tracker.end_workflow()

        json_str = tracker.to_json()
        data = json.loads(json_str)

        assert "id" in data
        assert "status" in data

    def test_reset(self):
        """测试重置追踪器"""
        tracker = PerformanceTracker()
        tracker.start_workflow()
        tracker.reset()

        assert tracker.workflow is None
        assert tracker._current_stage is None

    def test_save_to_file(self, tmp_path):
        """测试保存到文件"""
        tracker = PerformanceTracker()
        tracker.start_workflow("test_save")
        tracker.end_workflow()

        filepath = tmp_path / "test_metrics.json"
        saved_path = tracker.save_to_file(filepath)

        assert saved_path == filepath
        assert filepath.exists()

        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["id"] == "test_save"


class TestContextManagers:
    """测试上下文管理器"""

    @pytest.mark.asyncio
    async def test_stage_context_manager(self):
        """测试 Stage 异步上下文管理器"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        async with tracker.stage("test_stage", "测试阶段", order=1):
            await asyncio.sleep(0.01)

        assert len(tracker.workflow.stages) == 1
        stage = tracker.workflow.stages[0]
        assert stage.name == "test_stage"
        assert stage.display_name == "测试阶段"
        assert stage.order == 1
        assert stage.status == ExecutionStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_stage_context_manager_with_exception(self):
        """测试 Stage 上下文管理器异常处理"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        with pytest.raises(ValueError):
            async with tracker.stage("error_stage", "错误阶段", order=1):
                raise ValueError("Test error")

        stage = tracker.workflow.stages[0]
        assert stage.status == ExecutionStatus.FAILED
        assert stage.error == "Test error"

    @pytest.mark.asyncio
    async def test_operation_context_manager(self):
        """测试 Operation 异步上下文管理器"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        async with tracker.stage("stage1", "阶段1", order=1):
            async with tracker.operation("op1", extra_key="extra_value"):
                await asyncio.sleep(0.01)

        stage = tracker.workflow.stages[0]
        assert len(stage.operations) == 1
        op = stage.operations[0]
        assert op.name == "op1"
        assert op.status == ExecutionStatus.SUCCESS
        assert op.metadata["extra_key"] == "extra_value"

    @pytest.mark.asyncio
    async def test_action_context_manager(self):
        """测试 Action 异步上下文管理器"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        async with tracker.stage("stage1", "阶段1", order=1), tracker.operation("op1"):
            async with tracker.action("action1", detail="test"):
                await asyncio.sleep(0.01)

        op = tracker.workflow.stages[0].operations[0]
        assert len(op.actions) == 1
        action = op.actions[0]
        assert action.name == "action1"
        assert action.status == ExecutionStatus.SUCCESS
        assert action.metadata["detail"] == "test"

    def test_stage_sync_context_manager(self):
        """测试 Stage 同步上下文管理器"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        with tracker.stage_sync("sync_stage", "同步阶段", order=1):
            time.sleep(0.01)

        assert len(tracker.workflow.stages) == 1
        assert tracker.workflow.stages[0].status == ExecutionStatus.SUCCESS

    def test_operation_without_stage(self):
        """测试在 Stage 外使用 Operation(应该跳过)"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        # 不在 stage 内使用 operation,应该跳过
        with tracker.operation_sync("orphan_op"):
            pass

        assert len(tracker.workflow.stages) == 0


class TestDecorators:
    """测试装饰器功能"""

    @pytest.mark.asyncio
    async def test_track_operation_decorator_async(self):
        """测试异步 Operation 装饰器"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        @tracker.track_operation("decorated_op")
        async def decorated_func():
            await asyncio.sleep(0.01)
            return "result"

        async with tracker.stage("stage1", "阶段1", order=1):
            result = await decorated_func()

        assert result == "result"
        assert len(tracker.workflow.stages[0].operations) == 1
        assert tracker.workflow.stages[0].operations[0].name == "decorated_op"

    def test_track_operation_decorator_sync(self):
        """测试同步 Operation 装饰器"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        @tracker.track_operation("sync_decorated_op")
        def sync_func():
            return "sync_result"

        with tracker.stage_sync("stage1", "阶段1", order=1):
            result = sync_func()

        assert result == "sync_result"
        assert len(tracker.workflow.stages[0].operations) == 1

    @pytest.mark.asyncio
    async def test_track_action_decorator(self):
        """测试 Action 装饰器"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        @tracker.track_action("decorated_action")
        async def action_func():
            await asyncio.sleep(0.01)
            return "action_done"

        async with tracker.stage("stage1", "阶段1", order=1), tracker.operation("op1"):
            result = await action_func()

        assert result == "action_done"
        op = tracker.workflow.stages[0].operations[0]
        assert len(op.actions) == 1
        assert op.actions[0].name == "decorated_action"


class TestGlobalTracker:
    """测试全局追踪器"""

    def test_get_tracker_singleton(self):
        """测试获取全局追踪器(单例)"""
        reset_tracker()  # 确保干净状态
        tracker1 = get_tracker()
        tracker2 = get_tracker()

        assert tracker1 is tracker2

    def test_reset_tracker(self):
        """测试重置全局追踪器"""
        tracker1 = get_tracker()
        tracker1.start_workflow()

        tracker2 = reset_tracker()

        assert tracker2 is not tracker1
        assert tracker2.workflow is None

    def test_global_track_operation_decorator(self):
        """测试全局 Operation 装饰器"""
        reset_tracker()
        tracker = get_tracker()
        tracker.start_workflow()

        @track_operation("global_op")
        def global_func():
            return "global"

        with tracker.stage_sync("stage1", "阶段1", order=1):
            result = global_func()

        assert result == "global"

    def test_global_track_action_decorator(self):
        """测试全局 Action 装饰器"""
        reset_tracker()
        tracker = get_tracker()
        tracker.start_workflow()

        @track_action("global_action")
        def global_action_func():
            return "action"

        with tracker.stage_sync("stage1", "阶段1", order=1), tracker.operation_sync("op1"):
            result = global_action_func()

        assert result == "action"


class TestFormatDuration:
    """测试时间格式化函数"""

    def test_format_none(self):
        """测试 None 值"""
        assert format_duration(None) == "N/A"

    def test_format_seconds(self):
        """测试秒级格式化"""
        assert format_duration(0.5) == "0.50s"
        assert format_duration(1.234) == "1.23s"
        assert format_duration(59.99) == "59.99s"

    def test_format_minutes(self):
        """测试分钟级格式化"""
        assert format_duration(60) == "1m 0.0s"
        assert format_duration(90) == "1m 30.0s"
        assert format_duration(3599) == "59m 59.0s"

    def test_format_hours(self):
        """测试小时级格式化"""
        assert format_duration(3600) == "1h 0m"
        assert format_duration(7200) == "2h 0m"
        assert format_duration(5400) == "1h 30m"


class TestProgressBar:
    """测试进度条函数"""

    def test_create_progress_bar_empty(self):
        """测试空进度条"""
        bar = create_progress_bar(0)
        assert bar == "░" * 20

    def test_create_progress_bar_full(self):
        """测试满进度条"""
        bar = create_progress_bar(100)
        assert bar == "█" * 20

    def test_create_progress_bar_half(self):
        """测试半满进度条"""
        bar = create_progress_bar(50)
        assert bar == "█" * 10 + "░" * 10

    def test_create_progress_bar_custom_width(self):
        """测试自定义宽度"""
        bar = create_progress_bar(50, width=10)
        assert bar == "█" * 5 + "░" * 5

    def test_create_progress_bar_clamped(self):
        """测试边界值处理"""
        bar_negative = create_progress_bar(-10)
        assert bar_negative == "░" * 20

        bar_over = create_progress_bar(150)
        assert bar_over == "█" * 20


class TestConsoleReporter:
    """测试控制台报告器"""

    def test_init(self):
        """测试初始化"""
        tracker = PerformanceTracker()
        reporter = ConsoleReporter(tracker)

        assert reporter.tracker is tracker

    def test_print_summary_without_workflow(self, capsys):
        """测试无工作流时打印汇总"""
        tracker = PerformanceTracker()
        reporter = ConsoleReporter(tracker)

        reporter.print_summary()

        # 应该输出警告但不报错
        capsys.readouterr()
        # 由于使用 loguru,可能不会捕获到输出

    def test_get_detailed_report(self):
        """测试获取详细报告"""
        tracker = PerformanceTracker()
        tracker.start_workflow("report_test")
        tracker.end_workflow()

        reporter = ConsoleReporter(tracker)
        report = reporter.get_detailed_report()

        assert "workflow" in report
        assert report["workflow"]["id"] == "report_test"
        assert "summary" in report
        assert "stages" in report

    def test_get_detailed_report_with_stages(self):
        """测试带阶段的详细报告"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        with tracker.stage_sync("stage1", "第一阶段", order=1):
            with tracker.operation_sync("op1", key="value"):
                with tracker.action_sync("action1"):
                    time.sleep(0.01)

        tracker.end_workflow()

        reporter = ConsoleReporter(tracker)
        report = reporter.get_detailed_report()

        assert len(report["stages"]) == 1
        stage_report = report["stages"][0]
        assert stage_report["name"] == "stage1"
        assert stage_report["display_name"] == "第一阶段"
        assert len(stage_report["operations"]) == 1

    def test_print_header(self, capsys):
        """测试打印头部"""
        tracker = PerformanceTracker()
        reporter = ConsoleReporter(tracker)

        reporter.print_header("测试标题")

        captured = capsys.readouterr()
        assert "测试标题" in captured.out
        assert "═" in captured.out


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow_tracking(self):
        """测试完整的工作流追踪流程"""
        tracker = PerformanceTracker(workflow_name="integration_test")
        tracker.start_workflow("integration_wf_001")

        # Stage 1
        async with tracker.stage("stage1", "首次编辑", order=1):
            async with tracker.operation("edit_product_1", product_id=1):
                async with tracker.action("click_edit"):
                    await asyncio.sleep(0.01)
                async with tracker.action("fill_form"):
                    await asyncio.sleep(0.01)

        # Stage 2
        async with tracker.stage("stage2", "认领", order=2):
            async with tracker.operation("claim_product"):
                await asyncio.sleep(0.02)

        tracker.end_workflow(success=True)

        # 验证结构
        assert tracker.workflow.status == ExecutionStatus.SUCCESS
        assert len(tracker.workflow.stages) == 2

        # 验证阶段
        stage1 = tracker.workflow.stages[0]
        assert stage1.name == "stage1"
        assert len(stage1.operations) == 1
        assert len(stage1.operations[0].actions) == 2

        stage2 = tracker.workflow.stages[1]
        assert stage2.name == "stage2"

        # 验证百分比计算
        percentages = tracker.workflow.calculate_percentages()
        assert "stage1" in percentages
        assert "stage2" in percentages
        total_percentage = sum(percentages.values())
        assert abs(total_percentage - 100) < 1  # 允许舍入误差

        # 验证汇总
        summary = tracker.get_summary()
        assert summary["status"] == "success"
        assert summary["stage_count"] == 2

    @pytest.mark.asyncio
    async def test_error_handling_in_stages(self):
        """测试阶段中的错误处理"""
        tracker = PerformanceTracker()
        tracker.start_workflow()

        try:
            async with tracker.stage("error_stage", "错误阶段", order=1):
                async with tracker.operation("failing_op"):
                    raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass

        tracker.end_workflow(success=False, error="Stage failed")

        assert tracker.workflow.status == ExecutionStatus.FAILED
        stage = tracker.workflow.stages[0]
        assert stage.status == ExecutionStatus.FAILED
        assert stage.error == "Simulated failure"
