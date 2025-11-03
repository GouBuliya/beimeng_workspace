#!/usr/bin/env python3
"""
批量编辑结果验证脚本
自动登录并验证产品信息
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

async def verify():
    """验证批量编辑结果"""
    print("\n" + "="*70)
    print(" "*20 + "🔍 批量编辑结果验证")
    print("="*70 + "\n")
    
    login_ctrl = None
    try:
        # 从环境变量获取登录信息
        import os
        username = os.getenv("MIAOSHOU_USERNAME", "")
        password = os.getenv("MIAOSHOU_PASSWORD", "")
        
        # 1. 登录（会自动启动浏览器）
        print("🔐 [1/6] 登录妙手ERP...")
        login_ctrl = LoginController()
        
        if not await login_ctrl.login(username, password, headless=False):
            print("      ❌ 登录失败\n")
            return
        print("      ✅ 登录成功\n")
        
        # 获取page对象
        page = login_ctrl.browser_manager.page
        
        # 2. 导航
        print("🧭 [2/6] 导航到公用采集箱...")
        await page.goto("https://erp.91miaoshou.com/common_collect_box/items")
        await page.wait_for_timeout(3000)
        print("      ✅ 已到达采集箱\n")
        
        # 3. 切换tab
        print("📂 [3/6] 切换到'已认领'tab...")
        claimed_btn = page.locator(".jx-radio-button:has-text('已认领')").first
        await claimed_btn.click()
        await page.wait_for_timeout(2000)
        print("      ✅ 已切换\n")
        
        # 4. 产品统计
        print("📊 [4/6] 查看产品统计...")
        try:
            count_text = await page.locator(".jx-pagination__total").first.text_content()
            print(f"      {count_text}\n")
        except:
            print("      ⚠️  无法读取统计\n")
        
        # 5. 筛选人员
        print("👤 [5/6] 筛选人员: 柯诗俊(keshijun123)...")
        try:
            # 点击第2个选择框（人员）
            await page.locator(".jx-select").nth(1).click()
            await page.wait_for_timeout(500)
            
            # 输入并选择
            await page.locator(".jx-select__input input").nth(1).fill("柯诗俊")
            await page.wait_for_timeout(1000)
            await page.locator(".jx-select-dropdown__item:has-text('柯诗俊')").first.click()
            await page.wait_for_timeout(500)
            
            # 点击搜索
            await page.locator("button:has-text('搜索')").first.click()
            await page.wait_for_timeout(2000)
            print("      ✅ 已筛选柯诗俊的产品\n")
        except Exception as e:
            print(f"      ⚠️  筛选失败: {e}\n")
        
        # 6. 打开第一个产品
        print("📝 [6/6] 打开第1个产品查看详情...")
        try:
            await page.locator("button:has-text('编辑')").first.click()
            await page.wait_for_timeout(2500)
            print("      ✅ 编辑弹窗已打开\n")
        except Exception as e:
            print(f"      ❌ 无法打开: {e}\n")
            return
        
        # 验证产品信息
        print("="*70)
        print(" "*25 + "📋 产品信息验证")
        print("="*70 + "\n")
        
        results = []
        
        # 标题
        try:
            title = await page.locator(".jx-overlay-dialog input.jx-input__inner[type='text']:visible").first.input_value()
            has_model = "型号" in title or "A0" in title
            results.append(("产品标题", title[:60] + "..." if len(title) > 60 else title, "✅" if has_model else "⚠️"))
            if has_model:
                results.append(("  └─ 型号后缀", "已包含", "✅"))
            else:
                results.append(("  └─ 型号后缀", "未检测到", "⚠️"))
        except:
            results.append(("产品标题", "(无法读取)", "❌"))
        
        # 价格
        try:
            price = await page.locator("input[placeholder='价格']:not([aria-label='页'])").first.input_value()
            results.append(("SKU价格", f"¥{price}", "✅"))
        except:
            results.append(("SKU价格", "(无法读取)", "❌"))
        
        # 库存
        try:
            stock = await page.locator("input[type='number']").first.input_value()
            results.append(("SKU库存", f"{stock} 件", "✅"))
        except:
            results.append(("SKU库存", "(无法读取)", "❌"))
        
        # 尺寸
        try:
            length = await page.locator("input[placeholder='长']").first.input_value()
            width = await page.locator("input[placeholder='宽']").first.input_value()
            height = await page.locator("input[placeholder='高']").first.input_value()
            
            dim_str = f"{length} × {width} × {height} cm"
            results.append(("产品尺寸", dim_str, "✅"))
            
            # 验证长>宽>高
            try:
                l, w, h = float(length), float(width), float(height)
                if l > w > h:
                    results.append(("  └─ 规则检查", "长>宽>高 ✓", "✅"))
                else:
                    results.append(("  └─ 规则检查", f"不符合 ({l}>{w}>{h})", "⚠️"))
            except:
                results.append(("  └─ 规则检查", "(无法验证)", "⚠️"))
        except:
            results.append(("产品尺寸", "(无法读取)", "❌"))
        
        # 输出结果表格
        print(f"{'项目':<15} {'值':<45} {'状态':<5}")
        print("-"*70)
        for item, value, status in results:
            print(f"{item:<15} {value:<45} {status:<5}")
        
        print("\n" + "="*70)
        print(" "*25 + "✅ 验证完成")
        print("="*70 + "\n")
        
        # 统计
        success_count = sum(1 for _, _, s in results if s == "✅")
        warning_count = sum(1 for _, _, s in results if s == "⚠️")
        error_count = sum(1 for _, _, s in results if s == "❌")
        
        print(f"📈 统计: ✅ {success_count} 项成功 | ⚠️  {warning_count} 项警告 | ❌ {error_count} 项失败\n")
        
        print("💡 浏览器将保持打开30秒，您可以手动查看更多产品...")
        print("   (按 Ctrl+C 提前关闭)\n")
        
        # 等待30秒
        await page.wait_for_timeout(30000)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断\n")
    except Exception as e:
        print(f"\n\n❌ 发生错误: {e}\n")
    finally:
        if login_ctrl and login_ctrl.browser_manager:
            await login_ctrl.browser_manager.close()
            print("✅ 浏览器已关闭\n")

if __name__ == "__main__":
    asyncio.run(verify())
