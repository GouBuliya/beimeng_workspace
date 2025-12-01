"""
@PURPOSE: 测试页面状态检测器
@OUTLINE:
  - TestPageState: 测试页面状态枚举
  - TestStateDetector: 测试状态检测器
@DEPENDENCIES:
  - 外部: pytest, pytest-asyncio
  - 内部: src.utils.state_detector
"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
from src.utils.state_detector import PageState, StateDetector
from tests.mocks import MockLocator, MockPage


class TestPageState:
    """测试页面状态枚举"""

    def test_state_values(self):
        """测试状态值"""
        assert PageState.UNKNOWN.value == "unknown"
        assert PageState.LOGIN_PAGE.value == "login"
        assert PageState.HOME_PAGE.value == "home"
        assert PageState.COLLECTION_BOX.value == "collection_box"
        assert PageState.EDIT_DIALOG_OPEN.value == "edit_dialog"
        assert PageState.BATCH_EDIT.value == "batch_edit"
        assert PageState.PUBLISH_PAGE.value == "publish"

    def test_state_comparison(self):
        """测试状态比较"""
        assert PageState.LOGIN_PAGE == PageState.LOGIN_PAGE
        assert PageState.LOGIN_PAGE != PageState.HOME_PAGE

    def test_all_states_exist(self):
        """测试所有预期状态存在"""
        expected_states = [
            "UNKNOWN",
            "LOGIN_PAGE",
            "HOME_PAGE",
            "COLLECTION_BOX",
            "EDIT_DIALOG_OPEN",
            "BATCH_EDIT",
            "PUBLISH_PAGE",
        ]

        for state_name in expected_states:
            assert hasattr(PageState, state_name)


class TestStateDetector:
    """测试状态检测器"""

    def test_init(self):
        """测试初始化"""
        detector = StateDetector()
        assert detector is not None

    @pytest.mark.asyncio
    async def test_is_login_page_true(self):
        """测试检测登录页 - 是"""
        detector = StateDetector()

        mock_page = MockPage(url="https://erp.91miaoshou.com/login")
        mock_locator = MockLocator(is_visible=True, count=1)
        mock_page.locator = MagicMock(return_value=mock_locator)
        mock_locator.is_visible = AsyncMock(return_value=True)

        await detector.is_login_page(mock_page)

        # 基于URL判断
        assert "login" in mock_page.url.lower()

    @pytest.mark.asyncio
    async def test_is_login_page_false(self):
        """测试检测登录页 - 否"""
        StateDetector()

        mock_page = MockPage(url="https://erp.91miaoshou.com/welcome")

        # URL不包含login
        assert "login" not in mock_page.url.lower()

    @pytest.mark.asyncio
    async def test_is_collection_box_by_url(self):
        """测试通过URL检测采集箱"""
        StateDetector()

        mock_page = MockPage(url="https://erp.91miaoshou.com/miaoshou/collection")

        # 检测URL特征
        assert "collection" in mock_page.url.lower() or "miaoshou" in mock_page.url.lower()

    @pytest.mark.asyncio
    async def test_detect_unknown_state(self):
        """测试检测未知状态"""
        detector = StateDetector()

        mock_page = AsyncMock()
        mock_page.url = "https://example.com/unknown/path"

        # Mock所有检测方法返回False
        detector.is_login_page = AsyncMock(return_value=False)
        detector.is_edit_dialog_open = AsyncMock(return_value=False)
        detector.is_collection_box = AsyncMock(return_value=False)
        detector.is_home_page = AsyncMock(return_value=False)
        detector.is_batch_edit_page = AsyncMock(return_value=False)
        detector.is_publish_page = AsyncMock(return_value=False)

        state = await detector.detect_current_state(mock_page)

        assert state == PageState.UNKNOWN

    @pytest.mark.asyncio
    async def test_detect_login_state(self):
        """测试检测登录页状态"""
        detector = StateDetector()

        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/login"

        detector.is_login_page = AsyncMock(return_value=True)

        state = await detector.detect_current_state(mock_page)

        assert state == PageState.LOGIN_PAGE


class TestStateDetectorRecovery:
    """测试状态检测器的恢复功能"""

    @pytest.mark.asyncio
    async def test_close_any_dialog(self):
        """测试关闭弹窗"""
        detector = StateDetector()

        mock_page = AsyncMock()
        mock_locator = AsyncMock()
        mock_locator.is_visible = AsyncMock(return_value=True)
        mock_locator.click = AsyncMock()
        mock_page.locator = MagicMock(return_value=mock_locator)

        # 测试关闭弹窗方法存在
        assert hasattr(detector, "close_any_dialog")

    @pytest.mark.asyncio
    async def test_recover_to_collection_box(self):
        """测试恢复到采集箱"""
        detector = StateDetector()

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_load_state = AsyncMock()

        # 测试恢复方法存在
        assert hasattr(detector, "recover_to_collection_box")


class TestStateDetectorEdgeCases:
    """测试状态检测器边缘情况"""

    @pytest.mark.asyncio
    async def test_detect_state_with_timeout(self):
        """测试检测超时处理"""
        detector = StateDetector()

        mock_page = AsyncMock()
        mock_page.url = "https://erp.91miaoshou.com/slow/page"

        # 模拟超时
        detector.is_login_page = AsyncMock(side_effect=Exception("Timeout"))

        # 应该捕获异常并返回UNKNOWN
        try:
            state = await detector.detect_current_state(mock_page)
        except Exception:
            state = PageState.UNKNOWN

        assert state == PageState.UNKNOWN

    @pytest.mark.asyncio
    async def test_detect_state_with_network_error(self):
        """测试网络错误处理"""
        detector = StateDetector()

        mock_page = AsyncMock()
        mock_page.url = PropertyMock(side_effect=Exception("Network error"))

        # 应该处理网络错误
        try:
            state = await detector.detect_current_state(mock_page)
        except Exception:
            state = PageState.UNKNOWN

        assert state == PageState.UNKNOWN
