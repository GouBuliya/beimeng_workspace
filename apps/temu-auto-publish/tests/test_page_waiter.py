"""
@PURPOSE: 测试页面等待工具
@OUTLINE:
  - TestWaitStrategy: 测试等待策略配置
  - TestPageWaiter: 测试页面等待工具
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.utils.page_waiter
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from src.utils.page_waiter import WaitStrategy, PageWaiter


class TestWaitStrategy:
    """测试等待策略配置"""
    
    def test_default_values(self):
        """测试默认值"""
        strategy = WaitStrategy()
        
        assert strategy.wait_after_action_ms == 30
        assert strategy.wait_for_stability_timeout_ms == 375
        assert strategy.wait_for_network_idle_timeout_ms == 750
        assert strategy.retry_initial_delay_ms == 30
        assert strategy.retry_backoff_factor == 1.6
        assert strategy.retry_max_delay_ms == 375
        assert strategy.validation_timeout_ms == 500
        assert strategy.dom_stable_checks == 3
        assert strategy.dom_stable_interval_ms == 30
    
    def test_custom_values(self):
        """测试自定义值"""
        strategy = WaitStrategy(
            wait_after_action_ms=100,
            wait_for_stability_timeout_ms=1000,
            retry_initial_delay_ms=50
        )
        
        assert strategy.wait_after_action_ms == 100
        assert strategy.wait_for_stability_timeout_ms == 1000
        assert strategy.retry_initial_delay_ms == 50
    
    def test_next_retry_delay_first_attempt(self):
        """测试第一次重试延迟"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=2.0,
            retry_max_delay_ms=1000
        )
        
        delay = strategy.next_retry_delay(0)
        
        # 第0次尝试: 100 * (2.0 ** 0) = 100ms = 0.1s
        assert delay == 0.1
    
    def test_next_retry_delay_exponential(self):
        """测试指数退避延迟"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=2.0,
            retry_max_delay_ms=10000
        )
        
        # 第1次: 100 * 2 = 200ms
        assert strategy.next_retry_delay(1) == 0.2
        
        # 第2次: 100 * 4 = 400ms
        assert strategy.next_retry_delay(2) == 0.4
        
        # 第3次: 100 * 8 = 800ms
        assert strategy.next_retry_delay(3) == 0.8
    
    def test_next_retry_delay_capped(self):
        """测试延迟上限"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=2.0,
            retry_max_delay_ms=500
        )
        
        # 第10次: 100 * 1024 = 102400ms, 但应该被限制在500ms
        delay = strategy.next_retry_delay(10)
        
        assert delay == 0.5  # 500ms = 0.5s


class TestPageWaiter:
    """测试页面等待工具"""
    
    @pytest.fixture
    def mock_page(self):
        """创建Mock页面"""
        page = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.evaluate = AsyncMock(return_value=100)  # 返回DOM元素数量
        return page
    
    def test_init_with_default_strategy(self, mock_page):
        """测试使用默认策略初始化"""
        waiter = PageWaiter(mock_page)
        
        assert waiter.page == mock_page
        assert waiter.strategy is not None
        assert isinstance(waiter.strategy, WaitStrategy)
    
    def test_init_with_custom_strategy(self, mock_page):
        """测试使用自定义策略初始化"""
        custom_strategy = WaitStrategy(
            wait_after_action_ms=200,
            dom_stable_checks=5
        )
        
        waiter = PageWaiter(mock_page, strategy=custom_strategy)
        
        assert waiter.strategy.wait_after_action_ms == 200
        assert waiter.strategy.dom_stable_checks == 5
    
    @pytest.mark.asyncio
    async def test_post_action_wait(self, mock_page):
        """测试操作后等待"""
        waiter = PageWaiter(mock_page)
        
        # Mock内部方法
        waiter.wait_for_network_idle = AsyncMock()
        waiter.wait_for_dom_stable = AsyncMock()
        
        await waiter.post_action_wait(
            wait_for_network_idle=True,
            wait_for_dom_stable=True
        )
        
        waiter.wait_for_network_idle.assert_called_once()
        waiter.wait_for_dom_stable.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_post_action_wait_no_network(self, mock_page):
        """测试不等待网络的操作后等待"""
        waiter = PageWaiter(mock_page)
        
        waiter.wait_for_network_idle = AsyncMock()
        waiter.wait_for_dom_stable = AsyncMock()
        
        await waiter.post_action_wait(
            wait_for_network_idle=False,
            wait_for_dom_stable=True
        )
        
        waiter.wait_for_network_idle.assert_not_called()
        waiter.wait_for_dom_stable.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_wait_for_network_idle(self, mock_page):
        """测试等待网络空闲"""
        mock_page.wait_for_load_state = AsyncMock()
        
        waiter = PageWaiter(mock_page)
        
        await waiter.wait_for_network_idle()
        
        mock_page.wait_for_load_state.assert_called()
    
    @pytest.mark.asyncio
    async def test_wait_for_dom_stable(self, mock_page):
        """测试等待DOM稳定"""
        # 模拟DOM元素数量稳定
        mock_page.evaluate = AsyncMock(return_value=100)
        
        waiter = PageWaiter(mock_page, strategy=WaitStrategy(
            dom_stable_checks=3,
            dom_stable_interval_ms=10
        ))
        
        await waiter.wait_for_dom_stable()
        
        # evaluate应该被调用多次来检查DOM稳定
        assert mock_page.evaluate.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_wait_for_network_idle_timeout(self, mock_page):
        """测试网络空闲等待超时"""
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        
        mock_page.wait_for_load_state = AsyncMock(
            side_effect=PlaywrightTimeoutError("Timeout")
        )
        
        waiter = PageWaiter(mock_page)
        
        # 应该捕获超时而不是抛出
        await waiter.wait_for_network_idle()  # 不应抛出异常
    
    @pytest.mark.asyncio
    async def test_apply_retry_backoff(self, mock_page):
        """测试应用重试退避"""
        waiter = PageWaiter(mock_page, strategy=WaitStrategy(
            retry_initial_delay_ms=10,
            retry_backoff_factor=2.0,
            retry_max_delay_ms=100
        ))
        
        start = asyncio.get_event_loop().time()
        await waiter.apply_retry_backoff(0)
        elapsed = asyncio.get_event_loop().time() - start
        
        # 第0次重试应该等待约10ms
        assert elapsed >= 0.005  # 至少5ms（考虑精度）


class TestPageWaiterEdgeCases:
    """测试页面等待工具边缘情况"""
    
    @pytest.mark.asyncio
    async def test_zero_delay(self):
        """测试零延迟"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=0,
            retry_max_delay_ms=0
        )
        
        delay = strategy.next_retry_delay(0)
        
        assert delay == 0
    
    @pytest.mark.asyncio
    async def test_negative_attempt(self):
        """测试负数尝试次数"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=2.0
        )
        
        # 负数尝试应该返回合理值
        delay = strategy.next_retry_delay(-1)
        
        assert delay >= 0
    
    @pytest.mark.asyncio
    async def test_large_attempt_number(self):
        """测试大尝试次数"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=2.0,
            retry_max_delay_ms=1000
        )
        
        # 大尝试次数应该被限制在max_delay
        delay = strategy.next_retry_delay(100)
        
        assert delay == 1.0  # 1000ms = 1s
    
    @pytest.mark.asyncio
    async def test_dom_stability_changes(self):
        """测试DOM不稳定情况"""
        mock_page = AsyncMock()
        
        # 模拟DOM元素数量变化
        call_count = [0]
        async def changing_evaluate(*args):
            call_count[0] += 1
            return 100 + call_count[0]  # 每次返回不同值
        
        mock_page.evaluate = changing_evaluate
        
        waiter = PageWaiter(mock_page, strategy=WaitStrategy(
            dom_stable_checks=3,
            dom_stable_interval_ms=5,
            wait_for_stability_timeout_ms=50
        ))
        
        # 由于DOM不稳定，应该最终超时
        await waiter.wait_for_dom_stable()  # 不应无限循环


class TestWaitStrategyCalculations:
    """测试等待策略计算"""
    
    def test_backoff_sequence(self):
        """测试退避序列"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=1.5,
            retry_max_delay_ms=1000
        )
        
        delays = [strategy.next_retry_delay(i) for i in range(5)]
        
        # 验证序列递增（直到达到上限）
        for i in range(len(delays) - 1):
            if delays[i] < 1.0:  # 未达到上限
                assert delays[i] <= delays[i + 1]
    
    def test_backoff_factor_effect(self):
        """测试退避因子影响"""
        strategy_slow = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=1.5,
            retry_max_delay_ms=10000
        )
        
        strategy_fast = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=2.5,
            retry_max_delay_ms=10000
        )
        
        # 相同尝试次数，高因子应该有更长延迟
        slow_delay = strategy_slow.next_retry_delay(3)
        fast_delay = strategy_fast.next_retry_delay(3)
        
        assert fast_delay > slow_delay








