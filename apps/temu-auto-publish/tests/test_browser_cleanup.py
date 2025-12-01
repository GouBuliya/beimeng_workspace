"""
@PURPOSE: 浏览器资源清理单元测试 - 验证 BrowserManager 和 LoginController 的资源清理机制
@OUTLINE:
  - TestBrowserManagerClose: 测试 BrowserManager.close() 方法
  - TestPageWaiterCleanup: 测试 PageWaiter 内存泄漏修复
  - TestLoginControllerCleanup: 测试 LoginController._cleanup_browser() 方法
  - TestBrowserValidation: 测试浏览器有效性检查
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController


class TestBrowserManagerClose:
    """测试 BrowserManager.close() 方法的资源清理."""

    @pytest.mark.asyncio
    async def test_close_cleans_all_resources_on_success(self):
        """测试正常关闭时所有资源都被清理."""
        manager = BrowserManager.__new__(BrowserManager)
        manager.config = {}
        manager.tracing_config = {}

        # Mock 所有资源
        manager.page = AsyncMock()
        manager.context = AsyncMock()
        manager.browser = AsyncMock()
        manager.playwright = AsyncMock()

        await manager.close(save_state=False)

        # 验证所有资源被置为 None
        assert manager.page is None
        assert manager.context is None
        assert manager.browser is None
        assert manager.playwright is None

    @pytest.mark.asyncio
    async def test_close_continues_after_page_close_failure(self):
        """测试 page.close() 失败后继续清理其他资源."""
        manager = BrowserManager.__new__(BrowserManager)
        manager.config = {}
        manager.tracing_config = {}

        # Mock 资源,page.close() 会失败
        manager.page = AsyncMock()
        manager.page.close = AsyncMock(side_effect=Exception("模拟 page 关闭错误"))

        # 保存引用用于后续断言(close() 会置为 None)
        context_mock = AsyncMock()
        browser_mock = AsyncMock()
        playwright_mock = AsyncMock()

        manager.context = context_mock
        manager.browser = browser_mock
        manager.playwright = playwright_mock

        # 即使 page.close() 失败,其他资源也应该被清理
        await manager.close(save_state=False)

        # 验证所有资源被置为 None
        assert manager.page is None
        assert manager.context is None
        assert manager.browser is None
        assert manager.playwright is None

        # 验证其他资源的 close 被调用
        context_mock.close.assert_called_once()
        browser_mock.close.assert_called_once()
        playwright_mock.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_timeout(self):
        """测试资源关闭超时时的处理."""
        manager = BrowserManager.__new__(BrowserManager)
        manager.config = {}
        manager.tracing_config = {}

        # Mock 资源,page.close() 会超时
        async def slow_close():
            await asyncio.sleep(10)  # 超过 5s 超时

        manager.page = AsyncMock()
        manager.page.close = slow_close
        manager.context = AsyncMock()
        manager.browser = AsyncMock()
        manager.playwright = AsyncMock()

        # 应该超时但继续清理
        await manager.close(save_state=False)

        # 验证所有资源被置为 None(即使超时)
        assert manager.page is None
        assert manager.context is None
        assert manager.browser is None
        assert manager.playwright is None

    @pytest.mark.asyncio
    async def test_close_calls_page_waiter_cleanup(self):
        """测试 close() 调用 PageWaiter 清理方法."""
        manager = BrowserManager.__new__(BrowserManager)
        manager.config = {}
        manager.tracing_config = {}

        # Mock page 带 cleanup 方法
        manager.page = AsyncMock()
        cleanup_mock = MagicMock()
        manager.page._bemg_cleanup_waiter = cleanup_mock
        manager.context = AsyncMock()
        manager.browser = AsyncMock()
        manager.playwright = AsyncMock()

        await manager.close(save_state=False)

        # 验证 cleanup 被调用
        cleanup_mock.assert_called_once()


class TestPageWaiterCleanup:
    """测试 PageWaiter 内存泄漏修复."""

    def test_patch_page_wait_adds_cleanup_method(self):
        """测试 _patch_page_wait 添加清理方法."""
        manager = BrowserManager.__new__(BrowserManager)
        manager.timing_config = {}
        manager.network_idle_trigger_ms = 1200
        manager.wait_strategy = MagicMock()
        manager.wait_strategy.wait_after_action_ms = 100

        # Mock page
        page = MagicMock()
        page._bemg_smart_wait_patched = False
        page.wait_for_timeout = AsyncMock()

        # 执行 patch
        with patch("src.browser.browser_manager.PageWaiter") as mock_waiter:
            mock_waiter.return_value = MagicMock()
            manager._patch_page_wait(page)

        # 验证清理方法存在
        assert hasattr(page, "_bemg_cleanup_waiter")
        assert callable(page._bemg_cleanup_waiter)

    def test_cleanup_waiter_resets_state(self):
        """测试清理方法重置状态."""
        manager = BrowserManager.__new__(BrowserManager)
        manager.timing_config = {}
        manager.network_idle_trigger_ms = 1200
        manager.wait_strategy = MagicMock()
        manager.wait_strategy.wait_after_action_ms = 100

        # Mock page
        original_wait = AsyncMock()
        page = MagicMock()
        page._bemg_smart_wait_patched = False
        page.wait_for_timeout = original_wait

        # 执行 patch
        with patch("src.browser.browser_manager.PageWaiter") as mock_waiter:
            mock_waiter.return_value = MagicMock()
            manager._patch_page_wait(page)

        # 验证已 patch
        assert page._bemg_smart_wait_patched is True

        # 调用清理
        page._bemg_cleanup_waiter()

        # 验证状态被重置
        assert page._bemg_smart_wait_patched is False


class TestLoginControllerCleanup:
    """测试 LoginController._cleanup_browser() 方法."""

    @pytest.mark.asyncio
    async def test_cleanup_browser_returns_results(self):
        """测试 _cleanup_browser 返回清理结果."""
        controller = LoginController.__new__(LoginController)
        controller.browser_manager = MagicMock()
        controller.browser_manager.page = AsyncMock()
        controller.browser_manager.context = AsyncMock()
        controller.browser_manager.browser = AsyncMock()
        controller.browser_manager.playwright = AsyncMock()

        results = await controller._cleanup_browser()

        # 验证返回字典
        assert isinstance(results, dict)
        assert "page" in results
        assert "context" in results
        assert "browser" in results
        assert "playwright" in results

    @pytest.mark.asyncio
    async def test_cleanup_browser_handles_failures(self):
        """测试 _cleanup_browser 处理失败情况."""
        controller = LoginController.__new__(LoginController)
        controller.browser_manager = MagicMock()

        # page.close() 失败
        controller.browser_manager.page = AsyncMock()
        controller.browser_manager.page.close = AsyncMock(side_effect=Exception("模拟错误"))

        controller.browser_manager.context = AsyncMock()
        controller.browser_manager.browser = AsyncMock()
        controller.browser_manager.playwright = AsyncMock()

        results = await controller._cleanup_browser()

        # 验证 page 清理失败
        assert results["page"] is False

        # 验证其他资源清理成功
        assert results["context"] is True
        assert results["browser"] is True
        assert results["playwright"] is True

        # 验证资源被置为 None
        assert controller.browser_manager.page is None
        assert controller.browser_manager.context is None

    @pytest.mark.asyncio
    async def test_cleanup_browser_cleans_page_waiter(self):
        """测试 _cleanup_browser 清理 PageWaiter."""
        controller = LoginController.__new__(LoginController)
        controller.browser_manager = MagicMock()

        # Mock page 带 cleanup 方法
        controller.browser_manager.page = AsyncMock()
        cleanup_mock = MagicMock()
        controller.browser_manager.page._bemg_cleanup_waiter = cleanup_mock

        controller.browser_manager.context = AsyncMock()
        controller.browser_manager.browser = AsyncMock()
        controller.browser_manager.playwright = AsyncMock()

        results = await controller._cleanup_browser()

        # 验证 PageWaiter 清理被调用
        cleanup_mock.assert_called_once()
        assert results["page_waiter"] is True


class TestBrowserValidation:
    """测试浏览器有效性检查."""

    @pytest.mark.asyncio
    async def test_is_browser_valid_returns_false_when_no_page(self):
        """测试没有 page 时返回 False."""
        controller = LoginController.__new__(LoginController)
        controller.browser_manager = MagicMock()
        controller.browser_manager.playwright = MagicMock()
        controller.browser_manager.browser = MagicMock()
        controller.browser_manager.context = MagicMock()
        controller.browser_manager.page = None

        result = await controller._is_browser_valid()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_browser_valid_returns_false_when_disconnected(self):
        """测试浏览器断开连接时返回 False."""
        controller = LoginController.__new__(LoginController)
        controller.browser_manager = MagicMock()
        controller.browser_manager.playwright = MagicMock()
        controller.browser_manager.browser = MagicMock()
        controller.browser_manager.browser.is_connected.return_value = False
        controller.browser_manager.context = MagicMock()
        controller.browser_manager.page = MagicMock()

        result = await controller._is_browser_valid()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_browser_valid_returns_false_on_evaluate_timeout(self):
        """测试 evaluate 超时时返回 False."""
        controller = LoginController.__new__(LoginController)
        controller.browser_manager = MagicMock()
        controller.browser_manager.playwright = MagicMock()
        controller.browser_manager.browser = MagicMock()
        controller.browser_manager.browser.is_connected.return_value = True
        controller.browser_manager.context = MagicMock()
        controller.browser_manager.context.pages = [MagicMock()]

        # evaluate 会超时
        async def slow_evaluate(_):
            await asyncio.sleep(10)

        controller.browser_manager.page = MagicMock()
        controller.browser_manager.page.evaluate = slow_evaluate

        result = await controller._is_browser_valid()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_browser_valid_returns_true_when_all_checks_pass(self):
        """测试所有检查通过时返回 True."""
        controller = LoginController.__new__(LoginController)
        controller.browser_manager = MagicMock()
        controller.browser_manager.playwright = MagicMock()
        controller.browser_manager.browser = MagicMock()
        controller.browser_manager.browser.is_connected.return_value = True
        controller.browser_manager.context = MagicMock()
        controller.browser_manager.context.pages = [MagicMock()]

        # evaluate 返回正常状态
        async def mock_evaluate(_):
            return "complete"

        controller.browser_manager.page = MagicMock()
        controller.browser_manager.page.evaluate = mock_evaluate

        result = await controller._is_browser_valid()
        assert result is True


class TestResourceCleanupIntegration:
    """资源清理集成测试."""

    @pytest.mark.asyncio
    async def test_multiple_close_calls_are_safe(self):
        """测试多次调用 close() 是安全的."""
        manager = BrowserManager.__new__(BrowserManager)
        manager.config = {}
        manager.tracing_config = {}
        manager.page = None
        manager.context = None
        manager.browser = None
        manager.playwright = None

        # 多次调用 close 不应该抛出异常
        await manager.close(save_state=False)
        await manager.close(save_state=False)
        await manager.close(save_state=False)

        # 验证状态保持为 None
        assert manager.page is None
        assert manager.context is None
        assert manager.browser is None
        assert manager.playwright is None
