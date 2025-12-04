"""
测试首次编辑 API 模式。

使用方法:
uv run python scripts/test_first_edit_api.py
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

from src.browser.miaoshou.api_client import MiaoshouApiClient


async def test_api():
    """测试通用采集箱 API。"""
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
        print("正在打开妙手采集箱页面...")
        await page.goto(
            "https://erp.91miaoshou.com/collect_box/common_collect_box",
            wait_until="networkidle",
        )

        # 创建 API 客户端
        print("\n创建 API 客户端...")
        client = await MiaoshouApiClient.from_playwright_context(browser)

        try:
            # 测试 1: 获取创建人员列表
            print("\n[测试 1] 获取创建人员列表...")
            owner_result = await client.get_common_collect_box_owner_list()
            if owner_result.get("result") == "success":
                owners = owner_result.get("ownerAccountList", [])
                print(f"✓ 成功获取 {len(owners)} 个创建人员")
                for owner in owners[:5]:
                    print(f"  - {owner.get('subAccountAliasName')}")
            else:
                print(f"✗ 失败: {owner_result.get('message')}")

            # 测试 2: 获取已认领产品列表
            print("\n[测试 2] 获取已认领产品列表...")
            list_result = await client.get_product_list(tab="claimed", limit=10)
            if list_result.get("result") == "success":
                products = list_result.get("detailList", [])
                print(f"✓ 成功获取 {len(products)} 个已认领产品")
                for p in products[:3]:
                    detail_id = p.get("commonCollectBoxDetailId")
                    title = p.get("title", "")[:40]
                    owner = p.get("ownerSubAccountAliasName", "N/A")
                    print(f"  - [{detail_id}] {title}... (创建人: {owner})")
            else:
                print(f"✗ 失败: {list_result.get('message')}")

            # 测试 3: 获取单个产品编辑信息
            if products:
                first_product = products[0]
                detail_id = str(first_product.get("commonCollectBoxDetailId"))
                print(f"\n[测试 3] 获取产品编辑信息 (ID: {detail_id})...")

                info_result = await client.get_edit_common_box_detail(detail_id)
                if info_result.get("result") == "success":
                    detail = info_result.get("editCommonBoxDetail", {})
                    oss_md5 = info_result.get("ossMd5", "")
                    print(f"✓ 成功获取编辑信息")
                    print(f"  - 标题: {detail.get('title', '')[:50]}...")
                    print(f"  - 价格: {detail.get('price')}")
                    print(f"  - 库存: {detail.get('stock')}")
                    print(f"  - colorMap 数量: {len(detail.get('colorMap', {}))}")
                    print(f"  - skuMap 数量: {len(detail.get('skuMap', {}))}")
                    print(f"  - sizeChart: {detail.get('sizeChart', '')[:50] or '(空)'}")
                    print(f"  - mainImgVideoUrl: {detail.get('mainImgVideoUrl', '')[:50] or '(空)'}")
                    print(f"  - ossMd5: {oss_md5[:20]}...")

                    # 打印 skuMap 结构
                    print("\n  SKU Map 详情:")
                    for sku_key, sku_data in list(detail.get("skuMap", {}).items())[:2]:
                        print(f"    [{sku_key}]:")
                        print(f"      price: {sku_data.get('price')}")
                        print(f"      stock: {sku_data.get('stock')}")
                        print(f"      weight: {sku_data.get('weight')}")
                        print(f"      packageLength: {sku_data.get('packageLength')}")
                else:
                    print(f"✗ 失败: {info_result.get('message')}")

            print("\n" + "=" * 60)
            print("API 测试完成！")
            print("=" * 60)
            print("\n按 Enter 键关闭浏览器...")
            input()

        finally:
            await client.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_api())
