"""
@PURPOSE: 定义MCP文件信息工具的配置
@OUTLINE:
  - COMMENT_PATTERNS: 不同文件类型的注释模式定义
  - SUPPORTED_EXTENSIONS: 支持的文件扩展名集合
  - class ParserConfig: 解析器配置类
@DEPENDENCIES:
  - 标准库: dataclasses
"""

from dataclasses import dataclass


# 不同文件类型的注释模式
# 每种模式定义：(开始标记, 结束标记, 行内前缀)
COMMENT_PATTERNS = {
    # Python
    ".py": [
        ('"""', '"""', ""),  # 三引号字符串
        ("'''", "'''", ""),  # 三引号字符串
        ("#", None, "#"),  # 单行注释
    ],
    # JavaScript/TypeScript
    ".js": [
        ("/*", "*/", " *"),  # 多行注释
        ("//", None, "//"),  # 单行注释
    ],
    ".ts": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
    ".jsx": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
    ".tsx": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
    # Java/C/C++
    ".java": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
    ".c": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
    ".cpp": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
    ".h": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
    ".hpp": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
    # Go
    ".go": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
    # Rust
    ".rs": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
    # Ruby
    ".rb": [
        ("=begin", "=end", ""),
        ("#", None, "#"),
    ],
    # Shell
    ".sh": [
        ("#", None, "#"),
    ],
    ".bash": [
        ("#", None, "#"),
    ],
    # YAML
    ".yaml": [
        ("#", None, "#"),
    ],
    ".yml": [
        ("#", None, "#"),
    ],
    # HTML/XML
    ".html": [
        ("<!--", "-->", ""),
    ],
    ".xml": [
        ("<!--", "-->", ""),
    ],
    # CSS
    ".css": [
        ("/*", "*/", " *"),
    ],
    ".scss": [
        ("/*", "*/", " *"),
        ("//", None, "//"),
    ],
}

# 支持的文件扩展名集合
SUPPORTED_EXTENSIONS = set(COMMENT_PATTERNS.keys())


@dataclass
class ParserConfig:
    """解析器配置类.

    Attributes:
        max_lines_to_read: 最大读取行数（只读文件头部）
        strip_comment_markers: 是否移除注释标记
        normalize_whitespace: 是否规范化空白字符
    """

    max_lines_to_read: int = 100
    strip_comment_markers: bool = True
    normalize_whitespace: bool = True

