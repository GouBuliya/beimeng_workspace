#!/usr/bin/env python3
"""
测试改进版批量编辑控制器
验证18步是否都能自动化完成
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.browser.batch_edit_controller_v2 import BatchEditController

async def test_batch_edit_v2():
    """测试改进版批量编辑控制器"""
    print("\n" + "="*70)
    print(" "*15 + "🧪 测试批量编辑控制器 V2")
    print("="*70 + "\n")
    
    login_ctrl = None
    try:
        import os
        username = os.getenv("MIAOSHOU_USERNAME", "")
        password = os.getenv("MIAOSHOU_PASSWORD", "")
        
        # 1. 登录
        print("🔐 [1/3] 登录妙手ERP...")
        login_ctrl = LoginController()
        
        if not await login_ctrl.login(username, password, headless=False):
            print("      ❌ 登录失败\n")
            return
        print("      ✅ 登录成功\n")
        
        page = login_ctrl.browser_manager.page
        
        # 2. 创建批量编辑控制器
        print("🔧 [2/3] 初始化批量编辑控制器...")
        controller = BatchEditController(page)
        print("      ✅ 控制器已初始化\n")
        
        # 3. 导航到批量编辑页面
        print("🧭 [3/3] 导航并进入批量编辑...")
        if not await controller.navigate_to_batch_edit():
            print("      ❌ 导航失败\n")
            return
        print("      ✅ 已进入批量编辑页面\n")
        
        # 4. 执行18步
        print("="*70)
        print("开始执行批量编辑18步")
        print("="*70 + "\n")
        
        product_data = {
            "cost_price": 150.0  # 示例成本价
        }
        
        result = await controller.execute_all_steps(product_data)
        
        # 5. 显示结果
        print("\n" + "="*70)
        print(" "*25 + "📊 执行结果")
        print("="*70 + "\n")
        
        print(f"总计: {result['total']} 步")
        print(f"成功: {result['success']} 步 ✅")
        print(f"失败: {result['failed']} 步 ❌")
        print(f"成功率: {result['success']*100//result['total']}%\n")
        
        # 显示详细结果
        print("详细结果：")
        print("-" * 70)
        for step in result['steps']:
            status_icon = "✅" if step['status'] == 'success' else "❌"
            print(f"{status_icon} 步骤{step['step']}: {step['name']} - {step['status']}")
            if 'error' in step:
                print(f"      错误: {step['error']}")
        print()
        
        # 总体评估
        if result['success'] == result['total']:
            print("🎉 恭喜！所有18步都成功完成！")
        elif result['success'] >= result['total'] * 0.8:
            print("👍 大部分步骤成功！只有少数失败。")
        else:
            print("⚠️  有较多步骤失败，需要进一步调试。")
        
        print("\n💡 浏览器将保持打开30秒，您可以查看最终状态...")
        print("   (按 Ctrl+C 提前关闭)\n")
        
        await page.wait_for_timeout(30000)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断\n")
    except Exception as e:
        print(f"\n\n❌ 发生错误: {e}\n")
        import traceback
        traceback.print_exc()
    finally:
        if login_ctrl and login_ctrl.browser_manager:
            await login_ctrl.browser_manager.close()
            print("✅ 浏览器已关闭\n")

if __name__ == "__main__":
    asyncio.run(test_batch_edit_v2())

