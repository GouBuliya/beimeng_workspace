"""
@PURPOSE: debug_tools.py 单元测试
@OUTLINE:
  - TestCaptureDebugArtifacts: 调试资源保存测试
  - TestLogPayloadPreview: Rich 表格输出测试
  - TestMaybePauseForInspector: Playwright Inspector 条件触发测试
  - TestRunWithOptionalSyncer: 同步执行包装测试
@DEPENDENCIES:
  - 内部: browser.debug_tools
  - 外部: pytest, pytest-asyncio
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.browser.debug_tools import (
    capture_debug_artifacts,
    log_payload_preview,
    maybe_pause_for_inspector,
    run_with_optional_syncer,
)


# ============================================================
# capture_debug_artifacts 测试
# ============================================================
class TestCaptureDebugArtifacts:
    """调试资源保存测试"""

    @pytest.fixture
    def mock_page(self):
        """创建模拟 Page 对象"""
        page = MagicMock()
        page.screenshot = AsyncMock()
        page.content = AsyncMock(return_value="<html><body>Test</body></html>")
        return page

    @pytest.mark.asyncio
    async def test_creates_output_directory(self, mock_page, tmp_path):
        """测试自动创建输出目录"""
        output_dir = tmp_path / "debug" / "nested"
        assert not output_dir.exists()

        await capture_debug_artifacts(mock_page, step="test_step", output_dir=output_dir)

        assert output_dir.exists()

    @pytest.mark.asyncio
    async def test_saves_screenshot_and_html(self, mock_page, tmp_path):
        """测试保存截图和 HTML"""
        result = await capture_debug_artifacts(mock_page, step="test_step", output_dir=tmp_path)

        assert "screenshot" in result
        assert "html" in result
        mock_page.screenshot.assert_called_once()
        mock_page.content.assert_called_once()

    @pytest.mark.asyncio
    async def test_filename_contains_step_and_timestamp(self, mock_page, tmp_path):
        """测试文件名包含步骤名和时间戳"""
        result = await capture_debug_artifacts(mock_page, step="my_step", output_dir=tmp_path)

        assert "my_step" in result["screenshot"]
        assert "my_step" in result["html"]
        assert result["screenshot"].endswith(".png")
        assert result["html"].endswith(".html")

    @pytest.mark.asyncio
    async def test_sanitizes_step_name(self, mock_page, tmp_path):
        """测试步骤名特殊字符处理"""
        result = await capture_debug_artifacts(
            mock_page, step="step with spaces/slashes", output_dir=tmp_path
        )

        # 空格替换为下划线，斜杠替换为横杠
        assert "step_with_spaces-slashes" in result["screenshot"]

    @pytest.mark.asyncio
    async def test_writes_html_content(self, mock_page, tmp_path):
        """测试 HTML 内容写入"""
        expected_html = "<html><body>Test Content</body></html>"
        mock_page.content = AsyncMock(return_value=expected_html)

        result = await capture_debug_artifacts(mock_page, step="test", output_dir=tmp_path)

        html_path = Path(result["html"])
        assert html_path.exists()
        assert html_path.read_text(encoding="utf-8") == expected_html


# ============================================================
# log_payload_preview 测试
# ============================================================
class TestLogPayloadPreview:
    """Rich 表格输出测试"""

    def test_basic_payload(self):
        """测试基础 payload 输出"""
        payload = {"key1": "value1", "key2": 123}

        # 不应抛出异常
        log_payload_preview(payload)

    def test_nested_dict_payload(self):
        """测试嵌套字典 payload"""
        payload = {
            "simple": "value",
            "nested": {"inner": "data", "number": 42},
        }

        log_payload_preview(payload)

    def test_list_payload(self):
        """测试包含列表的 payload"""
        payload = {
            "items": ["a", "b", "c"],
            "objects": [{"id": 1}, {"id": 2}],
        }

        log_payload_preview(payload)

    def test_custom_title(self):
        """测试自定义标题"""
        payload = {"key": "value"}

        # 不应抛出异常
        log_payload_preview(payload, title="Custom Title")

    def test_empty_payload(self):
        """测试空 payload"""
        log_payload_preview({})


# ============================================================
# maybe_pause_for_inspector 测试
# ============================================================
class TestMaybePauseForInspector:
    """Playwright Inspector 条件触发测试"""

    @pytest.fixture
    def mock_page(self):
        """创建模拟 Page 对象"""
        page = MagicMock()
        page.pause = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_enabled_true_pauses(self, mock_page):
        """测试 enabled=True 时暂停"""
        await maybe_pause_for_inspector(mock_page, enabled=True)

        mock_page.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_enabled_false_does_not_pause(self, mock_page):
        """测试 enabled=False 时不暂停"""
        await maybe_pause_for_inspector(mock_page, enabled=False)

        mock_page.pause.assert_not_called()

    @pytest.mark.asyncio
    async def test_env_var_playwright_debug_1(self, mock_page):
        """测试环境变量 PLAYWRIGHT_DEBUG=1"""
        with patch.dict(os.environ, {"PLAYWRIGHT_DEBUG": "1"}):
            await maybe_pause_for_inspector(mock_page)

        mock_page.pause.assert_called_once()

    @pytest.mark.asyncio
    async def test_env_var_playwright_debug_0(self, mock_page):
        """测试环境变量 PLAYWRIGHT_DEBUG=0"""
        with patch.dict(os.environ, {"PLAYWRIGHT_DEBUG": "0"}):
            await maybe_pause_for_inspector(mock_page)

        mock_page.pause.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_env_var_does_not_pause(self, mock_page):
        """测试无环境变量时不暂停"""
        with patch.dict(os.environ, {}, clear=True):
            # 确保环境变量不存在
            os.environ.pop("PLAYWRIGHT_DEBUG", None)
            await maybe_pause_for_inspector(mock_page)

        mock_page.pause.assert_not_called()

    @pytest.mark.asyncio
    async def test_enabled_overrides_env_var(self, mock_page):
        """测试 enabled 参数优先于环境变量"""
        with patch.dict(os.environ, {"PLAYWRIGHT_DEBUG": "1"}):
            await maybe_pause_for_inspector(mock_page, enabled=False)

        mock_page.pause.assert_not_called()


# ============================================================
# run_with_optional_syncer 测试
# ============================================================
class TestRunWithOptionalSyncer:
    """同步执行包装测试

    注意: 这些测试不能使用 @pytest.mark.asyncio，因为 run_with_optional_syncer
    内部调用 asyncio.run()，而 asyncio.run() 不能在已有事件循环中调用。
    """

    def test_runs_async_function(self):
        """测试运行异步函数"""

        async def async_add(a, b):
            return a + b

        result = run_with_optional_syncer(async_add, 2, 3)

        assert result == 5

    def test_passes_kwargs(self):
        """测试传递关键字参数"""

        async def async_func(*, name, value):
            return f"{name}={value}"

        result = run_with_optional_syncer(async_func, name="test", value=42)

        assert result == "test=42"

    def test_handles_exception(self):
        """测试处理异步函数异常"""

        async def async_raise():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            run_with_optional_syncer(async_raise)

    def test_returns_correct_type(self):
        """测试返回正确的类型"""

        async def async_list():
            return [1, 2, 3]

        result = run_with_optional_syncer(async_list)

        assert result == [1, 2, 3]
        assert isinstance(result, list)


# ============================================================
# 边界情况测试
# ============================================================
class TestDebugToolsEdgeCases:
    """边界情况测试"""

    @pytest.mark.asyncio
    async def test_capture_with_unicode_step(self, tmp_path):
        """测试中文步骤名"""
        mock_page = MagicMock()
        mock_page.screenshot = AsyncMock()
        mock_page.content = AsyncMock(return_value="<html></html>")

        result = await capture_debug_artifacts(mock_page, step="测试步骤", output_dir=tmp_path)

        assert "测试步骤" in result["screenshot"]

    def test_log_payload_with_special_characters(self):
        """测试包含特殊字符的 payload"""
        payload = {
            "unicode": "中文测试",
            "emoji": "🎉",
            "special": "<>&\"'",
        }

        # 不应抛出异常
        log_payload_preview(payload)

    def test_log_payload_with_none_values(self):
        """测试包含 None 值的 payload"""
        payload = {
            "valid": "value",
            "null": None,
        }

        log_payload_preview(payload)
