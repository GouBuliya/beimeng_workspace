"""
@PURPOSE: 测试浏览器管理器功能
@OUTLINE:
  - TestBrowserManagerInit: 测试初始化
  - TestBrowserManagerConfig: 测试配置加载
  - TestBrowserManagerOperations: 测试浏览器操作
  - TestBrowserManagerCookies: 测试Cookie管理
  - TestBrowserManagerHelpers: 测试辅助方法
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.browser.browser_manager, tests.mocks
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from src.browser.browser_manager import BrowserManager


class TestBrowserManagerInit:
    """测试 BrowserManager 初始化"""

    def test_init_with_default_config(self, tmp_path):
        """测试使用默认配置初始化"""
        # 创建一个临时配置文件
        config_file = tmp_path / "config" / "browser_config.json"
        config_file.parent.mkdir(parents=True, exist_ok=True)

        config = {
            "browser": {"type": "chromium", "headless": False},
            "timeouts": {"default": 30000},
            "timing": {"slow_mo_ms": 100},
        }
        config_file.write_text(json.dumps(config))

        manager = BrowserManager(config_path=str(config_file))

        assert manager.config is not None
        assert manager.playwright is None
        assert manager.browser is None
        assert manager.page is None

    def test_init_with_missing_config(self, tmp_path):
        """测试配置文件不存在时使用默认配置"""
        nonexistent = tmp_path / "nonexistent.json"

        manager = BrowserManager(config_path=str(nonexistent))

        # 应该使用默认配置
        assert manager.config is not None
        assert "browser" in manager.config
        assert manager.config["browser"]["type"] == "chromium"

    def test_init_with_custom_config(self, tmp_path):
        """测试自定义配置"""
        config_file = tmp_path / "custom_config.json"

        config = {
            "browser": {
                "type": "firefox",
                "headless": True,
                "window_width": 1920,
                "window_height": 1080,
            },
            "timeouts": {"default": 60000},
            "timing": {"slow_mo_ms": 200, "wait_after_action_ms": 100},
        }
        config_file.write_text(json.dumps(config))

        manager = BrowserManager(config_path=str(config_file))

        assert manager.config["browser"]["type"] == "firefox"
        assert manager.config["browser"]["headless"] is True


class TestBrowserManagerConfig:
    """测试配置加载功能"""

    def test_load_config_success(self, tmp_path):
        """测试成功加载配置"""
        config_file = tmp_path / "config.json"
        config = {
            "browser": {"type": "chromium"},
            "stealth": {"enabled": True},
            "timing": {"slow_mo_ms": 50, "network_idle_trigger_ms": 1000},
        }
        config_file.write_text(json.dumps(config))

        manager = BrowserManager(config_path=str(config_file))

        assert manager.config["stealth"]["enabled"] is True
        assert manager.timing_config.get("slow_mo_ms") == 50

    def test_timing_config_defaults(self, tmp_path):
        """测试时序配置默认值"""
        config_file = tmp_path / "minimal.json"
        config = {"browser": {"type": "chromium"}}
        config_file.write_text(json.dumps(config))

        manager = BrowserManager(config_path=str(config_file))

        # 应该有默认的时序配置
        assert manager.timing_config is not None
        assert manager.wait_strategy is not None


class TestBrowserManagerOperations:
    """测试浏览器操作"""

    @pytest.mark.asyncio
    async def test_start_and_close(self, tmp_path):
        """测试启动和关闭浏览器(使用Mock)"""
        config_file = tmp_path / "config.json"
        config = {
            "browser": {"type": "chromium", "headless": True},
            "timeouts": {"default": 5000},
            "timing": {"slow_mo_ms": 0},
        }
        config_file.write_text(json.dumps(config))

        manager = BrowserManager(config_path=str(config_file))

        # Mock Playwright
        with patch("src.browser.browser_manager.async_playwright") as mock_playwright:
            mock_pw = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_pw.start = AsyncMock(return_value=mock_pw)
            mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_context.add_init_script = AsyncMock()

            mock_playwright.return_value.start = AsyncMock(return_value=mock_pw)

            await manager.start(headless=True)

            # 验证浏览器已启动
            assert manager.playwright is not None

    @pytest.mark.asyncio
    async def test_goto_without_browser_raises(self):
        """测试未启动浏览器时导航应该抛出异常"""
        manager = BrowserManager()

        with pytest.raises(RuntimeError, match="浏览器未启动"):
            await manager.goto("https://example.com")

    @pytest.mark.asyncio
    async def test_screenshot_without_browser_raises(self):
        """测试未启动浏览器时截图应该抛出异常"""
        manager = BrowserManager()

        with pytest.raises(RuntimeError, match="浏览器未启动"):
            await manager.screenshot("test.png")


class TestBrowserManagerCookies:
    """测试Cookie管理"""

    @pytest.mark.asyncio
    async def test_save_cookies(self, tmp_path):
        """测试保存Cookies"""
        manager = BrowserManager()

        # 模拟已启动的浏览器
        mock_context = AsyncMock()
        mock_context.cookies = AsyncMock(
            return_value=[{"name": "session", "value": "abc123", "domain": "example.com"}]
        )
        manager.context = mock_context

        cookie_file = tmp_path / "cookies.json"
        await manager.save_cookies(str(cookie_file))

        # 验证文件已创建
        assert cookie_file.exists()

        # 验证内容
        with open(cookie_file) as f:
            cookies = json.load(f)
        assert len(cookies) == 1
        assert cookies[0]["name"] == "session"

    @pytest.mark.asyncio
    async def test_load_cookies_success(self, tmp_path):
        """测试成功加载Cookies"""
        manager = BrowserManager()

        # 创建Cookie文件
        cookie_file = tmp_path / "cookies.json"
        cookies = [{"name": "session", "value": "abc123", "domain": "example.com"}]
        cookie_file.write_text(json.dumps(cookies))

        # 模拟已启动的浏览器
        mock_context = AsyncMock()
        mock_context.add_cookies = AsyncMock()
        manager.context = mock_context

        result = await manager.load_cookies(str(cookie_file))

        assert result is True
        mock_context.add_cookies.assert_called_once_with(cookies)

    @pytest.mark.asyncio
    async def test_load_cookies_file_not_found(self, tmp_path):
        """测试加载不存在的Cookie文件"""
        manager = BrowserManager()

        mock_context = AsyncMock()
        manager.context = mock_context

        nonexistent = tmp_path / "nonexistent.json"
        result = await manager.load_cookies(str(nonexistent))

        assert result is False

    @pytest.mark.asyncio
    async def test_save_cookies_without_browser_raises(self):
        """测试未启动浏览器时保存Cookies应该抛出异常"""
        manager = BrowserManager()

        with pytest.raises(RuntimeError, match="浏览器未启动"):
            await manager.save_cookies("cookies.json")


class TestBrowserManagerHelpers:
    """测试辅助方法"""

    def test_merge_launch_args(self):
        """测试合并启动参数"""
        base = ["--arg1", "--arg2"]
        extra = ["--arg2", "--arg3", "--arg4"]

        result = BrowserManager._merge_launch_args(base, extra)

        # 应该去重
        assert len(result) == 4
        assert "--arg1" in result
        assert "--arg2" in result
        assert "--arg3" in result
        assert "--arg4" in result

    def test_merge_launch_args_empty(self):
        """测试合并空参数"""
        base = ["--arg1"]
        extra = []

        result = BrowserManager._merge_launch_args(base, extra)

        assert result == ["--arg1"]

    def test_collect_channel_candidates_with_config(self):
        """测试收集渠道候选(有配置)"""
        config = {"channel": "chrome", "channel_fallbacks": ["msedge", "chromium"]}

        candidates = BrowserManager._collect_channel_candidates(config)

        # 应该包含配置的渠道和默认回退
        assert "chrome" in candidates
        assert "msedge" in candidates
        assert candidates[0] == "chrome"  # 配置的应该在前面

    def test_collect_channel_candidates_default(self):
        """测试收集渠道候选(无配置)"""
        config = {}

        candidates = BrowserManager._collect_channel_candidates(config)

        # 应该有默认候选
        assert "msedge" in candidates
        assert "chrome" in candidates

    def test_pick_user_agent_explicit(self):
        """测试选择显式指定的User-Agent"""
        config = {"user_agent": "Mozilla/5.0 Custom"}

        ua = BrowserManager._pick_user_agent(config)

        assert ua == "Mozilla/5.0 Custom"

    def test_pick_user_agent_from_list(self):
        """测试从列表随机选择User-Agent"""
        config = {"user_agents": ["Mozilla/5.0 UA1", "Mozilla/5.0 UA2", "Mozilla/5.0 UA3"]}

        ua = BrowserManager._pick_user_agent(config)

        assert ua in config["user_agents"]

    def test_pick_user_agent_none(self):
        """测试无User-Agent配置"""
        config = {}

        ua = BrowserManager._pick_user_agent(config)

        assert ua is None

    def test_build_wait_strategy(self, tmp_path):
        """测试构建等待策略"""
        config_file = tmp_path / "config.json"
        config = {
            "browser": {"type": "chromium"},
            "timing": {
                "wait_after_action_ms": 200,
                "wait_for_stability_timeout_ms": 2000,
                "retry_initial_delay_ms": 100,
            },
        }
        config_file.write_text(json.dumps(config))

        manager = BrowserManager(config_path=str(config_file))
        strategy = manager.wait_strategy

        assert strategy.wait_after_action_ms == 200
        assert strategy.wait_for_stability_timeout_ms == 2000
        assert strategy.retry_initial_delay_ms == 100


class TestBrowserManagerContextManager:
    """测试上下文管理器"""

    @pytest.mark.asyncio
    async def test_context_manager_success(self, tmp_path):
        """测试上下文管理器正常使用"""
        config_file = tmp_path / "config.json"
        config = {"browser": {"type": "chromium", "headless": True}, "timeouts": {"default": 5000}}
        config_file.write_text(json.dumps(config))

        with patch("src.browser.browser_manager.async_playwright") as mock_pw:
            mock_playwright_instance = AsyncMock()
            mock_browser = AsyncMock()
            mock_context = AsyncMock()
            mock_page = AsyncMock()

            mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
            mock_browser.new_context = AsyncMock(return_value=mock_context)
            mock_context.new_page = AsyncMock(return_value=mock_page)
            mock_context.add_init_script = AsyncMock()

            mock_pw.return_value.start = AsyncMock(return_value=mock_playwright_instance)

            manager = BrowserManager(config_path=str(config_file))

            async with manager:
                pass  # 正常进入和退出

            # 验证关闭方法被调用
            mock_page.close.assert_called()
