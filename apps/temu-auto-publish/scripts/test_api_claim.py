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


async def main():
    """主函数."""
    logger.info("妙手 API 认领功能测试")
    logger.info("=" * 60)

    # 测试 1: 获取产品列表
    await test_get_product_list()

    # 测试 2: API 认领 (默认 dry_run 模式)
    await test_api_claim(dry_run=True)

    logger.info("=" * 60)
    logger.info("测试完成")

    # 如果需要执行实际认领，取消下面的注释
    # await test_api_claim(dry_run=False)


if __name__ == "__main__":
    asyncio.run(main())
