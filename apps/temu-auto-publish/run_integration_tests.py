#!/usr/bin/env python3
"""
@PURPOSE: 集成测试运行脚本 - 需要真实浏览器环境
@OUTLINE:
  - run_integration_tests(): 运行集成测试
  - check_environment(): 检查环境配置
@GOTCHAS:
  - 需要先配置 .env 文件
  - 需要 Playwright 浏览器已安装
  - 需要有效的登录凭据
@DEPENDENCIES:
  - 外部: pytest, playwright
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
app_root = Path(__file__).parent
sys.path.insert(0, str(app_root))


def check_environment():
    """检查环境配置."""
    print("=" * 80)
    print("环境配置检查")
    print("=" * 80)
    
    errors = []
    
    # 检查.env文件
    env_file = app_root / ".env"
    if not env_file.exists():
        errors.append("❌ .env 文件不存在")
        print("\n请创建 .env 文件并配置以下变量：")
        print("  MIAOSHOU_USERNAME=your_username")
        print("  MIAOSHOU_PASSWORD=your_password")
        print("  BROWSER_HEADLESS=false")
    else:
        print("✓ .env 文件存在")
        
        # 检查必需的环境变量
        from dotenv import load_dotenv
        load_dotenv(env_file)
        
        required_vars = ["MIAOSHOU_USERNAME", "MIAOSHOU_PASSWORD"]
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                errors.append(f"❌ 环境变量 {var} 未设置")
            else:
                print(f"✓ {var} 已设置")
    
    # 检查Playwright安装
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            p.chromium.launch(headless=True)
        print("✓ Playwright Chromium 已安装")
    except Exception as e:
        errors.append(f"❌ Playwright 浏览器未安装: {e}")
        print("\n请运行以下命令安装 Playwright 浏览器：")
        print("  uv run playwright install chromium")
    
    print("\n" + "=" * 80)
    
    if errors:
        print("环境配置检查失败：")
        for error in errors:
            print(f"  {error}")
        print("\n" + "=" * 80)
        return False
    else:
        print("✅ 环境配置检查通过")
        print("=" * 80)
        return True


def run_integration_tests():
    """运行集成测试."""
    import subprocess
    
    # 检查环境
    if not check_environment():
        print("\n请先修复上述问题，然后重新运行。")
        return False
    
    print("\n" + "=" * 80)
    print("运行集成测试")
    print("=" * 80)
    print("\n提示：集成测试需要浏览器交互，可能需要较长时间。")
    print("      请确保测试期间不要操作浏览器窗口。\n")
    
    # 询问是否继续
    response = input("是否继续？(y/N): ").strip().lower()
    if response != 'y':
        print("已取消。")
        return False
    
    # 运行pytest集成测试
    cmd = [
        "uv", "run", "pytest",
        "-v",
        "-m", "integration",
        "--tb=short",
        "--no-cov",  # 集成测试不需要覆盖率
    ]
    
    print(f"\n运行命令: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=app_root)
    
    return result.returncode == 0


def main():
    """主函数."""
    success = run_integration_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

