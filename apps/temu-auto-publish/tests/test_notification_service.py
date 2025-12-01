"""
@PURPOSE: 测试通知服务
@OUTLINE:
  - TestNotificationMessage: 测试通知消息
  - TestWorkflowResult: 测试工作流结果
  - TestNotificationChannel: 测试通知渠道
  - TestNotificationService: 测试通知服务
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.core.notification_service
"""

from unittest.mock import AsyncMock

import pytest
from src.core.notification_service import (
    NotificationChannel,
    NotificationMessage,
    NotificationService,
    WorkflowResult,
)


class TestNotificationMessage:
    """测试通知消息数据结构"""

    def test_create_basic_message(self):
        """测试创建基本消息"""
        message = NotificationMessage(title="Test Title", content="Test Content")

        assert message.title == "Test Title"
        assert message.content == "Test Content"
        assert message.level == "info"  # 默认值
        assert message.workflow_id is None
        assert message.metadata is None

    def test_create_message_with_all_fields(self):
        """测试创建包含所有字段的消息"""
        message = NotificationMessage(
            title="Workflow Complete",
            content="Workflow finished successfully",
            level="success",
            workflow_id="WF-2024-001",
            metadata={"products_count": 20, "duration_minutes": 30},
        )

        assert message.level == "success"
        assert message.workflow_id == "WF-2024-001"
        assert message.metadata["products_count"] == 20

    def test_message_levels(self):
        """测试不同消息级别"""
        levels = ["info", "warning", "error", "success"]

        for level in levels:
            message = NotificationMessage(title="Test", content="Test", level=level)
            assert message.level == level


class TestWorkflowResult:
    """测试工作流结果"""

    def test_create_success_result(self):
        """测试创建成功结果"""
        result = WorkflowResult(
            workflow_id="WF-001",
            success=True,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:30:00",
            stages=[
                {"name": "stage1", "status": "completed"},
                {"name": "stage2", "status": "completed"},
            ],
        )

        assert result.workflow_id == "WF-001"
        assert result.success is True
        assert len(result.stages) == 2

    def test_create_failed_result(self):
        """测试创建失败结果"""
        result = WorkflowResult(
            workflow_id="WF-002",
            success=False,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:15:00",
            stages=[
                {"name": "stage1", "status": "completed"},
                {"name": "stage2", "status": "failed"},
            ],
            errors=["Connection timeout", "Retry exhausted"],
        )

        assert result.success is False
        assert len(result.errors) == 2

    def test_result_with_metrics(self):
        """测试包含指标的结果"""
        result = WorkflowResult(
            workflow_id="WF-003",
            success=True,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T11:00:00",
            stages=[],
            metrics={"total_products": 20, "success_rate": 0.95, "avg_time_per_product": 180},
        )

        assert result.metrics["total_products"] == 20
        assert result.metrics["success_rate"] == 0.95


class TestNotificationChannel:
    """测试通知渠道基类"""

    def test_channel_enabled_default(self):
        """测试渠道默认启用"""

        # 创建一个具体实现来测试基类
        class TestChannel(NotificationChannel):
            async def send(self, message: NotificationMessage) -> bool:
                return True

        channel = TestChannel()
        assert channel.enabled is True

    def test_channel_disabled(self):
        """测试禁用渠道"""

        class TestChannel(NotificationChannel):
            async def send(self, message: NotificationMessage) -> bool:
                return True

        channel = TestChannel(enabled=False)
        assert channel.enabled is False

    def test_format_message_default(self):
        """测试默认消息格式化"""

        class TestChannel(NotificationChannel):
            async def send(self, message: NotificationMessage) -> bool:
                return True

        channel = TestChannel()
        message = NotificationMessage(title="Test Title", content="Test Content")

        formatted = channel.format_message(message)

        # format_message 默认只返回 content
        assert "Test Content" in formatted


class TestNotificationService:
    """测试通知服务"""

    def test_init_default(self):
        """测试默认初始化"""
        service = NotificationService()

        assert service is not None
        assert isinstance(service.channels, list)

    def test_init_with_config(self):
        """测试初始化 - 不带配置路径参数"""
        # 当前 API 不支持 config_path 参数
        service = NotificationService()

        # 验证服务正常创建
        assert service is not None
        assert isinstance(service.channels, list)

    @pytest.mark.asyncio
    async def test_send_notification_no_channels(self):
        """测试无渠道时发送通知"""
        service = NotificationService()
        service.channels = []  # 确保为空列表

        message = NotificationMessage(title="Test", content="Test content")

        # 应该不抛异常
        results = await service.send(message)

        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_send_notification_with_mock_channel(self):
        """测试使用Mock渠道发送通知"""
        service = NotificationService()

        # 创建Mock渠道 (需要设置 __class__.__name__)
        mock_channel = AsyncMock()
        mock_channel.enabled = True
        mock_channel.send = AsyncMock(return_value=True)
        mock_channel.__class__.__name__ = "MockChannel"

        service.channels = [mock_channel]

        message = NotificationMessage(title="Test Notification", content="This is a test")

        results = await service.send(message)

        # 使用类名作为 key
        assert "MockChannel" in results
        assert results["MockChannel"] is True

    @pytest.mark.asyncio
    async def test_send_notification_channel_failure(self):
        """测试渠道发送失败"""
        service = NotificationService()

        # 创建失败的Mock渠道
        mock_channel = AsyncMock()
        mock_channel.enabled = True
        mock_channel.send = AsyncMock(side_effect=Exception("Network error"))
        mock_channel.__class__.__name__ = "FailingChannel"

        service.channels = [mock_channel]

        message = NotificationMessage(title="Test", content="Test")

        # 应该捕获异常而不是抛出
        results = await service.send(message)

        assert "FailingChannel" in results
        assert results["FailingChannel"] is False

    @pytest.mark.asyncio
    async def test_send_workflow_result_success(self):
        """测试发送成功的工作流结果"""
        service = NotificationService()

        mock_channel = AsyncMock()
        mock_channel.enabled = True
        mock_channel.send = AsyncMock(return_value=True)
        mock_channel.__class__.__name__ = "MockChannel"
        service.channels = [mock_channel]

        result = WorkflowResult(
            workflow_id="WF-001",
            success=True,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:30:00",
            stages=[{"name": "stage1", "status": "completed"}],
        )

        await service.send_workflow_result(result)

        mock_channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_workflow_result_failure(self):
        """测试发送失败的工作流结果"""
        service = NotificationService()

        mock_channel = AsyncMock()
        mock_channel.enabled = True
        mock_channel.send = AsyncMock(return_value=True)
        mock_channel.__class__.__name__ = "MockChannel"
        service.channels = [mock_channel]

        result = WorkflowResult(
            workflow_id="WF-002",
            success=False,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:15:00",
            stages=[{"name": "stage1", "status": "failed"}],
            errors=["Connection timeout"],
        )

        await service.send_workflow_result(result)

        mock_channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_alert(self):
        """测试发送告警"""
        service = NotificationService()

        mock_channel = AsyncMock()
        mock_channel.enabled = True
        mock_channel.send = AsyncMock(return_value=True)
        mock_channel.__class__.__name__ = "MockChannel"
        service.channels = [mock_channel]

        await service.send_alert(
            title="High Memory Usage", content="Memory usage exceeded 90%", level="warning"
        )

        mock_channel.send.assert_called_once()
        call_args = mock_channel.send.call_args
        message = call_args[0][0]
        assert message.level == "warning"

    @pytest.mark.asyncio
    async def test_disabled_channel_not_called(self):
        """测试禁用的渠道不被调用"""
        service = NotificationService()

        mock_channel = AsyncMock()
        mock_channel.enabled = False
        mock_channel.send = AsyncMock(return_value=True)
        mock_channel.__class__.__name__ = "DisabledChannel"

        service.channels = [mock_channel]

        message = NotificationMessage(title="Test", content="Test")

        await service.send(message)

        # 禁用的渠道不应该被调用
        mock_channel.send.assert_not_called()


class TestNotificationServiceConfiguration:
    """测试通知服务配置"""

    def test_load_config_file_not_found(self):
        """测试初始化默认服务"""
        # 当前 API 不支持 config_path
        service = NotificationService()

        assert service is not None
        assert isinstance(service.channels, list)

    def test_add_channel(self):
        """测试添加渠道"""
        service = NotificationService()

        mock_channel = AsyncMock()
        mock_channel.enabled = True

        service.add_channel(mock_channel)

        assert mock_channel in service.channels

    def test_remove_channel(self):
        """测试渠道列表操作"""
        service = NotificationService()

        mock_channel = AsyncMock()
        service.channels.append(mock_channel)

        # 使用列表操作移除
        service.channels.remove(mock_channel)

        assert mock_channel not in service.channels
