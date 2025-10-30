"""
@PURPOSE: 测试产品采集功能 - 采集测试产品到妙手ERP公用采集箱
@OUTLINE:
  - test_collect_products(): 采集1-2个测试产品
  - main(): 主测试函数
@DEPENDENCIES:
  - 内部: src.browser.login_controller, src.browser.browser_manager
  - 外部: playwright, loguru
@RELATED: test_controllers.py
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController


async def test_collect_products():
    """测试产品采集功能.
    
    手动在浏览器中采集1-2个测试产品。
    
    Returns:
        bool: 是否成功
    """
    logger.info("=" * 80)
    logger.info("产品采集测试（手动采集）")
    logger.info("=" * 80)

    # 1. 登录
    login_controller = LoginController()
    username = os.getenv("MIAOSHOU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD")

    if not username or not password:
        logger.error("请在 .env 文件中设置 MIAOSHOU_USERNAME 和 MIAOSHOU_PASSWORD")
        return False

    success = await login_controller.login(username, password, headless=False)
    if not success:
        logger.error("❌ 登录失败")
        return False

    page = login_controller.browser_manager.page

    # 2. 导航到产品采集页面
    logger.info("\n导航到产品采集页面...")
    await page.goto("https://erp.91miaoshou.com/common_collect_box/index", timeout=30000)
    await page.wait_for_load_state("domcontentloaded")
    logger.success("✓ 已到达产品采集页面")

    # 3. 等待用户手动采集产品
    logger.info("\n" + "=" * 80)
    logger.info("📝 请手动采集测试产品：")
    logger.info("=" * 80)
    logger.info("1. 在当前浏览器页面，找到「链接输入框」")
    logger.info("2. 粘贴一个1688或淘宝商品链接（推荐低价商品）")
    logger.info("   示例链接：https://detail.1688.com/offer/xxxxxxxx.html")
    logger.info("3. 选择平台（如：Temu）")
    logger.info("4. 点击「采集并自动认领」按钮")
    logger.info("5. 等待采集完成（大约10-30秒）")
    logger.info("6. 建议采集 1-2 个产品用于测试")
    logger.info("=" * 80)
    logger.info("\n⏰ 程序会等待 3 分钟，供您完成手动采集...")
    logger.info("   采集完成后，程序会自动继续\n")

    # 等待3分钟，让用户手动采集
    await asyncio.sleep(180)

    # 4. 检查采集箱中的产品数量
    logger.info("\n检查采集箱中的产品...")
    await page.goto("https://erp.91miaoshou.com/common_collect_box/items", timeout=30000)
    await page.wait_for_load_state("domcontentloaded")
    await asyncio.sleep(2)

    # 尝试获取产品数量
    try:
        # 查找"已认领"tab的产品数量
        claimed_tab_text = await page.locator("text='已认领'").text_content()
        logger.info(f"已认领tab文本: {claimed_tab_text}")

        # 检查是否有产品列表
        product_count = await page.locator("button:has-text('编辑')").count()
        logger.info(f"找到 {product_count} 个产品")

        if product_count > 0:
            logger.success(f"✅ 成功！采集箱中有 {product_count} 个产品")
            return True
        else:
            logger.warning("⚠️ 采集箱中暂无产品，请检查采集是否成功")
            logger.info("\n等待额外30秒，以防采集还在进行中...")
            await asyncio.sleep(30)

            # 再次检查
            product_count = await page.locator("button:has-text('编辑')").count()
            if product_count > 0:
                logger.success(f"✅ 成功！采集箱中有 {product_count} 个产品")
                return True
            else:
                logger.error("❌ 采集箱中仍然没有产品")
                return False

    except Exception as e:
        logger.error(f"检查产品数量失败: {e}")
        return False

    finally:
        # 暂时不关闭浏览器，方便查看
        logger.info("\n浏览器将保持打开状态，请按 Ctrl+C 关闭...")
        await asyncio.sleep(60)  # 等待1分钟
        await login_controller.browser_manager.close()


async def main():
    """主测试函数."""
    logger.info("=" * 80)
    logger.info("妙手ERP产品采集测试")
    logger.info("=" * 80)

    try:
        success = await test_collect_products()

        if success:
            logger.success("\n✅ 产品采集测试完成！可以继续进行编辑流程测试")
        else:
            logger.error("\n❌ 产品采集测试失败")

    except KeyboardInterrupt:
        logger.info("\n用户中断测试")
    except Exception as e:
        logger.error(f"\n测试过程出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

