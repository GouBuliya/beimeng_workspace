"""
调试外包装页面元素结构

运行方式:
    uv run python scripts/debug_packaging_page.py
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

from packages.common.logger import logger

# 加载环境变量
env_path = project_root / ".env"
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"✓ 已加载环境变量: {env_path}")

from src.browser.login_controller import LoginController
from src.browser.batch_edit_controller_v2 import BatchEditController


async def debug_packaging_page():
    """调试外包装页面元素"""
    username = os.getenv("MIAOSHOU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD")

    if not username or not password:
        logger.error("❌ 请配置环境变量")
        return

    login_controller = None

    try:
        # 登录
        logger.info("=" * 60)
        logger.info("第1步：登录")
        logger.info("=" * 60)

        login_controller = LoginController()
        login_success = await login_controller.login(username, password)

        if not login_success:
            logger.error("❌ 登录失败")
            return

        logger.success("✅ 登录成功")
        page = login_controller.browser_manager.page
        await page.wait_for_timeout(3000)

        # 进入批量编辑
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

        # 点击外包装步骤
        logger.info("\n" + "=" * 60)
        logger.info("第3步：进入外包装页面")
        logger.info("=" * 60)

        if not await batch_controller.click_step("外包装", "7.5"):
            logger.error("❌ 无法进入外包装页面")
            return

        logger.success("✅ 已进入外包装页面")
        await page.wait_for_timeout(3000)

        # 获取页面HTML
        logger.info("\n" + "=" * 60)
        logger.info("第4步：分析页面结构")
        logger.info("=" * 60)

        # 截图
        await page.screenshot(path="debug_packaging_full_page.png", full_page=True)
        logger.info("📸 已保存全页面截图: debug_packaging_full_page.png")

        # 查找所有radio按钮
        logger.info("\n查找所有单选按钮...")
        radios = await page.locator("input[type='radio']").all()
        logger.info(f"找到 {len(radios)} 个单选按钮")

        for i, radio in enumerate(radios[:10]):  # 只看前10个
            try:
                value = await radio.get_attribute("value")
                name = await radio.get_attribute("name")
                checked = await radio.is_checked()
                visible = await radio.is_visible()

                # 获取相邻的label文本
                parent = radio.locator("..")
                label_text = await parent.inner_text() if await parent.count() > 0 else "N/A"

                logger.info(
                    f"  Radio {i + 1}: name={name}, value={value}, checked={checked}, visible={visible}"
                )
                logger.info(f"    Label: {label_text[:50]}")
            except Exception as e:
                logger.debug(f"  Radio {i + 1}: 读取失败 - {e}")

        # 查找所有包含"长方体"的元素
        logger.info("\n查找所有包含'长方体'的元素...")
        elements = await page.locator("text='长方体'").all()
        logger.info(f"找到 {len(elements)} 个包含'长方体'的元素")

        for i, elem in enumerate(elements):
            try:
                tag = await elem.evaluate("el => el.tagName")
                classes = await elem.get_attribute("class")
                text = await elem.inner_text()
                visible = await elem.is_visible()
                logger.info(f"  元素 {i + 1}: <{tag}> class='{classes}' visible={visible}")
                logger.info(f"    文本: {text[:50]}")
            except Exception as e:
                logger.debug(f"  元素 {i + 1}: 读取失败 - {e}")

        # 查找所有包含"硬包装"的元素
        logger.info("\n查找所有包含'硬包装'的元素...")
        elements = await page.locator("text='硬包装'").all()
        logger.info(f"找到 {len(elements)} 个包含'硬包装'的元素")

        for i, elem in enumerate(elements):
            try:
                tag = await elem.evaluate("el => el.tagName")
                classes = await elem.get_attribute("class")
                text = await elem.inner_text()
                visible = await elem.is_visible()
                logger.info(f"  元素 {i + 1}: <{tag}> class='{classes}' visible={visible}")
                logger.info(f"    文本: {text[:50]}")
            except Exception as e:
                logger.debug(f"  元素 {i + 1}: 读取失败 - {e}")

        # 获取外包装区域的HTML
        logger.info("\n获取外包装表单区域HTML...")
        try:
            # 尝试找到包含"外包装形状"的区域
            form_area = page.locator("text='外包装形状'").locator("..")
            if await form_area.count() > 0:
                html = await form_area.inner_html()
                with open("debug_packaging_html.html", "w", encoding="utf-8") as f:
                    f.write(html)
                logger.info("📄 已保存HTML片段: debug_packaging_html.html")
        except Exception as e:
            logger.warning(f"无法获取HTML: {e}")

        # 等待观察
        logger.info("\n⏳ 等待30秒以便观察页面...")
        logger.info("请手动查看浏览器中的外包装页面")
        await page.wait_for_timeout(30000)

    except Exception as e:
        logger.error(f"❌ 调试过程出错: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if login_controller and login_controller.browser_manager:
            await login_controller.browser_manager.close()
            logger.info("✅ 浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(debug_packaging_page())
