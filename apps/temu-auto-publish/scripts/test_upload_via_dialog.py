"""测试通过批量编辑对话框上传图片."""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright, Page


async def close_popups(page: Page) -> int:
    """关闭页面上的各种弹窗.

    Returns:
        关闭的弹窗数量
    """
    closed = 0

    # 常见的弹窗关闭按钮
    popup_buttons = [
        "text='我知道了'",
        "text='知道了'",
        "text='确定'",
        "text='关闭'",
        "text='我已知晓'",
        "text='跳过'",
        "text='下次再说'",
        "button:has-text('我已知晓')",
        "button:has-text('跳过')",
        ".el-dialog__headerbtn",
        ".jx-dialog__headerbtn",
        "button[aria-label='关闭']",
        "button[aria-label='Close']",
        ".el-icon-close",
    ]

    for selector in popup_buttons:
        try:
            locator = page.locator(selector)
            count = await locator.count()
            if count > 0:
                for i in range(count):
                    try:
                        btn = locator.nth(i)
                        if await btn.is_visible():
                            await btn.click(timeout=1000)
                            closed += 1
                            print(f"  关闭弹窗: {selector}")
                            await page.wait_for_timeout(300)
                    except Exception:
                        pass
        except Exception:
            pass

    return closed


async def navigate_to_collect_box(page: Page):
    """导航到 Temu 采集箱列表页."""
    # 正确的 URL
    target_url = "https://erp.91miaoshou.com/pddkj/collect_box/items"

    print(f"导航到: {target_url}")
    await page.goto(target_url)
    await page.wait_for_timeout(2000)

    # 关闭可能出现的弹窗
    print("检查并关闭弹窗...")
    for _ in range(5):  # 最多尝试 5 次
        closed = await close_popups(page)
        if closed == 0:
            break
        await page.wait_for_timeout(500)

    # 等待页面稳定
    await page.wait_for_timeout(1000)


async def test_upload_via_dialog():
    """测试通过批量编辑对话框上传图片."""
    image_path = "/Users/candy/beimeng_workspace/apps/temu-auto-publish/data/input/web_panel/packaging/20251201-165528_20251201_165616.jpg"

    if not Path(image_path).exists():
        print(f"图片不存在: {image_path}")
        return

    print(f"图片路径: {image_path}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 设置响应监听器
        upload_result = {}

        async def handle_response(response):
            if "uploadPictureFile" in response.url:
                try:
                    body = await response.json()
                    upload_result.update(body)
                    print(f"\n上传响应: {body}")
                except Exception as e:
                    print(f"解析响应失败: {e}")

        page.on("response", handle_response)

        # 先导航到首页让用户登录
        print("\n导航到首页...")
        await page.goto("https://erp.91miaoshou.com/")

        print("\n请在浏览器中登录，登录后按回车继续...")
        input()

        # 导航到采集箱并关闭弹窗
        await navigate_to_collect_box(page)

        # Step 1: 勾选第一个产品
        print("\nStep 1: 勾选第一个产品...")

        # 使用更精确的选择器找到表格中的复选框
        table_checkboxes = page.locator(
            "table input[type='checkbox'], "
            ".el-table input[type='checkbox'], "
            ".el-checkbox__input input"
        )
        checkbox_count = await table_checkboxes.count()
        print(f"找到 {checkbox_count} 个表格复选框")

        if checkbox_count > 1:
            # 尝试点击第二个复选框（跳过全选）
            for i in range(1, min(3, checkbox_count)):
                try:
                    checkbox = table_checkboxes.nth(i)
                    if await checkbox.is_visible():
                        is_checked = await checkbox.is_checked()
                        if not is_checked:
                            await checkbox.click()
                            print(f"已勾选第 {i} 个产品")
                            await page.wait_for_timeout(500)
                            break
                except Exception as e:
                    print(f"勾选失败: {e}")

        # Step 2: 点击批量编辑按钮
        print("\nStep 2: 点击批量编辑按钮...")

        # 尝试多种选择器
        batch_edit_selectors = [
            "button:has-text('批量编辑')",
            "text='批量编辑'",
            ".el-button:has-text('批量编辑')",
        ]

        clicked = False
        for selector in batch_edit_selectors:
            try:
                btn = page.locator(selector)
                if await btn.count() > 0 and await btn.first.is_visible():
                    await btn.first.click()
                    print(f"已点击: {selector}")
                    clicked = True
                    await page.wait_for_timeout(2000)
                    break
            except Exception as e:
                print(f"尝试 {selector} 失败: {e}")

        if not clicked:
            print("未能点击批量编辑按钮")

        # Step 3: 等待对话框出现
        print("\nStep 3: 等待对话框...")
        dialog_selectors = [
            ".el-dialog__wrapper:visible",
            ".el-dialog:visible",
            "[role='dialog']",
        ]

        dialog_found = False
        for selector in dialog_selectors:
            try:
                dialog = page.locator(selector)
                await dialog.first.wait_for(state="visible", timeout=3000)
                print(f"对话框已打开: {selector}")
                dialog_found = True
                break
            except Exception:
                pass

        if not dialog_found:
            print("未找到对话框")

        # Step 4: 查找文件上传 input
        print("\nStep 4: 查找文件上传组件...")
        file_inputs = page.locator('input[type="file"]')
        count = await file_inputs.count()
        print(f"找到 {count} 个文件上传 input")

        for i in range(count):
            inp = file_inputs.nth(i)
            name = await inp.get_attribute("name")
            accept = await inp.get_attribute("accept")
            print(f"  [{i}] name={name}, accept={accept}")

        if count == 0:
            print("没有找到上传组件")
            print("\n按回车关闭浏览器...")
            input()
            await browser.close()
            return

        # Step 5: 上传图片
        print(f"\nStep 5: 使用最后一个 input 上传图片...")
        await file_inputs.last.set_input_files(image_path)
        print("已设置文件，等待上传...")

        # 等待上传完成
        for i in range(50):
            await asyncio.sleep(0.1)
            if upload_result:
                break

        if upload_result:
            print(f"\n上传成功!")
            print(f"  result: {upload_result.get('result')}")
            print(f"  picturePath: {upload_result.get('picturePath')}")
        else:
            print("\n上传超时，未收到响应")

        # 关闭对话框
        print("\nStep 6: 关闭对话框...")
        await close_popups(page)

        print("\n按回车关闭浏览器...")
        input()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_upload_via_dialog())
