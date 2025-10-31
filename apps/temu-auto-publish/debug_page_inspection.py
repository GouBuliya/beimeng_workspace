"""
@PURPOSE: 调试脚本 - 暂停浏览器用于检查页面元素
@OUTLINE:
  - async debug_inspect_page(): 打开采集箱页面并暂停，方便手动检查
@DEPENDENCIES:
  - 内部: src.browser.login_controller, src.browser.miaoshou_controller
  - 外部: playwright
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController


async def debug_inspect_page():
    """打开采集箱页面并暂停，用于手动检查页面元素."""
    
    # 加载环境变量
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"✓ 已加载环境变量从: {env_path}")
    
    # 获取登录凭证
    username = os.getenv("MIAOSHOU_USERNAME") or os.getenv("TEMU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD") or os.getenv("TEMU_PASSWORD")
    
    if not username or not password:
        logger.error("❌ 未找到登录凭证，请在 .env 文件中设置")
        return
    
    logger.info("=" * 80)
    logger.info("调试模式：页面元素检查")
    logger.info("=" * 80)
    logger.info("")
    logger.info("浏览器将保持打开状态，您可以：")
    logger.info("  1. 右键点击页面元素 -> 检查")
    logger.info("  2. 查看 Elements 面板中的HTML结构")
    logger.info("  3. 在 Console 面板中测试选择器")
    logger.info("  4. 按 Ctrl+C 退出调试模式")
    logger.info("")
    logger.info("=" * 80)
    
    login_ctrl = LoginController()
    
    try:
        # 启动浏览器
        logger.info("[1/3] 启动浏览器...")
        await login_ctrl.browser_manager.start()
        page = login_ctrl.browser_manager.page
        
        # 登录
        logger.info("[2/3] 登录妙手ERP...")
        await login_ctrl.login(username, password)
        
        # 导航到采集箱
        logger.info("[3/3] 导航到公用采集箱...")
        miaoshou_ctrl = MiaoshouController()
        await miaoshou_ctrl.navigate_to_collection_box(page, use_sidebar=False)
        
        logger.success("")
        logger.success("✅ 页面已打开！")
        logger.success("")
        logger.success("📋 调试任务：")
        logger.success("  1. 检查页面上是否有Tab栏（全部/未认领/已认领/失败）")
        logger.success("  2. 检查Tab的实际文本内容（可能不是'未认领'）")
        logger.success("  3. 检查产品列表是否有产品")
        logger.success("  4. 右键点击Tab元素 -> 检查，查看HTML结构")
        logger.success("")
        logger.success("💡 测试选择器的方法：")
        logger.success("  在浏览器Console中输入：")
        logger.success("    document.querySelectorAll('text=未认领')")
        logger.success("    或")
        logger.success("    $('text=未认领')")
        logger.success("")
        logger.info("按 Ctrl+C 退出...")
        
        # 无限等待，直到用户按Ctrl+C
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\n\n用户中断，关闭浏览器...")
    except Exception as e:
        logger.error(f"发生错误: {e}")
    finally:
        try:
            await login_ctrl.browser_manager.close()
            logger.info("浏览器已关闭")
        except:
            pass


if __name__ == "__main__":
    asyncio.run(debug_inspect_page())

