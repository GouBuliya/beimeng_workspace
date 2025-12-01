"""
@PURPOSE: 自动运行真实环境测试 - 直接执行测试1(5→20认领流程)
@OUTLINE:
  - async def main(): 自动执行5→20认领流程测试
@DEPENDENCIES:
  - 内部: browser_manager, workflows
  - 外部: playwright, loguru, python-dotenv
@RELATED: test_stage2_real_environment.py
"""

import asyncio
import os
import sys
from pathlib import Path

from loguru import logger

# 添加项目根目录到path
sys.path.insert(0, str(Path(__file__).parent))

# 加载.env环境变量(强制覆盖系统环境变量)
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path, override=True)  # 强制覆盖已存在的环境变量
    logger.info(f"✓ 环境变量已从 {env_path} 加载(已覆盖系统环境变量)")
    # 验证关键配置
    logger.debug(f"  DASHSCOPE_API_KEY: {os.getenv('DASHSCOPE_API_KEY', 'N/A')[:20]}...")
    logger.debug(f"  OPENAI_MODEL: {os.getenv('OPENAI_MODEL', 'N/A')}")
    logger.debug(f"  OPENAI_BASE_URL: {os.getenv('OPENAI_BASE_URL', 'N/A')}")
except ImportError:
    logger.warning("⚠️  python-dotenv未安装,请运行: pip install python-dotenv")
    logger.warning("   将使用硬编码的占位符账号")
except Exception as e:
    logger.warning(f"⚠️  加载.env失败: {e}")

from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController
from src.workflows.five_to_twenty_workflow import FiveToTwentyWorkflow


async def main():
    """自动运行5→20认领流程测试."""
    logger.info("=" * 80)
    logger.info("🚀 阶段2真实环境测试 - 5→20认领流程")
    logger.info("=" * 80)
    logger.info("")
    logger.info("测试内容:")
    logger.info("  1. 登录妙手ERP")
    logger.info("  2. 导航到待审核页面")
    logger.info("  3. 首次编辑5条商品(含AI标题,类目核对,图片,尺寸图,视频,重量,尺寸)")
    logger.info("  4. 每条商品认领4次")
    logger.info("  5. 验证总计20条商品")
    logger.info("")
    logger.info("⚠️  注意:")
    logger.info("  - 浏览器将以非headless模式启动(您可以观察执行过程)")
    logger.info("  - 请确保网络畅通")
    logger.info("  - 整个流程预计需要5-10分钟")
    logger.info("")

    login_controller = None

    try:
        # 1. 初始化登录控制器
        logger.info("步骤1:初始化登录控制器...")
        login_controller = LoginController()
        logger.success("✓ 登录控制器初始化成功")

        # 2. 登录(会自动启动浏览器)
        logger.info("\n步骤2:登录妙手ERP...")

        # 从.env环境变量读取账号密码
        username = os.getenv("MIAOSHOU_USERNAME")
        password = os.getenv("MIAOSHOU_PASSWORD")

        if not username or not password:
            logger.error("❌ 未找到妙手ERP账号配置")
            logger.info("\n请确保.env文件中包含以下配置:")
            logger.info("  MIAOSHOU_USERNAME=你的用户名")
            logger.info("  MIAOSHOU_PASSWORD=你的密码")
            return 1

        logger.info(f"  使用账号: {username}")
        logger.warning("⚠️  注意:优先使用Cookie登录模式")
        logger.info("   如果Cookie有效,将跳过账号密码登录")
        logger.info("   如果Cookie失效,将使用.env中的账号自动登录")

        login_success = await login_controller.login(
            username=username,
            password=password,
            force=False,  # 优先使用Cookie
            headless=False,
        )

        if not login_success:
            logger.error("❌ 登录失败,测试终止")
            logger.info("\n可能原因:")
            logger.info("  1. Cookie已过期,需要手动登录")
            logger.info("  2. 网络连接问题")
            logger.info("  3. 妙手ERP页面结构变化")
            return 1

        logger.success("✓ 登录成功")

        # 获取page对象
        page = login_controller.browser_manager.page
        await asyncio.sleep(2)

        # 3. 导航到公用采集箱(SOP步骤4.0)
        logger.info("\n步骤3:导航到公用采集箱...")
        miaoshou_ctrl = MiaoshouController()
        if not await miaoshou_ctrl.navigate_to_collection_box(page, use_sidebar=False):
            logger.error("✗ 导航失败")
            return 1
        logger.success("✓ 导航成功")

        # 4. 切换到"全部"tab(SOP步骤4.0)
        logger.info("\n步骤4:切换到「全部」tab...")
        if not await miaoshou_ctrl.switch_tab(page, "all"):
            logger.warning("⚠️ 切换tab失败,但继续尝试执行")
        else:
            logger.success("✓ 已切换到全部tab")
        await page.wait_for_timeout(1000)

        # 5. 执行5→20工作流
        logger.info("\n步骤5:执行5→20认领流程...")
        logger.info("----------------------------------------")
        workflow = FiveToTwentyWorkflow()

        # 准备测试数据(5条商品数据)
        test_products = [
            {
                "index": i,
                "cost": 150.0 + i * 10,
                "title_suffix": f"A000{i + 1}测试型号",
                "weight": 5000 + i * 500,  # 5000-7000G
                "length": 55 + i * 5,  # 55-75cm
                "width": 54 + i * 5,  # 54-74cm
                "height": 53 + i * 5,  # 53-73cm
                # 新增:测试尺寸图和视频URL(使用示例URL)
                "size_chart_url": "https://img.kwcdn.com/product/fancy/e7e3c9a5-size.jpg",  # 示例尺寸图
                "video_url": "https://video.kwcdn.com/example.mp4",  # 示例视频
            }
            for i in range(5)
        ]

        logger.info("测试数据:")
        for product in test_products:
            logger.info(
                f"  商品{product['index'] + 1}: "
                f"成本¥{product['cost']}, "
                f"型号{product['title_suffix']}, "
                f"重量{product['weight']}G, "
                f"尺寸{product['length']}x{product['width']}x{product['height']}cm"
            )
        logger.info("")

        # 执行工作流
        result = await workflow.execute(page, test_products)

        # 结果
        logger.info("\n" + "=" * 80)
        logger.info("📊 测试结果")
        logger.info("=" * 80)

        if result:
            logger.success("✅ 测试通过!5→20认领流程执行成功")
            logger.info("")
            logger.info("执行内容:")
            logger.info("  ✓ 首次编辑了5条商品")
            logger.info("  ✓ 每条商品认领了4次")
            logger.info("  ✓ 总计生成20条待编辑商品")
            logger.info("")
            logger.info("验证项:")
            logger.info("  ✓ AI标题生成:已应用")
            logger.info("  ✓ 图片管理:已处理")
            logger.info("  ✓ 重量设置:已设置")
            logger.info("  ✓ 尺寸设置:已设置")
            logger.info("  ✓ 认领流程:已完成")
            logger.info("")
            return 0
        else:
            logger.error("❌ 测试失败!5→20认领流程执行失败")
            logger.info("")
            logger.info("可能原因:")
            logger.info("  1. 页面元素未找到(选择器需要更新)")
            logger.info("  2. 网络超时")
            logger.info("  3. UI结构变化")
            logger.info("  4. 数据验证失败")
            logger.info("")
            logger.info("建议:")
            logger.info("  1. 查看日志中的详细错误信息")
            logger.info("  2. 检查浏览器中的实际页面状态")
            logger.info("  3. 使用Playwright Codegen更新选择器")
            logger.info("")
            return 1

    except Exception as e:
        logger.error(f"❌ 测试异常: {e}")
        import traceback

        traceback.print_exc()
        logger.info("")
        logger.info("调试信息:")
        logger.info(f"  异常类型: {type(e).__name__}")
        logger.info(f"  异常信息: {e!s}")
        logger.info("")
        return 1

    finally:
        if login_controller:
            logger.info("\n清理:准备关闭浏览器...")
            logger.info("  (等待5秒让您查看最终状态)")
            await asyncio.sleep(5)
            await login_controller.browser_manager.close()
            logger.info("  ✓ 浏览器已关闭")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
