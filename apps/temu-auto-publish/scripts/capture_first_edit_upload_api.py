"""
@PURPOSE: 抓取首次编辑弹窗的图片/视频上传 API 请求，用于逆向分析
@OUTLINE:
  - capture_upload_requests(): 主函数，抓取上传相关 API
  - _on_request(): 请求拦截器（捕获完整请求头）
  - _on_response(): 响应拦截器（捕获响应头和响应体）
  - _execute_first_edit_steps(): 自动执行上传操作
  - _auto_upload_size_chart(): 自动上传尺寸图
  - _auto_upload_video(): 自动上传视频
  - _analyze_upload_requests(): 分析并输出上传相关请求
@DEPENDENCIES:
  - 外部: playwright
  - 内部: ..src.browser.cookie_manager
@RELATED: capture_batch_edit_api.py, api_client.py, first_edit_dialog_codegen.py
"""

import asyncio
import contextlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from playwright.async_api import Locator, Page, Request, Response, async_playwright

from src.browser.cookie_manager import CookieManager

# 测试用的图片和视频 URL
TEST_SIZE_CHART_URL = (
    "https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/images/size_chart_test.jpg"
)
TEST_VIDEO_URL = (
    "https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/video/test_video.mp4"
)
TEST_SKU_IMAGE_URL = (
    "https://miaoshou-tuchuang-beimeng.oss-cn-hangzhou.aliyuncs.com/images/sku_test.jpg"
)

# 收集的请求
captured_requests: list[dict] = []

# 上传相关 API 关键词
UPLOAD_KEYWORDS = [
    "upload",
    "image",
    "video",
    "picture",
    "media",
    "file",
    "size",
    "chart",
    "sku",
    "save",
    "update",
    "edit",
    "collect",
]


def _is_upload_related(url: str) -> bool:
    """判断 URL 是否与上传相关."""
    url_lower = url.lower()
    return any(kw in url_lower for kw in UPLOAD_KEYWORDS)


async def _on_request(request: Request) -> None:
    """请求拦截器 - 捕获完整请求信息（含 Headers）."""
    url = request.url
    # 只关注 API 请求
    if "/api/" in url or "erp.91miaoshou.com" in url:
        req_data = {
            "timestamp": datetime.now().isoformat(),
            "method": request.method,
            "url": url,
            "headers": dict(request.headers),  # 完整请求头
            "post_data": None,
            "post_data_parsed": None,
            "response": None,
            "is_upload_related": _is_upload_related(url),
        }
        # 获取 POST/PUT 数据
        if request.method in ("POST", "PUT", "PATCH"):
            with contextlib.suppress(Exception):
                post_data = request.post_data
                req_data["post_data"] = post_data
                # 尝试解析
                if post_data:
                    try:
                        req_data["post_data_parsed"] = json.loads(post_data)
                    except json.JSONDecodeError:
                        try:
                            req_data["post_data_parsed"] = parse_qs(post_data)
                        except Exception:
                            pass
        captured_requests.append(req_data)


async def _on_response(response: Response) -> None:
    """响应拦截器 - 捕获响应信息（含 Headers）."""
    url = response.url
    if "/api/" in url or "erp.91miaoshou.com" in url:
        # 找到对应的请求并更新响应
        for req in reversed(captured_requests):
            if req["url"] == url and req["response"] is None:
                try:
                    body = None
                    body_parsed = None
                    if response.status == 200:
                        body = await response.text()
                        try:
                            body_parsed = json.loads(body)
                        except Exception:
                            pass
                    req["response"] = {
                        "status": response.status,
                        "headers": dict(response.headers),  # 完整响应头
                        "body": body,
                        "body_parsed": body_parsed,
                    }
                except Exception as e:
                    req["response"] = {"status": response.status, "error": str(e)}
                break


async def _close_popups(page: Page) -> None:
    """关闭可能的弹窗."""
    for _attempt in range(5):
        try:
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
                    print(f"  关闭弹窗: {selector}")
                    await page.wait_for_timeout(500)
                    break
        except Exception:
            pass
        await page.wait_for_timeout(300)


async def _first_visible(candidates: list[Locator | None], timeout: int = 2000) -> Locator | None:
    """从候选列表中返回第一个可见的 Locator."""
    for loc in candidates:
        if loc is None:
            continue
        try:
            await loc.wait_for(state="visible", timeout=timeout)
            return loc
        except Exception:
            continue
    return None


async def _auto_upload_size_chart(page: Page, image_url: str) -> bool:
    """自动执行尺寸图上传操作."""
    print("\n  [尺寸图上传] 开始...")

    try:
        # 定位尺寸图分组
        size_group_selectors = [
            page.get_by_role("group", name="尺寸图表 :", exact=True),
            page.get_by_role("group", name=re.compile("尺寸图")),
            page.locator("[class*='size-chart'], [class*='sizeChart']"),
            page.locator("text=尺寸图表").locator(".."),
        ]

        size_group = None
        for selector in size_group_selectors:
            try:
                if await selector.count():
                    size_group = selector.first
                    print("    找到尺寸图分组")
                    break
            except Exception:
                continue

        if size_group is None:
            print("    警告: 未找到尺寸图分组")
            return False

        await size_group.scroll_into_view_if_needed()

        # 点击"添加新图片"按钮
        add_image_selectors = [
            size_group.locator(".product-picture-item-add"),
            size_group.locator(".add-image-box .add-image-box-content"),
            size_group.locator(".add-image-box"),
            size_group.get_by_text("添加新图片", exact=False),
        ]

        add_clicked = False
        for selector in add_image_selectors:
            try:
                if await selector.count():
                    await selector.first.click()
                    add_clicked = True
                    print("    点击了『添加新图片』")
                    await page.wait_for_timeout(500)
                    break
            except Exception:
                continue

        if not add_clicked:
            print("    警告: 未能点击添加按钮")
            return False

        # 点击"使用网络图片"
        upload_btn_selectors = [
            page.get_by_text("使用网络图片", exact=True),
            page.get_by_text("使用网络图片", exact=False).first,
            page.locator(".jx-dropdown-menu").get_by_text("使用网络图片"),
        ]

        upload_btn = await _first_visible(upload_btn_selectors, timeout=2000)
        if upload_btn is None:
            print("    警告: 未找到『使用网络图片』按钮")
            return False

        await upload_btn.click()
        print("    点击了『使用网络图片』")
        await page.wait_for_timeout(500)

        # 填写 URL
        url_input_selectors = [
            page.get_by_role("textbox", name=re.compile("请输入图片链接")),
            page.get_by_role("textbox", name=re.compile("图片链接|图片URL")),
            page.locator("input[placeholder*='图片链接'], textarea[placeholder*='图片链接']"),
            page.locator(".jx-dialog, .el-dialog, [role='dialog']")
            .locator("input[type='text'], textarea")
            .first,
        ]

        url_input = await _first_visible(url_input_selectors, timeout=2000)
        if url_input is None:
            print("    警告: 未找到 URL 输入框")
            return False

        await url_input.click()
        await url_input.fill(image_url)
        print(f"    填写了 URL: {image_url[:50]}...")

        # 取消勾选"同时保存图片到妙手图片空间"
        try:
            checkbox = page.get_by_text("同时保存图片到妙手图片空间", exact=False)
            if await checkbox.count():
                await checkbox.click()
                print("    取消勾选保存到图片空间")
        except Exception:
            pass

        # 点击确定
        confirm_btn_selectors = [
            page.get_by_role("button", name="确定"),
            page.get_by_role("button", name=re.compile("确定|确认")),
            page.locator("button:has-text('确定')"),
        ]

        confirm_btn = await _first_visible(confirm_btn_selectors, timeout=2000)
        if confirm_btn:
            await confirm_btn.click()
            print("    点击了『确定』")
            await page.wait_for_timeout(2000)  # 等待上传完成
            print("  [尺寸图上传] 完成 ✓")
            return True
        else:
            print("    警告: 未找到确定按钮")
            return False

    except Exception as e:
        print(f"  [尺寸图上传] 失败: {e}")
        return False


async def _auto_upload_video(page: Page, video_url: str) -> bool:
    """自动执行视频上传操作."""
    print("\n  [视频上传] 开始...")

    try:
        # 定位产品视频分组
        video_group_selectors = [
            page.get_by_role("group", name="产品视频 :", exact=True),
            page.get_by_role("group", name="产品视频", exact=False),
            page.get_by_role("group", name=re.compile(r"产品视频|商品视频")),
            page.locator("[class*='video-group'], [class*='videoGroup']"),
        ]

        video_group = None
        for selector in video_group_selectors:
            try:
                if await selector.count():
                    video_group = selector.first
                    print("    找到产品视频分组")
                    break
            except Exception:
                continue

        if video_group is None:
            print("    警告: 未找到产品视频分组")
            return False

        await video_group.scroll_into_view_if_needed()

        # 点击视频区域
        try:
            video_wrap = video_group.locator(".video-wrap").first
            if await video_wrap.count():
                await video_wrap.click()
                print("    点击了视频区域")
            else:
                await video_group.get_by_role("img").first.click()
        except Exception as e:
            print(f"    警告: 点击视频区域失败 - {e}")

        await page.wait_for_timeout(500)

        # 点击"网络上传"
        network_upload_selectors = [
            page.get_by_text("网络上传", exact=True),
            page.get_by_text("网络上传", exact=False).first,
            page.get_by_role("button", name=re.compile(r"网络上传|网络视频")),
            page.get_by_role("menuitem", name=re.compile(r"网络上传|网络视频")),
        ]

        network_btn = await _first_visible(network_upload_selectors, timeout=2000)
        if network_btn is None:
            print("    警告: 未找到『网络上传』按钮")
            return False

        await network_btn.click()
        print("    点击了『网络上传』")
        await page.wait_for_timeout(500)

        # 填写视频 URL
        video_input_selectors = [
            page.get_by_role("textbox", name=re.compile("输入视频URL地址", re.IGNORECASE)),
            page.get_by_role("textbox", name=re.compile("视频URL|视频链接", re.IGNORECASE)),
            page.locator("input[placeholder*='视频']"),
            page.locator("textarea[placeholder*='视频']"),
        ]

        video_input = await _first_visible(video_input_selectors, timeout=2000)
        if video_input is None:
            print("    警告: 未找到视频 URL 输入框")
            return False

        await video_input.click()
        await video_input.fill(video_url)
        print(f"    填写了 URL: {video_url[:50]}...")

        # 取消勾选保存到图片空间
        try:
            checkbox = page.get_by_text("同时保存图片到妙手图片空间", exact=False)
            if await checkbox.count():
                await checkbox.click()
                print("    取消勾选保存到图片空间")
        except Exception:
            pass

        # 点击确定
        confirm_btn_selectors = [
            page.get_by_role("button", name="确定"),
            page.get_by_role("button", name=re.compile("确定|确认")),
            page.locator("button:has-text('确定')").last,
        ]

        confirm_btn = await _first_visible(confirm_btn_selectors, timeout=2000)
        if confirm_btn:
            await confirm_btn.click()
            print("    点击了『确定』")
            await page.wait_for_timeout(3000)  # 视频上传可能需要更长时间
            print("  [视频上传] 完成 ✓")
            return True
        else:
            print("    警告: 未找到确定按钮")
            return False

    except Exception as e:
        print(f"  [视频上传] 失败: {e}")
        return False


async def _auto_upload_sku_image(page: Page, image_url: str) -> bool:
    """自动执行 SKU 图片上传操作."""
    print("\n  [SKU图片上传] 开始...")

    try:
        # 找到 SKU 表格
        sku_table = page.locator(".pro-virtual-table").first
        if not await sku_table.count():
            print("    警告: 未找到 SKU 表格")
            return False

        # 找到第一行
        rows = sku_table.locator(".pro-virtual-table__row-body")
        if not await rows.count():
            print("    警告: 未找到 SKU 行")
            return False

        row = rows.first
        print("    找到 SKU 表格第一行")

        # 找到图片区域的添加按钮
        add_selectors = [
            row.locator(".picture-draggable-list .add-image-box").first,
            row.locator(".add-image-box").first,
            row.locator(".product-picture-item-add").first,
        ]

        add_btn = None
        for selector in add_selectors:
            try:
                if await selector.count():
                    add_btn = selector
                    break
            except Exception:
                continue

        if add_btn is None:
            print("    警告: 未找到 SKU 图片添加按钮")
            return False

        await add_btn.click()
        print("    点击了添加按钮")
        await page.wait_for_timeout(500)

        # 点击"使用网络图片"
        upload_btn = await _first_visible(
            [
                page.get_by_text("使用网络图片", exact=True),
                page.get_by_text("使用网络图片", exact=False).first,
            ],
            timeout=2000,
        )

        if upload_btn is None:
            print("    警告: 未找到『使用网络图片』按钮")
            return False

        await upload_btn.click()
        print("    点击了『使用网络图片』")
        await page.wait_for_timeout(500)

        # 填写 URL
        url_input = await _first_visible(
            [
                page.get_by_role("textbox", name=re.compile("请输入图片链接")),
                page.locator("input[placeholder*='图片链接'], textarea[placeholder*='图片链接']"),
                page.locator(".jx-dialog input[type='text'], .jx-dialog textarea").first,
            ],
            timeout=2000,
        )

        if url_input is None:
            print("    警告: 未找到 URL 输入框")
            return False

        await url_input.fill(image_url)
        print(f"    填写了 URL: {image_url[:50]}...")

        # 点击确定
        confirm_btn = await _first_visible(
            [
                page.get_by_role("button", name="确定"),
                page.locator("button:has-text('确定')"),
            ],
            timeout=2000,
        )

        if confirm_btn:
            await confirm_btn.click()
            print("    点击了『确定』")
            await page.wait_for_timeout(2000)
            print("  [SKU图片上传] 完成 ✓")
            return True
        else:
            print("    警告: 未找到确定按钮")
            return False

    except Exception as e:
        print(f"  [SKU图片上传] 失败: {e}")
        return False


async def _execute_first_edit_steps(page: Page) -> None:
    """等待用户手动执行上传操作."""
    print("\n" + "=" * 60)
    print("首次编辑上传 API 抓取工具 (手动模式)")
    print("=" * 60)

    # 导航到 Temu 采集箱页面
    print("\n正在导航到 Temu 采集箱页面...")
    await page.goto("https://erp.91miaoshou.com/pddkj/collect_box/items")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)

    # 关闭可能的弹窗
    await _close_popups(page)

    print("\n" + "=" * 60)
    print("请手动执行以下操作：")
    print("=" * 60)
    print("""
1. 选择一个商品 → 点击「首次编辑」

2. 尺寸图上传：
   - 找到「尺寸图表」→「添加新图片」→「使用网络图片」
   - 填写 URL → 确定

3. 视频上传：
   - 找到「产品视频」→ 点击 →「网络上传」
   - 填写 URL → 确定

4. SKU 图片上传：
   - 找到 SKU 表格某行 →「添加新图片」→「使用网络图片」
   - 填写 URL → 确定

完成后按 Ctrl+C 结束抓取
""")
    print("=" * 60)
    print("\n等待操作中... (5 分钟超时)")

    await page.wait_for_timeout(300000)  # 5 分钟


def _analyze_upload_requests() -> None:
    """分析并输出上传相关的请求."""
    print("\n" + "=" * 60)
    print("上传 API 请求分析报告")
    print("=" * 60)

    # 过滤出 API 请求
    api_requests = [r for r in captured_requests if "/api/" in r["url"]]
    upload_requests = [r for r in api_requests if r.get("is_upload_related")]

    print(f"\n共抓取 {len(captured_requests)} 个请求")
    print(f"  - API 请求: {len(api_requests)} 个")
    print(f"  - 上传相关: {len(upload_requests)} 个")

    # 重点分析上传相关请求
    if upload_requests:
        print("\n" + "─" * 50)
        print("上传相关 API 详情")
        print("─" * 50)

        for i, req in enumerate(upload_requests):
            print(f"\n[{i + 1}] {req['method']} {req['url']}")
            print(f"    时间: {req['timestamp']}")

            # 请求头（重点关注认证相关）
            headers = req.get("headers", {})
            auth_headers = {
                k: v
                for k, v in headers.items()
                if k.lower()
                in (
                    "cookie",
                    "authorization",
                    "x-csrf-token",
                    "x-xsrf-token",
                    "content-type",
                )
            }
            if auth_headers:
                print("    认证头:")
                for k, v in auth_headers.items():
                    # Cookie 太长，截断显示
                    if k.lower() == "cookie":
                        v = v[:100] + "..." if len(v) > 100 else v
                    print(f"      {k}: {v}")

            # POST 数据
            if req.get("post_data_parsed"):
                print("    请求参数:")
                data = req["post_data_parsed"]
                if isinstance(data, dict):
                    for k, v in list(data.items())[:15]:
                        v_str = str(v)[:100] if v else ""
                        print(f"      {k}: {v_str}")
            elif req.get("post_data"):
                print(f"    原始数据: {req['post_data'][:200]}")

            # 响应
            if req.get("response"):
                resp = req["response"]
                print(f"    响应状态: {resp.get('status')}")
                if resp.get("body_parsed"):
                    body = resp["body_parsed"]
                    print(f"    响应体: {json.dumps(body, ensure_ascii=False)[:300]}")

    # 按端点分组所有 API 请求
    print("\n" + "─" * 50)
    print("所有 API 端点汇总")
    print("─" * 50)

    url_groups: dict[str, list[dict]] = {}
    for req in api_requests:
        parsed = urlparse(req["url"])
        path = parsed.path
        if path not in url_groups:
            url_groups[path] = []
        url_groups[path].append(req)

    for path, reqs in sorted(url_groups.items()):
        methods = set(r["method"] for r in reqs)
        is_upload = any(r.get("is_upload_related") for r in reqs)
        marker = "★" if is_upload else " "
        print(f"{marker} [{','.join(methods)}] {path} ({len(reqs)} 次)")

    # 保存完整结果
    output_dir = project_root / "data" / "debug"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存所有请求
    all_requests_file = output_dir / "captured_first_edit_api.json"
    with open(all_requests_file, "w", encoding="utf-8") as f:
        json.dump(captured_requests, f, ensure_ascii=False, indent=2)
    print(f"\n完整请求已保存: {all_requests_file}")

    # 单独保存上传相关请求
    if upload_requests:
        upload_file = output_dir / "captured_upload_api.json"
        with open(upload_file, "w", encoding="utf-8") as f:
            json.dump(upload_requests, f, ensure_ascii=False, indent=2)
        print(f"上传请求已保存: {upload_file}")

    # 生成 API 文档摘要
    _generate_api_summary(upload_requests, output_dir)


def _generate_api_summary(upload_requests: list[dict], output_dir: Path) -> None:
    """生成 API 端点摘要文档."""
    if not upload_requests:
        return

    summary_file = output_dir / "upload_api_summary.md"
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("# 首次编辑上传 API 分析摘要\n\n")
        f.write(f"生成时间: {datetime.now().isoformat()}\n\n")

        f.write("## 发现的 API 端点\n\n")
        for i, req in enumerate(upload_requests):
            parsed = urlparse(req["url"])
            f.write(f"### {i + 1}. {parsed.path}\n\n")
            f.write(f"- **方法**: {req['method']}\n")
            f.write(f"- **完整 URL**: {req['url']}\n")

            # 请求头
            headers = req.get("headers", {})
            content_type = headers.get("content-type", "未知")
            f.write(f"- **Content-Type**: {content_type}\n")

            # 请求参数
            if req.get("post_data_parsed"):
                f.write("\n**请求参数**:\n```json\n")
                f.write(json.dumps(req["post_data_parsed"], ensure_ascii=False, indent=2))
                f.write("\n```\n")

            # 响应
            if req.get("response", {}).get("body_parsed"):
                f.write("\n**响应示例**:\n```json\n")
                f.write(
                    json.dumps(req["response"]["body_parsed"], ensure_ascii=False, indent=2)[:1000]
                )
                f.write("\n```\n")

            f.write("\n---\n\n")

    print(f"API 摘要文档: {summary_file}")


async def capture_upload_requests() -> None:
    """主函数：抓取首次编辑上传的网络请求."""
    # 加载 Cookie
    cookie_file = project_root.parent.parent / "data/temp/miaoshou_cookies.json"
    manager = CookieManager(str(cookie_file))
    cookies = manager.load_playwright_cookies()

    if not cookies:
        print("错误: 无法加载 Cookie，请先登录妙手 ERP")
        print(f"Cookie 文件路径: {cookie_file}")
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

        try:
            # 执行首次编辑操作（引导用户）
            await _execute_first_edit_steps(page)
        except KeyboardInterrupt:
            print("\n用户中断，开始分析已捕获的请求...")
        finally:
            await browser.close()

    # 分析请求
    _analyze_upload_requests()


if __name__ == "__main__":
    asyncio.run(capture_upload_requests())
