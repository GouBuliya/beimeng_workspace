"""
@PURPOSE: 浏览器管理器，使用Playwright管理浏览器实例，支持反检测和Cookie管理
@OUTLINE:
  - class BrowserManager: 浏览器管理器主类
  - async def start(): 启动浏览器
  - async def close(): 关闭浏览器
  - async def save_cookies(): 保存Cookie
  - async def load_cookies(): 加载Cookie
  - async def screenshot(): 截图
@GOTCHAS:
  - 必须使用async/await异步操作
  - 关闭浏览器前应保存Cookie
  - 反检测配置在browser_config.json中
@DEPENDENCIES:
  - 外部: playwright
@RELATED: login_controller.py, cookie_manager.py
"""

import json
from pathlib import Path

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)


class BrowserManager:
    """浏览器管理器.

    管理 Playwright 浏览器实例的创建、配置和销毁。

    Attributes:
        config: 浏览器配置
        playwright: Playwright 实例
        browser: 浏览器实例
        context: 浏览器上下文
        page: 当前页面

    Examples:
        >>> async with BrowserManager() as manager:
        ...     page = manager.page
        ...     await page.goto("https://example.com")
    """

    def __init__(self, config_path: str = "config/browser_config.json"):
        """初始化管理器.

        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.load_config()

        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def load_config(self) -> None:
        """加载配置."""
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
            self.config = {
                "browser": {"type": "chromium", "headless": False},
                "timeouts": {"default": 30000},
            }
            return

        with open(self.config_path, encoding="utf-8") as f:
            self.config = json.load(f)
        logger.info("浏览器配置已加载")

    async def start(self, headless: bool | None = None) -> None:
        """启动浏览器.

        Args:
            headless: 是否无头模式，None 则使用配置文件设置
        """
        logger.info("启动 Playwright 浏览器...")

        self.playwright = await async_playwright().start()

        # 浏览器选项
        browser_config = self.config.get("browser", {})
        browser_type = browser_config.get("type", "chromium")

        # 是否使用无头模式
        if headless is None:
            headless = browser_config.get("headless", False)

        # 启动参数（添加性能优化选项）
        launch_options = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-gpu",  # 禁用GPU加速
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",  # 跨域问题
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            "slow_mo": 300 if not headless else 0,  # 有头模式减速300ms便于观察
        }

        # 启动浏览器
        if browser_type == "chromium":
            self.browser = await self.playwright.chromium.launch(**launch_options)
        elif browser_type == "firefox":
            self.browser = await self.playwright.firefox.launch(**launch_options)
        elif browser_type == "webkit":
            self.browser = await self.playwright.webkit.launch(**launch_options)
        else:
            raise ValueError(f"不支持的浏览器类型: {browser_type}")

        # 创建上下文
        context_options = {
            "viewport": {
                "width": browser_config.get("window_width", 1920),
                "height": browser_config.get("window_height", 1080),
            },
            "locale": browser_config.get("locale", "zh-CN"),
            "timezone_id": browser_config.get("timezone", "Asia/Shanghai"),
        }

        # 设置 User-Agent
        if "user_agent" in browser_config:
            context_options["user_agent"] = browser_config["user_agent"]

        self.context = await self.browser.new_context(**context_options)

        # 应用反检测补丁
        if self.config.get("stealth", {}).get("enabled", True):
            await self._apply_stealth()
        
        # 添加禁用动画的初始化脚本（性能优化）
        await self.context.add_init_script("""
            // 禁用CSS动画和过渡效果，加速页面交互
            const style = document.createElement('style');
            style.innerHTML = `
                *, ::before, ::after {
                    transition: none !important;
                    animation: none !important;
                    animation-duration: 0s !important;
                    animation-delay: 0s !important;
                }
            `;
            document.head.appendChild(style);
        """)

        # 创建页面
        self.page = await self.context.new_page()

        # 设置默认超时
        default_timeout = self.config.get("timeouts", {}).get("default", 30000)
        self.page.set_default_timeout(default_timeout)

        logger.success(f"✓ 浏览器已启动 (headless={headless})")

    async def _apply_stealth(self) -> None:
        """应用反检测补丁."""
        try:
            from playwright_stealth import stealth_async

            await stealth_async(self.context)
            logger.debug("✓ 已应用反检测补丁")
        except ImportError:
            logger.warning("playwright-stealth 未安装，跳过反检测")
        except Exception as e:
            logger.warning(f"应用反检测补丁失败: {e}")

    async def goto(self, url: str, wait_until: str = "networkidle") -> None:
        """导航到URL.

        Args:
            url: 目标URL
            wait_until: 等待条件 (load|domcontentloaded|networkidle|commit)
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")

        logger.info(f"导航到: {url}")
        await self.page.goto(url, wait_until=wait_until)

    async def save_cookies(self, file_path: str) -> None:
        """保存 Cookie.

        Args:
            file_path: Cookie 文件路径
        """
        if not self.context:
            raise RuntimeError("浏览器未启动")

        cookies = await self.context.cookies()

        cookie_file = Path(file_path)
        cookie_file.parent.mkdir(parents=True, exist_ok=True)

        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        logger.info(f"Cookie 已保存到: {cookie_file}")

    async def load_cookies(self, file_path: str) -> bool:
        """加载 Cookie.

        Args:
            file_path: Cookie 文件路径

        Returns:
            是否成功加载
        """
        if not self.context:
            raise RuntimeError("浏览器未启动")

        cookie_file = Path(file_path)
        if not cookie_file.exists():
            logger.debug("Cookie 文件不存在")
            return False

        try:
            with open(cookie_file, encoding="utf-8") as f:
                cookies = json.load(f)

            await self.context.add_cookies(cookies)
            logger.success("✓ Cookie 已加载")
            return True
        except Exception as e:
            logger.error(f"加载 Cookie 失败: {e}")
            return False

    async def screenshot(self, path: str, full_page: bool = False) -> None:
        """截图.

        Args:
            path: 截图保存路径
            full_page: 是否截取整个页面
        """
        if not self.page:
            raise RuntimeError("浏览器未启动")

        screenshot_path = Path(path)
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)

        await self.page.screenshot(path=str(screenshot_path), full_page=full_page)
        logger.debug(f"截图已保存: {screenshot_path}")

    async def close(self) -> None:
        """关闭浏览器."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        logger.info("浏览器已关闭")

    async def __aenter__(self):
        """异步上下文管理器入口."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口."""
        await self.close()


# 测试代码
if __name__ == "__main__":
    import asyncio

    async def test():
        async with BrowserManager() as manager:
            await manager.goto("https://www.baidu.com")
            await manager.screenshot("data/temp/test.png")
            logger.success("✓ 测试完成")

    asyncio.run(test())
