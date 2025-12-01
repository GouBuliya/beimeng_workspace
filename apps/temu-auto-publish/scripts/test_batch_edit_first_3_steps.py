"""
@PURPOSE: 测试批量编辑前3个步骤(验证预览→保存流程)
@OUTLINE:
  - 快速验证脚本,只测试前3步
  - 验证每步都正确执行"点击预览→点击保存"
  - 用于快速调试和验证
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(project_root / ".env")

from src.browser.batch_edit_controller_v2 import BatchEditController
from src.browser.login_controller import LoginController

from packages.common.logger import logger


async def main():
    """测试批量编辑的前3个步骤."""
    logger.info("=" * 80)
    logger.info("🧪 测试批量编辑前3步(标题,英语标题,类目属性)")
    logger.info("=" * 80)

    login_controller = None

    try:
        # 1. 登录
        logger.info("\n" + "=" * 80)
        logger.info("📋 阶段1:登录妙手ERP")
        logger.info("=" * 80)

        # 从环境变量获取登录信息
        username = os.getenv("MIAOSHOU_USERNAME")
        password = os.getenv("MIAOSHOU_PASSWORD")

        if not username or not password:
            logger.error(
                "❌ 未找到登录凭据,请设置 MIAOSHOU_USERNAME 和 MIAOSHOU_PASSWORD 环境变量"
            )
            return

        login_controller = LoginController()
        login_result = await login_controller.login(username, password)

        if not login_result:
            logger.error("❌ 登录失败")
            return

        logger.success("✅ 登录成功")

        # 获取page对象
        page = login_controller.browser_manager.page

        # 2. 导航到批量编辑并选择产品
        logger.info("\n" + "=" * 80)
        logger.info("📋 阶段2:导航到批量编辑")
        logger.info("=" * 80)
        batch_controller = BatchEditController(page)

        if not await batch_controller.navigate_to_batch_edit(select_count=20):
            logger.error("❌ 无法进入批量编辑页面")
            return

        logger.success("✅ 已进入批量编辑页面")

        # 3. 执行前3个步骤
        logger.info("\n" + "=" * 80)
        logger.info("📋 阶段3:执行前3个步骤")
        logger.info("=" * 80)

        steps_to_test = [
            ("step_01_title", "7.1 标题"),
            ("step_02_english_title", "7.2 英语标题"),
            ("step_03_category_attrs", "7.3 类目属性"),
        ]

        results = {}

        for method_name, step_label in steps_to_test:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"🧪 测试步骤:{step_label}")
            logger.info(f"{'=' * 60}")

            try:
                method = getattr(batch_controller, method_name)
                result = await method()
                results[step_label] = result

                if result:
                    logger.success(f"✅ [{step_label}] 执行成功")
                else:
                    logger.error(f"❌ [{step_label}] 执行失败")

                # 每步之间额外等待
                await page.wait_for_timeout(2000)

            except Exception as e:
                logger.error(f"❌ [{step_label}] 执行异常: {e}")
                results[step_label] = False

        # 5. 汇总结果
        logger.info("\n" + "=" * 80)
        logger.info("📊 测试结果汇总")
        logger.info("=" * 80)

        total = len(results)
        success = sum(1 for r in results.values() if r)

        for step_label, result in results.items():
            status = "✅ 成功" if result else "❌ 失败"
            logger.info(f"  {step_label}: {status}")

        logger.info(f"\n总计:{success}/{total} 步成功")

        if success == total:
            logger.success("\n🎉 所有测试步骤都成功!预览→保存流程工作正常")
        else:
            logger.warning("\n⚠️ 部分步骤失败,请检查日志")

        # 等待查看结果
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
    asyncio.run(main())
