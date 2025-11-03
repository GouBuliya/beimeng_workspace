#!/usr/bin/env python3
"""
批量编辑入口验证脚本
验证如何正确进入批量编辑模式
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
    """验证批量编辑入口"""
    print("\n" + "="*70)
    print(" "*20 + "🔍 批量编辑入口验证")
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
        
        # 2. 导航
        print("🧭 [2/7] 导航到公用采集箱...")
        await page.goto("https://erp.91miaoshou.com/common_collect_box/items")
        await page.wait_for_timeout(3000)
        print("      ✅ 已到达采集箱\n")
        
        # 3. 切换tab
        print("📂 [3/7] 切换到'已认领'tab...")
        claimed_btn = page.locator(".jx-radio-button:has-text('已认领')").first
        await claimed_btn.click()
        await page.wait_for_timeout(2000)
        print("      ✅ 已切换\n")
        
        # 4. 产品统计
        print("📊 [4/7] 查看产品统计...")
        try:
            count_text = await page.locator(".jx-pagination__total").first.text_content()
            print(f"      {count_text}\n")
        except:
            print("      ⚠️  无法读取统计\n")
        
        # 5. 选择产品（勾选前3个）
        print("✅ [5/7] 选择产品（勾选前3个）...")
        try:
            # 方式1: 点击checkbox的可见容器（而不是隐藏的input）
            # 找到表格行的checkbox容器
            checkbox_containers = page.locator(".jx-table__body .jx-checkbox")
            count = await checkbox_containers.count()
            print(f"      找到 {count} 个checkbox容器")
            
            # 点击前3个产品的checkbox容器
            selected_count = 0
            for i in range(min(3, count)):
                try:
                    await checkbox_containers.nth(i).click()
                    await page.wait_for_timeout(300)
                    selected_count += 1
                    print(f"      ✅ 已勾选第 {i+1} 个产品")
                except Exception as e:
                    print(f"      ⚠️  第 {i+1} 个产品勾选失败: {e}")
            
            await page.wait_for_timeout(1000)
            print(f"      ✅ 已选择 {selected_count} 个产品\n")
            
            if selected_count == 0:
                print("      ❌ 未能选择任何产品，尝试备用方案...\n")
                
                # 备用方案：使用全选
                print("      尝试使用全选功能...")
                try:
                    select_all = page.locator("text='全选'").first
                    await select_all.click()
                    await page.wait_for_timeout(500)
                    print("      ✅ 已全选\n")
                except Exception as e:
                    print(f"      ❌ 全选也失败: {e}\n")
                    return
                
        except Exception as e:
            print(f"      ❌ 选择失败: {e}\n")
            return
        
        # 截图当前状态
        await page.screenshot(path="data/temp/screenshots/before_batch_edit.png")
        print("      📸 截图已保存: before_batch_edit.png\n")
        
        # 6. 点击"认领到"按钮
        print("🖱️  [6/7] 点击顶部的「认领到」按钮...")
        try:
            # 找到操作区域的"认领到"按钮（不是单个产品的按钮）
            claim_to_btn = page.locator(".jx-button:has-text('认领到')").first
            await claim_to_btn.click()
            await page.wait_for_timeout(2000)
            print("      ✅ 已点击「认领到」\n")
        except Exception as e:
            print(f"      ❌ 点击失败: {e}\n")
            
            # 调试：列出所有"认领到"按钮
            print("      调试：查找所有「认领到」按钮...")
            try:
                claim_btns = await page.locator("button:has-text('认领到')").all()
                print(f"      找到 {len(claim_btns)} 个「认领到」按钮")
                if len(claim_btns) > 0:
                    print("      尝试点击第1个...")
                    await claim_btns[0].click()
                    await page.wait_for_timeout(2000)
                    print("      ✅ 已点击")
            except Exception as e2:
                print(f"      调试也失败: {e2}")
                return
        
        # 截图点击后状态
        await page.screenshot(path="data/temp/screenshots/after_click_claim.png")
        print("      📸 截图已保存: after_click_claim.png\n")
        
        # 7. 检查是否弹出批量编辑对话框
        print("🔍 [7/7] 检查批量编辑对话框...")
        try:
            # 等待对话框出现
            dialog = page.locator(".jx-dialog, .jx-overlay-dialog").first
            if await dialog.count() > 0 and await dialog.is_visible():
                print("      ✅ 批量编辑对话框已打开\n")
                
                # 尝试读取对话框标题
                try:
                    title = await page.locator(".jx-dialog__header, .jx-dialog__title").first.text_content()
                    print(f"      对话框标题: {title}\n")
                except:
                    pass
                
                # 检查是否有批量编辑相关的内容
                page_text = await page.content()
                if "批量" in page_text or "认领" in page_text or "店铺" in page_text:
                    print("      ✅ 检测到批量编辑相关内容\n")
                    
                    # 截图对话框
                    await page.screenshot(path="data/temp/screenshots/batch_edit_dialog.png")
                    print("      📸 对话框截图已保存: batch_edit_dialog.png\n")
            else:
                print("      ⚠️  未检测到对话框\n")
        except Exception as e:
            print(f"      ❌ 检查失败: {e}\n")
        
        print("="*70)
        print(" "*25 + "✅ 验证完成")
        print("="*70 + "\n")
        
        print("💡 浏览器将保持打开60秒，您可以手动操作...")
        print("   - 查看批量编辑对话框")
        print("   - 尝试进入批量编辑流程")
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

