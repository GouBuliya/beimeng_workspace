"""
@PURPOSE: 测试 utils/selector_race.py 选择器竞速工具
@OUTLINE:
  - class TestSelectorTimeouts: 测试超时配置
  - class TestTrySelectorsRace: 测试并行竞速选择器
  - class TestTrySelectorsSequential: 测试顺序选择器
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.utils.selector_race
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSelectorTimeouts:
    """测试 SelectorTimeouts 配置类."""

    def test_default_values(self) -> None:
        """测试默认超时值."""
        from src.utils.selector_race import SelectorTimeouts

        timeouts = SelectorTimeouts()
        assert timeouts.FAST > 0
        assert timeouts.NORMAL > 0
        assert timeouts.SLOW > 0
        # FAST < NORMAL < SLOW
        assert timeouts.FAST <= timeouts.NORMAL <= timeouts.SLOW

    def test_environment_override(self) -> None:
        """测试环境变量覆盖."""
        # 保存原始环境变量
        original_fast = os.environ.get("SELECTOR_TIMEOUT_FAST")

        try:
            # 设置自定义超时
            os.environ["SELECTOR_TIMEOUT_FAST"] = "5000"

            # 需要重新导入以应用环境变量
            from importlib import reload

            from src.utils import selector_race

            reload(selector_race)

            assert selector_race.SelectorTimeouts.FAST == 5000
        finally:
            # 恢复环境变量
            if original_fast is not None:
                os.environ["SELECTOR_TIMEOUT_FAST"] = original_fast
            else:
                os.environ.pop("SELECTOR_TIMEOUT_FAST", None)

    def test_global_timeouts_instance(self) -> None:
        """测试全局 TIMEOUTS 实例."""
        from src.utils.selector_race import TIMEOUTS

        assert TIMEOUTS.FAST > 0
        assert TIMEOUTS.NORMAL > 0
        assert TIMEOUTS.SLOW > 0


def create_async_mock_locator(is_visible: bool = True, count: int = 1):
    """创建支持异步方法的 Mock Locator."""
    locator = MagicMock()
    locator.count = AsyncMock(return_value=count)
    locator.is_visible = AsyncMock(return_value=is_visible)
    locator.first = locator
    locator.nth = MagicMock(return_value=locator)
    return locator


def create_async_mock_page(locators: dict | None = None):
    """创建支持异步方法的 Mock Page."""
    page = MagicMock()
    locators = locators or {}

    def mock_locator(selector: str):
        if selector in locators:
            return locators[selector]
        # 默认返回不可见的 locator
        return create_async_mock_locator(is_visible=False, count=0)

    page.locator = mock_locator
    return page


class TestTrySelectorsRace:
    """测试 try_selectors_race 并行竞速函数."""

    @pytest.mark.asyncio
    async def test_empty_selectors(self) -> None:
        """测试空选择器列表返回 None."""
        from src.utils.selector_race import try_selectors_race

        page = create_async_mock_page()
        result = await try_selectors_race(page, [])
        assert result is None

    @pytest.mark.asyncio
    async def test_first_selector_wins(self) -> None:
        """测试第一个选择器成功时返回."""
        from src.utils.selector_race import try_selectors_race

        locators = {
            "selector1": create_async_mock_locator(is_visible=True, count=1),
            "selector2": create_async_mock_locator(is_visible=True, count=1),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_race(
            page,
            ["selector1", "selector2"],
            context_name="test",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_fallback_to_second_selector(self) -> None:
        """测试第一个失败时回退到第二个."""
        from src.utils.selector_race import try_selectors_race

        locators = {
            "selector1": create_async_mock_locator(is_visible=False, count=0),
            "selector2": create_async_mock_locator(is_visible=True, count=1),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_race(
            page,
            ["selector1", "selector2"],
            context_name="test",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_all_selectors_fail(self) -> None:
        """测试所有选择器都失败时返回 None."""
        from src.utils.selector_race import try_selectors_race

        locators = {
            "selector1": create_async_mock_locator(is_visible=False, count=0),
            "selector2": create_async_mock_locator(is_visible=False, count=0),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_race(
            page,
            ["selector1", "selector2"],
            context_name="test",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_custom_timeout(self) -> None:
        """测试自定义超时."""
        from src.utils.selector_race import try_selectors_race

        locators = {
            "selector1": create_async_mock_locator(is_visible=True, count=1),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_race(
            page,
            ["selector1"],
            timeout_ms=100,
            context_name="test",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_context_name_logging(self) -> None:
        """测试上下文名称用于日志."""
        from src.utils.selector_race import try_selectors_race

        locators = {
            "selector1": create_async_mock_locator(is_visible=True, count=1),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_race(
            page,
            ["selector1"],
            context_name="测试输入框",
        )

        assert result is not None


class TestTrySelectorsRaceWithElements:
    """测试 try_selectors_race_with_elements 函数."""

    @pytest.mark.asyncio
    async def test_empty_selectors(self) -> None:
        """测试空选择器列表."""
        from src.utils.selector_race import try_selectors_race_with_elements

        page = create_async_mock_page()
        result = await try_selectors_race_with_elements(page, [])
        assert result is None

    @pytest.mark.asyncio
    async def test_nth_element_selection(self) -> None:
        """测试选择第 N 个元素."""
        from src.utils.selector_race import try_selectors_race_with_elements

        locators = {
            "selector1": create_async_mock_locator(is_visible=True, count=3),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_race_with_elements(
            page,
            ["selector1"],
            nth=1,
            context_name="test",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_nth_out_of_range(self) -> None:
        """测试 nth 超出范围."""
        from src.utils.selector_race import try_selectors_race_with_elements

        locators = {
            "selector1": create_async_mock_locator(is_visible=True, count=1),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_race_with_elements(
            page,
            ["selector1"],
            nth=5,  # 超出范围
            context_name="test",
        )

        assert result is None


class TestTrySelectorsSequential:
    """测试 try_selectors_sequential 顺序选择器函数."""

    @pytest.mark.asyncio
    async def test_first_match(self) -> None:
        """测试第一个匹配成功."""
        from src.utils.selector_race import try_selectors_sequential

        locators = {
            "selector1": create_async_mock_locator(is_visible=True, count=1),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_sequential(
            page,
            ["selector1", "selector2"],
            context_name="test",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_sequential_fallback(self) -> None:
        """测试顺序回退."""
        from src.utils.selector_race import try_selectors_sequential

        locators = {
            "selector1": create_async_mock_locator(is_visible=False, count=0),
            "selector2": create_async_mock_locator(is_visible=True, count=1),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_sequential(
            page,
            ["selector1", "selector2"],
            context_name="test",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_all_fail(self) -> None:
        """测试全部失败."""
        from src.utils.selector_race import try_selectors_sequential

        locators = {
            "selector1": create_async_mock_locator(is_visible=False, count=0),
            "selector2": create_async_mock_locator(is_visible=False, count=0),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_sequential(
            page,
            ["selector1", "selector2"],
            context_name="test",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_exception_handling(self) -> None:
        """测试异常处理 - 继续尝试下一个."""
        from src.utils.selector_race import try_selectors_sequential

        # 第一个抛异常,第二个成功
        error_locator = MagicMock()
        error_locator.count = AsyncMock(side_effect=Exception("模拟错误"))

        locators = {
            "invalid_selector": error_locator,
            "selector2": create_async_mock_locator(is_visible=True, count=1),
        }
        page = create_async_mock_page(locators)

        result = await try_selectors_sequential(
            page,
            ["invalid_selector", "selector2"],
            context_name="test",
        )

        assert result is not None


class TestSelectorHitRecording:
    """测试选择器命中记录功能."""

    @pytest.mark.asyncio
    async def test_hit_recording(self) -> None:
        """测试命中记录调用."""
        from src.utils.selector_race import try_selectors_race

        locators = {
            "selector1": create_async_mock_locator(is_visible=True, count=1),
        }
        page = create_async_mock_page(locators)

        with patch("src.utils.selector_race.record_selector_hit") as mock_record:
            await try_selectors_race(
                page,
                ["selector1"],
                context_name="test_context",
            )

            # 应该记录命中
            mock_record.assert_called_once()
            call_args = mock_record.call_args
            assert call_args.kwargs["context"] == "test_context"


class TestModuleExports:
    """测试模块导出."""

    def test_exports(self) -> None:
        """测试 __all__ 导出."""
        from src.utils.selector_race import __all__

        expected = [
            "SelectorTimeouts",
            "TIMEOUTS",
            "try_selectors_race",
            "try_selectors_race_with_elements",
            "try_selectors_sequential",
        ]
        for name in expected:
            assert name in __all__

    def test_import_all(self) -> None:
        """测试所有导出项可导入."""
        from src.utils.selector_race import (
            TIMEOUTS,
            SelectorTimeouts,
            try_selectors_race,
            try_selectors_race_with_elements,
            try_selectors_sequential,
        )

        assert SelectorTimeouts is not None
        assert TIMEOUTS is not None
        assert try_selectors_race is not None
        assert try_selectors_race_with_elements is not None
        assert try_selectors_sequential is not None
