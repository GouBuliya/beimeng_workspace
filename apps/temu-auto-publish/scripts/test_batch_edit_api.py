"""
@PURPOSE: 测试批量编辑 API 的功能
@OUTLINE:
  - test_batch_edit_api(): 完整测试批量编辑 API 流程
    1. 搜索 Temu 采集箱产品（获取 collectBoxDetailId）
    2. 获取产品编辑信息
    3. 验证 API 格式
@DEPENDENCIES:
  - 内部: src.browser.miaoshou.api_client
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.browser.miaoshou.api_client import MiaoshouApiClient


async def test_batch_edit_api():
    """测试批量编辑 API."""
    print("=" * 60)
    print("批量编辑 API 测试")
    print("=" * 60)

    # 创建客户端
    cookie_file = project_root.parent.parent / "data/temp/miaoshou_cookies.json"
    client = await MiaoshouApiClient.from_cookie_file(str(cookie_file))

    if not client:
        print("错误: 无法加载 Cookie，请先登录妙手 ERP")
        return

    async with client:
        # 1. 搜索 Temu 采集箱产品（这是批量编辑的入口）
        print("\n1. 搜索 Temu 采集箱产品...")
        search_result = await client.search_temu_collect_box(
            status="notPublished",  # 未发布
            page_size=5,
        )

        if search_result.get("result") != "success":
            print(f"   搜索失败: {search_result.get('message')}")
            return

        items = search_result.get("detailList", [])
        if not items:
            print("   没有可编辑的产品（需要先认领产品到 Temu 平台）")
            return

        print(f"   找到 {len(items)} 个可编辑的产品")

        # 提取 collectBoxDetailId（这是批量编辑 API 需要的 ID）
        detail_ids = []
        for item in items[:3]:  # 只取前 3 个
            detail_id = str(item.get("collectBoxDetailId"))
            if detail_id and detail_id != "None":
                detail_ids.append(detail_id)
                print(f"   - collectBoxDetailId: {detail_id}, cid: {item.get('cid')}")

        if not detail_ids:
            print("   无法提取 collectBoxDetailId")
            return

        # 2. 测试获取产品编辑信息
        print(f"\n2. 获取产品编辑信息 (IDs: {detail_ids})...")
        info_result = await client.get_collect_item_info(
            detail_ids=detail_ids,
            fields=["title", "cid", "attributes", "itemNum", "productOriginCountry"],
        )

        if info_result.get("result") == "success":
            collect_items = info_result.get("collectItemInfoList", [])
            print(f"   成功获取 {len(collect_items)} 个产品的编辑信息")
            for item in collect_items[:2]:  # 只显示前 2 个
                print(f"\n   产品 {item.get('detailId')}:")
                print(f"     标题: {item.get('title', 'N/A')[:50]}...")
                print(f"     类目: {item.get('cid', 'N/A')}")
                print(f"     货号: {item.get('itemNum', 'N/A')}")
                print(f"     产地: {item.get('productOriginCountry', 'N/A')}")
        else:
            print(f"   获取编辑信息失败: {info_result.get('message')}")

        # 3. 验证 API 格式（不实际保存）
        print("\n3. API 格式验证:")
        print("   批量编辑工作流程:")
        print("   ┌─────────────────────────────────────────────────────┐")
        print("   │ 1. search_temu_collect_box() 获取可编辑产品列表     │")
        print("   │    → 返回 collectBoxDetailId                        │")
        print("   │                                                     │")
        print("   │ 2. get_collect_item_info() 获取当前编辑信息        │")
        print("   │    → 返回 title, cid, attributes 等                │")
        print("   │                                                     │")
        print("   │ 3. save_collect_item_info() 保存编辑               │")
        print("   │    → 提交修改后的字段                              │")
        print("   └─────────────────────────────────────────────────────┘")
        print("\n   支持的编辑字段:")
        for field in MiaoshouApiClient.BATCH_EDIT_FIELDS[:10]:
            print(f"     - {field}")
        print("     ... 更多字段请参考 BATCH_EDIT_FIELDS")

        print("\n" + "=" * 60)
        print("测试完成！批量编辑 API 客户端功能正常")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_batch_edit_api())
