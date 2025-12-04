"""测试图片上传功能 - 使用 input file 触发上传."""

import asyncio
import base64
from pathlib import Path

from playwright.async_api import async_playwright


async def test_upload():
    """测试通过 Playwright 的 set_input_files 上传图片."""
    image_path = "/Users/candy/beimeng_workspace/apps/temu-auto-publish/data/input/web_panel/packaging/20251201-165528_20251201_165616.jpg"

    if not Path(image_path).exists():
        print(f"图片不存在: {image_path}")
        return

    print(f"图片路径: {image_path}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 设置请求拦截，捕获上传请求的详细信息
        uploaded_url = None

        async def handle_response(response):
            nonlocal uploaded_url
            if "uploadPictureFile" in response.url:
                print(f"\n捕获到上传响应: {response.status}")
                try:
                    body = await response.json()
                    print(f"响应内容: {body}")
                    if body.get("result") == "success":
                        uploaded_url = body.get("picturePath")
                except Exception as e:
                    print(f"解析响应失败: {e}")

        page.on("response", handle_response)

        # 导航到妙手采集箱
        await page.goto("https://erp.91miaoshou.com/pddkj/collect_box/items")

        print("\n请在浏览器中登录，然后进入任意产品的编辑页面")
        print("按回车继续...")
        input()

        await page.wait_for_timeout(2000)

        # 尝试找到页面上的文件上传 input
        print("\n查找文件上传 input...")

        # 创建一个隐藏的 file input 并触发上传
        result = await page.evaluate(
            """
            async (imagePath) => {
                // 查找页面上现有的上传组件
                const uploadInputs = document.querySelectorAll('input[type="file"]');
                console.log('找到', uploadInputs.length, '个文件上传 input');

                // 查找上传按钮或区域
                const uploadAreas = document.querySelectorAll('[class*="upload"], [class*="Upload"]');
                console.log('找到', uploadAreas.length, '个上传区域');

                return {
                    inputCount: uploadInputs.length,
                    uploadAreaCount: uploadAreas.length,
                    inputs: Array.from(uploadInputs).map(input => ({
                        id: input.id,
                        name: input.name,
                        accept: input.accept,
                        className: input.className
                    }))
                };
            }
            """
        )
        print(f"页面上传元素: {result}")

        # 如果有文件 input，使用 Playwright 的 set_input_files
        if result["inputCount"] > 0:
            print(f"\n尝试使用 set_input_files 上传...")

            # 找到第一个 file input
            file_inputs = page.locator('input[type="file"]')
            count = await file_inputs.count()
            print(f"找到 {count} 个文件 input")

            if count > 0:
                # 使用 set_input_files
                await file_inputs.first.set_input_files(image_path)
                print("已设置文件，等待上传...")

                # 等待上传完成
                await page.wait_for_timeout(3000)

                if uploaded_url:
                    print(f"\n上传成功！URL: {uploaded_url}")
                else:
                    print("\n未捕获到成功的上传响应")

        print("\n按回车关闭浏览器...")
        input()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_upload())
