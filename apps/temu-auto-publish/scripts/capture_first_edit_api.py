"""
捕获"首次编辑"相关的所有 API 请求。

使用方法：
1. 运行此脚本: uv run python scripts/capture_first_edit_api.py
2. 在浏览器中手动执行以下操作：
   - 登录妙手 ERP（如果需要）
   - 进入采集箱页面
   - 筛选创建人员（可选）
   - 点击任意产品的"编辑"按钮，打开首次编辑弹窗
   - 在弹窗中进行各种操作：
     * 修改标题
     * 修改规格名称/规格选项
     * 修改价格、库存、重量、尺寸
     * 上传尺寸图（通过网络图片 URL）
     * 上传视频（通过网络视频 URL）
     * 点击保存
   - 可以对多个产品重复上述操作
3. 操作完成后按 Ctrl+C 结束脚本，API 请求会保存到 JSON 文件

捕获的 API 类型：
- 采集箱搜索相关
- 产品信息获取
- 产品信息保存
- 视频 URL 注册
- 图片上传相关
- 规格/属性相关
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright

# 强制刷新输出
sys.stdout.reconfigure(line_buffering=True)

# 输出文件路径
OUTPUT_DIR = Path("data/debug")
OUTPUT_FILE = OUTPUT_DIR / f"captured_first_edit_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

# 要捕获的 API 关键词
CAPTURE_KEYWORDS = [
    # 采集箱相关
    "collectBox",
    "searchCollectBoxDetail",
    "getCollectItemInfo",
    "saveCollectItemInfo",
    # 视频相关
    "video",
    "getVideoUrlAndStatusMap",
    # 图片相关
    "image",
    "upload",
    "oss",
    # 规格/属性相关
    "sku",
    "spec",
    "attribute",
    "saleAttribute",
    # 类目相关
    "category",
    "cid",
    # 其他可能相关
    "save",
    "edit",
    "update",
]

# 排除的 URL 模式（减少噪音）
EXCLUDE_PATTERNS = [
    "analytics",
    "tracking",
    "log",
    "monitor",
    ".png",
    ".jpg",
    ".gif",
    ".css",
    ".js",
    "favicon",
    "hot-update",
]


async def capture_first_edit_api():
    """捕获首次编辑相关的 API 请求。"""
    captured_requests: list[dict] = []
    request_count = 0

    async with async_playwright() as p:
        # 使用已有的浏览器配置（保持登录状态）
        profile_dir = Path.home() / ".playwright-profile"
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1400, "height": 900},
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        def should_capture(url: str) -> bool:
            """判断是否应该捕获该 URL。"""
            # 排除静态资源和跟踪请求
            url_lower = url.lower()
            if any(pattern in url_lower for pattern in EXCLUDE_PATTERNS):
                return False
            # 只捕获 API 请求
            if not any(keyword.lower() in url_lower for keyword in CAPTURE_KEYWORDS):
                return False
            return True

        async def handle_request(request):
            nonlocal request_count
            url = request.url

            if not should_capture(url):
                return

            try:
                post_data = request.post_data
                headers = dict(request.headers)

                request_info = {
                    "timestamp": datetime.now().isoformat(),
                    "index": request_count,
                    "url": url,
                    "method": request.method,
                    "post_data": post_data,
                    "headers": {
                        k: v
                        for k, v in headers.items()
                        if k.lower() in ["content-type", "cookie", "authorization"]
                    },
                }
                captured_requests.append(request_info)
                request_count += 1

                # 打印捕获信息
                print(f"\n{'=' * 70}")
                print(f"[#{request_count}] {request.method} {url}")
                if post_data:
                    # 尝试美化 JSON
                    try:
                        if "application/json" in headers.get("content-type", ""):
                            parsed = json.loads(post_data)
                            print(f"POST JSON:\n{json.dumps(parsed, ensure_ascii=False, indent=2)[:500]}")
                        else:
                            print(f"POST 数据: {post_data[:500]}")
                    except Exception:
                        print(f"POST 数据: {post_data[:500]}")

            except Exception as e:
                print(f"捕获请求失败: {e}")

        async def handle_response(response):
            url = response.url

            if not should_capture(url):
                return

            try:
                # 尝试获取响应体
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = await response.json()

                    # 更新对应请求的响应
                    for req in reversed(captured_requests):
                        if req["url"] == url and "response" not in req:
                            req["response"] = {
                                "status": response.status,
                                "body": body,
                            }
                            break

                    # 打印响应摘要
                    print(f"\n[响应] {response.status} {url}")

                    # 打印关键信息
                    if isinstance(body, dict):
                        result = body.get("result", body.get("code", ""))
                        message = body.get("message", body.get("msg", ""))
                        print(f"  结果: {result}, 消息: {message}")

                        # 特殊处理一些已知的响应格式
                        if "detailList" in body:
                            items = body.get("detailList", [])
                            print(f"  产品列表: {len(items)} 个")
                        if "collectItemInfoList" in body:
                            items = body.get("collectItemInfoList", [])
                            print(f"  编辑信息: {len(items)} 个产品")
                        if "skuMap" in body:
                            print(f"  SKU Map 字段存在")
                        if "successNum" in body or "failNum" in body:
                            print(f"  成功: {body.get('successNum', 0)}, 失败: {body.get('failNum', 0)}")

                        # 打印完整响应（如果较小）
                        text = json.dumps(body, ensure_ascii=False)
                        if len(text) < 1000:
                            print(f"  完整响应: {text}")
                        else:
                            print(f"  响应长度: {len(text)} 字符 (已截断)")

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

        print("\n" + "=" * 70)
        print("首次编辑 API 捕获脚本已启动")
        print("=" * 70)
        print("\n请在浏览器中执行以下操作：")
        print("")
        print("1. 【筛选产品】")
        print("   - 选择创建人员（可选）")
        print("   - 切换到需要的 Tab（如 '已认领'）")
        print("")
        print("2. 【打开首次编辑弹窗】")
        print("   - 点击任意产品的 '编辑' 按钮")
        print("")
        print("3. 【在弹窗中操作】")
        print("   - 修改标题")
        print("   - 修改规格名称/规格选项（如果有）")
        print("   - 修改价格、库存、重量、尺寸")
        print("   - 上传尺寸图（通过网络图片 URL）")
        print("   - 上传视频（通过网络视频 URL）")
        print("")
        print("4. 【保存并观察】")
        print("   - 点击保存按钮")
        print("   - 观察控制台输出的 API 请求")
        print("")
        print("5. 【结束捕获】")
        print("   - 可以对多个产品重复操作")
        print("   - 操作完成后按 Ctrl+C 结束脚本")
        print("")
        print("=" * 70)
        print(f"捕获结果将保存到: {OUTPUT_FILE}")
        print("=" * 70)
        print("\n等待操作... (按 Ctrl+C 结束)", flush=True)

        try:
            # 无限等待，直到用户按 Ctrl+C
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

        # 保存捕获的请求
        save_captured_requests(captured_requests)
        await browser.close()


def save_captured_requests(captured_requests: list[dict]):
    """保存捕获的请求到文件。"""
    if not captured_requests:
        print("\n没有捕获到任何 API 请求")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 保存完整数据
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(captured_requests, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print(f"已保存 {len(captured_requests)} 个 API 请求到: {OUTPUT_FILE}")

    # 打印摘要
    print("\n捕获的 API 摘要：")
    api_summary: dict[str, int] = {}
    for req in captured_requests:
        # 提取 API 路径
        url = req["url"]
        path = url.split("?")[0].split("/")[-1] if "/" in url else url
        api_summary[path] = api_summary.get(path, 0) + 1

    for api, count in sorted(api_summary.items(), key=lambda x: -x[1]):
        print(f"  {api}: {count} 次")

    print("=" * 70)


def main():
    try:
        asyncio.run(capture_first_edit_api())
    except KeyboardInterrupt:
        print("\n\n用户中断，正在保存...")
        # 注意：这里无法访问 captured_requests，需要在 async 函数中处理


if __name__ == "__main__":
    main()
