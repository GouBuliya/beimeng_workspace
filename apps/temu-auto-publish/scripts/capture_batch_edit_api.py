"""
@PURPOSE: 抓取二次编辑（批量编辑）的网络请求，分析 API 端点
@OUTLINE:
  - capture_requests(): 主函数，抓取并分析 API 请求
  - _setup_request_listener(): 设置请求监听器
  - _execute_batch_edit_steps(): 执行批量编辑操作
  - _analyze_requests(): 分析并输出请求
@DEPENDENCIES:
  - 外部: playwright
  - 内部: ..src.browser.cookie_manager
"""

import asyncio
import contextlib
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from playwright.async_api import Page, Request, Response, async_playwright
from src.browser.cookie_manager import CookieManager

# 收集的请求
captured_requests: list[dict] = []


async def _on_request(request: Request) -> None:
    """请求拦截器."""
    url = request.url
    # 只关注 API 请求
    if "/api/" in url or "erp.91miaoshou.com" in url:
        req_data = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": url,
            "post_data": None,
            "response": None,
        }
        # 获取 POST 数据
        if request.method == "POST":
            with contextlib.suppress(Exception):
                req_data["post_data"] = request.post_data
        captured_requests.append(req_data)


async def _on_response(response: Response) -> None:
    """响应拦截器."""
    url = response.url
    if "/api/" in url:
        # 找到对应的请求并更新响应
        for req in reversed(captured_requests):
            if req["url"] == url and req["response"] is None:
                try:
                    req["response"] = {
                        "status": response.status,
                        "body": await response.text() if response.status == 200 else None,
                    }
                except Exception as e:
                    req["response"] = {"status": response.status, "error": str(e)}
                break


async def _execute_batch_edit_steps(page: Page) -> None:
    """执行批量编辑操作的关键步骤."""
    print("\n=== 开始执行批量编辑操作 ===\n")

    # Step 1: 导航到 Temu 采集箱页面
    print("Step 1: 导航到 Temu 采集箱页面...")
    await page.goto("https://erp.91miaoshou.com/pddkj/collect_box/items")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)

    # Step 2: 关闭可能的弹窗（多次尝试）
    print("Step 2: 关闭弹窗...")
    for _attempt in range(5):
        try:
            # 尝试多种关闭按钮选择器
            close_selectors = [
                "button.el-dialog__headerbtn",
                ".jx-dialog__headerbtn",
                ".jx-overlay-dialog button.jx-dialog__headerbtn",
                "button[aria-label='Close']",
                ".el-icon-close",
                ".jx-overlay .jx-icon-close",
            ]
            for selector in close_selectors:
                close_btn = page.locator(selector).first
                if await close_btn.is_visible(timeout=500):
                    await close_btn.click(force=True)
                    print(f"  关闭弹窗成功: {selector}")
                    await page.wait_for_timeout(500)
                    break
        except Exception:
            pass
        await page.wait_for_timeout(300)

    # Step 3: 等待商品列表加载
    print("Step 3: 等待商品列表...")
    try:
        await page.wait_for_selector(".pro-virtual-table__row-body", timeout=10000)
    except Exception:
        print("  警告: 未找到商品行，尝试继续...")

    # Step 4: 全选商品
    print("Step 4: 全选商品...")
    try:
        checkbox = page.locator(".jx-checkbox").first
        await checkbox.click(force=True, timeout=5000)
        await page.wait_for_timeout(500)
    except Exception as e:
        print(f"  警告: 全选失败 - {e}")
        print("  请手动全选商品...")

    # Step 5: 点击批量编辑按钮
    print("Step 5: 点击批量编辑按钮...")
    try:
        batch_edit_btn = page.get_by_text("批量编辑", exact=True).first
        await batch_edit_btn.click()
        await page.wait_for_timeout(1500)
    except Exception as e:
        print(f"  错误: 无法点击批量编辑 - {e}")
        return

    # Step 6: 执行几个关键编辑步骤（用于抓取 API）
    edit_steps = [
        ("标题", "标题"),
        ("英语标题", "英语标题"),
        ("类目属性", "类目属性"),
        ("主货号", "主货号"),
        ("产地", "产地"),
    ]

    for step_name, btn_text in edit_steps:
        print(f"Step 6.x: 点击 {step_name}...")
        try:
            # 找到对应的按钮
            btn = page.get_by_text(btn_text, exact=True).first
            if await btn.is_visible(timeout=2000):
                await btn.click()
                await page.wait_for_timeout(1000)

                # 尝试点击确定按钮
                confirm_btn = page.locator("button:has-text('确定')").first
                if await confirm_btn.is_visible(timeout=2000):
                    await confirm_btn.click()
                    await page.wait_for_timeout(500)
        except Exception as e:
            print(f"  步骤 {step_name} 失败: {e}")

    print("\n=== 批量编辑操作完成 ===\n")


def _analyze_requests() -> None:
    """分析并输出抓取的请求."""
    print("\n" + "=" * 60)
    print("API 请求分析报告")
    print("=" * 60)

    # 过滤出 API 请求
    api_requests = [r for r in captured_requests if "/api/" in r["url"]]

    print(f"\n共抓取 {len(captured_requests)} 个请求，其中 {len(api_requests)} 个 API 请求\n")

    # 按 URL 分组
    url_groups: dict[str, list[dict]] = {}
    for req in api_requests:
        parsed = urlparse(req["url"])
        path = parsed.path
        if path not in url_groups:
            url_groups[path] = []
        url_groups[path].append(req)

    # 输出每个 API 端点
    for path, reqs in sorted(url_groups.items()):
        print(f"\n{'─' * 50}")
        print(f"端点: {path}")
        print(f"调用次数: {len(reqs)}")

        for i, req in enumerate(reqs[:3]):  # 只显示前3个
            print(f"\n  请求 #{i + 1}:")
            print(f"    方法: {req['method']}")
            print(f"    时间: {req['timestamp']}")

            if req["post_data"]:
                # 尝试解析 POST 数据
                post_data = req["post_data"]
                if isinstance(post_data, str):
                    # 尝试 URL 编码格式
                    try:
                        parsed_data = parse_qs(post_data)
                        print("    POST 数据 (URL 编码):")
                        for k, v in list(parsed_data.items())[:10]:
                            print(f"      {k}: {v[0][:100] if v else ''}")
                    except Exception:
                        # 尝试 JSON 格式
                        try:
                            json_data = json.loads(post_data)
                            print("    POST 数据 (JSON):")
                            print(
                                f"      {json.dumps(json_data, indent=6, ensure_ascii=False)[:500]}"
                            )
                        except Exception:
                            print(f"    POST 数据 (原始): {post_data[:200]}")

            if req["response"]:
                resp = req["response"]
                print(f"    响应状态: {resp.get('status')}")
                if resp.get("body"):
                    try:
                        body = json.loads(resp["body"])
                        print(f"    响应体: {json.dumps(body, indent=6, ensure_ascii=False)[:300]}")
                    except Exception:
                        print(f"    响应体: {resp['body'][:200]}")

    # 保存完整结果到文件
    output_file = project_root / "scripts" / "captured_api_requests.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(captured_requests, f, ensure_ascii=False, indent=2)
    print(f"\n完整请求已保存到: {output_file}")


async def capture_requests() -> None:
    """主函数：抓取二次编辑的网络请求."""
    cookie_file = project_root.parent.parent / "data/temp/miaoshou_cookies.json"
    manager = CookieManager(str(cookie_file))
    cookies = manager.load_playwright_cookies()

    if not cookies:
        print("错误: 无法加载 Cookie，请先登录妙手 ERP")
        return

    print(f"已加载 {len(cookies)} 个 Cookie")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        await context.add_cookies(cookies)

        page = await context.new_page()

        # 设置请求监听器
        page.on("request", _on_request)
        page.on("response", _on_response)

        print("已设置网络请求监听器")

        # 执行批量编辑操作
        await _execute_batch_edit_steps(page)

        # 等待用户查看或手动操作
        print("\n" + "=" * 60)
        print("浏览器已打开，请手动执行以下操作以抓取 API：")
        print("1. 关闭任何弹窗")
        print("2. 全选商品（点击表头复选框）")
        print("3. 点击「批量编辑」按钮")
        print("4. 依次点击每个编辑步骤的「确定」按钮")
        print("5. 完成后脚本会自动分析抓取的 API")
        print("=" * 60)
        print("\n浏览器将保持打开 120 秒...")
        await page.wait_for_timeout(120000)

        await browser.close()

    # 分析请求
    _analyze_requests()


if __name__ == "__main__":
    asyncio.run(capture_requests())
