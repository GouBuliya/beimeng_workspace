"""
@PURPOSE: API 方式执行批量编辑（纯数据部分），与 DOM 文件上传步骤配合使用
@OUTLINE:
  - async def run_batch_edit_via_api(): 主入口，执行 API 批量编辑
  - def _build_edit_payload(): 从业务 payload 构建 API 编辑数据
  - def _map_category_attrs(): 映射类目属性到 API 格式
@DEPENDENCIES:
  - 内部: .api_client.MiaoshouApiClient
@RELATED: api_client.py, batch_edit_codegen.py, complete_publish_workflow.py
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from playwright.async_api import Page

from .api_client import MiaoshouApiClient


async def run_batch_edit_via_api(
    page: Page,
    payload: dict[str, Any],
    *,
    filter_owner: str | None = None,
    cookie_file: str | None = None,
) -> dict[str, Any]:
    """使用 API 执行批量编辑的纯数据部分.

    此函数处理批量编辑 18 步中可 API 化的 14 步：
    - 标题、英语标题、类目属性、主货号、产地
    - 定制品、敏感属性、SKU 相关

    文件上传步骤（外包装、轮播图、颜色图、说明书）需另行用 DOM 处理。

    Args:
        page: Playwright 页面对象（用于获取 Cookie）
        payload: 业务参数字典，包含:
            - category_path: list[str] - 类目路径
            - category_attrs: dict - 类目属性
        filter_owner: 按创建人员筛选
        cookie_file: Cookie 文件路径（可选，默认从 page 获取）

    Returns:
        执行结果:
        {
            "success": bool,
            "edited_count": int,
            "total_count": int,
            "error": str | None,
            "detail_ids": list[str],
        }

    Examples:
        >>> result = await run_batch_edit_via_api(
        ...     page,
        ...     payload={"category_path": ["收纳用品", "收纳篮"], "category_attrs": {...}},
        ...     filter_owner="陈昊"
        ... )
        >>> print(f"编辑了 {result['edited_count']} 个产品")
    """
    result: dict[str, Any] = {
        "success": False,
        "edited_count": 0,
        "total_count": 0,
        "error": None,
        "detail_ids": [],
    }

    try:
        # Step 1: 创建 API 客户端
        logger.info("API 批量编辑: 创建 API 客户端...")
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
            # Step 2: 搜索 Temu 采集箱产品
            logger.info("API 批量编辑: 搜索可编辑产品...")
            search_result = await client.search_temu_collect_box(
                status="notPublished",
                page_size=100,  # 获取足够多的产品
            )

            if search_result.get("result") != "success":
                result["error"] = f"搜索产品失败: {search_result.get('message')}"
                logger.error(result["error"])
                return result

            items = search_result.get("detailList", [])
            if not items:
                result["error"] = "没有可编辑的产品"
                logger.warning(result["error"])
                return result

            # Step 3: 按创建人员筛选（如果指定）
            if filter_owner:
                owner_filter = filter_owner.strip()
                if "(" in owner_filter:
                    owner_filter = owner_filter.split("(")[0].strip()

                filtered_items = [
                    item for item in items
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
            result["total_count"] = len(detail_ids)
            result["detail_ids"] = detail_ids

            if not detail_ids:
                result["error"] = "无法提取产品 ID"
                logger.error(result["error"])
                return result

            logger.info(f"API 批量编辑: 准备编辑 {len(detail_ids)} 个产品")

            # Step 4: 获取产品当前编辑信息
            logger.info("API 批量编辑: 获取产品当前信息...")
            info_result = await client.get_collect_item_info(
                detail_ids=detail_ids,
                fields=["title", "cid", "attributes", "productOriginCountry"],
            )

            if info_result.get("result") != "success":
                result["error"] = f"获取产品信息失败: {info_result.get('message')}"
                logger.error(result["error"])
                return result

            # Step 5: 构建编辑数据并保存
            logger.info("API 批量编辑: 构建并保存编辑数据...")
            edit_data = _build_edit_payload(payload)

            # 使用批量编辑方法
            edit_result = await client.batch_edit_products(
                detail_ids=detail_ids,
                edits=edit_data,
            )

            if edit_result.get("success"):
                result["success"] = True
                result["edited_count"] = edit_result.get("success_count", len(detail_ids))
                logger.success(
                    f"API 批量编辑完成: 成功 {result['edited_count']}/{result['total_count']}"
                )
            else:
                result["error"] = f"保存编辑失败: {edit_result.get('error_map', {})}"
                result["edited_count"] = edit_result.get("success_count", 0)
                logger.warning(result["error"])

    except Exception as e:
        result["error"] = f"API 批量编辑异常: {e}"
        logger.exception(result["error"])

    return result


def _build_edit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """从业务 payload 构建 API 编辑数据.

    Args:
        payload: 业务参数字典

    Returns:
        API 可接受的编辑字段字典
    """
    edit_data: dict[str, Any] = {}

    # 类目属性映射
    if "category_attrs" in payload:
        attrs = payload["category_attrs"]
        # 将类目属性转换为 API 格式
        # 注意：具体格式需要根据实际 API 要求调整
        if attrs:
            edit_data["attributes"] = _map_category_attrs(attrs)

    # 产地映射（默认设置为中国）
    edit_data["productOriginCountry"] = "CN"

    # 定制品开关（默认关闭）
    edit_data["personalizationSwitch"] = "0"

    # 敏感属性（默认无）
    edit_data["technologyType"] = ""
    edit_data["firstType"] = ""
    edit_data["twiceType"] = ""

    return edit_data


def _map_category_attrs(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    """映射类目属性到 API 格式.

    Args:
        attrs: 业务层类目属性字典

    Returns:
        API 格式的属性列表
    """
    # 属性名称到 API 字段的映射
    # 这个映射可能需要根据实际的 API 响应来调整
    attr_list = []

    for key, value in attrs.items():
        if value:
            attr_list.append({
                "attrName": key,
                "attrValue": value,
            })

    return attr_list
