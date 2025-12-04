"""
抓取认领阶段筛选创建人员的 API 请求。

使用方法：
1. 运行此脚本
2. 在浏览器中手动执行以下操作：
   - 进入妙手采集箱页面
   - 选择创建人员下拉框，选择 "李英亮"
   - 点击搜索
   - 切换到 "未认领" tab
3. 脚本会捕获并显示相关的 API 请求
"""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

# 强制刷新输出
sys.stdout.reconfigure(line_buffering=True)


async def capture_filter_api():
    """捕获筛选创建人员的 API 请求。"""
    captured_requests: list[dict] = []

    async with async_playwright() as p:
        # 使用已有的浏览器配置
        profile_dir = Path.home() / ".playwright-profile"
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1400, "height": 900},
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        # 监听网络请求
        async def handle_request(request):
            url = request.url
            # 捕获相关的 API 请求
            if any(
                keyword in url
                for keyword in [
                    "searchDetailList",
                    "collectBox",
                    "getSubAccountList",
                    "owner",
                    "filter",
                ]
            ):
                try:
                    post_data = request.post_data
                    captured_requests.append(
                        {
                            "url": url,
                            "method": request.method,
                            "post_data": post_data,
                        }
                    )
                    print(f"\n{'=' * 60}")
                    print(f"[捕获] {request.method} {url}")
                    if post_data:
                        print(f"POST 数据: {post_data}")
                except Exception as e:
                    print(f"捕获请求失败: {e}")

        async def handle_response(response):
            url = response.url
            if any(
                keyword in url
                for keyword in [
                    "searchDetailList",
                    "collectBox",
                    "getSubAccountList",
                ]
            ):
                try:
                    body = await response.json()
                    print(f"\n[响应] {url}")
                    # 只打印关键信息
                    if "detailList" in body:
                        items = body.get("detailList", [])
                        print(f"  返回 {len(items)} 个产品")
                        if items:
                            sample = items[0]
                            print(
                                f"  示例 ownerSubAccountAliasName: {sample.get('ownerSubAccountAliasName')}"
                            )
                    elif "list" in body.get("data", {}):
                        items = body["data"]["list"]
                        print(f"  返回 {len(items)} 个产品")
                        if items:
                            sample = items[0]
                            print(
                                f"  示例 ownerSubAccountAliasName: {sample.get('ownerSubAccountAliasName')}"
                            )
                    else:
                        # 打印完整响应（如果是小数据）
                        text = json.dumps(body, ensure_ascii=False, indent=2)
                        if len(text) < 2000:
                            print(f"  响应: {text}")
                except Exception:
                    pass

        page.on("request", handle_request)
        page.on("response", handle_response)

        # 导航到采集箱页面
        print("正在打开妙手采集箱页面...")
        await page.goto(
            "https://erp.91miaoshou.com/collect_box/common_collect_box",
            wait_until="networkidle",
        )

        print("\n" + "=" * 60)
        print("请在浏览器中执行以下操作：")
        print("1. 选择创建人员下拉框，选择目标人员（如 '李英亮'）")
        print("2. 点击搜索按钮")
        print("3. 切换到 '未认领' tab")
        print("4. 观察控制台输出的 API 请求")
        print("=" * 60)
        print("\n等待 60 秒，请在此期间手动操作浏览器...")
        print("操作完成后脚本会自动结束并保存结果。", flush=True)

        # 等待 60 秒让用户操作
        await asyncio.sleep(99999999999)

        # 保存捕获的请求
        if captured_requests:
            output_file = Path("scripts/captured_claim_filter_api.json")
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(captured_requests, f, ensure_ascii=False, indent=2)
            print(f"\n已保存 {len(captured_requests)} 个请求到 {output_file}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(capture_filter_api())
