"""
@PURPOSE: 登录控制器，使用Playwright自动化登录Temu后台
@OUTLINE:
  - class LoginController: 登录控制器主类
  - async def login(): 执行登录流程
  - async def check_login_status(): 检查登录状态
  - async def wait_for_manual_login(): 等待手动登录
  - async def ensure_logged_in(): 确保已登录状态
@GOTCHAS:
  - 优先使用Cookie登录，失效后才执行完整登录
  - 支持手动登录（扫码等）
  - Cookie有效期24小时
@DEPENDENCIES:
  - 内部: .browser_manager, .cookie_manager
  - 外部: playwright
@RELATED: browser_manager.py, cookie_manager.py
"""

from datetime import datetime
from pathlib import Path

from loguru import logger

from .browser_manager import BrowserManager
from .cookie_manager import CookieManager


class LoginController:
    """登录控制器.
    
    管理 Temu 登录流程，包括 Cookie 管理和自动化登录。
    
    Attributes:
        browser_manager: 浏览器管理器
        cookie_manager: Cookie 管理器
        
    Examples:
        >>> controller = LoginController()
        >>> success = await controller.login("username", "password")
    """

    def __init__(self, config_path: str = "config/browser_config.json"):
        """初始化控制器.
        
        Args:
            config_path: 浏览器配置文件路径
        """
        self.browser_manager = BrowserManager(config_path)
        self.cookie_manager = CookieManager()
        self.config_path = Path(config_path)

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
            
            cookie_file = "data/temp/temu_cookies.json"
            if await self.browser_manager.load_cookies(cookie_file):
                # 验证登录状态
                await self.browser_manager.goto("https://seller.temu.com/")
                
                # 检查是否已登录
                if await self._check_login_status():
                    logger.success("✓ Cookie 登录成功")
                    await self.browser_manager.close()
                    return True
                else:
                    logger.warning("Cookie 已失效，需要重新登录")
                    self.cookie_manager.clear()

        # 2. 执行自动化登录
        logger.info("开始自动化登录...")
        
        try:
            # 启动浏览器（如果未启动）
            if not self.browser_manager.browser:
                await self.browser_manager.start(headless=headless)
            
            page = self.browser_manager.page
            
            # 导航到登录页
            login_url = "https://seller.temu.com/login"
            logger.info(f"导航到登录页: {login_url}")
            await page.goto(login_url)
            
            # 等待登录表单加载
            await page.wait_for_selector('input[type="text"], input[type="email"]', timeout=10000)
            
            # 输入用户名
            logger.debug("输入用户名...")
            username_input = page.locator('input[type="text"], input[type="email"]').first
            await username_input.fill(username)
            
            # 输入密码
            logger.debug("输入密码...")
            password_input = page.locator('input[type="password"]').first
            await password_input.fill(password)
            
            # 点击登录按钮
            logger.debug("点击登录按钮...")
            login_button = page.locator('button:has-text("登录"), button:has-text("Login")').first
            await login_button.click()
            
            # 等待登录结果
            logger.info("等待登录结果...")
            
            # 检查是否需要验证码
            try:
                captcha = page.locator('text="验证", text="captcha"')
                if await captcha.count() > 0:
                    logger.warning("⚠️ 检测到验证码，请手动完成")
                    logger.info("等待手动完成验证码...")
                    # 等待验证码消失或跳转
                    await page.wait_for_url("**/seller.temu.com/**", timeout=120000)
            except Exception:
                pass
            
            # 等待跳转到后台
            await page.wait_for_url("**/seller.temu.com/**", timeout=30000)
            
            # 验证登录状态
            if await self._check_login_status():
                logger.success("✓ 登录成功")
                
                # 保存 Cookie
                await self.browser_manager.save_cookies("data/temp/temu_cookies.json")
                
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
        """检查是否已登录.
        
        Returns:
            True 如果已登录
        """
        page = self.browser_manager.page
        
        try:
            # 检查页面URL
            url = page.url
            if "login" in url.lower():
                return False
            
            # 检查是否有用户信息元素（根据实际页面结构调整）
            # 这里需要根据实际的 Temu 后台结构来定位
            user_elements = await page.locator('[class*="user"], [class*="profile"], [class*="account"]').count()
            
            if user_elements > 0:
                logger.debug("✓ 检测到用户信息元素")
                return True
            
            # 也可以检查特定的后台页面元素
            dashboard_elements = await page.locator('[class*="dashboard"], [class*="home"]').count()
            if dashboard_elements > 0:
                logger.debug("✓ 检测到后台页面元素")
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"检查登录状态失败: {e}")
            return False


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

