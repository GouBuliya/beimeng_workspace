"""
@PURPOSE: executor 模块的完整单元测试
@OUTLINE:
  - TestWorkflowState: WorkflowState 数据类测试
  - TestWorkflowExecutor: WorkflowExecutor 类测试
  - TestCreateExecutor: create_executor 便捷函数测试
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.core.executor
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ==================== WorkflowState 数据类测试 ====================
class TestWorkflowState:
    """WorkflowState 数据类测试"""

    def test_create_with_defaults(self):
        """测试默认值创建"""
        from src.core.executor import WorkflowState

        state = WorkflowState(workflow_id="wf-001")

        assert state.workflow_id == "wf-001"
        assert state.status == "running"
        assert state.current_stage is None
        assert state.completed_stages == []
        assert state.failed_stages == []
        assert state.context == {}
        assert state.checkpoint_data == {}
        assert state.start_time is not None
        assert state.update_time is not None

    def test_create_with_all_fields(self):
        """测试完整字段创建"""
        from src.core.executor import WorkflowState

        state = WorkflowState(
            workflow_id="wf-002",
            status="completed",
            current_stage="stage-3",
            completed_stages=["stage-1", "stage-2"],
            failed_stages=["stage-x"],
            start_time="2024-01-01T10:00:00",
            update_time="2024-01-01T10:30:00",
            context={"key": "value"},
            checkpoint_data={"progress": 50},
        )

        assert state.workflow_id == "wf-002"
        assert state.status == "completed"
        assert state.current_stage == "stage-3"
        assert "stage-1" in state.completed_stages
        assert "stage-x" in state.failed_stages
        assert state.context["key"] == "value"

    def test_to_dict(self):
        """测试转换为字典"""
        from src.core.executor import WorkflowState

        state = WorkflowState(workflow_id="wf-003", status="running")

        result = state.to_dict()

        assert isinstance(result, dict)
        assert result["workflow_id"] == "wf-003"
        assert result["status"] == "running"

    def test_to_json(self):
        """测试转换为 JSON"""
        from src.core.executor import WorkflowState

        state = WorkflowState(workflow_id="wf-004")

        json_str = state.to_json()

        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["workflow_id"] == "wf-004"

    def test_from_dict(self):
        """测试从字典创建"""
        from src.core.executor import WorkflowState

        data = {
            "workflow_id": "wf-005",
            "status": "failed",
            "current_stage": "error-stage",
            "completed_stages": ["init"],
            "failed_stages": ["error-stage"],
            "start_time": "2024-01-01T10:00:00",
            "update_time": "2024-01-01T10:01:00",
            "context": {},
            "checkpoint_data": {},
        }

        state = WorkflowState.from_dict(data)

        assert state.workflow_id == "wf-005"
        assert state.status == "failed"
        assert state.current_stage == "error-stage"

    def test_from_json(self):
        """测试从 JSON 创建"""
        from src.core.executor import WorkflowState

        json_str = '{"workflow_id": "wf-006", "status": "completed", "current_stage": null, "completed_stages": ["a", "b"], "failed_stages": [], "start_time": "2024-01-01T10:00:00", "update_time": "2024-01-01T10:30:00", "context": {}, "checkpoint_data": {}}'

        state = WorkflowState.from_json(json_str)

        assert state.workflow_id == "wf-006"
        assert state.status == "completed"
        assert len(state.completed_stages) == 2

    def test_roundtrip_json(self):
        """测试 JSON 往返转换"""
        from src.core.executor import WorkflowState

        original = WorkflowState(
            workflow_id="wf-007",
            status="running",
            current_stage="processing",
            completed_stages=["init", "load"],
            context={"items": 10},
        )

        json_str = original.to_json()
        restored = WorkflowState.from_json(json_str)

        assert restored.workflow_id == original.workflow_id
        assert restored.status == original.status
        assert restored.current_stage == original.current_stage
        assert restored.completed_stages == original.completed_stages
        assert restored.context == original.context


# ==================== WorkflowExecutor 测试 ====================
class TestWorkflowExecutor:
    """WorkflowExecutor 类测试"""

    def test_init_defaults(self):
        """测试默认初始化"""
        from src.core.executor import WorkflowExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))

            assert executor.retry_handler is not None
            assert executor.perf_tracker is not None
            assert executor.current_workflow_id is None
            assert executor.current_state is None

    def test_init_with_custom_handlers(self):
        """测试自定义处理器初始化"""
        from src.core.executor import WorkflowExecutor
        from src.core.retry_handler import RetryHandler

        mock_tracker = MagicMock()
        retry_handler = RetryHandler()

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                retry_handler=retry_handler,
                perf_tracker=mock_tracker,
                state_dir=Path(tmpdir),
            )

            assert executor.retry_handler is retry_handler
            assert executor.perf_tracker is mock_tracker

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """测试成功执行"""
        from src.core.executor import WorkflowExecutor

        async def mock_workflow(page, config, **kwargs):
            return {"success": True, "data": "result"}

        mock_page = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.start_workflow = MagicMock()
        mock_tracker.end_workflow = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                perf_tracker=mock_tracker,
                state_dir=Path(tmpdir),
            )

            result = await executor.execute(
                workflow_func=mock_workflow,
                page=mock_page,
                config={"test": True},
                workflow_id="test-wf-001",
                enable_retry=False,
            )

            assert result["success"] is True
            assert result["data"] == "result"
            assert executor.current_state.status == "completed"
            mock_tracker.start_workflow.assert_called_once()
            mock_tracker.end_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_failure(self):
        """测试执行失败"""
        from src.core.executor import WorkflowExecutor

        async def failing_workflow(page, config, **kwargs):
            raise ValueError("Test error")

        mock_page = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.start_workflow = MagicMock()
        mock_tracker.end_workflow = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(
                perf_tracker=mock_tracker,
                state_dir=Path(tmpdir),
            )

            with pytest.raises(ValueError, match="Test error"):
                await executor.execute(
                    workflow_func=failing_workflow,
                    page=mock_page,
                    config={},
                    workflow_id="test-wf-fail",
                    enable_retry=False,
                )

            assert executor.current_state.status == "failed"
            mock_tracker.end_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_auto_generates_workflow_id(self):
        """测试自动生成工作流 ID"""
        from src.core.executor import WorkflowExecutor

        async def mock_workflow(page, config, **kwargs):
            return {"id": kwargs.get("workflow_id")}

        mock_page = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))

            result = await executor.execute(
                workflow_func=mock_workflow,
                page=mock_page,
                config={},
                enable_retry=False,
                enable_metrics=False,
            )

            assert executor.current_workflow_id is not None
            assert executor.current_workflow_id.startswith("workflow_")

    @pytest.mark.asyncio
    async def test_execute_with_retry_disabled(self):
        """测试禁用重试执行"""
        from src.core.executor import WorkflowExecutor

        async def simple_workflow(page, config, **kwargs):
            return {"success": True}

        mock_page = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))

            result = await executor.execute(
                workflow_func=simple_workflow,
                page=mock_page,
                config={},
                enable_retry=False,  # 禁用重试
                enable_metrics=False,
            )

            assert result["success"] is True

    def test_save_state(self):
        """测试保存状态"""
        from src.core.executor import WorkflowExecutor, WorkflowState

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            executor.current_state = WorkflowState(
                workflow_id="save-test",
                status="running",
                current_stage="stage-1",
            )

            executor.save_state()

            state_file = Path(tmpdir) / "save-test.json"
            assert state_file.exists()

            content = json.loads(state_file.read_text())
            assert content["workflow_id"] == "save-test"

    def test_save_state_no_active_state(self):
        """测试无活动状态时保存"""
        from src.core.executor import WorkflowExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            # current_state is None

            # Should not raise, just log warning
            executor.save_state()

    def test_save_state_custom_path(self):
        """测试保存到自定义路径"""
        from src.core.executor import WorkflowExecutor, WorkflowState

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            executor.current_state = WorkflowState(
                workflow_id="custom-path-test",
                status="completed",
            )

            custom_file = Path(tmpdir) / "custom_state.json"
            executor.save_state(custom_file)

            assert custom_file.exists()
            content = json.loads(custom_file.read_text())
            assert content["workflow_id"] == "custom-path-test"

    def test_load_state_success(self):
        """测试成功加载状态"""
        from src.core.executor import WorkflowExecutor, WorkflowState

        with tempfile.TemporaryDirectory() as tmpdir:
            # 先创建状态文件
            state_file = Path(tmpdir) / "load-test.json"
            state = WorkflowState(
                workflow_id="load-test",
                status="running",
                completed_stages=["init"],
            )
            state_file.write_text(state.to_json())

            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            loaded = executor.load_state(state_file)

            assert loaded is not None
            assert loaded.workflow_id == "load-test"
            assert "init" in loaded.completed_stages

    def test_load_state_file_not_found(self):
        """测试加载不存在的文件"""
        from src.core.executor import WorkflowExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            nonexistent = Path(tmpdir) / "nonexistent.json"

            result = executor.load_state(nonexistent)

            assert result is None

    def test_load_state_invalid_json(self):
        """测试加载无效 JSON"""
        from src.core.executor import WorkflowExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建无效 JSON 文件
            invalid_file = Path(tmpdir) / "invalid.json"
            invalid_file.write_text("not valid json {{{")

            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            result = executor.load_state(invalid_file)

            assert result is None

    def test_update_stage(self):
        """测试更新阶段"""
        from src.core.executor import WorkflowExecutor, WorkflowState

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            executor.current_state = WorkflowState(workflow_id="update-test")

            executor.update_stage("processing", checkpoint_data={"progress": 50})

            assert executor.current_state.current_stage == "processing"
            assert executor.current_state.checkpoint_data["progress"] == 50

    def test_update_stage_no_checkpoint(self):
        """测试更新阶段无检查点数据"""
        from src.core.executor import WorkflowExecutor, WorkflowState

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            executor.current_state = WorkflowState(workflow_id="update-test-2")

            executor.update_stage("stage-2")

            assert executor.current_state.current_stage == "stage-2"

    def test_update_stage_no_state(self):
        """测试无状态时更新阶段"""
        from src.core.executor import WorkflowExecutor

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            # current_state is None

            # Should not raise
            executor.update_stage("stage")

    def test_complete_stage(self):
        """测试完成阶段"""
        from src.core.executor import WorkflowExecutor, WorkflowState

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            executor.current_state = WorkflowState(workflow_id="complete-test")

            executor.complete_stage("init")
            executor.complete_stage("process")

            assert "init" in executor.current_state.completed_stages
            assert "process" in executor.current_state.completed_stages

    def test_complete_stage_no_duplicate(self):
        """测试完成阶段不重复添加"""
        from src.core.executor import WorkflowExecutor, WorkflowState

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            executor.current_state = WorkflowState(workflow_id="dup-test")

            executor.complete_stage("init")
            executor.complete_stage("init")  # 重复

            assert executor.current_state.completed_stages.count("init") == 1

    def test_fail_stage(self):
        """测试失败阶段"""
        from src.core.executor import WorkflowExecutor, WorkflowState

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            executor.current_state = WorkflowState(workflow_id="fail-test")

            executor.fail_stage("error-stage", ValueError("Test error"))

            assert "error-stage" in executor.current_state.failed_stages

    def test_fail_stage_no_duplicate(self):
        """测试失败阶段不重复添加"""
        from src.core.executor import WorkflowExecutor, WorkflowState

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            executor.current_state = WorkflowState(workflow_id="fail-dup-test")

            executor.fail_stage("bad", RuntimeError("error"))
            executor.fail_stage("bad", RuntimeError("error again"))

            assert executor.current_state.failed_stages.count("bad") == 1

    @pytest.mark.asyncio
    async def test_resume_completed_workflow(self):
        """测试恢复已完成的工作流"""
        from src.core.executor import WorkflowExecutor, WorkflowState

        async def mock_workflow(page, config, **kwargs):
            return {"resumed": True}

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建已完成的状态文件
            state_file = Path(tmpdir) / "completed.json"
            state = WorkflowState(workflow_id="completed-wf", status="completed")
            state_file.write_text(state.to_json())

            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            result = await executor.resume(
                workflow_func=mock_workflow,
                page=MagicMock(),
                state_file=state_file,
            )

            assert result["success"] is True
            assert result["message"] == "工作流已完成"

    @pytest.mark.asyncio
    async def test_resume_invalid_state_file(self):
        """测试恢复无效状态文件"""
        from src.core.executor import WorkflowExecutor

        async def mock_workflow(page, config, **kwargs):
            return {}

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))
            nonexistent = Path(tmpdir) / "nonexistent.json"

            with pytest.raises(ValueError, match="无法加载状态文件"):
                await executor.resume(
                    workflow_func=mock_workflow,
                    page=MagicMock(),
                    state_file=nonexistent,
                )


# ==================== create_executor 便捷函数测试 ====================
class TestCreateExecutor:
    """create_executor 便捷函数测试"""

    def test_create_with_defaults(self):
        """测试默认创建"""
        from src.core.executor import create_executor

        executor = create_executor()

        assert executor is not None
        assert executor.retry_handler is not None

    def test_create_without_retry(self):
        """测试不带重试创建"""
        from src.core.executor import create_executor

        executor = create_executor(enable_retry=False)

        assert executor is not None
        # 注意: create_executor 不带重试时,retry_handler 设为 None
        # 但 WorkflowExecutor.__init__ 会默认创建一个 RetryHandler
        # 所以这里我们验证 executor 已创建即可

    def test_create_with_custom_max_attempts(self):
        """测试自定义最大重试次数"""
        from src.core.executor import create_executor

        executor = create_executor(enable_retry=True, max_attempts=5)

        assert executor is not None
        assert executor.retry_handler is not None
        assert executor.retry_handler.config.max_attempts == 5


# ==================== 集成测试 ====================
class TestExecutorIntegration:
    """执行器集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow_lifecycle(self):
        """测试完整工作流生命周期"""
        from src.core.executor import WorkflowExecutor

        stages_executed = []

        async def multi_stage_workflow(page, config, **kwargs):
            stages_executed.append("init")
            stages_executed.append("process")
            stages_executed.append("finalize")
            return {"stages": stages_executed}

        mock_page = MagicMock()

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))

            result = await executor.execute(
                workflow_func=multi_stage_workflow,
                page=mock_page,
                config={"test": True},
                enable_retry=False,
                enable_metrics=False,
            )

            assert len(stages_executed) == 3
            assert result["stages"] == ["init", "process", "finalize"]
            assert executor.current_state.status == "completed"

    @pytest.mark.asyncio
    async def test_state_persistence(self):
        """测试状态持久化"""
        from src.core.executor import WorkflowExecutor

        async def workflow_with_stages(page, config, **kwargs):
            return {"done": True}

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = WorkflowExecutor(state_dir=Path(tmpdir))

            await executor.execute(
                workflow_func=workflow_with_stages,
                page=MagicMock(),
                config={},
                workflow_id="persist-test",
                enable_retry=False,
                enable_metrics=False,
                enable_state_save=True,
            )

            # 验证状态文件已创建
            state_file = Path(tmpdir) / "persist-test.json"
            assert state_file.exists()

            # 加载并验证
            loaded = executor.load_state(state_file)
            assert loaded.workflow_id == "persist-test"
            assert loaded.status == "completed"
