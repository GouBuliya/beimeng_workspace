"""
@PURPOSE: StateDetector 状态检测器完整测试
@OUTLINE:
  - TestPageStateEnum: PageState 枚举测试
  - TestStateDetectorInit: 初始化测试
  - TestIsLoginPage: 登录页检测测试
  - TestIsHomePage: 首页检测测试
  - TestIsCollectionBox: 采集箱检测测试
  - TestIsEditDialogOpen: 编辑弹窗检测测试
  - TestIsBatchEditPage: 批量编辑页检测测试
  - TestIsPublishPage: 发布页检测测试
  - TestDetectCurrentState: 综合状态检测测试
  - TestCloseAnyDialog: 关闭弹窗测试
  - TestRecoverToCollectionBox: 恢复采集箱测试
  - TestEnsureState: 状态确保测试
@DEPENDENCIES:
  - 内部: utils.state_detector
  - 外部: pytest, pytest-asyncio, unittest.mock
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.state_detector import PageState, StateDetector


# ============================================================
# PageState 枚举测试
# ============================================================
class TestPageStateEnum:
    """PageState 枚举测试"""

    def test_all_states_defined(self):
        """测试所有状态已定义"""
        assert PageState.UNKNOWN.value == "unknown"
        assert PageState.LOGIN_PAGE.value == "login"
        assert PageState.HOME_PAGE.value == "home"
        assert PageState.COLLECTION_BOX.value == "collection_box"
        assert PageState.EDIT_DIALOG_OPEN.value == "edit_dialog"
        assert PageState.BATCH_EDIT.value == "batch_edit"
        assert PageState.PUBLISH_PAGE.value == "publish"

    def test_state_count(self):
        """测试状态数量"""
        assert len(PageState) == 7

    def test_state_comparison(self):
        """测试状态比较"""
        assert PageState.UNKNOWN != PageState.LOGIN_PAGE
        assert PageState.COLLECTION_BOX == PageState.COLLECTION_BOX


# ============================================================
# StateDetector 初始化测试
# ============================================================
class TestStateDetectorInit:
    """StateDetector 初始化测试"""

    def test_init(self):
        """测试初始化"""
        detector = StateDetector()

        assert detector is not None


# ============================================================
# is_login_page 测试
# ============================================================
class TestIsLoginPage:
    """is_login_page 方法测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_login_url(self, detector):
        """测试登录 URL 检测"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/login"
        mock_page.locator.return_value.count = AsyncMock(return_value=0)

        result = await detector.is_login_page(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_sub_account_url(self, detector):
        """测试子账户 URL 检测"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/sub_account/users"
        mock_page.locator.return_value.count = AsyncMock(return_value=0)

        result = await detector.is_login_page(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_login_button_detected(self, detector):
        """测试登录按钮检测"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/other"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_page.locator.return_value = mock_locator

        result = await detector.is_login_page(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_not_login_page(self, detector):
        """测试非登录页"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/dashboard"
        mock_page.locator.return_value.count = AsyncMock(return_value=0)

        result = await detector.is_login_page(mock_page)

        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, detector):
        """测试异常返回 False"""
        mock_page = AsyncMock()
        mock_page.url = property(lambda self: (_ for _ in ()).throw(Exception("error")))

        result = await detector.is_login_page(mock_page)

        assert result is False


# ============================================================
# is_home_page 测试
# ============================================================
class TestIsHomePage:
    """is_home_page 方法测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_welcome_url(self, detector):
        """测试 welcome URL"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/welcome"

        result = await detector.is_home_page(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_root_url(self, detector):
        """测试根 URL"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/"

        result = await detector.is_home_page(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_not_home_page(self, detector):
        """测试非首页"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/dashboard"

        result = await detector.is_home_page(mock_page)

        assert result is False


# ============================================================
# is_collection_box 测试
# ============================================================
class TestIsCollectionBox:
    """is_collection_box 方法测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_collection_box_url_with_tab(self, detector):
        """测试采集箱 URL 且有 tab"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/common_collect_box/items"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=1)
        mock_page.locator.return_value = mock_locator

        result = await detector.is_collection_box(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_collection_box_url_no_tab(self, detector):
        """测试采集箱 URL 但无 tab"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/common_collect_box/items"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator

        result = await detector.is_collection_box(mock_page)

        assert result is False

    @pytest.mark.asyncio
    async def test_not_collection_box_url(self, detector):
        """测试非采集箱 URL"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/other"

        result = await detector.is_collection_box(mock_page)

        assert result is False


# ============================================================
# is_edit_dialog_open 测试
# ============================================================
class TestIsEditDialogOpen:
    """is_edit_dialog_open 方法测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_dialog_with_edit_indicator(self, detector):
        """测试有弹窗且有编辑指示器"""
        mock_page = AsyncMock()
        mock_page.locator = MagicMock()  # locator() 是同步方法

        # 使用 side_effect 模拟多次调用返回不同值
        call_count = [0]

        def make_locator(_selector):
            mock_locator = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:  # 弹窗检查
                mock_locator.count = AsyncMock(return_value=1)
            else:  # 编辑指示器检查
                mock_locator.count = AsyncMock(return_value=1)
            return mock_locator

        mock_page.locator.side_effect = make_locator

        result = await detector.is_edit_dialog_open(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_no_dialog(self, detector):
        """测试无弹窗"""
        mock_page = AsyncMock()
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator

        result = await detector.is_edit_dialog_open(mock_page)

        assert result is False

    @pytest.mark.asyncio
    async def test_dialog_without_edit_indicator(self, detector):
        """测试有弹窗但无编辑指示器"""
        mock_page = AsyncMock()
        mock_page.locator = MagicMock()  # locator() 是同步方法

        call_count = [0]

        def make_locator(_selector):
            mock_locator = MagicMock()
            call_count[0] += 1
            if call_count[0] == 1:  # 弹窗检查
                mock_locator.count = AsyncMock(return_value=1)
            else:  # 所有编辑指示器检查都返回 0
                mock_locator.count = AsyncMock(return_value=0)
            return mock_locator

        mock_page.locator.side_effect = make_locator

        result = await detector.is_edit_dialog_open(mock_page)

        assert result is False


# ============================================================
# is_batch_edit_page 测试
# ============================================================
class TestIsBatchEditPage:
    """is_batch_edit_page 方法测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_batch_edit_url(self, detector):
        """测试批量编辑 URL"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/batch_edit/products"
        mock_page.content = AsyncMock(return_value="<html></html>")

        result = await detector.is_batch_edit_page(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_content_contains_claim_text(self, detector):
        """测试页面内容包含认领文本"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/other"
        mock_page.content = AsyncMock(return_value="<html>认领到店铺</html>")

        result = await detector.is_batch_edit_page(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_not_batch_edit(self, detector):
        """测试非批量编辑页"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/other"
        mock_page.content = AsyncMock(return_value="<html>普通页面</html>")

        result = await detector.is_batch_edit_page(mock_page)

        assert result is False


# ============================================================
# is_publish_page 测试
# ============================================================
class TestIsPublishPage:
    """is_publish_page 方法测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_publish_url(self, detector):
        """测试发布 URL"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/publish/products"

        result = await detector.is_publish_page(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_chinese_publish_url(self, detector):
        """测试中文发布 URL"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/发布/products"

        result = await detector.is_publish_page(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_not_publish_page(self, detector):
        """测试非发布页"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/other"

        result = await detector.is_publish_page(mock_page)

        assert result is False


# ============================================================
# detect_current_state 综合测试
# ============================================================
class TestDetectCurrentState:
    """detect_current_state 综合测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_detect_login_page(self, detector):
        """测试检测登录页"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/login"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator

        result = await detector.detect_current_state(mock_page)

        assert result == PageState.LOGIN_PAGE

    @pytest.mark.asyncio
    async def test_detect_collection_box(self, detector):
        """测试检测采集箱"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/common_collect_box/items"
        mock_page.locator = MagicMock()  # locator() 是同步方法

        # 模拟多个 locator 调用的返回值
        call_count = [0]

        def make_locator(_selector):
            mock_locator = MagicMock()
            call_count[0] += 1
            # 登录按钮检查 - 返回 0
            if call_count[0] == 1:
                mock_locator.count = AsyncMock(return_value=0)
            # 弹窗检查 - 返回 0
            elif call_count[0] == 2:
                mock_locator.count = AsyncMock(return_value=0)
            # 采集箱 tab 检查 - 返回 1
            elif call_count[0] == 3:
                mock_locator.count = AsyncMock(return_value=1)
            else:
                mock_locator.count = AsyncMock(return_value=0)
            return mock_locator

        mock_page.locator.side_effect = make_locator

        result = await detector.detect_current_state(mock_page)

        assert result == PageState.COLLECTION_BOX

    @pytest.mark.asyncio
    async def test_detect_home_page(self, detector):
        """测试检测首页"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/welcome"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator

        result = await detector.detect_current_state(mock_page)

        assert result == PageState.HOME_PAGE

    @pytest.mark.asyncio
    async def test_detect_unknown(self, detector):
        """测试检测未知状态"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/unknown_page"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator
        mock_page.content.return_value = "<html></html>"

        result = await detector.detect_current_state(mock_page)

        assert result == PageState.UNKNOWN

    @pytest.mark.asyncio
    async def test_detect_exception_returns_unknown(self, detector):
        """测试异常返回 UNKNOWN"""
        mock_page = MagicMock()
        # 设置 url 属性抛出异常
        type(mock_page).url = property(
            lambda self: (_ for _ in ()).throw(Exception("error"))
        )

        result = await detector.detect_current_state(mock_page)

        assert result == PageState.UNKNOWN


# ============================================================
# close_any_dialog 测试
# ============================================================
class TestCloseAnyDialog:
    """close_any_dialog 方法测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_close_dialog_success(self, detector):
        """测试成功关闭弹窗"""
        mock_page = AsyncMock()
        mock_page.locator = MagicMock()  # locator() 是同步方法

        # 模拟找到关闭按钮并点击成功，最后验证弹窗已关闭
        call_count = [0]

        def make_locator(_selector):
            mock_locator = MagicMock()
            call_count[0] += 1
            # 前几次检查关闭按钮 - 返回有按钮
            if call_count[0] <= 9:
                mock_locator.count = AsyncMock(return_value=1)
            # 最后验证弹窗是否关闭 - 返回 0
            else:
                mock_locator.count = AsyncMock(return_value=0)
            mock_locator.nth.return_value = MagicMock(click=AsyncMock())
            return mock_locator

        mock_page.locator.side_effect = make_locator
        mock_page.keyboard = AsyncMock()

        result = await detector.close_any_dialog(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_close_dialog_still_open(self, detector):
        """测试弹窗仍然打开"""
        mock_page = AsyncMock()
        mock_page.locator = MagicMock()  # locator() 是同步方法

        def make_locator(_selector):
            mock_locator = MagicMock()
            mock_locator.count = AsyncMock(return_value=1)
            mock_locator.nth.return_value = MagicMock(click=AsyncMock())
            return mock_locator

        mock_page.locator.side_effect = make_locator
        mock_page.keyboard = AsyncMock()

        result = await detector.close_any_dialog(mock_page)

        assert result is False

    @pytest.mark.asyncio
    async def test_close_dialog_no_buttons(self, detector):
        """测试没有关闭按钮"""
        mock_page = AsyncMock()
        mock_page.locator = MagicMock()  # locator() 是同步方法

        def make_locator(_selector):
            mock_locator = MagicMock()
            mock_locator.count = AsyncMock(return_value=0)
            return mock_locator

        mock_page.locator.side_effect = make_locator
        mock_page.keyboard = AsyncMock()

        result = await detector.close_any_dialog(mock_page)

        # 无按钮但也无弹窗，应该返回 True
        assert result is True


# ============================================================
# recover_to_collection_box 测试
# ============================================================
class TestRecoverToCollectionBox:
    """recover_to_collection_box 方法测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_already_at_collection_box(self, detector):
        """测试已在采集箱"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/common_collect_box/items"
        mock_page.locator = MagicMock()  # locator() 是同步方法

        # 模拟已在采集箱
        call_count = [0]

        def make_locator(_selector):
            mock_locator = MagicMock()
            call_count[0] += 1
            # close_any_dialog 的关闭按钮检查 - 返回 0
            if call_count[0] <= 9:
                mock_locator.count = AsyncMock(return_value=0)
            # 弹窗验证检查 - 返回 0
            elif call_count[0] == 10:
                mock_locator.count = AsyncMock(return_value=0)
            # detect_current_state 中的 is_login_page 检查
            elif call_count[0] == 11:
                mock_locator.count = AsyncMock(return_value=0)
            # detect_current_state 中的 is_edit_dialog_open 检查
            elif call_count[0] == 12:
                mock_locator.count = AsyncMock(return_value=0)
            # detect_current_state 中的 is_collection_box 检查 - 返回 1
            elif call_count[0] == 13:
                mock_locator.count = AsyncMock(return_value=1)
            else:
                mock_locator.count = AsyncMock(return_value=0)
            return mock_locator

        mock_page.locator.side_effect = make_locator
        mock_page.keyboard = AsyncMock()

        result = await detector.recover_to_collection_box(mock_page)

        assert result is True

    @pytest.mark.asyncio
    async def test_navigate_to_collection_box(self, detector):
        """测试导航到采集箱"""
        mock_page = AsyncMock()
        mock_page.locator = MagicMock()  # locator() 是同步方法

        # 模拟初始在其他页面，导航后到达采集箱
        url_values = ["https://erp.91miaoshou.com/other"]
        type(mock_page).url = property(lambda self: url_values[0])

        async def mock_goto(url):
            url_values[0] = url

        mock_page.goto = mock_goto
        mock_page.keyboard = AsyncMock()

        # 模拟 locator 返回 - 基于 URL 判断是否在采集箱
        def make_locator(selector):
            mock_locator = MagicMock()
            # 如果 URL 包含 common_collect_box 且在检查 tab
            if "common_collect_box" in url_values[0] and "全部" in selector:
                mock_locator.count = AsyncMock(return_value=1)
            else:
                mock_locator.count = AsyncMock(return_value=0)
            return mock_locator

        mock_page.locator.side_effect = make_locator
        mock_page.content = AsyncMock(return_value="<html></html>")

        result = await detector.recover_to_collection_box(mock_page)

        assert result is True


# ============================================================
# ensure_state 测试
# ============================================================
class TestEnsureState:
    """ensure_state 方法测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_already_in_expected_state(self, detector):
        """测试已在期望状态"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/welcome"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator

        result = await detector.ensure_state(mock_page, PageState.HOME_PAGE)

        assert result is True

    @pytest.mark.asyncio
    async def test_not_in_expected_state_no_recovery(self, detector):
        """测试不在期望状态且不自动恢复"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/other"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator
        mock_page.content = AsyncMock(return_value="<html></html>")

        result = await detector.ensure_state(
            mock_page, PageState.HOME_PAGE, auto_recover=False
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_recover_to_home_page(self, detector):
        """测试恢复到首页"""
        mock_page = AsyncMock()
        mock_page.locator = MagicMock()  # locator() 是同步方法

        # 初始在其他页面
        url_values = ["https://erp.91miaoshou.com/other"]
        type(mock_page).url = property(lambda self: url_values[0])

        async def mock_goto(url):
            url_values[0] = url

        mock_page.goto = mock_goto
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator
        mock_page.content = AsyncMock(return_value="<html></html>")

        result = await detector.ensure_state(mock_page, PageState.HOME_PAGE)

        # 导航后应该在 welcome 页面
        assert "welcome" in url_values[0]

    @pytest.mark.asyncio
    async def test_unsupported_auto_recovery(self, detector):
        """测试不支持的自动恢复"""
        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/other"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator
        mock_page.content = AsyncMock(return_value="<html></html>")

        result = await detector.ensure_state(mock_page, PageState.BATCH_EDIT)

        assert result is False


# ============================================================
# 边界情况测试
# ============================================================
class TestEdgeCases:
    """边界情况测试"""

    @pytest.fixture
    def detector(self):
        """创建检测器实例"""
        return StateDetector()

    @pytest.mark.asyncio
    async def test_empty_url(self, detector):
        """测试空 URL"""
        mock_page = AsyncMock()
        mock_page.url = ""
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator
        mock_page.content = AsyncMock(return_value="<html></html>")

        result = await detector.detect_current_state(mock_page)

        assert result == PageState.UNKNOWN

    @pytest.mark.asyncio
    async def test_none_like_values(self, detector):
        """测试类似 None 的值"""
        mock_page = AsyncMock()
        mock_page.url = "about:blank"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator
        mock_page.content = AsyncMock(return_value="")

        result = await detector.detect_current_state(mock_page)

        assert result == PageState.UNKNOWN

    @pytest.mark.asyncio
    async def test_multiple_indicators_first_match(self, detector):
        """测试多个指示器时取第一个匹配"""
        mock_page = AsyncMock()
        # URL 同时包含 login 和 publish - 应该优先检测 login
        mock_page.url = "https://erp.91miaoshou.com/login/publish"
        mock_page.locator = MagicMock()  # locator() 是同步方法
        mock_locator = MagicMock()
        mock_locator.count = AsyncMock(return_value=0)
        mock_page.locator.return_value = mock_locator

        result = await detector.detect_current_state(mock_page)

        assert result == PageState.LOGIN_PAGE
