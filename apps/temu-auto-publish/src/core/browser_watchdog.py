"""
@PURPOSE: 浏览器看门狗 - 监控浏览器健康状态并自动恢复
@OUTLINE:
  - class RecoveryLevel: 恢复级别枚举
  - @dataclass WatchdogConfig: 看门狗配置
  - @dataclass HealthCheckResult: 健康检查结果
  - class BrowserWatchdog: 浏览器监控主类
    - async def start(): 启动监控循环
    - async def stop(): 停止监控
    - async def check_health(): 检查浏览器健康
    - async def recover(): 尝试恢复浏览器
    - async def _execute_recovery(): 执行特定级别的恢复
@GOTCHAS:
  - 看门狗在后台异步运行，不阻塞主工作流
  - 恢复策略按级别递进，从轻量到重量
  - 需要在工作流结束时显式调用 stop() 停止监控
@DEPENDENCIES:
  - 内部: browser_manager, login_controller
  - 外部: asyncio, loguru
@RELATED: browser_manager.py, health_checker.py
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from loguru import logger

if TYPE_CHECKING:
    from ..browser.browser_manager import BrowserManager
    from ..browser.login_controller import LoginController


class RecoveryLevel(IntEnum):
    """恢复级别枚举.

    从轻量到重量依次递进，优先尝试低级别恢复.
    """

    REFRESH_PAGE = 1  # 刷新页面
    NEW_PAGE = 2  # 创建新页面
    NEW_CONTEXT = 3  # 创建新上下文
    RESTART_BROWSER = 4  # 重启浏览器
    FULL_RELOGIN = 5  # 完全重新登录


@dataclass
class WatchdogConfig:
    """看门狗配置.

    Attributes:
        enabled: 是否启用看门狗
        heartbeat_interval_sec: 心跳检查间隔(秒)
        health_check_timeout_sec: 健康检查超时(秒)
        max_recovery_attempts: 单级别最大恢复尝试次数
        recovery_cooldown_sec: 恢复冷却时间(秒)
        enable_auto_relogin: 是否自动重新登录
        page_response_timeout_sec: 页面响应超时(秒)
        max_consecutive_failures: 最大连续失败次数(超过则停止看门狗)

    Note:
        心跳间隔已从 30s 优化为 10s，以更快检测浏览器崩溃。
        配合 24 小时稳定运行需求。
    """

    enabled: bool = True
    heartbeat_interval_sec: int = 10  # 从 30s 优化为 10s，更快检测崩溃
    health_check_timeout_sec: int = 10
    max_recovery_attempts: int = 3
    recovery_cooldown_sec: int = 60
    enable_auto_relogin: bool = True
    page_response_timeout_sec: int = 5
    max_consecutive_failures: int = 10


@dataclass
class WatchdogHealthResult:
    """看门狗健康检查结果.

    Attributes:
        is_healthy: 是否健康
        level: 问题级别 (0=健康, 1-5=对应恢复级别)
        message: 状态消息
        details: 详细信息
        timestamp: 检查时间
    """

    is_healthy: bool
    level: int = 0
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RecoveryStats:
    """恢复统计信息.

    Attributes:
        total_recoveries: 总恢复次数
        successful_recoveries: 成功恢复次数
        failed_recoveries: 失败恢复次数
        last_recovery_time: 最后恢复时间
        last_recovery_level: 最后恢复级别
        consecutive_failures: 连续失败次数
    """

    total_recoveries: int = 0
    successful_recoveries: int = 0
    failed_recoveries: int = 0
    last_recovery_time: datetime | None = None
    last_recovery_level: RecoveryLevel | None = None
    consecutive_failures: int = 0


class BrowserWatchdog:
    """浏览器看门狗 - 后台持续监控浏览器健康.

    功能:
    1. 定期心跳检测浏览器状态
    2. 发现异常时自动尝试恢复
    3. 分级恢复策略，从轻量到重量
    4. 支持恢复成功/失败回调

    Examples:
        >>> watchdog = BrowserWatchdog(
        ...     browser_manager=browser_manager,
        ...     login_controller=login_controller,
        ... )
        >>> await watchdog.start()
        >>> # ... 工作流执行 ...
        >>> await watchdog.stop()
    """

    def __init__(
        self,
        browser_manager: "BrowserManager",
        login_controller: "LoginController | None" = None,
        config: WatchdogConfig | None = None,
        on_recovery_success: Callable[[], Awaitable[None]] | None = None,
        on_recovery_failed: Callable[[Exception], Awaitable[None]] | None = None,
        on_health_check: Callable[[WatchdogHealthResult], Awaitable[None]] | None = None,
    ):
        """初始化浏览器看门狗.

        Args:
            browser_manager: 浏览器管理器实例
            login_controller: 登录控制器实例(用于完全重登)
            config: 看门狗配置
            on_recovery_success: 恢复成功回调
            on_recovery_failed: 恢复失败回调
            on_health_check: 健康检查完成回调
        """
        self.browser_manager = browser_manager
        self.login_controller = login_controller
        self.config = config or WatchdogConfig()

        self.on_recovery_success = on_recovery_success
        self.on_recovery_failed = on_recovery_failed
        self.on_health_check = on_health_check

        self._running = False
        self._task: asyncio.Task | None = None
        self._paused = False
        self._stats = RecoveryStats()

    @property
    def is_running(self) -> bool:
        """是否正在运行."""
        return self._running

    @property
    def stats(self) -> RecoveryStats:
        """获取恢复统计信息."""
        return self._stats

    async def start(self) -> None:
        """启动监控循环(非阻塞).

        如果看门狗已经在运行，则跳过启动.
        """
        if not self.config.enabled:
            logger.info("[Watchdog] 看门狗已禁用，跳过启动")
            return

        if self._running:
            logger.debug("[Watchdog] 看门狗已在运行")
            return

        self._running = True
        self._paused = False
        self._task = asyncio.create_task(self._monitor_loop(), name="browser_watchdog")
        logger.info(
            f"[Watchdog] 浏览器监控已启动 "
            f"(心跳间隔: {self.config.heartbeat_interval_sec}s)"
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
            f"[Watchdog] 浏览器监控已停止 "
            f"(总恢复: {self._stats.total_recoveries}, "
            f"成功: {self._stats.successful_recoveries}, "
            f"失败: {self._stats.failed_recoveries})"
        )

    def pause(self) -> None:
        """暂停监控(用于执行关键操作时临时暂停)."""
        self._paused = True
        logger.debug("[Watchdog] 监控已暂停")

    def resume(self) -> None:
        """恢复监控."""
        self._paused = False
        logger.debug("[Watchdog] 监控已恢复")

    async def _monitor_loop(self) -> None:
        """监控主循环."""
        while self._running:
            try:
                # 暂停时跳过检查
                if self._paused:
                    await asyncio.sleep(self.config.heartbeat_interval_sec)
                    continue

                # 执行健康检查
                health_result = await self.check_health()

                # 触发健康检查回调
                if self.on_health_check:
                    try:
                        await self.on_health_check(health_result)
                    except Exception as e:
                        logger.warning(f"[Watchdog] 健康检查回调执行失败: {e}")

                # 如果不健康，尝试恢复
                if not health_result.is_healthy:
                    logger.warning(
                        f"[Watchdog] 检测到浏览器异常: {health_result.message}"
                    )

                    recovery_success = await self.recover()

                    if recovery_success:
                        self._stats.consecutive_failures = 0
                        if self.on_recovery_success:
                            try:
                                await self.on_recovery_success()
                            except Exception as e:
                                logger.warning(f"[Watchdog] 恢复成功回调执行失败: {e}")
                    else:
                        self._stats.consecutive_failures += 1
                        if self.on_recovery_failed:
                            try:
                                await self.on_recovery_failed(
                                    Exception(f"恢复失败: {health_result.message}")
                                )
                            except Exception as e:
                                logger.warning(f"[Watchdog] 恢复失败回调执行失败: {e}")

                        # 检查是否超过最大连续失败次数
                        if (
                            self._stats.consecutive_failures
                            >= self.config.max_consecutive_failures
                        ):
                            logger.error(
                                f"[Watchdog] 连续失败次数达到上限 "
                                f"({self.config.max_consecutive_failures})，停止监控"
                            )
                            break
                else:
                    # 健康时重置连续失败计数
                    self._stats.consecutive_failures = 0

                # 等待下一次检查
                await asyncio.sleep(self.config.heartbeat_interval_sec)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Watchdog] 监控循环异常: {e}")
                await asyncio.sleep(self.config.heartbeat_interval_sec)

    async def check_health(self) -> WatchdogHealthResult:
        """执行浏览器健康检查.

        Returns:
            健康检查结果
        """
        details: dict[str, Any] = {}

        try:
            # 1. 基本对象检查
            if not self.browser_manager.playwright:
                return WatchdogHealthResult(
                    is_healthy=False,
                    level=RecoveryLevel.RESTART_BROWSER,
                    message="Playwright 未初始化",
                    details={"check": "playwright_init"},
                )

            if not self.browser_manager.browser:
                return WatchdogHealthResult(
                    is_healthy=False,
                    level=RecoveryLevel.RESTART_BROWSER,
                    message="浏览器未启动",
                    details={"check": "browser_init"},
                )

            if not self.browser_manager.context:
                return WatchdogHealthResult(
                    is_healthy=False,
                    level=RecoveryLevel.NEW_CONTEXT,
                    message="浏览器上下文不存在",
                    details={"check": "context_init"},
                )

            if not self.browser_manager.page:
                return WatchdogHealthResult(
                    is_healthy=False,
                    level=RecoveryLevel.NEW_PAGE,
                    message="页面不存在",
                    details={"check": "page_init"},
                )

            # 2. 连接状态检查
            if not self.browser_manager.browser.is_connected():
                return WatchdogHealthResult(
                    is_healthy=False,
                    level=RecoveryLevel.RESTART_BROWSER,
                    message="浏览器连接已断开",
                    details={"check": "browser_connected"},
                )

            # 3. 页面响应检查(带超时)
            try:
                result = await asyncio.wait_for(
                    self.browser_manager.page.evaluate("() => document.readyState"),
                    timeout=self.config.page_response_timeout_sec,
                )
                details["page_ready_state"] = result

                if result not in ("complete", "interactive", "loading"):
                    return WatchdogHealthResult(
                        is_healthy=False,
                        level=RecoveryLevel.REFRESH_PAGE,
                        message=f"页面状态异常: {result}",
                        details={"check": "page_state", "state": result},
                    )
            except asyncio.TimeoutError:
                return WatchdogHealthResult(
                    is_healthy=False,
                    level=RecoveryLevel.NEW_PAGE,
                    message="页面响应超时",
                    details={
                        "check": "page_response",
                        "timeout": self.config.page_response_timeout_sec,
                    },
                )
            except Exception as e:
                # 页面可能已关闭或崩溃
                return WatchdogHealthResult(
                    is_healthy=False,
                    level=RecoveryLevel.NEW_PAGE,
                    message=f"页面响应异常: {e}",
                    details={"check": "page_response", "error": str(e)},
                )

            # 4. 上下文页面数检查
            try:
                pages = self.browser_manager.context.pages
                details["page_count"] = len(pages)

                if not pages:
                    return WatchdogHealthResult(
                        is_healthy=False,
                        level=RecoveryLevel.NEW_PAGE,
                        message="无活跃页面",
                        details={"check": "page_count"},
                    )
            except Exception as e:
                return WatchdogHealthResult(
                    is_healthy=False,
                    level=RecoveryLevel.NEW_CONTEXT,
                    message=f"上下文检查异常: {e}",
                    details={"check": "context_pages", "error": str(e)},
                )

            # 所有检查通过
            return WatchdogHealthResult(
                is_healthy=True,
                level=0,
                message="浏览器健康",
                details=details,
            )

        except Exception as e:
            return WatchdogHealthResult(
                is_healthy=False,
                level=RecoveryLevel.RESTART_BROWSER,
                message=f"健康检查异常: {e}",
                details={"check": "unknown", "error": str(e)},
            )

    async def recover(self) -> bool:
        """执行分级恢复策略.

        Returns:
            是否恢复成功
        """
        self._stats.total_recoveries += 1
        self._stats.last_recovery_time = datetime.now()

        # 按级别依次尝试恢复
        for level in RecoveryLevel:
            logger.info(f"[Watchdog] 尝试恢复策略: {level.name} (级别 {level.value})")
            self._stats.last_recovery_level = level

            for attempt in range(self.config.max_recovery_attempts):
                try:
                    success = await self._execute_recovery(level)
                    if success:
                        # 验证恢复结果
                        await asyncio.sleep(1)  # 等待稳定
                        health = await self.check_health()

                        if health.is_healthy:
                            self._stats.successful_recoveries += 1
                            logger.success(
                                f"[Watchdog] 恢复成功: {level.name} "
                                f"(尝试 {attempt + 1}/{self.config.max_recovery_attempts})"
                            )
                            return True

                except Exception as e:
                    logger.warning(
                        f"[Watchdog] 恢复尝试 {attempt + 1} 失败: {e}"
                    )

                # 重试前等待
                if attempt < self.config.max_recovery_attempts - 1:
                    await asyncio.sleep(2)

            logger.warning(f"[Watchdog] 恢复策略 {level.name} 失败，尝试下一级")

        self._stats.failed_recoveries += 1
        logger.error("[Watchdog] 所有恢复策略均已失败")
        return False

    async def _execute_recovery(self, level: RecoveryLevel) -> bool:
        """执行特定级别的恢复.

        Args:
            level: 恢复级别

        Returns:
            是否执行成功(不代表恢复成功，需要后续验证)
        """
        try:
            if level == RecoveryLevel.REFRESH_PAGE:
                if self.browser_manager.page:
                    await self.browser_manager.page.reload(wait_until="domcontentloaded")
                    logger.info("[Watchdog] 已刷新页面")
                    return True
                return False

            elif level == RecoveryLevel.NEW_PAGE:
                if self.browser_manager.context:
                    old_page = self.browser_manager.page
                    self.browser_manager.page = await self.browser_manager.context.new_page()
                    # 应用智能等待补丁
                    self.browser_manager._patch_page_wait(self.browser_manager.page)
                    if old_page:
                        try:
                            await old_page.close()
                        except Exception:
                            pass
                    logger.info("[Watchdog] 已创建新页面")
                    return True
                return False

            elif level == RecoveryLevel.NEW_CONTEXT:
                if self.browser_manager.browser:
                    # 尝试保存 cookies
                    cookies = []
                    if self.browser_manager.context:
                        try:
                            cookies = await self.browser_manager.context.cookies()
                        except Exception:
                            pass
                        try:
                            await self.browser_manager.context.close()
                        except Exception:
                            pass

                    # 创建新上下文
                    self.browser_manager.context = (
                        await self.browser_manager.browser.new_context()
                    )
                    if cookies:
                        await self.browser_manager.context.add_cookies(cookies)

                    # 创建新页面
                    self.browser_manager.page = await self.browser_manager.context.new_page()
                    self.browser_manager._patch_page_wait(self.browser_manager.page)
                    logger.info("[Watchdog] 已创建新上下文和页面")
                    return True
                return False

            elif level == RecoveryLevel.RESTART_BROWSER:
                # 保存 storage state
                await self.browser_manager.save_storage_state()
                # 关闭并重启
                await self.browser_manager.close(save_state=True)
                await self.browser_manager.start()
                logger.info("[Watchdog] 已重启浏览器")
                return True

            elif level == RecoveryLevel.FULL_RELOGIN:
                if not self.config.enable_auto_relogin:
                    logger.warning("[Watchdog] 自动重登已禁用，跳过")
                    return False

                if not self.login_controller:
                    logger.warning("[Watchdog] 未提供登录控制器，无法重登")
                    return False

                # 完全重新登录
                await self.browser_manager.close(save_state=False)
                success = await self.login_controller.login(keep_browser_open=True)
                if success:
                    logger.info("[Watchdog] 已完成重新登录")
                return success

            return False

        except Exception as e:
            logger.error(f"[Watchdog] 执行恢复 {level.name} 时出错: {e}")
            return False

    async def force_recovery(self, level: RecoveryLevel | None = None) -> bool:
        """强制执行恢复(手动触发).

        Args:
            level: 指定恢复级别，为 None 则执行完整恢复流程

        Returns:
            是否恢复成功
        """
        if level is not None:
            logger.info(f"[Watchdog] 强制执行恢复: {level.name}")
            success = await self._execute_recovery(level)
            if success:
                await asyncio.sleep(1)
                health = await self.check_health()
                return health.is_healthy
            return False
        else:
            return await self.recover()


# 便捷工厂函数
def create_watchdog(
    browser_manager: "BrowserManager",
    login_controller: "LoginController | None" = None,
    **config_kwargs,
) -> BrowserWatchdog:
    """创建浏览器看门狗实例.

    Args:
        browser_manager: 浏览器管理器
        login_controller: 登录控制器(可选)
        **config_kwargs: 配置参数

    Returns:
        BrowserWatchdog 实例
    """
    config = WatchdogConfig(**config_kwargs)
    return BrowserWatchdog(
        browser_manager=browser_manager,
        login_controller=login_controller,
        config=config,
    )


# 导出
__all__ = [
    "BrowserWatchdog",
    "RecoveryLevel",
    "RecoveryStats",
    "WatchdogConfig",
    "WatchdogHealthResult",
    "create_watchdog",
]
