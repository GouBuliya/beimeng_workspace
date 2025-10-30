"""
集成测试：验证妙手ERP自动化流程

测试流程：
1. 登录妙手ERP
2. 导航到公用采集箱
3. 打开第一个产品的编辑弹窗
4. 执行首次编辑操作
5. 保存并验证

运行方式：
    uv run python apps/temu-auto-publish/tests/test_controllers.py
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
current_file = Path(__file__)
app_root = current_file.parent.parent
sys.path.insert(0, str(app_root))

from loguru import logger

from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController
from src.browser.first_edit_controller import FirstEditController


async def test_login():
    """测试1：登录妙手ERP."""
    logger.info("=" * 80)
    logger.info("测试1：登录妙手ERP")
    logger.info("=" * 80)

    # 从环境变量读取凭据
    username = os.getenv("MIAOSHOU_USERNAME", "lyl12345678")
    password = os.getenv("MIAOSHOU_PASSWORD", "Lyl12345678.")

    controller = LoginController()

    try:
        success = await controller.login(username, password, headless=False, force=False)

        if success:
            logger.success("✅ 测试1通过：登录成功")
            
            # 保持浏览器打开，供后续测试使用
            return controller
        else:
            logger.error("❌ 测试1失败：登录失败")
            return None

    except Exception as e:
        logger.error(f"❌ 测试1异常：{e}")
        return None


async def test_navigation(login_controller: LoginController):
    """测试2：导航到公用采集箱."""
    logger.info("=" * 80)
    logger.info("测试2：导航到公用采集箱")
    logger.info("=" * 80)

    miaoshou_controller = MiaoshouController()

    try:
        page = login_controller.browser_manager.page

        # 导航到公用采集箱
        success = await miaoshou_controller.navigate_to_collection_box(page, use_sidebar=True)

        if success:
            logger.success("✅ 测试2通过：导航成功")

            # 获取产品数量
            counts = await miaoshou_controller.get_product_count(page)
            logger.info(f"产品数量统计: {counts}")

            # 切换到已认领tab
            await miaoshou_controller.switch_tab(page, "claimed")

            return miaoshou_controller
        else:
            logger.error("❌ 测试2失败：导航失败")
            return None

    except Exception as e:
        logger.error(f"❌ 测试2异常：{e}")
        return None


async def test_first_edit(login_controller: LoginController, miaoshou_controller: MiaoshouController):
    """测试3：首次编辑功能."""
    logger.info("=" * 80)
    logger.info("测试3：首次编辑功能")
    logger.info("=" * 80)

    first_edit_controller = FirstEditController()

    try:
        page = login_controller.browser_manager.page

        # 点击第一个产品的编辑按钮
        logger.info("打开第一个产品的编辑弹窗...")
        success = await miaoshou_controller.click_edit_first_product(page)

        if not success:
            logger.error("❌ 测试3失败：无法打开编辑弹窗")
            return False

        # 等待弹窗加载
        await first_edit_controller.wait_for_dialog(page)

        # 执行首次编辑流程（使用测试数据）
        test_title = "【测试】自动化产品标题 A9999型号"
        test_price = 150.00
        test_stock = 99
        test_weight = 0.5
        test_dimensions = (40.0, 30.0, 50.0)

        logger.info("开始执行首次编辑流程...")
        logger.info(f"  标题: {test_title}")
        logger.info(f"  价格: {test_price} CNY")
        logger.info(f"  库存: {test_stock}")
        logger.info(f"  重量: {test_weight} KG")
        logger.info(f"  尺寸: {test_dimensions[0]}x{test_dimensions[1]}x{test_dimensions[2]} CM")

        # 注意：这里仅测试部分功能，避免实际修改数据
        # 如果要完整测试，取消注释以下代码：
        
        # success = await first_edit_controller.complete_first_edit(
        #     page,
        #     test_title,
        #     test_price,
        #     test_stock,
        #     test_weight,
        #     test_dimensions
        # )

        # 仅测试单个操作（不保存）
        success = await first_edit_controller.edit_title(page, test_title)

        if success:
            logger.success("✅ 测试3通过：首次编辑功能正常")
            logger.warning("⚠️ 本次测试未保存修改，请手动验证")

            # 关闭弹窗（不保存）
            await first_edit_controller.close_dialog(page)
            await page.wait_for_timeout(1000)

            return True
        else:
            logger.error("❌ 测试3失败：编辑操作失败")
            return False

    except Exception as e:
        logger.error(f"❌ 测试3异常：{e}")
        return False


async def main():
    """运行所有测试."""
    logger.info("=" * 80)
    logger.info("妙手ERP自动化流程集成测试")
    logger.info("=" * 80)

    # 测试1：登录
    login_controller = await test_login()
    if not login_controller:
        logger.error("登录测试失败，终止测试")
        return

    await asyncio.sleep(2)

    # 测试2：导航
    miaoshou_controller = await test_navigation(login_controller)
    if not miaoshou_controller:
        logger.error("导航测试失败，终止测试")
        await login_controller.browser_manager.close()
        return

    await asyncio.sleep(2)

    # 测试3：首次编辑
    success = await test_first_edit(login_controller, miaoshou_controller)

    # 测试完成，保持浏览器打开供手动检查
    logger.info("=" * 80)
    if success:
        logger.success("✅ 所有测试通过！")
    else:
        logger.error("❌ 部分测试失败")
    logger.info("=" * 80)
    logger.info("浏览器将保持打开10秒，供手动检查...")
    logger.info("按 Ctrl+C 可立即关闭")

    try:
        await asyncio.sleep(10)
    except KeyboardInterrupt:
        logger.info("用户中断")

    # 关闭浏览器
    await login_controller.browser_manager.close()
    logger.info("测试完成，浏览器已关闭")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error(f"测试运行失败: {e}")
        import traceback
        traceback.print_exc()
