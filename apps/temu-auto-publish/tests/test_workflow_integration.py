"""
@PURPOSE: 工作流集成测试 - 验证超时保护和紧急清理机制
@OUTLINE:
  - TestWorkflowTimeoutIntegration: 测试工作流超时保护
  - TestEmergencyCleanup: 测试紧急清理机制
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.core.workflow_timeout import TimeoutConfig
from src.workflows.complete_publish_workflow import (
    CompletePublishWorkflow,
    WorkflowExecutionResult,
)


class TestWorkflowTimeoutIntegration:
    """测试工作流超时保护集成."""

    def test_timeout_config_initialization_default(self):
        """测试默认超时配置初始化(24小时稳定运行模式)."""
        with patch.object(
            CompletePublishWorkflow, "_resolve_image_base_dir", return_value=MagicMock()
        ):
            workflow = CompletePublishWorkflow.__new__(CompletePublishWorkflow)
            workflow.settings = MagicMock()
            workflow.settings.browser.headless = True
            workflow.settings.business.collect_count = 5
            workflow.settings.business.claim_count = 5
            workflow._selection_rows_override = None
            workflow.timeout_config = TimeoutConfig()

            # 24 小时稳定运行配置
            assert workflow.timeout_config.workflow_total == 7200  # 120分钟
            assert workflow.timeout_config.stage1_first_edit == 1800  # 30分钟
            assert workflow.timeout_config.stage2_claim == 900  # 15分钟

    def test_timeout_config_initialization_custom_dict(self):
        """测试自定义字典超时配置初始化."""
        custom_config = {"workflow_total": 1800, "stage1_first_edit": 300}

        workflow = CompletePublishWorkflow.__new__(CompletePublishWorkflow)
        workflow.timeout_config = TimeoutConfig(
            workflow_total=custom_config.get("workflow_total", 7200),
            stage1_first_edit=custom_config.get("stage1_first_edit", 1800),
        )

        assert workflow.timeout_config.workflow_total == 1800
        assert workflow.timeout_config.stage1_first_edit == 300
        # 未覆盖的值使用新的 24 小时模式默认值
        assert workflow.timeout_config.stage2_claim == 900  # 15分钟

    def test_timeout_config_initialization_custom_object(self):
        """测试自定义 TimeoutConfig 对象初始化."""
        custom_config = TimeoutConfig(workflow_total=2400, stage3_batch_edit=600)

        workflow = CompletePublishWorkflow.__new__(CompletePublishWorkflow)
        workflow.timeout_config = custom_config

        assert workflow.timeout_config.workflow_total == 2400
        assert workflow.timeout_config.stage3_batch_edit == 600


class TestEmergencyCleanup:
    """测试紧急清理机制."""

    @pytest.mark.asyncio
    async def test_emergency_cleanup_closes_browser(self):
        """测试紧急清理关闭浏览器."""
        workflow = CompletePublishWorkflow.__new__(CompletePublishWorkflow)
        workflow._perf_tracker = MagicMock()
        workflow._perf_tracker.end_workflow = MagicMock()
        workflow._perf_reporter = MagicMock()
        workflow._perf_reporter.print_summary = MagicMock()

        # 初始化稳定性组件属性(新增)
        workflow._watchdog = None
        workflow._health_monitor = None
        workflow._resource_manager = None
        workflow._checkpoint_cleanup_task = None
        workflow._session_keeper = None

        # Mock browser manager
        mock_browser_manager = AsyncMock()
        mock_browser_manager.close = AsyncMock()

        workflow.login_ctrl = MagicMock()
        workflow.login_ctrl.browser_manager = mock_browser_manager

        await workflow._emergency_cleanup("timeout")

        # 验证浏览器关闭被调用
        mock_browser_manager.close.assert_called_once_with(save_state=False)
        # 验证性能追踪被结束
        workflow._perf_tracker.end_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_emergency_cleanup_handles_browser_close_failure(self):
        """测试紧急清理处理浏览器关闭失败."""
        workflow = CompletePublishWorkflow.__new__(CompletePublishWorkflow)
        workflow._perf_tracker = MagicMock()
        workflow._perf_tracker.end_workflow = MagicMock()
        workflow._perf_reporter = MagicMock()

        # 初始化稳定性组件属性(新增)
        workflow._watchdog = None
        workflow._health_monitor = None
        workflow._resource_manager = None
        workflow._checkpoint_cleanup_task = None
        workflow._session_keeper = None

        # Mock browser manager with failing close
        mock_browser_manager = AsyncMock()
        mock_browser_manager.close = AsyncMock(side_effect=Exception("模拟关闭失败"))

        workflow.login_ctrl = MagicMock()
        workflow.login_ctrl.browser_manager = mock_browser_manager

        # 不应抛出异常
        await workflow._emergency_cleanup("error")

        # 验证浏览器关闭被尝试调用
        mock_browser_manager.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_emergency_cleanup_without_login_ctrl(self):
        """测试无 login_ctrl 时的紧急清理."""
        workflow = CompletePublishWorkflow.__new__(CompletePublishWorkflow)
        workflow._perf_tracker = MagicMock()
        workflow._perf_tracker.end_workflow = MagicMock()
        workflow._perf_reporter = MagicMock()
        workflow.login_ctrl = None

        # 初始化稳定性组件属性(新增)
        workflow._watchdog = None
        workflow._health_monitor = None
        workflow._resource_manager = None
        workflow._checkpoint_cleanup_task = None
        workflow._session_keeper = None

        # 不应抛出异常
        await workflow._emergency_cleanup("cancelled")


class TestExecuteAsyncTimeout:
    """测试 execute_async 超时行为."""

    @pytest.mark.asyncio
    async def test_execute_async_returns_failure_on_timeout(self):
        """测试超时时 execute_async 返回失败结果."""
        workflow = CompletePublishWorkflow.__new__(CompletePublishWorkflow)
        workflow.timeout_config = TimeoutConfig(workflow_total=0.1)  # 极短超时
        workflow._perf_tracker = MagicMock()
        workflow._perf_tracker.end_workflow = MagicMock()
        workflow._perf_reporter = MagicMock()
        workflow.login_ctrl = None

        # 初始化稳定性组件属性(新增)
        workflow._watchdog = None
        workflow._health_monitor = None
        workflow._resource_manager = None
        workflow._checkpoint_cleanup_task = None
        workflow._session_keeper = None

        # Mock _run to be slow
        async def slow_run():
            await asyncio.sleep(10)  # 超过 0.1s 超时
            return WorkflowExecutionResult("test", True, [], [])

        workflow._run = slow_run

        result = await workflow.execute_async()

        assert result.total_success is False
        assert "超时" in result.errors[0]

    @pytest.mark.asyncio
    async def test_execute_async_succeeds_within_timeout(self):
        """测试正常执行时 execute_async 返回成功结果."""
        workflow = CompletePublishWorkflow.__new__(CompletePublishWorkflow)
        workflow.timeout_config = TimeoutConfig(workflow_total=5.0)
        workflow._perf_tracker = MagicMock()
        workflow._perf_reporter = MagicMock()
        workflow.login_ctrl = None

        expected_result = WorkflowExecutionResult("test_id", True, [], [])

        async def fast_run():
            await asyncio.sleep(0.01)
            return expected_result

        workflow._run = fast_run

        result = await workflow.execute_async()

        assert result.total_success is True
        assert result.workflow_id == "test_id"
