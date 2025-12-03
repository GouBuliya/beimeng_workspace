"""
@PURPOSE: API 方式执行发布流程
@OUTLINE:
  - async def run_publish_via_api(): 主入口，执行 API 发布完整流程
  - async def _ensure_products_have_shop(): 确保产品已关联店铺
@DEPENDENCIES:
  - 内部: .api_client.MiaoshouApiClient
@RELATED: api_client.py, batch_edit_api.py, complete_publish_workflow.py
@CHANGELOG:
  - 2025-12-04: 初始实现，支持 API 发布
  - 2025-12-04: 发布前自动全选店铺，修复"未选择发布店铺"问题
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from playwright.async_api import Page

from .api_client import MiaoshouApiClient


async def _ensure_products_have_shop(
    client: MiaoshouApiClient,
    detail_ids: list[str],
) -> dict[str, Any]:
    """确保产品已关联店铺（发布前必须）.

    在发布前调用此方法，为产品设置 collectBoxDetailShopList。
    会自动获取所有已授权店铺并全选。

    Args:
        client: API 客户端
        detail_ids: 产品 ID 列表

    Returns:
        结果字典：
        {
            "success": bool,
            "shop_count": int,  # 选择的店铺数量
            "error": str | None,
        }
    """
    result: dict[str, Any] = {
        "success": False,
        "shop_count": 0,
        "error": None,
    }

    try:
        # 获取店铺列表
        shop_result = await client.get_shop_list(platform="pddkj")
        if shop_result.get("result") != "success":
            result["error"] = f"获取店铺列表失败: {shop_result.get('message')}"
            logger.warning(result["error"])
            return result

        shop_list = shop_result.get("shopList", [])
        # 只选择授权状态有效的店铺
        shop_ids = [
            str(shop.get("shopId"))
            for shop in shop_list
            if shop.get("authStatus") == "valid" and shop.get("shopId")
        ]

        if not shop_ids:
            result["error"] = "没有可用的已授权店铺"
            logger.warning(result["error"])
            return result

        logger.info(f"发布前设置店铺: 为 {len(detail_ids)} 个产品选择 {len(shop_ids)} 个店铺")

        # 构建店铺列表
        shop_list_data = [{"shopId": sid} for sid in shop_ids]

        # 调用批量编辑 API 设置店铺
        edit_result = await client.batch_edit_products(
            detail_ids=detail_ids,
            edits={"collectBoxDetailShopList": shop_list_data},
        )

        if edit_result.get("success"):
            result["success"] = True
            result["shop_count"] = len(shop_ids)
            logger.info(f"店铺设置成功: {len(shop_ids)} 个店铺已关联到 {len(detail_ids)} 个产品")
        else:
            result["error"] = f"设置店铺失败: {edit_result.get('error_map', {})}"
            logger.warning(result["error"])

    except Exception as e:
        result["error"] = f"设置店铺异常: {e}"
        logger.exception(result["error"])

    return result


async def run_publish_via_api(
    page: Page,
    *,
    filter_owner: str | None = None,
    shop_id: str = "9134811",
    max_products: int = 20,
    cookie_file: str | None = None,
) -> dict[str, Any]:
    """使用 API 执行发布流程.

    Args:
        page: Playwright 页面对象（用于获取 Cookie）
        filter_owner: 按创建人员筛选
        shop_id: 目标店铺 ID（默认 9134811）
        max_products: 每次最多发布的产品数量（默认 20）
        cookie_file: Cookie 文件路径（可选，默认从 page 获取）

    Returns:
        执行结果:
        {
            "success": bool,
            "published_count": int,
            "total_count": int,
            "error": str | None,
            "detail_ids": list[str],
        }

    Examples:
        >>> result = await run_publish_via_api(
        ...     page,
        ...     filter_owner="李英亮",
        ...     shop_id="9134811",
        ... )
        >>> print(f"发布了 {result['published_count']} 个产品")
    """
    result: dict[str, Any] = {
        "success": False,
        "published_count": 0,
        "total_count": 0,
        "error": None,
        "detail_ids": [],
    }

    try:
        # Step 1: 创建 API 客户端
        logger.info("API 发布: 创建 API 客户端...")
        if cookie_file:
            client = await MiaoshouApiClient.from_cookie_file(cookie_file)
        else:
            context = page.context
            client = await MiaoshouApiClient.from_playwright_context(context)

        if not client:
            result["error"] = "无法创建 API 客户端（Cookie 无效）"
            logger.error(result["error"])
            return result

        async with client:
            # Step 2: 搜索已编辑但未发布的产品
            logger.info("API 发布: 搜索可发布产品...")
            search_result = await client.search_temu_collect_box(
                status="notPublished",
                page_size=100,
            )

            if search_result.get("result") != "success":
                result["error"] = f"搜索产品失败: {search_result.get('message')}"
                logger.error(result["error"])
                return result

            items = search_result.get("detailList", [])
            if not items:
                result["error"] = "没有可发布的产品"
                logger.warning(result["error"])
                return result

            # Step 3: 按创建人员筛选
            if filter_owner:
                owner_filter = filter_owner.strip()
                if "(" in owner_filter:
                    owner_filter = owner_filter.split("(")[0].strip()

                filtered_items = [
                    item
                    for item in items
                    if owner_filter in (item.get("ownerSubAccountAliasName") or "")
                ]
                if filtered_items:
                    logger.info(
                        f"按创建人员筛选: '{owner_filter}' 匹配到 "
                        f"{len(filtered_items)}/{len(items)} 个产品"
                    )
                    items = filtered_items
                else:
                    result["error"] = f"未找到创建人员 '{owner_filter}' 的产品"
                    logger.warning(result["error"])
                    return result

            # 提取 collectBoxDetailId
            detail_ids = [str(item.get("collectBoxDetailId")) for item in items]
            detail_ids = [did for did in detail_ids if did and did != "None"]

            # 限制每次发布的产品数量
            if max_products > 0 and len(detail_ids) > max_products:
                logger.info(f"限制发布数量: {len(detail_ids)} -> {max_products} 个产品")
                detail_ids = detail_ids[:max_products]

            result["total_count"] = len(detail_ids)
            result["detail_ids"] = detail_ids

            if not detail_ids:
                result["error"] = "无法提取产品 ID"
                logger.error(result["error"])
                return result

            logger.info(f"API 发布: 准备发布 {len(detail_ids)} 个产品")

            # Step 4: 发布前确保产品已关联店铺（自动全选）
            shop_result = await _ensure_products_have_shop(client, detail_ids)
            if not shop_result.get("success"):
                # 店铺设置失败，但仍尝试发布（使用默认店铺）
                logger.warning(
                    f"店铺设置未成功: {shop_result.get('error')}，将使用默认店铺发布"
                )

            # Step 5: 执行发布
            publish_result = await client.publish_to_shop(
                detail_ids=detail_ids,
                shop_id=shop_id,
            )

            if publish_result.get("result") == "success":
                result["success"] = True
                result["published_count"] = len(detail_ids)
                logger.success(
                    f"API 发布完成: 成功 {result['published_count']}/{result['total_count']}"
                )
            else:
                error_msg = (
                    publish_result.get("message")
                    or publish_result.get("errorMsg")
                    or str(publish_result)
                )
                result["error"] = f"发布失败: {error_msg}"
                logger.warning(result["error"])

    except Exception as e:
        result["error"] = f"API 发布异常: {e}"
        logger.exception(result["error"])

    return result
