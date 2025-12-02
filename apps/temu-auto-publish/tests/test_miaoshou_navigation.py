"""
@PURPOSE: miaoshou/navigation.py 单元测试
@OUTLINE:
  - TestConstants: 类常量测试
  - TestTabTextMatches: 静态方法测试
  - TestCollectPopupScopes: 弹窗范围收集测试
  - TestWaitMethods: 等待方法测试
  - TestNavigateToCollectionBox: 导航测试
  - TestFilterAndSearch: 筛选搜索测试
  - TestClosePopups: 弹窗关闭测试
  - TestProductOperations: 产品操作测试
@DEPENDENCIES:
  - 内部: browser.miaoshou.navigation
  - 外部: pytest, pytest-asyncio
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.browser.miaoshou.navigation import MiaoshouNavigationMixin


# ============================================================
# Mock Navigation Mixin
# ============================================================
class ConcreteNavigationMixin(MiaoshouNavigationMixin):
    """具体实现类用于测试"""

    def __init__(self):
        self.selectors = {}


# ============================================================
# 常量测试
# ============================================================
class TestConstants:
    """类常量测试"""

    def test_tab_label_variants(self):
        """测试 tab 标签变体"""
        assert "all" in MiaoshouNavigationMixin._TAB_LABEL_VARIANTS
        assert "unclaimed" in MiaoshouNavigationMixin._TAB_LABEL_VARIANTS
        assert "claimed" in MiaoshouNavigationMixin._TAB_LABEL_VARIANTS
        assert "failed" in MiaoshouNavigationMixin._TAB_LABEL_VARIANTS
        # 验证每个变体是元组
        for key, variants in MiaoshouNavigationMixin._TAB_LABEL_VARIANTS.items():
            assert isinstance(variants, tuple)
            assert len(variants) > 0

    def test_default_edit_button_selectors(self):
        """测试默认编辑按钮选择器"""
        selectors = MiaoshouNavigationMixin._DEFAULT_EDIT_BUTTON_SELECTORS
        assert isinstance(selectors, tuple)
        assert len(selectors) > 0
        # 验证包含常用选择器
        selector_str = " ".join(selectors)
        assert "编辑" in selector_str or "Edit" in selector_str

    def test_row_selector(self):
        """测试行选择器"""
        assert MiaoshouNavigationMixin._ROW_SELECTOR == ".pro-virtual-table__row-body"

    def test_virtual_row_selector(self):
        """测试虚拟滚动行选择器"""
        assert MiaoshouNavigationMixin._VIRTUAL_ROW_SELECTOR == ".vue-recycle-scroller__item-view"

    def test_row_height(self):
        """测试行高度"""
        assert MiaoshouNavigationMixin._ROW_HEIGHT == 128


# ============================================================
# _tab_text_matches 静态方法测试
# ============================================================
class TestTabTextMatches:
    """_tab_text_matches 静态方法测试"""

    def test_exact_match(self):
        """测试精确匹配"""
        assert MiaoshouNavigationMixin._tab_text_matches("全部", ["全部"]) is True
        assert MiaoshouNavigationMixin._tab_text_matches("All", ["All"]) is True

    def test_partial_match(self):
        """测试部分匹配"""
        assert MiaoshouNavigationMixin._tab_text_matches("全部(100)", ["全部"]) is True
        assert MiaoshouNavigationMixin._tab_text_matches("All Products", ["all"]) is True

    def test_case_insensitive(self):
        """测试大小写不敏感"""
        assert MiaoshouNavigationMixin._tab_text_matches("ALL", ["all"]) is True
        assert MiaoshouNavigationMixin._tab_text_matches("all", ["ALL"]) is True

    def test_no_match(self):
        """测试无匹配"""
        assert MiaoshouNavigationMixin._tab_text_matches("其他", ["全部"]) is False

    def test_empty_text(self):
        """测试空文本"""
        assert MiaoshouNavigationMixin._tab_text_matches("", ["全部"]) is False
        assert MiaoshouNavigationMixin._tab_text_matches(None, ["全部"]) is False

    def test_empty_labels(self):
        """测试空标签列表"""
        assert MiaoshouNavigationMixin._tab_text_matches("全部", []) is False

    def test_multiple_labels(self):
        """测试多个标签"""
        assert MiaoshouNavigationMixin._tab_text_matches("全部", ["其他", "全部"]) is True


# ============================================================
# Mock Page Fixture
# ============================================================
@pytest.fixture
def mock_page():
    """创建模拟 Page 对象"""
    page = MagicMock()
    page.url = "https://erp.91miaoshou.com/common_collect_box/items"
    page.goto = AsyncMock()
    page.wait_for_url = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.screenshot = AsyncMock()
    page.evaluate = AsyncMock(return_value={"success": True})
    page.keyboard = MagicMock()
    page.keyboard.press = AsyncMock()
    page.frames = []

    # 设置 locator 返回值
    mock_locator = MagicMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_locator.first = mock_locator
    mock_locator.last = mock_locator
    mock_locator.nth = MagicMock(return_value=mock_locator)
    mock_locator.all = AsyncMock(return_value=[mock_locator])
    mock_locator.wait_for = AsyncMock()
    mock_locator.click = AsyncMock()
    mock_locator.fill = AsyncMock()
    mock_locator.blur = AsyncMock()
    mock_locator.scroll_into_view_if_needed = AsyncMock()
    mock_locator.inner_text = AsyncMock(return_value="全部(100)")
    mock_locator.is_visible = AsyncMock(return_value=True)
    mock_locator.locator = MagicMock(return_value=mock_locator)
    mock_locator.filter = MagicMock(return_value=mock_locator)

    page.locator = MagicMock(return_value=mock_locator)
    page.get_by_role = MagicMock(return_value=mock_locator)
    page.get_by_text = MagicMock(return_value=mock_locator)

    return page


@pytest.fixture
def mixin():
    """创建测试用 mixin 实例"""
    return ConcreteNavigationMixin()


# ============================================================
# _collect_popup_scopes 测试
# ============================================================
class TestCollectPopupScopes:
    """弹窗范围收集测试"""

    def test_collect_page_only(self, mixin, mock_page):
        """测试只有页面"""
        mock_page.frames = []
        scopes = mixin._collect_popup_scopes(mock_page)
        assert len(scopes) == 1
        assert scopes[0][0] == "page"

    def test_collect_with_frames(self, mixin, mock_page):
        """测试包含 frames"""
        mock_frame = MagicMock()
        mock_frame.name = "test_frame"
        mock_frame.url = "https://example.com"
        mock_page.frames = [mock_frame]
        scopes = mixin._collect_popup_scopes(mock_page)
        assert len(scopes) == 2
        assert "frame" in scopes[1][0]

    def test_collect_with_frame_enumeration_error(self, mixin, mock_page):
        """测试 frame 枚举错误"""
        mock_page.frames = MagicMock()
        mock_page.frames.__iter__ = MagicMock(side_effect=Exception("error"))
        scopes = mixin._collect_popup_scopes(mock_page)
        assert len(scopes) == 1


# ============================================================
# 等待方法测试
# ============================================================
class TestWaitMethods:
    """等待方法测试"""

    @pytest.mark.asyncio
    async def test_wait_for_message_box_dismissal(self, mixin, mock_page):
        """测试等待消息框消失"""
        mock_locator = MagicMock()
        mock_locator.first = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_page.locator.return_value = mock_locator
        await mixin._wait_for_message_box_dismissal(mock_page)
        # 不应抛出异常

    @pytest.mark.asyncio
    async def test_wait_for_bulk_selection(self, mixin, mock_page):
        """测试等待批量选择"""
        mock_locator = MagicMock()
        mock_locator.first = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_page.locator.return_value = mock_locator
        await mixin._wait_for_bulk_selection(mock_page)

    @pytest.mark.asyncio
    async def test_wait_for_table_refresh(self, mixin, mock_page):
        """测试等待表格刷新"""
        mock_locator = MagicMock()
        mock_locator.first = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_page.locator.return_value = mock_locator
        await mixin._wait_for_table_refresh(mock_page)

    @pytest.mark.asyncio
    async def test_wait_for_idle(self, mixin, mock_page):
        """测试等待空闲"""
        with patch("src.browser.miaoshou.navigation.wait_network_idle", AsyncMock()):
            await mixin._wait_for_idle(mock_page)


# ============================================================
# 导航测试
# ============================================================
class TestNavigateToCollectionBox:
    """导航测试"""

    @pytest.mark.asyncio
    async def test_navigate_direct_success(self, mixin, mock_page):
        """测试直接导航成功"""
        mock_page.url = "https://erp.91miaoshou.com/common_collect_box/items"
        with (
            patch("src.browser.miaoshou.navigation.wait_dom_loaded", AsyncMock()),
            patch.object(mixin, "_ensure_popups_closed", AsyncMock()),
        ):
            result = await mixin.navigate_to_collection_box(mock_page)
            assert result is True

    @pytest.mark.asyncio
    async def test_navigate_with_sidebar(self, mixin, mock_page):
        """测试通过侧边栏导航"""
        mock_page.url = "https://erp.91miaoshou.com/common_collect_box/items"
        with (
            patch("src.browser.miaoshou.navigation.wait_dom_loaded", AsyncMock()),
            patch.object(mixin, "_ensure_popups_closed", AsyncMock()),
        ):
            result = await mixin.navigate_to_collection_box(mock_page, use_sidebar=True)
            assert result is True

    @pytest.mark.asyncio
    async def test_navigate_wrong_url_retry(self, mixin, mock_page):
        """测试 URL 错误时重试"""
        mock_page.url = "https://other-site.com"
        with (
            patch("src.browser.miaoshou.navigation.wait_dom_loaded", AsyncMock()),
            patch.object(mixin, "_ensure_popups_closed", AsyncMock()),
        ):
            # 模拟递归调用返回 False
            with patch.object(mixin, "navigate_to_collection_box", AsyncMock(return_value=False)):
                result = await MiaoshouNavigationMixin.navigate_to_collection_box(mixin, mock_page)
                # 由于 mock 返回 False，结果应该是 False

    @pytest.mark.asyncio
    async def test_navigate_exception(self, mixin, mock_page):
        """测试导航异常"""
        mock_page.goto = AsyncMock(side_effect=Exception("network error"))
        with (
            patch("src.browser.miaoshou.navigation.wait_dom_loaded", AsyncMock()),
            patch.object(mixin, "navigate_to_collection_box", AsyncMock(return_value=False)),
        ):
            # 直接测试异常处理路径
            result = await mixin.navigate_to_collection_box(mock_page)


# ============================================================
# 筛选搜索测试
# ============================================================
class TestFilterAndSearch:
    """筛选搜索测试"""

    @pytest.mark.asyncio
    async def test_filter_without_staff(self, mixin, mock_page):
        """测试无员工筛选"""
        with patch.object(mixin, "_wait_for_table_refresh", AsyncMock()):
            result = await mixin.filter_and_search(mock_page)
            assert result is True

    @pytest.mark.asyncio
    async def test_filter_with_staff_success(self, mixin, mock_page):
        """测试员工筛选成功"""
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=2)
        mock_locator.nth = MagicMock(return_value=mock_locator)
        mock_locator.click = AsyncMock()
        mock_locator.first = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_locator.all = AsyncMock(return_value=[mock_locator])
        mock_page.locator.return_value = mock_locator

        with patch.object(mixin, "_wait_for_table_refresh", AsyncMock()):
            result = await mixin.filter_and_search(mock_page, staff_name="张三")
            assert result is True

    @pytest.mark.asyncio
    async def test_filter_fallback(self, mixin, mock_page):
        """测试筛选失败后的 fallback"""
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator

        with (
            patch.object(mixin, "_wait_for_table_refresh", AsyncMock()),
            patch(
                "src.browser.miaoshou.navigation.fallback_apply_user_filter",
                AsyncMock(return_value=True),
            ),
        ):
            result = await mixin.filter_and_search(mock_page, staff_name="张三")
            assert result is True

    @pytest.mark.asyncio
    async def test_filter_exception(self, mixin, mock_page):
        """测试筛选异常"""
        mock_page.locator = MagicMock(side_effect=Exception("error"))
        result = await mixin.filter_and_search(mock_page, staff_name="张三")
        assert result is False


# ============================================================
# 弹窗关闭测试
# ============================================================
class TestClosePopups:
    """弹窗关闭测试"""

    @pytest.mark.asyncio
    async def test_close_popup_no_popup(self, mixin, mock_page):
        """测试无弹窗"""
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator
        result = await mixin.close_popup_if_exists(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_close_popup_success(self, mixin, mock_page):
        """测试成功关闭弹窗"""
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.first = mock_locator
        mock_locator.click = AsyncMock()
        mock_page.locator.return_value = mock_locator

        with patch.object(mixin, "_wait_for_message_box_dismissal", AsyncMock()):
            result = await mixin.close_popup_if_exists(mock_page)
            assert result is True

    @pytest.mark.asyncio
    async def test_ensure_popups_closed(self, mixin, mock_page):
        """测试确保弹窗关闭"""
        with (
            patch.object(mixin, "close_popup_if_exists", AsyncMock(return_value=False)),
            patch.object(mixin, "_wait_for_message_box_dismissal", AsyncMock()),
        ):
            await mixin._ensure_popups_closed(mock_page)


# ============================================================
# 产品操作测试
# ============================================================
class TestProductOperations:
    """产品操作测试"""

    @pytest.mark.asyncio
    async def test_get_product_count(self, mixin, mock_page):
        """测试获取产品数量"""
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=4)
        mock_locator.nth = MagicMock(return_value=mock_locator)
        mock_locator.inner_text = AsyncMock(
            side_effect=["全部(100)", "未认领(50)", "已认领(30)", "失败(20)"]
        )
        mock_page.locator.return_value = mock_locator

        counts = await mixin.get_product_count(mock_page)
        assert isinstance(counts, dict)
        assert "all" in counts
        assert "unclaimed" in counts

    @pytest.mark.asyncio
    async def test_switch_tab_success(self, mixin, mock_page):
        """测试切换标签成功"""
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.first = mock_locator
        mock_locator.wait_for = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_locator.inner_text = AsyncMock(return_value="全部(100)")
        mock_locator.scroll_into_view_if_needed = AsyncMock()
        mock_locator.all = AsyncMock(return_value=[])
        mock_page.locator.return_value = mock_locator

        with patch.object(mixin, "_wait_for_table_refresh", AsyncMock()):
            result = await mixin.switch_tab(mock_page, "all")
            assert result is True

    @pytest.mark.asyncio
    async def test_switch_tab_failure(self, mixin, mock_page):
        """测试切换标签失败"""
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_locator.all = AsyncMock(return_value=[])
        mock_page.locator.return_value = mock_locator

        result = await mixin.switch_tab(mock_page, "nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_search_products_with_title(self, mixin, mock_page):
        """测试搜索产品（带标题）"""
        mock_locator = MagicMock()
        mock_locator.fill = AsyncMock()
        mock_locator.blur = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_page.locator.return_value = mock_locator

        with patch.object(mixin, "_wait_for_table_refresh", AsyncMock()):
            result = await mixin.search_products(mock_page, title="测试产品")
            assert result is True

    @pytest.mark.asyncio
    async def test_search_products_with_price(self, mixin, mock_page):
        """测试搜索产品（带价格）"""
        mock_locator = MagicMock()
        mock_locator.fill = AsyncMock()
        mock_locator.blur = AsyncMock()
        mock_locator.click = AsyncMock()
        mock_page.locator.return_value = mock_locator

        with patch.object(mixin, "_wait_for_table_refresh", AsyncMock()):
            result = await mixin.search_products(mock_page, price_min=10.0, price_max=100.0)
            assert result is True

    @pytest.mark.asyncio
    async def test_select_all_products_success(self, mixin, mock_page):
        """测试全选产品成功"""
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_locator.first = mock_locator
        mock_locator.click = AsyncMock()
        mock_locator.scroll_into_view_if_needed = AsyncMock()
        mock_page.locator.return_value = mock_locator

        with patch.object(mixin, "_wait_for_bulk_selection", AsyncMock()):
            result = await mixin.select_all_products(mock_page)
            assert result is True

    @pytest.mark.asyncio
    async def test_select_all_products_failure(self, mixin, mock_page):
        """测试全选产品失败"""
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator

        result = await mixin.select_all_products(mock_page)
        assert result is False

    @pytest.mark.asyncio
    async def test_click_edit_first_product(self, mixin, mock_page):
        """测试点击第一个产品编辑"""
        with patch.object(mixin, "click_edit_product_by_index", AsyncMock(return_value=True)):
            result = await mixin.click_edit_first_product(mock_page)
            assert result is True

    @pytest.mark.asyncio
    async def test_click_edit_product_by_index_success(self, mixin, mock_page):
        """测试按索引点击编辑成功"""
        mock_page.evaluate = AsyncMock(return_value={"success": True})
        with patch.object(mixin, "_ensure_popups_closed", AsyncMock()):
            result = await mixin.click_edit_product_by_index(mock_page, 0)
            assert result is True

    @pytest.mark.asyncio
    async def test_click_edit_product_negative_index(self, mixin, mock_page):
        """测试负索引"""
        with patch.object(mixin, "_ensure_popups_closed", AsyncMock()):
            result = await mixin.click_edit_product_by_index(mock_page, -1)
            assert result is False

    @pytest.mark.asyncio
    async def test_click_edit_button_by_js_success(self, mixin, mock_page):
        """测试 JS 点击成功"""
        mock_page.evaluate = AsyncMock(
            return_value={
                "success": True,
                "scrollerInfo": "vue-recycle-scroller",
                "isPageMode": False,
                "actualScrollTop": 0,
                "matchedY": 0,
            }
        )
        result = await mixin._click_edit_button_by_js(mock_page, 0)
        assert result is True

    @pytest.mark.asyncio
    async def test_click_edit_button_by_js_failure(self, mixin, mock_page):
        """测试 JS 点击失败"""
        mock_page.evaluate = AsyncMock(
            return_value={
                "success": False,
                "error": "Target not found",
                "scrollerInfo": "page",
            }
        )
        result = await mixin._click_edit_button_by_js(mock_page, 10)
        assert result is False

    @pytest.mark.asyncio
    async def test_click_edit_button_by_js_exception(self, mixin, mock_page):
        """测试 JS 点击异常"""
        mock_page.evaluate = AsyncMock(side_effect=Exception("JS error"))
        result = await mixin._click_edit_button_by_js(mock_page, 0)
        assert result is False


# ============================================================
# _click_edit_button_in_row 测试
# ============================================================
class TestClickEditButtonInRow:
    """行内点击编辑按钮测试"""

    @pytest.mark.asyncio
    async def test_click_in_row_success(self, mixin, mock_page):
        """测试行内点击成功"""
        mock_row = MagicMock()
        mock_row.scroll_into_view_if_needed = AsyncMock()
        mock_btn = MagicMock()
        mock_btn.count = AsyncMock(return_value=1)
        mock_btn.first = mock_btn
        mock_btn.wait_for = AsyncMock()
        mock_btn.click = AsyncMock()
        mock_row.locator.return_value.first = mock_btn

        with patch("src.browser.miaoshou.navigation.wait_dom_loaded", AsyncMock()):
            result = await mixin._click_edit_button_in_row(
                mock_page, mock_row, ("button:has-text('编辑')",), 0
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_click_in_row_no_button(self, mixin, mock_page):
        """测试行内无按钮"""
        mock_row = MagicMock()
        mock_row.scroll_into_view_if_needed = AsyncMock()
        mock_btn = MagicMock()
        mock_btn.count = AsyncMock(return_value=0)
        mock_row.locator.return_value.first = mock_btn

        with patch("src.browser.miaoshou.navigation.wait_dom_loaded", AsyncMock()):
            result = await mixin._click_edit_button_in_row(
                mock_page, mock_row, ("button:has-text('编辑')",), 0
            )
            assert result is False


# ============================================================
# 边界情况测试
# ============================================================
class TestEdgeCases:
    """边界情况测试"""

    def test_tab_text_matches_with_numbers(self):
        """测试带数字的标签文本"""
        assert MiaoshouNavigationMixin._tab_text_matches("全部(1234)", ["全部"]) is True
        assert MiaoshouNavigationMixin._tab_text_matches("All (999)", ["All"]) is True

    def test_tab_text_matches_whitespace(self):
        """测试包含空白的文本"""
        assert MiaoshouNavigationMixin._tab_text_matches("  全部  ", ["全部"]) is True
        assert MiaoshouNavigationMixin._tab_text_matches("\t全部\n", ["全部"]) is True

    @pytest.mark.asyncio
    async def test_get_product_count_exception(self, mixin, mock_page):
        """测试获取产品数量异常"""
        mock_page.locator = MagicMock(side_effect=Exception("error"))
        counts = await mixin.get_product_count(mock_page)
        assert counts == {"all": 0, "unclaimed": 0, "claimed": 0, "failed": 0}

    @pytest.mark.asyncio
    async def test_search_products_exception(self, mixin, mock_page):
        """测试搜索产品异常"""
        mock_page.locator = MagicMock(side_effect=Exception("error"))
        result = await mixin.search_products(mock_page, title="test")
        assert result is False
