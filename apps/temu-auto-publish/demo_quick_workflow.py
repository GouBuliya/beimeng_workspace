"""
@PURPOSE: 快速打通方案演示脚本 - 展示5→20→批量编辑→发布的完整流程
@OUTLINE:
  - demo_five_to_twenty: 演示5→20工作流
  - demo_complete_workflow: 演示完整工作流
  - main: 主函数
@DEPENDENCIES:
  - 内部: workflows, browser
  - 外部: playwright, loguru, python-dotenv
"""

import asyncio
import os
from pathlib import Path

from loguru import logger

# 加载.env文件
try:
    from dotenv import load_dotenv

    # 加载项目根目录的.env文件
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.debug(f"✓ 已加载环境变量从: {env_path}")
    else:
        logger.warning(f"⚠️  .env文件不存在: {env_path}")
except ImportError:
    logger.warning("⚠️  python-dotenv未安装，将直接使用系统环境变量")

from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController
from src.workflows.complete_publish_workflow import CompletePublishWorkflow
from src.utils.debug_helper import DebugHelper, DebugConfig


# 演示数据
DEMO_PRODUCTS_DATA = [
    {
        "keyword": "药箱收纳盒",
        "model_number": "A0001",
        "cost": 10.0,
        "stock": 100,
    },
    {
        "keyword": "药箱收纳盒",
        "model_number": "A0002",
        "cost": 12.0,
        "stock": 100,
    },
    {
        "keyword": "药箱收纳盒",
        "model_number": "A0003",
        "cost": 15.0,
        "stock": 100,
    },
    {
        "keyword": "药箱收纳盒",
        "model_number": "A0004",
        "cost": 11.0,
        "stock": 100,
    },
    {
        "keyword": "药箱收纳盒",
        "model_number": "A0005",
        "cost": 13.0,
        "stock": 100,
    },
]


async def demo_five_to_twenty():
    """演示5→20工作流."""
    logger.info("=" * 100)
    logger.info("演示：5→20工作流（快速打通方案 - 阶段1）")
    logger.info("=" * 100)

    login_ctrl = None

    # 创建调试助手（根据需要配置）
    debug = DebugHelper(
        DebugConfig(
            enabled=True,
            auto_screenshot=True,
            auto_save_html=False,  # HTML较大，可选择关闭
            enable_timing=True,
            enable_breakpoint=False,
        )
    )

    try:
        # 1. 初始化和登录
        logger.info("\n[1/4] 初始化浏览器...")
        debug.start_timer("total")
        login_ctrl = LoginController()

        # 从环境变量获取登录信息（已从.env加载）
        username = os.getenv("MIAOSHOU_USERNAME") or os.getenv("TEMU_USERNAME", "")
        password = os.getenv("MIAOSHOU_PASSWORD") or os.getenv("TEMU_PASSWORD", "")

        if not username or not password:
            logger.error("✗ 请在.env文件中设置 TEMU_USERNAME 和 TEMU_PASSWORD")
            logger.info("或设置环境变量:")
            logger.info("  export MIAOSHOU_USERNAME=你的用户名")
            logger.info("  export MIAOSHOU_PASSWORD=你的密码")
            return

        logger.info("[2/4] 登录妙手ERP...")
        debug.start_timer("login")
        if not await login_ctrl.login(username, password):
            logger.error("✗ 登录失败")
            return
        debug.end_timer("login")

        page = login_ctrl.browser_manager.page
        await debug.save_state(page, "01_after_login")

        # 2. 导航到采集箱
        logger.info("[3/4] 导航到公用采集箱...")
        debug.start_timer("navigate")
        miaoshou_ctrl = MiaoshouController()
        if not await miaoshou_ctrl.navigate_to_collection_box(page):
            logger.error("✗ 导航失败")
            return
        debug.end_timer("navigate")
        await debug.save_state(page, "02_collection_box")

        # 3. 立即切换到"全部"tab
        logger.info("切换到「全部」tab...")
        debug.start_timer("switch_tab")
        if not await miaoshou_ctrl.switch_tab(page, "all"):
            logger.warning("⚠️ 切换tab失败，但继续尝试执行")
        debug.end_timer("switch_tab")
        await page.wait_for_timeout(1000)
        await debug.save_state(page, "03_after_tab_switch")

        # 4. 执行5→20工作流
        logger.info("[4/4] 执行5→20工作流...")
        debug.start_timer("workflow_execution")
        from src.workflows.five_to_twenty_workflow import execute_five_to_twenty_workflow

        result = await execute_five_to_twenty_workflow(page, DEMO_PRODUCTS_DATA)
        debug.end_timer("workflow_execution")
        await debug.save_state(page, "04_workflow_complete", full_page=True)

        # 5. 显示结果
        logger.info("\n" + "=" * 100)
        logger.info("演示结果")
        logger.info("=" * 100)
        logger.info(f"编辑成功: {result['edited_count']}/5")
        logger.info(f"认领成功: {result['claimed_count']}/{result['edited_count']}")
        logger.info(f"最终产品数: {result['final_count']}")
        logger.info(f"执行状态: {'✓ 成功' if result['success'] else '✗ 失败'}")

        if result["errors"]:
            logger.warning("错误列表：")
            for error in result["errors"]:
                logger.warning(f"  - {error}")

        logger.info("=" * 100)

        # 等待用户查看
        logger.info("\n等待10秒后关闭浏览器...")
        await page.wait_for_timeout(10000)

    except Exception as e:
        logger.error(f"演示失败: {e}")
        import traceback

        traceback.print_exc()

    finally:
        if login_ctrl and login_ctrl.browser_manager:
            await login_ctrl.browser_manager.close()


async def demo_complete_workflow():
    """演示完整工作流（包含批量编辑，不包含发布）."""
    logger.info("=" * 100)
    logger.info("演示：完整工作流（快速打通方案 - 阶段1+2+3）")
    logger.info("=" * 100)

    login_ctrl = None

    # 创建调试助手
    debug = DebugHelper(
        DebugConfig(
            enabled=True,
            auto_screenshot=True,
            auto_save_html=False,
            enable_timing=True,
            enable_breakpoint=False,
        )
    )

    try:
        # 1. 初始化和登录
        logger.info("\n[1/4] 初始化浏览器...")
        debug.start_timer("total")
        login_ctrl = LoginController()

        # 从环境变量获取登录信息（已从.env加载）
        username = os.getenv("MIAOSHOU_USERNAME") or os.getenv("TEMU_USERNAME", "")
        password = os.getenv("MIAOSHOU_PASSWORD") or os.getenv("TEMU_PASSWORD", "")

        if not username or not password:
            logger.error("✗ 请在.env文件中设置 TEMU_USERNAME 和 TEMU_PASSWORD")
            logger.info("或设置环境变量:")
            logger.info("  export MIAOSHOU_USERNAME=你的用户名")
            logger.info("  export MIAOSHOU_PASSWORD=你的密码")
            return

        logger.info("[2/4] 登录妙手ERP...")
        debug.start_timer("login")
        if not await login_ctrl.login(username, password):
            logger.error("✗ 登录失败")
            return
        debug.end_timer("login")

        page = login_ctrl.browser_manager.page
        await debug.save_state(page, "01_after_login")

        # 2. 导航到采集箱
        logger.info("[3/4] 导航到公用采集箱...")
        debug.start_timer("navigate")
        miaoshou_ctrl = MiaoshouController()
        if not await miaoshou_ctrl.navigate_to_collection_box(page):
            logger.error("✗ 导航失败")
            return
        debug.end_timer("navigate")
        await debug.save_state(page, "02_collection_box")

        # 3. 执行完整工作流
        logger.info("[4/4] 执行完整工作流...")
        debug.start_timer("complete_workflow")
        workflow = CompletePublishWorkflow()

        result = await workflow.execute(
            page,
            DEMO_PRODUCTS_DATA,
            shop_name=None,  # 使用第一个店铺
            enable_batch_edit=True,  # 启用批量编辑
            enable_publish=False,  # 禁用发布（演示模式）
        )
        debug.end_timer("complete_workflow")
        await debug.save_state(page, "03_workflow_complete", full_page=True)

        # 4. 显示结果
        logger.info("\n" + "=" * 100)
        logger.info("演示结果")
        logger.info("=" * 100)

        logger.info("\n【阶段1：5→20工作流】")
        stage1 = result["stage1_result"]
        logger.info(f"  状态: {'✓ 成功' if stage1.get('success') else '✗ 失败'}")
        logger.info(f"  编辑成功: {stage1.get('edited_count', 0)}/5")
        logger.info(f"  认领成功: {stage1.get('claimed_count', 0)}/5")
        logger.info(f"  最终产品数: {stage1.get('final_count', 0)}")

        logger.info("\n【阶段2：批量编辑18步】")
        stage2 = result["stage2_result"]
        if stage2.get("skipped"):
            logger.info("  状态: ⏭️  已跳过")
        else:
            logger.info(f"  状态: {'✓ 成功' if stage2.get('success') else '✗ 失败'}")
            if not stage2.get("success"):
                logger.warning("  提示: 批量编辑失败可能是因为选择器缺失，需要使用Codegen获取")

        logger.info("\n【阶段3：发布流程】")
        stage3 = result["stage3_result"]
        if stage3.get("skipped"):
            logger.info("  状态: ⏭️  已跳过（演示模式）")
        else:
            logger.info(f"  状态: {'✓ 成功' if stage3.get('success') else '✗ 失败'}")

        logger.info(f"\n【总体结果】: {'✓ 成功' if result['success'] else '✗ 失败'}")

        if result["errors"]:
            logger.warning("\n错误列表：")
            for error in result["errors"]:
                logger.warning(f"  - {error}")

        logger.info("=" * 100)

        debug.end_timer("total")

        # 显示性能摘要
        debug.log_performance_summary()

        # 等待用户查看
        logger.info("\n等待10秒后关闭浏览器...")
        await page.wait_for_timeout(10000)

    except Exception as e:
        logger.error(f"演示失败: {e}")
        # 保存错误状态
        try:
            await debug.save_error_state(page, "demo_failed", e)
        except:
            pass
        import traceback

        traceback.print_exc()

    finally:
        if login_ctrl and login_ctrl.browser_manager:
            await login_ctrl.browser_manager.close()


async def main():
    """主函数 - 选择演示模式."""
    print("\n" + "=" * 100)
    print("快速打通方案演示")
    print("=" * 100)
    print("\n请选择演示模式：")
    print("1. 演示5→20工作流（推荐首次测试）")
    print("2. 演示完整工作流（包含批量编辑，不包含发布）")
    print("=" * 100)

    try:
        choice = input("\n请输入选项（1或2）：").strip()

        if choice == "1":
            await demo_five_to_twenty()
        elif choice == "2":
            await demo_complete_workflow()
        else:
            print("无效选项，退出...")

    except KeyboardInterrupt:
        print("\n\n用户中断，退出...")


if __name__ == "__main__":
    asyncio.run(main())
