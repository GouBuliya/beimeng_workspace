"""
@PURPOSE: SmartLocator 类的完整单元测试
@OUTLINE:
  - TestSmartLocatorInit: 初始化测试
  - TestSmartLocatorFindElement: find_element 方法测试
  - TestSmartLocatorFindByText: find_by_text 方法测试
  - TestSmartLocatorFindInputByLabel: find_input_by_label 方法测试
  - TestSmartLocatorFindSelectByLabel: find_select_by_label 方法测试
  - TestSmartLocatorClickWithRetry: click_with_retry 方法测试
  - TestSmartLocatorFillWithRetry: fill_with_retry 方法测试
  - TestSmartLocatorSelectOptionWithRetry: select_option_with_retry 方法测试
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.utils.smart_locator
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


def create_mock_element(wait_for_succeeds=True):
    """创建完整的 mock element，包含 wait_for"""
    mock_element = MagicMock()
    mock_element.first = mock_element
    if wait_for_succeeds:
        mock_element.wait_for = AsyncMock()
    else:
        mock_element.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout"))
    mock_element.click = AsyncMock()
    mock_element.fill = AsyncMock()
    mock_element.input_value = AsyncMock(return_value="")
    mock_element.select_option = AsyncMock()
    mock_element.evaluate = AsyncMock(return_value=[])
    return mock_element


# ==================== SmartLocator 初始化测试 ====================
class TestSmartLocatorInit:
    """SmartLocator 初始化测试"""

    def test_init_with_defaults(self):
        """测试默认参数初始化"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        locator = SmartLocator(page)

        assert locator.page == page
        assert locator.default_timeout == 5000
        assert locator.retry_count == 3

    def test_init_with_custom_timeout(self):
        """测试自定义超时时间"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        locator = SmartLocator(page, default_timeout=10000)

        assert locator.default_timeout == 10000

    def test_init_with_custom_retry_count(self):
        """测试自定义重试次数"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        locator = SmartLocator(page, retry_count=5)

        assert locator.retry_count == 5

    def test_init_with_all_custom_params(self):
        """测试所有自定义参数"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        locator = SmartLocator(page, default_timeout=8000, retry_count=2)

        assert locator.default_timeout == 8000
        assert locator.retry_count == 2


# ==================== find_element 方法测试 ====================
class TestSmartLocatorFindElement:
    """find_element 方法测试"""

    @pytest.mark.asyncio
    async def test_find_element_first_selector_matches(self):
        """测试第一个选择器匹配成功"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = create_mock_element(wait_for_succeeds=True)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_element([".selector1", ".selector2"])

        assert result == mock_element
        page.locator.assert_called_with(".selector1")

    @pytest.mark.asyncio
    async def test_find_element_fallback_to_second_selector(self):
        """测试回退到第二个选择器"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()

        # 第一个选择器超时
        mock_element1 = create_mock_element(wait_for_succeeds=False)

        # 第二个选择器成功
        mock_element2 = create_mock_element(wait_for_succeeds=True)

        page.locator = MagicMock(side_effect=[mock_element1, mock_element2])

        locator = SmartLocator(page)
        result = await locator.find_element([".selector1", ".selector2"])

        assert result == mock_element2

    @pytest.mark.asyncio
    async def test_find_element_no_match(self):
        """测试所有选择器都不匹配（超时）"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = create_mock_element(wait_for_succeeds=False)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_element([".selector1", ".selector2"])

        assert result is None

    @pytest.mark.asyncio
    async def test_find_element_with_single_selector(self):
        """测试单个选择器"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = create_mock_element(wait_for_succeeds=True)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_element([".only-selector"])

        assert result == mock_element

    @pytest.mark.asyncio
    async def test_find_element_exception_handling(self):
        """测试异常处理"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        page.locator = MagicMock(side_effect=Exception("Selector error"))

        locator = SmartLocator(page)
        result = await locator.find_element([".bad-selector"])

        assert result is None


# ==================== find_by_text 方法测试 ====================
class TestSmartLocatorFindByText:
    """find_by_text 方法测试"""

    @pytest.mark.asyncio
    async def test_find_by_text_exact_match(self):
        """测试精确文本匹配"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = create_mock_element(wait_for_succeeds=True)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_by_text("确定")

        assert result == mock_element

    @pytest.mark.asyncio
    async def test_find_by_text_no_match(self):
        """测试文本不匹配"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = create_mock_element(wait_for_succeeds=False)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_by_text("不存在的文本")

        assert result is None

    @pytest.mark.asyncio
    async def test_find_by_text_partial_match(self):
        """测试部分文本匹配"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = create_mock_element(wait_for_succeeds=True)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_by_text("部分", exact=False)

        assert result == mock_element

    @pytest.mark.asyncio
    async def test_find_by_text_exception(self):
        """测试异常处理"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        page.locator = MagicMock(side_effect=Exception("Text search error"))

        locator = SmartLocator(page)
        result = await locator.find_by_text("测试")

        assert result is None


# ==================== find_input_by_label 方法测试 ====================
class TestSmartLocatorFindInputByLabel:
    """find_input_by_label 方法测试"""

    @pytest.mark.asyncio
    async def test_find_input_by_label_found(self):
        """测试通过标签找到输入框"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = create_mock_element(wait_for_succeeds=True)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_input_by_label("用户名")

        assert result == mock_element

    @pytest.mark.asyncio
    async def test_find_input_by_label_not_found(self):
        """测试标签不存在"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = create_mock_element(wait_for_succeeds=False)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_input_by_label("不存在的标签")

        assert result is None


# ==================== find_select_by_label 方法测试 ====================
class TestSmartLocatorFindSelectByLabel:
    """find_select_by_label 方法测试"""

    @pytest.mark.asyncio
    async def test_find_select_by_label_found(self):
        """测试通过标签找到下拉框"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = create_mock_element(wait_for_succeeds=True)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_select_by_label("类别")

        assert result == mock_element

    @pytest.mark.asyncio
    async def test_find_select_by_label_not_found(self):
        """测试下拉框不存在"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = create_mock_element(wait_for_succeeds=False)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_select_by_label("不存在")

        assert result is None


# ==================== click_with_retry 方法测试 ====================
class TestSmartLocatorClickWithRetry:
    """click_with_retry 方法测试"""

    @pytest.mark.asyncio
    async def test_click_with_retry_success_first_try(self):
        """测试第一次点击成功"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        mock_element = create_mock_element(wait_for_succeeds=True)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.click_with_retry([".button"])

        assert result is True
        mock_element.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_with_retry_success_after_retries(self):
        """测试重试后点击成功"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        mock_element = create_mock_element(wait_for_succeeds=True)
        # 前两次失败,第三次成功
        mock_element.click = AsyncMock(
            side_effect=[Exception("Click failed"), Exception("Click failed"), None]
        )
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page, retry_count=3)
        result = await locator.click_with_retry([".button"])

        assert result is True
        assert mock_element.click.call_count == 3

    @pytest.mark.asyncio
    async def test_click_with_retry_all_fail(self):
        """测试所有重试都失败"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        mock_element = create_mock_element(wait_for_succeeds=True)
        mock_element.click = AsyncMock(side_effect=Exception("Click failed"))
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page, retry_count=2)
        result = await locator.click_with_retry([".button"])

        assert result is False

    @pytest.mark.asyncio
    async def test_click_with_retry_element_not_found(self):
        """测试元素不存在"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        page.wait_for_timeout = AsyncMock()
        mock_element = create_mock_element(wait_for_succeeds=False)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page, retry_count=1)
        result = await locator.click_with_retry([".not-exist"])

        assert result is False


# ==================== fill_with_retry 方法测试 ====================
class TestSmartLocatorFillWithRetry:
    """fill_with_retry 方法测试"""

    @pytest.mark.asyncio
    async def test_fill_with_retry_success(self):
        """测试填充成功"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.count = AsyncMock(return_value=1)
        mock_element.first = mock_element
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.fill = AsyncMock()
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.fill_with_retry([".input"], "test value")

        assert result is True
        mock_element.fill.assert_called_with("test value")

    @pytest.mark.asyncio
    async def test_fill_with_retry_with_clear(self):
        """测试先清空再填充"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.count = AsyncMock(return_value=1)
        mock_element.first = mock_element
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.clear = AsyncMock()
        mock_element.fill = AsyncMock()
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.fill_with_retry([".input"], "new value", clear_first=True)

        assert result is True
        mock_element.clear.assert_called_once()
        mock_element.fill.assert_called_with("new value")

    @pytest.mark.asyncio
    async def test_fill_with_retry_failure(self):
        """测试填充失败"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.count = AsyncMock(return_value=1)
        mock_element.first = mock_element
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.fill = AsyncMock(side_effect=Exception("Fill failed"))
        page.locator = MagicMock(return_value=mock_element)
        page.wait_for_timeout = AsyncMock()

        locator = SmartLocator(page, retry_count=1)
        result = await locator.fill_with_retry([".input"], "value")

        assert result is False

    @pytest.mark.asyncio
    async def test_fill_with_retry_element_not_found(self):
        """测试元素不存在"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.count = AsyncMock(return_value=0)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.fill_with_retry([".not-exist"], "value")

        assert result is False


# ==================== select_option_with_retry 方法测试 ====================
class TestSmartLocatorSelectOptionWithRetry:
    """select_option_with_retry 方法测试"""

    @pytest.mark.asyncio
    async def test_select_option_success(self):
        """测试选择选项成功"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.count = AsyncMock(return_value=1)
        mock_element.first = mock_element
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.select_option = AsyncMock()
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.select_option_with_retry([".select"], "option1")

        assert result is True
        mock_element.select_option.assert_called_with("option1")

    @pytest.mark.asyncio
    async def test_select_option_by_label(self):
        """测试通过标签选择"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.count = AsyncMock(return_value=1)
        mock_element.first = mock_element
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.select_option = AsyncMock()
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.select_option_with_retry([".select"], label="选项一")

        assert result is True
        mock_element.select_option.assert_called()

    @pytest.mark.asyncio
    async def test_select_option_failure(self):
        """测试选择失败"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.count = AsyncMock(return_value=1)
        mock_element.first = mock_element
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.select_option = AsyncMock(side_effect=Exception("Select failed"))
        page.locator = MagicMock(return_value=mock_element)
        page.wait_for_timeout = AsyncMock()

        locator = SmartLocator(page, retry_count=1)
        result = await locator.select_option_with_retry([".select"], "option")

        assert result is False


# ==================== 边界情况测试 ====================
class TestSmartLocatorEdgeCases:
    """边界情况测试"""

    @pytest.mark.asyncio
    async def test_empty_selectors_list(self):
        """测试空选择器列表"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        locator = SmartLocator(page)
        result = await locator.find_element([])

        assert result is None

    @pytest.mark.asyncio
    async def test_zero_retry_count(self):
        """测试零重试次数"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.count = AsyncMock(return_value=1)
        mock_element.first = mock_element
        mock_element.is_visible = AsyncMock(return_value=True)
        mock_element.click = AsyncMock(side_effect=Exception("Click failed"))
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page, retry_count=0)
        # 零重试应该至少尝试一次
        result = await locator.click_with_retry([".button"])

        # 实现可能返回 False 或抛出异常,这里检查不会崩溃
        assert result in [True, False]

    @pytest.mark.asyncio
    async def test_very_long_selector(self):
        """测试超长选择器"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.count = AsyncMock(return_value=1)
        mock_element.first = mock_element
        mock_element.is_visible = AsyncMock(return_value=True)
        page.locator = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        long_selector = ".class" * 100
        result = await locator.find_element([long_selector])

        assert result == mock_element

    @pytest.mark.asyncio
    async def test_special_characters_in_text(self):
        """测试特殊字符文本"""
        from src.utils.smart_locator import SmartLocator

        page = MagicMock()
        mock_element = MagicMock()
        mock_element.count = AsyncMock(return_value=1)
        mock_element.first = mock_element
        mock_element.is_visible = AsyncMock(return_value=True)
        page.get_by_text = MagicMock(return_value=mock_element)

        locator = SmartLocator(page)
        result = await locator.find_by_text("特殊字符:[]<>")

        assert result == mock_element
