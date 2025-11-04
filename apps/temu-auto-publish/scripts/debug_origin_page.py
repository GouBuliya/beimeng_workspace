"""
调试产地页面元素结构

运行方式:
    uv run python scripts/debug_origin_page.py
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


async def debug_origin_page():
    """调试产地页面元素"""
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
        
        # 点击产地步骤
        logger.info("\n" + "=" * 60)
        logger.info("第3步：进入产地页面")
        logger.info("=" * 60)
        
        if not await batch_controller.click_step("产地", "7.6"):
            logger.error("❌ 无法进入产地页面")
            return
        
        logger.success("✅ 已进入产地页面")
        await page.wait_for_timeout(3000)
        
        # 获取页面HTML
        logger.info("\n" + "=" * 60)
        logger.info("第4步：分析产地页面结构")
        logger.info("=" * 60)
        
        # 截图
        await page.screenshot(path="debug_origin_full_page.png", full_page=True)
        logger.info("📸 已保存全页面截图: debug_origin_full_page.png")
        
        # 查找所有输入框
        logger.info("\n查找所有输入框...")
        inputs = await page.locator("input[type='text'], .el-input__inner").all()
        logger.info(f"找到 {len(inputs)} 个输入框")
        
        for i, input_elem in enumerate(inputs[:10]):  # 只看前10个
            try:
                placeholder = await input_elem.get_attribute("placeholder")
                name = await input_elem.get_attribute("name")
                value = await input_elem.input_value()
                visible = await input_elem.is_visible()
                
                logger.info(f"  输入框 {i+1}: placeholder='{placeholder}', name='{name}', visible={visible}")
                logger.info(f"    当前值: '{value}'")
            except Exception as e:
                logger.debug(f"  输入框 {i+1}: 读取失败 - {e}")
        
        # 查找包含"产地"的元素
        logger.info("\n查找所有包含'产地'的元素...")
        elements = await page.locator("text='产地'").all()
        logger.info(f"找到 {len(elements)} 个包含'产地'的元素")
        
        for i, elem in enumerate(elements):
            try:
                tag = await elem.evaluate("el => el.tagName")
                classes = await elem.get_attribute("class")
                text = await elem.inner_text()
                visible = await elem.is_visible()
                logger.info(f"  元素 {i+1}: <{tag}> class='{classes}' visible={visible}")
                logger.info(f"    文本: {text[:50]}")
                
                # 获取父元素
                parent = elem.locator("..")
                parent_html = await parent.inner_html()
                logger.info(f"    父元素HTML（前200字符）:")
                logger.info(f"    {parent_html[:200]}")
            except Exception as e:
                logger.debug(f"  元素 {i+1}: 读取失败 - {e}")
        
        # 测试输入"浙江"
        logger.info("\n" + "=" * 60)
        logger.info("第5步：测试输入'浙江'并观察下拉列表")
        logger.info("=" * 60)
        
        # 查找产地输入框（使用多种策略）
        input_selectors = [
            "input[placeholder*='产地']",
            "input[placeholder*='省份']",
            "text='产地' >> .. >> input",
            ".el-input__inner"
        ]
        
        input_found = False
        for selector in input_selectors:
            try:
                all_inputs = await page.locator(selector).all()
                logger.info(f"选择器 '{selector}' 找到 {len(all_inputs)} 个元素")
                
                for input_elem in all_inputs:
                    if await input_elem.is_visible():
                        logger.info(f"  找到可见输入框，尝试输入'浙江'...")
                        
                        # 清空并输入
                        await input_elem.clear()
                        await input_elem.fill("浙江")
                        logger.success("  ✓ 已输入：浙江")
                        input_found = True
                        
                        # 等待下拉列表
                        await page.wait_for_timeout(2000)
                        
                        # 查找下拉列表
                        logger.info("\n  查找下拉列表选项...")
                        dropdown_items = await page.locator(".el-select-dropdown__item, .jx-pro-option, li[role='option']").all()
                        logger.info(f"  找到 {len(dropdown_items)} 个下拉选项")
                        
                        for j, item in enumerate(dropdown_items):
                            try:
                                text = await item.inner_text()
                                visible = await item.is_visible()
                                classes = await item.get_attribute("class")
                                logger.info(f"    选项 {j+1}: visible={visible}, class='{classes}'")
                                logger.info(f"      文本: {text.strip()}")
                            except Exception as e:
                                logger.debug(f"    选项 {j+1}: 读取失败 - {e}")
                        
                        # 截图下拉列表
                        await page.screenshot(path="debug_origin_dropdown.png", full_page=True)
                        logger.info("\n  📸 已保存下拉列表截图: debug_origin_dropdown.png")
                        
                        break
                
                if input_found:
                    break
            except Exception as e:
                logger.debug(f"选择器 '{selector}' 失败: {e}")
                continue
        
        if not input_found:
            logger.warning("⚠️ 未找到产地输入框")
        
        # 等待观察
        logger.info("\n⏳ 等待30秒以便观察页面...")
        logger.info("请手动查看浏览器中的产地页面和下拉列表")
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
    asyncio.run(debug_origin_page())

