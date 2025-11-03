#!/usr/bin/env python3
"""
批量编辑18步深度验证脚本
实际测试每一步是否可以操作
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

async def test_batch_edit_steps():
    """深度测试批量编辑18步"""
    print("\n" + "="*70)
    print(" "*15 + "🔍 批量编辑18步深度验证")
    print("="*70 + "\n")
    
    login_ctrl = None
    try:
        import os
        username = os.getenv("MIAOSHOU_USERNAME", "")
        password = os.getenv("MIAOSHOU_PASSWORD", "")
        
        # 1. 登录
        print("🔐 [1/4] 登录妙手ERP...")
        login_ctrl = LoginController()
        
        if not await login_ctrl.login(username, password, headless=False):
            print("      ❌ 登录失败\n")
            return
        print("      ✅ 登录成功\n")
        
        page = login_ctrl.browser_manager.page
        
        # 2. 导航到Temu全托管采集箱
        print("🧭 [2/4] 导航到Temu全托管采集箱...")
        await page.goto("https://erp.91miaoshou.com/pddkj/collect_box/items")
        await page.wait_for_timeout(3000)
        print("      ✅ 已到达\n")
        
        # 3. 选择产品并进入批量编辑
        print("✅ [3/4] 选择产品并进入批量编辑...")
        
        # 全选
        try:
            select_all = page.locator("text='全选'").first
            await select_all.click()
            await page.wait_for_timeout(1000)
            print("      ✅ 已全选产品")
        except:
            print("      ⚠️  全选失败，尝试手动选择...")
        
        # 点击批量编辑
        try:
            batch_edit_btn = page.locator("button:has-text('批量编辑')").first
            await batch_edit_btn.click()
            await page.wait_for_timeout(3000)
            print("      ✅ 已进入批量编辑页面\n")
        except Exception as e:
            print(f"      ❌ 无法进入批量编辑: {e}\n")
            return
        
        # 4. 测试18步
        print("🧪 [4/4] 测试18步操作可行性...\n")
        print("="*70)
        
        steps = [
            ("标题", "7.1", False),
            ("英语标题", "7.2", True),
            ("类目属性", "7.3", True),
            ("主货号", "7.4", False),
            ("外包装", "7.5", True),
            ("产地", "7.6", True),
            ("定制品", "7.7", False),
            ("敏感属性", "7.8", False),
            ("重量", "7.9", True),
            ("尺寸", "7.10", True),
            ("平台SKU", "7.11", True),
            ("SKU分类", "7.12", True),
            ("尺码表", "7.13", False),
            ("建议售价", "7.14", True),
            ("包装清单", "7.15", False),
            ("轮播图", "7.16", False),
            ("颜色图", "7.17", False),
            ("产品说明书", "7.18", True)
        ]
        
        results = []
        
        for step_name, step_num, needs_edit in steps:
            print(f"\n【步骤{step_num}】{step_name} {'(需要编辑)' if needs_edit else '(预览+保存)'}")
            print("-" * 70)
            
            result = {
                "step": step_num,
                "name": step_name,
                "needs_edit": needs_edit,
                "found": False,
                "clickable": False,
                "has_preview": False,
                "has_save": False,
                "has_input": False,
                "error": None
            }
            
            try:
                # 1. 查找步骤按钮/链接
                step_locators = [
                    f"text='{step_name}'",
                    f"button:has-text('{step_name}')",
                    f"a:has-text('{step_name}')",
                    f".step-item:has-text('{step_name}')",
                    f".menu-item:has-text('{step_name}')"
                ]
                
                step_elem = None
                for locator in step_locators:
                    try:
                        elem = page.locator(locator).first
                        if await elem.count() > 0:
                            step_elem = elem
                            result["found"] = True
                            print(f"  ✅ 找到步骤: {locator}")
                            break
                    except:
                        continue
                
                if not step_elem:
                    result["error"] = "未找到步骤"
                    print(f"  ❌ 未找到步骤")
                    results.append(result)
                    continue
                
                # 2. 尝试点击步骤
                try:
                    await step_elem.click()
                    await page.wait_for_timeout(1500)
                    result["clickable"] = True
                    print(f"  ✅ 可以点击")
                except Exception as e:
                    result["error"] = f"无法点击: {e}"
                    print(f"  ❌ 无法点击: {e}")
                    results.append(result)
                    continue
                
                # 3. 检查页面元素
                # 查找预览按钮
                preview_selectors = [
                    "button:has-text('预览')",
                    "button:has-text('Preview')",
                    ".preview-btn"
                ]
                for selector in preview_selectors:
                    try:
                        btn = page.locator(selector).first
                        if await btn.count() > 0 and await btn.is_visible():
                            result["has_preview"] = True
                            print(f"  ✅ 找到预览按钮")
                            break
                    except:
                        pass
                
                # 查找保存按钮
                save_selectors = [
                    "button:has-text('保存修改')",
                    "button:has-text('保存')",
                    "button:has-text('Save')",
                    ".save-btn"
                ]
                for selector in save_selectors:
                    try:
                        btn = page.locator(selector).first
                        if await btn.count() > 0 and await btn.is_visible():
                            result["has_save"] = True
                            print(f"  ✅ 找到保存按钮")
                            break
                    except:
                        pass
                
                # 如果需要编辑，查找输入框
                if needs_edit:
                    input_selectors = [
                        "input[type='text']",
                        "input[type='number']",
                        "textarea",
                        ".jx-input__inner"
                    ]
                    for selector in input_selectors:
                        try:
                            inputs = page.locator(selector)
                            count = await inputs.count()
                            if count > 0:
                                result["has_input"] = True
                                print(f"  ✅ 找到 {count} 个输入框")
                                break
                        except:
                            pass
                    
                    if not result["has_input"]:
                        # 查找下拉框
                        select_selectors = [
                            "select",
                            ".jx-select",
                            ".el-select"
                        ]
                        for selector in select_selectors:
                            try:
                                selects = page.locator(selector)
                                count = await selects.count()
                                if count > 0:
                                    result["has_input"] = True
                                    print(f"  ✅ 找到 {count} 个下拉框")
                                    break
                            except:
                                pass
                
                # 判断是否可以完成
                if needs_edit:
                    can_complete = result["has_input"] and result["has_preview"] and result["has_save"]
                    status = "✅ 可以完成" if can_complete else "⚠️  可能需要手动操作"
                else:
                    can_complete = result["has_preview"] and result["has_save"]
                    status = "✅ 可以完成" if can_complete else "⚠️  缺少预览/保存按钮"
                
                print(f"  {status}")
                
            except Exception as e:
                result["error"] = str(e)
                print(f"  ❌ 测试失败: {e}")
            
            results.append(result)
            
            # 截图
            try:
                await page.screenshot(path=f"data/temp/screenshots/step_{step_num.replace('.', '_')}.png")
            except:
                pass
        
        # 5. 生成报告
        print("\n" + "="*70)
        print(" "*25 + "📊 测试报告")
        print("="*70 + "\n")
        
        total = len(results)
        found = sum(1 for r in results if r["found"])
        clickable = sum(1 for r in results if r["clickable"])
        has_preview = sum(1 for r in results if r["has_preview"])
        has_save = sum(1 for r in results if r["has_save"])
        needs_edit_count = sum(1 for r in results if r["needs_edit"])
        has_input = sum(1 for r in results if r["has_input"] and r["needs_edit"])
        
        print(f"总步骤数: {total}")
        print(f"找到步骤: {found}/{total} ({found*100//total}%)")
        print(f"可点击: {clickable}/{total} ({clickable*100//total}%)")
        print(f"有预览按钮: {has_preview}/{total} ({has_preview*100//total}%)")
        print(f"有保存按钮: {has_save}/{total} ({has_save*100//total}%)")
        print(f"需要编辑的步骤: {needs_edit_count}")
        print(f"  └─ 有输入框: {has_input}/{needs_edit_count}")
        print()
        
        # 问题步骤
        problem_steps = [r for r in results if not r["clickable"] or r["error"]]
        if problem_steps:
            print("⚠️  问题步骤：")
            for r in problem_steps:
                print(f"  - {r['step']} {r['name']}: {r['error'] or '无法点击'}")
            print()
        
        # 建议
        print("💡 建议：")
        if clickable < total:
            print(f"  - 有 {total - clickable} 个步骤无法点击，需要调整选择器")
        if has_preview < total:
            print(f"  - 有 {total - has_preview} 个步骤没有预览按钮")
        if has_save < total:
            print(f"  - 有 {total - has_save} 个步骤没有保存按钮")
        if has_input < needs_edit_count:
            print(f"  - 有 {needs_edit_count - has_input} 个需要编辑的步骤没有找到输入框")
        
        if clickable == total and has_preview == total and has_save == total:
            print("  ✅ 所有步骤都可以自动化完成！")
        else:
            print("  ⚠️  部分步骤可能需要手动处理或进一步调试")
        
        print("\n💡 浏览器将保持打开60秒，您可以手动测试各步骤...\n")
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
    asyncio.run(test_batch_edit_steps())

