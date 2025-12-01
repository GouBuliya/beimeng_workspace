"""
@PURPOSE: 数据转换脚本使用示例
@OUTLINE:
  - def main(): 运行所有示例
  - 示例1: 转换为大写
  - 示例2: 转换为小写
  - 示例3: 反转字符串
@DEPENDENCIES:
  - 标准库: json, subprocess, sys, pathlib
"""

import subprocess
import sys
from pathlib import Path


def main() -> None:
    """运行示例"""
    print("=== 数据转换脚本示例 ===\n")

    script_dir = Path(__file__).parent
    sample_data_path = script_dir / "sample_data.json"

    # 示例 1: 转换为大写
    print("1. 转换为大写:")
    print("   命令: cat sample_data.json | python main.py")
    with open(sample_data_path) as f:
        result = subprocess.run(
            [sys.executable, str(script_dir.parent / "main.py")],
            stdin=f,
            capture_output=True,
            text=True,
            check=False,
        )
    print(f"   输出:\n{result.stdout}\n")

    # 示例 2: 转换为小写
    print("2. 转换为小写:")
    print("   命令: python main.py -i sample_data.json --operation lowercase")
    result = subprocess.run(
        [
            sys.executable,
            str(script_dir.parent / "main.py"),
            "--input",
            str(sample_data_path),
            "--operation",
            "lowercase",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"   输出:\n{result.stdout}\n")

    # 示例 3: 反转字符串
    print("3. 反转字符串:")
    print("   命令: python main.py -i sample_data.json --operation reverse")
    result = subprocess.run(
        [
            sys.executable,
            str(script_dir.parent / "main.py"),
            "--input",
            str(sample_data_path),
            "--operation",
            "reverse",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"   输出:\n{result.stdout}\n")

    print("=== 示例完成 ===")


if __name__ == "__main__":
    main()
