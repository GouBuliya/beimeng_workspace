"""测试控制器模块（集成测试框架）.

此脚本用于测试所有新创建的控制器：
- MiaoshouController
- FirstEditController
- BatchEditController

注意：需要先使用 playwright codegen 获取实际的选择器。
"""

import asyncio
from pathlib import Path

from loguru import logger
from playwright.async_api import async_playwright

# 配置日志
logger.add(
    "data/logs/test_controllers_{time}.log",
    rotation="1 MB",
    retention="7 days",
    level="DEBUG",
)


async def test_miaoshou_controller():
    """测试妙手控制器."""
    logger.info("=" * 60)
    logger.info("测试妙手控制器（MiaoshouController）")
    logger.info("=" * 60)

    from src.browser.miaoshou_controller import MiaoshouController

    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()

        # 初始化控制器
        ctrl = MiaoshouController()

        try:
            # 测试1：访问前端店铺
            logger.info("\n测试1：访问前端店铺")
            result = await ctrl.navigate_to_store_front(page)
            logger.info(f"结果: {'✓ 成功' if result else '✗ 失败'}")

            # 等待用户观察
            await asyncio.sleep(3)

            # 测试2：进入采集箱
            logger.info("\n测试2：进入采集箱")
            result = await ctrl.navigate_to_collection_box(page)
            logger.info(f"结果: {'✓ 成功' if result else '✗ 失败'}")

            # 等待用户观察
            await asyncio.sleep(3)

            # 测试3：验证采集箱
            logger.info("\n测试3：验证采集箱")
            result = await ctrl.verify_collection_box(page)
            logger.info(f"结果: {'✓ 成功' if result else '✗ 失败'}")

            # 测试4：认领链接（模拟）
            logger.info("\n测试4：认领链接（模拟，link_count=2, claim_times=2）")
            result = await ctrl.claim_links(page, link_count=2, claim_times=2)
            logger.info(f"结果: {'✓ 成功' if result else '✗ 失败'}")

            # 测试5：验证认领结果
            logger.info("\n测试5：验证认领结果（预期4条）")
            result = await ctrl.verify_claims(page, expected_count=4)
            logger.info(f"结果: {'✓ 成功' if result else '✗ 失败'}")

        except Exception as e:
            logger.error(f"测试失败: {e}")
            await page.screenshot(path="data/temp/test_miaoshou_error.png")

        finally:
            logger.info("\n等待5秒后关闭浏览器...")
            await asyncio.sleep(5)
            await browser.close()

    logger.success("妙手控制器测试完成")


async def test_first_edit_controller():
    """测试首次编辑控制器."""
    logger.info("=" * 60)
    logger.info("测试首次编辑控制器（FirstEditController）")
    logger.info("=" * 60)

    from src.browser.first_edit_controller import FirstEditController

    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()

        # 初始化控制器
        ctrl = FirstEditController()

        # 准备测试数据
        product_data = {
            "title_cn": "智能手表 2025新款 A0001型号",
            "title_en": "Smart Watch 2025 New Model A0001",
            "cost": 150.0,
            "category": "智能穿戴",
            "main_images": [
                "data/temp/test_img1.jpg",
                "data/temp/test_img2.jpg",
            ],
            "detail_images": [
                "data/temp/detail1.jpg",
                "data/temp/detail2.jpg",
            ],
        }

        try:
            # 测试完整流程
            logger.info("\n测试：首次编辑完整流程")
            result = await ctrl.edit_product(page, product_data, link_index=1)
            logger.info(f"结果: {'✓ 成功' if result else '✗ 失败'}")

        except Exception as e:
            logger.error(f"测试失败: {e}")
            await page.screenshot(path="data/temp/test_first_edit_error.png")

        finally:
            logger.info("\n等待5秒后关闭浏览器...")
            await asyncio.sleep(5)
            await browser.close()

    logger.success("首次编辑控制器测试完成")


async def test_batch_edit_controller():
    """测试批量编辑控制器."""
    logger.info("=" * 60)
    logger.info("测试批量编辑控制器（BatchEditController）")
    logger.info("=" * 60)

    from src.browser.batch_edit_controller import BatchEditController

    async with async_playwright() as p:
        # 启动浏览器
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        page = await browser.new_page()

        # 初始化控制器
        ctrl = BatchEditController()

        # 准备测试数据（20条）
        products_data = [
            {
                "cost": 150.0 + i * 10,
                "title_en": f"Smart Watch A{i:04d}",
            }
            for i in range(1, 21)
        ]

        try:
            # 测试完整流程
            logger.info("\n测试：批量编辑完整流程（20条商品）")
            result = await ctrl.batch_edit(page, products_data)
            logger.info(f"结果: {'✓ 成功' if result else '✗ 失败'}")

        except Exception as e:
            logger.error(f"测试失败: {e}")
            await page.screenshot(path="data/temp/test_batch_edit_error.png")

        finally:
            logger.info("\n等待5秒后关闭浏览器...")
            await asyncio.sleep(5)
            await browser.close()

    logger.success("批量编辑控制器测试完成")


async def test_all_controllers():
    """测试所有控制器."""
    logger.info("=" * 60)
    logger.info("开始测试所有控制器")
    logger.info("=" * 60)

    try:
        # 测试1：妙手控制器
        await test_miaoshou_controller()
        await asyncio.sleep(2)

        # 测试2：首次编辑控制器
        await test_first_edit_controller()
        await asyncio.sleep(2)

        # 测试3：批量编辑控制器
        await test_batch_edit_controller()

        logger.success("\n所有测试完成！")

    except Exception as e:
        logger.error(f"测试过程出错: {e}")


def main():
    """主函数."""
    print("=" * 60)
    print("控制器集成测试")
    print("=" * 60)
    print()
    print("⚠️  注意：")
    print("1. 需要先使用 playwright codegen 获取实际选择器")
    print("2. 更新 config/miaoshou_selectors.json")
    print("3. 需要登录 Temu 商家后台")
    print("4. 测试过程中不要实际保存/发布商品")
    print()
    print("测试模式：")
    print("1. 测试妙手控制器")
    print("2. 测试首次编辑控制器")
    print("3. 测试批量编辑控制器")
    print("4. 测试所有控制器")
    print("0. 退出")
    print()

    choice = input("请选择测试模式 (1-4): ").strip()

    if choice == "1":
        asyncio.run(test_miaoshou_controller())
    elif choice == "2":
        asyncio.run(test_first_edit_controller())
    elif choice == "3":
        asyncio.run(test_batch_edit_controller())
    elif choice == "4":
        asyncio.run(test_all_controllers())
    elif choice == "0":
        print("退出测试")
    else:
        print("无效选择")


if __name__ == "__main__":
    main()

