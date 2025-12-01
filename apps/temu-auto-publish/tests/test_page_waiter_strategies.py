"""
@PURPOSE: WaitStrategy 配置类单元测试
@OUTLINE:
  - TestWaitStrategyDefaults: 默认值测试
  - TestWaitStrategyFactoryMethods: 工厂方法测试
  - TestWaitStrategyNextRetryDelay: 指数退避计算测试
@DEPENDENCIES:
  - 内部: utils.page_waiter
  - 外部: pytest
"""

import pytest

from src.utils.page_waiter import WaitStrategy


# ============================================================
# WaitStrategy 默认值测试
# ============================================================
class TestWaitStrategyDefaults:
    """WaitStrategy 默认值测试"""

    def test_default_values(self):
        """测试默认值"""
        strategy = WaitStrategy()

        assert strategy.wait_after_action_ms == 100
        assert strategy.wait_for_stability_timeout_ms == 2000
        assert strategy.wait_for_network_idle_timeout_ms == 3000
        assert strategy.retry_initial_delay_ms == 200
        assert strategy.retry_backoff_factor == 1.5
        assert strategy.retry_max_delay_ms == 2000
        assert strategy.validation_timeout_ms == 3000
        assert strategy.dom_stable_checks == 2
        assert strategy.dom_stable_interval_ms == 150
        assert strategy.quick_check_interval_ms == 50

    def test_slots_enabled(self):
        """测试 slots 已启用（不能添加新属性）"""
        strategy = WaitStrategy()

        with pytest.raises(AttributeError):
            strategy.new_attr = "value"

    def test_custom_values(self):
        """测试自定义值"""
        strategy = WaitStrategy(
            wait_after_action_ms=500,
            dom_stable_checks=5,
            retry_backoff_factor=2.0,
        )

        assert strategy.wait_after_action_ms == 500
        assert strategy.dom_stable_checks == 5
        assert strategy.retry_backoff_factor == 2.0
        # 其他保持默认
        assert strategy.wait_for_stability_timeout_ms == 2000


# ============================================================
# WaitStrategy 工厂方法测试
# ============================================================
class TestWaitStrategyFactoryMethods:
    """WaitStrategy 工厂方法测试"""

    def test_conservative_mode(self):
        """测试保守模式"""
        strategy = WaitStrategy.conservative()

        assert strategy.wait_after_action_ms == 300
        assert strategy.wait_for_stability_timeout_ms == 3750
        assert strategy.wait_for_network_idle_timeout_ms == 5000
        assert strategy.retry_initial_delay_ms == 300
        assert strategy.retry_backoff_factor == 1.6
        assert strategy.retry_max_delay_ms == 3750
        assert strategy.validation_timeout_ms == 5000
        assert strategy.dom_stable_checks == 3
        assert strategy.dom_stable_interval_ms == 300
        assert strategy.quick_check_interval_ms == 100

    def test_balanced_mode(self):
        """测试平衡模式"""
        strategy = WaitStrategy.balanced()

        # 平衡模式使用默认值
        default = WaitStrategy()
        assert strategy.wait_after_action_ms == default.wait_after_action_ms
        assert strategy.dom_stable_checks == default.dom_stable_checks
        assert strategy.retry_backoff_factor == default.retry_backoff_factor

    def test_aggressive_mode(self):
        """测试激进模式"""
        strategy = WaitStrategy.aggressive()

        assert strategy.wait_after_action_ms == 50
        assert strategy.wait_for_stability_timeout_ms == 1000
        assert strategy.wait_for_network_idle_timeout_ms == 1500
        assert strategy.retry_initial_delay_ms == 100
        assert strategy.retry_backoff_factor == 1.3
        assert strategy.retry_max_delay_ms == 1000
        assert strategy.validation_timeout_ms == 2000
        assert strategy.dom_stable_checks == 1
        assert strategy.dom_stable_interval_ms == 80
        assert strategy.quick_check_interval_ms == 30

    def test_factory_methods_return_new_instances(self):
        """测试工厂方法返回新实例"""
        s1 = WaitStrategy.conservative()
        s2 = WaitStrategy.conservative()

        assert s1 is not s2

    def test_modes_ordering(self):
        """测试模式顺序 - 保守 > 平衡 > 激进"""
        conservative = WaitStrategy.conservative()
        balanced = WaitStrategy.balanced()
        aggressive = WaitStrategy.aggressive()

        # 等待时间: 保守 > 平衡 > 激进
        assert conservative.wait_after_action_ms > balanced.wait_after_action_ms
        assert balanced.wait_after_action_ms > aggressive.wait_after_action_ms

        # DOM 检查次数: 保守 > 平衡 > 激进
        assert conservative.dom_stable_checks > balanced.dom_stable_checks
        assert balanced.dom_stable_checks > aggressive.dom_stable_checks


# ============================================================
# WaitStrategy.next_retry_delay 测试
# ============================================================
class TestWaitStrategyNextRetryDelay:
    """next_retry_delay 指数退避计算测试"""

    def test_first_retry_delay(self):
        """测试第一次重试延迟"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=2.0,
            retry_max_delay_ms=1000,
        )

        # attempt=0: 100 * 2^0 = 100ms = 0.1s
        delay = strategy.next_retry_delay(0)

        assert delay == 0.1

    def test_exponential_growth(self):
        """测试指数增长"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=2.0,
            retry_max_delay_ms=10000,
        )

        # attempt=0: 100 * 2^0 = 100ms
        assert strategy.next_retry_delay(0) == 0.1
        # attempt=1: 100 * 2^1 = 200ms
        assert strategy.next_retry_delay(1) == 0.2
        # attempt=2: 100 * 2^2 = 400ms
        assert strategy.next_retry_delay(2) == 0.4
        # attempt=3: 100 * 2^3 = 800ms
        assert strategy.next_retry_delay(3) == 0.8

    def test_max_delay_cap(self):
        """测试最大延迟限制"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=2.0,
            retry_max_delay_ms=500,
        )

        # attempt=10: 100 * 2^10 = 102400ms, 但被限制为 500ms
        delay = strategy.next_retry_delay(10)

        assert delay == 0.5

    def test_default_strategy_delays(self):
        """测试默认策略的延迟序列"""
        strategy = WaitStrategy()  # 默认: 200ms, 1.5x, 2000ms max

        delays = [strategy.next_retry_delay(i) for i in range(10)]

        # 验证是递增的（直到达到上限）
        for i in range(1, len(delays)):
            assert delays[i] >= delays[i - 1]

        # 验证不超过最大值
        assert all(d <= 2.0 for d in delays)

    def test_conservative_strategy_delays(self):
        """测试保守策略的延迟"""
        strategy = WaitStrategy.conservative()

        # 第一次: 300ms
        assert strategy.next_retry_delay(0) == 0.3

        # 高次数时应该接近最大值 3750ms = 3.75s
        delay_high = strategy.next_retry_delay(20)
        assert delay_high == 3.75

    def test_aggressive_strategy_delays(self):
        """测试激进策略的延迟"""
        strategy = WaitStrategy.aggressive()

        # 第一次: 100ms
        assert strategy.next_retry_delay(0) == 0.1

        # 高次数时应该等于最大值 1000ms = 1.0s
        delay_high = strategy.next_retry_delay(20)
        assert delay_high == 1.0

    def test_zero_attempt(self):
        """测试零次重试"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=200,
            retry_backoff_factor=1.5,
        )

        delay = strategy.next_retry_delay(0)

        # 200 * 1.5^0 = 200ms = 0.2s
        assert delay == 0.2

    def test_non_integer_result(self):
        """测试非整数结果"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=1.5,
            retry_max_delay_ms=10000,
        )

        # attempt=1: 100 * 1.5^1 = 150ms = 0.15s
        delay = strategy.next_retry_delay(1)

        assert delay == 0.15


# ============================================================
# 边界情况测试
# ============================================================
class TestWaitStrategyEdgeCases:
    """边界情况测试"""

    def test_zero_initial_delay(self):
        """测试零初始延迟"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=0,
            retry_backoff_factor=2.0,
        )

        delay = strategy.next_retry_delay(5)

        # 0 * 2^5 = 0
        assert delay == 0.0

    def test_backoff_factor_one(self):
        """测试退避因子为 1（无增长）"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=1.0,
            retry_max_delay_ms=1000,
        )

        # 所有尝试都应该返回相同的延迟
        assert strategy.next_retry_delay(0) == 0.1
        assert strategy.next_retry_delay(5) == 0.1
        assert strategy.next_retry_delay(100) == 0.1

    def test_very_small_backoff_factor(self):
        """测试非常小的退避因子"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=1000,
            retry_backoff_factor=0.5,  # 每次减半
            retry_max_delay_ms=10000,
        )

        # attempt=0: 1000 * 0.5^0 = 1000ms
        assert strategy.next_retry_delay(0) == 1.0
        # attempt=1: 1000 * 0.5^1 = 500ms
        assert strategy.next_retry_delay(1) == 0.5
        # attempt=2: 1000 * 0.5^2 = 250ms
        assert strategy.next_retry_delay(2) == 0.25

    def test_large_attempt_number(self):
        """测试大的尝试次数"""
        strategy = WaitStrategy(
            retry_initial_delay_ms=100,
            retry_backoff_factor=2.0,
            retry_max_delay_ms=1000,
        )

        # 即使 attempt 很大，也应该被限制在 max_delay
        delay = strategy.next_retry_delay(1000)

        assert delay == 1.0

    def test_equality(self):
        """测试相等性比较"""
        s1 = WaitStrategy()
        s2 = WaitStrategy()

        assert s1 == s2

    def test_inequality(self):
        """测试不等性比较"""
        s1 = WaitStrategy()
        s2 = WaitStrategy(wait_after_action_ms=999)

        assert s1 != s2
