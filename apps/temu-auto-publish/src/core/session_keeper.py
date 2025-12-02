"""
@PURPOSE: 定时刷新登录态，防止 24 小时运行时会话过期
@OUTLINE:
  - class SessionKeeper: 会话保活管理器
    - async def start(): 启动后台刷新任务
    - async def stop(): 停止刷新任务
    - async def _refresh_loop(): 后台循环刷新登录态
    - async def _refresh_session(): 执行会话刷新
    - async def _validate_session(): 验证会话有效性
@GOTCHAS:
  - 刷新间隔默认 30 分钟，可根据实际会话过期时间调整
  - 刷新失败时会尝试重新登录
  - 需要在工作流结束时显式调用 stop() 停止任务
@DEPENDENCIES:
  - 内部: browser_manager, login_controller
  - 外部: asyncio, loguru
@RELATED: browser_watchdog.py, login_controller.py
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from ..browser.browser_manager import BrowserManager
    from ..browser.login_controller import LoginController


@dataclass
class SessionKeeperConfig:
    """会话保活配置.

    Attributes:
        enabled: 是否启用
        refresh_interval_minutes: 刷新间隔(分钟)
        refresh_timeout_sec: 单次刷新超时(秒)
        max_refresh_failures: 最大连续刷新失败次数
        relogin_on_failure: 刷新失败时是否自动重新登录
    """

    enabled: bool = True
    refresh_interval_minutes: int = 30
    refresh_timeout_sec: int = 30
    max_refresh_failures: int = 3
    relogin_on_failure: bool = True


@dataclass
class SessionStats:
    """会话统计信息.

    Attributes:
        total_refreshes: 总刷新次数
        successful_refreshes: 成功刷新次数
        failed_refreshes: 失败刷新次数
        relogin_count: 重新登录次数
        last_refresh_time: 最后刷新时间
        consecutive_failures: 连续失败次数
    """

    total_refreshes: int = 0
    successful_refreshes: int = 0
    failed_refreshes: int = 0
    relogin_count: int = 0
    last_refresh_time: datetime | None = None
    consecutive_failures: int = 0


class SessionKeeper:
    """会话保活管理器 - 定时刷新登录态防止过期.

    功能:
    1. 后台定时刷新会话
    2. 刷新失败时自动重新登录
    3. 保存更新后的 Cookie/Storage State
    4. 支持暂停/恢复

    Examples:
        >>> keeper = SessionKeeper(
        ...     browser_manager=browser_manager,
        ...     login_controller=login_controller,
        ... )
        >>> await keeper.start()
        >>> # ... 工作流执行 ...
        >>> await keeper.stop()
    """

    # 默认的会话刷新 URL（妙手 ERP 用户信息接口）
    DEFAULT_REFRESH_URL = "https://erp.91miaoshou.com/api/user/info"

    def __init__(
        self,
        browser_manager: BrowserManager,
        login_controller: LoginController,
        config: SessionKeeperConfig | None = None,
        refresh_url: str | None = None,
    ):
        """初始化会话保活管理器.

        Args:
            browser_manager: 浏览器管理器实例
            login_controller: 登录控制器实例
            config: 配置对象
            refresh_url: 用于刷新会话的 URL（可选）
        """
        self._browser_manager = browser_manager
        self._login_controller = login_controller
        self.config = config or SessionKeeperConfig()
        self._refresh_url = refresh_url or self.DEFAULT_REFRESH_URL

        self._running = False
        self._paused = False
        self._task: asyncio.Task | None = None
        self._stats = SessionStats()

    @property
    def is_running(self) -> bool:
        """是否正在运行."""
        return self._running

    @property
    def stats(self) -> SessionStats:
        """获取统计信息."""
        return self._stats

    async def start(self) -> None:
        """启动后台刷新任务(非阻塞)."""
        if not self.config.enabled:
            logger.info("[SessionKeeper] 会话保活已禁用，跳过启动")
            return

        if self._running:
            logger.debug("[SessionKeeper] 已在运行")
            return

        self._running = True
        self._paused = False
        self._task = asyncio.create_task(self._refresh_loop(), name="session_keeper")
        logger.info(
            f"[SessionKeeper] 会话保活已启动 (刷新间隔: {self.config.refresh_interval_minutes}分钟)"
        )

    async def stop(self) -> None:
        """停止刷新任务."""
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info(
            f"[SessionKeeper] 会话保活已停止 "
            f"(总刷新: {self._stats.total_refreshes}, "
            f"成功: {self._stats.successful_refreshes}, "
            f"失败: {self._stats.failed_refreshes}, "
            f"重登: {self._stats.relogin_count})"
        )

    def pause(self) -> None:
        """暂停刷新（用于执行关键操作时）."""
        self._paused = True
        logger.debug("[SessionKeeper] 刷新已暂停")

    def resume(self) -> None:
        """恢复刷新."""
        self._paused = False
        logger.debug("[SessionKeeper] 刷新已恢复")

    async def _refresh_loop(self) -> None:
        """后台循环刷新登录态."""
        interval_sec = self.config.refresh_interval_minutes * 60

        while self._running:
            try:
                # 等待刷新间隔
                await asyncio.sleep(interval_sec)

                # 暂停时跳过
                if self._paused:
                    continue

                # 执行刷新
                success = await self._refresh_session()

                if success:
                    self._stats.successful_refreshes += 1
                    self._stats.consecutive_failures = 0
                    self._stats.last_refresh_time = datetime.now()
                    logger.info("[SessionKeeper] 登录态已刷新")
                else:
                    self._stats.failed_refreshes += 1
                    self._stats.consecutive_failures += 1
                    logger.warning(
                        f"[SessionKeeper] 登录态刷新失败 "
                        f"(连续失败: {self._stats.consecutive_failures})"
                    )

                    # 检查是否需要重新登录
                    if (
                        self.config.relogin_on_failure
                        and self._stats.consecutive_failures >= self.config.max_refresh_failures
                    ):
                        logger.warning("[SessionKeeper] 连续刷新失败，尝试重新登录")
                        await self._attempt_relogin()

                self._stats.total_refreshes += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SessionKeeper] 刷新循环异常: {e}")
                await asyncio.sleep(60)  # 异常后等待 1 分钟再重试

    async def _refresh_session(self) -> bool:
        """执行会话刷新.

        Returns:
            是否刷新成功
        """
        try:
            page = self._browser_manager.page
            if not page:
                logger.warning("[SessionKeeper] 页面不存在，无法刷新会话")
                return False

            # 保存当前 URL
            current_url = page.url

            # 访问刷新 URL（带超时）
            try:
                async with asyncio.timeout(self.config.refresh_timeout_sec):
                    response = await page.goto(
                        self._refresh_url,
                        wait_until="domcontentloaded",
                    )

                    # 检查响应状态
                    if response and response.status == 200:
                        # 验证会话有效性
                        is_valid = await self._validate_session()

                        if is_valid:
                            # 保存更新后的 Cookie
                            await self._browser_manager.save_storage_state()

                            # 返回原页面
                            if current_url and current_url != self._refresh_url:
                                await page.goto(current_url, wait_until="domcontentloaded")

                            return True

                    logger.warning(
                        f"[SessionKeeper] 刷新响应异常: "
                        f"status={response.status if response else 'None'}"
                    )
                    return False

            except TimeoutError:
                logger.warning("[SessionKeeper] 刷新请求超时")
                return False

        except Exception as e:
            logger.error(f"[SessionKeeper] 刷新会话异常: {e}")
            return False

    async def _validate_session(self) -> bool:
        """验证会话有效性.

        检测多种会话过期场景：
        1. URL 重定向到登录页（包含 login 关键字）
        2. URL 包含 ?redirect= 参数（会话过期重定向）
        3. API 返回 401 错误码
        4. 页面包含登录表单

        Returns:
            会话是否有效
        """
        try:
            page = self._browser_manager.page
            if not page:
                return False

            url = page.url.lower()

            # 场景1: 检查是否被重定向到登录页
            if "login" in url and "api" not in url:
                logger.warning("[SessionKeeper] 检测到会话已过期（重定向到登录页）")
                return False

            # 场景2: 检查 URL 是否包含 ?redirect= 参数（会话过期重定向）
            # 例如: https://erp.91miaoshou.com/?redirect=%2Fcommon_collect_box%2Fitems
            if "redirect=" in url or "redirect%3d" in url:
                from urllib.parse import urlparse

                parsed = urlparse(url)
                # 路径为空或为根路径，且有 redirect 参数，说明被重定向到登录页
                if parsed.path in ("", "/") or "sub_account" in parsed.path:
                    logger.warning(f"[SessionKeeper] 检测到会话已过期（redirect参数重定向）: {url}")
                    return False

            # 场景3: 检查响应内容是否包含错误标识
            content = await page.content()
            if '"code":401' in content or '"code": 401' in content:
                logger.warning("[SessionKeeper] 检测到会话已过期（401 响应）")
                return False

            # 场景4: 检查页面是否包含登录表单（会话过期但 URL 未变化的情况）
            try:
                login_form_count = await page.locator(
                    "input[name='mobile'], input[name='username'], "
                    "input[placeholder*='手机'], input[placeholder*='账号']"
                ).count()
                if login_form_count > 0:
                    login_btn_count = await page.locator(
                        "button:has-text('登录'), button:has-text('立即登录')"
                    ).count()
                    if login_btn_count > 0:
                        logger.warning("[SessionKeeper] 检测到会话已过期（页面显示登录表单）")
                        return False
            except Exception:
                pass  # 元素检测失败不影响整体判断

            return True

        except Exception as e:
            logger.warning(f"[SessionKeeper] 验证会话异常: {e}")
            return False

    async def _attempt_relogin(self) -> bool:
        """尝试重新登录.

        Returns:
            是否登录成功
        """
        try:
            logger.info("[SessionKeeper] 开始重新登录...")

            # 调用登录控制器的 ensure_logged_in 方法
            if hasattr(self._login_controller, "ensure_logged_in"):
                success = await self._login_controller.ensure_logged_in()
            else:
                # 回退到完整登录流程
                success = await self._login_controller.login(keep_browser_open=True)

            if success:
                self._stats.relogin_count += 1
                self._stats.consecutive_failures = 0
                logger.success("[SessionKeeper] 重新登录成功")
                return True
            else:
                logger.error("[SessionKeeper] 重新登录失败")
                return False

        except Exception as e:
            logger.error(f"[SessionKeeper] 重新登录异常: {e}")
            return False

    async def force_refresh(self) -> bool:
        """强制立即刷新会话（手动触发）.

        Returns:
            是否刷新成功
        """
        logger.info("[SessionKeeper] 强制刷新会话")
        return await self._refresh_session()


# 便捷工厂函数
def create_session_keeper(
    browser_manager: BrowserManager,
    login_controller: LoginController,
    **config_kwargs,
) -> SessionKeeper:
    """创建会话保活管理器实例.

    Args:
        browser_manager: 浏览器管理器
        login_controller: 登录控制器
        **config_kwargs: 配置参数

    Returns:
        SessionKeeper 实例
    """
    config = SessionKeeperConfig(**config_kwargs)
    return SessionKeeper(
        browser_manager=browser_manager,
        login_controller=login_controller,
        config=config,
    )


# 导出
__all__ = [
    "SessionKeeper",
    "SessionKeeperConfig",
    "SessionStats",
    "create_session_keeper",
]
