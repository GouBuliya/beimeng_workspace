"""
@PURPOSE: 测试 utils/runtime_paths.py 路径解析工具
@OUTLINE:
  - class TestGetRuntimeBase: 测试运行时基础路径获取
  - class TestResolveRuntimePath: 测试路径解析
@DEPENDENCIES:
  - 外部: pytest
  - 内部: src.utils.runtime_paths
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest


class TestGetRuntimeBase:
    """测试 get_runtime_base 函数."""

    def test_normal_environment(self) -> None:
        """测试正常 Python 环境（非打包）."""
        from src.utils.runtime_paths import get_runtime_base

        # 清除缓存
        get_runtime_base.cache_clear()

        # 正常环境下 _MEIPASS 不存在
        base = get_runtime_base()
        assert isinstance(base, Path)
        assert base.exists()

    def test_frozen_environment(self) -> None:
        """测试 PyInstaller 打包环境."""
        from src.utils.runtime_paths import get_runtime_base

        # 清除缓存
        get_runtime_base.cache_clear()

        fake_meipass = "/tmp/fake_meipass"  # nosec B108 - 测试用临时路径
        with patch.object(sys, "_MEIPASS", fake_meipass, create=True):
            base = get_runtime_base()
            assert base == Path(fake_meipass)

        # 恢复缓存
        get_runtime_base.cache_clear()

    def test_caching(self) -> None:
        """测试结果缓存."""
        from src.utils.runtime_paths import get_runtime_base

        # 清除缓存
        get_runtime_base.cache_clear()

        # 第一次调用
        base1 = get_runtime_base()
        # 第二次调用应该返回缓存结果
        base2 = get_runtime_base()

        assert base1 == base2
        assert get_runtime_base.cache_info().hits >= 1


class TestResolveRuntimePath:
    """测试 resolve_runtime_path 函数."""

    def test_absolute_path(self) -> None:
        """测试绝对路径直接返回."""
        from src.utils.runtime_paths import resolve_runtime_path

        abs_path = Path("/tmp/test/file.txt")  # nosec B108 - 测试用临时路径
        result = resolve_runtime_path(abs_path)
        assert result == abs_path

    def test_absolute_path_string(self) -> None:
        """测试字符串绝对路径."""
        from src.utils.runtime_paths import resolve_runtime_path

        abs_path = "/tmp/test/file.txt"  # nosec B108 - 测试用临时路径
        result = resolve_runtime_path(abs_path)
        assert result == Path(abs_path)

    def test_relative_path_resolution(self) -> None:
        """测试相对路径解析."""
        from src.utils.runtime_paths import resolve_runtime_path

        # 使用一个已知存在的相对路径
        result = resolve_runtime_path("config")
        assert isinstance(result, Path)
        # 结果应该是绝对路径
        assert result.is_absolute()

    def test_nonexistent_path(self) -> None:
        """测试不存在的路径."""
        from src.utils.runtime_paths import resolve_runtime_path

        result = resolve_runtime_path("nonexistent/path/file.txt")
        assert isinstance(result, Path)
        assert result.is_absolute()
        # 即使不存在也应返回解析后的路径
        assert "nonexistent" in str(result)

    def test_user_data_override(self, tmp_path: Path) -> None:
        """测试用户数据目录优先级."""
        from src.utils import runtime_paths
        from src.utils.runtime_paths import resolve_runtime_path

        # 保存原始值
        original_user_data_root = runtime_paths.USER_DATA_ROOT

        try:
            # 创建临时用户数据目录
            user_data = tmp_path / "user_data"
            user_data.mkdir()
            test_file = user_data / "test_config.json"
            test_file.write_text("{}")

            # 覆盖 USER_DATA_ROOT
            runtime_paths.USER_DATA_ROOT = user_data

            result = resolve_runtime_path("test_config.json")
            # 应该找到用户数据目录中的文件
            assert result.exists()
            assert result == test_file.resolve()

        finally:
            # 恢复原始值
            runtime_paths.USER_DATA_ROOT = original_user_data_root

    def test_path_object_input(self) -> None:
        """测试 Path 对象输入."""
        from src.utils.runtime_paths import resolve_runtime_path

        path = Path("config")
        result = resolve_runtime_path(path)
        assert isinstance(result, Path)
        assert result.is_absolute()


class TestUserDataRoot:
    """测试 USER_DATA_ROOT 常量."""

    def test_user_data_root_location(self) -> None:
        """测试用户数据根目录位置."""
        from src.utils.runtime_paths import USER_DATA_ROOT

        assert isinstance(USER_DATA_ROOT, Path)
        # 应该在用户主目录下
        assert USER_DATA_ROOT.parent == Path.home()
        assert USER_DATA_ROOT.name == "TemuWebPanel"


class TestPathIntegration:
    """路径解析集成测试."""

    def test_config_path_resolution(self) -> None:
        """测试配置文件路径解析."""
        from src.utils.runtime_paths import resolve_runtime_path

        # 尝试解析已知的配置文件
        config_path = resolve_runtime_path("config/settings.yaml")
        assert isinstance(config_path, Path)
        assert config_path.is_absolute()

    def test_data_path_resolution(self) -> None:
        """测试数据目录路径解析."""
        from src.utils.runtime_paths import resolve_runtime_path

        data_path = resolve_runtime_path("data")
        assert isinstance(data_path, Path)
        assert data_path.is_absolute()

    def test_nested_path_resolution(self) -> None:
        """测试嵌套路径解析."""
        from src.utils.runtime_paths import resolve_runtime_path

        nested_path = resolve_runtime_path("config/browser_config.json")
        assert isinstance(nested_path, Path)
        assert "config" in str(nested_path)
        assert nested_path.name == "browser_config.json"
