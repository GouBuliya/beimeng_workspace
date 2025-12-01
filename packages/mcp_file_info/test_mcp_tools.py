#!/usr/bin/env python3
"""
@PURPOSE: 测试 MCP 工具功能(无需 MCP SDK)
@OUTLINE:
  - test_get_file_metadata: 测试获取全部元信息
  - test_get_specific_metadata: 测试获取特定字段
@DEPENDENCIES:
  - 内部: packages.mcp_file_info
"""

import json
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from packages.mcp_file_info.parser import FileInfoParser

print("=" * 70)
print("🧪 MCP 工具功能测试(模拟调用)")
print("=" * 70)

parser = FileInfoParser()

# 测试文件路径
test_files = [
    "packages/mcp_file_info/examples/sample_files/example.py",
    "packages/mcp_file_info/examples/sample_files/example.ts",
]

print("\n📋 可用的 MCP 工具:")
print("  1. get_file_metadata - 获取文件全部元信息")
print("  2. get_specific_metadata - 获取特定字段")

for test_file in test_files:
    file_path = Path(__file__).parent.parent.parent / test_file

    if not file_path.exists():
        print(f"\n❌ 文件不存在: {test_file}")
        continue

    print(f"\n{'=' * 70}")
    print(f"📄 测试文件: {file_path.name}")
    print("=" * 70)

    # 测试工具 1: get_file_metadata
    print("\n🔧 工具 1: get_file_metadata")
    print(f'   参数: {{ "file_path": "{test_file}" }}')

    metadata = parser.parse_file(file_path)

    response = {
        "file_path": metadata.file_path,
        "has_metadata": metadata.has_metadata,
        "fields": metadata.fields,
    }

    if not metadata.error:
        response["is_complete"] = metadata.is_complete()
        missing = metadata.missing_required_fields()
        if missing:
            response["missing_required_fields"] = missing
    else:
        response["error"] = metadata.error

    print("\n   响应:")
    print(json.dumps(response, ensure_ascii=False, indent=4))

    # 测试工具 2: get_specific_metadata
    if metadata.has_metadata:
        print("\n🔧 工具 2: get_specific_metadata")
        requested_fields = ["PURPOSE", "OUTLINE", "DEPENDENCIES"]
        print("   参数: {")
        print(f'     "file_path": "{test_file}",')
        print(f'     "fields": {requested_fields}')
        print("   }")

        result = metadata.get_fields(requested_fields)

        response = {
            "file_path": metadata.file_path,
            "has_metadata": metadata.has_metadata,
            "requested_fields": requested_fields,
            "fields": result,
        }

        print("\n   响应:")
        print(json.dumps(response, ensure_ascii=False, indent=4))

print("\n" + "=" * 70)
print("✅ 所有工具测试完成!")
print("=" * 70)

print("\n💡 提示:")
print("   - 这些是 MCP 工具返回的实际数据格式")
print("   - 在 Cursor 中配置 MCP 服务器后可以直接调用这些工具")
print("   - 详见 MCP_SETUP.md 配置说明")
