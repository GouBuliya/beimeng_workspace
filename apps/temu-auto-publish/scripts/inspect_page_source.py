"""
@PURPOSE: 查看批量编辑页面的HTML源码，找到预览和保存按钮的真实结构
@OUTLINE:
  - 登录并导航到批量编辑页面
  - 点击第一个步骤（标题）
  - 保存完整的HTML源码
  - 分析按钮的实际选择器
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(project_root / ".env")

from src.browser.login_controller import LoginController
from src.browser.batch_edit_controller_v2 import BatchEditController
from packages.common.logger import logger


async def main():
    """查看页面源码."""
    logger.info("=" * 80)
    logger.info("🔍 查看批量编辑页面源码")
    logger.info("=" * 80)
    
    login_controller = None
    
    try:
        # 1. 登录
        logger.info("\n📋 阶段1：登录妙手ERP")
        username = os.getenv("MIAOSHOU_USERNAME")
        password = os.getenv("MIAOSHOU_PASSWORD")
        
        if not username or not password:
            logger.error("❌ 未找到登录凭据")
            return
        
        login_controller = LoginController()
        login_result = await login_controller.login(username, password)
        
        if not login_result:
            logger.error("❌ 登录失败")
            return
        
        logger.success("✅ 登录成功")
        
        # 获取page对象
        page = login_controller.browser_manager.page
        
        # 2. 导航到批量编辑
        logger.info("\n📋 阶段2：导航到批量编辑")
        batch_controller = BatchEditController(page)
        
        if not await batch_controller.navigate_to_batch_edit(select_count=20):
            logger.error("❌ 无法进入批量编辑页面")
            return
        
        logger.success("✅ 已进入批量编辑页面")
        
        # 3. 点击第一个步骤（标题）
        logger.info("\n📋 阶段3：点击标题步骤")
        title_locator = page.locator("text='标题'").first
        await title_locator.click()
        await page.wait_for_timeout(5000)
        logger.success("✅ 已点击标题步骤，等待页面加载")
        
        # 4. 保存完整HTML
        logger.info("\n📋 阶段4：保存页面源码")
        html_content = await page.content()
        
        output_file = project_root / "debug" / "batch_edit_page_source.html"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(html_content, encoding="utf-8")
        logger.success(f"✅ 页面源码已保存到: {output_file}")
        
        # 5. 查找所有按钮
        logger.info("\n📋 阶段5：查找所有按钮")
        all_buttons = await page.locator("button").all()
        logger.info(f"找到 {len(all_buttons)} 个按钮")
        
        button_info = []
        for i, btn in enumerate(all_buttons):
            try:
                text = await btn.inner_text()
                is_visible = await btn.is_visible()
                class_name = await btn.get_attribute("class") or ""
                btn_type = await btn.get_attribute("type") or ""
                
                if text and ("预览" in text or "保存" in text or "修改" in text):
                    button_info.append({
                        "index": i,
                        "text": text.strip(),
                        "visible": is_visible,
                        "class": class_name,
                        "type": btn_type
                    })
            except:
                continue
        
        # 6. 输出按钮信息
        logger.info("\n" + "=" * 80)
        logger.info("📊 找到的相关按钮：")
        logger.info("=" * 80)
        
        for info in button_info:
            logger.info(f"\n按钮 #{info['index']}:")
            logger.info(f"  文本: {info['text']}")
            logger.info(f"  可见: {info['visible']}")
            logger.info(f"  类型: {info['type']}")
            logger.info(f"  类名: {info['class']}")
        
        # 7. 查找特定的预览和保存按钮
        logger.info("\n" + "=" * 80)
        logger.info("🔍 详细分析预览和保存按钮：")
        logger.info("=" * 80)
        
        # 查找预览按钮
        logger.info("\n【预览按钮】")
        preview_selectors = [
            "button:has-text('预览')",
            "button.el-button:has-text('预览')",
            "button.jx-button:has-text('预览')",
        ]
        
        for selector in preview_selectors:
            try:
                btns = await page.locator(selector).all()
                logger.info(f"  选择器: {selector}")
                logger.info(f"    找到: {len(btns)} 个")
                for i, btn in enumerate(btns):
                    is_visible = await btn.is_visible()
                    logger.info(f"    按钮{i+1}: 可见={is_visible}")
            except Exception as e:
                logger.error(f"    错误: {e}")
        
        # 查找保存按钮
        logger.info("\n【保存修改按钮】")
        save_selectors = [
            "button:has-text('保存修改')",
            "button:has-text('保存')",
            "button.el-button:has-text('保存')",
            "button.jx-button:has-text('保存')",
        ]
        
        for selector in save_selectors:
            try:
                btns = await page.locator(selector).all()
                logger.info(f"  选择器: {selector}")
                logger.info(f"    找到: {len(btns)} 个")
                for i, btn in enumerate(btns):
                    is_visible = await btn.is_visible()
                    logger.info(f"    按钮{i+1}: 可见={is_visible}")
            except Exception as e:
                logger.error(f"    错误: {e}")
        
        # 8. 截图
        screenshot_file = project_root / "debug" / "batch_edit_page_screenshot.png"
        await page.screenshot(path=str(screenshot_file), full_page=True)
        logger.success(f"\n✅ 完整页面截图已保存到: {screenshot_file}")
        
        # 等待查看
        logger.info("\n等待30秒后关闭浏览器...")
        await page.wait_for_timeout(30000)
        
    except KeyboardInterrupt:
        logger.warning("\n⚠️ 用户中断")
    except Exception as e:
        logger.error(f"❌ 出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if login_controller and login_controller.browser_manager:
            await login_controller.browser_manager.close()
            logger.info("✅ 浏览器已关闭")


if __name__ == "__main__":
    asyncio.run(main())

