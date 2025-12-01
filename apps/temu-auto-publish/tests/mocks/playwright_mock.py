"""
@PURPOSE: Playwright 核心对象 Mock 类
@OUTLINE:
  - MockBrowserContext: 模拟浏览器上下文
  - MockBrowser: 模拟浏览器实例
  - MockPlaywright: 模拟 Playwright 主对象
@DEPENDENCIES:
  - 外部: unittest.mock
  - 内部: browser_mock
"""

from typing import List, Dict, Optional, Any
from unittest.mock import MagicMock

from .browser_mock import MockPage


class MockBrowserContext:
    """模拟 Playwright BrowserContext"""

    def __init__(self):
        self._pages: List[MockPage] = []
        self._cookies: List[Dict] = []
        self._storage_state: Dict = {}

    async def new_page(self) -> MockPage:
        """创建新页面"""
        page = MockPage()
        self._pages.append(page)
        return page

    async def close(self) -> None:
        """关闭上下文"""
        self._pages.clear()

    @property
    def pages(self) -> List[MockPage]:
        """获取所有页面"""
        return self._pages

    async def cookies(self, urls: Optional[List[str]] = None) -> List[Dict]:
        """获取Cookies"""
        return self._cookies

    async def add_cookies(self, cookies: List[Dict]) -> None:
        """添加Cookies"""
        self._cookies.extend(cookies)

    async def clear_cookies(self) -> None:
        """清除Cookies"""
        self._cookies.clear()

    async def storage_state(self, path: Optional[str] = None) -> Dict:
        """获取存储状态"""
        return self._storage_state

    async def grant_permissions(self, permissions: List[str], **kwargs) -> None:
        """授予权限"""
        pass

    async def set_geolocation(self, geolocation: Dict) -> None:
        """设置地理位置"""
        pass

    async def set_extra_http_headers(self, headers: Dict[str, str]) -> None:
        """设置额外HTTP头"""
        pass

    def set_default_timeout(self, timeout: float) -> None:
        """设置默认超时"""
        pass

    def set_default_navigation_timeout(self, timeout: float) -> None:
        """设置默认导航超时"""
        pass


class MockBrowser:
    """模拟 Playwright Browser"""

    def __init__(self):
        self._contexts: List[MockBrowserContext] = []
        self._is_connected = True
        self.version = "mock-browser-1.0"

    async def new_context(self, **kwargs) -> MockBrowserContext:
        """创建新的浏览器上下文"""
        context = MockBrowserContext()
        self._contexts.append(context)
        return context

    async def new_page(self, **kwargs) -> MockPage:
        """创建新页面（便捷方法）"""
        context = await self.new_context()
        return await context.new_page()

    async def close(self) -> None:
        """关闭浏览器"""
        self._is_connected = False
        self._contexts.clear()

    @property
    def contexts(self) -> List[MockBrowserContext]:
        """获取所有上下文"""
        return self._contexts

    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._is_connected


class MockBrowserType:
    """模拟 Playwright BrowserType (chromium, firefox, webkit)"""

    def __init__(self, name: str = "chromium"):
        self.name = name

    async def launch(self, **kwargs) -> MockBrowser:
        """启动浏览器"""
        return MockBrowser()

    async def launch_persistent_context(self, user_data_dir: str, **kwargs) -> MockBrowserContext:
        """启动持久化上下文"""
        return MockBrowserContext()

    async def connect(self, ws_endpoint: str, **kwargs) -> MockBrowser:
        """连接到远程浏览器"""
        return MockBrowser()

    async def connect_over_cdp(self, endpoint_url: str, **kwargs) -> MockBrowser:
        """通过CDP连接"""
        return MockBrowser()


class MockPlaywright:
    """模拟 Playwright 主对象"""

    def __init__(self):
        self.chromium = MockBrowserType("chromium")
        self.firefox = MockBrowserType("firefox")
        self.webkit = MockBrowserType("webkit")
        self.devices = {
            "iPhone 13": {
                "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)",
                "viewport": {"width": 390, "height": 844},
                "device_scale_factor": 3,
                "is_mobile": True,
                "has_touch": True,
            },
            "Pixel 5": {
                "user_agent": "Mozilla/5.0 (Linux; Android 11; Pixel 5)",
                "viewport": {"width": 393, "height": 851},
                "device_scale_factor": 2.75,
                "is_mobile": True,
                "has_touch": True,
            },
        }

    async def stop(self) -> None:
        """停止 Playwright"""
        pass


# 用于 async with async_playwright() as p: 的上下文管理器
class MockAsyncPlaywright:
    """模拟 async_playwright() 上下文管理器"""

    async def __aenter__(self) -> MockPlaywright:
        return MockPlaywright()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


def mock_async_playwright() -> MockAsyncPlaywright:
    """返回模拟的 async_playwright 上下文管理器"""
    return MockAsyncPlaywright()
