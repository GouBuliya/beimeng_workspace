#!/usr/bin/env python3
"""
批量编辑结果验证脚本（调试版本）
增加更多调试信息来诊断登录问题
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
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

async def debug_login():
    """调试登录流程"""
    print("\n" + "="*70)
    print(" "*20 + "🔍 登录流程调试")
    print("="*70 + "\n")
    
    browser_mgr = None
    try:
        # 从环境变量获取登录信息
        import os
        username = os.getenv("MIAOSHOU_USERNAME", "")
        password = os.getenv("MIAOSHOU_PASSWORD", "")
        
        if not username or not password:
            print("❌ 未配置用户名或密码")
            print(f"   MIAOSHOU_USERNAME: {'已设置' if username else '未设置'}")
            print(f"   MIAOSHOU_PASSWORD: {'已设置' if password else '未设置'}")
            return
        
        print(f"✅ 环境变量已配置")
        print(f"   用户名: {username}")
        print(f"   密码: {'*' * len(password)}\n")
        
        # 1. 启动浏览器
        print("🚀 [1/8] 启动浏览器...")
        browser_mgr = BrowserManager()
        await browser_mgr.start(headless=False)
        page = browser_mgr.page
        print("      ✅ 浏览器已启动\n")
        
        # 2. 导航到登录页
        print("🧭 [2/8] 导航到登录页...")
        login_url = "https://erp.91miaoshou.com/sub_account/users"
        await page.goto(login_url, timeout=60000)
        await page.wait_for_load_state("domcontentloaded")
        print(f"      ✅ 已到达: {page.url}\n")
        
        # 3. 等待登录表单
        print("⏳ [3/8] 等待登录表单加载...")
        try:
            await page.wait_for_selector("input[name='mobile']", timeout=10000)
            print("      ✅ 登录表单已加载\n")
        except Exception as e:
            print(f"      ❌ 等待表单失败: {e}\n")
            return
        
        # 4. 输入用户名
        print("📝 [4/8] 输入用户名...")
        # 使用更具体的选择器，选择登录表单的输入框
        username_input = page.locator("input[name='mobile'].account-input").first
        await username_input.fill(username)
        await page.wait_for_timeout(500)
        value = await username_input.input_value()
        print(f"      ✅ 已输入: {value}\n")
        
        # 5. 输入密码
        print("🔐 [5/8] 输入密码...")
        password_input = page.locator("input[name='password'].password-input").first
        await password_input.fill(password)
        await page.wait_for_timeout(500)
        value = await password_input.input_value()
        print(f"      ✅ 已输入: {'*' * len(value)}\n")
        
        # 6. 查找并点击登录按钮
        print("🖱️  [6/8] 查找登录按钮...")
        
        # 尝试多个选择器
        selectors = [
            "button:has-text('立即登录')",
            "button:has-text('登录')",
            "button.login-button",
            ".login-button"
        ]
        
        login_btn = None
        for selector in selectors:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    login_btn = btn
                    print(f"      ✅ 找到按钮: {selector}")
                    break
            except:
                continue
        
        if not login_btn:
            print("      ❌ 未找到登录按钮\n")
            # 列出所有按钮
            buttons = await page.locator("button").all()
            print(f"      页面共有 {len(buttons)} 个按钮:")
            for i, btn in enumerate(buttons[:10]):
                try:
                    text = await btn.text_content()
                    print(f"        {i+1}. {text.strip()}")
                except:
                    pass
            return
        
        # 截图前状态
        await page.screenshot(path="data/temp/screenshots/before_login.png")
        print("      📸 登录前截图已保存\n")
        
        # 点击登录
        print("🖱️  [7/8] 点击登录按钮...")
        await login_btn.click()
        print("      ✅ 已点击\n")
        
        # 8. 等待响应
        print("⏳ [8/8] 等待登录响应...")
        await page.wait_for_timeout(3000)
        
        current_url = page.url
        print(f"      当前URL: {current_url}")
        
        # 截图后状态
        await page.screenshot(path="data/temp/screenshots/after_login.png")
        print("      📸 登录后截图已保存\n")
        
        # 检查是否有错误提示
        print("🔍 检查错误提示...")
        error_selectors = [
            ".error-message",
            ".jx-message--error",
            ".el-message--error",
            "[class*='error']",
            "text='用户名或密码错误'",
            "text='账号或密码错误'",
            "text='登录失败'"
        ]
        
        has_error = False
        for selector in error_selectors:
            try:
                error_elem = page.locator(selector).first
                if await error_elem.count() > 0 and await error_elem.is_visible():
                    error_text = await error_elem.text_content()
                    print(f"      ❌ 发现错误: {error_text}")
                    has_error = True
                    break
            except:
                continue
        
        if not has_error:
            print("      ✅ 未发现错误提示")
        
        # 检查是否跳转成功
        if "welcome" in current_url or ("sub_account/users" not in current_url and "login" not in current_url.lower()):
            print("\n✅ 登录成功！")
        else:
            print("\n⚠️  登录可能失败（URL未变化）")
            print("\n💡 可能原因:")
            print("   1. 用户名或密码错误")
            print("   2. 需要图形验证码")
            print("   3. 需要手机验证码")
            print("   4. 账号被限制登录")
        
        print("\n💡 浏览器将保持打开60秒，请手动检查页面状态...")
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
        if browser_mgr:
            await browser_mgr.close()
            print("✅ 浏览器已关闭\n")

if __name__ == "__main__":
    asyncio.run(debug_login())

