#!/usr/bin/env python3
"""快速测试Tab切换功能."""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController


async def test_tab_switch():
    """测试Tab切换."""
    
    # 加载环境变量
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    username = os.getenv("MIAOSHOU_USERNAME") or os.getenv("TEMU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD") or os.getenv("TEMU_PASSWORD")
    
    if not username or not password:
        logger.error("❌ 未找到登录凭证")
        return
    
    login_ctrl = LoginController()
    
    try:
        # 启动浏览器
        logger.info("启动浏览器...")
        await login_ctrl.browser_manager.start()
        page = login_ctrl.browser_manager.page
        
        # 登录
        logger.info("登录...")
        await login_ctrl.login(username, password)
        
        # 导航到采集箱
        logger.info("导航到采集箱...")
        miaoshou_ctrl = MiaoshouController()
        await miaoshou_ctrl.navigate_to_collection_box(page, use_sidebar=False)
        
        # 测试切换tab
        logger.info("\n" + "=" * 60)
        logger.info("测试Tab切换功能")
        logger.info("=" * 60)
        
        tabs = ["all", "unclaimed", "claimed", "failed"]
        for tab_name in tabs:
            logger.info(f"\n>>> 切换到「{tab_name}」tab...")
            success = await miaoshou_ctrl.switch_tab(page, tab_name)
            if success:
                logger.success(f"✅ 成功切换到「{tab_name}」tab")
                
                # 检查产品数量
                counts = await miaoshou_ctrl.get_product_count(page)
                logger.info(f"   产品统计: {counts}")
            else:
                logger.error(f"❌ 切换失败")
            
            await page.wait_for_timeout(1000)
        
        logger.info("\n" + "=" * 60)
        logger.success("✅ 测试完成！")
        logger.info("=" * 60)
        
        # 保持浏览器打开10秒
        logger.info("\n浏览器将在10秒后关闭...")
        await asyncio.sleep(10)
        
    except Exception as e:
        logger.error(f"发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await login_ctrl.browser_manager.close()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(test_tab_switch())

