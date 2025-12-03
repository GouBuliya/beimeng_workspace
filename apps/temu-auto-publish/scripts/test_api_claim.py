"""
@PURPOSE: 测试妙手 API 认领功能
@OUTLINE:
  - test_get_product_list(): 测试获取产品列表
  - test_api_claim(): 测试 API 认领
@DEPENDENCIES:
  - 内部: src.browser.miaoshou.api_client
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from src.browser.miaoshou.api_client import MiaoshouApiClient


async def test_get_product_list():
    """测试获取产品列表."""
    logger.info("=" * 50)
    logger.info("测试 1: 获取产品列表")
    logger.info("=" * 50)

    # 使用默认 cookie 文件路径
    cookie_file = project_root.parent.parent / "data/temp/miaoshou_cookies.json"
    logger.info(f"Cookie 文件: {cookie_file}")

    client = await MiaoshouApiClient.from_cookie_file(str(cookie_file))

    if not client:
        logger.error("无法创建 API 客户端，请检查 Cookie 文件")
        return None

    async with client:
        # 获取未认领产品列表
        result = await client.get_product_list(tab="unclaimed", limit=5)

        # 兼容两种响应格式
        is_success = result.get("result") == "success" or result.get("code") == 0
        if is_success:
            # 兼容两种响应格式
            if "detailList" in result:
                total = result.get("total", 0)
                items = result.get("detailList", [])
            else:
                data = result.get("data", {})
                total = data.get("total", 0)
                items = data.get("list", [])

            logger.success(f"获取成功: 共 {total} 个未认领产品")

            if items:
                logger.info("前 5 个产品:")
                for i, item in enumerate(items[:5], 1):
                    detail_id = (
                        item.get("commonCollectBoxDetailId")
                        or item.get("detailId")
                        or item.get("id")
                    )
                    title = item.get("title", "")[:40]
                    logger.info(f"  {i}. ID={detail_id}, 标题={title}...")
            else:
                logger.warning("暂无未认领产品")

            return items
        else:
            logger.error(f"获取失败: {result.get('message', '未知错误')}")
            return None


async def test_api_claim(dry_run: bool = True):
    """测试 API 认领功能.

    Args:
        dry_run: 如果为 True，只获取列表不执行认领
    """
    logger.info("=" * 50)
    logger.info("测试 2: API 认领功能")
    logger.info("=" * 50)

    cookie_file = project_root.parent.parent / "data/temp/miaoshou_cookies.json"
    client = await MiaoshouApiClient.from_cookie_file(str(cookie_file))

    if not client:
        logger.error("无法创建 API 客户端")
        return

    async with client:
        if dry_run:
            logger.warning("DRY RUN 模式 - 不执行实际认领")
            # 只获取列表验证 API 是否正常
            result = await client.get_product_list(tab="unclaimed", limit=3)

            # 兼容两种响应格式
            is_success = result.get("result") == "success" or result.get("code") == 0
            if is_success:
                # 兼容两种响应格式
                if "detailList" in result:
                    items = result.get("detailList", [])
                else:
                    items = result.get("data", {}).get("list", [])

                if items:
                    detail_ids = [
                        str(
                            item.get("commonCollectBoxDetailId")
                            or item.get("detailId")
                            or item.get("id")
                        )
                        for item in items[:3]
                    ]
                    logger.info(f"如果执行认领，将认领以下产品: {detail_ids}")
                    logger.success("API 连接正常，可以执行认领")
                else:
                    logger.info("暂无可认领产品")
            else:
                logger.error(f"API 返回错误: {result}")
        else:
            # 执行实际认领
            logger.warning("执行实际认领...")
            result = await client.claim_unclaimed_products(count=1, platform="pddkj")

            if result.get("success"):
                logger.success(f"认领成功: {result.get('claimed_count')} 个产品")
                logger.info(f"认领的产品 ID: {result.get('detail_ids')}")
            else:
                logger.error(f"认领失败: {result.get('message')}")


async def test_owner_filter():
    """测试人员筛选功能."""
    logger.info("=" * 50)
    logger.info("测试 3: 人员筛选功能")
    logger.info("=" * 50)

    cookie_file = project_root.parent.parent / "data/temp/miaoshou_cookies.json"
    client = await MiaoshouApiClient.from_cookie_file(str(cookie_file))

    if not client:
        logger.error("无法创建 API 客户端")
        return

    async with client:
        # 先获取一些产品看看有哪些创建人员
        result = await client.get_product_list(tab="unclaimed", limit=20)

        is_success = result.get("result") == "success" or result.get("code") == 0
        if not is_success:
            logger.error("获取产品列表失败")
            return

        if "detailList" in result:
            items = result.get("detailList", [])
        else:
            items = result.get("data", {}).get("list", [])

        # 统计创建人员
        owners = {}
        for item in items:
            owner = item.get("ownerSubAccountAliasName", "未知")
            owners[owner] = owners.get(owner, 0) + 1

        logger.info("前 20 个产品的创建人员分布:")
        for owner, count in sorted(owners.items(), key=lambda x: -x[1]):
            logger.info(f"  {owner}: {count} 个")

        # 测试筛选（如果有多个创建人员）
        if len(owners) > 1:
            # 取第一个创建人员进行筛选测试
            test_owner = next(iter(owners.keys()))
            # 提取简短名称用于部分匹配测试
            if "(" in test_owner:
                short_name = test_owner.split("(")[0].rstrip("）").rstrip()
            else:
                short_name = test_owner[:2]  # 取前两个字符

            logger.info(f"\n测试筛选: 完整名称='{test_owner}', 部分匹配='{short_name}'")

            # 测试 claim_unclaimed_products 的筛选功能 (dry run)
            logger.info(f"\n模拟认领 (筛选 '{short_name}'):")

            # 获取更多产品进行筛选测试
            list_result = await client.get_product_list(tab="unclaimed", limit=50)
            if "detailList" in list_result:
                all_items = list_result.get("detailList", [])
            else:
                all_items = list_result.get("data", {}).get("list", [])

            # 客户端筛选
            filtered = [
                item for item in all_items
                if short_name in (item.get("ownerSubAccountAliasName") or "")
            ]
            logger.info(f"  获取 50 个产品，筛选后匹配 '{short_name}' 的有 {len(filtered)} 个")

            if filtered:
                for i, item in enumerate(filtered[:3], 1):
                    detail_id = (
                        item.get("commonCollectBoxDetailId")
                        or item.get("detailId")
                        or item.get("id")
                    )
                    owner = item.get("ownerSubAccountAliasName", "未知")
                    title = item.get("title", "")[:30]
                    logger.info(f"    {i}. ID={detail_id}, 创建人员={owner}, 标题={title}...")

                logger.success("人员筛选功能正常工作！")
            else:
                logger.warning(f"筛选 '{short_name}' 没有匹配结果")
        else:
            logger.info("只有一个创建人员，跳过筛选测试")


async def main():
    """主函数."""
    logger.info("妙手 API 认领功能测试")
    logger.info("=" * 60)

    # 测试 1: 获取产品列表
    await test_get_product_list()

    # 测试 2: API 认领 (默认 dry_run 模式)
    await test_api_claim(dry_run=True)

    # 测试 3: 人员筛选功能
    await test_owner_filter()

    logger.info("=" * 60)
    logger.info("测试完成")

    # 如果需要执行实际认领，取消下面的注释
    # await test_api_claim(dry_run=False)


if __name__ == "__main__":
    asyncio.run(main())
