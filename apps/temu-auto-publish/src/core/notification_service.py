"""
@PURPOSE: 通知服务 - 支持钉钉,企业微信,邮件等多渠道告警通知
@OUTLINE:
  - class NotificationChannel: 通知渠道基类
  - class DingTalkChannel: 钉钉机器人通知
  - class WeComChannel: 企业微信机器人通知
  - class EmailChannel: 邮件通知
  - class NotificationService: 通知服务主类
  - def send_workflow_result(): 发送工作流结果通知
  - def send_alert(): 发送告警通知
@GOTCHAS:
  - Webhook URL需要在配置文件中设置
  - 邮件发送需要SMTP配置
  - 通知失败不应影响主流程
@DEPENDENCIES:
  - 外部: requests, aiohttp, aiosmtplib
  - 内部: loguru
@RELATED: health_checker.py, executor.py
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import aiohttp
from loguru import logger


@dataclass
class NotificationMessage:
    """通知消息数据结构.

    Attributes:
        title: 消息标题
        content: 消息内容
        level: 消息级别(info/warning/error/success)
        workflow_id: 工作流ID(可选)
        metadata: 额外元数据
    """

    title: str
    content: str
    level: str = "info"
    workflow_id: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class WorkflowResult:
    """工作流执行结果.

    用于生成结构化的通知消息.

    Attributes:
        workflow_id: 工作流ID
        success: 是否成功
        start_time: 开始时间
        end_time: 结束时间
        stages: 阶段结果列表
        errors: 错误列表
        metrics: 指标数据
    """

    workflow_id: str
    success: bool
    start_time: str
    end_time: str
    stages: list[dict[str, Any]]
    errors: list[str] = None
    metrics: dict[str, Any] | None = None


class NotificationChannel(ABC):
    """通知渠道基类."""

    def __init__(self, enabled: bool = True):
        """初始化通知渠道.

        Args:
            enabled: 是否启用该渠道
        """
        self.enabled = enabled

    @abstractmethod
    async def send(self, message: NotificationMessage) -> bool:
        """发送通知.

        Args:
            message: 通知消息

        Returns:
            是否发送成功
        """
        pass

    def format_message(self, message: NotificationMessage) -> str:
        """格式化消息内容.

        Args:
            message: 通知消息

        Returns:
            格式化后的内容
        """
        return message.content


class DingTalkChannel(NotificationChannel):
    """钉钉机器人通知渠道.

    使用钉钉自定义机器人Webhook发送Markdown消息.

    Examples:
        >>> channel = DingTalkChannel(webhook_url="https://...")
        >>> await channel.send(NotificationMessage(
        ...     title="测试通知",
        ...     content="这是一条测试消息",
        ...     level="info"
        ... ))
    """

    def __init__(self, webhook_url: str, enabled: bool = True):
        """初始化钉钉通知渠道.

        Args:
            webhook_url: 钉钉机器人Webhook URL
            enabled: 是否启用
        """
        super().__init__(enabled)
        self.webhook_url = webhook_url

    async def send(self, message: NotificationMessage) -> bool:
        """发送钉钉通知.

        Args:
            message: 通知消息

        Returns:
            是否发送成功
        """
        if not self.enabled or not self.webhook_url:
            logger.debug("钉钉通知已禁用或未配置Webhook URL")
            return False

        try:
            # 格式化为Markdown
            markdown_text = self._format_markdown(message)

            # 构造钉钉消息体
            payload = {
                "msgtype": "markdown",
                "markdown": {"title": message.title, "text": markdown_text},
            }

            # 发送请求
            async with aiohttp.ClientSession() as session, session.post(
                self.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("errcode") == 0:
                        logger.info(f"✓ 钉钉通知发送成功: {message.title}")
                        return True
                    else:
                        logger.warning(f"钉钉通知发送失败: {result.get('errmsg')}")
                        return False
                else:
                    logger.warning(f"钉钉通知HTTP请求失败: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"发送钉钉通知异常: {e}")
            return False

    def _format_markdown(self, message: NotificationMessage) -> str:
        """格式化为钉钉Markdown格式.

        Args:
            message: 通知消息

        Returns:
            Markdown文本
        """
        # 根据级别选择emoji
        emoji_map = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
        emoji = emoji_map.get(message.level, "ℹ️")

        # 构建Markdown
        md_lines = [
            f"## {emoji} {message.title}",
            "",
            message.content,
            "",
            f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if message.workflow_id:
            md_lines.append(f"**工作流ID**: {message.workflow_id}")

        return "\n".join(md_lines)


class WeComChannel(NotificationChannel):
    """企业微信机器人通知渠道.

    使用企业微信群机器人Webhook发送Markdown消息.

    Examples:
        >>> channel = WeComChannel(webhook_url="https://...")
        >>> await channel.send(NotificationMessage(
        ...     title="测试通知",
        ...     content="这是一条测试消息"
        ... ))
    """

    def __init__(self, webhook_url: str, enabled: bool = True):
        """初始化企业微信通知渠道.

        Args:
            webhook_url: 企业微信机器人Webhook URL
            enabled: 是否启用
        """
        super().__init__(enabled)
        self.webhook_url = webhook_url

    async def send(self, message: NotificationMessage) -> bool:
        """发送企业微信通知.

        Args:
            message: 通知消息

        Returns:
            是否发送成功
        """
        if not self.enabled or not self.webhook_url:
            logger.debug("企业微信通知已禁用或未配置Webhook URL")
            return False

        try:
            # 格式化为Markdown
            markdown_text = self._format_markdown(message)

            # 构造企业微信消息体
            payload = {"msgtype": "markdown", "markdown": {"content": markdown_text}}

            # 发送请求
            async with aiohttp.ClientSession() as session, session.post(
                self.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("errcode") == 0:
                        logger.info(f"✓ 企业微信通知发送成功: {message.title}")
                        return True
                    else:
                        logger.warning(f"企业微信通知发送失败: {result.get('errmsg')}")
                        return False
                else:
                    logger.warning(f"企业微信通知HTTP请求失败: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"发送企业微信通知异常: {e}")
            return False

    def _format_markdown(self, message: NotificationMessage) -> str:
        """格式化为企业微信Markdown格式.

        Args:
            message: 通知消息

        Returns:
            Markdown文本
        """
        # 根据级别选择颜色标记
        color_map = {"info": "info", "success": "info", "warning": "warning", "error": "warning"}
        color = color_map.get(message.level, "info")

        # 构建Markdown
        md_lines = [
            f"**{message.title}**",
            f'> <font color="{color}">{message.content}</font>',
            "",
            f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if message.workflow_id:
            md_lines.append(f"工作流ID: `{message.workflow_id}`")

        return "\n".join(md_lines)


class EmailChannel(NotificationChannel):
    """邮件通知渠道.

    使用SMTP发送HTML格式的邮件通知.

    Examples:
        >>> channel = EmailChannel(
        ...     smtp_host="smtp.example.com",
        ...     smtp_port=587,
        ...     username="user@example.com",
        ...     password="password",
        ...     from_addr="noreply@example.com",
        ...     to_addrs=["admin@example.com"]
        ... )
        >>> await channel.send(NotificationMessage(...))
    """

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
        to_addrs: list[str],
        use_tls: bool = True,
        enabled: bool = True,
    ):
        """初始化邮件通知渠道.

        Args:
            smtp_host: SMTP服务器地址
            smtp_port: SMTP端口
            username: SMTP用户名
            password: SMTP密码
            from_addr: 发件人地址
            to_addrs: 收件人地址列表
            use_tls: 是否使用TLS
            enabled: 是否启用
        """
        super().__init__(enabled)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.use_tls = use_tls

    async def send(self, message: NotificationMessage) -> bool:
        """发送邮件通知.

        Args:
            message: 通知消息

        Returns:
            是否发送成功
        """
        if not self.enabled:
            logger.debug("邮件通知已禁用")
            return False

        try:
            # 由于aiosmtplib可能未安装,使用同步smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            # 创建邮件
            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.title
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)

            # HTML内容
            html_content = self._format_html(message)
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            # 发送邮件(在线程池中执行以避免阻塞)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._send_email_sync, msg)

            logger.info(f"✓ 邮件通知发送成功: {message.title}")
            return True

        except Exception as e:
            logger.error(f"发送邮件通知异常: {e}")
            return False

    def _send_email_sync(self, msg):
        """同步发送邮件(在线程池中执行).

        Args:
            msg: 邮件消息对象
        """
        import smtplib

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.send_message(msg)

    def _format_html(self, message: NotificationMessage) -> str:
        """格式化为HTML格式.

        Args:
            message: 通知消息

        Returns:
            HTML文本
        """
        # 根据级别选择颜色
        color_map = {
            "info": "#1890ff",
            "success": "#52c41a",
            "warning": "#faad14",
            "error": "#f5222d",
        }
        color = color_map.get(message.level, "#1890ff")

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .header {{ background-color: {color}; color: white; padding: 20px; }}
                .content {{ padding: 20px; }}
                .footer {{ background-color: #f0f0f0; padding: 10px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{message.title}</h2>
            </div>
            <div class="content">
                <pre style="white-space: pre-wrap;">{message.content}</pre>
                <p><strong>时间:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        """

        if message.workflow_id:
            html += f"<p><strong>工作流ID:</strong> {message.workflow_id}</p>"

        html += """
            </div>
            <div class="footer">
                <p>此邮件由Temu自动发布系统自动发送,请勿回复.</p>
            </div>
        </body>
        </html>
        """

        return html


class NotificationService:
    """通知服务主类.

    管理多个通知渠道,支持同时发送到多个渠道.

    Attributes:
        channels: 通知渠道列表

    Examples:
        >>> service = NotificationService()
        >>> service.add_channel(DingTalkChannel(webhook_url="..."))
        >>> await service.send_workflow_result(result)
    """

    def __init__(self):
        """初始化通知服务."""
        self.channels: list[NotificationChannel] = []
        logger.info("通知服务已初始化")

    def add_channel(self, channel: NotificationChannel):
        """添加通知渠道.

        Args:
            channel: 通知渠道实例
        """
        self.channels.append(channel)
        logger.debug(f"已添加通知渠道: {channel.__class__.__name__}")

    async def send(self, message: NotificationMessage) -> dict[str, bool]:
        """发送通知到所有渠道.

        Args:
            message: 通知消息

        Returns:
            各渠道发送结果 {渠道名: 是否成功}
        """
        if not self.channels:
            logger.warning("没有配置任何通知渠道")
            return {}

        results = {}
        tasks = []

        for channel in self.channels:
            if channel.enabled:
                tasks.append(self._send_to_channel(channel, message))

        if tasks:
            channel_results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, channel in enumerate([c for c in self.channels if c.enabled]):
                channel_name = channel.__class__.__name__
                if isinstance(channel_results[i], Exception):
                    logger.error(f"渠道 {channel_name} 发送异常: {channel_results[i]}")
                    results[channel_name] = False
                else:
                    results[channel_name] = channel_results[i]

        return results

    async def _send_to_channel(
        self, channel: NotificationChannel, message: NotificationMessage
    ) -> bool:
        """发送通知到指定渠道.

        Args:
            channel: 通知渠道
            message: 通知消息

        Returns:
            是否发送成功
        """
        try:
            return await channel.send(message)
        except Exception as e:
            logger.error(f"渠道 {channel.__class__.__name__} 发送失败: {e}")
            return False

    async def send_workflow_result(self, result: WorkflowResult) -> dict[str, bool]:
        """发送工作流执行结果通知.

        Args:
            result: 工作流结果

        Returns:
            各渠道发送结果
        """
        # 格式化结果为消息
        message = self._format_workflow_result(result)
        return await self.send(message)

    def _format_workflow_result(self, result: WorkflowResult) -> NotificationMessage:
        """格式化工作流结果为通知消息.

        Args:
            result: 工作流结果

        Returns:
            通知消息
        """
        # 确定消息级别
        level = "success" if result.success else "error"

        # 计算总耗时
        try:
            start_dt = datetime.fromisoformat(result.start_time)
            end_dt = datetime.fromisoformat(result.end_time)
            duration = (end_dt - start_dt).total_seconds()
            duration_str = f"{int(duration // 60)}分{int(duration % 60)}秒"
        except:
            duration_str = "未知"

        # 构建内容
        content_lines = [
            f"**工作流ID**: {result.workflow_id}",
            f"**执行时间**: {result.start_time[:19]}",
            f"**执行结果**: {'✅ 成功' if result.success else '❌ 失败'}",
            f"**总耗时**: {duration_str}",
            "",
            "### 阶段统计",
        ]

        # 添加阶段信息
        for stage in result.stages:
            stage_name = stage.get("name", "未知阶段")
            stage_success = stage.get("success", False)
            stage_message = stage.get("message", "")
            status_icon = "✅" if stage_success else "❌"
            content_lines.append(f"- {status_icon} {stage_name}: {stage_message}")

        # 添加错误信息
        if result.errors:
            content_lines.append("")
            content_lines.append("### 错误详情")
            for error in result.errors[:5]:  # 最多显示5个错误
                content_lines.append(f"- {error}")

        # 添加指标信息
        if result.metrics:
            content_lines.append("")
            content_lines.append("### 关键指标")
            for key, value in result.metrics.items():
                content_lines.append(f"- {key}: {value}")

        content = "\n".join(content_lines)

        title = f"Temu自动发布 - {'执行成功' if result.success else '执行失败'}"

        return NotificationMessage(
            title=title, content=content, level=level, workflow_id=result.workflow_id
        )

    async def send_alert(
        self, title: str, content: str, level: str = "warning", workflow_id: str | None = None
    ) -> dict[str, bool]:
        """发送告警通知.

        Args:
            title: 告警标题
            content: 告警内容
            level: 告警级别
            workflow_id: 工作流ID(可选)

        Returns:
            各渠道发送结果
        """
        message = NotificationMessage(
            title=title, content=content, level=level, workflow_id=workflow_id
        )
        return await self.send(message)


# 全局通知服务实例
_notification_service: NotificationService | None = None


def get_notification_service() -> NotificationService:
    """获取全局通知服务实例.

    Returns:
        通知服务实例
    """
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


def configure_notifications(config: dict[str, Any]):
    """根据配置初始化通知服务.

    Args:
        config: 配置字典,包含各渠道配置

    Examples:
        >>> configure_notifications({
        ...     "dingtalk": {
        ...         "enabled": True,
        ...         "webhook_url": "https://..."
        ...     },
        ...     "wecom": {
        ...         "enabled": True,
        ...         "webhook_url": "https://..."
        ...     }
        ... })
    """
    service = get_notification_service()

    # 配置钉钉
    dingtalk_config = config.get("dingtalk", {})
    if dingtalk_config.get("enabled"):
        webhook_url = dingtalk_config.get("webhook_url")
        if webhook_url:
            service.add_channel(DingTalkChannel(webhook_url=webhook_url))
            logger.info("✓ 钉钉通知渠道已启用")

    # 配置企业微信
    wecom_config = config.get("wecom", {})
    if wecom_config.get("enabled"):
        webhook_url = wecom_config.get("webhook_url")
        if webhook_url:
            service.add_channel(WeComChannel(webhook_url=webhook_url))
            logger.info("✓ 企业微信通知渠道已启用")

    # 配置邮件
    email_config = config.get("email", {})
    if email_config.get("enabled"):
        required_fields = [
            "smtp_host",
            "smtp_port",
            "username",
            "password",
            "from_addr",
            "to_addrs",
        ]
        if all(email_config.get(field) for field in required_fields):
            service.add_channel(
                EmailChannel(
                    smtp_host=email_config["smtp_host"],
                    smtp_port=email_config["smtp_port"],
                    username=email_config["username"],
                    password=email_config["password"],
                    from_addr=email_config["from_addr"],
                    to_addrs=email_config["to_addrs"],
                    use_tls=email_config.get("use_tls", True),
                )
            )
            logger.info("✓ 邮件通知渠道已启用")
        else:
            logger.warning("邮件通知配置不完整,已跳过")
