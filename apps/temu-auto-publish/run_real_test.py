"""
@PURPOSE: 自动运行真实环境测试 - 直接执行测试1（5→20认领流程）
@OUTLINE:
  - async def main(): 自动执行5→20认领流程测试
@DEPENDENCIES:
  - 内部: browser_manager, workflows
  - 外部: playwright, loguru
@RELATED: test_stage2_real_environment.py
"""

import asyncio
import sys
from pathlib import Path

from loguru import logger

# 添加项目根目录到path
sys.path.insert(0, str(Path(__file__).parent))

from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController
from src.workflows.five_to_twenty_workflow import FiveToTwentyWorkflow


async def main():
    """自动运行5→20认领流程测试."""
    logger.info("=" * 80)
    logger.info("🚀 阶段2真实环境测试 - 5→20认领流程")
    logger.info("=" * 80)
    logger.info("")
    logger.info("测试内容：")
    logger.info("  1. 登录妙手ERP")
    logger.info("  2. 导航到待审核页面")
    logger.info("  3. 首次编辑5条商品（含AI标题、图片、重量、尺寸）")
    logger.info("  4. 每条商品认领4次")
    logger.info("  5. 验证总计20条商品")
    logger.info("")
    logger.info("⚠️  注意：")
    logger.info("  - 浏览器将以非headless模式启动（您可以观察执行过程）")
    logger.info("  - 请确保网络畅通")
    logger.info("  - 整个流程预计需要5-10分钟")
    logger.info("")
    
    browser_manager = None
    try:
        # 1. 初始化浏览器
        logger.info("步骤1：初始化浏览器...")
        browser_manager = BrowserManager()
        await browser_manager.start(headless=False)
        page = browser_manager.page
        logger.success("✓ 浏览器初始化成功")
        await asyncio.sleep(1)
        
        # 2. 登录
        logger.info("\n步骤2：登录妙手ERP...")
        login_controller = LoginController()
        login_success = await login_controller.login(page)
        
        if not login_success:
            logger.error("❌ 登录失败，测试终止")
            logger.info("\n可能原因：")
            logger.info("  1. Cookie已过期，需要手动登录")
            logger.info("  2. 网络连接问题")
            logger.info("  3. 妙手ERP页面结构变化")
            return 1
        
        logger.success("✓ 登录成功")
        await asyncio.sleep(2)
        
        # 3. 执行5→20工作流
        logger.info("\n步骤3：执行5→20认领流程...")
        logger.info("----------------------------------------")
        workflow = FiveToTwentyWorkflow()
        
        # 准备测试数据（5条商品数据）
        test_products = [
            {
                "index": i,
                "cost": 150.0 + i * 10,
                "title_suffix": f"A000{i+1}测试型号",
                "weight": 5000 + i * 500,  # 5000-7000G
                "length": 55 + i * 5,       # 55-75cm
                "width": 54 + i * 5,        # 54-74cm
                "height": 53 + i * 5,       # 53-73cm
            }
            for i in range(5)
        ]
        
        logger.info("测试数据：")
        for product in test_products:
            logger.info(
                f"  商品{product['index']+1}: "
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
            logger.success("✅ 测试通过！5→20认领流程执行成功")
            logger.info("")
            logger.info("执行内容：")
            logger.info("  ✓ 首次编辑了5条商品")
            logger.info("  ✓ 每条商品认领了4次")
            logger.info("  ✓ 总计生成20条待编辑商品")
            logger.info("")
            logger.info("验证项：")
            logger.info("  ✓ AI标题生成：已应用")
            logger.info("  ✓ 图片管理：已处理")
            logger.info("  ✓ 重量设置：已设置")
            logger.info("  ✓ 尺寸设置：已设置")
            logger.info("  ✓ 认领流程：已完成")
            logger.info("")
            return 0
        else:
            logger.error("❌ 测试失败！5→20认领流程执行失败")
            logger.info("")
            logger.info("可能原因：")
            logger.info("  1. 页面元素未找到（选择器需要更新）")
            logger.info("  2. 网络超时")
            logger.info("  3. UI结构变化")
            logger.info("  4. 数据验证失败")
            logger.info("")
            logger.info("建议：")
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
        logger.info("调试信息：")
        logger.info(f"  异常类型: {type(e).__name__}")
        logger.info(f"  异常信息: {str(e)}")
        logger.info("")
        return 1
    
    finally:
        if browser_manager:
            logger.info("\n清理：准备关闭浏览器...")
            logger.info("  （等待5秒让您查看最终状态）")
            await asyncio.sleep(5)
            await browser_manager.close()
            logger.info("  ✓ 浏览器已关闭")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

