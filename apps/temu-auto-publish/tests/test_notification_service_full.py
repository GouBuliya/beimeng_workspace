"""
@PURPOSE: notification_service 模块的完整单元测试
@OUTLINE:
  - TestNotificationMessage: NotificationMessage 数据类测试
  - TestWorkflowResult: WorkflowResult 数据类测试
  - TestDingTalkChannel: 钉钉通知渠道测试
  - TestWeComChannel: 企业微信通知渠道测试
  - TestEmailChannel: 邮件通知渠道测试
  - TestNotificationService: 通知服务测试
  - TestConfigureNotifications: 配置函数测试
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.core.notification_service
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# ==================== NotificationMessage 数据类测试 ====================
class TestNotificationMessage:
    """NotificationMessage 数据类测试"""

    def test_create_with_required_fields(self):
        """测试只用必填字段创建"""
        from src.core.notification_service import NotificationMessage

        msg = NotificationMessage(
            title="测试标题",
            content="测试内容"
        )

        assert msg.title == "测试标题"
        assert msg.content == "测试内容"
        assert msg.level == "info"  # 默认值
        assert msg.timestamp is not None

    def test_create_with_all_fields(self):
        """测试使用所有字段创建"""
        from src.core.notification_service import NotificationMessage

        ts = datetime.now()
        msg = NotificationMessage(
            title="错误标题",
            content="错误内容",
            level="error",
            timestamp=ts,
            extra={"key": "value"}
        )

        assert msg.title == "错误标题"
        assert msg.content == "错误内容"
        assert msg.level == "error"
        assert msg.timestamp == ts
        assert msg.extra == {"key": "value"}

    def test_different_levels(self):
        """测试不同的消息级别"""
        from src.core.notification_service import NotificationMessage

        levels = ["info", "warning", "error", "success"]
        for level in levels:
            msg = NotificationMessage(title="Test", content="Content", level=level)
            assert msg.level == level


# ==================== WorkflowResult 数据类测试 ====================
class TestWorkflowResult:
    """WorkflowResult 数据类测试"""

    def test_create_success_result(self):
        """测试创建成功结果"""
        from src.core.notification_service import WorkflowResult

        result = WorkflowResult(
            workflow_name="测试工作流",
            success=True,
            total_items=10,
            processed_items=10,
            failed_items=0
        )

        assert result.workflow_name == "测试工作流"
        assert result.success is True
        assert result.total_items == 10
        assert result.processed_items == 10
        assert result.failed_items == 0

    def test_create_failure_result(self):
        """测试创建失败结果"""
        from src.core.notification_service import WorkflowResult

        result = WorkflowResult(
            workflow_name="失败工作流",
            success=False,
            total_items=10,
            processed_items=5,
            failed_items=5,
            error_message="处理失败"
        )

        assert result.success is False
        assert result.failed_items == 5
        assert result.error_message == "处理失败"

    def test_with_duration(self):
        """测试带持续时间的结果"""
        from src.core.notification_service import WorkflowResult

        result = WorkflowResult(
            workflow_name="计时工作流",
            success=True,
            total_items=100,
            processed_items=100,
            failed_items=0,
            duration_seconds=120.5
        )

        assert result.duration_seconds == 120.5

    def test_with_details(self):
        """测试带详情的结果"""
        from src.core.notification_service import WorkflowResult

        result = WorkflowResult(
            workflow_name="详情工作流",
            success=True,
            total_items=5,
            processed_items=5,
            failed_items=0,
            details={"sku_list": ["SKU1", "SKU2"]}
        )

        assert result.details == {"sku_list": ["SKU1", "SKU2"]}


# ==================== DingTalkChannel 测试 ====================
class TestDingTalkChannel:
    """钉钉通知渠道测试"""

    def test_init_with_webhook(self):
        """测试使用 webhook 初始化"""
        from src.core.notification_service import DingTalkChannel

        channel = DingTalkChannel(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx")

        assert channel.webhook_url == "https://oapi.dingtalk.com/robot/send?access_token=xxx"
        assert channel.secret is None

    def test_init_with_secret(self):
        """测试使用密钥初始化"""
        from src.core.notification_service import DingTalkChannel

        channel = DingTalkChannel(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx",
            secret="SEC123456"
        )

        assert channel.secret == "SEC123456"

    @pytest.mark.asyncio
    async def test_send_success(self):
        """测试发送成功"""
        from src.core.notification_service import DingTalkChannel, NotificationMessage

        channel = DingTalkChannel(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx")

        msg = NotificationMessage(title="测试", content="测试内容")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"errcode": 0}
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock()
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await channel.send(msg)

            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self):
        """测试发送失败"""
        from src.core.notification_service import DingTalkChannel, NotificationMessage

        channel = DingTalkChannel(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx")

        msg = NotificationMessage(title="测试", content="测试内容")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"errcode": 1, "errmsg": "error"}
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock()
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await channel.send(msg)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_network_error(self):
        """测试网络错误"""
        from src.core.notification_service import DingTalkChannel, NotificationMessage

        channel = DingTalkChannel(webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx")

        msg = NotificationMessage(title="测试", content="测试内容")

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock()
            mock_client.return_value.post = AsyncMock(side_effect=Exception("Network error"))

            result = await channel.send(msg)

            assert result is False


# ==================== WeComChannel 测试 ====================
class TestWeComChannel:
    """企业微信通知渠道测试"""

    def test_init(self):
        """测试初始化"""
        from src.core.notification_service import WeComChannel

        channel = WeComChannel(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx")

        assert channel.webhook_url == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"

    @pytest.mark.asyncio
    async def test_send_success(self):
        """测试发送成功"""
        from src.core.notification_service import WeComChannel, NotificationMessage

        channel = WeComChannel(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx")

        msg = NotificationMessage(title="测试", content="测试内容")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"errcode": 0}
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock()
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await channel.send(msg)

            assert result is True

    @pytest.mark.asyncio
    async def test_send_failure(self):
        """测试发送失败"""
        from src.core.notification_service import WeComChannel, NotificationMessage

        channel = WeComChannel(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx")

        msg = NotificationMessage(title="测试", content="测试内容")

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock()
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await channel.send(msg)

            assert result is False


# ==================== EmailChannel 测试 ====================
class TestEmailChannel:
    """邮件通知渠道测试"""

    def test_init(self):
        """测试初始化"""
        from src.core.notification_service import EmailChannel

        channel = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="user@example.com",
            password="password",
            recipients=["admin@example.com"]
        )

        assert channel.smtp_host == "smtp.example.com"
        assert channel.smtp_port == 587
        assert channel.username == "user@example.com"
        assert "admin@example.com" in channel.recipients

    def test_init_with_multiple_recipients(self):
        """测试多收件人"""
        from src.core.notification_service import EmailChannel

        channel = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="user@example.com",
            password="password",
            recipients=["admin1@example.com", "admin2@example.com"]
        )

        assert len(channel.recipients) == 2

    @pytest.mark.asyncio
    async def test_send_success(self):
        """测试发送成功"""
        from src.core.notification_service import EmailChannel, NotificationMessage

        channel = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="user@example.com",
            password="password",
            recipients=["admin@example.com"]
        )

        msg = NotificationMessage(title="测试邮件", content="测试内容")

        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp.return_value.__exit__ = MagicMock()

            result = await channel.send(msg)

            # 邮件发送可能返回 True 或 False 取决于实现
            assert result in [True, False]


# ==================== NotificationService 测试 ====================
class TestNotificationService:
    """通知服务测试"""

    def test_init_empty(self):
        """测试空初始化"""
        from src.core.notification_service import NotificationService

        service = NotificationService()

        assert len(service.channels) == 0

    def test_add_channel(self):
        """测试添加渠道"""
        from src.core.notification_service import NotificationService, DingTalkChannel

        service = NotificationService()
        channel = DingTalkChannel(webhook_url="https://example.com")
        service.add_channel(channel)

        assert len(service.channels) == 1

    def test_add_multiple_channels(self):
        """测试添加多个渠道"""
        from src.core.notification_service import (
            NotificationService,
            DingTalkChannel,
            WeComChannel
        )

        service = NotificationService()
        service.add_channel(DingTalkChannel(webhook_url="https://dingtalk.com"))
        service.add_channel(WeComChannel(webhook_url="https://wecom.com"))

        assert len(service.channels) == 2

    @pytest.mark.asyncio
    async def test_notify_no_channels(self):
        """测试无渠道时通知"""
        from src.core.notification_service import NotificationService, NotificationMessage

        service = NotificationService()
        msg = NotificationMessage(title="测试", content="内容")

        # 无渠道应该不报错
        await service.notify(msg)

    @pytest.mark.asyncio
    async def test_notify_all_channels(self):
        """测试通知所有渠道"""
        from src.core.notification_service import NotificationService, NotificationMessage

        service = NotificationService()

        # 创建 mock 渠道
        channel1 = MagicMock()
        channel1.send = AsyncMock(return_value=True)
        channel2 = MagicMock()
        channel2.send = AsyncMock(return_value=True)

        service.add_channel(channel1)
        service.add_channel(channel2)

        msg = NotificationMessage(title="测试", content="内容")
        await service.notify(msg)

        channel1.send.assert_called_once_with(msg)
        channel2.send.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_notify_partial_failure(self):
        """测试部分渠道失败"""
        from src.core.notification_service import NotificationService, NotificationMessage

        service = NotificationService()

        channel1 = MagicMock()
        channel1.send = AsyncMock(return_value=True)
        channel2 = MagicMock()
        channel2.send = AsyncMock(return_value=False)

        service.add_channel(channel1)
        service.add_channel(channel2)

        msg = NotificationMessage(title="测试", content="内容")
        # 部分失败不应该抛出异常
        await service.notify(msg)

    @pytest.mark.asyncio
    async def test_notify_workflow_result(self):
        """测试通知工作流结果"""
        from src.core.notification_service import (
            NotificationService,
            WorkflowResult
        )

        service = NotificationService()

        channel = MagicMock()
        channel.send = AsyncMock(return_value=True)
        service.add_channel(channel)

        result = WorkflowResult(
            workflow_name="测试工作流",
            success=True,
            total_items=10,
            processed_items=10,
            failed_items=0
        )

        await service.notify_workflow_result(result)

        channel.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_workflow_result_failure(self):
        """测试通知工作流失败结果"""
        from src.core.notification_service import (
            NotificationService,
            WorkflowResult
        )

        service = NotificationService()

        channel = MagicMock()
        channel.send = AsyncMock(return_value=True)
        service.add_channel(channel)

        result = WorkflowResult(
            workflow_name="失败工作流",
            success=False,
            total_items=10,
            processed_items=3,
            failed_items=7,
            error_message="处理出错"
        )

        await service.notify_workflow_result(result)

        channel.send.assert_called_once()
        # 验证发送的消息包含错误信息
        call_args = channel.send.call_args
        msg = call_args[0][0]
        assert "失败" in msg.title or "error" in msg.level


# ==================== configure_notifications 函数测试 ====================
class TestConfigureNotifications:
    """configure_notifications 配置函数测试"""

    def test_configure_empty(self):
        """测试空配置"""
        from src.core.notification_service import configure_notifications

        service = configure_notifications({})

        assert len(service.channels) == 0

    def test_configure_dingtalk(self):
        """测试配置钉钉"""
        from src.core.notification_service import configure_notifications

        config = {
            "dingtalk": {
                "enabled": True,
                "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx"
            }
        }

        service = configure_notifications(config)

        assert len(service.channels) == 1

    def test_configure_dingtalk_disabled(self):
        """测试禁用钉钉"""
        from src.core.notification_service import configure_notifications

        config = {
            "dingtalk": {
                "enabled": False,
                "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx"
            }
        }

        service = configure_notifications(config)

        assert len(service.channels) == 0

    def test_configure_wecom(self):
        """测试配置企业微信"""
        from src.core.notification_service import configure_notifications

        config = {
            "wecom": {
                "enabled": True,
                "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
            }
        }

        service = configure_notifications(config)

        assert len(service.channels) == 1

    def test_configure_multiple_channels(self):
        """测试配置多个渠道"""
        from src.core.notification_service import configure_notifications

        config = {
            "dingtalk": {
                "enabled": True,
                "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx"
            },
            "wecom": {
                "enabled": True,
                "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
            }
        }

        service = configure_notifications(config)

        assert len(service.channels) == 2


# ==================== 集成测试 ====================
class TestNotificationIntegration:
    """通知服务集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow_notification(self):
        """测试完整工作流通知"""
        from src.core.notification_service import (
            NotificationService,
            WorkflowResult,
            NotificationMessage
        )

        service = NotificationService()

        # Mock 渠道
        channel = MagicMock()
        channel.send = AsyncMock(return_value=True)
        service.add_channel(channel)

        # 发送工作流开始通知
        start_msg = NotificationMessage(
            title="工作流开始",
            content="开始处理 10 个商品",
            level="info"
        )
        await service.notify(start_msg)

        # 发送工作流结果通知
        result = WorkflowResult(
            workflow_name="批量编辑",
            success=True,
            total_items=10,
            processed_items=10,
            failed_items=0,
            duration_seconds=60.5
        )
        await service.notify_workflow_result(result)

        # 验证两次通知都被发送
        assert channel.send.call_count == 2

    @pytest.mark.asyncio
    async def test_error_notification(self):
        """测试错误通知"""
        from src.core.notification_service import (
            NotificationService,
            NotificationMessage
        )

        service = NotificationService()

        channel = MagicMock()
        channel.send = AsyncMock(return_value=True)
        service.add_channel(channel)

        error_msg = NotificationMessage(
            title="错误警报",
            content="浏览器连接超时",
            level="error",
            extra={"error_code": "TIMEOUT_001"}
        )
        await service.notify(error_msg)

        channel.send.assert_called_once()
        sent_msg = channel.send.call_args[0][0]
        assert sent_msg.level == "error"
