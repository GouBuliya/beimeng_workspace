#!/usr/bin/env python3
"""
@PURPOSE: 简单的功能验证脚本
@OUTLINE:
  - 直接导入模块测试核心功能
"""

import sys
from pathlib import Path

# 添加包目录到路径
package_dir = Path(__file__).parent.parent
sys.path.insert(0, str(package_dir))

from config import SUPPORTED_EXTENSIONS
from parser import FileInfoParser

print("=" * 60)
print("MCP File Info - 功能验证")
print("=" * 60)

# 测试1: 检查支持的文件类型
print("\n✓ 支持的文件类型:")
print(f"  共 {len(SUPPORTED_EXTENSIONS)} 种: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

# 测试2: 创建解析器
parser = FileInfoParser()
print("\n✓ 解析器创建成功")

# 测试3: 解析示例Python文件
sample_dir = Path(__file__).parent / "sample_files"
py_file = sample_dir / "example.py"

if py_file.exists():
    print(f"\n✓ 解析文件: {py_file.name}")
    metadata = parser.parse_file(py_file)

    if metadata.has_metadata:
        print("  ✓ 成功提取元信息")
        print(f"  - 文件路径: {metadata.file_path}")
        print(f"  - 包含字段: {', '.join(metadata.fields.keys())}")
        print(f"  - 必填字段完整: {'是' if metadata.is_complete() else '否'}")

        if metadata.get_field("PURPOSE"):
            purpose = metadata.get_field("PURPOSE")
            if len(purpose) > 60:
                purpose = purpose[:60] + "..."
            print(f"  - 目的: {purpose}")
    else:
        print(f"  ✗ 解析失败: {metadata.error}")
else:
    print(f"\n✗ 示例文件不存在: {py_file}")

# 测试4: 解析TypeScript文件
ts_file = sample_dir / "example.ts"
if ts_file.exists():
    print(f"\n✓ 解析文件: {ts_file.name}")
    metadata = parser.parse_file(ts_file)

    if metadata.has_metadata:
        print("  ✓ 成功提取元信息")
        print(f"  - 包含字段: {', '.join(metadata.fields.keys())}")
    else:
        print(f"  ✗ 解析失败: {metadata.error}")

# 测试5: 批量解析
print("\n✓ 测试批量解析")
sample_files = list(sample_dir.glob("*"))
if sample_files:
    results = parser.parse_multiple_files(sample_files)
    print(f"  - 解析了 {len(results)} 个文件")
    success_count = sum(1 for m in results.values() if m.has_metadata)
    print(f"  - 成功提取元信息: {success_count}/{len(results)}")

print("\n" + "=" * 60)
print("✨ 所有测试完成!")
print("=" * 60)
