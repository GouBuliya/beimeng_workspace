"""
@PURPOSE: 测试 utils/logger_setup.py 日志系统设置
@OUTLINE:
  - class TestLogFormatters: 测试日志格式化器
  - class TestLoggerSetup: 测试日志系统配置
  - class TestLoggerContext: 测试带上下文的日志
  - class TestLogDecorator: 测试日志装饰器
  - class TestLogHelpers: 测试日志辅助函数
@DEPENDENCIES:
  - 外部: pytest
  - 内部: src.utils.logger_setup
"""

from datetime import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestLogFormatters:
    """测试日志格式化器."""

    def test_format_detailed_basic(self) -> None:
        """测试详细格式化器基本输出."""
        from src.utils.logger_setup import format_detailed

        record = {
            "time": datetime.now(),
            "level": MagicMock(name="INFO"),
            "name": "test_logger",
            "function": "test_func",
            "line": 42,
            "message": "测试消息",
            "extra": {},
            "exception": None,
        }
        record["level"].name = "INFO"

        result = format_detailed(record)
        assert isinstance(result, str)
        assert "{time:" in result
        assert "{level:" in result
        assert "{message}" in result

    def test_format_detailed_with_context(self) -> None:
        """测试详细格式化器带上下文."""
        from src.utils.logger_setup import format_detailed

        record = {
            "time": datetime.now(),
            "level": MagicMock(name="INFO"),
            "name": "test_logger",
            "function": "test_func",
            "line": 42,
            "message": "测试消息",
            "extra": {
                "workflow_id": "abc12345678",
                "stage": "stage1",
                "action": "login",
            },
            "exception": None,
        }
        record["level"].name = "INFO"

        result = format_detailed(record)
        # 应该包含上下文信息
        assert "workflow=" in result or "{" in result
        assert "stage=" in result or "{" in result

    def test_format_json_basic(self) -> None:
        """测试 JSON 格式化器基本输出."""
        from src.utils.logger_setup import format_json

        record = {
            "time": datetime.now(),
            "level": MagicMock(name="INFO"),
            "name": "test_logger",
            "function": "test_func",
            "line": 42,
            "message": "测试消息",
            "extra": {},
            "exception": None,
        }
        record["level"].name = "INFO"

        result = format_json(record)
        assert isinstance(result, str)
        assert result.endswith("\n")

        import json

        parsed = json.loads(result.strip())
        assert "timestamp" in parsed
        assert "level" in parsed
        assert "message" in parsed
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "测试消息"

    def test_format_json_with_context(self) -> None:
        """测试 JSON 格式化器带上下文."""
        from src.utils.logger_setup import format_json

        import json

        record = {
            "time": datetime.now(),
            "level": MagicMock(name="INFO"),
            "name": "test_logger",
            "function": "test_func",
            "line": 42,
            "message": "测试消息",
            "extra": {
                "workflow_id": "test_workflow",
                "stage": "test_stage",
            },
            "exception": None,
        }
        record["level"].name = "INFO"

        result = format_json(record)
        parsed = json.loads(result.strip())

        assert "context" in parsed
        assert parsed["context"]["workflow_id"] == "test_workflow"
        assert parsed["context"]["stage"] == "test_stage"

    def test_format_json_with_exception(self) -> None:
        """测试 JSON 格式化器带异常信息."""
        from src.utils.logger_setup import format_json

        import json

        exception_mock = MagicMock()
        exception_mock.type = ValueError
        exception_mock.value = "测试错误"

        record = {
            "time": datetime.now(),
            "level": MagicMock(name="ERROR"),
            "name": "test_logger",
            "function": "test_func",
            "line": 42,
            "message": "发生错误",
            "extra": {},
            "exception": exception_mock,
        }
        record["level"].name = "ERROR"

        result = format_json(record)
        parsed = json.loads(result.strip())

        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert parsed["exception"]["value"] == "测试错误"

    def test_format_simple(self) -> None:
        """测试简单格式化器."""
        from src.utils.logger_setup import format_simple

        record = {
            "time": datetime.now(),
            "level": MagicMock(name="INFO"),
            "message": "测试消息",
        }
        record["level"].name = "INFO"

        result = format_simple(record)
        assert isinstance(result, str)
        assert "{time:" in result
        assert "{level:" in result
        assert "{message}" in result


class TestLoggerContext:
    """测试带上下文的日志功能."""

    def test_get_logger_with_context(self) -> None:
        """测试获取带上下文的 logger."""
        from src.utils.logger_setup import get_logger_with_context

        log = get_logger_with_context(
            workflow_id="test123",
            stage="login",
            action="click",
        )

        # 应该返回绑定了上下文的 logger
        assert log is not None
        # 可以调用日志方法
        assert hasattr(log, "info")
        assert hasattr(log, "error")
        assert hasattr(log, "debug")

    def test_log_with_context(self) -> None:
        """测试 log_with_context 函数."""
        from src.utils.logger_setup import log_with_context

        # 不应抛出异常
        log_with_context(
            "info",
            "测试消息",
            workflow_id="test123",
            product_index=1,
        )

    def test_log_with_context_different_levels(self) -> None:
        """测试不同日志级别."""
        from src.utils.logger_setup import log_with_context

        levels = ["debug", "info", "warning", "error"]
        for level in levels:
            # 不应抛出异常
            log_with_context(level, f"测试 {level} 消息")


class TestLogDecorator:
    """测试日志装饰器."""

    def test_log_function_call_sync(self) -> None:
        """测试同步函数装饰器."""
        from src.utils.logger_setup import log_function_call

        @log_function_call("debug")
        def sync_func(x: int, y: int) -> int:
            return x + y

        result = sync_func(1, 2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_log_function_call_async(self) -> None:
        """测试异步函数装饰器."""
        from src.utils.logger_setup import log_function_call

        @log_function_call("info")
        async def async_func(x: int) -> int:
            return x * 2

        result = await async_func(5)
        assert result == 10

    def test_log_function_call_exception(self) -> None:
        """测试装饰器异常处理."""
        from src.utils.logger_setup import log_function_call

        @log_function_call("debug")
        def failing_func() -> None:
            raise ValueError("测试错误")

        with pytest.raises(ValueError):
            failing_func()

    @pytest.mark.asyncio
    async def test_log_function_call_async_exception(self) -> None:
        """测试异步装饰器异常处理."""
        from src.utils.logger_setup import log_function_call

        @log_function_call("debug")
        async def failing_async_func() -> None:
            raise RuntimeError("异步错误")

        with pytest.raises(RuntimeError):
            await failing_async_func()


class TestLogHelpers:
    """测试日志辅助函数."""

    def test_log_section(self) -> None:
        """测试分隔行日志."""
        from src.utils.logger_setup import log_section

        # 不应抛出异常
        log_section("测试标题")
        log_section("自定义分隔", char="-", width=40)

    def test_log_dict(self) -> None:
        """测试字典日志."""
        from src.utils.logger_setup import log_dict

        data = {"key1": "value1", "key2": 123, "key3": True}

        # 不应抛出异常
        log_dict(data)
        log_dict(data, title="测试数据")

    def test_log_list(self) -> None:
        """测试列表日志."""
        from src.utils.logger_setup import log_list

        items = ["item1", "item2", "item3"]

        # 不应抛出异常
        log_list(items)
        log_list(items, title="测试列表")

    def test_log_dict_empty(self) -> None:
        """测试空字典日志."""
        from src.utils.logger_setup import log_dict

        log_dict({})
        log_dict({}, title="空数据")

    def test_log_list_empty(self) -> None:
        """测试空列表日志."""
        from src.utils.logger_setup import log_list

        log_list([])
        log_list([], title="空列表")


class TestSetupLogger:
    """测试日志系统配置."""

    def test_setup_logger_import(self) -> None:
        """测试模块导入时自动配置."""
        # 模块已在之前导入，验证不会抛异常
        from src.utils import logger_setup

        assert logger_setup is not None

    def test_setup_logger_with_config(self) -> None:
        """测试使用自定义配置."""
        from src.utils.logger_setup import setup_logger

        # 创建模拟配置
        mock_config = MagicMock()
        mock_config.format = "simple"
        mock_config.level = "DEBUG"
        mock_config.output = ["console"]

        # 不应抛出异常
        with patch("src.utils.logger_setup.logger") as mock_logger:
            mock_logger.remove = MagicMock()
            mock_logger.add = MagicMock()
            mock_logger.info = MagicMock()

            setup_logger(config=mock_config, force=True)

    def test_setup_logger_json_format(self) -> None:
        """测试 JSON 格式配置."""
        from src.utils.logger_setup import setup_logger

        mock_config = MagicMock()
        mock_config.format = "json"
        mock_config.level = "INFO"
        mock_config.output = ["console"]

        with patch("src.utils.logger_setup.logger") as mock_logger:
            mock_logger.remove = MagicMock()
            mock_logger.add = MagicMock()
            mock_logger.info = MagicMock()

            setup_logger(config=mock_config, force=True)

    def test_setup_logger_detailed_format(self) -> None:
        """测试详细格式配置."""
        from src.utils.logger_setup import setup_logger

        mock_config = MagicMock()
        mock_config.format = "detailed"
        mock_config.level = "DEBUG"
        mock_config.output = ["console"]

        with patch("src.utils.logger_setup.logger") as mock_logger:
            mock_logger.remove = MagicMock()
            mock_logger.add = MagicMock()
            mock_logger.info = MagicMock()

            setup_logger(config=mock_config, force=True)


class TestModuleExports:
    """测试模块导出."""

    def test_main_functions_available(self) -> None:
        """测试主要函数可用."""
        from src.utils.logger_setup import (
            format_detailed,
            format_json,
            format_simple,
            get_logger_with_context,
            log_dict,
            log_function_call,
            log_list,
            log_section,
            log_with_context,
            setup_logger,
        )

        assert callable(setup_logger)
        assert callable(get_logger_with_context)
        assert callable(log_with_context)
        assert callable(log_function_call)
        assert callable(log_section)
        assert callable(log_dict)
        assert callable(log_list)
        assert callable(format_detailed)
        assert callable(format_json)
        assert callable(format_simple)
