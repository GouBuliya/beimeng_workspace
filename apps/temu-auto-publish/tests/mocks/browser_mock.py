"""
@PURPOSE: 浏览器相关 Mock 类
@OUTLINE:
  - MockLocator: 模拟 Playwright Locator
  - MockPage: 模拟 Playwright Page
  - MockBrowserManager: 模拟 BrowserManager
@DEPENDENCIES:
  - 外部: unittest.mock
"""

from typing import Any
from unittest.mock import MagicMock


class MockLocator:
    """模拟 Playwright Locator 对象"""

    def __init__(self, text: str = "", is_visible: bool = True, count: int = 1):
        self._text = text
        self._is_visible = is_visible
        self._count = count
        self._inner_text = text
        self._input_value = ""

    async def click(self, **kwargs) -> None:
        """模拟点击"""
        pass

    async def fill(self, value: str, **kwargs) -> None:
        """模拟填充"""
        self._input_value = value

    async def type(self, text: str, **kwargs) -> None:
        """模拟输入"""
        self._input_value += text

    async def press(self, key: str, **kwargs) -> None:
        """模拟按键"""
        pass

    async def hover(self, **kwargs) -> None:
        """模拟悬停"""
        pass

    async def scroll_into_view_if_needed(self, **kwargs) -> None:
        """模拟滚动到视图"""
        pass

    async def is_visible(self, **kwargs) -> bool:
        """检查是否可见"""
        return self._is_visible

    async def is_enabled(self, **kwargs) -> bool:
        """检查是否启用"""
        return True

    async def is_checked(self, **kwargs) -> bool:
        """检查是否选中"""
        return False

    async def count(self) -> int:
        """返回匹配元素数量"""
        return self._count

    async def text_content(self, **kwargs) -> str:
        """获取文本内容"""
        return self._text

    async def inner_text(self, **kwargs) -> str:
        """获取内部文本"""
        return self._inner_text

    async def input_value(self, **kwargs) -> str:
        """获取输入值"""
        return self._input_value

    async def get_attribute(self, name: str, **kwargs) -> str | None:
        """获取属性"""
        return None

    async def wait_for(self, **kwargs) -> None:
        """等待元素"""
        pass

    def first(self) -> "MockLocator":
        """获取第一个元素"""
        return self

    def last(self) -> "MockLocator":
        """获取最后一个元素"""
        return self

    def nth(self, index: int) -> "MockLocator":
        """获取第n个元素"""
        return self

    def locator(self, selector: str) -> "MockLocator":
        """子选择器"""
        return MockLocator()

    def filter(self, **kwargs) -> "MockLocator":
        """过滤"""
        return self


class MockPage:
    """模拟 Playwright Page 对象"""

    def __init__(self, url: str = "https://example.com"):
        self._url = url
        self._content = "<html><body></body></html>"
        self._title = "Mock Page"
        self._cookies: list[dict] = []
        self._locators: dict[str, MockLocator] = {}

    @property
    def url(self) -> str:
        return self._url

    @url.setter
    def url(self, value: str):
        self._url = value

    async def goto(self, url: str, **kwargs) -> None:
        """导航到URL"""
        self._url = url

    async def reload(self, **kwargs) -> None:
        """重新加载页面"""
        pass

    async def go_back(self, **kwargs) -> None:
        """返回上一页"""
        pass

    async def go_forward(self, **kwargs) -> None:
        """前进到下一页"""
        pass

    async def close(self) -> None:
        """关闭页面"""
        pass

    async def content(self) -> str:
        """获取页面内容"""
        return self._content

    async def title(self) -> str:
        """获取页面标题"""
        return self._title

    async def wait_for_timeout(self, timeout: int) -> None:
        """等待超时"""
        pass

    async def wait_for_load_state(self, state: str = "load", **kwargs) -> None:
        """等待加载状态"""
        pass

    async def wait_for_selector(self, selector: str, **kwargs) -> MockLocator:
        """等待选择器"""
        return self._locators.get(selector, MockLocator())

    async def wait_for_url(self, url: str, **kwargs) -> None:
        """等待URL"""
        self._url = url

    def locator(self, selector: str) -> MockLocator:
        """获取定位器"""
        return self._locators.get(selector, MockLocator())

    def get_by_text(self, text: str, **kwargs) -> MockLocator:
        """通过文本获取"""
        return MockLocator(text=text)

    def get_by_role(self, role: str, **kwargs) -> MockLocator:
        """通过角色获取"""
        return MockLocator()

    def get_by_placeholder(self, text: str, **kwargs) -> MockLocator:
        """通过占位符获取"""
        return MockLocator()

    def get_by_label(self, text: str, **kwargs) -> MockLocator:
        """通过标签获取"""
        return MockLocator()

    async def click(self, selector: str, **kwargs) -> None:
        """点击元素"""
        pass

    async def fill(self, selector: str, value: str, **kwargs) -> None:
        """填充输入"""
        pass

    async def type(self, selector: str, text: str, **kwargs) -> None:
        """输入文本"""
        pass

    async def press(self, selector: str, key: str, **kwargs) -> None:
        """按键"""
        pass

    async def select_option(self, selector: str, value: Any, **kwargs) -> list[str]:
        """选择选项"""
        return [str(value)]

    async def check(self, selector: str, **kwargs) -> None:
        """勾选"""
        pass

    async def uncheck(self, selector: str, **kwargs) -> None:
        """取消勾选"""
        pass

    async def screenshot(self, **kwargs) -> bytes:
        """截图"""
        return b""

    async def pdf(self, **kwargs) -> bytes:
        """生成PDF"""
        return b""

    async def evaluate(self, expression: str, *args) -> Any:
        """执行JavaScript"""
        return None

    async def evaluate_handle(self, expression: str, *args) -> Any:
        """执行JavaScript并返回句柄"""
        return None

    async def add_script_tag(self, **kwargs) -> None:
        """添加脚本标签"""
        pass

    async def add_style_tag(self, **kwargs) -> None:
        """添加样式标签"""
        pass

    async def set_input_files(self, selector: str, files: Any, **kwargs) -> None:
        """设置文件输入"""
        pass

    def set_mock_locator(self, selector: str, locator: MockLocator) -> None:
        """设置模拟定位器(测试辅助方法)"""
        self._locators[selector] = locator

    def set_content(self, content: str) -> None:
        """设置页面内容(测试辅助方法)"""
        self._content = content


class MockBrowserManager:
    """模拟 BrowserManager"""

    def __init__(self):
        self.page = MockPage()
        self.browser = MagicMock()
        self.context = MagicMock()
        self._is_started = False
        self._cookies: list[dict] = []

    async def start(self, headless: bool = True) -> None:
        """启动浏览器"""
        self._is_started = True

    async def close(self) -> None:
        """关闭浏览器"""
        self._is_started = False

    async def new_page(self) -> MockPage:
        """创建新页面"""
        return MockPage()

    async def save_cookies(self, path: str | None = None) -> bool:
        """保存Cookies"""
        return True

    async def load_cookies(self, path: str | None = None) -> bool:
        """加载Cookies"""
        return True

    async def get_cookies(self) -> list[dict]:
        """获取Cookies"""
        return self._cookies

    async def set_cookies(self, cookies: list[dict]) -> None:
        """设置Cookies"""
        self._cookies = cookies

    async def screenshot(self, path: str | None = None) -> bytes:
        """截图"""
        return b""

    @property
    def is_started(self) -> bool:
        """是否已启动"""
        return self._is_started
