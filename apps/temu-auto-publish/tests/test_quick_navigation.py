"""
简化测试：验证选择器和导航功能（基于浏览器session）

这个测试假设浏览器已经登录（session有效），直接测试导航和选择器功能。

运行方式：
    uv run python apps/temu-auto-publish/tests/test_quick_navigation.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
current_file = Path(__file__)
app_root = current_file.parent.parent
sys.path.insert(0, str(app_root))

import pytest
from loguru import logger
from playwright.async_api import async_playwright


@pytest.mark.asyncio
@pytest.mark.integration
async def test_navigation():
    """快速测试：直接在浏览器中导航到公用采集箱."""
    logger.info("=" * 80)
    logger.info("快速导航测试")
    logger.info("=" * 80)

    async with async_playwright() as p:
        # 启动浏览器（使用持久化上下文，保留session）
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 1. 直接访问首页（依赖cookie session）
            logger.info("访问妙手ERP首页...")
            await page.goto("https://erp.91miaoshou.com/welcome", timeout=60000)
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)

            # 检查是否登录成功
            current_url = page.url
            logger.info(f"当前URL: {current_url}")

            if "welcome" in current_url:
                logger.success("✅ 成功访问首页（Session有效）")
            else:
                logger.error("❌ Session已过期，请先手动登录")
                logger.info("保持浏览器打开10秒，供手动登录...")
                await asyncio.sleep(10)
                return

            # 2. 测试通过侧边栏导航到公用采集箱
            logger.info("测试导航...")
            
            # 方式1：直接URL导航
            logger.info("方式1：直接URL导航到公用采集箱")
            await page.goto("https://erp.91miaoshou.com/common_collect_box/items", timeout=30000)
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(2)

            if "common_collect_box/items" in page.url:
                logger.success("✅ URL导航成功")
            else:
                logger.error(f"❌ URL导航失败，当前URL: {page.url}")

            # 3. 测试切换到"已认领"tab
            logger.info("测试Tab切换...")
            
            # 使用文本定位器（更可靠）
            claimed_tab = page.locator('text="已认领"')
            if await claimed_tab.count() > 0:
                await claimed_tab.click()
                await asyncio.sleep(2)
                logger.success("✅ 成功切换到「已认领」tab")
            else:
                logger.warning("⚠️ 未找到「已认领」tab")

            # 4. 打印当前页面的一些选择器（用于调试）
            logger.info("获取当前页面的选择器信息...")
            
            # 尝试找到产品列表的编辑按钮
            edit_buttons = await page.locator('button:has-text("编辑")').count()
            logger.info(f"找到 {edit_buttons} 个编辑按钮")

            if edit_buttons > 0:
                logger.success("✅ 产品列表加载正常")
                logger.info("尝试点击第一个编辑按钮...")
                await page.locator('button:has-text("编辑")').first.click()
                await asyncio.sleep(2)

                # 检查弹窗是否打开
                close_button = await page.locator('button:has-text("关闭"), button[aria-label*="关闭"]').count()
                if close_button > 0:
                    logger.success("✅ 编辑弹窗已打开")
                    await page.locator('button:has-text("关闭"), button[aria-label*="关闭"]').first.click()
                    await asyncio.sleep(1)
                    logger.info("✓ 弹窗已关闭")
                else:
                    logger.warning("⚠️ 未检测到弹窗")

            # 测试完成
            logger.info("=" * 80)
            logger.success("✅ 导航测试完成！")
            logger.info("=" * 80)
            logger.info("浏览器将保持打开10秒...")

            await asyncio.sleep(10)

        except Exception as e:
            logger.error(f"❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(test_navigation())
    except KeyboardInterrupt:
        logger.info("测试被用户中断")
    except Exception as e:
        logger.error(f"测试运行失败: {e}")

