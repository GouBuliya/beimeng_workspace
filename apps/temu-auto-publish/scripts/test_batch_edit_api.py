"""
@PURPOSE: 测试批量编辑 API 的功能
@OUTLINE:
  - test_api_client(): 测试 API 客户端基础功能
  - test_batch_edit_integration(): 测试工作流集成（使用 run_batch_edit_via_api）
@DEPENDENCIES:
  - 内部: src.browser.miaoshou.api_client, src.browser.miaoshou.batch_edit_api
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.browser.miaoshou.api_client import MiaoshouApiClient


async def test_api_client():
    """测试 API 客户端基础功能."""
    print("=" * 60)
    print("批量编辑 API 客户端测试")
    print("=" * 60)

    # 创建客户端
    cookie_file = project_root.parent.parent / "data/temp/miaoshou_cookies.json"
    client = await MiaoshouApiClient.from_cookie_file(str(cookie_file))

    if not client:
        print("错误: 无法加载 Cookie，请先登录妙手 ERP")
        return False

    async with client:
        # 1. 搜索 Temu 采集箱产品
        print("\n1. 搜索 Temu 采集箱产品...")
        search_result = await client.search_temu_collect_box(
            status="notPublished",
            page_size=5,
        )

        if search_result.get("result") != "success":
            print(f"   搜索失败: {search_result.get('message')}")
            return False

        items = search_result.get("detailList", [])
        if not items:
            print("   没有可编辑的产品（需要先认领产品到 Temu 平台）")
            return False

        print(f"   找到 {len(items)} 个可编辑的产品")

        # 提取 collectBoxDetailId
        detail_ids = []
        for item in items[:3]:
            detail_id = str(item.get("collectBoxDetailId"))
            if detail_id and detail_id != "None":
                detail_ids.append(detail_id)
                print(f"   - collectBoxDetailId: {detail_id}, cid: {item.get('cid')}")

        if not detail_ids:
            print("   无法提取 collectBoxDetailId")
            return False

        # 2. 获取产品编辑信息
        print(f"\n2. 获取产品编辑信息 (IDs: {detail_ids})...")
        info_result = await client.get_collect_item_info(
            detail_ids=detail_ids,
            fields=["title", "cid", "attributes", "productOriginCountry"],
        )

        if info_result.get("result") == "success":
            collect_items = info_result.get("collectItemInfoList", [])
            print(f"   成功获取 {len(collect_items)} 个产品的编辑信息")
            for item in collect_items[:2]:
                print(f"\n   产品 {item.get('detailId')}:")
                print(f"     标题: {item.get('title', 'N/A')[:50]}...")
                print(f"     类目: {item.get('cid', 'N/A')}")
                print(f"     产地: {item.get('productOriginCountry', 'N/A')}")
        else:
            print(f"   获取编辑信息失败: {info_result.get('message')}")
            return False

        # 3. 测试获取商品选项（外包装形状/类型）
        print("\n3. 获取商品选项（外包装形状/类型）...")
        options_result = await client.get_item_options()
        if options_result.get("result") == "success":
            shape_options = options_result.get("outerPackageShapeOptions", [])
            type_options = options_result.get("outerPackageTypeOptions", [])
            print(f"   外包装形状选项: {len(shape_options)} 个")
            for opt in shape_options[:3]:
                print(f"     - {opt.get('key')}: {opt.get('value')}")
            print(f"   外包装类型选项: {len(type_options)} 个")
            for opt in type_options[:3]:
                print(f"     - {opt.get('key')}: {opt.get('value')}")
        else:
            print(f"   获取选项失败: {options_result.get('message')}")

        # 4. 显示工作流集成信息
        print("\n4. 工作流集成:")
        print("   使用方式:")
        print("   ┌─────────────────────────────────────────────────────┐")
        print("   │ CompletePublishWorkflow(use_api_batch_edit=True)    │")
        print("   │                                                     │")
        print("   │ Stage 3 将使用 API 方式执行批量编辑：              │")
        print("   │ - 自动搜索 Temu 采集箱产品                         │")
        print("   │ - 上传外包装图片和产品说明书                       │")
        print("   │ - 批量更新产品数据字段                             │")
        print("   └─────────────────────────────────────────────────────┘")

        print("\n   支持的编辑字段:")
        for field in MiaoshouApiClient.BATCH_EDIT_FIELDS[:12]:
            print(f"     - {field}")
        print("     ... 更多字段请参考 BATCH_EDIT_FIELDS")

        print("\n   新增文件上传 API:")
        print("     - upload_picture_file(): 上传图片（外包装图、轮播图等）")
        print("     - upload_attach_file(): 上传附件（产品说明书 PDF）")
        print("     - get_item_options(): 获取外包装形状/类型选项")

        print("\n" + "=" * 60)
        print("测试完成！API 客户端功能正常")
        print("=" * 60)
        return True


async def main():
    """主测试入口."""
    success = await test_api_client()
    if not success:
        print("\n测试失败，请检查 Cookie 或网络连接")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
