"""
@PURPOSE: 测试断点恢复管理器
@OUTLINE:
  - test_workflow_checkpoint_properties: 测试检查点属性
  - test_checkpoint_manager_save_load: 测试保存和加载
  - test_checkpoint_manager_stages: 测试阶段管理
  - test_checkpoint_manager_resume: 测试恢复功能
  - test_checkpoint_manager_cleanup: 测试清理功能
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.core.checkpoint_manager import (
    CheckpointManager,
    StageCheckpoint,
    WorkflowCheckpoint,
    get_checkpoint_manager,
)


class TestStageCheckpoint:
    """测试 StageCheckpoint 数据结构"""
    
    def test_default_values(self):
        """测试默认值"""
        stage = StageCheckpoint(name="test_stage", status="pending")
        
        assert stage.name == "test_stage"
        assert stage.status == "pending"
        assert stage.start_time is None
        assert stage.end_time is None
        assert stage.data == {}
        assert stage.error is None
        assert stage.retry_count == 0
    
    def test_with_data(self):
        """测试带数据的阶段"""
        stage = StageCheckpoint(
            name="stage1",
            status="completed",
            data={"products": [1, 2, 3]},
        )
        
        assert stage.data == {"products": [1, 2, 3]}


class TestWorkflowCheckpoint:
    """测试 WorkflowCheckpoint 数据结构"""
    
    def test_completed_stages_property(self):
        """测试已完成阶段属性"""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_123",
            stages={
                "stage1": StageCheckpoint(name="stage1", status="completed"),
                "stage2": StageCheckpoint(name="stage2", status="in_progress"),
                "stage3": StageCheckpoint(name="stage3", status="pending"),
            },
        )
        
        assert checkpoint.completed_stages == ["stage1"]
    
    def test_failed_stages_property(self):
        """测试失败阶段属性"""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_123",
            stages={
                "stage1": StageCheckpoint(name="stage1", status="completed"),
                "stage2": StageCheckpoint(name="stage2", status="failed"),
            },
        )
        
        assert checkpoint.failed_stages == ["stage2"]
    
    def test_is_resumable_true(self):
        """测试可恢复判断 - 可恢复"""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_123",
            stages={
                "stage1": StageCheckpoint(name="stage1", status="completed"),
                "stage2": StageCheckpoint(name="stage2", status="failed"),
            },
        )
        
        # 有完成的阶段且有未完成的阶段
        assert checkpoint.is_resumable is True
    
    def test_is_resumable_false_no_completed(self):
        """测试可恢复判断 - 无完成阶段"""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_123",
            stages={
                "stage1": StageCheckpoint(name="stage1", status="pending"),
            },
        )
        
        assert checkpoint.is_resumable is False
    
    def test_is_resumable_false_all_completed(self):
        """测试可恢复判断 - 全部完成"""
        checkpoint = WorkflowCheckpoint(
            workflow_id="test_123",
            stages={
                "stage1": StageCheckpoint(name="stage1", status="completed"),
                "stage2": StageCheckpoint(name="stage2", status="completed"),
            },
        )
        
        # 没有未完成的阶段
        assert checkpoint.is_resumable is False
    
    def test_to_dict_and_from_dict(self):
        """测试序列化和反序列化"""
        original = WorkflowCheckpoint(
            workflow_id="test_123",
            workflow_type="test_type",
            current_stage="stage2",
            stages={
                "stage1": StageCheckpoint(
                    name="stage1",
                    status="completed",
                    data={"key": "value"},
                ),
            },
            global_data={"shared": True},
        )
        
        # 转换为字典
        data = original.to_dict()
        
        assert data["workflow_id"] == "test_123"
        assert data["stages"]["stage1"]["status"] == "completed"
        
        # 从字典恢复
        restored = WorkflowCheckpoint.from_dict(data)
        
        assert restored.workflow_id == original.workflow_id
        assert restored.stages["stage1"].data == {"key": "value"}


@pytest.mark.asyncio
class TestCheckpointManager:
    """测试 CheckpointManager"""
    
    @pytest.fixture
    def temp_checkpoint_dir(self):
        """创建临时检查点目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    async def test_save_and_load_checkpoint(self, temp_checkpoint_dir):
        """测试保存和加载检查点"""
        manager = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        # 保存检查点
        await manager.save_checkpoint("stage1", {"data": 123})
        
        # 创建新管理器加载
        manager2 = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        checkpoint = await manager2.load_checkpoint()
        
        assert checkpoint is not None
        assert checkpoint.workflow_id == "workflow_test"
        assert checkpoint.current_stage == "stage1"
        assert "stage1" in checkpoint.stages
    
    async def test_mark_stage_complete(self, temp_checkpoint_dir):
        """测试标记阶段完成"""
        manager = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        await manager.mark_stage_complete("stage1", {"products": [1, 2]})
        
        assert manager.checkpoint is not None
        assert manager.checkpoint.stages["stage1"].status == "completed"
        assert manager.checkpoint.stages["stage1"].data == {"products": [1, 2]}
    
    async def test_mark_stage_failed(self, temp_checkpoint_dir):
        """测试标记阶段失败"""
        manager = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        # 先保存一个进行中的状态
        await manager.save_checkpoint("stage1")
        
        # 标记失败
        await manager.mark_stage_failed("stage1", "测试错误")
        
        assert manager.checkpoint.stages["stage1"].status == "failed"
        assert manager.checkpoint.stages["stage1"].error == "测试错误"
        assert manager.checkpoint.last_error == "测试错误"
    
    async def test_should_skip_stage(self, temp_checkpoint_dir):
        """测试跳过阶段判断"""
        manager = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        # 无检查点时不跳过
        assert manager.should_skip_stage("stage1") is False
        
        # 阶段完成后跳过
        await manager.mark_stage_complete("stage1")
        assert manager.should_skip_stage("stage1") is True
        
        # 未完成的阶段不跳过
        assert manager.should_skip_stage("stage2") is False
    
    async def test_get_stage_data(self, temp_checkpoint_dir):
        """测试获取阶段数据"""
        manager = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        # 无数据时返回空字典
        assert manager.get_stage_data("stage1") == {}
        
        # 保存数据后可获取
        await manager.mark_stage_complete("stage1", {"key": "value"})
        assert manager.get_stage_data("stage1") == {"key": "value"}
    
    async def test_get_global_data(self, temp_checkpoint_dir):
        """测试获取全局数据"""
        manager = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        # 无数据时返回空字典
        assert manager.get_global_data() == {}
        
        # 保存全局数据
        await manager.save_checkpoint("stage1", global_data={"shared": True})
        assert manager.get_global_data() == {"shared": True}
    
    async def test_increment_retry(self, temp_checkpoint_dir):
        """测试增加重试计数"""
        manager = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        await manager.save_checkpoint("stage1")
        
        # 增加全局计数
        count = await manager.increment_retry()
        assert count == 1
        
        count = await manager.increment_retry()
        assert count == 2
        
        # 增加阶段计数
        count = await manager.increment_retry("stage1")
        assert count == 1
    
    async def test_clear_checkpoint(self, temp_checkpoint_dir):
        """测试清除检查点"""
        manager = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        await manager.save_checkpoint("stage1")
        assert manager.checkpoint_file.exists()
        
        result = await manager.clear_checkpoint()
        
        assert result is True
        assert not manager.checkpoint_file.exists()
        assert manager.checkpoint is None
    
    async def test_get_resume_info(self, temp_checkpoint_dir):
        """测试获取恢复信息"""
        manager = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        # 无检查点时
        info = manager.get_resume_info()
        assert info["has_checkpoint"] is False
        assert info["resumable"] is False
        
        # 有检查点时
        await manager.mark_stage_complete("stage1")
        await manager.save_checkpoint("stage2")
        
        info = manager.get_resume_info()
        assert info["has_checkpoint"] is True
        assert info["workflow_id"] == "workflow_test"
        assert "stage1" in info["completed_stages"]
    
    async def test_concurrent_access(self, temp_checkpoint_dir):
        """测试并发访问"""
        manager = CheckpointManager(
            "workflow_test",
            checkpoint_dir=temp_checkpoint_dir,
        )
        
        # 并发保存多个阶段
        async def save_stage(name: str):
            await manager.save_checkpoint(name, {"stage": name})
        
        import asyncio
        await asyncio.gather(
            save_stage("stage1"),
            save_stage("stage2"),
            save_stage("stage3"),
        )
        
        # 所有阶段都应该被保存
        assert len(manager.checkpoint.stages) == 3


@pytest.mark.asyncio
class TestCheckpointCleanup:
    """测试检查点清理功能"""
    
    async def test_cleanup_old_checkpoints(self):
        """测试清理过期检查点"""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_dir = Path(tmpdir)
            
            # 创建一个"旧"检查点文件
            old_file = checkpoint_dir / "old_workflow.json"
            old_file.write_text(json.dumps({
                "workflow_id": "old",
                "workflow_type": "test",
            }))
            
            # 修改文件时间为48小时前
            import os
            old_time = datetime.now() - timedelta(hours=48)
            os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))
            
            # 创建一个新检查点文件
            new_file = checkpoint_dir / "new_workflow.json"
            new_file.write_text(json.dumps({
                "workflow_id": "new",
                "workflow_type": "test",
            }))
            
            # 清理（保留24小时）
            cleaned = await CheckpointManager.cleanup_old_checkpoints(
                checkpoint_dir=checkpoint_dir,
                retention_hours=24,
            )
            
            assert cleaned == 1
            assert not old_file.exists()
            assert new_file.exists()
    
    def test_list_checkpoints(self):
        """测试列出检查点"""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_dir = Path(tmpdir)
            
            # 创建检查点文件
            for i in range(3):
                file = checkpoint_dir / f"workflow_{i}.json"
                file.write_text(json.dumps({
                    "workflow_id": f"workflow_{i}",
                    "workflow_type": "test",
                    "current_stage": f"stage{i}",
                    "updated_at": f"2024-01-0{i+1}T00:00:00",
                }))
            
            checkpoints = CheckpointManager.list_checkpoints(checkpoint_dir)
            
            assert len(checkpoints) == 3
            # 应该按更新时间倒序排列
            assert checkpoints[0]["workflow_id"] == "workflow_2"


class TestGetCheckpointManager:
    """测试便捷函数"""
    
    def test_get_checkpoint_manager(self):
        """测试获取管理器实例"""
        manager = get_checkpoint_manager("test_workflow", "test_type")
        
        assert isinstance(manager, CheckpointManager)
        assert manager.workflow_id == "test_workflow"
        assert manager.workflow_type == "test_type"

