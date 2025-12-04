"""捕获浏览器上传请求的详细信息."""

import asyncio

from playwright.async_api import async_playwright


async def capture_upload():
    """打开浏览器并捕获上传请求."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 设置请求拦截
        async def handle_request(request):
            if "uploadPictureFile" in request.url:
                print("\n" + "=" * 60)
                print("捕获到上传请求!")
                print("=" * 60)
                print(f"URL: {request.url}")
                print(f"Method: {request.method}")
                print(f"\nHeaders:")
                for key, value in request.headers.items():
                    print(f"  {key}: {value[:100] if len(value) > 100 else value}")

                # 尝试获取 post_data
                post_data = request.post_data
                if post_data:
                    print(f"\nPost Data (前500字符): {post_data[:500]}")
                    print(f"Post Data 长度: {len(post_data)}")

                # post_data_buffer
                try:
                    post_buffer = request.post_data_buffer
                    if post_buffer:
                        print(f"\nPost Buffer 长度: {len(post_buffer)} bytes")
                        # 查找 multipart boundary
                        content_type = request.headers.get("content-type", "")
                        print(f"Content-Type: {content_type}")
                except Exception as e:
                    print(f"获取 post buffer 失败: {e}")

        async def handle_response(response):
            if "uploadPictureFile" in response.url:
                print("\n" + "-" * 60)
                print("上传响应:")
                print("-" * 60)
                print(f"Status: {response.status}")
                try:
                    body = await response.json()
                    print(f"Response: {body}")
                except Exception:
                    text = await response.text()
                    print(f"Response Text: {text[:500]}")

        page.on("request", handle_request)
        page.on("response", handle_response)

        # 导航到妙手
        await page.goto("https://erp.91miaoshou.com/common_collect_box/items")

        print("\n" + "=" * 60)
        print("请在浏览器中:")
        print("1. 登录账号")
        print("2. 进入编辑页面")
        print("3. 手动上传一张外包装图片")
        print("=" * 60)
        print("\n观察控制台输出，查看上传请求的详细信息")
        print("完成后按回车退出...")

        input()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(capture_upload())
