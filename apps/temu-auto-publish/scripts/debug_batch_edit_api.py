#!/usr/bin/env python3
"""调试二次编辑 API，查看 SKU 数据结构."""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import async_playwright

from src.browser.miaoshou.api_client import MiaoshouApiClient


async def wait_for_login(page, context) -> MiaoshouApiClient | None:
    """等待用户登录并返回 API 客户端."""
    print("\n" + "=" * 70)
    print("请在浏览器中完成登录")
    print("登录成功后，请按回车键继续...")
    print("=" * 70)

    input()

    # 等待页面稳定
    await page.wait_for_load_state("networkidle", timeout=60000)

    # 重新创建 API 客户端
    client = await MiaoshouApiClient.from_playwright_context(context)
    return client


async def main():
    """调试二次编辑 API."""
    print("=" * 70)
    print("调试二次编辑 API")
    print("=" * 70)

    # 使用 Playwright 打开浏览器获取 Cookie
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # 打开妙手 ERP
        print("\n正在打开妙手采集箱页面...")
        await page.goto("https://erp.91miaoshou.com/pddkj/collect_box/items")

        # 等待页面加载
        print("等待页面加载完成...")
        await page.wait_for_load_state("networkidle", timeout=30000)

        # 从 Playwright 上下文创建 API 客户端
        client = await MiaoshouApiClient.from_playwright_context(context)
        if not client:
            print("无法创建 API 客户端")
            await browser.close()
            return

        # Step 1: 搜索产品
        print("\n[Step 1] 搜索 Temu 采集箱产品...")
        async with client:
            search_result = await client.search_temu_collect_box(
                status="notPublished",
                page_size=5,  # 只取 5 个用于调试
            )

        # 如果 Cookie 过期，等待重新登录
        if search_result.get("code") == 50001:
            print(f"\nCookie 已过期: {search_result.get('reason')}")
            client = await wait_for_login(page, context)
            if not client:
                print("无法创建 API 客户端")
                await browser.close()
                return

        # 重新搜索或继续使用当前 client
        async with client:
            if search_result.get("code") == 50001:
                print("\n[Step 1] 重新搜索 Temu 采集箱产品...")
                search_result = await client.search_temu_collect_box(
                    status="notPublished",
                    page_size=5,
                )

            if search_result.get("result") != "success":
                print(f"搜索失败: {search_result}")
                await browser.close()
                return

            items = search_result.get("detailList", [])
            print(f"找到 {len(items)} 个产品")

            if not items:
                print("没有可编辑的产品")
                await browser.close()
                return

            # 提取产品 ID
            detail_ids = [str(item.get("collectBoxDetailId")) for item in items[:3]]
            print(f"测试产品 ID: {detail_ids}")

            # Step 2: 获取产品 SKU 信息
            print("\n[Step 2] 获取产品 SKU 信息...")
            item_info_result = await client.get_collect_item_info(
                detail_ids=detail_ids,
                fields=["skuMap", "title", "cid"],
            )

            print(f"\n返回结果 keys: {item_info_result.keys()}")
            print(f"result: {item_info_result.get('result')}")

            item_info_list = item_info_result.get("collectItemInfoList", [])
            print(f"collectItemInfoList 长度: {len(item_info_list)}")

            # 打印第一个产品的详细信息
            if item_info_list:
                first_item = item_info_list[0]
                print(f"\n第一个产品的 keys: {first_item.keys()}")
                print(f"detailId: {first_item.get('detailId')}")
                print(f"title: {first_item.get('title', '')[:50]}...")

                sku_map = first_item.get("skuMap", {})
                print(f"\nskuMap 类型: {type(sku_map)}")
                print(
                    f"skuMap keys: {list(sku_map.keys())[:5] if isinstance(sku_map, dict) else 'N/A'}"
                )

                if isinstance(sku_map, dict) and sku_map:
                    # 打印第一个 SKU 的详细信息
                    first_sku_key = list(sku_map.keys())[0]
                    first_sku = sku_map[first_sku_key]
                    print(f"\n第一个 SKU key: {first_sku_key}")
                    print(f"第一个 SKU 类型: {type(first_sku)}")
                    if isinstance(first_sku, dict):
                        print(f"第一个 SKU keys: {list(first_sku.keys())}")
                        # 打印价格相关字段
                        price_fields = {
                            k: v
                            for k, v in first_sku.items()
                            if "price" in k.lower()
                            or "cost" in k.lower()
                            or "supply" in k.lower()
                        }
                        print(
                            f"\n价格相关字段: {json.dumps(price_fields, indent=2, ensure_ascii=False)}"
                        )

                        # 打印完整 SKU 数据
                        print("\n完整 SKU 数据:")
                        print(json.dumps(first_sku, indent=2, ensure_ascii=False))

            # Step 3: 测试保存（只修改价格）
            print("\n" + "=" * 70)
            print("[Step 3] 测试保存 - 价格 × 10")
            print("=" * 70)

            if item_info_list:
                test_item = item_info_list[0]
                detail_id = str(test_item.get("detailId"))
                sku_map = test_item.get("skuMap", {})

                if sku_map:
                    # 计算新价格
                    updated_sku_map = {}
                    for sku_key, sku_data in sku_map.items():
                        if isinstance(sku_data, dict):
                            new_sku = dict(sku_data)
                            # 获取原价 - 尝试多个可能的字段名
                            origin_price = None
                            for field in [
                                "supplyPrice",
                                "supplierPrice",
                                "costPrice",
                                "originPrice",
                                "price",
                            ]:
                                if sku_data.get(field):
                                    try:
                                        origin_price = float(sku_data.get(field))
                                        print(f"  找到价格字段 {field} = {origin_price}")
                                        break
                                    except (ValueError, TypeError):
                                        continue

                            if origin_price:
                                new_price = int(origin_price * 10)
                                new_sku["price"] = str(new_price)
                                print(
                                    f"  SKU {sku_key[:30]}: {origin_price} -> {new_price}"
                                )
                            updated_sku_map[sku_key] = new_sku

                    # 构建保存数据
                    save_data = {
                        "site": "PDDKJ",
                        "detailId": detail_id,
                        "skuMap": updated_sku_map,
                        "multiLanguageTitleMap": {"en": " "},
                    }

                    print("\n保存数据 preview:")
                    print(f"  detailId: {detail_id}")
                    print(f"  skuMap keys: {list(updated_sku_map.keys())}")

                    # 执行保存
                    confirm = input("\n是否执行保存? (y/n): ").strip().lower()
                    if confirm == "y":
                        save_result = await client.save_collect_item_info(
                            items=[save_data]
                        )
                        print(
                            f"\n保存结果: {json.dumps(save_result, indent=2, ensure_ascii=False)}"
                        )
                    else:
                        print("跳过保存")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
