#!/usr/bin/env python3
"""
批量编辑入口验证脚本（菜单导航版本）
通过左侧菜单导航到Temu全托管采集箱
"""
import asyncio
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from src.browser.browser_manager import BrowserManager
from src.browser.login_controller import LoginController

async def verify_batch_edit():
    """通过菜单导航找到批量编辑入口"""
    print("\n" + "="*70)
    print(" "*15 + "🔍 批量编辑验证（通过菜单导航）")
    print("="*70 + "\n")
    
    login_ctrl = None
    try:
        import os
        username = os.getenv("MIAOSHOU_USERNAME", "")
        password = os.getenv("MIAOSHOU_PASSWORD", "")
        
        # 1. 登录
        print("🔐 [1/5] 登录妙手ERP...")
        login_ctrl = LoginController()
        
        if not await login_ctrl.login(username, password, headless=False):
            print("      ❌ 登录失败\n")
            return
        print("      ✅ 登录成功\n")
        
        page = login_ctrl.browser_manager.page
        
        # 2. 查看左侧菜单结构
        print("🧭 [2/5] 查看左侧菜单...")
        await page.wait_for_timeout(2000)
        
        # 列出所有可能的菜单项
        menu_items = [
            "Temu全托管", "在线产品", "Temu全", "托管",
            "采集箱", "产品采集", "公用采集箱", "共用采集箱",
            "产品管理", "产品", "店铺产品"
        ]
        
        print("      正在查找菜单项...\n")
        for menu_name in menu_items:
            try:
                menu = page.locator(f"text='{menu_name}'").first
                if await menu.count() > 0:
                    print(f"      ✅ 找到菜单: {menu_name}")
            except:
                pass
        print()
        
        # 3. 尝试通过不同路径导航
        print("🚀 [3/5] 尝试导航到 Temu全托管采集箱...\n")
        
        # 策略1：直接点击"Temu全托管"相关菜单
        navigation_success = False
        
        # 尝试1：点击"Temu全托管"
        try:
            print("      [尝试1] 查找「Temu全托管」菜单...")
            temu_menu_selectors = [
                "text='Temu全托管'",
                "text='Temu全'",
                "text='在线产品'",
                ".sidebar-menu-item:has-text('Temu')",
                ".menu-item:has-text('Temu')"
            ]
            
            for selector in temu_menu_selectors:
                try:
                    menu = page.locator(selector).first
                    if await menu.count() > 0:
                        print(f"              找到菜单: {selector}")
                        await menu.click()
                        await page.wait_for_timeout(1000)
                        
                        # 点击后查看是否有"采集箱"子菜单
                        sub_menus = await page.locator("text='采集箱'").all()
                        if sub_menus:
                            print(f"              找到 {len(sub_menus)} 个「采集箱」子菜单")
                            await sub_menus[0].click()
                            await page.wait_for_timeout(2000)
                            navigation_success = True
                            print("              ✅ 导航成功\n")
                            break
                except:
                    continue
                    
            if navigation_success:
                pass  # 已成功
            else:
                print("              ⚠️  未找到Temu菜单\n")
        except Exception as e:
            print(f"              ❌ 失败: {e}\n")
        
        # 如果失败，尝试2：查找页面上的"采集箱"链接
        if not navigation_success:
            print("      [尝试2] 查找页面上的「采集箱」链接...")
            try:
                # 在整个页面查找"采集箱"文本
                collect_box_links = await page.locator("a:has-text('采集箱')").all()
                print(f"              找到 {len(collect_box_links)} 个采集箱链接")
                
                # 尝试点击每个链接
                for i, link in enumerate(collect_box_links):
                    try:
                        text = await link.text_content()
                        print(f"              [{i+1}] {text}")
                        
                        # 如果包含"Temu"或"托管"，优先点击
                        if "Temu" in text or "托管" in text or "全" in text:
                            await link.click()
                            await page.wait_for_timeout(2000)
                            navigation_success = True
                            print(f"              ✅ 点击了: {text}\n")
                            break
                    except:
                        pass
                
                if not navigation_success and collect_box_links:
                    # 点击第一个
                    await collect_box_links[0].click()
                    await page.wait_for_timeout(2000)
                    navigation_success = True
                    print("              ✅ 点击了第1个采集箱链接\n")
                    
            except Exception as e:
                print(f"              ❌ 失败: {e}\n")
        
        # 检查当前页面
        current_url = page.url
        page_title = await page.title()
        print(f"      当前URL: {current_url}")
        print(f"      页面标题: {page_title}\n")
        
        # 截图
        await page.screenshot(path="data/temp/screenshots/current_page.png")
        print("      📸 截图: current_page.png\n")
        
        # 4. 查找产品和批量编辑按钮
        print("📊 [4/5] 查找产品列表和批量编辑按钮...\n")
        
        # 检查是否有产品列表
        try:
            # 查找表格
            table = page.locator(".jx-table, table").first
            if await table.count() > 0:
                print("      ✅ 找到产品列表表格")
                
                # 尝试全选
                try:
                    select_all = page.locator("text='全选'").first
                    await select_all.click()
                    await page.wait_for_timeout(1000)
                    print("      ✅ 已全选产品\n")
                except:
                    print("      ⚠️  无法全选\n")
            else:
                print("      ⚠️  未找到产品列表\n")
        except:
            print("      ⚠️  检查产品列表失败\n")
        
        # 查找所有按钮
        print("      页面上的按钮：")
        try:
            buttons = await page.locator("button").all()
            for i, btn in enumerate(buttons[:20]):
                try:
                    text = await btn.text_content(timeout=1000)
                    if text and text.strip():
                        text = text.strip()
                        if len(text) < 50:  # 只显示合理长度的按钮文本
                            marker = "🎯" if "批量" in text or "编辑" in text else "  "
                            print(f"        {marker} {text}")
                except:
                    pass
        except:
            pass
        print()
        
        # 5. 尝试点击批量编辑
        print("🖱️  [5/5] 尝试点击批量编辑按钮...\n")
        
        batch_edit_found = False
        batch_edit_selectors = [
            "button:has-text('批量编辑')",
            "button:has-text('批量')",
            "a:has-text('批量编辑')",
            ".jx-button:has-text('批量')"
        ]
        
        for selector in batch_edit_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    print(f"      ✅ 找到按钮: {selector}")
                    await btn.click()
                    await page.wait_for_timeout(3000)
                    batch_edit_found = True
                    
                    # 截图
                    await page.screenshot(path="data/temp/screenshots/after_batch_edit_click.png")
                    print("      📸 截图: after_batch_edit_click.png")
                    
                    # 检查是否进入批量编辑页面
                    new_url = page.url
                    print(f"      新URL: {new_url}\n")
                    
                    # 查找批量编辑步骤
                    step_names = ["标题", "英语标题", "类目属性", "重量", "尺寸"]
                    print("      查找批量编辑步骤：")
                    for step in step_names:
                        try:
                            elem = page.locator(f"text='{step}'").first
                            if await elem.count() > 0:
                                print(f"        ✅ {step}")
                        except:
                            pass
                    print()
                    
                    break
            except:
                continue
        
        if not batch_edit_found:
            print("      ⚠️  未找到批量编辑按钮\n")
            print("      💡 可能需要：")
            print("         1. 先选择产品")
            print("         2. 确认在正确的采集箱页面")
            print("         3. 手动查看页面找到正确的按钮\n")
        
        print("="*70)
        print(" "*25 + "✅ 验证完成")
        print("="*70 + "\n")
        
        print("💡 浏览器将保持打开60秒，请手动操作以找到正确入口...\n")
        await page.wait_for_timeout(60000)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断\n")
    except Exception as e:
        print(f"\n\n❌ 发生错误: {e}\n")
        import traceback
        traceback.print_exc()
    finally:
        if login_ctrl and login_ctrl.browser_manager:
            await login_ctrl.browser_manager.close()
            print("✅ 浏览器已关闭\n")

if __name__ == "__main__":
    asyncio.run(verify_batch_edit())

