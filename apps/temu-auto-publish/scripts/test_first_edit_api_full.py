"""
测试首次编辑 API 模式的完整功能。

使用 data/10月新品可上架(3).csv 作为样例数据，验证:
1. 规格名称填写 (colorPropName)
2. 规格选项替换 (colorMap.name)
3. 标题更新
4. 价格/库存/重量/尺寸更新
5. SKU 图片更新
6. 尺寸图更新
7. 视频更新

使用方法:
uv run python scripts/test_first_edit_api_full.py
"""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright
from src.browser.miaoshou.api_client import MiaoshouApiClient
from src.data_processor.selection_table_reader import SelectionTableReader


async def test_first_edit_api_full():
    """测试首次编辑 API 的完整功能。"""
    # 读取选品数据
    csv_path = Path("/Users/candy/beimeng_workspace/data/10月新品可上架(3).csv")
    if not csv_path.exists():
        print(f"✗ 样例数据文件不存在: {csv_path}")
        return

    print("=" * 70)
    print("首次编辑 API 完整功能测试")
    print("=" * 70)

    # 使用 SelectionTableReader 读取选品数据
    reader = SelectionTableReader()
    selections = reader.read_excel(str(csv_path))

    print(f"\n[1] 读取选品数据: {len(selections)} 条")
    for i, sel in enumerate(selections[:3]):
        print(f"  [{i + 1}] 型号={sel.model_number}")
        print(f"      规格单位={sel.spec_unit}")
        print(f"      规格选项={sel.spec_options}")
        print(f"      进货价={sel.cost_price}")
        print(f"      视频={sel.product_video_url}")
        print(f"      尺码图={sel.size_chart_image_url}")
        print(
            f"      SKU图={sel.sku_image_urls[:2]}..." if sel.sku_image_urls else "      SKU图=[]"
        )

    async with async_playwright() as p:
        # 使用已有的浏览器配置（保持登录状态）
        profile_dir = Path.home() / ".playwright-profile"
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1400, "height": 900},
        )

        page = browser.pages[0] if browser.pages else await browser.new_page()

        # 导航到采集箱页面以确保 Cookie 有效
        print("\n[2] 打开妙手采集箱页面...")
        await page.goto(
            "https://erp.91miaoshou.com/collect_box/common_collect_box",
            wait_until="networkidle",
        )

        # 创建 API 客户端
        print("\n[3] 创建 API 客户端...")
        client = await MiaoshouApiClient.from_playwright_context(browser)

        try:
            # 获取已认领产品列表
            print("\n[4] 获取已认领产品列表...")
            list_result = await client.get_product_list(tab="claimed", limit=10)
            if list_result.get("result") != "success":
                print(f"✗ 获取产品列表失败: {list_result.get('message')}")
                return

            products = list_result.get("detailList", [])
            print(f"  找到 {len(products)} 个已认领产品")

            if not products:
                print("  ⚠ 没有已认领产品，无法测试")
                return

            # 选择第一个产品进行测试
            test_product = products[0]
            detail_id = str(test_product.get("commonCollectBoxDetailId"))
            print(f"\n[5] 测试产品: ID={detail_id}")
            print(f"    标题: {test_product.get('title', '')[:50]}...")

            # 获取编辑信息
            print("\n[6] 获取产品编辑信息...")
            info_result = await client.get_edit_common_box_detail(detail_id)
            if info_result.get("result") != "success":
                print(f"✗ 获取编辑信息失败: {info_result.get('message')}")
                return

            detail = info_result.get("editCommonBoxDetail", {})
            oss_md5 = info_result.get("ossMd5", "")

            print("  原始数据:")
            print(f"    - title: {detail.get('title', '')[:50]}...")
            print(f"    - colorPropName: {detail.get('colorPropName', '(空)')}")
            print(f"    - colorMap: {list(detail.get('colorMap', {}).keys())}")
            print(f"    - skuMap: {list(detail.get('skuMap', {}).keys())}")
            print(f"    - sizeChart: {detail.get('sizeChart', '(空)')[:50] or '(空)'}")
            print(f"    - mainImgVideoUrl: {detail.get('mainImgVideoUrl', '(空)')[:50] or '(空)'}")

            # 打印 colorMap 中的 name 字段
            color_map = detail.get("colorMap", {})
            if color_map:
                print("\n  colorMap 规格选项:")
                for cid, cdata in list(color_map.items())[:3]:
                    print(f"    - [{cid}]: name={cdata.get('name', '(空)')}")

            # 使用第一个选品数据进行模拟更新
            if selections:
                sel = selections[0]
                print(f"\n[7] 模拟更新 (使用选品 {sel.model_number})...")

                # 创建更新后的 detail 副本
                updated_detail = json.loads(json.dumps(detail))

                # 更新规格名称
                if sel.spec_unit:
                    updated_detail["colorPropName"] = sel.spec_unit
                    print(f"    ✓ colorPropName: {detail.get('colorPropName')} -> {sel.spec_unit}")

                # 更新规格选项
                if sel.spec_options:
                    for idx, (cid, cdata) in enumerate(updated_detail.get("colorMap", {}).items()):
                        if idx < len(sel.spec_options):
                            old_name = cdata.get("name", "")
                            cdata["name"] = sel.spec_options[idx]
                            print(
                                f"    ✓ colorMap[{cid}].name: {old_name} -> {sel.spec_options[idx]}"
                            )

                # 更新 SKU 图片
                if sel.sku_image_urls:
                    for idx, (cid, cdata) in enumerate(updated_detail.get("colorMap", {}).items()):
                        if idx < len(sel.sku_image_urls):
                            cdata["imgUrls"] = [sel.sku_image_urls[idx]]
                            cdata["imgUrl"] = sel.sku_image_urls[idx]
                            print(
                                f"    ✓ colorMap[{cid}].imgUrl: {sel.sku_image_urls[idx][:50]}..."
                            )

                # 更新尺寸图
                if sel.size_chart_image_url:
                    updated_detail["sizeChart"] = sel.size_chart_image_url
                    print(f"    ✓ sizeChart: {sel.size_chart_image_url[:50]}...")

                # 更新视频
                if sel.product_video_url:
                    updated_detail["mainImgVideoUrl"] = sel.product_video_url
                    print(f"    ✓ mainImgVideoUrl: {sel.product_video_url[:50]}...")

                # 询问是否实际保存
                print("\n" + "=" * 70)
                print("以上为模拟更新预览。是否实际保存更改？")
                print("输入 'yes' 保存，其他任意键跳过: ", end="", flush=True)

                try:
                    user_input = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, input),
                        timeout=30,
                    )
                except TimeoutError:
                    user_input = ""

                if user_input.strip().lower() == "yes":
                    print("\n[8] 保存更改...")
                    save_result = await client.save_edit_common_box_detail(updated_detail, oss_md5)
                    if save_result.get("result") == "success":
                        print("✓ 保存成功!")
                        print(f"  新 ossMd5: {save_result.get('ossMd5', '')[:20]}...")
                    else:
                        print(f"✗ 保存失败: {save_result.get('message')}")
                else:
                    print("\n跳过保存。")

            print("\n" + "=" * 70)
            print("测试完成!")
            print("=" * 70)
            print("\n按 Enter 键关闭浏览器...")
            input()

        finally:
            await client.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_first_edit_api_full())
