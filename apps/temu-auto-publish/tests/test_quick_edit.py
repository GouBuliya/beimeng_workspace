"""
@PURPOSE: 快速验证编辑流程 - 检查现有产品并测试编辑
@OUTLINE:
  - quick_test(): 快速测试编辑流程(使用现有产品)
  - main(): 主函数
@DEPENDENCIES:
  - 内部: src.browser控制器
  - 外部: playwright, loguru
"""

import asyncio
import os
import random
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv

env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)

from loguru import logger
from src.browser.first_edit_controller import FirstEditController
from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController
from src.data_processor.price_calculator import PriceCalculator, PriceResult
from src.data_processor.title_generator import TitleGenerator


async def quick_test():
    """快速测试编辑流程."""
    # 登录
    login_controller = LoginController()
    username = os.getenv("MIAOSHOU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD")

    logger.info("正在登录...")
    success = await login_controller.login(username, password, headless=False)
    if not success:
        logger.error("登录失败")
        return False

    page = login_controller.browser_manager.page
    miaoshou_controller = MiaoshouController()

    # 导航到采集箱
    logger.info("正在导航到采集箱...")
    await miaoshou_controller.navigate_to_collection_box(page, use_sidebar=False)
    await asyncio.sleep(1)  # 1秒

    # 尝试关闭可能出现的弹窗
    logger.info("检查并关闭可能的弹窗...")
    try:
        # 查找"我知道了"按钮
        know_btn_count = await page.locator("button:has-text('我知道了')").count()
        if know_btn_count > 0:
            logger.info("发现弹窗,点击「我知道了」...")
            await page.locator("button:has-text('我知道了')").first.click()
            await asyncio.sleep(0.5)  # 0.5秒
            logger.success("✓ 已关闭弹窗")

        # 也尝试其他可能的关闭按钮
        close_btn_count = await page.locator("button:has-text('关闭')").count()
        if close_btn_count > 0:
            await page.locator("button:has-text('关闭')").first.click()
            await asyncio.sleep(0.3)  # 0.3秒
    except Exception as e:
        logger.warning(f"关闭弹窗时出错(可忽略): {e}")

    # 切换到"全部"tab(SOP要求:先切换到全部tab)
    logger.info("正在切换到「全部」tab...")
    try:
        # 方法1: 使用正则表达式匹配完整的tab文本(包含数字),例如 "全部 (7661)"
        all_tab_regex = await page.locator("text=/全部.*\\(\\d+\\)/").count()
        if all_tab_regex > 0:
            await page.locator("text=/全部.*\\(\\d+\\)/").click()
            await asyncio.sleep(1)  # 1秒
            logger.success("✓ 已切换到「全部」tab(方法1)")
        else:
            # 方法2: 尝试通过radio button的class定位
            radio_buttons = await page.locator(".jx-radio-button:has-text('全部')").count()
            if radio_buttons > 0:
                await page.locator(".jx-radio-button:has-text('全部')").first.click()
                await asyncio.sleep(1)  # 1秒
                logger.success("✓ 已切换到「全部」tab(方法2)")
            else:
                logger.warning("未找到「全部」tab,可能已经在全部tab")

        # 等待页面加载完成
        await page.wait_for_load_state("networkidle", timeout=10000)
        logger.info("✓ 页面加载完成")
    except Exception as e:
        logger.warning(f"切换tab失败: {e}")

    # 选择创建人员:柯诗俊(keshijun123)
    logger.info("正在筛选创建人员...")
    try:
        # 查找"创建人员"下拉框
        creator_input = await page.locator(
            "input[placeholder*='创建人员'], input[placeholder*='全部']"
        ).count()
        if creator_input > 0:
            logger.info("找到创建人员筛选项")
            # 点击下拉框
            await page.locator(
                "input[placeholder*='创建人员'], input[placeholder*='全部']"
            ).first.click()
            await asyncio.sleep(0.5)  # 0.5秒
            # 输入搜索
            await page.keyboard.type("柯诗俊")
            await asyncio.sleep(0.5)  # 0.5秒
            # 选择结果(查找包含"柯诗俊"的选项)
            keshijun_option = await page.locator("text='柯诗俊'").count()
            if keshijun_option > 0:
                await page.locator("text='柯诗俊'").first.click()
                await asyncio.sleep(0.3)  # 0.3秒
                logger.success("✓ 已选择创建人员:柯诗俊")
            else:
                logger.warning("未找到「柯诗俊」选项,尝试直接搜索")

        # 点击搜索按钮
        search_btn = await page.locator("button:has-text('搜索')").count()
        if search_btn > 0:
            await page.locator("button:has-text('搜索')").first.click()
            logger.info("✓ 已点击搜索按钮")
            await asyncio.sleep(2)  # 2秒,等待搜索结果加载

            # 等待搜索结果加载完成
            await page.wait_for_load_state("networkidle", timeout=10000)
            logger.success("✓ 搜索结果已加载")
    except Exception as e:
        logger.warning(f"选择创建人员失败(可能不需要): {e}")

    # 移除了重复的切换到"全部"tab代码,因为已经在前面完成

    # 检查产品
    logger.info("正在检查产品...")
    counts = await miaoshou_controller.get_product_count(page)
    logger.info(f"产品统计: {counts}")

    total = counts.get("claimed", 0) + counts.get("unclaimed", 0)
    if total == 0:
        logger.warning("\n⚠️ 采集箱中暂无产品")
        logger.info("\n请按以下步骤手动采集测试产品:")
        logger.info("1. 在当前浏览器窗口,点击顶部菜单「产品」->「产品采集」")
        logger.info("2. 或直接访问:https://erp.91miaoshou.com/common_collect_box/index")
        logger.info("3. 粘贴商品链接(1688/淘宝),选择平台,点击「采集并自动认领」")
        logger.info("\n程序会等待2分钟,供您完成采集...")
        await asyncio.sleep(120)

        # 重新检查
        await page.goto("https://erp.91miaoshou.com/common_collect_box/items")
        await asyncio.sleep(2)

        # 重新选择创建人员和切换到全部tab
        try:
            await page.locator("input[placeholder*='创建人员']").first.click()
            await asyncio.sleep(0.5)
            await page.keyboard.type("柯诗俊")
            await asyncio.sleep(0.5)
            await page.locator("text='柯诗俊'").first.click()
            await asyncio.sleep(0.3)
            await page.locator("button:has-text('搜索')").first.click()
            await asyncio.sleep(2)
            await page.locator("text=/全部.*\\(\\d+\\)/").click()
            await asyncio.sleep(1)
        except Exception:
            pass

        counts = await miaoshou_controller.get_product_count(page)
        total = counts.get("claimed", 0) + counts.get("unclaimed", 0)

        if total == 0:
            logger.error("仍然没有产品,测试终止")
            return False

    # 不需要切换tab了,已经在"全部"tab
    logger.info("准备编辑产品...")
    await asyncio.sleep(0.5)  # 0.5秒

    # 打开编辑弹窗
    logger.info("正在打开编辑弹窗...")
    success = await miaoshou_controller.click_edit_first_product(page)
    if not success:
        logger.error("无法打开编辑弹窗")
        return False

    await asyncio.sleep(1)  # 1秒

    # 生成测试数据
    cost = 10.0
    price_calc = PriceCalculator()
    # 使用PriceResult的静态方法计算价格
    price_result = PriceResult.calculate(
        cost, price_calc.suggested_multiplier, price_calc.supply_multiplier
    )

    title_gen = TitleGenerator()
    titles = title_gen.generate_with_model_suffix(
        ["自动化测试商品"],
        model_prefix="AUTO",
        start_number=random.randint(1, 9999),
        add_modifiers=True,
    )

    test_data = {
        "title": titles[0],
        "price": price_result.suggested_price,
        "stock": 99,
        "weight": round(random.uniform(0.3, 0.8), 2),
        "dimensions": (random.randint(20, 40), random.randint(20, 40), random.randint(10, 30)),
    }

    logger.info("\n测试数据:")
    logger.info(f"  标题: {test_data['title']}")
    logger.info(f"  价格: {test_data['price']} CNY")
    logger.info(f"  库存: {test_data['stock']}")
    logger.info(f"  重量: {test_data['weight']} KG")
    logger.info(
        f"  尺寸: {test_data['dimensions'][0]}x{test_data['dimensions'][1]}x{test_data['dimensions'][2]} CM\n"
    )

    # 执行编辑
    logger.info("开始执行编辑流程...")
    first_edit_controller = FirstEditController()

    success = await first_edit_controller.complete_first_edit(
        page=page,
        title=test_data["title"],
        price=test_data["price"],
        stock=test_data["stock"],
        weight=test_data["weight"],
        dimensions=test_data["dimensions"],
    )

    if success:
        logger.success("\n🎉 编辑流程测试通过!")
        await asyncio.sleep(5)
        return True
    else:
        logger.error("\n❌ 编辑流程测试失败")
        await asyncio.sleep(10)
        return False


async def main():
    try:
        await quick_test()
    except Exception as e:
        logger.error(f"错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
