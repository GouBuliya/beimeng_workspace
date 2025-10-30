"""
@PURPOSE: MCP服务器实现，提供文件元信息提取工具
@OUTLINE:
  - get_file_metadata: 获取文件全部元信息
  - get_specific_metadata: 获取指定字段的元信息
  - main: 启动MCP服务器
@GOTCHAS:
  - MCP协议要求严格的JSON格式
  - 错误处理需要返回明确的错误信息
@TECH_DEBT:
  - TODO: 添加缓存机制提高性能
  - TODO: 支持并发解析多个文件
@DEPENDENCIES:
  - 内部: .parser, .models
  - 外部: mcp
"""

import asyncio
import json
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .models import METADATA_FIELDS
from .parser import FileInfoParser

# 创建 MCP 服务器实例
app = Server("mcp-file-info")

# 创建解析器实例
parser = FileInfoParser()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用的工具.

    Returns:
        工具列表
    """
    return [
        Tool(
            name="get_file_metadata",
            description="获取文件的全部元信息。读取文件头部的元数据注释并返回所有字段。",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "要读取的文件路径（绝对路径或相对路径）",
                    }
                },
                "required": ["file_path"],
            },
        ),
        Tool(
            name="get_specific_metadata",
            description="获取文件的特定元信息字段。可以指定要获取的字段名称列表。",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "要读取的文件路径",
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": f"要获取的字段名称列表。可用字段: {', '.join(METADATA_FIELDS.keys())}",
                    },
                },
                "required": ["file_path", "fields"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """处理工具调用.

    Args:
        name: 工具名称
        arguments: 工具参数

    Returns:
        工具执行结果
    """
    if name == "get_file_metadata":
        return await get_file_metadata(arguments)
    elif name == "get_specific_metadata":
        return await get_specific_metadata(arguments)
    else:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": f"未知的工具: {name}"}, ensure_ascii=False, indent=2
                ),
            )
        ]


async def get_file_metadata(arguments: dict) -> list[TextContent]:
    """获取文件的全部元信息.

    Args:
        arguments: 包含 file_path 的参数字典

    Returns:
        包含元信息的响应
    """
    file_path = arguments.get("file_path")

    if not file_path:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": "缺少必需参数: file_path"}, ensure_ascii=False, indent=2
                ),
            )
        ]

    # 解析文件
    metadata = parser.parse_file(file_path)

    # 构建响应
    response = {
        "file_path": metadata.file_path,
        "has_metadata": metadata.has_metadata,
        "fields": metadata.fields,
    }

    if metadata.error:
        response["error"] = metadata.error
    else:
        # 添加完整性检查
        response["is_complete"] = metadata.is_complete()
        missing = metadata.missing_required_fields()
        if missing:
            response["missing_required_fields"] = missing

    return [
        TextContent(
            type="text", text=json.dumps(response, ensure_ascii=False, indent=2)
        )
    ]


async def get_specific_metadata(arguments: dict) -> list[TextContent]:
    """获取文件的特定元信息字段.

    Args:
        arguments: 包含 file_path 和 fields 的参数字典

    Returns:
        包含指定字段的响应
    """
    file_path = arguments.get("file_path")
    fields = arguments.get("fields", [])

    if not file_path:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": "缺少必需参数: file_path"}, ensure_ascii=False, indent=2
                ),
            )
        ]

    if not fields:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": "缺少必需参数: fields"}, ensure_ascii=False, indent=2
                ),
            )
        ]

    # 验证字段名称
    invalid_fields = [f for f in fields if f not in METADATA_FIELDS]
    if invalid_fields:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "error": f"无效的字段名称: {', '.join(invalid_fields)}",
                        "valid_fields": list(METADATA_FIELDS.keys()),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]

    # 解析文件
    metadata = parser.parse_file(file_path)

    if metadata.error:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": metadata.error, "file_path": metadata.file_path},
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        ]

    # 获取指定字段
    result = metadata.get_fields(fields)

    response = {
        "file_path": metadata.file_path,
        "has_metadata": metadata.has_metadata,
        "requested_fields": fields,
        "fields": result,
    }

    return [
        TextContent(
            type="text", text=json.dumps(response, ensure_ascii=False, indent=2)
        )
    ]


async def main():
    """启动 MCP 服务器."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

