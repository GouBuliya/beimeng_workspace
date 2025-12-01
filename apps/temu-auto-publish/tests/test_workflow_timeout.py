"""
@PURPOSE: 工作流超时控制单元测试
@OUTLINE:
  - TestWorkflowTimeoutError: 测试超时异常类
  - TestWithStageTimeout: 测试超时上下文管理器
  - TestTimeoutConfig: 测试超时配置
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.workflow_timeout import (
    DEFAULT_STAGE_TIMEOUTS,
    TimeoutConfig,
    WorkflowTimeoutError,
    get_timeout_config,
    run_with_workflow_timeout,
    timeout_stage,
    with_stage_timeout,
)


class TestWorkflowTimeoutError:
    """测试 WorkflowTimeoutError 异常类."""

    def test_error_message(self):
        """测试错误消息格式."""
        error = WorkflowTimeoutError("test_stage", 60.0)
        assert "test_stage" in str(error)
        assert "60" in str(error)

    def test_attributes(self):
        """测试异常属性."""
        started_at = datetime.now()
        error = WorkflowTimeoutError("my_stage", 120.0, started_at)
        assert error.stage == "my_stage"
        assert error.timeout_seconds == 120.0
        assert error.started_at == started_at


class TestTimeoutConfig:
    """测试 TimeoutConfig 配置类."""

    def test_default_values(self):
        """测试默认配置值."""
        config = TimeoutConfig()
        assert config.stage1_first_edit == 900  # 15分钟
        assert config.stage2_claim == 600  # 10分钟
        assert config.stage3_batch_edit == 1200  # 20分钟
        assert config.stage4_publish == 600  # 10分钟
        assert config.workflow_total == 3600  # 60分钟

    def test_get_stage_timeout(self):
        """测试获取阶段超时."""
        config = TimeoutConfig()
        assert config.get("stage1_first_edit") == 900
        assert config.get("unknown_stage", 999) == 999

    def test_custom_config(self):
        """测试自定义配置."""
        config = TimeoutConfig(
            stage1_first_edit=300,
            workflow_total=1800,
        )
        assert config.stage1_first_edit == 300
        assert config.workflow_total == 1800


class TestGetTimeoutConfig:
    """测试 get_timeout_config 函数."""

    def test_returns_default_when_none(self):
        """测试无参数时返回默认配置."""
        config = get_timeout_config(None)
        assert config == DEFAULT_STAGE_TIMEOUTS

    def test_custom_config_override(self):
        """测试自定义配置覆盖."""
        custom = {"stage1_first_edit": 300, "workflow_total": 1800}
        config = get_timeout_config(custom)
        assert config.stage1_first_edit == 300
        assert config.workflow_total == 1800
        # 未覆盖的值应使用默认
        assert config.stage2_claim == DEFAULT_STAGE_TIMEOUTS.stage2_claim


class TestWithStageTimeout:
    """测试 with_stage_timeout 上下文管理器."""

    @pytest.mark.asyncio
    async def test_completes_within_timeout(self):
        """测试在超时内完成."""
        executed = False

        async with with_stage_timeout("test_stage", 5.0):
            await asyncio.sleep(0.1)
            executed = True

        assert executed is True

    @pytest.mark.asyncio
    async def test_raises_timeout_error(self):
        """测试超时时抛出异常."""
        with pytest.raises(WorkflowTimeoutError) as exc_info:
            async with with_stage_timeout("slow_stage", 0.1):
                await asyncio.sleep(1.0)

        assert exc_info.value.stage == "slow_stage"
        assert exc_info.value.timeout_seconds == 0.1

    @pytest.mark.asyncio
    async def test_calls_on_timeout_callback(self):
        """测试超时时调用回调."""
        callback_called = False

        def on_timeout():
            nonlocal callback_called
            callback_called = True

        with pytest.raises(WorkflowTimeoutError):
            async with with_stage_timeout("test", 0.1, on_timeout=on_timeout):
                await asyncio.sleep(1.0)

        assert callback_called is True

    @pytest.mark.asyncio
    async def test_calls_async_on_timeout_callback(self):
        """测试超时时调用异步回调."""
        callback_called = False

        async def async_on_timeout():
            nonlocal callback_called
            callback_called = True

        with pytest.raises(WorkflowTimeoutError):
            async with with_stage_timeout("test", 0.1, on_timeout=async_on_timeout):
                await asyncio.sleep(1.0)

        assert callback_called is True

    @pytest.mark.asyncio
    async def test_callback_exception_does_not_suppress_timeout(self):
        """测试回调异常不会抑制超时异常."""

        def bad_callback():
            raise ValueError("callback error")

        with pytest.raises(WorkflowTimeoutError):
            async with with_stage_timeout("test", 0.1, on_timeout=bad_callback):
                await asyncio.sleep(1.0)


class TestRunWithWorkflowTimeout:
    """测试 run_with_workflow_timeout 函数."""

    @pytest.mark.asyncio
    async def test_returns_workflow_result(self):
        """测试返回工作流结果."""

        async def my_workflow(x, y):
            return x + y

        result = await run_with_workflow_timeout(my_workflow, 1, 2, timeout_seconds=5.0)
        assert result == 3

    @pytest.mark.asyncio
    async def test_raises_timeout_on_slow_workflow(self):
        """测试慢工作流超时."""

        async def slow_workflow():
            await asyncio.sleep(10.0)

        with pytest.raises(WorkflowTimeoutError) as exc_info:
            await run_with_workflow_timeout(slow_workflow, timeout_seconds=0.1)

        assert exc_info.value.stage == "workflow_total"


class TestTimeoutStageDecorator:
    """测试 timeout_stage 装饰器."""

    @pytest.mark.asyncio
    async def test_decorator_applies_timeout(self):
        """测试装饰器应用超时."""
        custom_config = TimeoutConfig(stage1_first_edit=0.1)

        @timeout_stage("stage1_first_edit", timeout_config=custom_config)
        async def slow_function():
            await asyncio.sleep(1.0)

        with pytest.raises(WorkflowTimeoutError):
            await slow_function()

    @pytest.mark.asyncio
    async def test_decorator_allows_completion(self):
        """测试装饰器允许正常完成."""

        @timeout_stage("stage1_first_edit")
        async def fast_function():
            return "done"

        result = await fast_function()
        assert result == "done"
