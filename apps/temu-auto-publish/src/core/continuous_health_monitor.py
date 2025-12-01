"""
@PURPOSE: 持续健康监控服务 - 定期执行健康检查并触发告警
@OUTLINE:
  - @dataclass MonitorConfig: 监控配置
  - @dataclass MonitorStats: 监控统计
  - class ContinuousHealthMonitor: 持续监控主类
    - async def start(): 启动后台监控
    - async def stop(): 停止监控
    - async def run_health_check(): 执行单次健康检查
    - async def _process_result(): 处理检查结果
    - async def _send_alert(): 发送告警
@GOTCHAS:
  - 监控在后台异步运行，不阻塞主工作流
  - 连续失败N次后才触发告警，避免误报
  - 需要在工作流结束时显式调用 stop() 停止监控
@DEPENDENCIES:
  - 内部: health_checker, notification_service
  - 外部: asyncio, loguru
@RELATED: health_checker.py, notification_service.py, browser_watchdog.py
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

from .health_checker import HealthChecker, HealthStatus, get_health_checker

if TYPE_CHECKING:
    from ..browser.browser_manager import BrowserManager
    from ..browser.login_controller import LoginController


@dataclass
class MonitorConfig:
    """监控配置.

    Attributes:
        enabled: 是否启用监控
        check_interval_sec: 健康检查间隔(秒)
        alert_threshold: 连续失败N次后触发告警
        include_browser_check: 是否包含浏览器检查
        include_network_check: 是否包含网络检查
        include_disk_check: 是否包含磁盘检查
        include_memory_check: 是否包含内存检查
        alert_cooldown_sec: 同一组件告警冷却时间(秒)
    """

    enabled: bool = True
    check_interval_sec: int = 60
    alert_threshold: int = 3
    include_browser_check: bool = True
    include_network_check: bool = True
    include_disk_check: bool = True
    include_memory_check: bool = True
    alert_cooldown_sec: int = 300  # 5分钟内同一组件不重复告警


@dataclass
class MonitorStats:
    """监控统计信息.

    Attributes:
        total_checks: 总检查次数
        healthy_checks: 健康检查次数
        warning_checks: 警告检查次数
        error_checks: 错误检查次数
        alerts_sent: 已发送告警数
        last_check_time: 最后检查时间
        last_status: 最后状态
    """

    total_checks: int = 0
    healthy_checks: int = 0
    warning_checks: int = 0
    error_checks: int = 0
    alerts_sent: int = 0
    last_check_time: datetime | None = None
    last_status: str = "unknown"


class ContinuousHealthMonitor:
    """持续健康监控.

    功能:
    1. 后台定期执行健康检查
    2. 连续失败N次后触发告警
    3. 支持自定义告警处理
    4. 统计健康状态趋势

    Examples:
        >>> monitor = ContinuousHealthMonitor(
        ...     health_checker=get_health_checker(),
        ...     browser_manager=browser_manager,
        ... )
        >>> await monitor.start()
        >>> # ... 工作流执行 ...
        >>> await monitor.stop()
    """

    def __init__(
        self,
        health_checker: HealthChecker | None = None,
        browser_manager: "BrowserManager | None" = None,
        login_controller: "LoginController | None" = None,
        config: MonitorConfig | None = None,
        on_alert: Callable[[str, dict], Awaitable[None]] | None = None,
        on_status_change: Callable[[str, str], Awaitable[None]] | None = None,
    ):
        """初始化持续健康监控.

        Args:
            health_checker: 健康检查器实例
            browser_manager: 浏览器管理器实例
            login_controller: 登录控制器实例
            config: 监控配置
            on_alert: 告警回调 (component, details)
            on_status_change: 状态变化回调 (old_status, new_status)
        """
        self.health_checker = health_checker or get_health_checker()
        self.browser_manager = browser_manager
        self.login_controller = login_controller
        self.config = config or MonitorConfig()

        self.on_alert = on_alert
        self.on_status_change = on_status_change

        self._running = False
        self._task: asyncio.Task | None = None
        self._consecutive_failures: dict[str, int] = {}
        self._last_alert_time: dict[str, datetime] = {}
        self._stats = MonitorStats()

    @property
    def is_running(self) -> bool:
        """是否正在运行."""
        return self._running

    @property
    def stats(self) -> MonitorStats:
        """获取监控统计信息."""
        return self._stats

    async def start(self) -> None:
        """启动后台监控任务(非阻塞)."""
        if not self.config.enabled:
            logger.info("[HealthMonitor] 健康监控已禁用，跳过启动")
            return

        if self._running:
            logger.debug("[HealthMonitor] 健康监控已在运行")
            return

        self._running = True
        self._task = asyncio.create_task(
            self._monitor_loop(), name="continuous_health_monitor"
        )
        logger.info(
            f"[HealthMonitor] 持续健康监控已启动 "
            f"(检查间隔: {self.config.check_interval_sec}s, "
            f"告警阈值: {self.config.alert_threshold}次)"
        )

    async def stop(self) -> None:
        """停止监控."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        logger.info(
            f"[HealthMonitor] 持续健康监控已停止 "
            f"(总检查: {self._stats.total_checks}, "
            f"健康: {self._stats.healthy_checks}, "
            f"告警: {self._stats.alerts_sent})"
        )

    async def _monitor_loop(self) -> None:
        """监控主循环."""
        while self._running:
            try:
                # 执行健康检查
                result = await self.run_health_check()

                # 处理结果
                await self._process_result(result)

                # 更新统计
                self._stats.total_checks += 1
                self._stats.last_check_time = datetime.now()

                overall_status = result.get("status", "unknown")
                if overall_status == "healthy":
                    self._stats.healthy_checks += 1
                elif overall_status == "degraded":
                    self._stats.warning_checks += 1
                else:
                    self._stats.error_checks += 1

                # 状态变化回调
                if self._stats.last_status != overall_status:
                    if self.on_status_change:
                        try:
                            await self.on_status_change(
                                self._stats.last_status, overall_status
                            )
                        except Exception as e:
                            logger.warning(f"[HealthMonitor] 状态变化回调执行失败: {e}")
                    self._stats.last_status = overall_status

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HealthMonitor] 监控循环异常: {e}")

            # 等待下一次检查
            await asyncio.sleep(self.config.check_interval_sec)

    async def run_health_check(self) -> dict[str, Any]:
        """执行单次健康检查.

        Returns:
            健康检查结果
        """
        return await self.health_checker.check_all(
            browser_manager=self.browser_manager,
            login_controller=self.login_controller,
            include_network=self.config.include_network_check,
        )

    async def _process_result(self, result: dict[str, Any]) -> None:
        """处理健康检查结果.

        Args:
            result: 健康检查结果
        """
        checks = result.get("checks", {})

        for component, check in checks.items():
            status = check.get("status")

            if status == "error":
                # 增加连续失败计数
                self._consecutive_failures[component] = (
                    self._consecutive_failures.get(component, 0) + 1
                )

                # 达到告警阈值
                if (
                    self._consecutive_failures[component]
                    >= self.config.alert_threshold
                ):
                    await self._send_alert(component, check)

            elif status == "warning":
                # 警告不重置计数，但也不增加
                pass

            else:
                # OK 状态重置计数
                self._consecutive_failures[component] = 0

    async def _send_alert(self, component: str, check: dict[str, Any]) -> None:
        """发送告警.

        Args:
            component: 组件名称
            check: 检查结果
        """
        # 检查告警冷却
        now = datetime.now()
        last_alert = self._last_alert_time.get(component)
        if last_alert:
            elapsed = (now - last_alert).total_seconds()
            if elapsed < self.config.alert_cooldown_sec:
                logger.debug(
                    f"[HealthMonitor] 组件 {component} 告警冷却中 "
                    f"(剩余 {self.config.alert_cooldown_sec - elapsed:.0f}s)"
                )
                return

        # 更新告警时间
        self._last_alert_time[component] = now
        self._stats.alerts_sent += 1

        # 构建告警信息
        alert_info = {
            "component": component,
            "status": check.get("status"),
            "message": check.get("message"),
            "details": check.get("details"),
            "consecutive_failures": self._consecutive_failures.get(component, 0),
            "timestamp": now.isoformat(),
        }

        logger.warning(
            f"[HealthMonitor] 健康告警: {component} - {check.get('message')} "
            f"(连续失败 {self._consecutive_failures.get(component, 0)} 次)"
        )

        # 触发告警回调
        if self.on_alert:
            try:
                await self.on_alert(component, alert_info)
            except Exception as e:
                logger.warning(f"[HealthMonitor] 告警回调执行失败: {e}")

    async def get_current_status(self) -> dict[str, Any]:
        """获取当前健康状态摘要.

        Returns:
            状态摘要
        """
        return {
            "is_running": self._running,
            "last_status": self._stats.last_status,
            "last_check_time": (
                self._stats.last_check_time.isoformat()
                if self._stats.last_check_time
                else None
            ),
            "stats": {
                "total_checks": self._stats.total_checks,
                "healthy_checks": self._stats.healthy_checks,
                "warning_checks": self._stats.warning_checks,
                "error_checks": self._stats.error_checks,
                "alerts_sent": self._stats.alerts_sent,
            },
            "consecutive_failures": dict(self._consecutive_failures),
        }


# 便捷工厂函数
def create_health_monitor(
    browser_manager: "BrowserManager | None" = None,
    login_controller: "LoginController | None" = None,
    **config_kwargs,
) -> ContinuousHealthMonitor:
    """创建持续健康监控实例.

    Args:
        browser_manager: 浏览器管理器
        login_controller: 登录控制器(可选)
        **config_kwargs: 配置参数

    Returns:
        ContinuousHealthMonitor 实例
    """
    config = MonitorConfig(**config_kwargs)
    return ContinuousHealthMonitor(
        browser_manager=browser_manager,
        login_controller=login_controller,
        config=config,
    )


# 导出
__all__ = [
    "ContinuousHealthMonitor",
    "MonitorConfig",
    "MonitorStats",
    "create_health_monitor",
]
