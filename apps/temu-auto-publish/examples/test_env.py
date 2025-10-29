"""环境测试脚本.

测试依赖是否正确安装。
"""

import sys


def test_imports():
    """测试所有必需的导入."""
    print("测试导入...")

    try:
        import pandas as pd

        print("✓ pandas")
    except ImportError as e:
        print(f"✗ pandas: {e}")
        return False

    try:
        import openpyxl

        print("✓ openpyxl")
    except ImportError as e:
        print(f"✗ openpyxl: {e}")
        return False

    try:
        from pydantic import BaseModel

        print("✓ pydantic")
    except ImportError as e:
        print(f"✗ pydantic: {e}")
        return False

    try:
        from loguru import logger

        print("✓ loguru")
    except ImportError as e:
        print(f"✗ loguru: {e}")
        return False

    try:
        import typer

        print("✓ typer")
    except ImportError as e:
        print(f"✗ typer: {e}")
        return False

    try:
        from rich.console import Console

        print("✓ rich")
    except ImportError as e:
        print(f"✗ rich: {e}")
        return False

    return True


def test_modules():
    """测试项目模块导入."""
    print("\n测试项目模块...")

    try:
        from config.settings import settings

        print("✓ config.settings")
    except ImportError as e:
        print(f"✗ config.settings: {e}")
        return False

    try:
        from src.models.task import ProductInput, TaskData

        print("✓ src.models.task")
    except ImportError as e:
        print(f"✗ src.models.task: {e}")
        return False

    try:
        from src.data_processor.excel_reader import ExcelReader

        print("✓ src.data_processor.excel_reader")
    except ImportError as e:
        print(f"✗ src.data_processor.excel_reader: {e}")
        return False

    try:
        from src.data_processor.price_calculator import PriceCalculator

        print("✓ src.data_processor.price_calculator")
    except ImportError as e:
        print(f"✗ src.data_processor.price_calculator: {e}")
        return False

    try:
        from src.yingdao.cookie_manager import CookieManager

        print("✓ src.yingdao.cookie_manager")
    except ImportError as e:
        print(f"✗ src.yingdao.cookie_manager: {e}")
        return False

    return True


def test_config():
    """测试配置加载."""
    print("\n测试配置...")

    try:
        from config.settings import settings

        print(f"  价格倍率: {settings.price_multiplier}")
        print(f"  供货价倍率: {settings.supply_price_multiplier}")
        print(f"  采集数量: {settings.collect_count}")
        print("✓ 配置加载成功")
        return True
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        return False


def main():
    """运行所有测试."""
    print("=" * 60)
    print("Temu 自动发布 - 环境测试")
    print("=" * 60)
    print(f"Python 版本: {sys.version}")
    print()

    results = []

    # 测试导入
    results.append(("依赖导入", test_imports()))

    # 测试模块
    results.append(("项目模块", test_modules()))

    # 测试配置
    results.append(("配置加载", test_config()))

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n✓ 所有测试通过！环境配置正确。")
        return 0
    else:
        print("\n✗ 部分测试失败，请检查依赖安装。")
        print("\n运行以下命令安装依赖：")
        print("  uv sync --extra temu --extra dev")
        return 1


if __name__ == "__main__":
    sys.exit(main())


