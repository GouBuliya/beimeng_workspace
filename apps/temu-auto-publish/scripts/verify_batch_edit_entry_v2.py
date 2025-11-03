#!/usr/bin/env python3
"""
批量编辑入口验证脚本（正确版本）
进入 Temu全托管采集箱 进行批量编辑
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

async def verify_batch_edit_entry():
    """验证批量编辑入口（Temu全托管采集箱）"""
    print("\n" + "="*70)
    print(" "*15 + "🔍 批量编辑入口验证（Temu全托管采集箱）")
    print("="*70 + "\n")
    
    login_ctrl = None
    try:
        # 从环境变量获取登录信息
        import os
        username = os.getenv("MIAOSHOU_USERNAME", "")
        password = os.getenv("MIAOSHOU_PASSWORD", "")
        
        # 1. 登录
        print("🔐 [1/7] 登录妙手ERP...")
        login_ctrl = LoginController()
        
        if not await login_ctrl.login(username, password, headless=False):
            print("      ❌ 登录失败\n")
            return
        print("      ✅ 登录成功\n")
        
        page = login_ctrl.browser_manager.page
        
        # 2. 导航到 Temu全托管采集箱（正确的批量编辑入口）
        print("🧭 [2/7] 导航到 Temu全托管采集箱...")
        print("      💡 注意：批量编辑只能在Temu全托管采集箱中进行\n")
        
        # Temu全托管采集箱的正确URL
        temu_box_url = "https://erp.91miaoshou.com/pddkj/collect_box/items"
        await page.goto(temu_box_url)
        await page.wait_for_timeout(3000)
        
        # 检查是否到达正确页面
        current_url = page.url
        page_title = await page.title()
        print(f"      当前URL: {current_url}")
        print(f"      页面标题: {page_title}")
        
        if "pddkj" in current_url or "Temu" in page_title or "全托管" in page_title:
            print("      ✅ 已到达 Temu全托管采集箱\n")
        else:
            print("      ⚠️  可能未到达正确页面，尝试通过菜单导航...\n")
            
            # 备用方案：通过左侧菜单导航
            try:
                # 点击"在线产品"或"Temu全托管"菜单
                temu_menu = page.locator("text='Temu全托管', text='在线产品'").first
                if await temu_menu.count() > 0:
                    await temu_menu.click()
                    await page.wait_for_timeout(1000)
                    
                    # 点击"采集箱"子菜单
                    collect_box = page.locator("text='采集箱'").first
                    await collect_box.click()
                    await page.wait_for_timeout(2000)
                    print("      ✅ 通过菜单导航成功\n")
            except Exception as e:
                print(f"      ⚠️  菜单导航失败: {e}\n")
        
        # 3. 查看页面信息
        print("📊 [3/7] 查看采集箱信息...")
        try:
            # 尝试读取产品统计
            count_text = await page.locator(".jx-pagination__total").first.text_content(timeout=5000)
            print(f"      产品总数: {count_text}")
        except:
            print("      ⚠️  无法读取统计信息")
        
        # 检查是否有tab切换
        try:
            tabs = await page.locator(".jx-radio-button").all()
            if tabs:
                print(f"      找到 {len(tabs)} 个tab")
                for tab in tabs[:5]:
                    tab_text = await tab.text_content()
                    print(f"        - {tab_text}")
        except:
            pass
        
        print()
        
        # 4. 选择产品
        print("✅ [4/7] 选择产品...")
        
        # 方式1：尝试全选
        try:
            select_all = page.locator("text='全选'").first
            if await select_all.count() > 0:
                await select_all.click()
                await page.wait_for_timeout(1000)
                print("      ✅ 已使用全选功能\n")
            else:
                # 方式2：逐个勾选
                print("      尝试逐个勾选产品...")
                checkboxes = page.locator(".jx-table__body .jx-checkbox")
                count = await checkboxes.count()
                print(f"      找到 {count} 个checkbox")
                
                # 勾选前3个
                for i in range(min(3, count)):
                    try:
                        await checkboxes.nth(i).click()
                        await page.wait_for_timeout(300)
                        print(f"      ✅ 已勾选第 {i+1} 个产品")
                    except:
                        pass
                print()
        except Exception as e:
            print(f"      ⚠️  选择失败: {e}\n")
        
        # 截图
        await page.screenshot(path="data/temp/screenshots/temu_box_before_batch_edit.png")
        print("      📸 截图已保存: temu_box_before_batch_edit.png\n")
        
        # 5. 查找"批量编辑"按钮
        print("🔍 [5/7] 查找「批量编辑」按钮...")
        
        batch_edit_selectors = [
            "button:has-text('批量编辑')",
            "button:has-text('批量')",
            ".jx-button:has-text('批量编辑')"
        ]
        
        batch_edit_btn = None
        for selector in batch_edit_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    batch_edit_btn = btn
                    print(f"      ✅ 找到按钮: {selector}\n")
                    break
            except:
                continue
        
        if not batch_edit_btn:
            print("      ⚠️  未找到「批量编辑」按钮")
            print("      💡 可能原因：")
            print("         1. 未选择产品")
            print("         2. 当前不在Temu全托管采集箱")
            print("         3. 按钮文案不同\n")
            
            # 列出所有按钮
            print("      页面上的所有按钮：")
            try:
                all_buttons = await page.locator("button").all()
                for i, btn in enumerate(all_buttons[:15]):
                    try:
                        text = await btn.text_content()
                        if text and text.strip():
                            print(f"        {i+1}. {text.strip()}")
                    except:
                        pass
            except:
                pass
            print()
        else:
            # 6. 点击"批量编辑"按钮
            print("🖱️  [6/7] 点击「批量编辑」按钮...")
            try:
                await batch_edit_btn.click()
                await page.wait_for_timeout(3000)
                print("      ✅ 已点击\n")
                
                # 截图
                await page.screenshot(path="data/temp/screenshots/after_batch_edit_click.png")
                print("      📸 截图已保存: after_batch_edit_click.png\n")
                
                # 7. 检查是否进入批量编辑页面
                print("🔍 [7/7] 检查批量编辑页面...")
                
                current_url = page.url
                print(f"      当前URL: {current_url}")
                
                # 检查URL或页面内容
                if "batch" in current_url.lower() or "批量" in current_url:
                    print("      ✅ URL包含批量编辑关键词\n")
                
                # 检查是否有批量编辑的步骤导航
                try:
                    # 查找步骤1-18的导航
                    steps = await page.locator("text='标题', text='英语标题', text='类目属性'").all()
                    if steps:
                        print(f"      ✅ 找到 {len(steps)} 个批量编辑步骤\n")
                    
                    # 列出步骤
                    print("      批量编辑步骤：")
                    step_names = [
                        "标题", "英语标题", "类目属性", "主货号", "外包装",
                        "产地", "定制品", "敏感属性", "重量", "尺寸",
                        "平台SKU", "SKU分类", "尺码表", "建议售价", "包装清单",
                        "轮播图", "颜色图", "产品说明书"
                    ]
                    
                    for i, step_name in enumerate(step_names, 1):
                        try:
                            step = page.locator(f"text='{step_name}'").first
                            if await step.count() > 0:
                                print(f"        ✅ 步骤{i}: {step_name}")
                            else:
                                print(f"        ⚪ 步骤{i}: {step_name} (未找到)")
                        except:
                            pass
                    print()
                    
                except Exception as e:
                    print(f"      ⚠️  未找到批量编辑步骤: {e}\n")
                
                # 最终截图
                await page.screenshot(path="data/temp/screenshots/batch_edit_page.png")
                print("      📸 批量编辑页面截图: batch_edit_page.png\n")
                
            except Exception as e:
                print(f"      ❌ 点击失败: {e}\n")
        
        print("="*70)
        print(" "*25 + "✅ 验证完成")
        print("="*70 + "\n")
        
        print("💡 浏览器将保持打开60秒，您可以手动操作...")
        print("   - 查看批量编辑页面")
        print("   - 尝试各个步骤")
        print("   (按 Ctrl+C 提前关闭)\n")
        
        # 等待60秒
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
    asyncio.run(verify_batch_edit_entry())

