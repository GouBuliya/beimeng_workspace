"""
@PURPOSE: 登录控制器，使用Playwright自动化登录妙手ERP系统
@OUTLINE:
  - class LoginController: 登录控制器主类
  - async def login(): 执行登录流程
  - async def login_if_needed(): 如果需要则登录（检查状态后按需登录）
  - async def _check_login_status(): 检查登录状态（私有方法）
@GOTCHAS:
  - 使用aria-ref定位元素（妙手ERP特有）
  - 优先使用Cookie登录，失效后才执行完整登录
  - Cookie有效期24小时
@DEPENDENCIES:
  - 内部: .browser_manager, .cookie_manager
  - 外部: playwright
@RELATED: browser_manager.py, cookie_manager.py, miaoshou_controller.py
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from .browser_manager import BrowserManager
from .cookie_manager import CookieManager
from ..utils.selector_race import TIMEOUTS


class LoginController:
    """登录控制器.

    管理妙手ERP登录流程，包括 Cookie 管理和自动化登录。

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
            selector_path: 选择器配置文件路径（默认使用v2文本定位器版本）
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
        """检查浏览器是否仍然有效。

        Returns:
            True 如果浏览器有效且可用
        """
        try:
            # 检查基本对象是否存在
            if not self.browser_manager.browser:
                return False
            if not self.browser_manager.page:
                return False
            if not self.browser_manager.playwright:
                return False

            # 尝试执行一个简单操作来验证连接是否有效
            # 使用 evaluate 检查页面是否响应
            await self.browser_manager.page.evaluate("() => true")
            return True
        except Exception as e:
            logger.debug(f"浏览器有效性检查失败: {e}")
            return False

    async def _cleanup_browser(self) -> None:
        """清理失效的浏览器资源。"""
        try:
            if self.browser_manager.page:
                try:
                    await self.browser_manager.page.close()
                except Exception:
                    pass
                self.browser_manager.page = None

            if self.browser_manager.context:
                try:
                    await self.browser_manager.context.close()
                except Exception:
                    pass
                self.browser_manager.context = None

            if self.browser_manager.browser:
                try:
                    await self.browser_manager.browser.close()
                except Exception:
                    pass
                self.browser_manager.browser = None

            if self.browser_manager.playwright:
                try:
                    await self.browser_manager.playwright.stop()
                except Exception:
                    pass
                self.browser_manager.playwright = None

            logger.debug("已清理失效的浏览器资源")
        except Exception as e:
            logger.debug(f"清理浏览器资源时出错: {e}")

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
            force: 强制重新登录（忽略 Cookie）
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

        # 1. 检查 Cookie
        if not force and self.cookie_manager.is_valid():
            logger.success("✓ Cookie 有效，尝试使用 Cookie 登录")

            # 启动浏览器并加载 Cookie
            await self.browser_manager.start(headless=headless)

            cookie_file = "data/temp/miaoshou_cookies.json"
            if await self.browser_manager.load_cookies(cookie_file):
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
                        timeout=3000
                    )
                except Exception:
                    pass  # 即使超时也继续检查登录状态

                # 检查是否已登录
                if await self._check_login_status():
                    logger.success("✓ Cookie 登录成功")
                    return True
                else:
                    logger.warning("Cookie 已失效，需要重新登录")
                    self.cookie_manager.clear()

        # 2. 执行自动化登录
        logger.info("开始自动化登录妙手ERP...")

        try:
            # 启动浏览器（如果未启动或已失效）
            browser_valid = await self._is_browser_valid()
            if not browser_valid:
                logger.info("浏览器未启动或已失效，正在重新启动...")
                # 清理旧的浏览器资源
                await self._cleanup_browser()
                await self.browser_manager.start(headless=headless)

            page = self.browser_manager.page

            # 导航到登录页
            login_config = self.selectors.get("login", {})
            login_url = login_config.get("url", "https://erp.91miaoshou.com/sub_account/users")
            logger.info(f"导航到登录页: {login_url}")
            await page.goto(login_url, timeout=60000)
            await page.wait_for_load_state("domcontentloaded")

            # 使用文本定位器（更稳定）
            username_selector = login_config.get("username_input", "input[type='text']")
            password_selector = login_config.get("password_input", "input[type='password']")
            login_btn_selector = login_config.get("login_button", "button:has-text('登录')")

            # 等待登录表单加载
            await page.wait_for_selector(username_selector, timeout=10000)

            # 输入用户名 (激进优化: 移除固定等待，输入即时生效)
            logger.debug("输入用户名...")
            await page.locator(username_selector).fill(username)

            # 输入密码 (激进优化: 移除固定等待)
            logger.debug("输入密码...")
            await page.locator(password_selector).fill(password)

            # 点击登录按钮
            logger.debug("点击登录按钮...")
            await page.locator(login_btn_selector).click()

            # 等待登录结果（跳转到首页或显示错误）
            logger.info("等待登录结果...")

            try:
                # 等待跳转到首页或弹窗消失 (激进优化: 15s -> 8s)
                await page.wait_for_url("**/erp.91miaoshou.com/welcome**", timeout=8000)
                logger.success("✓ 已跳转到首页")
            except Exception as e:
                logger.debug(f"未能等待到URL变化: {e}")
                # 激进优化: 条件等待替代固定2秒等待
                try:
                    await page.wait_for_selector(
                        ".jx-main, .pro-layout, .el-message--error, [class*='error']",
                        state="visible",
                        timeout=2000
                    )
                except Exception:
                    pass

            # 验证登录状态
            if await self._check_login_status():
                logger.success("✓ 登录成功")

                # 保存 Cookie
                await self.browser_manager.save_cookies("data/temp/miaoshou_cookies.json")
                logger.debug("✓ Cookie 已保存")

                await self._dismiss_overlays_if_any()

                return True
            else:
                logger.error("✗ 登录失败")

                # 截图保存错误状态
                screenshot_path = f"data/temp/screenshots/login_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.browser_manager.screenshot(screenshot_path)
                logger.info(f"错误截图已保存: {screenshot_path}")

                return False

        except Exception as e:
            logger.error(f"登录过程出错: {e}")

            # 截图保存错误状态
            try:
                screenshot_path = f"data/temp/screenshots/login_exception_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await self.browser_manager.screenshot(screenshot_path)
                logger.info(f"异常截图已保存: {screenshot_path}")
            except:
                pass

            return False

        finally:
            # 如果是 headless 模式，关闭浏览器
            if headless and not keep_browser_open:
                await self.browser_manager.close()

    async def ensure_collect_box_ready(self, target_url: str) -> None:
        """登录后跳转到指定采集箱，并清理弹窗/新手教程."""

        page = self.browser_manager.page
        if not page:
            raise RuntimeError("浏览器页面未初始化，无法导航到采集箱")

        logger.info("导航到采集箱页面: {}", target_url)
        await page.goto(target_url, timeout=60_000)
        await page.wait_for_load_state("domcontentloaded")
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
        """登录后尝试关闭广告或提示弹窗.

        Args:
            skip_health: True 时跳过“店铺健康功能迁移”弹窗，由调用方单独处理。
        """

        page = self.browser_manager.page
        if not page:
            return

        # 登录后优先尝试关闭已知弹窗（录制的稳定选择器）
        try:
            quick_close = page.locator(
                "body > div:nth-child(27) > div > div > header > button"
            ).first
            if await quick_close.count() and await quick_close.is_visible(timeout=500):
                await quick_close.click(timeout=TIMEOUTS.NORMAL)
                logger.info("✓ 快速关闭登录后弹窗 (nth-child(27) header button)")
        except Exception as exc:  # pragma: no cover - 运行时保护
            logger.debug("快速关闭登录后弹窗失败: {}", exc)

        if not skip_health:
            # 首先处理"店铺健康功能迁移"弹窗 - 使用精确定位
            await self._dismiss_health_migration_popup(page)

        overlay_selector = ".jx-overlay-dialog, .el-dialog, .pro-dialog, [role='dialog']"
        close_selectors = [
            "button:has-text('我已知晓')",
            "button:has-text('关闭')",
            "button:has-text('我知道了')",
            "button:has-text('知道了')",
            "button:has-text('确定')",
            ".jx-dialog__headerbtn",
            ".el-dialog__headerbtn",
            "button[aria-label='关闭']",
            "button[aria-label='Close']",
            ".pro-dialog__close",
            ".pro-dialog__header button",
            ".dialog-close",
            "[class*='icon-close']",
            "button:has-text('关闭广告')",
            "button:has-text('立即进入')",
        ]

        if skip_health:
            close_selectors = [
                selector
                for selector in close_selectors
                if "我已知晓" not in selector
            ]

        for attempt in range(5):
            dialogs = page.locator(overlay_selector)
            dialog_count = await dialogs.count()
            if dialog_count == 0:
                return

            logger.info("检测到登录后弹窗, 尝试关闭 (第{}次)", attempt + 1)

            closed_any = False
            for index in range(dialog_count - 1, -1, -1):
                dialog = dialogs.nth(index)
                closed_this_dialog = False
                for selector in close_selectors:
                    locator = dialog.locator(selector)
                    try:
                        if await locator.count() and await locator.first.is_visible(timeout=1000):
                            logger.debug("点击弹窗关闭控件 selector={} index={}", selector, index)
                            await locator.first.click()
                            closed_any = True
                            closed_this_dialog = True
                            break
                    except Exception as exc:  # pragma: no cover - 调试场景
                        logger.debug("关闭弹窗时忽略异常: {}", exc)
                if not closed_this_dialog:
                    try:
                        logger.debug("未找到关闭按钮, 尝试发送 Escape")
                        await page.keyboard.press("Escape")
                        closed_any = True
                        closed_this_dialog = True
                    except Exception:
                        pass

            if not closed_any:
                logger.warning("⚠️ 弹窗仍存在, 强制继续后续流程")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_dir = Path("data/debug/login_overlays")
                debug_dir.mkdir(parents=True, exist_ok=True)
                screenshot_path = debug_dir / f"overlay_{timestamp}.png"
                html_path = debug_dir / f"overlay_{timestamp}.html"
                try:
                    await page.screenshot(path=str(screenshot_path))
                    html_path.write_text(await page.content(), encoding="utf-8")
                    logger.warning("⚠️ 未能识别弹窗关闭控件, 已保存快照: {}", screenshot_path)
                except Exception as exc:
                    logger.debug("保存弹窗快照失败: {}", exc)
                break

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

            logger.info("检测到新手教程引导，尝试跳过 (第{}次)", attempt + 1)
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
                logger.warning("未能自动跳过新手教程，引导仍在")
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

    async def _dismiss_health_migration_popup(self, page) -> bool:
        """关闭'店铺健康功能迁移'等弹窗 - 点击3次'我已知晓'."""
        clicked_count = 0

        # 等待页面稳定
        await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUTS.SLOW)

        try:
            # 使用多种定位方式，点击3次处理可能出现的多个弹窗
            for attempt in range(3):
                clicked = False
                scopes = self._collect_page_scopes(page)

                # 方式1: 直接用 CSS 选择器找按钮
                selectors = [
                    "button:has-text('我已知晓')",
                    ".el-button:has-text('我已知晓')",
                    "button.el-button--primary:has-text('我已知晓')",
                    "[class*='dialog'] button:has-text('我已知晓')",
                    "footer button",
                    ".el-dialog__footer button.el-button--primary",
                ]

                for selector in selectors:
                    for scope_name, scope in scopes:
                        try:
                            locator = scope.locator(selector)
                            count = await locator.count()
                        except Exception as e:
                            logger.debug(f"选择器 {selector} 在 {scope_name} 失败: {e}")
                            continue

                        if count == 0:
                            continue

                        candidate = locator.first

                        try:
                            is_visible = await candidate.is_visible()
                        except Exception as exc:
                            logger.debug(f"检测 {selector} 可见性失败 ({scope_name}): {exc}")
                            continue

                        if not is_visible:
                            continue

                        try:
                            await candidate.click(timeout=2000)
                        except Exception as exc:
                            logger.debug(f"点击 {selector} 失败 ({scope_name}): {exc}")
                            continue

                        clicked = True
                        clicked_count += 1
                        logger.info(
                            "✓ 点击'我已知晓'按钮成功 (第%s次, selector: %s, scope: %s)",
                            attempt + 1,
                            selector,
                            scope_name,
                        )
                        break

                    if clicked:
                        break

                # 方式2: 使用 get_by_role
                if not clicked:
                    for scope_name, scope in scopes:
                        if not hasattr(scope, "get_by_role"):
                            continue
                        try:
                            btn = scope.get_by_role("button", name="我已知晓")
                            if await btn.count() > 0 and await btn.first.is_visible():
                                await btn.first.click(timeout=2000)
                                clicked = True
                                clicked_count += 1
                                logger.info(
                                    "✓ 点击'我已知晓'按钮成功 (第%s次, role定位, scope: %s)",
                                    attempt + 1,
                                    scope_name,
                                )
                                break
                        except Exception as e:
                            logger.debug(f"role定位失败({scope_name}): {e}")

                # 方式3: 使用 get_by_text
                if not clicked:
                    for scope_name, scope in scopes:
                        if not hasattr(scope, "get_by_text"):
                            continue
                        try:
                            btn = scope.get_by_text("我已知晓")
                            if await btn.count() > 0 and await btn.first.is_visible():
                                await btn.first.click(timeout=2000)
                                clicked = True
                                clicked_count += 1
                                logger.info(
                                    "✓ 点击'我已知晓'按钮成功 (第%s次, text定位, scope: %s)",
                                    attempt + 1,
                                    scope_name,
                                )
                                break
                        except Exception as e:
                            logger.debug(f"text定位失败({scope_name}): {e}")

                if not clicked:
                    logger.debug(f"第{attempt + 1}次尝试未找到'我已知晓'按钮")

            if clicked_count > 0:
                logger.info("✓ 共关闭 {} 个'我已知晓'弹窗", clicked_count)
                return True
            else:
                logger.debug("未找到'我已知晓'弹窗")
            return False
        except Exception as exc:
            logger.debug("关闭店铺健康弹窗时出错: {}", exc)
            return False

    async def _check_login_status(self) -> bool:
        """检查是否已登录妙手ERP.

        Returns:
            True 如果已登录
        """
        page = self.browser_manager.page

        try:
            # 检查页面URL
            url = page.url
            if "sub_account/users" in url or "login" in url.lower():
                logger.debug("✗ 仍在登录页面")
                return False

            # 检查是否在欢迎页面或其他后台页面
            if "welcome" in url or "common_collect_box" in url:
                logger.debug("✓ 已在后台页面")
                return True

            # 检查是否有产品菜单元素（首页特有）
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
        """如果需要则登录（检查登录状态，未登录则执行登录）.

        这个方法会：
        1. 启动浏览器（如果未启动）
        2. 检查登录状态
        3. 如果未登录，使用提供的或环境变量中的凭据执行登录

        Args:
            username: 用户名（可选，如果不提供则从环境变量读取）
            password: 密码（可选，如果不提供则从环境变量读取）

        Returns:
            True 如果已登录或登录成功

        Examples:
            >>> controller = LoginController()
            >>> await controller.login_if_needed()
            >>> # 或者显式提供凭据
            >>> await controller.login_if_needed("user", "pass")
        """
        import os

        # 1. 启动浏览器（如果未启动）
        if not self.browser_manager.browser:
            logger.info("浏览器未启动，正在启动...")
            await self.browser_manager.start()

        # 2. 检查是否已经登录
        try:
            if await self._check_login_status():
                logger.info("已登录，无需重新登录")
                return True
        except Exception as e:
            logger.debug(f"检查登录状态时出错: {e}")

        # 3. 需要登录，获取凭据
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
        logger.info(f"需要登录，使用用户名: {username}")
        return await self.login(username, password)


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test():
        controller = LoginController()

        # 测试登录（需要实际账号）
        username = "test_user"
        password = "test_pass"

        success = await controller.login(username, password, headless=False)

        if success:
            logger.success("✓ 登录测试通过")
        else:
            logger.error("✗ 登录测试失败")

    asyncio.run(test())
