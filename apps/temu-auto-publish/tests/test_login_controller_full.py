"""
@PURPOSE: LoginController 登录控制器测试
@OUTLINE:
  - TestLoginControllerInit: 控制器初始化测试
  - TestLoginControllerLoadSelectors: 选择器加载测试
  - TestLoginControllerBrowserValidation: 浏览器有效性检查测试
  - TestLoginControllerCleanup: 浏览器清理测试
  - TestLoginControllerCheckLoginStatus: 登录状态检查测试
  - TestLoginControllerLogin: 登录流程测试
@DEPENDENCIES:
  - 内部: browser.login_controller
  - 外部: pytest, pytest-asyncio
"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# LoginController 初始化测试
# ============================================================
class TestLoginControllerInit:
    """LoginController 初始化测试"""

    @pytest.fixture
    def temp_config_files(self, tmp_path):
        """创建临时配置文件"""
        # 浏览器配置
        browser_config = {
            "headless": False,
            "slow_mo": 50,
        }
        browser_config_file = tmp_path / "browser_config.json"
        browser_config_file.write_text(json.dumps(browser_config))

        # 选择器配置
        selector_config = {
            "login": {
                "url": "https://example.com/login",
                "username_input": "input[name='username']",
                "password_input": "input[type='password']",
                "login_button": "button:has-text('登录')",
            },
            "homepage": {
                "url": "https://example.com/welcome",
                "product_menu": "text='产品'",
            },
        }
        selector_config_file = tmp_path / "selectors.json"
        selector_config_file.write_text(json.dumps(selector_config))

        return str(browser_config_file), str(selector_config_file)

    def test_init_default(self):
        """测试默认初始化"""
        from src.browser.login_controller import LoginController

        with (
            patch.object(LoginController, "_load_selectors", return_value={}),
            patch("src.browser.login_controller.BrowserManager"),
            patch("src.browser.login_controller.CookieManager"),
        ):
            controller = LoginController()

            assert controller.selectors == {}
            assert controller.browser_manager is not None
            assert controller.cookie_manager is not None

    def test_init_with_config_paths(self, temp_config_files):
        """测试指定配置路径初始化"""
        from src.browser.login_controller import LoginController

        browser_config, selector_config = temp_config_files

        with patch("src.browser.login_controller.BrowserManager"):
            controller = LoginController(
                config_path=browser_config,
                selector_path=selector_config,
            )

            assert "login" in controller.selectors
            assert "homepage" in controller.selectors


# ============================================================
# 选择器加载测试
# ============================================================
class TestLoginControllerLoadSelectors:
    """选择器加载测试"""

    @pytest.fixture
    def temp_selector_file(self, tmp_path):
        """创建临时选择器文件"""
        selector_config = {
            "login": {
                "url": "https://example.com/login",
            },
        }
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps(selector_config))
        return str(selector_file)

    def test_load_selectors_success(self, temp_selector_file):
        """测试选择器加载成功"""
        from src.browser.login_controller import LoginController

        with patch("src.browser.login_controller.BrowserManager"):
            controller = LoginController(selector_path=temp_selector_file)

            assert "login" in controller.selectors

    def test_load_selectors_file_not_found(self, tmp_path):
        """测试选择器文件不存在"""
        from src.browser.login_controller import LoginController

        non_existent = str(tmp_path / "non_existent.json")

        with patch("src.browser.login_controller.BrowserManager"):
            controller = LoginController(selector_path=non_existent)

            # 应该返回空字典而不是抛出异常
            assert controller.selectors == {}

    def test_load_selectors_invalid_json(self, tmp_path):
        """测试无效 JSON 文件"""
        from src.browser.login_controller import LoginController

        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text("not valid json")

        with patch("src.browser.login_controller.BrowserManager"):
            controller = LoginController(selector_path=str(invalid_file))

            assert controller.selectors == {}


# ============================================================
# 浏览器有效性检查测试
# ============================================================
class TestLoginControllerBrowserValidation:
    """浏览器有效性检查测试"""

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.login_controller import LoginController

        selector_file = tmp_path / "selectors.json"
        selector_file.write_text("{}")

        with patch("src.browser.login_controller.BrowserManager"):
            return LoginController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_is_browser_valid_all_none(self, controller):
        """测试浏览器对象为 None"""
        controller.browser_manager.playwright = None
        controller.browser_manager.browser = None
        controller.browser_manager.context = None
        controller.browser_manager.page = None

        result = await controller._is_browser_valid()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_browser_valid_browser_disconnected(self, controller):
        """测试浏览器已断开连接"""
        controller.browser_manager.playwright = MagicMock()
        controller.browser_manager.browser = MagicMock()
        controller.browser_manager.browser.is_connected.return_value = False
        controller.browser_manager.context = MagicMock()
        controller.browser_manager.page = MagicMock()

        result = await controller._is_browser_valid()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_browser_valid_page_timeout(self, controller):
        """测试页面响应超时"""
        controller.browser_manager.playwright = MagicMock()
        controller.browser_manager.browser = MagicMock()
        controller.browser_manager.browser.is_connected.return_value = True
        controller.browser_manager.context = MagicMock()
        controller.browser_manager.page = AsyncMock()

        # 修复: 直接抛出 TimeoutError，避免真正等待 5 秒
        controller.browser_manager.page.evaluate = AsyncMock(side_effect=TimeoutError())

        result = await controller._is_browser_valid()

        assert result is False

    @pytest.mark.asyncio
    async def test_is_browser_valid_success(self, controller):
        """测试浏览器有效"""
        controller.browser_manager.playwright = MagicMock()
        controller.browser_manager.browser = MagicMock()
        controller.browser_manager.browser.is_connected.return_value = True
        controller.browser_manager.context = MagicMock()
        controller.browser_manager.context.pages = [MagicMock()]
        controller.browser_manager.page = AsyncMock()
        controller.browser_manager.page.evaluate = AsyncMock(return_value="complete")

        result = await controller._is_browser_valid()

        assert result is True


# ============================================================
# 浏览器清理测试
# ============================================================
class TestLoginControllerCleanup:
    """浏览器清理测试"""

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.login_controller import LoginController

        selector_file = tmp_path / "selectors.json"
        selector_file.write_text("{}")

        with patch("src.browser.login_controller.BrowserManager"):
            return LoginController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_cleanup_browser_all_none(self, controller):
        """测试清理所有为 None 的资源"""
        controller.browser_manager.page = None
        controller.browser_manager.context = None
        controller.browser_manager.browser = None
        controller.browser_manager.playwright = None

        result = await controller._cleanup_browser()

        assert result["page"] is True
        assert result["context"] is True
        assert result["browser"] is True
        assert result["playwright"] is True

    @pytest.mark.asyncio
    async def test_cleanup_browser_success(self, controller):
        """测试成功清理浏览器资源"""
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_browser = AsyncMock()
        mock_playwright = AsyncMock()

        controller.browser_manager.page = mock_page
        controller.browser_manager.context = mock_context
        controller.browser_manager.browser = mock_browser
        controller.browser_manager.playwright = mock_playwright

        result = await controller._cleanup_browser()

        assert result["page"] is True
        assert result["context"] is True
        assert result["browser"] is True
        assert result["playwright"] is True
        assert controller.browser_manager.page is None
        assert controller.browser_manager.context is None
        assert controller.browser_manager.browser is None
        assert controller.browser_manager.playwright is None


# ============================================================
# 登录状态检查测试
# ============================================================
class TestLoginControllerCheckLoginStatus:
    """登录状态检查测试"""

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.login_controller import LoginController

        selector_config = {
            "homepage": {
                "product_menu": "text='产品'",
            },
        }
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps(selector_config))

        with patch("src.browser.login_controller.BrowserManager"):
            return LoginController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_check_login_status_on_login_page(self, controller):
        """测试在登录页面时返回 False"""
        mock_page = AsyncMock()
        mock_page.url = "https://example.com/sub_account/users"
        controller.browser_manager.page = mock_page

        result = await controller._check_login_status()

        assert result is False

    @pytest.mark.asyncio
    async def test_check_login_status_on_welcome_page(self, controller):
        """测试在欢迎页面时返回 True"""
        mock_page = AsyncMock()
        mock_page.url = "https://example.com/welcome"
        controller.browser_manager.page = mock_page

        result = await controller._check_login_status()

        assert result is True

    @pytest.mark.asyncio
    async def test_check_login_status_on_collection_page(self, controller):
        """测试在采集箱页面时返回 True"""
        mock_page = AsyncMock()
        mock_page.url = "https://example.com/common_collect_box"
        controller.browser_manager.page = mock_page

        result = await controller._check_login_status()

        assert result is True

    @pytest.mark.asyncio
    async def test_check_login_status_with_product_menu(self, controller):
        """测试检测到产品菜单时返回 True"""
        mock_page = AsyncMock()
        mock_page.url = "https://example.com/other"

        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_page.locator = MagicMock(return_value=mock_locator)

        controller.browser_manager.page = mock_page

        result = await controller._check_login_status()

        assert result is True

    @pytest.mark.asyncio
    async def test_check_login_status_exception(self, controller):
        """测试异常时返回 False"""
        mock_page = MagicMock()
        mock_page.url = property(lambda self: (_ for _ in ()).throw(Exception("test")))
        controller.browser_manager.page = mock_page

        result = await controller._check_login_status()

        assert result is False


# ============================================================
# 收集页面作用域测试
# ============================================================
class TestCollectPageScopes:
    """收集页面作用域测试"""

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.login_controller import LoginController

        selector_file = tmp_path / "selectors.json"
        selector_file.write_text("{}")

        with patch("src.browser.login_controller.BrowserManager"):
            return LoginController(selector_path=str(selector_file))

    def test_collect_page_scopes_none(self, controller):
        """测试页面为 None"""
        result = controller._collect_page_scopes(None)

        assert result == []

    def test_collect_page_scopes_no_frames(self, controller):
        """测试没有 frames"""
        mock_page = MagicMock()
        mock_page.frames = []

        result = controller._collect_page_scopes(mock_page)

        assert len(result) == 1
        assert result[0][0] == "page"
        assert result[0][1] is mock_page

    def test_collect_page_scopes_with_frames(self, controller):
        """测试有 frames"""
        mock_page = MagicMock()
        mock_frame1 = MagicMock()
        mock_frame1.name = "frame1"
        mock_frame1.url = "https://example.com/frame1"
        mock_frame2 = MagicMock()
        mock_frame2.name = ""
        mock_frame2.url = "https://example.com/frame2"
        mock_page.frames = [mock_frame1, mock_frame2]

        result = controller._collect_page_scopes(mock_page)

        assert len(result) == 3
        assert result[0][0] == "page"
        assert "frame[0]" in result[1][0]
        assert "frame[1]" in result[2][0]


# ============================================================
# 点击首个可见元素测试
# ============================================================
class TestClickFirstVisible:
    """点击首个可见元素测试"""

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.login_controller import LoginController

        selector_file = tmp_path / "selectors.json"
        selector_file.write_text("{}")

        with patch("src.browser.login_controller.BrowserManager"):
            return LoginController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_click_first_visible_found(self, controller):
        """测试找到可点击元素"""
        mock_page = MagicMock()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.first = mock_locator
        mock_locator.is_visible = AsyncMock(return_value=True)
        mock_locator.click = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)

        scopes = [("page", mock_page)]
        selectors = [".close-button"]

        result = await controller._click_first_visible(scopes, selectors)

        assert result is True
        mock_locator.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_first_visible_not_found(self, controller):
        """测试未找到可点击元素"""
        mock_page = MagicMock()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator = MagicMock(return_value=mock_locator)

        scopes = [("page", mock_page)]
        selectors = [".close-button"]

        result = await controller._click_first_visible(scopes, selectors)

        assert result is False

    @pytest.mark.asyncio
    async def test_click_first_visible_not_visible(self, controller):
        """测试元素不可见"""
        mock_page = MagicMock()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.first = mock_locator
        mock_locator.is_visible = AsyncMock(return_value=False)
        mock_page.locator = MagicMock(return_value=mock_locator)

        scopes = [("page", mock_page)]
        selectors = [".close-button"]

        result = await controller._click_first_visible(scopes, selectors)

        assert result is False


# ============================================================
# login_if_needed 测试
# ============================================================
class TestLoginIfNeeded:
    """login_if_needed 测试"""

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.login_controller import LoginController

        selector_file = tmp_path / "selectors.json"
        selector_file.write_text("{}")

        with patch("src.browser.login_controller.BrowserManager"):
            return LoginController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_login_if_needed_already_logged_in(self, controller):
        """测试已登录时不执行登录"""
        controller.browser_manager.browser = MagicMock()

        with patch.object(controller, "_check_login_status", return_value=True):
            result = await controller.login_if_needed("user", "pass")

            assert result is True

    @pytest.mark.asyncio
    async def test_login_if_needed_browser_not_started(self, controller):
        """测试浏览器未启动时启动浏览器"""
        controller.browser_manager.browser = None
        controller.browser_manager.start = AsyncMock()

        with (
            patch.object(controller, "_check_login_status", return_value=True),
        ):
            result = await controller.login_if_needed("user", "pass")

            controller.browser_manager.start.assert_called_once()
            assert result is True

    @pytest.mark.asyncio
    async def test_login_if_needed_no_username(self, controller, monkeypatch):
        """测试未提供用户名且环境变量未设置"""
        controller.browser_manager.browser = MagicMock()
        monkeypatch.delenv("MIAOSHOU_USERNAME", raising=False)

        with patch.object(controller, "_check_login_status", return_value=False):
            result = await controller.login_if_needed()

            assert result is False

    @pytest.mark.asyncio
    async def test_login_if_needed_no_password(self, controller, monkeypatch):
        """测试未提供密码且环境变量未设置"""
        controller.browser_manager.browser = MagicMock()
        monkeypatch.setenv("MIAOSHOU_USERNAME", "test_user")
        monkeypatch.delenv("MIAOSHOU_PASSWORD", raising=False)

        with patch.object(controller, "_check_login_status", return_value=False):
            result = await controller.login_if_needed()

            assert result is False

    @pytest.mark.asyncio
    async def test_login_if_needed_with_env_vars(self, controller, monkeypatch):
        """测试使用环境变量登录"""
        controller.browser_manager.browser = MagicMock()
        monkeypatch.setenv("MIAOSHOU_USERNAME", "test_user")
        monkeypatch.setenv("MIAOSHOU_PASSWORD", "test_pass")

        with (
            patch.object(controller, "_check_login_status", return_value=False),
            patch.object(controller, "login", return_value=True) as mock_login,
        ):
            result = await controller.login_if_needed()

            mock_login.assert_called_once_with("test_user", "test_pass")
            assert result is True


# ============================================================
# 弹窗关闭测试
# ============================================================
class TestDismissOverlays:
    """弹窗关闭测试"""

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.login_controller import LoginController

        selector_file = tmp_path / "selectors.json"
        selector_file.write_text("{}")

        with patch("src.browser.login_controller.BrowserManager"):
            return LoginController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_dismiss_overlays_no_page(self, controller):
        """测试页面不存在时直接返回"""
        controller.browser_manager.page = None

        # 不应该抛出异常
        await controller._dismiss_overlays_if_any()

    @pytest.mark.asyncio
    async def test_dismiss_overlays_no_overlays(self, controller):
        """测试没有弹窗时直接返回"""
        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator = MagicMock(return_value=mock_locator)

        controller.browser_manager.page = mock_page

        # 不应该抛出异常
        await controller._dismiss_overlays_if_any()


# ============================================================
# 并行竞速关闭弹窗测试
# ============================================================
class TestTryCloseOverlayRace:
    """并行竞速关闭弹窗测试"""

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.login_controller import LoginController

        selector_file = tmp_path / "selectors.json"
        selector_file.write_text("{}")

        with patch("src.browser.login_controller.BrowserManager"):
            return LoginController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_try_close_overlay_race_found(self, controller):
        """测试找到并关闭弹窗"""
        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.click = AsyncMock()

        with patch(
            "src.utils.selector_race.try_selectors_race",
            return_value=mock_locator,
        ):
            result = await controller._try_close_overlay_race(
                mock_page,
                [".close"],
                timeout_ms=500,
            )

            assert result is True
            mock_locator.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_try_close_overlay_race_not_found(self, controller):
        """测试未找到弹窗"""
        mock_page = AsyncMock()

        with patch(
            "src.utils.selector_race.try_selectors_race",
            return_value=None,
        ):
            result = await controller._try_close_overlay_race(
                mock_page,
                [".close"],
                timeout_ms=500,
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_try_close_overlay_race_click_fails(self, controller):
        """测试点击关闭按钮失败"""
        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.click = AsyncMock(side_effect=Exception("Click failed"))

        with patch(
            "src.utils.selector_race.try_selectors_race",
            return_value=mock_locator,
        ):
            result = await controller._try_close_overlay_race(
                mock_page,
                [".close"],
                timeout_ms=500,
            )

            assert result is False
