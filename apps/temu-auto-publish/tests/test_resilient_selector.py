"""
@PURPOSE: 测试弹性选择器
@OUTLINE:
  - test_selector_chain: 测试选择器链配置
  - test_selector_hit_metrics: 测试命中统计
  - test_resilient_locator: 测试弹性定位器
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from src.browser.resilient_selector import (
    ResilientLocator,
    SelectorChain,
    SelectorHitMetrics,
    get_resilient_locator,
    resilient_click,
    resilient_locate,
)


class TestSelectorChain:
    """测试 SelectorChain 数据结构"""

    def test_basic_chain(self):
        """测试基本选择器链"""
        chain = SelectorChain(
            key="test_button",
            primary="#main-button",
            fallbacks=["button.primary", "button:has-text('Click')"],
            description="测试按钮",
        )

        assert chain.key == "test_button"
        assert chain.primary == "#main-button"
        assert len(chain.fallbacks) == 2
        assert chain.description == "测试按钮"

    def test_all_selectors_property(self):
        """测试 all_selectors 属性"""
        chain = SelectorChain(
            key="test",
            primary="#primary",
            fallbacks=["#fallback1", "#fallback2"],
        )

        all_sel = chain.all_selectors

        assert len(all_sel) == 3
        assert all_sel[0] == "#primary"
        assert all_sel[1] == "#fallback1"
        assert all_sel[2] == "#fallback2"

    def test_default_values(self):
        """测试默认值"""
        chain = SelectorChain(key="test", primary="#test")

        assert chain.fallbacks == []
        assert chain.description == ""
        assert chain.wait_state == "visible"
        assert chain.timeout_per_selector == 2000


class TestSelectorHitMetrics:
    """测试 SelectorHitMetrics 统计类"""

    def test_record_hit(self):
        """测试记录命中"""
        metrics = SelectorHitMetrics(chain_key="test")

        metrics.record_hit(0, 100.0)  # 主选择器命中
        metrics.record_hit(1, 200.0)  # 第一个降级命中

        assert metrics.hits[0] == 1
        assert metrics.hits[1] == 1
        assert metrics.total_time_ms == 300.0

    def test_record_miss(self):
        """测试记录未命中"""
        metrics = SelectorHitMetrics(chain_key="test")

        metrics.record_miss(500.0)

        assert metrics.misses == 1
        assert metrics.total_time_ms == 500.0

    def test_total_attempts(self):
        """测试总尝试次数"""
        metrics = SelectorHitMetrics(chain_key="test")

        metrics.record_hit(0, 100.0)
        metrics.record_hit(0, 100.0)
        metrics.record_miss(200.0)

        assert metrics.total_attempts == 3

    def test_success_rate(self):
        """测试成功率"""
        metrics = SelectorHitMetrics(chain_key="test")

        metrics.record_hit(0, 100.0)
        metrics.record_hit(0, 100.0)
        metrics.record_miss(200.0)
        metrics.record_miss(200.0)

        assert metrics.success_rate == 0.5

    def test_primary_hit_rate(self):
        """测试主选择器命中率"""
        metrics = SelectorHitMetrics(chain_key="test")

        metrics.record_hit(0, 100.0)  # 主选择器
        metrics.record_hit(1, 100.0)  # 降级选择器
        metrics.record_miss(100.0)

        assert metrics.primary_hit_rate == pytest.approx(1 / 3, rel=0.01)

    def test_to_dict(self):
        """测试转换为字典"""
        metrics = SelectorHitMetrics(chain_key="test")
        metrics.record_hit(0, 100.0)
        metrics.record_miss(200.0)

        data = metrics.to_dict()

        assert data["chain_key"] == "test"
        assert data["hits_by_index"] == {0: 1}
        assert data["misses"] == 1
        assert data["total_attempts"] == 2
        assert data["success_rate"] == 0.5


@pytest.mark.asyncio
class TestResilientLocator:
    """测试 ResilientLocator 类"""

    @pytest.fixture
    def mock_page(self):
        """创建模拟的 Page 对象"""
        page = MagicMock()
        return page

    @pytest.fixture
    def locator(self):
        """创建 ResilientLocator 实例"""
        return ResilientLocator()

    def test_default_chains_loaded(self, locator):
        """测试默认选择器链已加载"""
        assert "claim_button" in locator._chains
        assert "batch_edit_button" in locator._chains
        assert "save_button" in locator._chains

    def test_register_chain(self, locator):
        """测试注册新的选择器链"""
        custom_chain = SelectorChain(
            key="custom_element",
            primary="#custom",
            fallbacks=[".custom-class"],
        )

        locator.register_chain(custom_chain)

        assert "custom_element" in locator._chains
        assert locator._chains["custom_element"].primary == "#custom"

    def test_get_chain(self, locator):
        """测试获取选择器链"""
        chain = locator.get_chain("claim_button")

        assert chain is not None
        assert chain.key == "claim_button"

        # 不存在的链
        assert locator.get_chain("nonexistent") is None

    async def test_locate_success_primary(self, locator, mock_page):
        """测试主选择器定位成功"""
        mock_locator = MagicMock()
        mock_locator.wait_for = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)

        result = await locator.locate(mock_page, "claim_button", timeout=1000)

        assert result is mock_locator
        # 应该记录主选择器命中
        metrics = locator._metrics.get("claim_button")
        assert metrics is not None
        assert 0 in metrics.hits

    async def test_locate_fallback(self, locator, mock_page):
        """测试降级到次选择器"""
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        call_count = 0

        def create_locator(selector):
            nonlocal call_count
            mock_loc = MagicMock()
            if call_count == 0:
                # 第一个选择器超时
                mock_loc.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
            else:
                # 第二个选择器成功
                mock_loc.wait_for = AsyncMock()
            call_count += 1
            return mock_loc

        mock_page.locator = MagicMock(side_effect=create_locator)

        result = await locator.locate(mock_page, "claim_button", timeout=2000)

        assert result is not None
        # 应该记录降级选择器命中
        metrics = locator._metrics.get("claim_button")
        assert metrics is not None
        assert 1 in metrics.hits  # 第二个选择器(索引1)命中

    async def test_locate_all_failed(self, locator, mock_page):
        """测试所有选择器都失败"""
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        mock_loc = MagicMock()
        mock_loc.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        mock_page.locator = MagicMock(return_value=mock_loc)

        result = await locator.locate(mock_page, "claim_button", timeout=1000)

        assert result is None
        # 应该记录未命中
        metrics = locator._metrics.get("claim_button")
        assert metrics is not None
        assert metrics.misses == 1

    async def test_locate_unknown_key(self, locator, mock_page):
        """测试未知的选择器键"""
        result = await locator.locate(mock_page, "unknown_key")

        assert result is None

    async def test_locate_with_selector(self, locator, mock_page):
        """测试使用单个选择器定位"""
        mock_loc = MagicMock()
        mock_loc.wait_for = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_loc)

        result = await locator.locate_with_selector(
            mock_page,
            "#custom-selector",
            timeout=1000,
            description="自定义元素",
        )

        assert result is mock_loc
        mock_page.locator.assert_called_with("#custom-selector")

    async def test_click_success(self, locator, mock_page):
        """测试点击成功"""
        mock_loc = MagicMock()
        mock_loc.wait_for = AsyncMock()
        mock_loc.click = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_loc)

        result = await locator.click(mock_page, "claim_button")

        assert result is True
        mock_loc.click.assert_called_once()

    async def test_click_locate_failed(self, locator, mock_page):
        """测试点击失败(定位失败)"""
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        mock_loc = MagicMock()
        mock_loc.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("timeout"))
        mock_page.locator = MagicMock(return_value=mock_loc)

        result = await locator.click(mock_page, "claim_button", timeout=100)

        assert result is False

    async def test_fill_success(self, locator, mock_page):
        """测试填写成功"""
        mock_loc = MagicMock()
        mock_loc.wait_for = AsyncMock()
        mock_loc.clear = AsyncMock()
        mock_loc.fill = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_loc)

        result = await locator.fill(mock_page, "title_input", "测试标题")

        assert result is True
        mock_loc.clear.assert_called_once()
        mock_loc.fill.assert_called_once_with("测试标题")

    async def test_fill_no_clear(self, locator, mock_page):
        """测试填写不清空"""
        mock_loc = MagicMock()
        mock_loc.wait_for = AsyncMock()
        mock_loc.clear = AsyncMock()
        mock_loc.fill = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_loc)

        result = await locator.fill(mock_page, "title_input", "测试", clear_first=False)

        assert result is True
        mock_loc.clear.assert_not_called()

    def test_get_metrics_single(self, locator):
        """测试获取单个选择器的统计"""
        locator._metrics["test_key"] = SelectorHitMetrics(chain_key="test_key")
        locator._metrics["test_key"].record_hit(0, 100.0)

        metrics = locator.get_metrics("test_key")

        assert metrics["chain_key"] == "test_key"
        assert metrics["total_attempts"] == 1

    def test_get_metrics_all(self, locator):
        """测试获取所有统计"""
        locator._metrics["key1"] = SelectorHitMetrics(chain_key="key1")
        locator._metrics["key2"] = SelectorHitMetrics(chain_key="key2")

        all_metrics = locator.get_metrics()

        assert "key1" in all_metrics
        assert "key2" in all_metrics

    def test_reset_metrics(self, locator):
        """测试重置统计"""
        locator._metrics["test"] = SelectorHitMetrics(chain_key="test")

        locator.reset_metrics()

        assert len(locator._metrics) == 0

    def test_suggest_optimizations_low_primary_rate(self, locator):
        """测试建议优化 - 主选择器命中率低"""
        # 创建一个主选择器命中率很低的统计
        metrics = SelectorHitMetrics(chain_key="claim_button")
        for _ in range(8):
            metrics.record_hit(1, 100.0)  # 降级选择器
        for _ in range(2):
            metrics.record_hit(0, 100.0)  # 主选择器
        locator._metrics["claim_button"] = metrics

        suggestions = locator.suggest_optimizations()

        assert len(suggestions) > 0
        reorder_suggestion = next((s for s in suggestions if s["type"] == "reorder"), None)
        assert reorder_suggestion is not None

    def test_suggest_optimizations_low_success_rate(self, locator):
        """测试建议优化 - 成功率低"""
        metrics = SelectorHitMetrics(chain_key="claim_button")
        for _ in range(3):
            metrics.record_hit(0, 100.0)
        for _ in range(7):
            metrics.record_miss(100.0)
        locator._metrics["claim_button"] = metrics

        suggestions = locator.suggest_optimizations()

        add_suggestion = next((s for s in suggestions if s["type"] == "add_selectors"), None)
        assert add_suggestion is not None

    def test_suggest_optimizations_insufficient_data(self, locator):
        """测试建议优化 - 数据不足"""
        metrics = SelectorHitMetrics(chain_key="claim_button")
        for _ in range(5):  # 少于10次
            metrics.record_hit(0, 100.0)
        locator._metrics["claim_button"] = metrics

        suggestions = locator.suggest_optimizations()

        # 样本太少,不应该有建议
        assert len(suggestions) == 0


class TestGlobalResilientLocator:
    """测试全局弹性定位器"""

    def test_get_resilient_locator_singleton(self):
        """测试获取单例"""
        loc1 = get_resilient_locator()
        loc2 = get_resilient_locator()

        assert loc1 is loc2

    @pytest.mark.asyncio
    async def test_resilient_locate_convenience(self):
        """测试便捷定位函数"""
        mock_page = MagicMock()
        mock_loc = MagicMock()
        mock_loc.wait_for = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_loc)

        result = await resilient_locate(mock_page, "claim_button", timeout=1000)

        assert result is mock_loc

    @pytest.mark.asyncio
    async def test_resilient_click_convenience(self):
        """测试便捷点击函数"""
        mock_page = MagicMock()
        mock_loc = MagicMock()
        mock_loc.wait_for = AsyncMock()
        mock_loc.click = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_loc)

        result = await resilient_click(mock_page, "claim_button")

        assert result is True
