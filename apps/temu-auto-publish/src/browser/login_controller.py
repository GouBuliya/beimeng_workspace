"""
@PURPOSE: 登录控制器,使用Playwright自动化登录妙手ERP系统
@OUTLINE:
  - class LoginController: 登录控制器主类
  - async def login(): 执行登录流程
  - async def login_if_needed(): 如果需要则登录(检查状态后按需登录)
  - async def _check_login_status(): 检查登录状态(私有方法)
@GOTCHAS:
  - 使用aria-ref定位元素(妙手ERP特有)
  - 优先使用Cookie登录,失效后才执行完整登录
  - Cookie有效期24小时
@DEPENDENCIES:
  - 内部: .browser_manager, .cookie_manager
  - 外部: playwright
@RELATED: browser_manager.py, cookie_manager.py, miaoshou_controller.py
"""

import asyncio
import contextlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from ..utils.page_load_decorator import wait_dom_loaded
from ..utils.page_waiter import PageWaiter
from ..utils.selector_race import TIMEOUTS
from .browser_manager import BrowserManager
from .cookie_manager import CookieManager


class LoginController:
    """登录控制器.

    管理妙手ERP登录流程,包括 Cookie 管理和自动化登录.

    Attributes:
        browser_manager: 浏览器管理器
        cookie_manager: Cookie 管理器
        selectors: 妙手ERP选择器配置

    Examples:
        >>> controller = LoginController()
        >>> success = await controller.login("username", "password")
    """

    def __init__(
        self,
        config_path: str = "config/browser_config.json",
        selector_path: str = "config/miaoshou_selectors_v2.json",
    ):
        """初始化控制器.

        Args:
            config_path: 浏览器配置文件路径
            selector_path: 选择器配置文件路径(默认使用v2文本定位器版本)
        """
        self.browser_manager = BrowserManager(config_path)
        self.cookie_manager = CookieManager()
        self.config_path = Path(config_path)
        self.selector_path = Path(selector_path)
        self.selectors = self._load_selectors()

    def _load_selectors(self) -> dict:
        """加载选择器配置.

        Returns:
            选择器配置字典
        """
        try:
            # 尝试相对于当前文件的路径
            if not self.selector_path.is_absolute():
                # 获取项目根目录
                current_file = Path(__file__)
                project_root = current_file.parent.parent.parent
                selector_file = project_root / self.selector_path
            else:
                selector_file = self.selector_path

            with open(selector_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载选择器配置失败: {e}")
            return {}

    async def _is_browser_valid(self) -> bool:
        """检查浏览器是否仍然有效且可响应.

        执行多层检查:
        1. 对象存在性检查
        2. 浏览器连接状态检查
        3. 页面响应检查(带超时)
        4. 上下文活跃性检查

        Returns:
            True 如果浏览器有效且可响应
        """
        try:
            # 1. 基本对象存在性检查
            if not all(
                [
                    self.browser_manager.playwright,
                    self.browser_manager.browser,
                    self.browser_manager.context,
                    self.browser_manager.page,
                ]
            ):
                logger.debug("浏览器对象不完整")
                return False

            # 2. 浏览器连接状态检查
            if not self.browser_manager.browser.is_connected():
                logger.debug("浏览器已断开连接")
                return False

            # 3. 页面响应检查(带超时)
            try:
                result = await asyncio.wait_for(
                    self.browser_manager.page.evaluate("() => document.readyState"), timeout=5.0
                )
                if result not in ("complete", "interactive", "loading"):
                    logger.debug(f"页面状态异常: {result}")
                    return False
            except TimeoutError:
                logger.debug("页面响应超时 (5s)")
                return False

            # 4. 上下文活跃性检查
            try:
                pages = self.browser_manager.context.pages
                if not pages:
                    logger.debug("上下文中没有活跃页面")
                    return False
            except Exception:
                logger.debug("获取上下文页面列表失败")
                return False

            return True

        except Exception as e:
            logger.debug(f"浏览器有效性检查异常: {type(e).__name__}: {e}")
            return False

    async def _cleanup_browser(self) -> dict[str, bool]:
        """清理失效的浏览器资源,返回清理结果.

        每个资源独立清理,带超时控制,确保即使某个资源清理失败也不影响其他资源.

        Returns:
            清理结果字典,格式: {"page": True/False, "context": True/False, ...}
        """
        cleanup_results = {
            "page_waiter": False,
            "page": False,
            "context": False,
            "browser": False,
            "playwright": False,
        }

        async def safe_close(
            resource: Any, name: str, close_method: str = "close", timeout: float = 5.0
        ) -> bool:
            """安全关闭资源,带超时和异常处理."""
            if resource is None:
                return True  # 资源不存在视为成功

            try:
                method = getattr(resource, close_method, None)
                if method is None:
                    logger.debug(f"{name} 没有 {close_method} 方法")
                    return False

                await asyncio.wait_for(method(), timeout=timeout)
                return True
            except TimeoutError:
                logger.warning(f"{name}.{close_method}() 超时 ({timeout}s)")
                return False
            except Exception as e:
                logger.debug(f"{name}.{close_method}() 失败: {type(e).__name__}: {e}")
                return False

        # 1. 清理 PageWaiter(防止内存泄漏)
        if self.browser_manager.page and hasattr(self.browser_manager.page, "_bemg_cleanup_waiter"):
            try:
                self.browser_manager.page._bemg_cleanup_waiter()
                cleanup_results["page_waiter"] = True
            except Exception:
                pass

        # 2. 关闭 Page
        cleanup_results["page"] = await safe_close(self.browser_manager.page, "page", "close", 5.0)
        self.browser_manager.page = None

        # 3. 关闭 Context
        cleanup_results["context"] = await safe_close(
            self.browser_manager.context, "context", "close", 5.0
        )
        self.browser_manager.context = None

        # 4. 关闭 Browser
        cleanup_results["browser"] = await safe_close(
            self.browser_manager.browser, "browser", "close", 10.0
        )
        self.browser_manager.browser = None

        # 5. 停止 Playwright
        cleanup_results["playwright"] = await safe_close(
            self.browser_manager.playwright, "playwright", "stop", 5.0
        )
        self.browser_manager.playwright = None

        # 记录清理结果
        success_count = sum(1 for v in cleanup_results.values() if v)
        total_count = len(cleanup_results)
        logger.info(f"浏览器资源清理完成: {success_count}/{total_count} 成功")

        if not all(cleanup_results.values()):
            failed = [k for k, v in cleanup_results.items() if not v]
            logger.debug(f"清理失败的资源: {failed}")

        return cleanup_results

    async def login(
        self,
        username: str,
        password: str,
        force: bool = False,
        headless: bool = False,
        keep_browser_open: bool = True,
    ) -> bool:
        """执行登录.

        Args:
            username: 用户名
            password: 密码
            force: 强制重新登录(忽略 Cookie)
            headless: 是否无头模式

        Returns:
            True 如果登录成功

        Examples:
            >>> controller = LoginController()
            >>> await controller.login("user", "pass")
        """
        logger.info("=" * 60)
        logger.info("开始登录流程")
        logger.info("=" * 60)

        # 0. 检查配置是否禁用 Cookie 登录
        try:
            if self.config_path.exists():
                with open(self.config_path, encoding="utf-8") as f:
                    browser_config = json.load(f)
                use_cookie_login = browser_config.get("login", {}).get("use_cookie_login", True)
                if not use_cookie_login:
                    logger.info("Cookie 登录已禁用(配置 use_cookie_login=false), 将执行手动登录")
                    force = True
        except Exception as e:
            logger.debug(f"读取 browser_config.json 失败: {e}, 使用默认行为")

        # 1. 检查 Cookie
        if not force and self.cookie_manager.is_valid():
            logger.success("✓ Cookie 有效,尝试使用 Cookie 登录")

            # 启动浏览器并加载 Cookie
            await self.browser_manager.start(headless=headless)

            # 使用 CookieManager 加载 Playwright 格式 Cookie
            cookies = self.cookie_manager.load_playwright_cookies()
            if cookies and self.browser_manager.context:
                await self.browser_manager.context.add_cookies(cookies)
                logger.debug("✓ 已加载 {} 条 Cookie", len(cookies))
                # 验证登录状态 - 直接访问首页而不是登录页
                welcome_url = self.selectors.get("homepage", {}).get(
                    "url", "https://erp.91miaoshou.com/welcome"
                )
                await self.browser_manager.goto(welcome_url)
                # 激进优化: 条件等待替代固定2秒等待
                try:
                    await self.browser_manager.page.wait_for_selector(
                        ".jx-main, .pro-layout, [class*='welcome'], [class*='dashboard']",
                        state="visible",
                        timeout=3000,
                    )
                except Exception:
                    pass  # 即使超时也继续检查登录状态

                # 检查是否已登录
                if await self._check_login_status():
                    logger.success("✓ Cookie 登录成功")
                    return True
                else:
                    logger.warning("Cookie 已失效,需要重新登录")
                    self.cookie_manager.clear()

        # 2. 执行自动化登录
        logger.info("开始自动化登录妙手ERP...")

        try:
            # 启动浏览器(如果未启动或已失效)
            browser_valid = await self._is_browser_valid()
            if not browser_valid:
                logger.info("浏览器未启动或已失效,正在重新启动...")
                # 清理旧的浏览器资源
                await self._cleanup_browser()
                await self.browser_manager.start(headless=headless)

            page = self.browser_manager.page
            if not page:
                raise RuntimeError("浏览器页面未初始化,无法执行登录")
            waiter = PageWaiter(page)

            # 导航到登录页
            login_config = self.selectors.get("login", {})
            login_url = login_config.get("url", "https://erp.91miaoshou.com/sub_account/users")
            logger.info(f"导航到登录页: {login_url}")
            await page.goto(login_url, timeout=60000)
            await wait_dom_loaded(page, context=" [login page]")

            # 使用文本定位器(更稳定)
            username_selector = login_config.get("username_input", "input[type='text']")
            password_selector = login_config.get("password_input", "input[type='password']")
            login_btn_selector = login_config.get("login_button", "button:has-text('登录')")

            # 等待登录表单并安全填充
            logger.debug("输入用户名...")
            if not await waiter.safe_fill(
                page.locator(username_selector),
                username,
                timeout_ms=TIMEOUTS.NORMAL,
                name="login.username",
            ):
                logger.error("用户名输入失败")
                return False

            logger.debug("输入密码...")
            if not await waiter.safe_fill(
                page.locator(password_selector),
                password,
                timeout_ms=TIMEOUTS.NORMAL,
                name="login.password",
            ):
                logger.error("密码输入失败")
                return False

            # 点击登录按钮
            logger.debug("点击登录按钮...")
            login_btn = page.locator(login_btn_selector).first
            try:
                await login_btn.wait_for(state="visible", timeout=TIMEOUTS.SLOW)
            except Exception as exc:
                logger.warning(f"登录按钮不可见: {exc}")
            login_clicked = await waiter.safe_click(
                login_btn,
                timeout_ms=TIMEOUTS.SLOW,
                name="login.submit",
            )
            if not login_clicked:
                logger.debug("登录按钮 safe_click 失败,尝试直接 click + Enter 兜底")
                try:
                    await login_btn.click(timeout=TIMEOUTS.SLOW)
                    login_clicked = True
                except Exception as exc:
                    logger.debug(f"直接点击失败,尝试回车提交: {exc}")
                    try:
                        await page.keyboard.press("Enter")
                        login_clicked = True
                    except Exception as exc2:
                        logger.debug(f"回车提交失败: {exc2}")
            if not login_clicked:
                logger.error("登录按钮点击失败")
                return False

            # 等待登录结果(跳转到首页或显示错误)
            logger.info("等待登录结果...")

            try:
                # 等待跳转到首页或弹窗消失
                await page.wait_for_url("**/erp.91miaoshou.com/welcome**", timeout=15000)
                logger.success("✓ 已跳转到首页")
            except Exception as e:
                logger.debug(f"未能等待到URL变化: {e}")
                # 激进优化: 条件等待替代固定2秒等待
                with contextlib.suppress(Exception):
                    await page.wait_for_selector(
                        ".jx-main, .pro-layout, .el-message--error, [class*='error']",
                        state="visible",
                        timeout=2000,
                    )

            # 验证登录状态
            if await self._check_login_status():
                logger.success("✓ 登录成功")

                # 保存 Cookie(使用 CookieManager 管理时间戳)
                cookies = await self.browser_manager.context.cookies()
                self.cookie_manager.save_playwright_cookies(cookies)
                logger.debug("✓ Cookie 已保存({} 条)", len(cookies))

                await self._dismiss_overlays_if_any(skip_health=True)

                return True
            else:
                logger.error("✗ 登录失败")

                # 截图保存错误状态
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"data/temp/screenshots/login_error_{timestamp}.png"
                await self.browser_manager.screenshot(screenshot_path)
                logger.info(f"错误截图已保存: {screenshot_path}")

                return False

        except Exception as e:
            logger.error(f"登录过程出错: {e}")

            # 截图保存错误状态
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"data/temp/screenshots/login_exception_{timestamp}.png"
                await self.browser_manager.screenshot(screenshot_path)
                logger.info(f"异常截图已保存: {screenshot_path}")
            except Exception:
                pass

            return False

        finally:
            # 如果是 headless 模式,关闭浏览器
            if headless and not keep_browser_open:
                await self.browser_manager.close()

    async def ensure_collect_box_ready(self, target_url: str) -> None:
        """登录后跳转到指定采集箱,并清理弹窗/新手教程."""

        page = self.browser_manager.page
        if not page:
            raise RuntimeError("浏览器页面未初始化,无法导航到采集箱")

        logger.info("导航到采集箱页面: {}", target_url)
        await page.goto(target_url, timeout=60_000)
        await wait_dom_loaded(page, context=" [collection box]")
        await self._dismiss_overlays_if_any()
        await self._dismiss_newbie_guide(page)

    async def dismiss_login_overlays(self) -> None:
        """对外暴露登录后弹窗关闭能力(并行处理重点弹窗与常规弹窗)."""

        page = self.browser_manager.page
        if not page:
            return

        results = await asyncio.gather(
            self._dismiss_overlays_if_any(skip_health=True),
            self._dismiss_health_migration_popup(page),
            return_exceptions=True,
        )
        for task_result in results:
            if isinstance(task_result, Exception):
                logger.debug("关闭登录弹窗子任务异常: {}", task_result)

    async def _dismiss_overlays_if_any(self, *, skip_health: bool = False) -> None:
        """登录后尝试关闭广告或提示弹窗 - 优化版.

        优化说明:
        - 快速检测弹窗存在性,无弹窗立即返回(避免无意义等待)
        - 使用并行竞速关闭,提升响应速度
        - 循环次数 5→3,减少最大等待时间
        - 移除 wait_for_dom_stable 调用
        - 移除调试快照功能

        Args:
            skip_health: True 时跳过"店铺健康功能迁移"弹窗,由调用方单独处理.
        """
        page = self.browser_manager.page
        if not page:
            return

        # 弹窗检测选择器
        overlay_selector = (
            ".jx-overlay-dialog, .el-dialog, .pro-dialog, [role='dialog'], "
            "[role='alertdialog'], .ant-modal-wrap, .ant-drawer-content-wrapper, "
            ".n-modal, .n-dialog"
        )

        # 优化: 快速检测是否存在弹窗,无弹窗立即返回
        try:
            overlay_count = await page.locator(overlay_selector).count()
            if overlay_count == 0:
                logger.debug("无弹窗,跳过关闭流程")
                return
        except Exception:
            pass

        # 关闭按钮选择器(按优先级排序)
        close_selectors = [
            # 高优先级 - 常见关闭按钮
            ".ant-modal-close",
            ".ant-drawer-close",
            ".el-dialog__headerbtn",
            "button[aria-label='关闭']",
            "button[aria-label='Close']",
            # 中优先级 - 文本按钮
            "button:has-text('关闭')",
            "button:has-text('我知道了')",
            "button:has-text('知道了')",
            "button:has-text('确定')",
            "button:has-text('关闭广告')",
            "button:has-text('立即进入')",
            "button:has-text('关闭弹窗')",
            # 低优先级 - 其他选择器
            ".jx-dialog__headerbtn",
            ".pro-dialog__close",
            ".pro-dialog__header button",
            ".dialog-close",
            "[class*='icon-close']",
            ".el-message-box__headerbtn",
            ".n-dialog__close",
            ".n-base-close",
        ]

        # 浮层关闭选择器
        floating_close_selectors = [
            ".el-message-box__headerbtn",
            ".el-notification__closeBtn",
            ".jx-message__close",
            ".ant-notification-close-icon",
            ".ant-message-notice-close",
        ]

        if not skip_health:
            # 添加"我已知晓"按钮到关闭选择器列表最前面
            close_selectors = ["button:has-text('我已知晓')", *close_selectors]

        # 优化: 减少循环次数 5 → 3
        for attempt in range(3):
            # 快速检测弹窗存在性
            try:
                overlay_count = await page.locator(overlay_selector).count()
                if overlay_count == 0:
                    logger.debug("弹窗已全部关闭")
                    return
            except Exception:
                return

            logger.info("检测到登录后弹窗 ({}个), 尝试关闭 (第{}次)", overlay_count, attempt + 1)

            # 优化: 使用并行竞速关闭
            closed = await self._try_close_overlay_race(page, close_selectors, timeout_ms=500)

            if not closed:
                # 尝试关闭浮层
                scopes = self._collect_page_scopes(page)
                closed = await self._click_first_visible(
                    scopes,
                    floating_close_selectors,
                    timeout_ms=300,
                    context="浮层/广告",
                )

            if not closed:
                # 没有可关闭的弹窗,退出循环
                logger.warning("⚠️ 弹窗仍存在但无法关闭,强制继续后续流程")
                break

        # 处理"店铺健康功能迁移"弹窗
        if not skip_health:
            await self._dismiss_health_migration_popup(page)

    async def _dismiss_newbie_guide(self, page) -> None:
        """处理新手教程/引导层."""

        guide_overlay_selectors = [
            ".novice-guide",
            ".guide-overlay",
            ".tour-guide",
            "[class*='guide-mask']",
            "[class*='tour']",
            "[id*='guide']",
        ]
        skip_button_selectors = [
            "button:has-text('跳过新手教程')",
            "button:has-text('跳过教程')",
            "button:has-text('跳过')",
            "a:has-text('跳过')",
            ".guide-skip",
            ".novice-guide__skip",
            ".introjs-skipbutton",
            ".driver-popover-close-btn",
            ".driver-close-btn",
        ]

        for attempt in range(3):
            overlay_found = False
            for selector in guide_overlay_selectors:
                locator = page.locator(selector)
                try:
                    if await locator.count() and await locator.first.is_visible(timeout=500):
                        overlay_found = True
                        break
                except Exception:
                    continue

            if not overlay_found:
                return

            logger.info("检测到新手教程引导,尝试跳过 (第{}次)", attempt + 1)
            skipped = False
            for selector in skip_button_selectors:
                locator = page.locator(selector)
                try:
                    if await locator.count() == 0:
                        continue
                    candidate = locator.first
                    if await candidate.is_visible(timeout=500):
                        await candidate.click(timeout=2_000)
                        skipped = True
                        break
                except Exception as exc:
                    logger.debug("点击跳过教程控件失败 ({}): {}", selector, exc)

            if not skipped:
                try:
                    await page.keyboard.press("Escape")
                    skipped = True
                except Exception:
                    pass

            if not skipped:
                logger.warning("未能自动跳过新手教程,引导仍在")
                break

    def _collect_page_scopes(self, page):
        """Collect main page and visible frames for popup detection."""

        if not page:
            return []

        scopes = [("page", page)]
        try:
            for idx, frame in enumerate(page.frames):
                label = frame.name or frame.url or f"frame-{idx}"
                scopes.append((f"frame[{idx}]::{label}", frame))
        except Exception as exc:
            logger.debug("枚举 frame 时出错: {}", exc)

        return scopes

    async def _try_close_overlay_race(
        self,
        page,
        close_selectors: list[str],
        timeout_ms: int = 500,
    ) -> bool:
        """并行竞速尝试关闭弹窗.

        使用 selector_race 并行检测多个关闭按钮选择器,
        第一个找到的立即点击关闭.

        Args:
            page: Playwright 页面对象
            close_selectors: 关闭按钮选择器列表
            timeout_ms: 超时时间(毫秒)

        Returns:
            True 如果成功关闭了弹窗
        """
        from ..utils.selector_race import try_selectors_race

        locator = await try_selectors_race(
            page,
            close_selectors,
            timeout_ms=timeout_ms,
            context_name="关闭弹窗",
        )

        if locator is None:
            return False

        try:
            await locator.click(timeout=timeout_ms)
            return True
        except Exception:
            return False

    async def _click_first_visible(
        self,
        scopes: list[tuple[str, Any]],
        selectors: list[str],
        *,
        timeout_ms: int = 500,  # 优化: 减少默认超时 TIMEOUTS.FAST -> 500ms
        context: str = "",
    ) -> bool:
        """在多作用域内点击首个可见元素.

        优化说明:
        - 先检测 count,为 0 直接跳过(避免无意义的超时等待)
        - 减少默认超时时间
        """
        for selector in selectors:
            for scope_name, scope in scopes:
                try:
                    locator = scope.locator(selector)
                    count = await locator.count()
                except Exception:
                    continue  # 静默跳过,减少日志噪音

                if count == 0:
                    continue

                candidate = locator.first

                try:
                    if await candidate.is_visible(timeout=timeout_ms):
                        await candidate.click(timeout=timeout_ms)
                        logger.debug(
                            "已点击{}关闭控件 selector={} scope={}",
                            context or "弹窗",
                            selector,
                            scope_name,
                        )
                        return True
                except Exception:
                    continue  # 静默跳过,减少日志噪音

        return False

    async def _dismiss_health_migration_popup(self, page) -> bool:
        """关闭'店铺健康功能迁移'等弹窗 - 优化版.

        优化说明:
        - 移除 wait_dom_loaded 调用(节省约 2.5s)
        - 使用并行竞速选择器替代串行遍历
        - 无按钮时早退出
        """
        from ..utils.selector_race import try_selectors_race

        # 精简的"我已知晓"按钮选择器
        selectors = [
            "button:has-text('我已知晓')",
            ".el-button:has-text('我已知晓')",
            "[class*='dialog'] button:has-text('我已知晓')",
        ]

        clicked_count = 0

        for attempt in range(3):
            # 使用并行竞速快速定位按钮
            btn = await try_selectors_race(
                page,
                selectors,
                timeout_ms=500,
                context_name="我已知晓按钮",
            )

            if btn is None:
                # 没有按钮,早退出
                break

            try:
                await btn.click(timeout=1000)
                clicked_count += 1
                logger.info(f"✓ 点击'我已知晓'按钮成功 (第{attempt + 1}次)")
            except Exception:
                break

        if clicked_count > 0:
            logger.info("✓ 共关闭 {} 个'我已知晓'弹窗", clicked_count)
            return True

        logger.debug("未找到'我已知晓'弹窗")
        return False

    async def _check_login_status(self) -> bool:
        """检查是否已登录妙手ERP.

        检测多种场景：
        1. URL 关键字检测（login, sub_account/users）
        2. 会话过期重定向检测（?redirect= 参数）
        3. 后台页面 URL 检测（welcome, common_collect_box）
        4. 页面元素检测（产品菜单、登录表单）

        Returns:
            True 如果已登录
        """
        page = self.browser_manager.page

        try:
            # 检查页面URL
            url = page.url
            url_lower = url.lower()

            # 场景1: 明确的登录页 URL
            if "sub_account/users" in url or "login" in url_lower:
                logger.debug("✗ 仍在登录页面")
                return False

            # 场景2: 会话过期重定向 - URL 包含 ?redirect= 参数
            # 例如: https://erp.91miaoshou.com/?redirect=%2Fcommon_collect_box%2Fitems
            if "redirect=" in url_lower or "redirect%3d" in url_lower:
                from urllib.parse import urlparse

                parsed = urlparse(url)
                # 路径为空或为根路径，且有 redirect 参数，说明被重定向到登录页
                if parsed.path in ("", "/") or "sub_account" in parsed.path:
                    logger.debug(f"✗ 检测到会话过期重定向到登录页: {url}")
                    return False

            # 场景3: 检查是否在后台页面
            if "welcome" in url or "common_collect_box" in url:
                logger.debug("✓ 已在后台页面")
                return True

            # 场景4: 检查是否有登录表单（会话过期但 URL 未变化的情况）
            try:
                login_form_count = await page.locator(
                    "input[name='mobile'], input[name='username'], "
                    "input[placeholder*='手机'], input[placeholder*='账号']"
                ).count()
                if login_form_count > 0:
                    # 检查是否同时有登录按钮
                    login_btn_count = await page.locator(
                        "button:has-text('登录'), button:has-text('立即登录')"
                    ).count()
                    if login_btn_count > 0:
                        logger.debug("✗ 检测到登录表单，会话可能已过期")
                        return False
            except Exception as e:
                logger.debug(f"检查登录表单时出错: {e}")

            # 场景5: 检查是否有产品菜单元素(首页特有)
            homepage_config = self.selectors.get("homepage", {})
            product_menu_selector = homepage_config.get("product_menu", "text='产品'")

            menu_count = await page.locator(product_menu_selector).count()
            if menu_count > 0:
                logger.debug("✓ 检测到产品菜单元素")
                return True

            return False

        except Exception as e:
            logger.debug(f"检查登录状态失败: {e}")
            return False

    async def login_if_needed(
        self,
        username: str | None = None,
        password: str | None = None,
    ) -> bool:
        """如果需要则登录(检查登录状态,未登录则执行登录).

        这个方法会:
        1. 启动浏览器(如果未启动)
        2. 检查登录状态
        3. 如果未登录,使用提供的或环境变量中的凭据执行登录

        Args:
            username: 用户名(可选,如果不提供则从环境变量读取)
            password: 密码(可选,如果不提供则从环境变量读取)

        Returns:
            True 如果已登录或登录成功

        Examples:
            >>> controller = LoginController()
            >>> await controller.login_if_needed()
            >>> # 或者显式提供凭据
            >>> await controller.login_if_needed("user", "pass")
        """
        import os

        # 1. 启动浏览器(如果未启动)
        if not self.browser_manager.browser:
            logger.info("浏览器未启动,正在启动...")
            await self.browser_manager.start()

        # 2. 检查是否已经登录
        try:
            if await self._check_login_status():
                logger.info("已登录,无需重新登录")
                return True
        except Exception as e:
            logger.debug(f"检查登录状态时出错: {e}")

        # 3. 需要登录,获取凭据
        if username is None:
            username = os.getenv("MIAOSHOU_USERNAME")
            if not username:
                logger.error("未提供用户名且环境变量 MIAOSHOU_USERNAME 未设置")
                return False

        if password is None:
            password = os.getenv("MIAOSHOU_PASSWORD")
            if not password:
                logger.error("未提供密码且环境变量 MIAOSHOU_PASSWORD 未设置")
                return False

        # 4. 执行登录
        logger.info(f"需要登录,使用用户名: {username}")
        return await self.login(username, password)


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test():
        controller = LoginController()

        # 测试登录(需要实际账号)
        username = "test_user"
        password = "test_pass"

        success = await controller.login(username, password, headless=False)

        if success:
            logger.success("✓ 登录测试通过")
        else:
            logger.error("✗ 登录测试失败")

    asyncio.run(test())
