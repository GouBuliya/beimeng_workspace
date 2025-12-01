"""
@PURPOSE: 测试文件元信息解析器的核心功能
@OUTLINE:
  - test_parse_python_file: 测试解析Python文件
  - test_parse_typescript_file: 测试解析TypeScript文件
  - test_missing_metadata: 测试处理无元信息的文件
  - test_invalid_file: 测试处理不存在的文件
  - test_get_specific_fields: 测试获取特定字段
  - test_completeness_check: 测试完整性检查
@DEPENDENCIES:
  - 外部: pytest
  - 内部: packages.mcp_file_info
"""

from pathlib import Path

import pytest

from packages.mcp_file_info import FileInfoParser
from packages.mcp_file_info.models import FileMetadata


@pytest.fixture
def parser():
    """创建解析器实例."""
    return FileInfoParser()


@pytest.fixture
def sample_files_dir():
    """获取示例文件目录."""
    return Path(__file__).parent.parent / "examples" / "sample_files"


def test_parse_python_file(parser, sample_files_dir):
    """测试解析Python文件."""
    py_file = sample_files_dir / "example.py"
    metadata = parser.parse_file(py_file)

    assert metadata.has_metadata is True
    assert metadata.error is None
    assert "PURPOSE" in metadata.fields
    assert "OUTLINE" in metadata.fields
    assert len(metadata.get_field("PURPOSE")) > 0


def test_parse_typescript_file(parser, sample_files_dir):
    """测试解析TypeScript文件."""
    ts_file = sample_files_dir / "example.ts"
    metadata = parser.parse_file(ts_file)

    assert metadata.has_metadata is True
    assert metadata.error is None
    assert "PURPOSE" in metadata.fields
    assert "OUTLINE" in metadata.fields


def test_file_not_found(parser):
    """测试处理不存在的文件."""
    metadata = parser.parse_file("nonexistent_file.py")

    assert metadata.has_metadata is False
    assert metadata.error is not None
    assert "不存在" in metadata.error


def test_unsupported_extension(parser, tmp_path):
    """测试不支持的文件类型."""
    # 创建一个不支持的文件类型
    test_file = tmp_path / "test.xyz"
    test_file.write_text("some content")

    metadata = parser.parse_file(test_file)

    assert metadata.has_metadata is False
    assert metadata.error is not None
    assert "不支持" in metadata.error


def test_get_specific_fields(parser, sample_files_dir):
    """测试获取特定字段."""
    py_file = sample_files_dir / "example.py"
    metadata = parser.parse_file(py_file)

    # 获取单个字段
    purpose = metadata.get_field("PURPOSE")
    assert len(purpose) > 0

    # 获取多个字段
    fields = metadata.get_fields(["PURPOSE", "OUTLINE", "DEPENDENCIES"])
    assert "PURPOSE" in fields
    assert "OUTLINE" in fields
    assert "DEPENDENCIES" in fields


def test_completeness_check(parser, sample_files_dir):
    """测试完整性检查."""
    py_file = sample_files_dir / "example.py"
    metadata = parser.parse_file(py_file)

    # 检查是否包含必填字段
    is_complete = metadata.is_complete()
    assert isinstance(is_complete, bool)

    # 如果不完整,应该能获取缺失的字段
    if not is_complete:
        missing = metadata.missing_required_fields()
        assert isinstance(missing, list)
        assert len(missing) > 0


def test_parse_multiple_files(parser, sample_files_dir):
    """测试批量解析文件."""
    files = [
        sample_files_dir / "example.py",
        sample_files_dir / "example.ts",
    ]

    results = parser.parse_multiple_files(files)

    assert len(results) == 2
    for _file_path, metadata in results.items():
        assert isinstance(metadata, FileMetadata)


def test_multiline_field_content(parser, sample_files_dir):
    """测试多行字段内容."""
    py_file = sample_files_dir / "example.py"
    metadata = parser.parse_file(py_file)

    # OUTLINE 字段通常包含多行
    outline = metadata.get_field("OUTLINE")
    assert "\n" in outline or len(outline) > 0


def test_optional_fields(parser, sample_files_dir):
    """测试可选字段."""
    py_file = sample_files_dir / "example.py"
    metadata = parser.parse_file(py_file)

    # 可选字段可能存在也可能不存在
    gotchas = metadata.get_field("GOTCHAS")
    tech_debt = metadata.get_field("TECH_DEBT")
    dependencies = metadata.get_field("DEPENDENCIES")

    # 不应该抛出异常,即使字段不存在
    assert isinstance(gotchas, str)
    assert isinstance(tech_debt, str)
    assert isinstance(dependencies, str)


def test_file_with_no_metadata(parser, tmp_path):
    """测试没有元信息的文件."""
    # 创建一个没有元信息的Python文件
    test_file = tmp_path / "no_metadata.py"
    test_file.write_text("def hello():\n    print('Hello')\n")

    metadata = parser.parse_file(test_file)

    assert metadata.has_metadata is False
    assert metadata.error is None  # 不是错误,只是没有元信息
    assert len(metadata.fields) == 0


def test_field_names_case_sensitive(parser, sample_files_dir):
    """测试字段名大小写敏感."""
    py_file = sample_files_dir / "example.py"
    metadata = parser.parse_file(py_file)

    # 字段名应该是大写
    assert "PURPOSE" in metadata.fields
    assert "purpose" not in metadata.fields  # 小写不应该存在


def test_raw_content_preservation(parser, sample_files_dir):
    """测试原始内容保留."""
    py_file = sample_files_dir / "example.py"
    metadata = parser.parse_file(py_file)

    # 应该保留原始注释内容
    assert len(metadata.raw_content) > 0
    assert isinstance(metadata.raw_content, str)
