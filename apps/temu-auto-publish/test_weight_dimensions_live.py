"""
@PURPOSE: 实际页面测试 - 重量/尺寸设置功能
@OUTLINE:
  - test_weight_dimensions(): 测试重量和尺寸设置
@DEPENDENCIES:
  - 内部: src.browser.*
  - 外部: playwright
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright
from loguru import logger

from src.browser.browser_manager import BrowserManager
from src.browser.cookie_manager import CookieManager
from src.browser.login_controller import LoginController
from src.browser.miaoshou_controller import MiaoshouController
from src.browser.first_edit_controller import FirstEditController


async def test_weight_dimensions():
    """测试重量/尺寸设置功能.
    
    测试内容：
    1. 导航到物流信息Tab
    2. 设置包裹重量（7500G）
    3. 设置包裹尺寸（89x64x32cm）
    """
    logger.info("=" * 80)
    logger.info("开始测试重量/尺寸设置功能")
    logger.info("=" * 80)
    
    async with async_playwright() as p:
        # 启动浏览器（非无头模式，方便观察）
        browser_manager = BrowserManager()
        await browser_manager.start(p, headless=False, slow_mo=300)
        page = browser_manager.page
        
        try:
            # 1. 登录
            logger.info("\n[步骤1] 登录妙手ERP...")
            cookie_manager = CookieManager()
            login_ctrl = LoginController(cookie_manager)
            
            if not await login_ctrl.login_with_cookies(page):
                logger.error("✗ 使用cookie登录失败，尝试手动登录...")
                # 这里可以添加手动登录逻辑
                return False
            
            logger.success("✓ 登录成功")
            
            # 2. 导航到采集箱
            logger.info("\n[步骤2] 导航到公用采集箱...")
            miaoshou_ctrl = MiaoshouController()
            await miaoshou_ctrl.navigate_to_collection_box(page)
            await page.wait_for_timeout(2000)
            
            logger.success("✓ 已到达公用采集箱")
            
            # 3. 筛选产品（可选）
            logger.info("\n[步骤3] 筛选产品...")
            # 如果需要筛选特定人员，取消注释下面一行
            # await miaoshou_ctrl.filter_by_staff(page, "你的名字")
            await miaoshou_ctrl.switch_tab(page, "all")
            await page.wait_for_timeout(1000)
            
            # 4. 打开第一个产品编辑
            logger.info("\n[步骤4] 打开第一个产品的编辑弹窗...")
            if not await miaoshou_ctrl.click_edit_product_by_index(page, 0):
                logger.error("✗ 无法打开编辑弹窗")
                return False
            
            await page.wait_for_timeout(2000)
            logger.success("✓ 编辑弹窗已打开")
            
            # 5. 测试重量设置
            logger.info("\n[步骤5] 测试包裹重量设置...")
            first_edit_ctrl = FirstEditController()
            
            weight_success = await first_edit_ctrl.set_package_weight_in_logistics(
                page,
                7500  # 7500G (在5000-9999范围内)
            )
            
            if weight_success:
                logger.success("✓ 包裹重量设置成功: 7500G")
            else:
                logger.warning("⚠️ 包裹重量设置失败 - 可能需要验证选择器")
            
            await page.wait_for_timeout(1000)
            
            # 6. 测试尺寸设置
            logger.info("\n[步骤6] 测试包裹尺寸设置...")
            
            try:
                dimensions_success = await first_edit_ctrl.set_package_dimensions_in_logistics(
                    page,
                    89,  # 长（cm）
                    64,  # 宽（cm）
                    32   # 高（cm）
                )
                
                if dimensions_success:
                    logger.success("✓ 包裹尺寸设置成功: 89x64x32cm")
                else:
                    logger.warning("⚠️ 包裹尺寸设置失败 - 可能需要验证选择器")
                    
            except ValueError as e:
                logger.error(f"✗ 尺寸验证失败: {e}")
            
            await page.wait_for_timeout(2000)
            
            # 7. 截图保存
            logger.info("\n[步骤7] 保存测试截图...")
            screenshot_path = "data/debug/weight_dimensions_test.png"
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=screenshot_path)
            logger.success(f"✓ 截图已保存: {screenshot_path}")
            
            # 8. 总结
            logger.info("\n" + "=" * 80)
            logger.info("测试总结:")
            logger.info("=" * 80)
            logger.info(f"重量设置: {'✓ 成功' if weight_success else '✗ 失败/需验证'}")
            logger.info(f"尺寸设置: {'✓ 成功' if dimensions_success else '✗ 失败/需验证'}")
            logger.info("\n提示：如果测试失败，请使用 Playwright Codegen 验证选择器")
            logger.info("命令: python -m playwright codegen https://erp.91miaoshou.com")
            
            # 等待一段时间以便观察
            logger.info("\n等待10秒后自动关闭浏览器...")
            await page.wait_for_timeout(10000)
            
            return weight_success and dimensions_success
            
        except Exception as e:
            logger.error(f"测试过程出错: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
            
        finally:
            await browser_manager.stop()


if __name__ == "__main__":
    result = asyncio.run(test_weight_dimensions())
    sys.exit(0 if result else 1)

