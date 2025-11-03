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

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from .browser_manager import BrowserManager
from .cookie_manager import CookieManager


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

            with open(selector_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"加载选择器配置失败: {e}")
            return {}

    async def login(
        self,
        username: str,
        password: str,
        force: bool = False,
        headless: bool = False,
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
                welcome_url = self.selectors.get("homepage", {}).get("url", "https://erp.91miaoshou.com/welcome")
                await self.browser_manager.goto(welcome_url)
                await self.browser_manager.page.wait_for_timeout(2000)  # 等待页面加载

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
            # 启动浏览器（如果未启动）
            if not self.browser_manager.browser:
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

            # 输入用户名
            logger.debug("输入用户名...")
            await page.locator(username_selector).fill(username)
            await page.wait_for_timeout(500)  # 等待输入生效

            # 输入密码
            logger.debug("输入密码...")
            await page.locator(password_selector).fill(password)
            await page.wait_for_timeout(500)

            # 点击登录按钮
            logger.debug("点击登录按钮...")
            await page.locator(login_btn_selector).click()

            # 等待登录结果（跳转到首页或显示错误）
            logger.info("等待登录结果...")

            try:
                # 等待跳转到首页或弹窗消失
                await page.wait_for_url("**/erp.91miaoshou.com/welcome**", timeout=15000)
                logger.success("✓ 已跳转到首页")
            except Exception as e:
                logger.debug(f"未能等待到URL变化: {e}")
                # 可能登录失败或需要额外操作
                await page.wait_for_timeout(2000)

            # 验证登录状态
            if await self._check_login_status():
                logger.success("✓ 登录成功")

                # 保存 Cookie
                await self.browser_manager.save_cookies("data/temp/miaoshou_cookies.json")
                logger.debug("✓ Cookie 已保存")

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
            if headless:
                await self.browser_manager.close()

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
        username: Optional[str] = None,
        password: Optional[str] = None,
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
