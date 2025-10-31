#!/usr/bin/env python3
"""测试状态检测器功能."""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from src.browser.login_controller import LoginController
from src.utils.state_detector import PageState, StateDetector


async def test_state_detector():
    """测试状态检测器."""
    
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
    logger.info("状态检测器功能演示")
    logger.info("=" * 80)
    
    login_ctrl = LoginController()
    detector = StateDetector()
    
    try:
        # 1. 启动浏览器
        logger.info("\n[步骤1] 启动浏览器...")
        await login_ctrl.browser_manager.start()
        page = login_ctrl.browser_manager.page
        
        # 2. 检测登录页状态
        logger.info("\n[步骤2] 检测登录页状态...")
        state = await detector.detect_current_state(page)
        assert state == PageState.LOGIN_PAGE, f"期望LOGIN_PAGE，实际{state}"
        logger.success(f"✓ 正确检测到: {state.value}")
        
        # 3. 登录
        logger.info("\n[步骤3] 登录...")
        await login_ctrl.login(username, password)
        
        # 4. 检测首页状态
        logger.info("\n[步骤4] 检测首页状态...")
        state = await detector.detect_current_state(page)
        logger.info(f"当前状态: {state.value}")
        
        # 5. 确保到达采集箱
        logger.info("\n[步骤5] 确保到达采集箱（自动恢复）...")
        success = await detector.ensure_state(page, PageState.COLLECTION_BOX)
        if success:
            logger.success("✓ 成功确保在采集箱")
        else:
            logger.error("✗ 无法到达采集箱")
            return
        
        # 6. 测试：打开一个编辑弹窗
        logger.info("\n[步骤6] 打开编辑弹窗...")
        try:
            edit_btn = page.locator("button:has-text('编辑')").first
            await edit_btn.click(timeout=5000)
            await page.wait_for_timeout(2000)
        except:
            logger.warning("未找到编辑按钮，跳过")
        
        # 7. 检测弹窗状态
        logger.info("\n[步骤7] 检测弹窗状态...")
        state = await detector.detect_current_state(page)
        if state == PageState.EDIT_DIALOG_OPEN:
            logger.success("✓ 正确检测到编辑弹窗")
            
            # 8. 测试关闭弹窗
            logger.info("\n[步骤8] 测试关闭所有弹窗...")
            success = await detector.close_any_dialog(page)
            if success:
                logger.success("✓ 成功关闭弹窗")
            else:
                logger.warning("⚠️  关闭弹窗可能失败")
            
            # 9. 验证弹窗已关闭
            logger.info("\n[步骤9] 验证弹窗已关闭...")
            state = await detector.detect_current_state(page)
            if state == PageState.COLLECTION_BOX:
                logger.success("✓ 弹窗已关闭，回到采集箱")
            else:
                logger.warning(f"⚠️  当前状态: {state.value}")
        else:
            logger.info(f"当前状态: {state.value}（未打开编辑弹窗）")
        
        # 10. 测试恢复功能
        logger.info("\n[步骤10] 测试恢复到采集箱...")
        success = await detector.recover_to_collection_box(page)
        if success:
            logger.success("✓ 恢复成功")
        else:
            logger.error("✗ 恢复失败")
        
        logger.info("\n" + "=" * 80)
        logger.success("🎉 状态检测器测试完成！")
        logger.info("=" * 80)
        logger.info("\n浏览器将在10秒后关闭...")
        await asyncio.sleep(10)
        
    except KeyboardInterrupt:
        logger.info("\n\n用户中断")
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await login_ctrl.browser_manager.close()
        except:
            pass


if __name__ == "__main__":
    asyncio.run(test_state_detector())

