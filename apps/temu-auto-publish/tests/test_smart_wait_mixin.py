"""
@PURPOSE: 测试智能等待混入类
@OUTLINE:
  - test_wait_metrics: 测试等待统计
  - test_adaptive_wait_config: 测试自适应配置
  - test_smart_wait_mixin: 测试智能等待类
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.browser.smart_wait_mixin import (
    AdaptiveWaitConfig,
    SmartWaitMixin,
    WaitMetrics,
    get_smart_waiter,
    smart_wait,
)


class TestWaitMetrics:
    """测试 WaitMetrics 数据结构"""

    def test_initial_values(self):
        """测试初始值"""
        metrics = WaitMetrics(operation="test_op")

        assert metrics.operation == "test_op"
        assert metrics.success_count == 0
        assert metrics.failure_count == 0
        assert metrics.total_wait_ms == 0.0
        assert metrics.avg_wait_ms == 0.0

    def test_record_success(self):
        """测试记录成功"""
        metrics = WaitMetrics(operation="test")

        metrics.record(100.0, success=True)

        assert metrics.success_count == 1
        assert metrics.failure_count == 0
        assert metrics.total_wait_ms == 100.0
        assert metrics.avg_wait_ms == 100.0

    def test_record_failure(self):
        """测试记录失败"""
        metrics = WaitMetrics(operation="test")

        metrics.record(200.0, success=False)

        assert metrics.success_count == 0
        assert metrics.failure_count == 1
        assert metrics.total_wait_ms == 200.0

    def test_average_calculation(self):
        """测试平均值计算"""
        metrics = WaitMetrics(operation="test")

        metrics.record(100.0, success=True)
        metrics.record(200.0, success=True)
        metrics.record(300.0, success=False)

        assert metrics.success_count == 2
        assert metrics.failure_count == 1
        assert metrics.total_wait_ms == 600.0
        assert metrics.avg_wait_ms == 200.0


class TestAdaptiveWaitConfig:
    """测试 AdaptiveWaitConfig 配置"""

    def test_default_values(self):
        """测试默认配置"""
        config = AdaptiveWaitConfig()

        assert config.min_wait_ms == 30
        assert config.max_wait_ms == 2000
        assert config.network_idle_timeout_ms == 500
        assert config.dom_stable_timeout_ms == 500
        assert config.dom_stable_checks == 3
        assert config.learning_factor == 0.3

    def test_custom_values(self):
        """测试自定义配置"""
        config = AdaptiveWaitConfig(
            min_wait_ms=50,
            max_wait_ms=5000,
            learning_factor=0.5,
        )

        assert config.min_wait_ms == 50
        assert config.max_wait_ms == 5000
        assert config.learning_factor == 0.5


@pytest.mark.asyncio
class TestSmartWaitMixin:
    """测试 SmartWaitMixin 类"""

    @pytest.fixture
    def mock_page(self):
        """创建模拟的 Page 对象"""
        page = MagicMock()
        page.wait_for_load_state = AsyncMock(return_value=None)
        page.evaluate = AsyncMock(return_value=(1000, 50))  # 返回 DOM 快照
        return page

    @pytest.fixture
    def wait_mixin(self):
        """创建 SmartWaitMixin 实例"""
        return SmartWaitMixin()

    async def test_adaptive_wait_basic(self, wait_mixin, mock_page):
        """测试基本的自适应等待"""
        elapsed = await wait_mixin.adaptive_wait(
            mock_page,
            "test_operation",
            min_ms=10,
            max_ms=100,
        )

        assert elapsed >= 10  # 至少等待最小时间

    async def test_adaptive_wait_no_conditions(self, wait_mixin, mock_page):
        """测试无条件时的最小等待"""
        elapsed = await wait_mixin.adaptive_wait(
            mock_page,
            "test_no_conditions",
            min_ms=20,
            wait_for_network=False,
            wait_for_dom=False,
        )

        assert elapsed >= 20

    async def test_adaptive_wait_updates_metrics(self, wait_mixin, mock_page):
        """测试等待后更新统计"""
        await wait_mixin.adaptive_wait(mock_page, "test_metrics", min_ms=10)
        await wait_mixin.adaptive_wait(mock_page, "test_metrics", min_ms=10)

        stats = wait_mixin.get_wait_statistics()

        assert "test_metrics" in stats
        assert stats["test_metrics"]["success_count"] + stats["test_metrics"]["failure_count"] == 2

    async def test_adaptive_wait_learns_from_history(self, wait_mixin, mock_page):
        """测试从历史数据学习"""
        # 执行多次建立历史
        for _ in range(5):
            await wait_mixin.adaptive_wait(mock_page, "learning_test", min_ms=10)

        # 缓存应该被更新
        assert "learning_test" in wait_mixin._wait_cache

    async def test_wait_for_network_quiet_success(self, wait_mixin, mock_page):
        """测试网络空闲等待成功"""
        result = await wait_mixin._wait_for_network_quiet(mock_page, timeout_ms=1000)

        assert result is True
        mock_page.wait_for_load_state.assert_called_once_with("networkidle", timeout=1000)

    async def test_wait_for_network_quiet_timeout(self, wait_mixin, mock_page):
        """测试网络空闲等待超时"""
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        mock_page.wait_for_load_state = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))

        result = await wait_mixin._wait_for_network_quiet(mock_page, timeout_ms=100)

        # 超时不阻塞，返回 False
        assert result is False

    async def test_wait_for_dom_stable_success(self, wait_mixin, mock_page):
        """测试 DOM 稳定等待成功"""
        # 模拟稳定的 DOM（返回相同值）
        mock_page.evaluate = AsyncMock(return_value=(1000, 50))

        result = await wait_mixin._wait_for_dom_stable(
            mock_page,
            timeout_ms=500,
            checks=2,
            interval_ms=10,
        )

        assert result is True

    async def test_wait_for_dom_stable_unstable(self, wait_mixin, mock_page):
        """测试 DOM 不稳定"""
        # 模拟变化的 DOM
        call_count = 0

        async def changing_dom(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return (1000 + call_count * 100, 50 + call_count)

        mock_page.evaluate = AsyncMock(side_effect=changing_dom)

        result = await wait_mixin._wait_for_dom_stable(
            mock_page,
            timeout_ms=100,
            checks=3,
            interval_ms=10,
        )

        # DOM 持续变化，应该超时
        assert result is False

    def test_boxes_equal(self, wait_mixin):
        """测试边界框比较"""
        box1 = {"x": 100, "y": 200, "width": 50, "height": 30}
        box2 = {"x": 100.5, "y": 200.5, "width": 50.5, "height": 30.5}
        box3 = {"x": 150, "y": 200, "width": 50, "height": 30}

        # 在容差范围内
        assert wait_mixin._boxes_equal(box1, box2, tolerance=1.0) is True
        # 超出容差
        assert wait_mixin._boxes_equal(box1, box3, tolerance=1.0) is False

    async def test_batch_wait_any(self, wait_mixin, mock_page):
        """测试批量等待（任一满足）"""

        async def always_true(page):
            return True

        async def always_false(page):
            return False

        overall, results = await wait_mixin.batch_wait(
            mock_page,
            [always_true, always_false],
            timeout_ms=1000,
            require_all=False,
        )

        assert overall is True
        assert results == [True, False]

    async def test_batch_wait_all(self, wait_mixin, mock_page):
        """测试批量等待（全部满足）"""

        async def always_true(page):
            return True

        async def always_false(page):
            return False

        overall, results = await wait_mixin.batch_wait(
            mock_page,
            [always_true, always_false],
            timeout_ms=1000,
            require_all=True,
        )

        assert overall is False

    def test_get_wait_statistics(self, wait_mixin):
        """测试获取统计数据"""
        # 手动设置一些指标
        wait_mixin._wait_metrics["op1"] = WaitMetrics(
            operation="op1",
            success_count=5,
            total_wait_ms=500.0,
        )
        wait_mixin._wait_metrics["op1"].avg_wait_ms = 100.0

        stats = wait_mixin.get_wait_statistics()

        assert "op1" in stats
        assert stats["op1"]["success_count"] == 5
        assert stats["op1"]["avg_wait_ms"] == 100.0

    def test_reset_wait_cache(self, wait_mixin):
        """测试重置缓存"""
        wait_mixin._wait_cache["test"] = 100.0
        wait_mixin._wait_metrics["test"] = WaitMetrics(operation="test")

        wait_mixin.reset_wait_cache()

        assert len(wait_mixin._wait_cache) == 0
        assert len(wait_mixin._wait_metrics) == 0


class TestGlobalSmartWaiter:
    """测试全局智能等待器"""

    def test_get_smart_waiter_singleton(self):
        """测试获取单例"""
        waiter1 = get_smart_waiter()
        waiter2 = get_smart_waiter()

        assert waiter1 is waiter2

    @pytest.mark.asyncio
    async def test_smart_wait_convenience_function(self):
        """测试便捷函数"""
        mock_page = MagicMock()
        mock_page.wait_for_load_state = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value=(100, 10))

        elapsed = await smart_wait(
            mock_page,
            "convenience_test",
            min_ms=10,
            max_ms=100,
        )

        assert elapsed >= 10
