#!/usr/bin/env python3
"""
完整发布工作流测试脚本
演示从公用采集箱到Temu全托管采集箱的完整流程
"""

import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(project_root / ".env")

from src.browser.login_controller import LoginController  # noqa: E402
from src.workflows.complete_publish_workflow import CompletePublishWorkflow  # noqa: E402


async def test_complete_workflow():
    """测试完整发布工作流"""
    print("\n" + "=" * 70)
    print(" " * 15 + "🚀 完整发布工作流测试")
    print("=" * 70 + "\n")

    print("流程说明:")
    print("  阶段1: 公用采集箱首次编辑(5个产品)")
    print("  阶段2: 认领产品(5x4=20个)")
    print("  阶段3: Temu全托管采集箱批量编辑(18步)")
    print("  阶段4: 选择店铺、设置供货价、批量发布")
    print()

    login_ctrl = None
    try:
        import os

        username = os.getenv("MIAOSHOU_USERNAME", "")
        password = os.getenv("MIAOSHOU_PASSWORD", "")

        # 1. 登录
        print("🔐 登录妙手ERP...")
        login_ctrl = LoginController()

        if not await login_ctrl.login(username, password, headless=False):
            print("❌ 登录失败\n")
            return
        print("✅ 登录成功\n")

        page = login_ctrl.browser_manager.page

        # 2. 准备测试数据
        print("📋 准备产品数据...")
        product_data_list = [
            {
                "id": f"P{i:03d}",
                "name": f"药箱收纳盒{i}",
                "cost_price": 150.0,
                "suggested_price": 1500.0,
                "supply_price": 450.0,
                "keyword": "药箱收纳盒",
            }
            for i in range(1, 6)
        ]
        print(f"✅ 已准备{len(product_data_list)}个产品数据\n")

        # 3. 创建工作流
        print("🔧 初始化工作流控制器...")
        workflow = CompletePublishWorkflow(page)
        print("✅ 控制器已初始化\n")

        # 4. 执行完整工作流
        print("=" * 70)
        print("开始执行完整工作流")
        print("=" * 70 + "\n")

        result = await workflow.execute_full_workflow(
            product_data_list,
            username="keshijun123",  # 筛选柯诗俊的产品
        )

        # 5. 显示结果
        print("\n" + "=" * 70)
        print(" " * 20 + "📊 工作流执行结果")
        print("=" * 70 + "\n")

        print(f"流程ID: {result['workflow_id']}")
        print(f"开始时间: {result['start_time']}")
        print(f"结束时间: {result.get('end_time', 'N/A')}")
        print(f"总体状态: {'✅ 成功' if result['total_success'] else '❌ 失败'}\n")

        print("各阶段结果:")
        print("-" * 70)

        stages = [
            ("阶段1", "stage1_first_edit", "公用采集箱首次编辑"),
            ("阶段2", "stage2_claim", "认领产品"),
            ("阶段3", "stage3_batch_edit", "批量编辑18步"),
            ("阶段4", "stage4_publish", "选择店铺、发布"),
        ]

        for stage_label, stage_key, stage_desc in stages:
            if stage_key in result["stages"]:
                stage_result = result["stages"][stage_key]
                status = "✅" if stage_result.get("success") else "❌"
                message = stage_result.get("message", "N/A")
                print(f"{status} {stage_label} ({stage_desc}): {message}")

                # 显示详细信息
                if stage_key == "stage1_first_edit":
                    edited_count = stage_result.get("edited_count", 0)
                    print(f"      已编辑产品数: {edited_count}")
                elif stage_key == "stage2_claim":
                    total_claimed = stage_result.get("total_claimed", 0)
                    print(f"      已认领次数: {total_claimed}")
                elif stage_key == "stage3_batch_edit":
                    success_count = stage_result.get("success_count", 0)
                    failed_count = stage_result.get("failed_count", 0)
                    print(f"      成功步骤: {success_count}, 失败步骤: {failed_count}")

        print()

        # 总体评估
        if result["total_success"]:
            print("🎉 恭喜! 完整工作流执行成功!")
            print("   产品已从公用采集箱完成首次编辑、认领、批量编辑, 并成功发布!")
        else:
            print("⚠️  工作流部分失败, 请查看上述详细结果.")
            if "error" in result:
                print(f"   错误信息: {result['error']}")

        print("\n💡 浏览器将保持打开30秒, 您可以查看最终状态...")
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
    print("""
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║              完整发布工作流 - 从采集箱到发布                          ║
║                                                                    ║
║  本脚本演示完整的商品发布流程:                                        ║
║  1. 公用采集箱 → 首次编辑(AI标题、类目、图片)                        ║
║  2. 认领4次 → 生成20个产品                                           ║
║  3. Temu全托管采集箱 → 批量编辑18步                                  ║
║  4. 选择店铺、设置供货价、批量发布                                     ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
    """)

    asyncio.run(test_complete_workflow())
