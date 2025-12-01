"""
测试批量编辑18步完整流程（集成Excel数据）

运行方式:
    uv run python scripts/test_batch_edit_with_excel.py
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
workspace_root = project_root.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(workspace_root))

# 先导入logger（在加载环境变量前）
from packages.common.logger import logger

# 加载环境变量（优先从项目根目录，其次从workspace根目录）
env_paths = [
    project_root / ".env",  # apps/temu-auto-publish/.env
    workspace_root / ".env",  # beimeng_workspace/.env
]

env_loaded = False
for env_path in env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"✓ 已加载环境变量: {env_path}")
        env_loaded = True
        break

if not env_loaded:
    logger.warning(f"⚠️ 环境变量文件不存在，尝试过的路径: {[str(p) for p in env_paths]}")

from src.browser.login_controller import LoginController
from src.browser.batch_edit_controller_v2 import BatchEditController
from src.data_processor.product_data_reader import ProductDataReader


async def test_batch_edit_with_excel(product_name: str = None, manual_pdf_path: str = None):
    """
    测试批量编辑18步流程（集成Excel数据）

    Args:
        product_name: 产品名称，用于从Excel读取数据
        manual_pdf_path: 产品说明书PDF文件路径（可选）
    """
    # 获取登录凭据
    username = os.getenv("MIAOSHOU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD")

    if not username or not password:
        logger.error("❌ 请在 .env 文件中配置 MIAOSHOU_USERNAME 和 MIAOSHOU_PASSWORD")
        return

    logger.info("=" * 80)
    logger.info("🎯 测试批量编辑18步流程（集成Excel数据）")
    logger.info("=" * 80)

    if product_name:
        logger.info(f"📦 产品名称: {product_name}")
    if manual_pdf_path:
        logger.info(f"📄 说明书: {manual_pdf_path}")

    # 初始化Excel数据读取器
    reader = ProductDataReader()
    logger.info(f"📊 Excel数据: 已加载 {len(reader.data_cache)} 个产品")

    login_controller = None

    try:
        # ========================================
        # 第1步：登录
        # ========================================
        logger.info("\n" + "=" * 60)
        logger.info("第1步：登录")
        logger.info("=" * 60)

        login_controller = LoginController()
        login_success = await login_controller.login(username, password)

        if not login_success:
            logger.error("❌ 登录失败")
            return

        logger.success("✅ 登录成功")

        # 获取page对象
        page = login_controller.browser_manager.page
        await page.wait_for_timeout(3000)

        # ========================================
        # 第2步：进入批量编辑
        # ========================================
        logger.info("\n" + "=" * 60)
        logger.info("第2步：进入批量编辑")
        logger.info("=" * 60)

        batch_controller = BatchEditController(page)
        nav_success = await batch_controller.navigate_to_batch_edit()

        if not nav_success:
            logger.error("❌ 进入批量编辑失败")
            return

        logger.success("✅ 已进入批量编辑页面")
        await page.wait_for_timeout(5000)

        # ========================================
        # 第3步：执行18步批量编辑
        # ========================================
        logger.info("\n" + "=" * 60)
        logger.info("第3步：执行18步批量编辑")
        logger.info("=" * 60)

        results = {"total": 18, "success": 0, "failed": 0, "steps": []}

        # 定义18个步骤
        steps = [
            ("7.1", "标题", lambda: batch_controller.step_01_title()),
            ("7.2", "英语标题", lambda: batch_controller.step_02_english_title()),
            ("7.3", "类目属性", lambda: batch_controller.step_03_category_attrs()),
            ("7.4", "主货号", lambda: batch_controller.step_04_main_sku()),
            ("7.5", "外包装", lambda: batch_controller.step_05_packaging()),
            ("7.6", "产地", lambda: batch_controller.step_06_origin()),
            ("7.7", "定制品", lambda: batch_controller.step_07_customization()),
            ("7.8", "敏感属性", lambda: batch_controller.step_08_sensitive_attrs()),
            ("7.9", "重量", lambda: batch_controller.step_09_weight(product_name=product_name)),
            (
                "7.10",
                "尺寸",
                lambda: batch_controller.step_10_dimensions(product_name=product_name),
            ),
            ("7.11", "平台SKU", lambda: batch_controller.step_11_platform_sku()),
            ("7.12", "SKU分类", lambda: batch_controller.step_12_sku_category()),
            ("7.13", "尺码表", lambda: batch_controller.step_13_size_chart()),
            (
                "7.14",
                "建议售价",
                lambda: batch_controller.step_14_suggested_price(product_name=product_name),
            ),
            ("7.15", "包装清单", lambda: batch_controller.step_15_package_list()),
            ("7.16", "轮播图", lambda: batch_controller.step_16_carousel_images()),
            ("7.17", "颜色图", lambda: batch_controller.step_17_color_images()),
            (
                "7.18",
                "产品说明书",
                lambda: batch_controller.step_18_manual(manual_file_path=manual_pdf_path),
            ),
        ]

        for step_num, step_name, step_func in steps:
            logger.info(f"\n{'─' * 60}")
            logger.info(f"🔄 执行步骤 {step_num}：{step_name}")
            logger.info(f"{'─' * 60}")

            try:
                success = await step_func()

                if success:
                    logger.success(f"✅ 步骤 {step_num} {step_name} 成功")
                    results["success"] += 1
                    results["steps"].append(
                        {"step": step_num, "name": step_name, "status": "success"}
                    )
                else:
                    logger.error(f"❌ 步骤 {step_num} {step_name} 失败")
                    results["failed"] += 1
                    results["steps"].append(
                        {"step": step_num, "name": step_name, "status": "failed"}
                    )

                    # 失败后是否继续？
                    # 这里选择继续执行后续步骤
                    logger.warning(f"⚠️ 继续执行下一步...")

            except Exception as e:
                logger.error(f"❌ 步骤 {step_num} {step_name} 异常: {e}")
                results["failed"] += 1
                results["steps"].append(
                    {"step": step_num, "name": step_name, "status": "error", "error": str(e)}
                )

            # 每步之间短暂等待
            await page.wait_for_timeout(1000)

        # ========================================
        # 第4步：输出测试报告
        # ========================================
        logger.info("\n" + "=" * 80)
        logger.info("📊 测试报告")
        logger.info("=" * 80)

        logger.info(f"总步数: {results['total']}")
        logger.info(f"成功: {results['success']} ✅")
        logger.info(f"失败: {results['failed']} ❌")
        logger.info(f"成功率: {results['success'] / results['total'] * 100:.1f}%")

        logger.info("\n详细结果:")
        for step_result in results["steps"]:
            status_emoji = "✅" if step_result["status"] == "success" else "❌"
            logger.info(
                f"  {status_emoji} {step_result['step']} {step_result['name']}: {step_result['status']}"
            )
            if step_result.get("error"):
                logger.info(f"      错误: {step_result['error']}")

        if results["failed"] == 0:
            logger.success("\n🎉 所有18步均执行成功！")
        else:
            logger.warning(f"\n⚠️ 有 {results['failed']} 步执行失败，请检查日志")

        # 等待一会儿以便观察结果
        logger.info("\n等待10秒后关闭浏览器...")
        await page.wait_for_timeout(10000)

    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户中断测试")
    except Exception as e:
        logger.error(f"❌ 测试过程中出错: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if login_controller and login_controller.browser_manager:
            await login_controller.browser_manager.close()
            logger.info("✅ 浏览器已关闭")


if __name__ == "__main__":
    # 可以指定产品名称和说明书文件
    # product_name = "卫生间收纳柜"
    # manual_pdf_path = "/path/to/manual.pdf"

    # 或者使用默认值（无产品名称，无说明书）
    asyncio.run(test_batch_edit_with_excel(product_name=None, manual_pdf_path=None))
