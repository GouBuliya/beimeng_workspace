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

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ==================== NotificationMessage 数据类测试 ====================
class TestNotificationMessage:
    """NotificationMessage 数据类测试"""

    def test_create_with_required_fields(self):
        """测试只用必填字段创建"""
        from src.core.notification_service import NotificationMessage

        msg = NotificationMessage(title="测试标题", content="测试内容")

        assert msg.title == "测试标题"
        assert msg.content == "测试内容"
        assert msg.level == "info"  # 默认值
        assert msg.workflow_id is None
        assert msg.metadata is None

    def test_create_with_all_fields(self):
        """测试使用所有字段创建"""
        from src.core.notification_service import NotificationMessage

        msg = NotificationMessage(
            title="错误标题",
            content="错误内容",
            level="error",
            workflow_id="wf-12345",
            metadata={"key": "value"},
        )

        assert msg.title == "错误标题"
        assert msg.content == "错误内容"
        assert msg.level == "error"
        assert msg.workflow_id == "wf-12345"
        assert msg.metadata == {"key": "value"}

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
            workflow_id="wf-001",
            success=True,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:05:00",
            stages=[{"name": "阶段1", "success": True}],
        )

        assert result.workflow_id == "wf-001"
        assert result.success is True
        assert result.start_time == "2024-01-01T10:00:00"
        assert result.end_time == "2024-01-01T10:05:00"
        assert len(result.stages) == 1

    def test_create_failure_result(self):
        """测试创建失败结果"""
        from src.core.notification_service import WorkflowResult

        result = WorkflowResult(
            workflow_id="wf-002",
            success=False,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:02:00",
            stages=[{"name": "阶段1", "success": False, "message": "处理失败"}],
            errors=["连接超时", "数据验证失败"],
        )

        assert result.success is False
        assert len(result.errors) == 2
        assert "连接超时" in result.errors

    def test_with_metrics(self):
        """测试带指标的结果"""
        from src.core.notification_service import WorkflowResult

        result = WorkflowResult(
            workflow_id="wf-003",
            success=True,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:10:00",
            stages=[],
            metrics={"total_items": 100, "processed_items": 100},
        )

        assert result.metrics is not None
        assert result.metrics["total_items"] == 100

    def test_with_multiple_stages(self):
        """测试多阶段结果"""
        from src.core.notification_service import WorkflowResult

        result = WorkflowResult(
            workflow_id="wf-004",
            success=True,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:30:00",
            stages=[
                {"name": "初始化", "success": True, "message": "完成"},
                {"name": "数据处理", "success": True, "message": "处理100条"},
                {"name": "提交", "success": True, "message": "全部提交"},
            ],
        )

        assert len(result.stages) == 3
        assert all(s["success"] for s in result.stages)


# ==================== DingTalkChannel 测试 ====================
class TestDingTalkChannel:
    """钉钉通知渠道测试"""

    def test_init_with_webhook(self):
        """测试使用 webhook 初始化"""
        from src.core.notification_service import DingTalkChannel

        channel = DingTalkChannel(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx"
        )

        assert channel.webhook_url == "https://oapi.dingtalk.com/robot/send?access_token=xxx"
        assert channel.enabled is True

    def test_init_disabled(self):
        """测试禁用状态初始化"""
        from src.core.notification_service import DingTalkChannel

        channel = DingTalkChannel(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx",
            enabled=False,
        )

        assert channel.enabled is False

    @pytest.mark.asyncio
    async def test_send_disabled(self):
        """测试禁用时发送"""
        from src.core.notification_service import DingTalkChannel, NotificationMessage

        channel = DingTalkChannel(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx",
            enabled=False,
        )

        msg = NotificationMessage(title="测试", content="测试内容")
        result = await channel.send(msg)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_no_webhook(self):
        """测试无 webhook URL 时发送"""
        from src.core.notification_service import DingTalkChannel, NotificationMessage

        channel = DingTalkChannel(webhook_url="")

        msg = NotificationMessage(title="测试", content="测试内容")
        result = await channel.send(msg)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        """测试发送成功"""
        from src.core.notification_service import DingTalkChannel, NotificationMessage

        channel = DingTalkChannel(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx"
        )

        msg = NotificationMessage(title="测试", content="测试内容")

        # Mock aiohttp.ClientSession
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"errcode": 0})

            mock_session = MagicMock()
            mock_session.post = MagicMock(
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()
                )
            )
            mock_session_class.return_value = MagicMock(
                __aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock()
            )

            result = await channel.send(msg)

            assert result is True

    @pytest.mark.asyncio
    async def test_send_api_error(self):
        """测试 API 返回错误"""
        from src.core.notification_service import DingTalkChannel, NotificationMessage

        channel = DingTalkChannel(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx"
        )

        msg = NotificationMessage(title="测试", content="测试内容")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"errcode": 1, "errmsg": "error"})

            mock_session = MagicMock()
            mock_session.post = MagicMock(
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()
                )
            )
            mock_session_class.return_value = MagicMock(
                __aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock()
            )

            result = await channel.send(msg)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_http_error(self):
        """测试 HTTP 请求失败"""
        from src.core.notification_service import DingTalkChannel, NotificationMessage

        channel = DingTalkChannel(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx"
        )

        msg = NotificationMessage(title="测试", content="测试内容")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 500

            mock_session = MagicMock()
            mock_session.post = MagicMock(
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()
                )
            )
            mock_session_class.return_value = MagicMock(
                __aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock()
            )

            result = await channel.send(msg)

            assert result is False

    @pytest.mark.asyncio
    async def test_send_network_error(self):
        """测试网络错误"""
        from src.core.notification_service import DingTalkChannel, NotificationMessage

        channel = DingTalkChannel(
            webhook_url="https://oapi.dingtalk.com/robot/send?access_token=xxx"
        )

        msg = NotificationMessage(title="测试", content="测试内容")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Network error")
            )

            result = await channel.send(msg)

            assert result is False

    def test_format_markdown(self):
        """测试 Markdown 格式化"""
        from src.core.notification_service import DingTalkChannel, NotificationMessage

        channel = DingTalkChannel(webhook_url="https://example.com")

        msg = NotificationMessage(
            title="测试标题",
            content="测试内容",
            level="success",
            workflow_id="wf-001",
        )

        formatted = channel._format_markdown(msg)

        assert "测试标题" in formatted
        assert "测试内容" in formatted
        assert "✅" in formatted  # success emoji
        assert "wf-001" in formatted


# ==================== WeComChannel 测试 ====================
class TestWeComChannel:
    """企业微信通知渠道测试"""

    def test_init(self):
        """测试初始化"""
        from src.core.notification_service import WeComChannel

        channel = WeComChannel(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        )

        assert channel.webhook_url == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        assert channel.enabled is True

    def test_init_disabled(self):
        """测试禁用状态"""
        from src.core.notification_service import WeComChannel

        channel = WeComChannel(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
            enabled=False,
        )

        assert channel.enabled is False

    @pytest.mark.asyncio
    async def test_send_disabled(self):
        """测试禁用时发送"""
        from src.core.notification_service import NotificationMessage, WeComChannel

        channel = WeComChannel(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
            enabled=False,
        )

        msg = NotificationMessage(title="测试", content="测试内容")
        result = await channel.send(msg)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        """测试发送成功"""
        from src.core.notification_service import NotificationMessage, WeComChannel

        channel = WeComChannel(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        )

        msg = NotificationMessage(title="测试", content="测试内容")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={"errcode": 0})

            mock_session = MagicMock()
            mock_session.post = MagicMock(
                return_value=AsyncMock(
                    __aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()
                )
            )
            mock_session_class.return_value = MagicMock(
                __aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock()
            )

            result = await channel.send(msg)

            assert result is True

    @pytest.mark.asyncio
    async def test_send_network_error(self):
        """测试网络错误"""
        from src.core.notification_service import NotificationMessage, WeComChannel

        channel = WeComChannel(
            webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
        )

        msg = NotificationMessage(title="测试", content="测试内容")

        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_class.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Network error")
            )

            result = await channel.send(msg)

            assert result is False

    def test_format_markdown(self):
        """测试 Markdown 格式化"""
        from src.core.notification_service import NotificationMessage, WeComChannel

        channel = WeComChannel(webhook_url="https://example.com")

        msg = NotificationMessage(
            title="测试标题",
            content="测试内容",
            level="warning",
            workflow_id="wf-002",
        )

        formatted = channel._format_markdown(msg)

        assert "测试标题" in formatted
        assert "测试内容" in formatted
        assert "wf-002" in formatted


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
            from_addr="noreply@example.com",
            to_addrs=["admin@example.com"],
        )

        assert channel.smtp_host == "smtp.example.com"
        assert channel.smtp_port == 587
        assert channel.username == "user@example.com"
        assert channel.from_addr == "noreply@example.com"
        assert "admin@example.com" in channel.to_addrs
        assert channel.use_tls is True  # 默认值
        assert channel.enabled is True

    def test_init_with_multiple_recipients(self):
        """测试多收件人"""
        from src.core.notification_service import EmailChannel

        channel = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="user@example.com",
            password="password",
            from_addr="noreply@example.com",
            to_addrs=["admin1@example.com", "admin2@example.com"],
        )

        assert len(channel.to_addrs) == 2

    def test_init_disabled(self):
        """测试禁用状态"""
        from src.core.notification_service import EmailChannel

        channel = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="user@example.com",
            password="password",
            from_addr="noreply@example.com",
            to_addrs=["admin@example.com"],
            enabled=False,
        )

        assert channel.enabled is False

    @pytest.mark.asyncio
    async def test_send_disabled(self):
        """测试禁用时发送"""
        from src.core.notification_service import EmailChannel, NotificationMessage

        channel = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="user@example.com",
            password="password",
            from_addr="noreply@example.com",
            to_addrs=["admin@example.com"],
            enabled=False,
        )

        msg = NotificationMessage(title="测试邮件", content="测试内容")
        result = await channel.send(msg)

        assert result is False

    def test_format_html(self):
        """测试 HTML 格式化"""
        from src.core.notification_service import EmailChannel, NotificationMessage

        channel = EmailChannel(
            smtp_host="smtp.example.com",
            smtp_port=587,
            username="user@example.com",
            password="password",
            from_addr="noreply@example.com",
            to_addrs=["admin@example.com"],
        )

        msg = NotificationMessage(
            title="测试标题",
            content="测试内容",
            level="error",
            workflow_id="wf-003",
        )

        html = channel._format_html(msg)

        assert "测试标题" in html
        assert "测试内容" in html
        assert "wf-003" in html
        assert "#f5222d" in html  # error 颜色


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
        from src.core.notification_service import DingTalkChannel, NotificationService

        service = NotificationService()
        channel = DingTalkChannel(webhook_url="https://example.com")
        service.add_channel(channel)

        assert len(service.channels) == 1

    def test_add_multiple_channels(self):
        """测试添加多个渠道"""
        from src.core.notification_service import DingTalkChannel, NotificationService, WeComChannel

        service = NotificationService()
        service.add_channel(DingTalkChannel(webhook_url="https://dingtalk.com"))
        service.add_channel(WeComChannel(webhook_url="https://wecom.com"))

        assert len(service.channels) == 2

    @pytest.mark.asyncio
    async def test_send_no_channels(self):
        """测试无渠道时发送"""
        from src.core.notification_service import NotificationMessage, NotificationService

        service = NotificationService()
        msg = NotificationMessage(title="测试", content="内容")

        result = await service.send(msg)

        assert result == {}

    @pytest.mark.asyncio
    async def test_send_all_channels(self):
        """测试发送到所有渠道"""
        from src.core.notification_service import NotificationMessage, NotificationService

        service = NotificationService()

        # 创建 mock 渠道
        channel1 = MagicMock()
        channel1.enabled = True
        channel1.__class__.__name__ = "Channel1"
        channel1.send = AsyncMock(return_value=True)

        channel2 = MagicMock()
        channel2.enabled = True
        channel2.__class__.__name__ = "Channel2"
        channel2.send = AsyncMock(return_value=True)

        service.add_channel(channel1)
        service.add_channel(channel2)

        msg = NotificationMessage(title="测试", content="内容")
        result = await service.send(msg)

        assert result["Channel1"] is True
        assert result["Channel2"] is True

    @pytest.mark.asyncio
    async def test_send_partial_failure(self):
        """测试部分渠道失败"""
        from src.core.notification_service import NotificationMessage, NotificationService

        service = NotificationService()

        channel1 = MagicMock()
        channel1.enabled = True
        channel1.__class__.__name__ = "Channel1"
        channel1.send = AsyncMock(return_value=True)

        channel2 = MagicMock()
        channel2.enabled = True
        channel2.__class__.__name__ = "Channel2"
        channel2.send = AsyncMock(return_value=False)

        service.add_channel(channel1)
        service.add_channel(channel2)

        msg = NotificationMessage(title="测试", content="内容")
        result = await service.send(msg)

        assert result["Channel1"] is True
        assert result["Channel2"] is False

    @pytest.mark.asyncio
    async def test_send_with_exception(self):
        """测试发送时异常处理"""
        from src.core.notification_service import NotificationMessage, NotificationService

        service = NotificationService()

        channel = MagicMock()
        channel.enabled = True
        channel.__class__.__name__ = "FailingChannel"
        channel.send = AsyncMock(side_effect=Exception("Send failed"))

        service.add_channel(channel)

        msg = NotificationMessage(title="测试", content="内容")
        result = await service.send(msg)

        assert result["FailingChannel"] is False

    @pytest.mark.asyncio
    async def test_send_workflow_result(self):
        """测试发送工作流结果"""
        from src.core.notification_service import NotificationService, WorkflowResult

        service = NotificationService()

        channel = MagicMock()
        channel.enabled = True
        channel.__class__.__name__ = "TestChannel"
        channel.send = AsyncMock(return_value=True)
        service.add_channel(channel)

        result = WorkflowResult(
            workflow_id="wf-001",
            success=True,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:05:00",
            stages=[{"name": "阶段1", "success": True}],
        )

        send_result = await service.send_workflow_result(result)

        channel.send.assert_called_once()
        assert send_result["TestChannel"] is True

    @pytest.mark.asyncio
    async def test_send_workflow_result_failure(self):
        """测试发送工作流失败结果"""
        from src.core.notification_service import NotificationService, WorkflowResult

        service = NotificationService()

        channel = MagicMock()
        channel.enabled = True
        channel.__class__.__name__ = "TestChannel"
        channel.send = AsyncMock(return_value=True)
        service.add_channel(channel)

        result = WorkflowResult(
            workflow_id="wf-002",
            success=False,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:02:00",
            stages=[{"name": "阶段1", "success": False}],
            errors=["处理出错"],
        )

        await service.send_workflow_result(result)

        channel.send.assert_called_once()
        # 验证发送的消息包含错误信息
        call_args = channel.send.call_args
        msg = call_args[0][0]
        assert "失败" in msg.title
        assert msg.level == "error"

    @pytest.mark.asyncio
    async def test_send_alert(self):
        """测试发送告警"""
        from src.core.notification_service import NotificationService

        service = NotificationService()

        channel = MagicMock()
        channel.enabled = True
        channel.__class__.__name__ = "TestChannel"
        channel.send = AsyncMock(return_value=True)
        service.add_channel(channel)

        await service.send_alert(
            title="测试告警",
            content="告警内容",
            level="warning",
            workflow_id="wf-003",
        )

        channel.send.assert_called_once()
        call_args = channel.send.call_args
        msg = call_args[0][0]
        assert msg.title == "测试告警"
        assert msg.level == "warning"
        assert msg.workflow_id == "wf-003"

    def test_format_workflow_result_success(self):
        """测试格式化成功的工作流结果"""
        from src.core.notification_service import NotificationService, WorkflowResult

        service = NotificationService()

        result = WorkflowResult(
            workflow_id="wf-001",
            success=True,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:05:00",
            stages=[{"name": "阶段1", "success": True, "message": "完成"}],
            metrics={"total": 100},
        )

        msg = service._format_workflow_result(result)

        assert "成功" in msg.title
        assert msg.level == "success"
        assert "wf-001" in msg.content
        assert "阶段1" in msg.content

    def test_format_workflow_result_failure(self):
        """测试格式化失败的工作流结果"""
        from src.core.notification_service import NotificationService, WorkflowResult

        service = NotificationService()

        result = WorkflowResult(
            workflow_id="wf-002",
            success=False,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:02:00",
            stages=[{"name": "阶段1", "success": False}],
            errors=["错误1", "错误2"],
        )

        msg = service._format_workflow_result(result)

        assert "失败" in msg.title
        assert msg.level == "error"
        assert "错误1" in msg.content


# ==================== configure_notifications 函数测试 ====================
class TestConfigureNotifications:
    """configure_notifications 配置函数测试"""

    def test_configure_empty(self):
        """测试空配置"""
        # 重置全局实例
        import src.core.notification_service as ns_module
        from src.core.notification_service import (
            configure_notifications,
            get_notification_service,
        )

        ns_module._notification_service = None

        configure_notifications({})
        service = get_notification_service()

        # 空配置不添加任何渠道
        assert len(service.channels) == 0

    def test_configure_dingtalk(self):
        """测试配置钉钉"""
        # 重置全局实例
        import src.core.notification_service as ns_module
        from src.core.notification_service import configure_notifications, get_notification_service

        ns_module._notification_service = None

        config = {
            "dingtalk": {
                "enabled": True,
                "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
            }
        }

        configure_notifications(config)
        service = get_notification_service()

        assert len(service.channels) == 1
        assert service.channels[0].__class__.__name__ == "DingTalkChannel"

    def test_configure_dingtalk_disabled(self):
        """测试禁用钉钉"""
        # 重置全局实例
        import src.core.notification_service as ns_module
        from src.core.notification_service import configure_notifications, get_notification_service

        ns_module._notification_service = None

        config = {
            "dingtalk": {
                "enabled": False,
                "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
            }
        }

        configure_notifications(config)
        service = get_notification_service()

        assert len(service.channels) == 0

    def test_configure_wecom(self):
        """测试配置企业微信"""
        # 重置全局实例
        import src.core.notification_service as ns_module
        from src.core.notification_service import configure_notifications, get_notification_service

        ns_module._notification_service = None

        config = {
            "wecom": {
                "enabled": True,
                "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
            }
        }

        configure_notifications(config)
        service = get_notification_service()

        assert len(service.channels) == 1
        assert service.channels[0].__class__.__name__ == "WeComChannel"

    def test_configure_email(self):
        """测试配置邮件"""
        # 重置全局实例
        import src.core.notification_service as ns_module
        from src.core.notification_service import configure_notifications, get_notification_service

        ns_module._notification_service = None

        config = {
            "email": {
                "enabled": True,
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "username": "user@example.com",
                "password": "password",
                "from_addr": "noreply@example.com",
                "to_addrs": ["admin@example.com"],
            }
        }

        configure_notifications(config)
        service = get_notification_service()

        assert len(service.channels) == 1
        assert service.channels[0].__class__.__name__ == "EmailChannel"

    def test_configure_multiple_channels(self):
        """测试配置多个渠道"""
        # 重置全局实例
        import src.core.notification_service as ns_module
        from src.core.notification_service import configure_notifications, get_notification_service

        ns_module._notification_service = None

        config = {
            "dingtalk": {
                "enabled": True,
                "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
            },
            "wecom": {
                "enabled": True,
                "webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
            },
        }

        configure_notifications(config)
        service = get_notification_service()

        assert len(service.channels) == 2


# ==================== get_notification_service 函数测试 ====================
class TestGetNotificationService:
    """get_notification_service 函数测试"""

    def test_returns_singleton(self):
        """测试返回单例"""
        # 重置
        import src.core.notification_service as ns_module
        from src.core.notification_service import get_notification_service

        ns_module._notification_service = None

        service1 = get_notification_service()
        service2 = get_notification_service()

        assert service1 is service2

    def test_creates_new_if_none(self):
        """测试无实例时创建新实例"""
        # 重置
        import src.core.notification_service as ns_module
        from src.core.notification_service import get_notification_service

        ns_module._notification_service = None

        service = get_notification_service()

        assert service is not None
        assert len(service.channels) == 0


# ==================== 集成测试 ====================
class TestNotificationIntegration:
    """通知服务集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow_notification(self):
        """测试完整工作流通知"""
        from src.core.notification_service import (
            NotificationMessage,
            NotificationService,
            WorkflowResult,
        )

        service = NotificationService()

        # Mock 渠道
        channel = MagicMock()
        channel.enabled = True
        channel.__class__.__name__ = "MockChannel"
        channel.send = AsyncMock(return_value=True)
        service.add_channel(channel)

        # 发送工作流开始通知
        start_msg = NotificationMessage(
            title="工作流开始", content="开始处理 10 个商品", level="info"
        )
        await service.send(start_msg)

        # 发送工作流结果通知
        result = WorkflowResult(
            workflow_id="wf-001",
            success=True,
            start_time="2024-01-01T10:00:00",
            end_time="2024-01-01T10:05:00",
            stages=[{"name": "处理", "success": True}],
            metrics={"total": 10, "success": 10},
        )
        await service.send_workflow_result(result)

        # 验证两次通知都被发送
        assert channel.send.call_count == 2

    @pytest.mark.asyncio
    async def test_error_notification(self):
        """测试错误通知"""
        from src.core.notification_service import NotificationService

        service = NotificationService()

        channel = MagicMock()
        channel.enabled = True
        channel.__class__.__name__ = "MockChannel"
        channel.send = AsyncMock(return_value=True)
        service.add_channel(channel)

        await service.send_alert(
            title="错误警报",
            content="浏览器连接超时",
            level="error",
            workflow_id="wf-err-001",
        )

        channel.send.assert_called_once()
        sent_msg = channel.send.call_args[0][0]
        assert sent_msg.level == "error"
        assert sent_msg.workflow_id == "wf-err-001"
