"""
@PURPOSE: MCP File Info 包的初始化模块
@OUTLINE:
  - 导出主要类和函数供外部使用
  - 提供版本信息
@DEPENDENCIES:
  - 内部: .parser, .models, .config
"""

__version__ = "0.1.0"

from .config import COMMENT_PATTERNS, SUPPORTED_EXTENSIONS, ParserConfig
from .models import METADATA_FIELDS, FileMetadata, MetadataField
from .parser import FileInfoParser

__all__ = [
    "FileInfoParser",
    "FileMetadata",
    "MetadataField",
    "METADATA_FIELDS",
    "ParserConfig",
    "COMMENT_PATTERNS",
    "SUPPORTED_EXTENSIONS",
]
