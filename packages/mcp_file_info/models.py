"""
@PURPOSE: 定义文件元信息的数据模型
@OUTLINE:
  - class FileMetadata: 完整的文件元信息模型
  - class MetadataField: 单个元信息字段模型
  - METADATA_FIELDS: 支持的元信息字段定义
@DEPENDENCIES:
  - 标准库: dataclasses
"""

from dataclasses import dataclass, field
from typing import Any


# 支持的元信息字段定义
METADATA_FIELDS = {
    "PURPOSE": {
        "required": True,
        "description": "文件的核心作用和功能",
    },
    "OUTLINE": {
        "required": True,
        "description": "文件的结构大纲，包括主要类/函数/模块",
    },
    "GOTCHAS": {
        "required": False,
        "description": "易出错点、注意事项、常见陷阱",
    },
    "TECH_DEBT": {
        "required": False,
        "description": "已知的技术债务和待优化项",
    },
    "DEPENDENCIES": {
        "required": False,
        "description": "关键依赖关系（内部/外部模块）",
    },
    "CHANGELOG": {
        "required": False,
        "description": "重要修改历史记录",
    },
    "AUTHOR": {
        "required": False,
        "description": "作者信息",
    },
    "RELATED": {
        "required": False,
        "description": "相关文件引用",
    },
}


@dataclass
class MetadataField:
    """单个元信息字段模型.

    Attributes:
        name: 字段名称（如 PURPOSE, OUTLINE）
        value: 字段内容
        required: 是否为必填字段
        description: 字段描述
    """

    name: str
    value: str = ""
    required: bool = False
    description: str = ""


@dataclass
class FileMetadata:
    """完整的文件元信息模型.

    Attributes:
        file_path: 文件路径
        has_metadata: 是否包含元信息
        fields: 元信息字段字典
        raw_content: 原始注释内容
        error: 错误信息（如果解析失败）
    """

    file_path: str
    has_metadata: bool = False
    fields: dict[str, str] = field(default_factory=dict)
    raw_content: str = ""
    error: str | None = None

    def get_field(self, field_name: str) -> str:
        """获取指定字段的值.

        Args:
            field_name: 字段名称

        Returns:
            字段值，如果不存在则返回空字符串
        """
        return self.fields.get(field_name, "")

    def get_fields(self, field_names: list[str]) -> dict[str, str]:
        """获取多个指定字段的值.

        Args:
            field_names: 字段名称列表

        Returns:
            字段名到值的字典
        """
        return {name: self.fields.get(name, "") for name in field_names}

    def is_complete(self) -> bool:
        """检查必填字段是否完整.

        Returns:
            如果所有必填字段都存在则返回 True
        """
        required_fields = [name for name, info in METADATA_FIELDS.items() if info["required"]]
        return all(field in self.fields and self.fields[field] for field in required_fields)

    def missing_required_fields(self) -> list[str]:
        """获取缺失的必填字段列表.

        Returns:
            缺失的必填字段名称列表
        """
        required_fields = [name for name, info in METADATA_FIELDS.items() if info["required"]]
        return [
            field for field in required_fields if field not in self.fields or not self.fields[field]
        ]
