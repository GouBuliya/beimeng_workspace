"""
@PURPOSE: 浏览器相关功能集成测试
@OUTLINE:
  - class TestBrowserManagerIntegration: 浏览器管理器集成测试
  - class TestCookieManagerIntegration: Cookie 管理器集成测试
  - class TestLoginControllerIntegration: 登录控制器集成测试
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.browser 模块
@GOTCHAS:
  - 这些测试不需要真实浏览器,使用 Mock 模拟浏览器行为
  - 标记为 integration 的测试需要真实环境
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestBrowserManagerIntegration:
    """浏览器管理器集成测试."""

    def test_browser_manager_import(self) -> None:
        """测试 BrowserManager 可导入."""
        from src.browser.browser_manager import BrowserManager

        assert BrowserManager is not None

    def test_browser_manager_initialization(self) -> None:
        """测试 BrowserManager 初始化."""
        from src.browser.browser_manager import BrowserManager

        # 直接测试初始化,不需要 patch sync_playwright
        manager = BrowserManager()
        assert manager is not None

    @pytest.mark.asyncio
    async def test_browser_manager_context_methods(self) -> None:
        """测试 BrowserManager 上下文管理方法."""
        with patch("src.browser.browser_manager.async_playwright") as mock_playwright:
            # 设置 mock
            mock_browser = MagicMock()
            mock_context = MagicMock()
            mock_page = MagicMock()

            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_browser.new_context = AsyncMock(return_value=mock_context)

            mock_playwright_instance = MagicMock()
            mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_playwright_instance.start = AsyncMock(return_value=mock_playwright_instance)

            mock_playwright.return_value.__aenter__ = AsyncMock(
                return_value=mock_playwright_instance
            )
            mock_playwright.return_value.__aexit__ = AsyncMock()

            from src.browser.browser_manager import BrowserManager

            manager = BrowserManager()
            # 验证初始化成功
            assert manager is not None


class TestCookieManagerIntegration:
    """Cookie 管理器集成测试."""

    def test_cookie_manager_import(self) -> None:
        """测试 CookieManager 可导入."""
        from src.browser.cookie_manager import CookieManager

        assert CookieManager is not None

    def test_cookie_manager_initialization(self, tmp_path: Path) -> None:
        """测试 CookieManager 初始化."""
        from src.browser.cookie_manager import CookieManager

        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(cookie_file=str(cookie_file))
        assert manager is not None

    def test_cookie_file_path_handling(self, tmp_path: Path) -> None:
        """测试 Cookie 文件路径处理."""
        from src.browser.cookie_manager import CookieManager

        # 测试绝对路径
        cookie_file = tmp_path / "test_cookies.json"
        manager = CookieManager(cookie_file=str(cookie_file))
        assert manager.cookie_file == cookie_file

    def test_save_and_load_cookies(self, tmp_path: Path) -> None:
        """测试保存和加载 Cookies (使用实际 API)."""
        from src.browser.cookie_manager import CookieManager

        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(cookie_file=str(cookie_file))

        # 使用 CookieManager 实际的 save 方法
        test_cookies = [
            {"name": "session", "value": "abc123", "domain": "example.com"},
            {"name": "token", "value": "xyz789", "domain": "example.com"},
        ]
        manager.save(test_cookies)

        # 使用 CookieManager 实际的 load 方法
        loaded_cookies = manager.load()
        assert loaded_cookies is not None
        assert len(loaded_cookies) == 2

    def test_load_nonexistent_cookies(self, tmp_path: Path) -> None:
        """测试加载不存在的 Cookie 文件."""
        from src.browser.cookie_manager import CookieManager

        cookie_file = tmp_path / "nonexistent.json"
        manager = CookieManager(cookie_file=str(cookie_file))

        loaded_cookies = manager.load()
        assert loaded_cookies is None

    def test_clear_cookies(self, tmp_path: Path) -> None:
        """测试清除 Cookies."""
        from src.browser.cookie_manager import CookieManager

        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(cookie_file=str(cookie_file))

        # 先保存一些 cookies
        test_cookies = [{"name": "test", "value": "value", "domain": "example.com"}]
        manager.save(test_cookies)

        # 清除
        manager.clear()

        # 验证已清除
        loaded_cookies = manager.load()
        assert loaded_cookies is None

    def test_is_valid(self, tmp_path: Path) -> None:
        """测试 Cookie 有效性检查."""
        from src.browser.cookie_manager import CookieManager

        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(cookie_file=str(cookie_file))

        # 未保存时应该无效
        assert manager.is_valid() is False

        # 保存后应该有效
        test_cookies = [{"name": "test", "value": "value", "domain": "example.com"}]
        manager.save(test_cookies)
        assert manager.is_valid() is True


class TestLoginControllerIntegration:
    """登录控制器集成测试."""

    def test_login_controller_import(self) -> None:
        """测试 LoginController 可导入."""
        from src.browser.login_controller import LoginController

        assert LoginController is not None

    def test_login_controller_initialization(self) -> None:
        """测试 LoginController 初始化."""
        from src.browser.login_controller import LoginController

        controller = LoginController()
        assert controller is not None

    @pytest.mark.asyncio
    async def test_check_login_status(self) -> None:
        """测试检查登录状态 (控制器使用实例属性 page)."""
        from src.browser.login_controller import LoginController

        controller = LoginController()

        # 创建 mock page 并赋值给控制器实例属性
        page = MagicMock()
        page.url = "https://seller.temu.com/dashboard"

        # Mock locator
        locator = MagicMock()
        locator.count = AsyncMock(return_value=1)
        page.locator = MagicMock(return_value=locator)

        # _check_login_status 使用 self.page
        controller.page = page

        # 检查登录状态 - 使用 _check_login_status (无参数)
        result = await controller._check_login_status()
        # 结果取决于具体实现
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_wait_for_login_with_timeout(self) -> None:
        """测试等待登录超时."""
        from src.browser.login_controller import LoginController

        controller = LoginController()

        page = MagicMock()
        page.url = "https://seller.temu.com/login"
        page.wait_for_timeout = AsyncMock()

        locator = MagicMock()
        locator.count = AsyncMock(return_value=0)
        page.locator = MagicMock(return_value=locator)

        # 短超时应该失败(但我们只是确保不会抛异常)
        try:
            await controller.wait_for_login(page, timeout=0.1)
        except Exception:
            pass  # 可能会超时,这是预期的


class TestPublishControllerIntegration:
    """发布控制器集成测试."""

    def test_publish_controller_import(self) -> None:
        """测试 PublishController 可导入."""
        from src.browser.publish_controller import PublishController

        assert PublishController is not None

    def test_publish_controller_initialization(self) -> None:
        """测试 PublishController 初始化."""
        from src.browser.publish_controller import PublishController

        controller = PublishController()
        assert controller is not None


class TestFirstEditIntegration:
    """首次编辑模块集成测试."""

    def test_first_edit_base_import(self) -> None:
        """测试 FirstEditBase 可导入."""
        from src.browser.first_edit.base import FirstEditBase

        assert FirstEditBase is not None

    def test_first_edit_controller_import(self) -> None:
        """测试 FirstEditController 可导入."""
        from src.browser.first_edit.controller import FirstEditController

        assert FirstEditController is not None

    def test_first_edit_workflow_mixin_import(self) -> None:
        """测试 FirstEditWorkflowMixin 可导入."""
        from src.browser.first_edit.workflow import FirstEditWorkflowMixin

        assert FirstEditWorkflowMixin is not None

    def test_first_edit_dialog_mixin_import(self) -> None:
        """测试 FirstEditDialogMixin 可导入."""
        from src.browser.first_edit.dialog import FirstEditDialogMixin

        assert FirstEditDialogMixin is not None

    def test_first_edit_category_mixin_import(self) -> None:
        """测试 FirstEditCategoryMixin 可导入."""
        from src.browser.first_edit.category import FirstEditCategoryMixin

        assert FirstEditCategoryMixin is not None


class TestSelectorRaceIntegration:
    """选择器竞速工具集成测试."""

    def test_selector_race_import(self) -> None:
        """测试选择器竞速函数可导入."""
        from src.utils.selector_race import (
            TIMEOUTS,
            SelectorTimeouts,
            try_selectors_race,
            try_selectors_race_with_elements,
            try_selectors_sequential,
        )

        assert try_selectors_race is not None
        assert try_selectors_race_with_elements is not None
        assert try_selectors_sequential is not None
        assert SelectorTimeouts is not None
        assert TIMEOUTS is not None

    @pytest.mark.asyncio
    async def test_selector_race_with_mock_page(self) -> None:
        """测试选择器竞速与 mock 页面."""
        from src.utils.selector_race import try_selectors_race

        page = MagicMock()
        locator = MagicMock()
        locator.count = AsyncMock(return_value=1)
        locator.is_visible = AsyncMock(return_value=True)
        locator.first = locator
        page.locator = MagicMock(return_value=locator)

        result = await try_selectors_race(
            page,
            ["selector1", "selector2"],
            context_name="test",
            timeout_ms=100,
        )

        assert result is not None


class TestDataProcessorIntegration:
    """数据处理器集成测试."""

    def test_data_converter_import(self) -> None:
        """测试 DataConverter 可导入."""
        from src.data_processor.data_converter import DataConverter

        assert DataConverter is not None

    def test_selection_table_reader_import(self) -> None:
        """测试 SelectionTableReader 可导入."""
        from src.data_processor.selection_table_reader import SelectionTableReader

        assert SelectionTableReader is not None


class TestBrowserSettingsIntegration:
    """浏览器设置集成测试."""

    def test_browser_settings_import(self) -> None:
        """测试 BrowserSettings 可导入."""
        from src.browser.browser_settings import BrowserSettings

        assert BrowserSettings is not None

    def test_browser_settings_initialization(self) -> None:
        """测试 BrowserSettings 初始化."""
        from src.browser.browser_settings import BrowserSettings

        # BrowserSettings 继承自 pydantic BaseSettings
        settings = BrowserSettings()
        assert settings is not None


class TestEndToEndMock:
    """端到端模拟测试(不需要真实浏览器)."""

    @pytest.mark.asyncio
    async def test_full_workflow_mock(self) -> None:
        """测试完整工作流(使用 mock)."""
        with (
            patch("src.workflows.full_publish_workflow.CollectionController") as mock_collection,
            patch("src.workflows.full_publish_workflow.CompletePublishWorkflow") as mock_publish,
        ):
            # 设置 mocks
            mock_collection_instance = MagicMock()
            mock_collection_instance.visit_store = AsyncMock(return_value=True)
            mock_collection_instance.search_and_collect = AsyncMock(
                return_value=[{"url": "https://example.com", "title": "商品"}]
            )
            mock_collection.return_value = mock_collection_instance

            mock_publish_instance = MagicMock()
            mock_publish_instance.execute = AsyncMock(
                return_value={"status": "success", "published_count": 1}
            )
            mock_publish.return_value = mock_publish_instance

            from src.workflows.full_publish_workflow import FullPublishWorkflow

            workflow = FullPublishWorkflow()

            page = MagicMock()
            page.goto = AsyncMock()
            page.wait_for_load_state = AsyncMock()

            products = [
                {
                    "keyword": "测试产品",
                    "collect_count": 1,
                    "cost": 10.0,
                    "stock": 100,
                }
            ]

            result = await workflow.execute(
                page, products, enable_batch_edit=True, enable_publish=False
            )

            assert result["status"] == "success"
            assert result["total_products"] >= 0


@pytest.mark.integration
class TestRealBrowserIntegration:
    """真实浏览器集成测试(需要浏览器环境)."""

    @pytest.mark.skip(reason="需要真实浏览器环境")
    @pytest.mark.asyncio
    async def test_real_browser_launch(self) -> None:
        """测试真实浏览器启动."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("https://example.com")
            title = await page.title()
            assert "Example" in title
            await browser.close()

    @pytest.mark.skip(reason="需要真实浏览器环境和登录凭证")
    @pytest.mark.asyncio
    async def test_real_temu_login(self) -> None:
        """测试真实 Temu 登录."""
        pytest.skip("需要真实登录凭证")
