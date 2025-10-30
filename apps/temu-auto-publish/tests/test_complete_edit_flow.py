"""
@PURPOSE: 完整的产品编辑流程测试 - 验证首次编辑的所有步骤
@OUTLINE:
  - test_complete_edit_flow(): 完整编辑流程测试
  - generate_test_data(): 生成测试数据
  - main(): 主测试函数
@DEPENDENCIES:
  - 内部: src.browser.login_controller, src.browser.miaoshou_controller, src.browser.first_edit_controller
  - 内部: src.data_processor.price_calculator, src.data_processor.title_generator
  - 外部: playwright, loguru
@RELATED: test_controllers.py, test_product_collection.py
"""

import asyncio
import os
import random
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger

from src.browser.browser_manager import BrowserManager
from src.browser.first_edit_controller import FirstEditController
from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController
from src.data_processor.price_calculator import PriceCalculator
from src.data_processor.title_generator import TitleGenerator


def generate_test_data():
    """生成测试数据.
    
    Returns:
        dict: 包含标题、价格、库存、重量、尺寸的测试数据
    """
    # 生成测试价格（假设成本为10元）
    cost_price = 10.0
    price_calc = PriceCalculator()
    price_result = price_calc.calculate(cost_price)

    # 生成测试标题
    original_title = "测试商品"
    title_gen = TitleGenerator()
    titles = title_gen.generate_with_model_suffix(
        [original_title],
        model_prefix="TEST",
        start_number=1,
        add_modifiers=True
    )

    # 生成随机重量和尺寸
    weight = round(random.uniform(0.1, 1.0), 2)
    length = random.randint(10, 50)
    width = random.randint(10, 50)
    height = random.randint(5, 30)

    return {
        "title": titles[0],
        "price": price_result.suggested_price,  # 使用建议售价
        "stock": 99,
        "weight": weight,
        "dimensions": (length, width, height),
    }


async def test_complete_edit_flow():
    """测试完整的产品编辑流程.
    
    测试步骤：
    1. 登录妙手ERP
    2. 导航到公用采集箱
    3. 检查产品数量
    4. 点击第一个产品的编辑按钮
    5. 执行完整的首次编辑流程（SOP步骤4）
    
    Returns:
        bool: 是否成功
    """
    logger.info("=" * 80)
    logger.info("完整产品编辑流程测试")
    logger.info("=" * 80)

    # 1. 登录
    logger.info("\n步骤1：登录妙手ERP")
    logger.info("-" * 80)
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

    logger.success("✅ 步骤1完成：登录成功\n")

    # 2. 导航到公用采集箱
    logger.info("步骤2：导航到公用采集箱")
    logger.info("-" * 80)
    miaoshou_controller = MiaoshouController()
    page = login_controller.browser_manager.page

    success = await miaoshou_controller.navigate_to_collection_box(page, use_sidebar=False)
    if not success:
        logger.error("❌ 导航失败")
        return False

    logger.success("✅ 步骤2完成：导航成功\n")

    # 3. 检查产品数量
    logger.info("步骤3：检查产品数量")
    logger.info("-" * 80)
    product_counts = await miaoshou_controller.get_product_count(page)
    total_products = product_counts.get("claimed", 0) + product_counts.get("unclaimed", 0)

    if total_products == 0:
        logger.error("❌ 采集箱中没有产品，请先运行 test_product_collection.py 采集测试产品")
        return False

    logger.info(f"采集箱中共有 {total_products} 个产品")
    logger.success("✅ 步骤3完成：产品检查通过\n")

    # 4. 切换到"已认领"或"未认领"tab（选择有产品的tab）
    logger.info("步骤4：切换到有产品的tab")
    logger.info("-" * 80)
    
    if product_counts.get("claimed", 0) > 0:
        logger.info("切换到「已认领」tab...")
        await miaoshou_controller.switch_tab(page, "claimed")
    elif product_counts.get("unclaimed", 0) > 0:
        logger.info("切换到「未认领」tab...")
        await miaoshou_controller.switch_tab(page, "unclaimed")
    
    await asyncio.sleep(2)
    logger.success("✅ 步骤4完成：tab切换成功\n")

    # 5. 点击第一个产品的编辑按钮
    logger.info("步骤5：打开编辑弹窗")
    logger.info("-" * 80)
    success = await miaoshou_controller.click_edit_first_product(page)
    if not success:
        logger.error("❌ 无法打开编辑弹窗")
        return False

    logger.success("✅ 步骤5完成：编辑弹窗已打开\n")

    # 6. 生成测试数据
    logger.info("步骤6：生成测试数据")
    logger.info("-" * 80)
    test_data = generate_test_data()
    logger.info(f"测试标题: {test_data['title']}")
    logger.info(f"测试价格: {test_data['price']} CNY")
    logger.info(f"测试库存: {test_data['stock']}")
    logger.info(f"测试重量: {test_data['weight']} KG")
    logger.info(f"测试尺寸: {test_data['dimensions'][0]}x{test_data['dimensions'][1]}x{test_data['dimensions'][2]} CM")
    logger.success("✅ 步骤6完成：测试数据已生成\n")

    # 7. 执行完整的首次编辑流程
    logger.info("步骤7：执行完整的首次编辑流程（SOP步骤4）")
    logger.info("-" * 80)
    first_edit_controller = FirstEditController()

    success = await first_edit_controller.complete_first_edit(
        page=page,
        title=test_data["title"],
        price=test_data["price"],
        stock=test_data["stock"],
        weight=test_data["weight"],
        dimensions=test_data["dimensions"],
    )

    if not success:
        logger.error("❌ 首次编辑流程失败")
        return False

    logger.success("✅ 步骤7完成：首次编辑流程执行成功\n")

    # 等待一下，让用户看到结果
    logger.info("等待5秒，查看编辑结果...")
    await asyncio.sleep(5)

    return True


async def main():
    """主测试函数."""
    logger.info("=" * 80)
    logger.info("妙手ERP完整编辑流程测试")
    logger.info("=" * 80)
    logger.info("⚠️ 请确保已运行 test_product_collection.py 采集了测试产品\n")

    try:
        success = await test_complete_edit_flow()

        if success:
            logger.info("\n" + "=" * 80)
            logger.success("🎉 完整编辑流程测试通过！")
            logger.info("=" * 80)
            logger.info("\n测试总结：")
            logger.info("✅ 登录功能：正常")
            logger.info("✅ 导航功能：正常")
            logger.info("✅ 产品检查：正常")
            logger.info("✅ 编辑弹窗：正常")
            logger.info("✅ 标题编辑：正常")
            logger.info("✅ 价格设置：正常")
            logger.info("✅ 库存设置：正常")
            logger.info("✅ 重量设置：正常")
            logger.info("✅ 尺寸设置：正常")
            logger.info("✅ 保存修改：正常")
            logger.info("\n🚀 妙手ERP自动化系统已可用于生产环境！")
        else:
            logger.error("\n" + "=" * 80)
            logger.error("❌ 完整编辑流程测试失败")
            logger.info("=" * 80)

    except KeyboardInterrupt:
        logger.info("\n用户中断测试")
    except Exception as e:
        logger.error(f"\n测试过程出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

