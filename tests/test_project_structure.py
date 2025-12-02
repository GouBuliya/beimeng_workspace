"""
@PURPOSE: 项目结构测试,检查应用和包是否包含必需文件
@OUTLINE:
  - TestAppsStructure: 应用结构测试类
    - test_apps_have_required_files: 检查 apps/ 下应用是否包含必需文件
    - test_apps_have_ai_json: 检查应用是否有 .ai.json
    - test_apps_have_readme: 检查应用是否有 README.md
  - TestPackagesStructure: 包结构测试类
    - test_packages_have_required_files: 检查 packages/ 下包是否包含必需文件
  - TestMetadataProtocol: 元信息协议测试类(可选)
    - test_python_files_have_purpose: 检查文件是否有 @PURPOSE
    - test_python_files_have_outline: 检查文件是否有 @OUTLINE
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

from utils.project_scanner import ProjectScanner


@pytest.fixture(scope="module")
def scanner() -> ProjectScanner:
    """创建项目扫描器实例."""
    root_path = Path(__file__).resolve().parents[1]
    return ProjectScanner(root_path=root_path)


class TestAppsStructure:
    """应用结构测试."""

    def test_apps_have_required_files(self, scanner: ProjectScanner) -> None:
        """检查 apps/ 下的应用是否包含必需文件.

        必需文件:
        - .ai.json: AI 元数据文件
        - README.md: 应用文档
        - __init__.py: 包初始化文件
        """
        violations: list[str] = []

        for component in scanner.scan_apps():
            if component.missing_files:
                missing = ", ".join(component.missing_files)
                violations.append(f"apps/{component.name}: 缺少必需文件 [{missing}]")

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(f"发现 {len(violations)} 个应用缺少必需文件:\n{violation_msg}")

    def test_apps_have_ai_json(self, scanner: ProjectScanner) -> None:
        """检查 apps/ 下的应用是否都有 .ai.json 文件."""
        violations: list[str] = []

        for component in scanner.scan_apps():
            if not component.has_ai_json:
                violations.append(f"apps/{component.name}: 缺少 .ai.json 文件")

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(f"发现 {len(violations)} 个应用缺少 .ai.json:\n{violation_msg}")

    def test_apps_have_readme(self, scanner: ProjectScanner) -> None:
        """检查 apps/ 下的应用是否都有 README.md 文件."""
        violations: list[str] = []

        for component in scanner.scan_apps():
            if not component.has_readme:
                violations.append(f"apps/{component.name}: 缺少 README.md 文件")

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(f"发现 {len(violations)} 个应用缺少 README.md:\n{violation_msg}")


class TestPackagesStructure:
    """包结构测试."""

    def test_packages_have_required_files(self, scanner: ProjectScanner) -> None:
        """检查 packages/ 下的包是否包含必需文件.

        必需文件:
        - .ai.json: AI 元数据文件
        - README.md: 包文档
        - __init__.py: 包初始化文件
        """
        violations: list[str] = []

        for component in scanner.scan_packages():
            if component.missing_files:
                missing = ", ".join(component.missing_files)
                violations.append(f"packages/{component.name}: 缺少必需文件 [{missing}]")

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(f"发现 {len(violations)} 个包缺少必需文件:\n{violation_msg}")

    def test_packages_have_ai_json(self, scanner: ProjectScanner) -> None:
        """检查 packages/ 下的包是否都有 .ai.json 文件."""
        violations: list[str] = []

        for component in scanner.scan_packages():
            if not component.has_ai_json:
                violations.append(f"packages/{component.name}: 缺少 .ai.json 文件")

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(f"发现 {len(violations)} 个包缺少 .ai.json:\n{violation_msg}")

    def test_packages_have_readme(self, scanner: ProjectScanner) -> None:
        """检查 packages/ 下的包是否都有 README.md 文件."""
        violations: list[str] = []

        for component in scanner.scan_packages():
            if not component.has_readme:
                violations.append(f"packages/{component.name}: 缺少 README.md 文件")

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(f"发现 {len(violations)} 个包缺少 README.md:\n{violation_msg}")


@pytest.mark.metadata_check
class TestMetadataProtocol:
    """元信息协议测试.

    这些测试默认跳过,需要使用 --run-metadata-check 参数启用。
    检查 Python 文件是否包含 @PURPOSE 和 @OUTLINE 元信息注释。
    """

    def test_python_files_have_purpose(self, scanner: ProjectScanner) -> None:
        """检查 Python 文件是否包含 @PURPOSE 元信息.

        @PURPOSE 应该在文件顶部的 docstring 中,描述文件的核心作用。
        """
        violations: list[str] = []

        for file_info, missing_fields in scanner.scan_files_missing_metadata(
            search_paths=["apps", "packages"],
            required_fields=["PURPOSE"],
        ):
            violations.append(f"{file_info.relative_path}: 缺少 @PURPOSE 元信息")

        if violations:
            # 只显示前 20 个违规
            shown_violations = violations[:20]
            remaining = len(violations) - 20
            violation_msg = "\n".join(shown_violations)
            if remaining > 0:
                violation_msg += f"\n... 还有 {remaining} 个文件"
            pytest.fail(f"发现 {len(violations)} 个文件缺少 @PURPOSE:\n{violation_msg}")

    def test_python_files_have_outline(self, scanner: ProjectScanner) -> None:
        """检查 Python 文件是否包含 @OUTLINE 元信息.

        @OUTLINE 应该在文件顶部的 docstring 中,描述文件的结构大纲。
        """
        violations: list[str] = []

        for file_info, missing_fields in scanner.scan_files_missing_metadata(
            search_paths=["apps", "packages"],
            required_fields=["OUTLINE"],
        ):
            violations.append(f"{file_info.relative_path}: 缺少 @OUTLINE 元信息")

        if violations:
            # 只显示前 20 个违规
            shown_violations = violations[:20]
            remaining = len(violations) - 20
            violation_msg = "\n".join(shown_violations)
            if remaining > 0:
                violation_msg += f"\n... 还有 {remaining} 个文件"
            pytest.fail(f"发现 {len(violations)} 个文件缺少 @OUTLINE:\n{violation_msg}")

    def test_python_files_have_metadata(self, scanner: ProjectScanner) -> None:
        """检查 Python 文件是否包含完整的元信息(@PURPOSE 和 @OUTLINE).

        这是一个综合检查,确保文件同时包含 @PURPOSE 和 @OUTLINE。
        """
        violations: list[str] = []

        for file_info, missing_fields in scanner.scan_files_missing_metadata(
            search_paths=["apps", "packages"],
            required_fields=["PURPOSE", "OUTLINE"],
        ):
            missing = ", ".join(f"@{f}" for f in missing_fields)
            violations.append(f"{file_info.relative_path}: 缺少 {missing}")

        if violations:
            # 只显示前 20 个违规
            shown_violations = violations[:20]
            remaining = len(violations) - 20
            violation_msg = "\n".join(shown_violations)
            if remaining > 0:
                violation_msg += f"\n... 还有 {remaining} 个文件"
            pytest.fail(f"发现 {len(violations)} 个文件缺少元信息:\n{violation_msg}")


class TestComponentDiscovery:
    """组件发现测试."""

    def test_apps_discovered(self, scanner: ProjectScanner) -> None:
        """测试能够正确发现 apps/ 下的应用."""
        apps = list(scanner.scan_apps())
        # 项目中应该至少有一些应用
        assert len(apps) > 0, "未发现任何应用,请检查 apps/ 目录"

        # 打印发现的应用(用于调试)
        app_names = [app.name for app in apps]
        print(f"\n发现 {len(apps)} 个应用: {', '.join(app_names)}")

    def test_packages_discovered(self, scanner: ProjectScanner) -> None:
        """测试能够正确发现 packages/ 下的包."""
        packages = list(scanner.scan_packages())
        # 项目中应该至少有一些包
        assert len(packages) > 0, "未发现任何包,请检查 packages/ 目录"

        # 打印发现的包(用于调试)
        pkg_names = [pkg.name for pkg in packages]
        print(f"\n发现 {len(packages)} 个包: {', '.join(pkg_names)}")
