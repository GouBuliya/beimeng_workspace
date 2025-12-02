"""
@PURPOSE: Miaoshou 妙手模块测试
@OUTLINE:
  - TestMiaoshouControllerBase: 基础类测试(选择器加载、规范化)
  - TestMiaoshouController: 控制器测试
@DEPENDENCIES:
  - 内部: browser.miaoshou.base, browser.miaoshou.controller
  - 外部: pytest, pytest-asyncio
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================
# MiaoshouControllerBase 测试
# ============================================================
class TestMiaoshouControllerBase:
    """MiaoshouControllerBase 基础类测试"""

    @pytest.fixture
    def temp_selector_file(self, tmp_path):
        """创建临时选择器配置文件"""
        selector_config = {
            "collection_box": {
                "row_selector": ".row-item",
                "checkbox": ["input.checkbox", "input[type='checkbox']"],
                "claim_button": "button.claim",
            },
            "navigation": {
                "collection_box_url": "https://example.com/collection",
                "filter_owner": "select.owner",
            },
        }
        selector_file = tmp_path / "test_selectors.json"
        selector_file.write_text(json.dumps(selector_config))
        return str(selector_file)

    def test_init_default(self):
        """测试默认初始化"""
        from src.browser.miaoshou.base import MiaoshouControllerBase

        with patch.object(MiaoshouControllerBase, "_load_selectors", return_value={}):
            base = MiaoshouControllerBase()

            assert base.selectors == {}

    def test_init_with_selector_path(self, temp_selector_file):
        """测试指定选择器路径初始化"""
        from src.browser.miaoshou.base import MiaoshouControllerBase

        base = MiaoshouControllerBase(selector_path=temp_selector_file)

        assert "collection_box" in base.selectors
        assert "row_selector" in base.selectors["collection_box"]

    def test_load_selectors_success(self, temp_selector_file):
        """测试选择器加载成功"""
        from src.browser.miaoshou.base import MiaoshouControllerBase

        base = MiaoshouControllerBase(selector_path=temp_selector_file)

        assert base.selectors["collection_box"]["row_selector"] == ".row-item"

    def test_load_selectors_file_not_found(self, tmp_path):
        """测试选择器文件不存在"""
        from src.browser.miaoshou.base import MiaoshouControllerBase

        non_existent = str(tmp_path / "non_existent.json")
        base = MiaoshouControllerBase(selector_path=non_existent)

        # 应该返回空字典而不是抛出异常
        assert base.selectors == {}


# ============================================================
# _normalize_selector_value 测试
# ============================================================
class TestNormalizeSelectorValue:
    """测试选择器值规范化"""

    @pytest.fixture
    def base(self, tmp_path):
        """创建基础实例"""
        from src.browser.miaoshou.base import MiaoshouControllerBase

        selector_file = tmp_path / "test.json"
        selector_file.write_text("{}")
        return MiaoshouControllerBase(selector_path=str(selector_file))

    def test_normalize_none(self, base):
        """测试 None 值"""
        result = base._normalize_selector_value(None)

        assert result == []

    def test_normalize_string(self, base):
        """测试字符串值"""
        result = base._normalize_selector_value(".selector")

        assert result == [".selector"]

    def test_normalize_string_with_comma(self, base):
        """测试带逗号的字符串值"""
        result = base._normalize_selector_value(".sel1, .sel2, .sel3")

        assert result == [".sel1", ".sel2", ".sel3"]

    def test_normalize_string_with_spaces(self, base):
        """测试带空格的字符串值"""
        result = base._normalize_selector_value("  .selector  ")

        assert result == [".selector"]

    def test_normalize_empty_string(self, base):
        """测试空字符串"""
        result = base._normalize_selector_value("")

        assert result == []

    def test_normalize_list(self, base):
        """测试列表值"""
        result = base._normalize_selector_value([".sel1", ".sel2"])

        assert result == [".sel1", ".sel2"]

    def test_normalize_nested_list(self, base):
        """测试嵌套列表值"""
        result = base._normalize_selector_value([[".sel1", ".sel2"], ".sel3"])

        assert result == [".sel1", ".sel2", ".sel3"]

    def test_normalize_list_with_comma_strings(self, base):
        """测试列表中包含带逗号的字符串"""
        result = base._normalize_selector_value([".sel1, .sel2", ".sel3"])

        assert result == [".sel1", ".sel2", ".sel3"]

    def test_normalize_number(self, base):
        """测试数字值"""
        result = base._normalize_selector_value(123)

        assert result == ["123"]

    def test_normalize_mixed_list(self, base):
        """测试混合类型列表"""
        result = base._normalize_selector_value([".sel1", 123, None])

        assert ".sel1" in result
        assert "123" in result


# ============================================================
# _resolve_selectors 测试
# ============================================================
class TestResolveSelectors:
    """测试选择器解析"""

    @pytest.fixture
    def base(self, tmp_path):
        """创建基础实例"""
        from src.browser.miaoshou.base import MiaoshouControllerBase

        selector_file = tmp_path / "test.json"
        selector_file.write_text("{}")
        return MiaoshouControllerBase(selector_path=str(selector_file))

    def test_resolve_single_key(self, base):
        """测试解析单个键"""
        config = {"selector": ".my-selector"}

        result = base._resolve_selectors(config, ["selector"], [".default"])

        assert result == [".my-selector"]

    def test_resolve_multiple_keys(self, base):
        """测试解析多个键"""
        config = {"primary": ".primary", "secondary": ".secondary"}

        result = base._resolve_selectors(config, ["primary", "secondary"], [".default"])

        assert ".primary" in result
        assert ".secondary" in result

    def test_resolve_missing_key_uses_default(self, base):
        """测试缺失键使用默认值"""
        config = {"other": ".other"}

        result = base._resolve_selectors(config, ["missing"], [".default"])

        assert result == [".default"]

    def test_resolve_empty_config_uses_default(self, base):
        """测试空配置使用默认值"""
        config = {}

        result = base._resolve_selectors(config, ["selector"], [".default"])

        assert result == [".default"]

    def test_resolve_deduplicates(self, base):
        """测试去重"""
        config = {"a": ".same", "b": ".same"}

        result = base._resolve_selectors(config, ["a", "b"], [".default"])

        assert result == [".same"]

    def test_resolve_preserves_order(self, base):
        """测试保持顺序"""
        config = {"a": ".first", "b": ".second", "c": ".third"}

        result = base._resolve_selectors(config, ["a", "b", "c"], [".default"])

        assert result == [".first", ".second", ".third"]

    def test_resolve_filters_empty(self, base):
        """测试过滤空值"""
        config = {"a": "", "b": ".valid"}

        result = base._resolve_selectors(config, ["a", "b"], [".default"])

        assert result == [".valid"]

    def test_resolve_default_deduplicates(self, base):
        """测试默认值去重"""
        config = {}

        result = base._resolve_selectors(config, ["missing"], [".default", ".default", ".other"])

        assert result == [".default", ".other"]

    def test_resolve_default_strips_whitespace(self, base):
        """测试默认值去除空格"""
        config = {}

        result = base._resolve_selectors(config, ["missing"], ["  .default  ", "  .other  "])

        assert result == [".default", ".other"]


# ============================================================
# MiaoshouController 测试
# ============================================================
class TestMiaoshouController:
    """MiaoshouController 控制器测试"""

    @pytest.fixture
    def temp_selector_file(self, tmp_path):
        """创建临时选择器配置文件"""
        selector_config = {
            "collection_box": {
                "row_selector": ".row-item",
                "checkbox": "input.checkbox",
                "claim_button": "button.claim",
            },
            "claim": {
                "claim_button": "button.claim-action",
                "confirm_button": "button.confirm",
            },
        }
        selector_file = tmp_path / "test_selectors.json"
        selector_file.write_text(json.dumps(selector_config))
        return str(selector_file)

    @pytest.fixture
    def controller(self, temp_selector_file):
        """创建控制器实例"""
        from src.browser.miaoshou.controller import MiaoshouController

        return MiaoshouController(selector_path=temp_selector_file)

    def test_controller_init(self, controller):
        """测试控制器初始化"""
        assert controller.selectors is not None
        assert "collection_box" in controller.selectors

    def test_controller_inherits_base(self, controller):
        """测试控制器继承基础类"""
        assert hasattr(controller, "_normalize_selector_value")
        assert hasattr(controller, "_resolve_selectors")
        assert hasattr(controller, "_load_selectors")


# ============================================================
# MiaoshouClaimMixin 测试 (使用 Mock)
# ============================================================
class TestMiaoshouClaimMixin:
    """MiaoshouClaimMixin 认领功能测试"""

    @pytest.fixture
    def mock_page(self):
        """创建 Mock 页面"""
        page = AsyncMock()
        page.url = "https://example.com/collection"
        page.goto = AsyncMock()
        page.reload = AsyncMock()
        page.wait_for_load_state = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.evaluate = AsyncMock(return_value=[])

        mock_locator = AsyncMock()
        mock_locator.count = AsyncMock(return_value=5)
        mock_locator.nth = MagicMock(return_value=mock_locator)
        # first 属性也需要返回一个 AsyncMock 对象
        mock_first = AsyncMock()
        mock_first.wait_for = AsyncMock()
        mock_locator.first = mock_first
        mock_locator.is_visible = AsyncMock(return_value=True)
        mock_locator.click = AsyncMock()
        mock_locator.wait_for = AsyncMock()
        mock_locator.locator = MagicMock(return_value=mock_locator)

        page.locator = MagicMock(return_value=mock_locator)
        page.get_by_text = MagicMock(return_value=mock_locator)
        page.get_by_role = MagicMock(return_value=mock_locator)

        return page

    @pytest.fixture
    def controller(self, tmp_path):
        """创建控制器实例"""
        from src.browser.miaoshou.controller import MiaoshouController

        selector_config = {
            "collection_box": {
                "row_selector": ".row-item",
                "checkbox": "input.checkbox",
            },
            "claim": {
                "button": "button.claim",
            },
            "navigation": {
                "collection_box_url": "https://example.com/collection",
            },
        }
        selector_file = tmp_path / "selectors.json"
        selector_file.write_text(json.dumps(selector_config))

        return MiaoshouController(selector_path=str(selector_file))

    @pytest.mark.asyncio
    async def test_wait_for_rows_success(self, controller, mock_page):
        """测试等待行加载成功"""
        mock_locator = mock_page.locator.return_value
        mock_locator.count = AsyncMock(return_value=10)

        result = await controller._wait_for_rows(mock_page, timeout=1000)

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_rows_timeout(self, controller, mock_page):
        """测试等待行加载超时"""
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError

        mock_locator = mock_page.locator.return_value
        mock_locator.first.wait_for = AsyncMock(side_effect=PlaywrightTimeoutError("Timeout"))

        result = await controller._wait_for_rows(mock_page, timeout=100)

        assert result is False


# ============================================================
# 选择器常量测试
# ============================================================
class TestClaimSelectors:
    """测试认领相关选择器常量"""

    def test_row_selector_defined(self):
        """测试行选择器已定义"""
        from src.browser.miaoshou.claim import MiaoshouClaimMixin

        assert hasattr(MiaoshouClaimMixin, "_ROW_SELECTOR")

    def test_checkbox_selectors_defined(self):
        """测试复选框选择器已定义"""
        from src.browser.miaoshou.claim import MiaoshouClaimMixin

        assert hasattr(MiaoshouClaimMixin, "_CHECKBOX_CANDIDATE_SELECTORS")

    def test_claim_button_selectors_defined(self):
        """测试认领按钮选择器已定义"""
        from src.browser.miaoshou.claim import MiaoshouClaimMixin

        assert hasattr(MiaoshouClaimMixin, "_CLAIM_PRIORITY_SELECTORS")
        assert hasattr(MiaoshouClaimMixin, "_CLAIM_FALLBACK_SELECTORS")


# ============================================================
# 边界情况测试
# ============================================================
class TestEdgeCases:
    """边界情况测试"""

    @pytest.fixture
    def base(self, tmp_path):
        """创建基础实例"""
        from src.browser.miaoshou.base import MiaoshouControllerBase

        selector_file = tmp_path / "test.json"
        selector_file.write_text("{}")
        return MiaoshouControllerBase(selector_path=str(selector_file))

    def test_normalize_empty_list(self, base):
        """测试空列表"""
        result = base._normalize_selector_value([])

        assert result == []

    def test_normalize_list_with_none(self, base):
        """测试包含 None 的列表"""
        result = base._normalize_selector_value([None, ".valid", None])

        assert result == [".valid"]

    def test_normalize_whitespace_only(self, base):
        """测试仅包含空格的字符串"""
        result = base._normalize_selector_value("   ")

        assert result == []

    def test_resolve_all_keys_missing(self, base):
        """测试所有键都不存在"""
        config = {"x": ".x", "y": ".y"}

        result = base._resolve_selectors(config, ["a", "b", "c"], [".default"])

        assert result == [".default"]

    def test_resolve_empty_default(self, base):
        """测试空默认值"""
        config = {}

        result = base._resolve_selectors(config, ["missing"], [])

        assert result == []

    def test_resolve_config_with_none_value(self, base):
        """测试配置值为 None"""
        config = {"selector": None}

        result = base._resolve_selectors(config, ["selector"], [".default"])

        assert result == [".default"]


# ============================================================
# 性能相关测试
# ============================================================
class TestPerformance:
    """性能相关测试"""

    @pytest.fixture
    def base(self, tmp_path):
        """创建基础实例"""
        from src.browser.miaoshou.base import MiaoshouControllerBase

        selector_file = tmp_path / "test.json"
        selector_file.write_text("{}")
        return MiaoshouControllerBase(selector_path=str(selector_file))

    def test_normalize_large_list(self, base):
        """测试大列表规范化"""
        large_list = [f".selector-{i}" for i in range(1000)]

        result = base._normalize_selector_value(large_list)

        assert len(result) == 1000

    def test_resolve_many_keys(self, base):
        """测试多键解析"""
        config = {f"key-{i}": f".selector-{i}" for i in range(100)}
        keys = [f"key-{i}" for i in range(100)]

        result = base._resolve_selectors(config, keys, [".default"])

        assert len(result) == 100

    def test_normalize_deeply_nested(self, base):
        """测试深度嵌套列表"""
        nested = [[[[".deep"]]], ".shallow"]

        result = base._normalize_selector_value(nested)

        assert ".deep" in result
        assert ".shallow" in result
