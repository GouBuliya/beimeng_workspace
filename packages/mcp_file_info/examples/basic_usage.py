"""
@PURPOSE: 演示如何使用 MCP File Info 工具解析文件元信息
@OUTLINE:
  - example_parse_single_file: 解析单个文件示例
  - example_parse_multiple_files: 批量解析文件示例
  - example_check_completeness: 检查元信息完整性示例
  - main: 运行所有示例
@DEPENDENCIES:
  - 内部: packages.mcp_file_info
@RELATED: ../README.md, sample_files/
"""

from pathlib import Path

from packages.mcp_file_info import FileInfoParser


def example_parse_single_file():
    """示例1: 解析单个文件."""
    print("=" * 60)
    print("示例1: 解析单个文件")
    print("=" * 60)

    parser = FileInfoParser()

    # 解析示例Python文件
    sample_file = Path(__file__).parent / "sample_files" / "example.py"
    metadata = parser.parse_file(sample_file)

    print(f"\n文件: {metadata.file_path}")
    print(f"包含元信息: {metadata.has_metadata}")

    if metadata.has_metadata:
        print(f"\n目的 (PURPOSE):\n{metadata.get_field('PURPOSE')}")
        print(f"\n大纲 (OUTLINE):\n{metadata.get_field('OUTLINE')}")

        if metadata.get_field("GOTCHAS"):
            print(f"\n易错点 (GOTCHAS):\n{metadata.get_field('GOTCHAS')}")

        if metadata.get_field("DEPENDENCIES"):
            print(f"\n依赖 (DEPENDENCIES):\n{metadata.get_field('DEPENDENCIES')}")

        # 检查完整性
        print(f"\n必填字段完整: {metadata.is_complete()}")
        missing = metadata.missing_required_fields()
        if missing:
            print(f"缺失字段: {', '.join(missing)}")
    else:
        print(f"错误: {metadata.error}")


def example_parse_multiple_files():
    """示例2: 批量解析多个文件."""
    print("\n" + "=" * 60)
    print("示例2: 批量解析多个文件")
    print("=" * 60)

    parser = FileInfoParser()

    # 获取所有示例文件
    sample_dir = Path(__file__).parent / "sample_files"
    sample_files = list(sample_dir.glob("*"))

    # 批量解析
    results = parser.parse_multiple_files(sample_files)

    print(f"\n共解析 {len(results)} 个文件:\n")

    for file_path, metadata in results.items():
        filename = Path(file_path).name
        print(f"📄 {filename}")

        if metadata.has_metadata:
            purpose = metadata.get_field("PURPOSE")
            # 截断过长的内容
            if len(purpose) > 60:
                purpose = purpose[:60] + "..."
            print(f"   目的: {purpose}")
            print(f"   完整性: {'✅' if metadata.is_complete() else '❌'}")
        else:
            print("   状态: 无元信息或解析失败")
            if metadata.error:
                print(f"   错误: {metadata.error}")
        print()


def example_check_completeness():
    """示例3: 检查元信息完整性."""
    print("=" * 60)
    print("示例3: 检查元信息完整性")
    print("=" * 60)

    parser = FileInfoParser()
    sample_dir = Path(__file__).parent / "sample_files"

    files = list(sample_dir.glob("*"))
    complete_files = []
    incomplete_files = []

    for file_path in files:
        metadata = parser.parse_file(file_path)
        if metadata.has_metadata:
            if metadata.is_complete():
                complete_files.append(file_path)
            else:
                incomplete_files.append((file_path, metadata.missing_required_fields()))

    print(f"\n✅ 完整的文件 ({len(complete_files)}):")
    for f in complete_files:
        print(f"   - {f.name}")

    if incomplete_files:
        print(f"\n❌ 不完整的文件 ({len(incomplete_files)}):")
        for f, missing in incomplete_files:
            print(f"   - {f.name}")
            print(f"     缺失字段: {', '.join(missing)}")


def example_get_specific_fields():
    """示例4: 获取特定字段."""
    print("\n" + "=" * 60)
    print("示例4: 获取特定字段")
    print("=" * 60)

    parser = FileInfoParser()
    sample_file = Path(__file__).parent / "sample_files" / "example.py"
    metadata = parser.parse_file(sample_file)

    # 只获取感兴趣的字段
    fields = metadata.get_fields(["PURPOSE", "DEPENDENCIES", "TECH_DEBT"])

    print(f"\n文件: {sample_file.name}\n")
    for field_name, value in fields.items():
        if value:
            print(f"{field_name}:")
            print(f"  {value}\n")
        else:
            print(f"{field_name}: (未定义)\n")


def main():
    """运行所有示例."""
    print("\n🚀 MCP File Info 使用示例\n")

    example_parse_single_file()
    example_parse_multiple_files()
    example_check_completeness()
    example_get_specific_fields()

    print("\n✨ 所有示例运行完成!\n")


if __name__ == "__main__":
    main()
