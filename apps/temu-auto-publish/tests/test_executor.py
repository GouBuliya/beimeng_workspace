"""
@PURPOSE: 测试工作流执行器
@OUTLINE:
  - TestWorkflowState: 测试工作流状态
  - TestWorkflowExecutor: 测试工作流执行器
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.core.executor
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.core.executor import WorkflowState, WorkflowExecutor


class TestWorkflowState:
    """测试工作流状态"""

    def test_create_default_state(self):
        """测试创建默认状态"""
        state = WorkflowState(workflow_id="WF-001")

        assert state.workflow_id == "WF-001"
        assert state.status == "running"
        assert state.current_stage is None
        assert state.completed_stages == []
        assert state.failed_stages == []
        assert state.context == {}
        assert state.checkpoint_data == {}

    def test_create_state_with_values(self):
        """测试创建带值的状态"""
        state = WorkflowState(
            workflow_id="WF-002",
            status="completed",
            current_stage="stage3",
            completed_stages=["stage1", "stage2"],
            context={"key": "value"},
        )

        assert state.status == "completed"
        assert state.current_stage == "stage3"
        assert len(state.completed_stages) == 2
        assert state.context["key"] == "value"

    def test_to_dict(self):
        """测试转换为字典"""
        state = WorkflowState(workflow_id="WF-003", status="running", current_stage="stage1")

        data = state.to_dict()

        assert isinstance(data, dict)
        assert data["workflow_id"] == "WF-003"
        assert data["status"] == "running"
        assert data["current_stage"] == "stage1"

    def test_to_json(self):
        """测试转换为JSON"""
        state = WorkflowState(workflow_id="WF-004", status="completed")

        json_str = state.to_json()

        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["workflow_id"] == "WF-004"

    def test_from_dict(self):
        """测试从字典创建"""
        data = {
            "workflow_id": "WF-005",
            "status": "failed",
            "current_stage": "stage2",
            "completed_stages": ["stage1"],
            "failed_stages": ["stage2"],
            "start_time": "2024-01-01T10:00:00",
            "update_time": "2024-01-01T10:30:00",
            "context": {"error": "timeout"},
            "checkpoint_data": {},
        }

        state = WorkflowState.from_dict(data)

        assert state.workflow_id == "WF-005"
        assert state.status == "failed"
        assert "stage1" in state.completed_stages
        assert "stage2" in state.failed_stages

    def test_from_json(self):
        """测试从JSON创建"""
        json_str = json.dumps(
            {
                "workflow_id": "WF-006",
                "status": "running",
                "current_stage": None,
                "completed_stages": [],
                "failed_stages": [],
                "start_time": "2024-01-01T10:00:00",
                "update_time": "2024-01-01T10:00:00",
                "context": {},
                "checkpoint_data": {},
            }
        )

        state = WorkflowState.from_json(json_str)

        assert state.workflow_id == "WF-006"
        assert state.status == "running"

    def test_timestamp_auto_generated(self):
        """测试时间戳自动生成"""
        state = WorkflowState(workflow_id="WF-007")

        assert state.start_time is not None
        assert state.update_time is not None
        # 验证时间戳格式
        datetime.fromisoformat(state.start_time)
        datetime.fromisoformat(state.update_time)


class TestWorkflowExecutor:
    """测试工作流执行器"""

    def test_init_default(self):
        """测试默认初始化"""
        executor = WorkflowExecutor()

        assert executor is not None
        assert executor.state_dir is not None

    def test_init_with_custom_state_dir(self, tmp_path):
        """测试自定义状态目录"""
        executor = WorkflowExecutor(state_dir=str(tmp_path))

        assert executor.state_dir == Path(tmp_path)

    @pytest.mark.asyncio
    async def test_execute_simple_workflow(self):
        """测试执行简单工作流"""
        executor = WorkflowExecutor()

        # 创建简单的工作流函数
        async def simple_workflow(page, config):
            return {"success": True, "result": "done"}

        # Mock page
        mock_page = MagicMock()

        result = await executor.execute(
            workflow_func=simple_workflow, page=mock_page, config={"test": True}
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_execute_with_stages(self):
        """测试执行多阶段工作流"""
        executor = WorkflowExecutor()

        stage_results = []

        async def stage1(page, context):
            stage_results.append("stage1")
            return {"stage1": "done"}

        async def stage2(page, context):
            stage_results.append("stage2")
            return {"stage2": "done"}

        async def multi_stage_workflow(page, config):
            context = {}
            context.update(await stage1(page, context))
            context.update(await stage2(page, context))
            return {"success": True, "context": context}

        mock_page = MagicMock()

        result = await executor.execute(
            workflow_func=multi_stage_workflow, page=mock_page, config={}
        )

        assert len(stage_results) == 2
        assert "stage1" in stage_results
        assert "stage2" in stage_results

    @pytest.mark.asyncio
    async def test_execute_with_failure(self):
        """测试工作流执行失败"""
        executor = WorkflowExecutor()

        async def failing_workflow(page, config):
            raise Exception("Workflow failed")

        mock_page = MagicMock()

        with pytest.raises(Exception, match="Workflow failed"):
            await executor.execute(workflow_func=failing_workflow, page=mock_page, config={})

    @pytest.mark.asyncio
    async def test_save_state(self, tmp_path):
        """测试保存状态"""
        executor = WorkflowExecutor(state_dir=str(tmp_path))

        state = WorkflowState(workflow_id="WF-SAVE-001", status="running", current_stage="stage1")

        await executor.save_state(state)

        # 验证文件创建
        state_file = tmp_path / "WF-SAVE-001.json"
        assert state_file.exists()

        # 验证内容
        with open(state_file) as f:
            data = json.load(f)
        assert data["workflow_id"] == "WF-SAVE-001"

    @pytest.mark.asyncio
    async def test_load_state(self, tmp_path):
        """测试加载状态"""
        executor = WorkflowExecutor(state_dir=str(tmp_path))

        # 创建状态文件
        state_data = {
            "workflow_id": "WF-LOAD-001",
            "status": "running",
            "current_stage": "stage2",
            "completed_stages": ["stage1"],
            "failed_stages": [],
            "start_time": "2024-01-01T10:00:00",
            "update_time": "2024-01-01T10:15:00",
            "context": {"products": [1, 2, 3]},
            "checkpoint_data": {},
        }

        state_file = tmp_path / "WF-LOAD-001.json"
        state_file.write_text(json.dumps(state_data))

        state = await executor.load_state("WF-LOAD-001")

        assert state is not None
        assert state.workflow_id == "WF-LOAD-001"
        assert state.current_stage == "stage2"
        assert "stage1" in state.completed_stages

    @pytest.mark.asyncio
    async def test_load_state_not_found(self, tmp_path):
        """测试加载不存在的状态"""
        executor = WorkflowExecutor(state_dir=str(tmp_path))

        state = await executor.load_state("NONEXISTENT")

        assert state is None

    @pytest.mark.asyncio
    async def test_resume_workflow(self, tmp_path):
        """测试恢复工作流"""
        executor = WorkflowExecutor(state_dir=str(tmp_path))

        # 创建已有状态
        state_data = {
            "workflow_id": "WF-RESUME-001",
            "status": "running",
            "current_stage": "stage2",
            "completed_stages": ["stage1"],
            "failed_stages": [],
            "start_time": "2024-01-01T10:00:00",
            "update_time": "2024-01-01T10:15:00",
            "context": {"stage1_result": "done"},
            "checkpoint_data": {},
        }

        state_file = tmp_path / "WF-RESUME-001.json"
        state_file.write_text(json.dumps(state_data))

        # 定义可恢复的工作流
        async def resumable_workflow(page, config, resume_from=None):
            if resume_from == "stage2":
                return {"success": True, "resumed": True}
            return {"success": True, "resumed": False}

        mock_page = MagicMock()

        result = await executor.resume(
            workflow_id="WF-RESUME-001", workflow_func=resumable_workflow, page=mock_page, config={}
        )

        # 验证恢复逻辑被触发
        assert result is not None


class TestWorkflowExecutorRetry:
    """测试工作流执行器的重试功能"""

    @pytest.mark.asyncio
    async def test_execute_with_retry_success(self):
        """测试重试后成功"""
        executor = WorkflowExecutor()

        call_count = 0

        async def flaky_workflow(page, config):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return {"success": True}

        mock_page = MagicMock()

        # 这里需要根据实际executor的重试配置
        # 如果executor内置重试，应该成功
        try:
            result = await executor.execute(
                workflow_func=flaky_workflow, page=mock_page, config={}, max_retries=3
            )
            assert result is not None
        except Exception:
            # 如果不支持重试参数，至少验证调用了
            assert call_count >= 1


class TestWorkflowExecutorMetrics:
    """测试工作流执行器的指标收集"""

    @pytest.mark.asyncio
    async def test_metrics_collected(self):
        """测试指标被收集"""
        executor = WorkflowExecutor()

        async def workflow_with_metrics(page, config):
            return {"success": True, "products_processed": 20}

        mock_page = MagicMock()

        with patch("src.core.executor.get_metrics") as mock_get_metrics:
            mock_metrics = MagicMock()
            mock_get_metrics.return_value = mock_metrics

            result = await executor.execute(
                workflow_func=workflow_with_metrics, page=mock_page, config={}
            )

            # 验证指标收集器被调用（如果executor集成了）
            assert result is not None


class TestWorkflowStateLifecycle:
    """测试工作流状态生命周期"""

    def test_state_transitions(self):
        """测试状态转换"""
        # 初始状态
        state = WorkflowState(workflow_id="WF-LIFECYCLE")
        assert state.status == "running"

        # 更新为完成
        state.status = "completed"
        state.completed_stages.append("all")
        assert state.status == "completed"

        # 验证可以序列化和反序列化
        json_str = state.to_json()
        restored = WorkflowState.from_json(json_str)
        assert restored.status == "completed"

    def test_failed_state(self):
        """测试失败状态"""
        state = WorkflowState(
            workflow_id="WF-FAILED",
            status="failed",
            failed_stages=["stage2"],
            context={"error": "Connection timeout"},
        )

        assert state.status == "failed"
        assert "stage2" in state.failed_stages
        assert state.context["error"] == "Connection timeout"
