"""
@PURPOSE: PageWaiter 页面等待器完整测试
@OUTLINE:
  - TestPageWaiterInit: 初始化测试
  - TestPostActionWait: post_action_wait 方法测试
  - TestWaitForNetworkIdle: wait_for_network_idle 方法测试
  - TestWaitForDomStable: wait_for_dom_stable 方法测试
  - TestApplyRetryBackoff: apply_retry_backoff 方法测试
  - TestWaitForCondition: wait_for_condition 方法测试
  - TestSafeClick: safe_click 方法测试
  - TestSafeFill: safe_fill 方法测试
  - TestWaitForLocatorHidden: wait_for_locator_hidden 方法测试
  - TestEnsureDomReady: ensure_dom_ready 装饰器测试
@DEPENDENCIES:
  - 内部: utils.page_waiter
  - 外部: pytest, pytest-asyncio, unittest.mock
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.utils.page_waiter import PageWaiter, WaitStrategy, ensure_dom_ready


# ============================================================
# PageWaiter 初始化测试
# ============================================================
class TestPageWaiterInit:
    """PageWaiter 初始化测试"""

    def test_init_with_default_strategy(self):
        """测试使用默认策略初始化"""
        mock_page = MagicMock()

        waiter = PageWaiter(mock_page)

        assert waiter.page is mock_page
        assert waiter.strategy is not None
        assert isinstance(waiter.strategy, WaitStrategy)

    def test_init_with_custom_strategy(self):
        """测试使用自定义策略初始化"""
        mock_page = MagicMock()
        custom_strategy = WaitStrategy(wait_after_action_ms=500)

        waiter = PageWaiter(mock_page, strategy=custom_strategy)

        assert waiter.strategy.wait_after_action_ms == 500


# ============================================================
# post_action_wait 测试
# ============================================================
class TestPostActionWait:
    """post_action_wait 方法测试"""

    @pytest.fixture
    def mock_page(self):
        """创建 mock page"""
        page = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.evaluate = AsyncMock(return_value=[100, 50])
        return page

    @pytest.mark.asyncio
    async def test_post_action_wait_default(self, mock_page):
        """测试默认等待"""
        waiter = PageWaiter(mock_page)
        waiter.wait_for_network_idle = AsyncMock()
        waiter.wait_for_dom_stable = AsyncMock(return_value=True)

        await waiter.post_action_wait()

        waiter.wait_for_network_idle.assert_called_once()
        waiter.wait_for_dom_stable.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_action_wait_network_only(self, mock_page):
        """测试只等待网络"""
        waiter = PageWaiter(mock_page)
        waiter.wait_for_network_idle = AsyncMock()
        waiter.wait_for_dom_stable = AsyncMock(return_value=True)

        await waiter.post_action_wait(wait_for_network_idle=True, wait_for_dom_stable=False)

        waiter.wait_for_network_idle.assert_called_once()
        waiter.wait_for_dom_stable.assert_not_called()

    @pytest.mark.asyncio
    async def test_post_action_wait_dom_only(self, mock_page):
        """测试只等待 DOM"""
        waiter = PageWaiter(mock_page)
        waiter.wait_for_network_idle = AsyncMock()
        waiter.wait_for_dom_stable = AsyncMock(return_value=True)

        await waiter.post_action_wait(wait_for_network_idle=False, wait_for_dom_stable=True)

        waiter.wait_for_network_idle.assert_not_called()
        waiter.wait_for_dom_stable.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_action_wait_no_waits(self, mock_page):
        """测试不等待时使用固定延迟"""
        waiter = PageWaiter(mock_page)
        waiter.strategy = WaitStrategy(wait_after_action_ms=100)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await waiter.post_action_wait(wait_for_network_idle=False, wait_for_dom_stable=False)

            mock_sleep.assert_called_once_with(0.1)  # 100ms


# ============================================================
# wait_for_network_idle 测试
# ============================================================
class TestWaitForNetworkIdle:
    """wait_for_network_idle 方法测试"""

    @pytest.mark.asyncio
    async def test_network_idle_success(self):
        """测试成功等待网络空闲"""
        mock_page = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()

        waiter = PageWaiter(mock_page)

        await waiter.wait_for_network_idle()

        mock_page.wait_for_load_state.assert_called_once_with(
            "networkidle", timeout=waiter.strategy.wait_for_network_idle_timeout_ms
        )

    @pytest.mark.asyncio
    async def test_network_idle_timeout(self):
        """测试等待超时"""
        mock_page = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout"))

        waiter = PageWaiter(mock_page)

        # 不应该抛出异常
        await waiter.wait_for_network_idle()

    @pytest.mark.asyncio
    async def test_network_idle_custom_timeout(self):
        """测试自定义超时"""
        mock_page = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()

        waiter = PageWaiter(mock_page)

        await waiter.wait_for_network_idle(timeout_ms=10000)

        mock_page.wait_for_load_state.assert_called_once_with("networkidle", timeout=10000)


# ============================================================
# wait_for_dom_stable 测试
# ============================================================
class TestWaitForDomStable:
    """wait_for_dom_stable 方法测试"""

    @pytest.fixture
    def mock_page(self):
        """创建 mock page"""
        page = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_dom_stable_quick_check_success(self, mock_page):
        """测试快速检测成功"""
        # DOM 快照连续两次相同
        mock_page.evaluate = AsyncMock(return_value=[100, 50])

        waiter = PageWaiter(mock_page)

        result = await waiter.wait_for_dom_stable()

        assert result is True

    @pytest.mark.asyncio
    async def test_dom_stable_standard_check_success(self, mock_page):
        """测试标准检测成功"""
        # 快速检测失败（不同快照），然后标准检测成功
        call_count = [0]

        async def mock_evaluate(_):
            call_count[0] += 1
            if call_count[0] <= 2:  # 快速检测
                return [100 + call_count[0], 50]  # 不同快照
            else:  # 标准检测
                return [200, 60]  # 相同快照

        mock_page.evaluate = mock_evaluate

        waiter = PageWaiter(mock_page, strategy=WaitStrategy(dom_stable_checks=2))

        result = await waiter.wait_for_dom_stable(timeout_ms=5000)

        assert result is True

    @pytest.mark.asyncio
    async def test_dom_stable_disable_quick_check(self, mock_page):
        """测试禁用快速检测"""
        mock_page.evaluate = AsyncMock(return_value=[100, 50])

        waiter = PageWaiter(mock_page, strategy=WaitStrategy(dom_stable_checks=1))

        result = await waiter.wait_for_dom_stable(enable_quick_check=False, timeout_ms=1000)

        assert result is True

    @pytest.mark.asyncio
    async def test_dom_stable_timeout(self, mock_page):
        """测试等待超时"""
        # 快照一直变化
        counter = [0]

        async def mock_evaluate(_):
            counter[0] += 1
            return [counter[0], counter[0]]  # 每次不同

        mock_page.evaluate = mock_evaluate

        waiter = PageWaiter(mock_page)

        result = await waiter.wait_for_dom_stable(timeout_ms=100)

        assert result is False

    @pytest.mark.asyncio
    async def test_dom_stable_exception_handling(self, mock_page):
        """测试异常处理"""
        mock_page.evaluate = AsyncMock(side_effect=Exception("评估失败"))

        waiter = PageWaiter(mock_page)

        result = await waiter.wait_for_dom_stable(timeout_ms=100)

        assert result is False


# ============================================================
# apply_retry_backoff 测试
# ============================================================
class TestApplyRetryBackoff:
    """apply_retry_backoff 方法测试"""

    @pytest.mark.asyncio
    async def test_retry_backoff_first_attempt(self):
        """测试第一次重试"""
        mock_page = MagicMock()
        waiter = PageWaiter(mock_page)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await waiter.apply_retry_backoff(0)

            mock_sleep.assert_called_once()
            # 默认: 200ms * 1.5^0 = 200ms = 0.2s
            call_args = mock_sleep.call_args[0][0]
            assert 0.19 <= call_args <= 0.21

    @pytest.mark.asyncio
    async def test_retry_backoff_multiple_attempts(self):
        """测试多次重试的指数退避"""
        mock_page = MagicMock()
        strategy = WaitStrategy(
            retry_initial_delay_ms=100, retry_backoff_factor=2.0, retry_max_delay_ms=10000
        )
        waiter = PageWaiter(mock_page, strategy=strategy)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # 第一次: 100ms
            await waiter.apply_retry_backoff(0)
            assert mock_sleep.call_args[0][0] == pytest.approx(0.1)

            # 第二次: 200ms
            await waiter.apply_retry_backoff(1)
            assert mock_sleep.call_args[0][0] == pytest.approx(0.2)

            # 第三次: 400ms
            await waiter.apply_retry_backoff(2)
            assert mock_sleep.call_args[0][0] == pytest.approx(0.4)


# ============================================================
# wait_for_condition 测试
# ============================================================
class TestWaitForCondition:
    """wait_for_condition 方法测试"""

    @pytest.mark.asyncio
    async def test_condition_success_immediately(self):
        """测试条件立即满足"""
        mock_page = MagicMock()
        waiter = PageWaiter(mock_page)

        async def condition(_):
            return True

        result = await waiter.wait_for_condition(condition)

        assert result is True

    @pytest.mark.asyncio
    async def test_condition_success_after_retries(self):
        """测试条件重试后满足"""
        mock_page = MagicMock()
        waiter = PageWaiter(mock_page)

        call_count = [0]

        async def condition(_):
            call_count[0] += 1
            return call_count[0] >= 3

        result = await waiter.wait_for_condition(condition, timeout_ms=2000, interval_ms=50)

        assert result is True
        assert call_count[0] >= 3

    @pytest.mark.asyncio
    async def test_condition_timeout(self):
        """测试条件超时"""
        mock_page = MagicMock()
        waiter = PageWaiter(mock_page)

        async def condition(_):
            return False

        result = await waiter.wait_for_condition(condition, timeout_ms=100, interval_ms=20)

        assert result is False

    @pytest.mark.asyncio
    async def test_condition_exception_handling(self):
        """测试条件异常处理"""
        mock_page = MagicMock()
        waiter = PageWaiter(mock_page)

        call_count = [0]

        async def condition(_):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("检查失败")
            return True

        result = await waiter.wait_for_condition(condition, timeout_ms=2000, interval_ms=50)

        assert result is True


# ============================================================
# safe_click 测试
# ============================================================
class TestSafeClick:
    """safe_click 方法测试"""

    @pytest.fixture
    def mock_page(self):
        """创建 mock page"""
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=[100, 50])
        return page

    @pytest.mark.asyncio
    async def test_safe_click_success(self, mock_page):
        """测试成功点击"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.is_enabled = AsyncMock(return_value=True)
        mock_locator.first.scroll_into_view_if_needed = AsyncMock()
        mock_locator.first.click = AsyncMock()

        waiter = PageWaiter(mock_page)
        waiter.post_action_wait = AsyncMock()

        result = await waiter.safe_click(mock_locator)

        assert result is True
        mock_locator.first.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_safe_click_none_locator(self, mock_page):
        """测试 None locator"""
        waiter = PageWaiter(mock_page)

        result = await waiter.safe_click(None)

        assert result is False

    @pytest.mark.asyncio
    async def test_safe_click_element_disabled(self, mock_page):
        """测试元素禁用"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.is_enabled = AsyncMock(return_value=False)

        waiter = PageWaiter(mock_page)

        result = await waiter.safe_click(mock_locator)

        assert result is False

    @pytest.mark.asyncio
    async def test_safe_click_timeout(self, mock_page):
        """测试点击超时"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout"))

        waiter = PageWaiter(mock_page)

        result = await waiter.safe_click(mock_locator)

        assert result is False

    @pytest.mark.asyncio
    async def test_safe_click_quick_wait(self, mock_page):
        """测试快速等待模式"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.is_enabled = AsyncMock(return_value=True)
        mock_locator.first.scroll_into_view_if_needed = AsyncMock()
        mock_locator.first.click = AsyncMock()

        waiter = PageWaiter(mock_page)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await waiter.safe_click(mock_locator, quick_wait=True)

            assert result is True
            mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_safe_click_no_scroll(self, mock_page):
        """测试禁用滚动"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.is_enabled = AsyncMock(return_value=True)
        mock_locator.first.scroll_into_view_if_needed = AsyncMock()
        mock_locator.first.click = AsyncMock()

        waiter = PageWaiter(mock_page)
        waiter.post_action_wait = AsyncMock()

        await waiter.safe_click(mock_locator, scroll=False)

        mock_locator.first.scroll_into_view_if_needed.assert_not_called()

    @pytest.mark.asyncio
    async def test_safe_click_force(self, mock_page):
        """测试强制点击"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.is_enabled = AsyncMock(return_value=True)
        mock_locator.first.scroll_into_view_if_needed = AsyncMock()
        mock_locator.first.click = AsyncMock()

        waiter = PageWaiter(mock_page)
        waiter.post_action_wait = AsyncMock()

        await waiter.safe_click(mock_locator, force=True)

        call_kwargs = mock_locator.first.click.call_args[1]
        assert call_kwargs["force"] is True


# ============================================================
# safe_fill 测试
# ============================================================
class TestSafeFill:
    """safe_fill 方法测试"""

    @pytest.fixture
    def mock_page(self):
        """创建 mock page"""
        page = AsyncMock()
        page.evaluate = AsyncMock(return_value=[100, 50])
        return page

    @pytest.mark.asyncio
    async def test_safe_fill_success(self, mock_page):
        """测试成功填充"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.fill = AsyncMock()

        waiter = PageWaiter(mock_page)
        waiter.post_action_wait = AsyncMock()

        result = await waiter.safe_fill(mock_locator, "test value")

        assert result is True
        mock_locator.first.fill.assert_called_once_with(
            "test value", timeout=waiter.strategy.validation_timeout_ms
        )

    @pytest.mark.asyncio
    async def test_safe_fill_none_locator(self, mock_page):
        """测试 None locator"""
        waiter = PageWaiter(mock_page)

        result = await waiter.safe_fill(None, "test")

        assert result is False

    @pytest.mark.asyncio
    async def test_safe_fill_with_click_first(self, mock_page):
        """测试先点击再填充"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.click = AsyncMock()
        mock_locator.first.fill = AsyncMock()

        waiter = PageWaiter(mock_page)
        waiter.post_action_wait = AsyncMock()

        result = await waiter.safe_fill(mock_locator, "test", click_first=True)

        assert result is True
        mock_locator.first.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_safe_fill_no_clear(self, mock_page):
        """测试不清除使用 type"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.type = AsyncMock()

        waiter = PageWaiter(mock_page)
        waiter.post_action_wait = AsyncMock()

        result = await waiter.safe_fill(mock_locator, "test", clear=False)

        assert result is True
        mock_locator.first.type.assert_called_once()

    @pytest.mark.asyncio
    async def test_safe_fill_timeout(self, mock_page):
        """测试填充超时"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout"))

        waiter = PageWaiter(mock_page)

        result = await waiter.safe_fill(mock_locator, "test")

        assert result is False

    @pytest.mark.asyncio
    async def test_safe_fill_quick_wait(self, mock_page):
        """测试快速等待模式"""
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.fill = AsyncMock()

        waiter = PageWaiter(mock_page)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await waiter.safe_fill(mock_locator, "test", quick_wait=True)

            assert result is True
            mock_sleep.assert_called()


# ============================================================
# wait_for_locator_hidden 测试
# ============================================================
class TestWaitForLocatorHidden:
    """wait_for_locator_hidden 方法测试"""

    @pytest.mark.asyncio
    async def test_hidden_success(self):
        """测试成功等待隐藏"""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.wait_for = AsyncMock()

        waiter = PageWaiter(mock_page)

        result = await waiter.wait_for_locator_hidden(mock_locator)

        assert result is True
        mock_locator.wait_for.assert_called_once_with(
            state="hidden", timeout=waiter.strategy.validation_timeout_ms
        )

    @pytest.mark.asyncio
    async def test_hidden_timeout(self):
        """测试等待超时"""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout"))

        waiter = PageWaiter(mock_page)

        result = await waiter.wait_for_locator_hidden(mock_locator)

        assert result is False

    @pytest.mark.asyncio
    async def test_hidden_custom_timeout(self):
        """测试自定义超时"""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.wait_for = AsyncMock()

        waiter = PageWaiter(mock_page)

        await waiter.wait_for_locator_hidden(mock_locator, timeout_ms=5000)

        mock_locator.wait_for.assert_called_once_with(state="hidden", timeout=5000)


# ============================================================
# ensure_dom_ready 装饰器测试
# ============================================================
class TestEnsureDomReady:
    """ensure_dom_ready 装饰器测试"""

    @pytest.mark.asyncio
    async def test_decorator_with_page_kwarg(self):
        """测试通过 kwargs 传递 page"""
        from playwright.async_api import Page

        mock_page = MagicMock(spec=Page)
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[100, 50])
        mock_page._bemg_dom_ready_guard = False

        @ensure_dom_ready
        async def test_func(page=None):
            return "result"

        result = await test_func(page=mock_page)

        assert result == "result"
        mock_page.wait_for_load_state.assert_called_once_with("domcontentloaded")

    @pytest.mark.asyncio
    async def test_decorator_without_page(self):
        """测试无 page 参数"""

        @ensure_dom_ready
        async def test_func(data):
            return data * 2

        result = await test_func(5)

        assert result == 10

    @pytest.mark.asyncio
    async def test_decorator_guard_prevents_double_wait(self):
        """测试防护机制防止重复等待"""
        mock_page = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[100, 50])
        mock_page._bemg_dom_ready_guard = True  # 模拟已激活

        @ensure_dom_ready
        async def test_func(page=None):
            return "result"

        result = await test_func(page=mock_page)

        assert result == "result"
        # 由于 guard 已激活，不应调用 wait_for_load_state
        mock_page.wait_for_load_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_decorator_with_page_in_args(self):
        """测试通过 args 传递 page"""
        from playwright.async_api import Page

        mock_page = MagicMock(spec=Page)
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[100, 50])
        mock_page._bemg_dom_ready_guard = False

        @ensure_dom_ready
        async def test_func(self, page):
            return "result"

        result = await test_func("self", mock_page)

        assert result == "result"


# ============================================================
# 边界情况测试
# ============================================================
class TestPageWaiterEdgeCases:
    """PageWaiter 边界情况测试"""

    @pytest.mark.asyncio
    async def test_scroll_exception_handled(self):
        """测试滚动异常被处理"""
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[100, 50])

        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.is_enabled = AsyncMock(return_value=True)
        mock_locator.first.scroll_into_view_if_needed = AsyncMock(side_effect=Exception("滚动失败"))
        mock_locator.first.click = AsyncMock()

        waiter = PageWaiter(mock_page)
        waiter.post_action_wait = AsyncMock()

        # 滚动失败不应该阻止点击
        result = await waiter.safe_click(mock_locator)

        assert result is True

    @pytest.mark.asyncio
    async def test_click_first_exception_handled(self):
        """测试预点击异常被处理"""
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[100, 50])

        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.click = AsyncMock(side_effect=[Exception("点击失败"), None])
        mock_locator.first.fill = AsyncMock()

        waiter = PageWaiter(mock_page)
        waiter.post_action_wait = AsyncMock()

        # 预点击失败不应该阻止填充
        result = await waiter.safe_fill(mock_locator, "test", click_first=True)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_enabled_exception_handled(self):
        """测试 is_enabled 异常被处理"""
        mock_page = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=[100, 50])

        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.first.is_enabled = AsyncMock(side_effect=Exception("检查失败"))
        mock_locator.first.scroll_into_view_if_needed = AsyncMock()
        mock_locator.first.click = AsyncMock()

        waiter = PageWaiter(mock_page)
        waiter.post_action_wait = AsyncMock()

        # is_enabled 异常不应该阻止点击
        result = await waiter.safe_click(mock_locator)

        assert result is True
