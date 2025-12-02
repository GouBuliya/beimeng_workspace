"""
@PURPOSE: 文件命名风格测试,检查 Python 文件和目录是否遵循命名规范
@OUTLINE:
  - TestPythonFileNaming: Python 文件命名测试类
    - test_python_files_use_snake_case: 检查所有 Python 文件是否使用 snake_case
    - test_files_in_directory: 分目录检查文件命名
  - TestDirectoryNaming: 目录命名测试类
    - test_directories_use_valid_names: 检查目录名是否有效
@DEPENDENCIES:
  - 内部: tests.utils.project_scanner
  - 外部: pytest
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# 确保 tests 目录在 Python 路径中
_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))

from utils.project_scanner import (
    ProjectScanner,
    is_valid_directory_name,
    is_valid_python_filename,
)


@pytest.fixture(scope="module")
def scanner() -> ProjectScanner:
    """创建项目扫描器实例."""
    # 获取项目根目录(tests 目录的父目录)
    root_path = Path(__file__).resolve().parents[1]
    return ProjectScanner(root_path=root_path)


class TestPythonFileNaming:
    """Python 文件命名测试."""

    def test_python_files_use_snake_case(self, scanner: ProjectScanner) -> None:
        """检查所有 Python 文件是否使用 snake_case 命名.

        遍历项目中的所有 Python 文件,检查文件名是否符合 snake_case 规范。
        允许的特殊文件名(如 __init__.py, conftest.py)不检查。
        """
        violations: list[str] = []

        for file_info in scanner.scan_python_files(["apps", "packages", "scripts", "tests"]):
            if not is_valid_python_filename(file_info.name):
                violations.append(
                    f"{file_info.relative_path}: 文件名 '{file_info.name}' 不符合 snake_case 规范"
                )

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(f"发现 {len(violations)} 个文件命名违规:\n{violation_msg}")

    @pytest.mark.parametrize("search_path", ["apps", "packages", "scripts"])
    def test_files_in_directory(self, scanner: ProjectScanner, search_path: str) -> None:
        """分目录检查 Python 文件命名.

        Args:
            scanner: 项目扫描器
            search_path: 要检查的目录路径
        """
        violations: list[str] = []

        for file_info in scanner.scan_python_files([search_path]):
            if not is_valid_python_filename(file_info.name):
                violations.append(
                    f"{file_info.relative_path}: 文件名 '{file_info.name}' 不符合 snake_case 规范"
                )

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(
                f"在 {search_path}/ 目录发现 {len(violations)} 个文件命名违规:\n{violation_msg}"
            )


class TestDirectoryNaming:
    """目录命名测试."""

    def test_directories_use_valid_names(self, scanner: ProjectScanner) -> None:
        """检查所有目录是否使用有效的命名(snake_case 或 kebab-case).

        遍历项目中的所有目录,检查目录名是否符合命名规范。
        隐藏目录(以 . 开头)和特殊目录(以 _ 开头)不检查。
        """
        violations: list[str] = []

        for dir_info in scanner.scan_directories(["apps", "packages", "scripts"]):
            if not is_valid_directory_name(dir_info.name):
                violations.append(
                    f"{dir_info.relative_path}: 目录名 '{dir_info.name}' "
                    "不符合 snake_case 或 kebab-case 规范"
                )

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(f"发现 {len(violations)} 个目录命名违规:\n{violation_msg}")

    @pytest.mark.parametrize("search_path", ["apps", "packages"])
    def test_directories_in_path(self, scanner: ProjectScanner, search_path: str) -> None:
        """分目录检查目录命名.

        Args:
            scanner: 项目扫描器
            search_path: 要检查的目录路径
        """
        violations: list[str] = []

        for dir_info in scanner.scan_directories([search_path]):
            if not is_valid_directory_name(dir_info.name):
                violations.append(
                    f"{dir_info.relative_path}: 目录名 '{dir_info.name}' "
                    "不符合 snake_case 或 kebab-case 规范"
                )

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(
                f"在 {search_path}/ 目录发现 {len(violations)} 个目录命名违规:\n{violation_msg}"
            )


class TestNamingHelpers:
    """命名检查辅助函数测试."""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("browser_manager.py", True),
            ("retry_handler.py", True),
            ("my_module.py", True),
            ("test_something.py", True),
            ("__init__.py", True),
            ("__main__.py", True),
            ("conftest.py", True),
            ("setup.py", True),
            ("MyClass.py", False),
            ("myClass.py", False),
            ("my-module.py", False),
            ("MyModule.py", False),
            ("README.md", True),  # 非 Python 文件不检查
        ],
    )
    def test_is_valid_python_filename(self, filename: str, expected: bool) -> None:
        """测试 is_valid_python_filename 函数."""
        assert is_valid_python_filename(filename) == expected

    @pytest.mark.parametrize(
        "dirname,expected",
        [
            ("browser", True),
            ("browser_manager", True),
            ("my_module", True),
            ("temu-auto-publish", True),  # kebab-case
            ("web-panel", True),  # kebab-case
            ("__pycache__", True),  # 特殊目录
            (".git", True),  # 隐藏目录
            ("_private", True),  # 特殊目录
            ("MyModule", False),
            ("myModule", False),
            ("My_Module", False),
            ("my_Module", False),
        ],
    )
    def test_is_valid_directory_name(self, dirname: str, expected: bool) -> None:
        """测试 is_valid_directory_name 函数."""
        assert is_valid_directory_name(dirname) == expected
