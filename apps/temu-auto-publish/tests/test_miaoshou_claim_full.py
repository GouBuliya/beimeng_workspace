"""
@PURPOSE: miaoshou/claim.py 单元测试
@OUTLINE:
  - TestMiaoshouClaimInit: 初始化测试
  - TestResolveTargetIndexes: 索引解析测试
  - TestWaitMethods: 等待方法测试
  - TestRefreshCollectionBox: 刷新采集箱测试
  - TestSelectProductsForClaim: 产品选择测试
  - TestClaimMethods: 认领方法测试
@DEPENDENCIES:
  - 内部: browser.miaoshou.claim
  - 外部: pytest, pytest-asyncio
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from src.browser.miaoshou.claim import MiaoshouClaimMixin


# ============================================================
# 初始化测试
# ============================================================
class TestMiaoshouClaimInit:
    """初始化测试"""

    def test_class_constants(self):
        """测试类常量定义"""
        assert MiaoshouClaimMixin._COLLECTION_BOX_URL is not None
        assert "miaoshou.com" in MiaoshouClaimMixin._COLLECTION_BOX_URL
        assert MiaoshouClaimMixin._ROW_SELECTOR == ".pro-virtual-table__row-body"
        assert MiaoshouClaimMixin._ROW_HEIGHT == 119
        assert MiaoshouClaimMixin._PAGE_SIZE == 20

    def test_selector_constants(self):
        """测试选择器常量"""
        assert len(MiaoshouClaimMixin._CHECKBOX_CANDIDATE_SELECTORS) > 0
        assert len(MiaoshouClaimMixin._CLAIM_PRIORITY_SELECTORS) > 0
        assert len(MiaoshouClaimMixin._CLAIM_FALLBACK_SELECTORS) > 0

    def test_init_with_default_path(self):
        """测试默认路径初始化"""
        with patch.object(MiaoshouClaimMixin, "__init__", lambda self, **kwargs: None):
            mixin = MiaoshouClaimMixin.__new__(MiaoshouClaimMixin)
            # 验证类已创建
            assert mixin is not None


# ============================================================
# _resolve_target_indexes 静态方法测试
# ============================================================
class TestResolveTargetIndexes:
    """索引解析测试"""

    def test_with_count_only(self):
        """测试仅提供 count"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=5, indexes=None, available=10
        )
        assert result == [0, 1, 2, 3, 4]

    def test_with_specific_indexes(self):
        """测试指定索引"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=5, indexes=[2, 4, 6], available=10
        )
        assert result == [2, 4, 6]

    def test_filters_negative_indexes(self):
        """测试过滤负数索引"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=5, indexes=[-1, 0, 2, -3], available=10
        )
        assert result == [0, 2]

    def test_filters_out_of_range_indexes(self):
        """测试过滤超范围索引"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=5, indexes=[0, 5, 10, 15], available=10
        )
        assert result == [0, 5]

    def test_sorts_indexes(self):
        """测试索引排序"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=5, indexes=[5, 1, 3, 2], available=10
        )
        assert result == [1, 2, 3, 5]

    def test_removes_duplicates(self):
        """测试去重"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=5, indexes=[1, 1, 2, 2, 3], available=10
        )
        assert result == [1, 2, 3]

    def test_empty_result_when_all_filtered(self):
        """测试全部被过滤时返回空列表"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=5, indexes=[10, 11, 12], available=5
        )
        assert result == []

    def test_count_exceeds_available(self):
        """测试 count 超过可用数量"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=10, indexes=None, available=5
        )
        assert result == [0, 1, 2, 3, 4]

    def test_handles_none_in_indexes(self):
        """测试索引中包含 None"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=5, indexes=[0, None, 2, None, 4], available=10
        )
        assert result == [0, 2, 4]


# ============================================================
# 等待方法测试
# ============================================================
class TestWaitMethods:
    """等待方法测试"""

    @pytest.fixture
    def mock_mixin(self):
        """创建 mock mixin 实例"""
        with patch.object(MiaoshouClaimMixin, "__init__", lambda self, **kwargs: None):
            mixin = MiaoshouClaimMixin.__new__(MiaoshouClaimMixin)
            return mixin

    @pytest.fixture
    def mock_page(self):
        """创建模拟 Page"""
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.wait_for_load_state = AsyncMock()

        # 创建 mock locator
        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.count = AsyncMock(return_value=1)
        page.locator = MagicMock(return_value=mock_locator)

        return page

    @pytest.mark.asyncio
    async def test_wait_for_rows_success(self, mock_mixin, mock_page):
        """测试等待行成功"""
        mock_mixin._ROW_SELECTOR = ".test-row"

        result = await mock_mixin._wait_for_rows(mock_page, timeout=1000)

        assert result is True
        mock_page.locator.assert_called_with(".test-row")

    @pytest.mark.asyncio
    async def test_wait_for_rows_timeout(self, mock_mixin, mock_page):
        """测试等待行超时"""
        mock_mixin._ROW_SELECTOR = ".test-row"
        mock_page.locator.return_value.first.wait_for = AsyncMock(
            side_effect=PlaywrightTimeoutError("timeout")
        )

        result = await mock_mixin._wait_for_rows(mock_page, timeout=100)

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_for_dropdown_state_visible(self, mock_mixin, mock_page):
        """测试等待下拉框可见"""
        await mock_mixin._wait_for_dropdown_state(
            mock_page, ".dropdown", state="visible", timeout=250
        )

        mock_page.locator.assert_called_with(".dropdown")

    @pytest.mark.asyncio
    async def test_wait_for_select_dropdown(self, mock_mixin, mock_page):
        """测试等待 select 下拉框"""
        mock_mixin._SELECT_DROPDOWN_LOCATOR = ".select-dropdown"

        await mock_mixin._wait_for_select_dropdown(mock_page)

        mock_page.locator.assert_called_with(".select-dropdown")

    @pytest.mark.asyncio
    async def test_wait_for_claim_dropdown(self, mock_mixin, mock_page):
        """测试等待认领下拉框"""
        mock_mixin._CLAIM_DROPDOWN_LOCATOR = ".claim-dropdown"

        await mock_mixin._wait_for_claim_dropdown(mock_page)

        mock_page.locator.assert_called_with(".claim-dropdown")


# ============================================================
# refresh_collection_box 测试
# ============================================================
class TestRefreshCollectionBox:
    """刷新采集箱测试"""

    @pytest.fixture
    def mock_mixin(self):
        """创建 mock mixin 实例"""
        with patch.object(MiaoshouClaimMixin, "__init__", lambda self, **kwargs: None):
            mixin = MiaoshouClaimMixin.__new__(MiaoshouClaimMixin)
            mixin._COLLECTION_BOX_URL = "https://example.com/collection"
            mixin._ROW_SELECTOR = ".row"
            mixin.filter_and_search = AsyncMock(return_value=True)
            return mixin

    @pytest.fixture
    def mock_page(self):
        """创建模拟 Page"""
        page = MagicMock()
        page.goto = AsyncMock()
        page.wait_for_timeout = AsyncMock()

        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        page.locator = MagicMock(return_value=mock_locator)

        return page

    @pytest.mark.asyncio
    async def test_refresh_basic(self, mock_mixin, mock_page):
        """测试基础刷新"""
        await mock_mixin.refresh_collection_box(mock_page)

        mock_page.goto.assert_called_once()
        assert "collection" in mock_page.goto.call_args[0][0]

    @pytest.mark.asyncio
    async def test_refresh_with_filter(self, mock_mixin, mock_page):
        """测试带过滤的刷新"""
        await mock_mixin.refresh_collection_box(mock_page, filter_owner="test_user")

        mock_mixin.filter_and_search.assert_called_once_with(mock_page, "test_user")

    @pytest.mark.asyncio
    async def test_refresh_filter_fails(self, mock_mixin, mock_page):
        """测试过滤失败时继续执行"""
        mock_mixin.filter_and_search = AsyncMock(return_value=False)

        # 不应抛出异常
        await mock_mixin.refresh_collection_box(mock_page, filter_owner="test_user")

    @pytest.mark.asyncio
    async def test_refresh_goto_fails(self, mock_mixin, mock_page):
        """测试 goto 失败时继续执行"""
        mock_page.goto = AsyncMock(side_effect=Exception("network error"))

        # 不应抛出异常
        await mock_mixin.refresh_collection_box(mock_page)


# ============================================================
# select_products_for_claim 测试
# ============================================================
class TestSelectProductsForClaim:
    """产品选择测试"""

    @pytest.fixture
    def mock_mixin(self):
        """创建 mock mixin 实例"""
        with patch.object(MiaoshouClaimMixin, "__init__", lambda self, **kwargs: None):
            mixin = MiaoshouClaimMixin.__new__(MiaoshouClaimMixin)
            mixin._ROW_SELECTOR = ".row"
            mixin._PAGE_SIZE = 20
            mixin._select_checkboxes_by_js = AsyncMock(return_value=5)
            mixin._jump_to_page_for_claim = AsyncMock(return_value=True)
            return mixin

    @pytest.fixture
    def mock_page(self):
        """创建模拟 Page"""
        page = MagicMock()
        page.evaluate = AsyncMock(return_value={"selected": 5})

        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.wait_for = AsyncMock()
        mock_locator.count = AsyncMock(return_value=20)
        page.locator = MagicMock(return_value=mock_locator)

        return page

    @pytest.mark.asyncio
    async def test_select_basic(self, mock_mixin, mock_page):
        """测试基础选择"""
        result = await mock_mixin.select_products_for_claim(mock_page, count=5)

        assert result is True
        mock_mixin._select_checkboxes_by_js.assert_called()

    @pytest.mark.asyncio
    async def test_select_with_specific_indexes(self, mock_mixin, mock_page):
        """测试指定索引选择"""
        mock_mixin._select_checkboxes_by_js = AsyncMock(return_value=3)

        result = await mock_mixin.select_products_for_claim(
            mock_page, count=5, indexes=[0, 2, 4]
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_select_no_rows_visible(self, mock_mixin, mock_page):
        """测试无可见行时失败"""
        mock_page.locator.return_value.first.wait_for = AsyncMock(
            side_effect=PlaywrightTimeoutError("timeout")
        )

        result = await mock_mixin.select_products_for_claim(mock_page, count=5)

        assert result is False

    @pytest.mark.asyncio
    async def test_select_zero_rows(self, mock_mixin, mock_page):
        """测试行数为 0 时失败"""
        mock_page.locator.return_value.count = AsyncMock(return_value=0)

        result = await mock_mixin.select_products_for_claim(mock_page, count=5)

        assert result is False

    @pytest.mark.asyncio
    async def test_select_cross_page(self, mock_mixin, mock_page):
        """测试跨页选择"""
        mock_mixin._select_checkboxes_by_js = AsyncMock(return_value=2)

        result = await mock_mixin.select_products_for_claim(
            mock_page, count=5, indexes=[0, 1, 25, 26]  # 索引 25, 26 在第二页
        )

        # 应该触发翻页
        mock_mixin._jump_to_page_for_claim.assert_called()


# ============================================================
# JS 方法测试
# ============================================================
class TestJsMethods:
    """JavaScript 方法测试"""

    @pytest.fixture
    def mock_mixin(self):
        """创建 mock mixin 实例"""
        with patch.object(MiaoshouClaimMixin, "__init__", lambda self, **kwargs: None):
            mixin = MiaoshouClaimMixin.__new__(MiaoshouClaimMixin)
            return mixin

    @pytest.fixture
    def mock_page(self):
        """创建模拟 Page"""
        page = MagicMock()
        page.evaluate = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_select_checkboxes_by_js_success(self, mock_mixin, mock_page):
        """测试 JS 批量勾选成功"""
        mock_page.evaluate = AsyncMock(
            return_value={
                "selected": 3,
                "isPageMode": False,
                "results": [],
                "debugInfo": {"detectedRowHeight": 128},
            }
        )

        result = await mock_mixin._select_checkboxes_by_js(mock_page, [0, 1, 2])

        assert result == 3
        mock_page.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_checkboxes_by_js_exception(self, mock_mixin, mock_page):
        """测试 JS 批量勾选异常"""
        mock_page.evaluate = AsyncMock(side_effect=Exception("JS error"))

        result = await mock_mixin._select_checkboxes_by_js(mock_page, [0, 1, 2])

        assert result == 0

    @pytest.mark.asyncio
    async def test_click_checkbox_by_js_success(self, mock_mixin, mock_page):
        """测试 JS 单个勾选成功"""
        mock_page.evaluate = AsyncMock(return_value=True)

        result = await mock_mixin._click_checkbox_by_js(mock_page, 0)

        assert result is True

    @pytest.mark.asyncio
    async def test_click_checkbox_by_js_failure(self, mock_mixin, mock_page):
        """测试 JS 单个勾选失败"""
        mock_page.evaluate = AsyncMock(return_value=False)

        result = await mock_mixin._click_checkbox_by_js(mock_page, 0)

        assert result is False

    @pytest.mark.asyncio
    async def test_click_checkbox_by_js_exception(self, mock_mixin, mock_page):
        """测试 JS 单个勾选异常"""
        mock_page.evaluate = AsyncMock(side_effect=Exception("error"))

        result = await mock_mixin._click_checkbox_by_js(mock_page, 0)

        assert result is False

    @pytest.mark.asyncio
    async def test_click_claim_button_in_row_by_js(self, mock_mixin, mock_page):
        """测试 JS 点击认领按钮"""
        mock_page.evaluate = AsyncMock(
            return_value={"success": True, "matchedY": 128}
        )

        result = await mock_mixin._click_claim_button_in_row_by_js(
            mock_page, 0, target="claim_button"
        )

        assert result["success"] is True


# ============================================================
# _jump_to_page_for_claim 测试
# ============================================================
class TestJumpToPage:
    """翻页测试"""

    @pytest.fixture
    def mock_mixin(self):
        """创建 mock mixin 实例"""
        with patch.object(MiaoshouClaimMixin, "__init__", lambda self, **kwargs: None):
            mixin = MiaoshouClaimMixin.__new__(MiaoshouClaimMixin)
            mixin._ROW_SELECTOR = ".row"
            return mixin

    @pytest.fixture
    def mock_page(self):
        """创建模拟 Page"""
        page = MagicMock()

        mock_locator = MagicMock()
        mock_locator.first = MagicMock()
        mock_locator.first.count = AsyncMock(return_value=1)
        mock_locator.first.click = AsyncMock()
        mock_locator.first.fill = AsyncMock()
        mock_locator.first.press = AsyncMock()
        mock_locator.first.wait_for = AsyncMock()
        page.locator = MagicMock(return_value=mock_locator)

        return page

    @pytest.mark.asyncio
    async def test_jump_to_page_1_no_action(self, mock_mixin, mock_page):
        """测试跳转到第 1 页无需操作"""
        result = await mock_mixin._jump_to_page_for_claim(mock_page, 1)

        assert result is True
        mock_page.locator.return_value.first.click.assert_not_called()

    @pytest.mark.asyncio
    async def test_jump_to_page_success(self, mock_mixin, mock_page):
        """测试成功跳转"""
        result = await mock_mixin._jump_to_page_for_claim(mock_page, 2)

        assert result is True
        mock_page.locator.return_value.first.fill.assert_called_with("2")

    @pytest.mark.asyncio
    async def test_jump_to_page_no_input_found(self, mock_mixin, mock_page):
        """测试未找到输入框"""
        mock_page.locator.return_value.first.count = AsyncMock(return_value=0)

        result = await mock_mixin._jump_to_page_for_claim(mock_page, 2)

        assert result is False


# ============================================================
# 边界情况测试
# ============================================================
class TestMiaoshouClaimEdgeCases:
    """边界情况测试"""

    def test_resolve_target_indexes_empty_indexes(self):
        """测试空索引列表（空列表被视为 falsy，回退到 count 模式）"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=5, indexes=[], available=10
        )
        # 空列表被视为 falsy，所以回退到使用 count
        assert result == [0, 1, 2, 3, 4]

    def test_resolve_target_indexes_zero_count(self):
        """测试 count 为 0"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=0, indexes=None, available=10
        )
        assert result == []

    def test_resolve_target_indexes_zero_available(self):
        """测试 available 为 0"""
        result = MiaoshouClaimMixin._resolve_target_indexes(
            count=5, indexes=None, available=0
        )
        assert result == []

    def test_page_grouping_calculation(self):
        """测试页码分组计算"""
        # 索引 0-19 应该在第 1 页，20-39 在第 2 页
        page_size = 20

        # 索引 0 -> 第 1 页
        assert 0 // page_size + 1 == 1

        # 索引 19 -> 第 1 页
        assert 19 // page_size + 1 == 1

        # 索引 20 -> 第 2 页
        assert 20 // page_size + 1 == 2

        # 索引 39 -> 第 2 页
        assert 39 // page_size + 1 == 2

    def test_page_relative_index_calculation(self):
        """测试页内相对索引计算"""
        page_size = 20

        # 索引 0 -> 页内索引 0
        assert 0 % page_size == 0

        # 索引 19 -> 页内索引 19
        assert 19 % page_size == 19

        # 索引 20 -> 页内索引 0
        assert 20 % page_size == 0

        # 索引 25 -> 页内索引 5
        assert 25 % page_size == 5
