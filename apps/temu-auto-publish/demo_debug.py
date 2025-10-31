#!/usr/bin/env python3
"""演示调试功能的使用."""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController
from src.utils.debug_helper import DebugHelper, DebugConfig


async def demo_debug_features():
    """演示各种调试功能."""
    
    # 加载环境变量
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    username = os.getenv("MIAOSHOU_USERNAME") or os.getenv("TEMU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD") or os.getenv("TEMU_PASSWORD")
    
    if not username or not password:
        logger.error("❌ 未找到登录凭证")
        return
    
    logger.info("=" * 80)
    logger.info("调试功能演示")
    logger.info("=" * 80)
    
    # 1. 创建调试助手（启用所有功能）
    debug_config = DebugConfig(
        enabled=True,
        auto_screenshot=True,
        auto_save_html=True,
        enable_timing=True,
        enable_breakpoint=False,  # 断点模式需要手动交互
        screenshot_format="png"
    )
    debug = DebugHelper(debug_config)
    
    login_ctrl = LoginController()
    
    try:
        # 2. 启动浏览器
        logger.info("\n[步骤1] 启动浏览器...")
        debug.start_timer("browser_start")
        await login_ctrl.browser_manager.start()
        page = login_ctrl.browser_manager.page
        debug.end_timer("browser_start")
        
        # 3. 截图：登录页
        await debug.save_state(page, "01_login_page")
        
        # 4. 登录
        logger.info("\n[步骤2] 登录...")
        debug.start_timer("login")
        await login_ctrl.login(username, password)
        debug.end_timer("login")
        
        # 5. 截图：登录后
        await debug.save_state(page, "02_after_login")
        
        # 6. 导航到采集箱
        logger.info("\n[步骤3] 导航到采集箱...")
        debug.start_timer("navigate_to_collection_box")
        miaoshou_ctrl = MiaoshouController()
        await miaoshou_ctrl.navigate_to_collection_box(page)
        debug.end_timer("navigate_to_collection_box")
        
        # 7. 截图：采集箱页面
        await debug.save_state(page, "03_collection_box", full_page=True)
        
        # 8. 切换tab
        logger.info("\n[步骤4] 切换到全部tab...")
        debug.start_timer("switch_tab")
        await miaoshou_ctrl.switch_tab(page, "all")
        debug.end_timer("switch_tab")
        
        # 9. 截图：切换tab后
        await debug.screenshot(page, "04_after_tab_switch")
        
        # 10. 模拟错误场景
        logger.info("\n[步骤5] 模拟错误场景...")
        try:
            # 故意触发一个错误
            await page.locator("non_existent_element").click(timeout=2000)
        except Exception as e:
            # 保存错误状态
            await debug.save_error_state(page, "click_failed", e)
        
        # 11. 断点（如果启用）
        # await debug.breakpoint(page, "检查采集箱页面", auto_continue=True)
        
        # 12. 显示性能摘要
        logger.info("\n[步骤6] 性能分析...")
        debug.log_performance_summary()
        
        logger.info("\n" + "=" * 80)
        logger.success("🎉 调试功能演示完成！")
        logger.info("=" * 80)
        logger.info(f"\n调试文件已保存到: {debug.config.debug_dir}")
        logger.info("包含:")
        logger.info(f"  - {debug.screenshot_count} 张截图")
        logger.info(f"  - {debug.html_count} 个HTML文件")
        logger.info("")
        logger.info("浏览器将在10秒后关闭...")
        await asyncio.sleep(10)
        
    except KeyboardInterrupt:
        logger.info("\n\n用户中断")
    except Exception as e:
        logger.error(f"演示过程中发生错误: {e}")
        # 保存错误状态
        try:
            await debug.save_error_state(page, "demo_error", e)
        except:
            pass
        import traceback
        traceback.print_exc()
    finally:
        try:
            await login_ctrl.browser_manager.close()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(demo_debug_features())

