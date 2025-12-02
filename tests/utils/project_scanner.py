"""
@PURPOSE: 项目文件扫描器,用于扫描项目结构和检查命名规范
@OUTLINE:
  - ScanConfig: 扫描配置数据类
  - FileInfo: 文件信息数据类
  - DirectoryInfo: 目录信息数据类
  - ComponentInfo: 组件(应用/包)信息数据类
  - ProjectScanner: 项目扫描器类
  - is_snake_case(): 检查是否为 snake_case
  - is_valid_python_filename(): 检查 Python 文件名是否有效
  - is_valid_directory_name(): 检查目录名是否有效
@DEPENDENCIES:
  - 外部: pathlib, dataclasses, re
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

# 命名模式正则表达式
SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
KEBAB_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
PYTHON_FILE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.py$")

# 允许的特殊文件名(不需要遵循 snake_case)
ALLOWED_SPECIAL_FILES: set[str] = {
    "__init__.py",
    "__main__.py",
    "conftest.py",
    "setup.py",
    "pyproject.toml",
    "Makefile",
    "Dockerfile",
    "README.md",
    ".ai.json",
    ".env",
    ".env.example",
    ".gitignore",
    ".pre-commit-config.yaml",
    "mkdocs.yml",
    "pytest.ini",
    "CLAUDE.md",
}

# 默认排除的目录
DEFAULT_EXCLUDED_DIRS: set[str] = {
    ".venv",
    "venv",
    "__pycache__",
    ".git",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "node_modules",
    "build",
    "dist",
    "htmlcov",
    ".cursor",
    ".claude",
    ".air",
    "data",
    ".idea",
    ".vscode",
    "site-packages",
    "egg-info",
    "docs",  # 文档目录通常有大写名称
}

# 排除的应用目录(部署包、服务器镜像等)
EXCLUDED_APP_DIRS: set[str] = {
    "temu-auto-publish-server",  # Docker 部署包,不是标准 Python 应用
}

# 组件必需文件
REQUIRED_APP_FILES: list[str] = [".ai.json", "README.md", "__init__.py"]
REQUIRED_PACKAGE_FILES: list[str] = [".ai.json", "README.md", "__init__.py"]


@dataclass
class ScanConfig:
    """扫描配置."""

    root_path: Path
    exclude_dirs: set[str] = field(default_factory=lambda: DEFAULT_EXCLUDED_DIRS.copy())
    exclude_files: set[str] = field(default_factory=lambda: ALLOWED_SPECIAL_FILES.copy())


@dataclass
class FileInfo:
    """文件信息."""

    path: Path
    relative_path: Path
    name: str
    extension: str

    @property
    def stem(self) -> str:
        """文件名(不含扩展名)."""
        return self.path.stem


@dataclass
class DirectoryInfo:
    """目录信息."""

    path: Path
    relative_path: Path
    name: str
    depth: int


@dataclass
class ComponentInfo:
    """组件(应用/包)信息."""

    path: Path
    name: str
    has_ai_json: bool
    has_readme: bool
    has_init: bool
    missing_files: list[str] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        """是否包含所有必需文件."""
        return len(self.missing_files) == 0


def is_snake_case(name: str) -> bool:
    """检查字符串是否为 snake_case 格式.

    Args:
        name: 要检查的字符串

    Returns:
        True 如果是 snake_case,否则 False
    """
    if not name:
        return False
    return bool(SNAKE_CASE_PATTERN.match(name))


def is_kebab_case(name: str) -> bool:
    """检查字符串是否为 kebab-case 格式.

    Args:
        name: 要检查的字符串

    Returns:
        True 如果是 kebab-case,否则 False
    """
    if not name:
        return False
    return bool(KEBAB_CASE_PATTERN.match(name))


def is_valid_python_filename(filename: str) -> bool:
    """检查 Python 文件名是否有效.

    有效的文件名:
    - snake_case.py 格式
    - 或者是允许的特殊文件名

    Args:
        filename: 文件名(包含扩展名)

    Returns:
        True 如果文件名有效,否则 False
    """
    if filename in ALLOWED_SPECIAL_FILES:
        return True
    if not filename.endswith(".py"):
        return True  # 非 Python 文件不检查
    return bool(PYTHON_FILE_PATTERN.match(filename))


def is_valid_directory_name(dirname: str) -> bool:
    """检查目录名是否有效.

    有效的目录名:
    - snake_case 格式
    - 或 kebab-case 格式
    - 或以 . 开头的隐藏目录
    - 或以 _ 开头的特殊目录
    - 或以 .air 结尾的 AirTest 脚本目录

    Args:
        dirname: 目录名

    Returns:
        True 如果目录名有效,否则 False
    """
    if not dirname:
        return False
    # 隐藏目录和特殊目录
    if dirname.startswith(".") or dirname.startswith("_"):
        return True
    # AirTest 脚本目录
    if dirname.endswith(".air"):
        # 检查去掉 .air 后是否为有效名称
        base_name = dirname[:-4]
        return is_snake_case(base_name) or is_kebab_case(base_name)
    return is_snake_case(dirname) or is_kebab_case(dirname)


class ProjectScanner:
    """项目扫描器,用于扫描项目文件和目录结构."""

    def __init__(self, root_path: Path | str | None = None, config: ScanConfig | None = None):
        """初始化扫描器.

        Args:
            root_path: 项目根目录,默认为当前工作目录
            config: 扫描配置,如果未提供则使用默认配置
        """
        if root_path is None:
            root_path = Path.cwd()
        elif isinstance(root_path, str):
            root_path = Path(root_path)

        self.root_path = root_path.resolve()

        if config is None:
            self.config = ScanConfig(root_path=self.root_path)
        else:
            self.config = config
            self.config.root_path = self.root_path

    def _should_skip_dir(self, dir_path: Path) -> bool:
        """检查是否应该跳过目录.

        Args:
            dir_path: 目录路径

        Returns:
            True 如果应该跳过,否则 False
        """
        return dir_path.name in self.config.exclude_dirs

    def scan_python_files(self, search_paths: list[str] | None = None) -> Iterator[FileInfo]:
        """扫描 Python 文件.

        Args:
            search_paths: 要扫描的相对路径列表,默认扫描整个项目

        Yields:
            FileInfo 对象
        """
        if search_paths is None:
            search_paths = ["."]

        for search_path in search_paths:
            base_path = self.root_path / search_path
            if not base_path.exists():
                continue

            for py_file in base_path.rglob("*.py"):
                # 检查是否在排除目录中
                skip = False
                for parent in py_file.parents:
                    if parent.name in self.config.exclude_dirs:
                        skip = True
                        break
                if skip:
                    continue

                yield FileInfo(
                    path=py_file,
                    relative_path=py_file.relative_to(self.root_path),
                    name=py_file.name,
                    extension=py_file.suffix,
                )

    def scan_directories(
        self, search_paths: list[str] | None = None, max_depth: int = 10
    ) -> Iterator[DirectoryInfo]:
        """扫描目录结构.

        Args:
            search_paths: 要扫描的相对路径列表,默认扫描整个项目
            max_depth: 最大扫描深度

        Yields:
            DirectoryInfo 对象
        """
        if search_paths is None:
            search_paths = ["."]

        for search_path in search_paths:
            base_path = self.root_path / search_path
            if not base_path.exists():
                continue

            base_depth = len(base_path.parts)

            for dir_path in base_path.rglob("*"):
                if not dir_path.is_dir():
                    continue

                # 检查深度
                depth = len(dir_path.parts) - base_depth
                if depth > max_depth:
                    continue

                # 检查是否在排除目录中
                if self._should_skip_dir(dir_path):
                    continue

                skip = False
                for parent in dir_path.parents:
                    if parent.name in self.config.exclude_dirs:
                        skip = True
                        break
                if skip:
                    continue

                yield DirectoryInfo(
                    path=dir_path,
                    relative_path=dir_path.relative_to(self.root_path),
                    name=dir_path.name,
                    depth=depth,
                )

    def scan_apps(self) -> Iterator[ComponentInfo]:
        """扫描 apps/ 目录下的应用.

        扫描规则:
        - 如果目录直接包含 Python 文件或 __init__.py,视为应用
        - 如果目录不包含 Python 文件但包含子目录,检查子目录是否是应用

        Yields:
            ComponentInfo 对象
        """
        apps_path = self.root_path / "apps"
        if not apps_path.exists():
            return

        for app_dir in apps_path.iterdir():
            if not app_dir.is_dir():
                continue
            if app_dir.name in self.config.exclude_dirs:
                continue
            if app_dir.name in EXCLUDED_APP_DIRS:
                continue
            if app_dir.name.startswith("."):
                continue

            # 检查是否是真正的应用目录(有 __init__.py 或直接的 Python 文件)
            has_init = (app_dir / "__init__.py").exists()
            has_direct_py = any(app_dir.glob("*.py"))

            if has_init or has_direct_py:
                # 这是一个应用
                yield self._create_component_info(app_dir, REQUIRED_APP_FILES)
            else:
                # 检查是否是嵌套的应用目录(如 apps/cli/hello)
                # 这种情况下,父目录不是应用,只检查子目录
                for sub_dir in app_dir.iterdir():
                    if not sub_dir.is_dir():
                        continue
                    if sub_dir.name.startswith("."):
                        continue
                    if sub_dir.name in self.config.exclude_dirs:
                        continue

                    sub_has_init = (sub_dir / "__init__.py").exists()
                    sub_has_py = any(sub_dir.glob("*.py"))
                    if sub_has_init or sub_has_py:
                        yield self._create_component_info(sub_dir, REQUIRED_APP_FILES)

    def scan_packages(self) -> Iterator[ComponentInfo]:
        """扫描 packages/ 目录下的包.

        Yields:
            ComponentInfo 对象
        """
        packages_path = self.root_path / "packages"
        if not packages_path.exists():
            return

        for pkg_dir in packages_path.iterdir():
            if not pkg_dir.is_dir():
                continue
            if pkg_dir.name in self.config.exclude_dirs:
                continue
            if pkg_dir.name.startswith("."):
                continue

            yield self._create_component_info(pkg_dir, REQUIRED_PACKAGE_FILES)

    def _create_component_info(
        self, component_path: Path, required_files: list[str]
    ) -> ComponentInfo:
        """创建组件信息对象.

        Args:
            component_path: 组件目录路径
            required_files: 必需的文件列表

        Returns:
            ComponentInfo 对象
        """
        has_ai_json = (component_path / ".ai.json").exists()
        has_readme = (component_path / "README.md").exists()
        has_init = (component_path / "__init__.py").exists()

        missing_files = []
        for required_file in required_files:
            if not (component_path / required_file).exists():
                missing_files.append(required_file)

        return ComponentInfo(
            path=component_path,
            name=component_path.name,
            has_ai_json=has_ai_json,
            has_readme=has_readme,
            has_init=has_init,
            missing_files=missing_files,
        )

    def check_file_has_metadata(self, file_path: Path, field: str) -> bool:
        """检查文件是否包含指定的元信息字段.

        Args:
            file_path: 文件路径
            field: 元信息字段名(如 'PURPOSE', 'OUTLINE')

        Returns:
            True 如果包含该字段,否则 False
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            # 检查文件开头的 docstring 中是否包含 @FIELD:
            pattern = rf"@{field}:"
            return bool(re.search(pattern, content[:2000]))  # 只检查前 2000 字符
        except (OSError, UnicodeDecodeError):
            return False

    def scan_files_missing_metadata(
        self,
        search_paths: list[str] | None = None,
        required_fields: list[str] | None = None,
    ) -> Iterator[tuple[FileInfo, list[str]]]:
        """扫描缺少元信息的文件.

        Args:
            search_paths: 要扫描的相对路径列表
            required_fields: 必需的元信息字段列表,默认 ['PURPOSE', 'OUTLINE']

        Yields:
            (FileInfo, missing_fields) 元组
        """
        if required_fields is None:
            required_fields = ["PURPOSE", "OUTLINE"]

        for file_info in self.scan_python_files(search_paths):
            # 跳过特殊文件
            if file_info.name in ALLOWED_SPECIAL_FILES:
                continue

            missing_fields = []
            for field_name in required_fields:
                if not self.check_file_has_metadata(file_info.path, field_name):
                    missing_fields.append(field_name)

            if missing_fields:
                yield file_info, missing_fields
