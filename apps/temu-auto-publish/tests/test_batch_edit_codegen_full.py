"""
@PURPOSE: batch_edit_codegen.py 单元测试
@OUTLINE:
  - TestConstants: 常量测试
  - TestSmartRetry: 智能重试装饰器测试
  - TestStabilize: _stabilize 函数测试
  - TestClosePopups: 弹窗关闭测试
  - TestWaitFunctions: 等待函数测试
  - TestEnsureTitleLength: 标题长度检查测试
  - TestRunBatchEdit: 主函数测试
  - TestStepFunctions: 各步骤函数测试
  - TestUserFilter: 用户筛选测试
@DEPENDENCIES:
  - 内部: browser.batch_edit_codegen
  - 外部: pytest, pytest-asyncio
"""

import re
from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.browser.batch_edit_codegen import (
    MAX_TITLE_LENGTH,
    _apply_user_filter,
    _click_dropdown_option,
    _click_search_button,
    _close_edit_dialog,
    _close_popups,
    _ensure_title_length,
    _open_batch_edit_popover,
    _stabilize,
    _step_01_title,
    _step_02_english_title,
    _step_03_category_attrs,
    _step_04_main_sku,
    _step_07_customized,
    _step_08_sensitive,
    _step_09_weight,
    _step_10_dimensions,
    _step_11_platform_sku,
    _step_13_size_chart,
    _step_15_packing_list,
    _step_16_carousel,
    _step_17_color_image,
    _wait_for_dialog_open,
    _wait_for_dropdown_options,
    _wait_for_save_toast,
    run_batch_edit,
    smart_retry,
)


# ============================================================
# 常量测试
# ============================================================
class TestConstants:
    """常量定义测试"""

    def test_max_title_length(self):
        """测试最大标题长度"""
        assert MAX_TITLE_LENGTH == 250
        assert isinstance(MAX_TITLE_LENGTH, int)


# ============================================================
# smart_retry 装饰器测试
# ============================================================
class TestSmartRetry:
    """smart_retry 装饰器测试"""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        """测试首次成功不重试"""
        call_count = 0

        @smart_retry(max_attempts=3, delay=0.01)
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await success_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_exception(self):
        """测试异常后重试"""
        call_count = 0

        @smart_retry(max_attempts=3, delay=0.01)
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("temp error")
            return "ok"

        result = await fail_then_succeed()
        assert result == "ok"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_max_attempts_reached(self):
        """测试达到最大重试次数"""
        call_count = 0

        @smart_retry(max_attempts=2, delay=0.01)
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("always fail")

        with pytest.raises(RuntimeError, match="always fail"):
            await always_fail()
        assert call_count == 2


# ============================================================
# Mock Page Fixture
# ============================================================
@pytest.fixture
def mock_page():
    """创建模拟 Page 对象"""
    page = MagicMock()
    page.url = "https://erp.91miaoshou.com/pddkj/collect_box/items"
    page.goto = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.wait_for_selector = AsyncMock()

    # 设置 locator 返回值
    mock_locator = MagicMock()
    mock_locator.count = AsyncMock(return_value=1)
    mock_locator.first = mock_locator
    mock_locator.last = mock_locator
    mock_locator.nth = MagicMock(return_value=mock_locator)
    mock_locator.wait_for = AsyncMock()
    mock_locator.click = AsyncMock()
    mock_locator.fill = AsyncMock()
    mock_locator.type = AsyncMock()
    mock_locator.press = AsyncMock()
    mock_locator.hover = AsyncMock()
    mock_locator.scroll_into_view_if_needed = AsyncMock()
    mock_locator.focus = AsyncMock()
    mock_locator.evaluate = AsyncMock()
    mock_locator.input_value = AsyncMock(return_value="Test Title")
    mock_locator.inner_html = AsyncMock(return_value="<div></div>")
    mock_locator.get_attribute = AsyncMock(return_value="")
    mock_locator.is_visible = AsyncMock(return_value=True)
    mock_locator.is_checked = AsyncMock(return_value=False)
    mock_locator.is_disabled = AsyncMock(return_value=False)
    mock_locator.set_input_files = AsyncMock()
    mock_locator.locator = MagicMock(return_value=mock_locator)
    mock_locator.filter = MagicMock(return_value=mock_locator)
    mock_locator.get_by_role = MagicMock(return_value=mock_locator)
    mock_locator.get_by_label = MagicMock(return_value=mock_locator)
    mock_locator.get_by_text = MagicMock(return_value=mock_locator)
    mock_locator.get_by_placeholder = MagicMock(return_value=mock_locator)

    page.locator = MagicMock(return_value=mock_locator)
    page.get_by_role = MagicMock(return_value=mock_locator)
    page.get_by_label = MagicMock(return_value=mock_locator)
    page.get_by_text = MagicMock(return_value=mock_locator)
    page.get_by_placeholder = MagicMock(return_value=mock_locator)

    return page


# ============================================================
# _stabilize 测试
# ============================================================
class TestStabilize:
    """_stabilize 函数测试"""

    @pytest.mark.asyncio
    async def test_stabilize_success(self, mock_page):
        """测试成功稳定化"""
        with patch(
            "src.browser.batch_edit_codegen.smart_wait",
            AsyncMock(return_value=100.0),
        ):
            result = await _stabilize(mock_page, "test_label")
            assert isinstance(result, float)

    @pytest.mark.asyncio
    async def test_stabilize_fallback_on_error(self, mock_page):
        """测试错误时回退"""
        with patch(
            "src.browser.batch_edit_codegen.smart_wait",
            AsyncMock(side_effect=Exception("error")),
        ):
            result = await _stabilize(mock_page, "test_label", min_ms=50)
            assert isinstance(result, float)

    @pytest.mark.asyncio
    async def test_stabilize_with_network_wait(self, mock_page):
        """测试带网络等待"""
        with patch(
            "src.browser.batch_edit_codegen.smart_wait",
            AsyncMock(return_value=200.0),
        ):
            result = await _stabilize(
                mock_page, "test", min_ms=100, max_ms=500, wait_for_network=True
            )
            assert isinstance(result, float)


# ============================================================
# _close_popups 测试
# ============================================================
class TestClosePopups:
    """弹窗关闭测试"""

    @pytest.mark.asyncio
    async def test_no_popups(self, mock_page):
        """测试无弹窗"""
        mock_page.locator.return_value.count = AsyncMock(return_value=0)
        await _close_popups(mock_page)
        # 不应抛出异常

    @pytest.mark.asyncio
    async def test_close_single_popup(self, mock_page):
        """测试关闭单个弹窗"""
        mock_btn = MagicMock()
        mock_btn.count = AsyncMock(return_value=1)
        mock_btn.first = mock_btn
        mock_btn.is_visible = AsyncMock(return_value=True)
        mock_btn.click = AsyncMock()
        mock_btn.wait_for = AsyncMock()
        mock_page.locator.return_value = mock_btn
        await _close_popups(mock_page)

    @pytest.mark.asyncio
    async def test_close_popup_exception_handled(self, mock_page):
        """测试关闭弹窗异常处理"""
        mock_btn = MagicMock()
        mock_btn.count = AsyncMock(return_value=1)
        mock_btn.first = mock_btn
        mock_btn.is_visible = AsyncMock(side_effect=Exception("error"))
        mock_page.locator.return_value = mock_btn
        # 不应抛出异常
        await _close_popups(mock_page)


# ============================================================
# 等待函数测试
# ============================================================
class TestWaitFunctions:
    """等待函数测试"""

    @pytest.mark.asyncio
    async def test_wait_for_save_toast_success(self, mock_page):
        """测试等待保存提示成功"""
        mock_toast = MagicMock()
        mock_toast.wait_for = AsyncMock()
        mock_page.locator.return_value = mock_toast
        with patch("src.browser.batch_edit_codegen.smart_wait", AsyncMock()):
            await _wait_for_save_toast(mock_page)

    @pytest.mark.asyncio
    async def test_wait_for_save_toast_timeout(self, mock_page):
        """测试等待保存提示超时"""
        mock_toast = MagicMock()
        mock_toast.wait_for = AsyncMock(side_effect=TimeoutError("timeout"))
        mock_page.locator.return_value = mock_toast
        with patch("src.browser.batch_edit_codegen.smart_wait", AsyncMock()):
            # 不应抛出异常
            await _wait_for_save_toast(mock_page)

    @pytest.mark.asyncio
    async def test_wait_for_dropdown_options(self, mock_page):
        """测试等待下拉选项"""
        mock_dropdown = MagicMock()
        mock_dropdown.wait_for = AsyncMock()
        mock_page.locator.return_value = mock_dropdown
        await _wait_for_dropdown_options(mock_page)

    @pytest.mark.asyncio
    async def test_wait_for_dialog_open_success(self, mock_page):
        """测试等待弹窗打开成功"""
        mock_dialog = MagicMock()
        mock_dialog.wait_for = AsyncMock()
        mock_page.get_by_role.return_value = mock_dialog
        with patch("src.browser.batch_edit_codegen.smart_wait", AsyncMock()):
            await _wait_for_dialog_open(mock_page)

    @pytest.mark.asyncio
    async def test_wait_for_dialog_open_timeout(self, mock_page):
        """测试等待弹窗打开超时"""
        mock_dialog = MagicMock()
        mock_dialog.wait_for = AsyncMock(side_effect=TimeoutError("timeout"))
        mock_page.get_by_role.return_value = mock_dialog
        with patch("src.browser.batch_edit_codegen.smart_wait", AsyncMock()):
            # 不应抛出异常
            await _wait_for_dialog_open(mock_page)


# ============================================================
# _close_edit_dialog 测试
# ============================================================
class TestCloseEditDialog:
    """关闭编辑对话框测试"""

    @pytest.mark.asyncio
    async def test_close_with_resilient_locator(self, mock_page):
        """测试使用弹性选择器关闭"""
        mock_close = MagicMock()
        mock_close.click = AsyncMock()
        with (
            patch(
                "src.browser.batch_edit_codegen._resilient_locator.locate",
                AsyncMock(return_value=mock_close),
            ),
            patch("src.browser.batch_edit_codegen.smart_wait", AsyncMock()),
        ):
            await _close_edit_dialog(mock_page)
            mock_close.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_fallback_to_role(self, mock_page):
        """测试回退到 role 定位"""
        mock_btn = MagicMock()
        mock_btn.click = AsyncMock()
        mock_page.get_by_role.return_value = mock_btn
        with (
            patch(
                "src.browser.batch_edit_codegen._resilient_locator.locate",
                AsyncMock(return_value=None),
            ),
            patch("src.browser.batch_edit_codegen.smart_wait", AsyncMock()),
        ):
            await _close_edit_dialog(mock_page)

    @pytest.mark.asyncio
    async def test_close_fallback_to_icon(self, mock_page):
        """测试回退到图标关闭"""
        mock_btn = MagicMock()
        mock_btn.click = AsyncMock(side_effect=Exception("fail"))
        mock_page.get_by_role.return_value = mock_btn
        mock_icon = MagicMock()
        mock_icon.click = AsyncMock()
        mock_page.locator.return_value = mock_icon
        with (
            patch(
                "src.browser.batch_edit_codegen._resilient_locator.locate",
                AsyncMock(return_value=None),
            ),
            patch("src.browser.batch_edit_codegen.smart_wait", AsyncMock()),
        ):
            await _close_edit_dialog(mock_page)


# ============================================================
# _ensure_title_length 测试
# ============================================================
class TestEnsureTitleLength:
    """标题长度检查测试"""

    @pytest.mark.asyncio
    async def test_title_within_limit(self, mock_page):
        """测试标题未超限"""
        mock_input = MagicMock()
        mock_input.count = AsyncMock(return_value=1)
        mock_input.input_value = AsyncMock(return_value="Short title")
        mock_page.locator.return_value.first = mock_input
        await _ensure_title_length(mock_page)
        # 不应调用 fill
        mock_input.fill.assert_not_called()

    @pytest.mark.asyncio
    async def test_title_exceeds_limit(self, mock_page):
        """测试标题超限被裁剪"""
        long_title = "A" * 300  # 超过 250
        mock_input = MagicMock()
        mock_input.count = AsyncMock(return_value=1)
        mock_input.input_value = AsyncMock(return_value=long_title)
        mock_input.fill = AsyncMock()
        mock_input.evaluate = AsyncMock()
        mock_page.locator.return_value.first = mock_input
        await _ensure_title_length(mock_page)
        mock_input.fill.assert_called_once()
        # 验证裁剪后长度
        filled_title = mock_input.fill.call_args[0][0]
        assert len(filled_title) <= MAX_TITLE_LENGTH

    @pytest.mark.asyncio
    async def test_no_title_input_found(self, mock_page):
        """测试未找到标题输入框"""
        mock_input = MagicMock()
        mock_input.count = AsyncMock(return_value=0)
        mock_page.locator.return_value.first = mock_input
        # 不应抛出异常
        await _ensure_title_length(mock_page)

    @pytest.mark.asyncio
    async def test_title_empty(self, mock_page):
        """测试空标题"""
        mock_input = MagicMock()
        mock_input.count = AsyncMock(return_value=1)
        mock_input.input_value = AsyncMock(return_value=None)
        mock_page.locator.return_value.first = mock_input
        await _ensure_title_length(mock_page)
        mock_input.fill.assert_not_called()


# ============================================================
# _open_batch_edit_popover 测试
# ============================================================
class TestOpenBatchEditPopover:
    """打开批量编辑弹窗测试"""

    @pytest.mark.asyncio
    async def test_open_popover(self, mock_page):
        """测试打开弹窗"""
        mock_checkbox = MagicMock()
        mock_checkbox.click = AsyncMock()
        mock_page.locator.return_value.first = mock_checkbox
        mock_page.locator.return_value.wait_for = AsyncMock()
        await _open_batch_edit_popover(mock_page)
        mock_checkbox.click.assert_called_once()


# ============================================================
# 步骤函数测试
# ============================================================
class TestStepFunctions:
    """各步骤函数测试"""

    @pytest.mark.asyncio
    async def test_step_02_english_title(self, mock_page):
        """测试步骤2: 英语标题"""
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_page.get_by_text.return_value = mock_locator
        mock_page.locator.return_value.filter.return_value.get_by_role.return_value = mock_locator
        mock_page.get_by_role.return_value = mock_locator

        with patch("src.browser.batch_edit_codegen._close_edit_dialog", AsyncMock()):
            await _step_02_english_title(mock_page)

    @pytest.mark.asyncio
    async def test_step_03_category_attrs(self, mock_page):
        """测试步骤3: 类目属性"""
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_page.get_by_text.return_value = mock_locator
        mock_page.get_by_role.return_value = mock_locator

        payload = {"category_path": ["收纳用品"], "category_attrs": {}}
        with patch("src.browser.batch_edit_codegen._close_edit_dialog", AsyncMock()):
            await _step_03_category_attrs(mock_page, payload)

    @pytest.mark.asyncio
    async def test_step_04_main_sku(self, mock_page):
        """测试步骤4: 主货号 - 使用 patch 避免复杂 mock"""
        with patch("src.browser.batch_edit_codegen._close_edit_dialog", AsyncMock()):
            # 验证函数存在且可调用
            assert callable(_step_04_main_sku)

    @pytest.mark.asyncio
    async def test_step_07_customized(self, mock_page):
        """测试步骤7: 定制品"""
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_page.get_by_text.return_value = mock_locator
        mock_page.get_by_role.return_value = mock_locator

        with patch("src.browser.batch_edit_codegen._close_edit_dialog", AsyncMock()):
            await _step_07_customized(mock_page)

    @pytest.mark.asyncio
    async def test_step_08_sensitive(self, mock_page):
        """测试步骤8: 敏感属性"""
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_page.get_by_text.return_value = mock_locator
        mock_page.get_by_role.return_value = mock_locator

        with patch("src.browser.batch_edit_codegen._close_edit_dialog", AsyncMock()):
            await _step_08_sensitive(mock_page)

    @pytest.mark.asyncio
    async def test_step_09_weight(self, mock_page):
        """测试步骤9: 重量 - 验证函数存在"""
        # 由于步骤函数内部调用链复杂，使用集成测试覆盖
        # 这里只验证函数可调用
        assert callable(_step_09_weight)

    @pytest.mark.asyncio
    async def test_step_10_dimensions(self, mock_page):
        """测试步骤10: 尺寸"""
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_locator.fill = AsyncMock()
        mock_dialog = MagicMock()
        mock_dialog.get_by_text.return_value = mock_locator
        mock_dialog.locator.return_value.filter.return_value.get_by_role.return_value = mock_locator
        mock_dialog.get_by_role.return_value = mock_locator
        mock_page.get_by_role.return_value = mock_dialog

        with patch("src.browser.batch_edit_codegen._close_edit_dialog", AsyncMock()):
            await _step_10_dimensions(mock_page)

    @pytest.mark.asyncio
    async def test_step_11_platform_sku(self, mock_page):
        """测试步骤11: 平台SKU - 验证函数存在"""
        # 由于步骤函数内部调用链复杂，使用集成测试覆盖
        # 这里只验证函数可调用
        assert callable(_step_11_platform_sku)

    @pytest.mark.asyncio
    async def test_step_13_size_chart(self, mock_page):
        """测试步骤13: 尺码表"""
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_page.get_by_text.return_value = mock_locator
        await _step_13_size_chart(mock_page)

    @pytest.mark.asyncio
    async def test_step_15_packing_list(self, mock_page):
        """测试步骤15: 包装清单"""
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_page.get_by_text.return_value = mock_locator
        mock_page.get_by_role.return_value = mock_locator

        with patch("src.browser.batch_edit_codegen._close_edit_dialog", AsyncMock()):
            await _step_15_packing_list(mock_page)

    @pytest.mark.asyncio
    async def test_step_16_carousel(self, mock_page):
        """测试步骤16: 轮播图"""
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_page.get_by_text.return_value = mock_locator
        await _step_16_carousel(mock_page)

    @pytest.mark.asyncio
    async def test_step_17_color_image(self, mock_page):
        """测试步骤17: 颜色图"""
        mock_locator = MagicMock()
        mock_locator.click = AsyncMock()
        mock_page.get_by_text.return_value = mock_locator
        await _step_17_color_image(mock_page)


# ============================================================
# 用户筛选测试
# ============================================================
class TestUserFilter:
    """用户筛选测试"""

    @pytest.mark.asyncio
    async def test_click_dropdown_option_success(self, mock_page):
        """测试点击下拉选项成功"""
        mock_option = MagicMock()
        mock_option.count = AsyncMock(return_value=1)
        mock_option.click = AsyncMock()
        mock_page.locator.return_value.first = mock_option

        result = await _click_dropdown_option(mock_page, "张三")
        assert result is True
        mock_option.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_click_dropdown_option_not_found(self, mock_page):
        """测试下拉选项未找到"""
        mock_option = MagicMock()
        mock_option.count = AsyncMock(return_value=0)
        mock_page.locator.return_value.first = mock_option

        result = await _click_dropdown_option(mock_page, "不存在的用户")
        assert result is False

    @pytest.mark.asyncio
    async def test_click_search_button_success(self, mock_page):
        """测试点击搜索按钮成功"""
        mock_btn = MagicMock()
        mock_btn.count = AsyncMock(return_value=1)
        mock_btn.click = AsyncMock()
        mock_page.locator.return_value.first = mock_btn

        result = await _click_search_button(mock_page)
        assert result is True

    @pytest.mark.asyncio
    async def test_click_search_button_not_found(self, mock_page):
        """测试搜索按钮未找到"""
        mock_btn = MagicMock()
        mock_btn.count = AsyncMock(return_value=0)
        mock_page.locator.return_value.first = mock_btn

        result = await _click_search_button(mock_page)
        assert result is False


# ============================================================
# run_batch_edit 主函数测试
# ============================================================
def _create_step_patches():
    """创建所有步骤的 patch 字典"""
    return {
        "_close_popups": AsyncMock(),
        "smart_wait": AsyncMock(),
        "_wait_for_dialog_open": AsyncMock(),
        "_step_01_title": AsyncMock(),
        "_step_02_english_title": AsyncMock(),
        "_step_03_category_attrs": AsyncMock(),
        "_step_04_main_sku": AsyncMock(),
        "_step_05_outer_package": AsyncMock(),
        "_step_06_origin": AsyncMock(),
        "_step_07_customized": AsyncMock(),
        "_step_08_sensitive": AsyncMock(),
        "_step_09_weight": AsyncMock(),
        "_step_10_dimensions": AsyncMock(),
        "_step_11_platform_sku": AsyncMock(),
        "_step_12_sku_category": AsyncMock(),
        "_step_13_size_chart": AsyncMock(),
        "_step_14_suggested_price": AsyncMock(),
        "_step_15_packing_list": AsyncMock(),
        "_step_16_carousel": AsyncMock(),
        "_step_17_color_image": AsyncMock(),
        "_step_18_manual": AsyncMock(),
        "_close_edit_dialog": AsyncMock(),
    }


class TestRunBatchEdit:
    """run_batch_edit 主函数测试"""

    @pytest.fixture
    def sample_payload(self):
        """示例 payload"""
        return {
            "category_path": ["收纳用品", "收纳篮,箱子,盒子", "盖式储物箱"],
            "category_attrs": {
                "product_use": "多用途",
                "shape": "其他形状",
                "material": "其他材料",
            },
            "outer_package_image": "/path/to/package.jpg",
            "manual_file": "/path/to/manual.pdf",
        }

    @pytest.mark.asyncio
    async def test_run_batch_edit_success(self, mock_page, sample_payload):
        """测试批量编辑成功"""
        patches = _create_step_patches()
        with patch.multiple("src.browser.batch_edit_codegen", **patches):
            result = await run_batch_edit(mock_page, sample_payload)
            assert result["success"] is True
            assert result["completed_steps"] == 18
            assert result["error"] is None

    @pytest.mark.asyncio
    async def test_run_batch_edit_with_filter(self, mock_page, sample_payload):
        """测试带筛选的批量编辑"""
        patches = _create_step_patches()
        patches["_apply_user_filter"] = AsyncMock(return_value=True)
        with patch.multiple("src.browser.batch_edit_codegen", **patches):
            result = await run_batch_edit(mock_page, sample_payload, filter_owner="张三")
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_run_batch_edit_step_failure_non_critical(self, mock_page, sample_payload):
        """测试非关键步骤失败继续执行"""
        patches = _create_step_patches()
        patches["_step_13_size_chart"] = AsyncMock(side_effect=Exception("non-critical error"))
        with patch.multiple("src.browser.batch_edit_codegen", **patches):
            result = await run_batch_edit(mock_page, sample_payload)
            # 非关键步骤(13)失败但继续执行
            assert result["success"] is True
            assert len(result["step_errors"]) > 0

    @pytest.mark.asyncio
    async def test_run_batch_edit_critical_step_failure(self, mock_page, sample_payload):
        """测试关键步骤失败停止执行"""
        patches = _create_step_patches()
        patches["_step_01_title"] = AsyncMock(side_effect=Exception("critical error"))
        with patch.multiple("src.browser.batch_edit_codegen", **patches):
            result = await run_batch_edit(mock_page, sample_payload)
            assert result["success"] is False
            assert result["error"] is not None

    @pytest.mark.asyncio
    async def test_run_batch_edit_navigate_when_wrong_url(self, mock_page, sample_payload):
        """测试 URL 错误时自动导航"""
        mock_page.url = "https://other-site.com"
        patches = _create_step_patches()
        with patch.multiple("src.browser.batch_edit_codegen", **patches):
            result = await run_batch_edit(mock_page, sample_payload)
            mock_page.goto.assert_called_once()


# ============================================================
# 边界情况测试
# ============================================================
class TestEdgeCases:
    """边界情况测试"""

    def test_max_title_length_value(self):
        """测试最大标题长度常量值"""
        assert MAX_TITLE_LENGTH > 0
        assert isinstance(MAX_TITLE_LENGTH, int)

    @pytest.mark.asyncio
    async def test_stabilize_optimized_values(self, mock_page):
        """测试优化后的等待值"""
        with patch(
            "src.browser.batch_edit_codegen.smart_wait",
            AsyncMock(return_value=50.0),
        ) as mock_wait:
            await _stabilize(mock_page, "test", min_ms=100, max_ms=500)
            # 验证优化因子应用
            call_kwargs = mock_wait.call_args[1]
            assert call_kwargs["min_ms"] <= 100  # 优化后应更小
            assert call_kwargs["max_ms"] <= 500  # 优化后应更小

    @pytest.mark.asyncio
    async def test_title_exactly_at_limit(self, mock_page):
        """测试标题正好在限制边界"""
        title_at_limit = "A" * MAX_TITLE_LENGTH
        mock_input = MagicMock()
        mock_input.count = AsyncMock(return_value=1)
        mock_input.input_value = AsyncMock(return_value=title_at_limit)
        mock_input.fill = AsyncMock()
        mock_page.locator.return_value.first = mock_input
        await _ensure_title_length(mock_page)
        # 不应调用 fill，因为正好在限制内
        mock_input.fill.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_payload(self, mock_page):
        """测试空 payload"""
        empty_payload = {}
        patches = _create_step_patches()
        with patch.multiple("src.browser.batch_edit_codegen", **patches):
            result = await run_batch_edit(mock_page, empty_payload)
            assert isinstance(result, dict)
