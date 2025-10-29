"""基础使用示例

展示 hello CLI 的基本功能。
"""

import subprocess
import sys


def main() -> None:
    """运行基础示例"""
    print("=== Hello CLI 基础示例 ===\n")

    # 示例 1: 简单问候
    print("1. 简单问候:")
    print("   命令: python -m apps.cli.hello greet World")
    result = subprocess.run(
        [sys.executable, "-m", "apps.cli.hello", "greet", "World"],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"   输出: {result.stdout.strip()}\n")

    # 示例 2: JSON 输出
    print("2. JSON 格式输出:")
    print("   命令: python -m apps.cli.hello greet World --format json")
    result = subprocess.run(
        [sys.executable, "-m", "apps.cli.hello", "greet", "World", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"   输出: {result.stdout.strip()}\n")

    # 示例 3: 自定义问候语
    print("3. 自定义问候语:")
    print("   命令: python -m apps.cli.hello greet 世界 --greeting 你好")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "apps.cli.hello",
            "greet",
            "世界",
            "--greeting",
            "你好",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"   输出: {result.stdout.strip()}\n")

    print("=== 示例完成 ===")


if __name__ == "__main__":
    main()

