"""
@PURPOSE: API 方式执行批量编辑（完整 18 步），包括文件上传
@OUTLINE:
  - async def run_batch_edit_via_api(): 主入口，执行 API 批量编辑完整流程
  - async def _upload_files_for_products(): 为产品上传所需文件
  - def _build_edit_payload(): 从业务 payload 构建 API 编辑数据
  - def _map_category_attrs(): 映射类目属性到 API 格式
@DEPENDENCIES:
  - 内部: .api_client.MiaoshouApiClient
@RELATED: api_client.py, batch_edit_codegen.py, complete_publish_workflow.py
@CHANGELOG:
  - 2025-12-03: 支持完整 18 步，包括文件上传（外包装图、说明书）
"""

from __future__ import annotations

from pathlib import Path
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
    outer_package_image: str | None = None,
    product_guide_pdf: str | None = None,
    max_products: int = 20,
) -> dict[str, Any]:
    """使用 API 执行批量编辑完整 18 步.

    支持的编辑步骤：
    1. 标题 - 保持原标题
    2. 英语标题 - 保持原标题
    3. 类目属性 - 通过 payload["category_attrs"] 设置
    4. 主货号 - 保持原货号
    5. 外包装 - 通过 outer_package_image 上传
    6. 产地 - 默认设置为中国(CN)
    7. 定制品 - 默认关闭
    8. 敏感属性 - 默认无
    9-14. SKU 相关 - 保持原数据
    15. 包装清单 - 跳过（DOM 处理）
    16. 轮播图 - 跳过（DOM 处理）
    17. 颜色图 - 跳过（DOM 处理）
    18. 产品说明书 - 通过 product_guide_pdf 上传

    Args:
        page: Playwright 页面对象（用于获取 Cookie）
        payload: 业务参数字典，包含:
            - category_path: list[str] - 类目路径
            - category_attrs: dict - 类目属性
        filter_owner: 按创建人员筛选
        cookie_file: Cookie 文件路径（可选，默认从 page 获取）
        outer_package_image: 外包装图片本地路径
        product_guide_pdf: 产品说明书 PDF 本地路径
        max_products: 每次最多编辑的产品数量（默认 20）

    Returns:
        执行结果:
        {
            "success": bool,
            "edited_count": int,
            "total_count": int,
            "error": str | None,
            "detail_ids": list[str],
            "uploaded_files": dict,  # 上传的文件 URL
        }

    Examples:
        >>> result = await run_batch_edit_via_api(
        ...     page,
        ...     payload={"category_attrs": {"材质": "塑料"}},
        ...     filter_owner="陈昊",
        ...     outer_package_image="/path/to/package.jpg",
        ...     product_guide_pdf="/path/to/manual.pdf",
        ... )
        >>> print(f"编辑了 {result['edited_count']} 个产品")
    """
    result: dict[str, Any] = {
        "success": False,
        "edited_count": 0,
        "total_count": 0,
        "error": None,
        "detail_ids": [],
        "uploaded_files": {},
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
                page_size=100,
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

            # 限制每次编辑的产品数量
            if max_products > 0 and len(detail_ids) > max_products:
                logger.info(f"限制编辑数量: {len(detail_ids)} -> {max_products} 个产品")
                detail_ids = detail_ids[:max_products]

            result["total_count"] = len(detail_ids)
            result["detail_ids"] = detail_ids

            if not detail_ids:
                result["error"] = "无法提取产品 ID"
                logger.error(result["error"])
                return result

            logger.info(f"API 批量编辑: 准备编辑 {len(detail_ids)} 个产品")

            # Step 4: 上传文件（如果提供）
            uploaded_files = await _upload_files_for_products(
                client,
                outer_package_image=outer_package_image,
                product_guide_pdf=product_guide_pdf,
            )
            result["uploaded_files"] = uploaded_files

            # Step 5: 获取外包装选项
            outer_package_shape = None
            outer_package_type = None
            if outer_package_image:
                options_result = await client.get_item_options()
                if options_result.get("result") == "success":
                    # 默认使用"长方体"和第一个类型
                    shape_options = options_result.get("outerPackageShapeOptions", [])
                    type_options = options_result.get("outerPackageTypeOptions", [])
                    if shape_options:
                        # 找"长方体"或使用第一个
                        for opt in shape_options:
                            if opt.get("value") == "长方体":
                                outer_package_shape = opt.get("key")
                                break
                        if outer_package_shape is None:
                            outer_package_shape = shape_options[0].get("key")
                    if type_options:
                        outer_package_type = type_options[0].get("key")

            # Step 6: 获取店铺列表（默认全选）
            shop_ids: list[str] = []
            shop_result = await client.get_shop_list(platform="pddkj")
            if shop_result.get("result") == "success":
                shop_list = shop_result.get("shopList", [])
                # 只选择授权状态有效的店铺
                shop_ids = [
                    str(shop.get("shopId"))
                    for shop in shop_list
                    if shop.get("authStatus") == "valid" and shop.get("shopId")
                ]
                logger.info(f"API 批量编辑: 已获取 {len(shop_ids)} 个有效店铺")
            else:
                logger.warning("获取店铺列表失败，将使用默认店铺")

            # Step 7: 构建编辑数据
            logger.info("API 批量编辑: 构建编辑数据...")
            edit_data = _build_edit_payload(
                payload,
                uploaded_files=uploaded_files,
                outer_package_shape=outer_package_shape,
                outer_package_type=outer_package_type,
                shop_ids=shop_ids,
            )

            # Step 8: 批量保存编辑
            logger.info("API 批量编辑: 保存编辑数据...")
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


async def _upload_files_for_products(
    client: MiaoshouApiClient,
    *,
    outer_package_image: str | None = None,
    product_guide_pdf: str | None = None,
) -> dict[str, Any]:
    """为产品上传所需文件.

    Args:
        client: API 客户端
        outer_package_image: 外包装图片路径
        product_guide_pdf: 产品说明书 PDF 路径

    Returns:
        上传结果字典:
        {
            "outer_package_url": str | None,
            "product_guide_url": str | None,
        }
    """
    uploaded: dict[str, Any] = {
        "outer_package_url": None,
        "product_guide_url": None,
    }

    # 上传外包装图片
    if outer_package_image and Path(outer_package_image).exists():
        logger.info(f"API 批量编辑: 上传外包装图片 {outer_package_image}...")
        try:
            result = await client.upload_picture_file(file_path=outer_package_image)
            if result.get("result") == "success":
                uploaded["outer_package_url"] = result.get("picturePath")
                logger.info(f"外包装图片上传成功: {uploaded['outer_package_url']}")
            else:
                logger.warning(f"外包装图片上传失败: {result.get('message')}")
        except Exception as e:
            logger.error(f"外包装图片上传异常: {e}")

    # 上传产品说明书
    if product_guide_pdf and Path(product_guide_pdf).exists():
        logger.info(f"API 批量编辑: 上传产品说明书 {product_guide_pdf}...")
        try:
            result = await client.upload_attach_file(file_path=product_guide_pdf)
            if result.get("result") == "success":
                uploaded["product_guide_url"] = result.get("fileUrl")
                logger.info(f"产品说明书上传成功: {uploaded['product_guide_url']}")
            else:
                logger.warning(f"产品说明书上传失败: {result.get('message')}")
        except Exception as e:
            logger.error(f"产品说明书上传异常: {e}")

    return uploaded


def _build_edit_payload(
    payload: dict[str, Any],
    *,
    uploaded_files: dict[str, Any] | None = None,
    outer_package_shape: int | None = None,
    outer_package_type: int | None = None,
    shop_ids: list[str] | None = None,
) -> dict[str, Any]:
    """从业务 payload 构建 API 编辑数据.

    Args:
        payload: 业务参数字典
        uploaded_files: 已上传的文件 URL
        outer_package_shape: 外包装形状 key
        outer_package_type: 外包装类型 key
        shop_ids: 发布目标店铺 ID 列表（默认全选已授权店铺）

    Returns:
        API 可接受的编辑字段字典
    """
    edit_data: dict[str, Any] = {}
    uploaded_files = uploaded_files or {}

    # 类目属性映射
    if "category_attrs" in payload:
        attrs = payload["category_attrs"]
        if attrs:
            edit_data["attributes"] = _map_category_attrs(attrs)

    # 产地映射（默认设置为中国浙江省，代码 43000000000031）
    edit_data["productOriginCountry"] = "CN"
    edit_data["productOriginProvince"] = "43000000000031"
    edit_data["productOriginCertFiles"] = []

    # 英语标题设置为空格（必填但无实际内容）
    edit_data["multiLanguageTitleMap"] = {"en": " "}

    # 定制品开关（默认关闭）
    edit_data["personalizationSwitch"] = "0"

    # 敏感属性（默认无）
    edit_data["technologyType"] = ""
    edit_data["firstType"] = ""
    edit_data["twiceType"] = ""

    # 店铺列表（发布时必需，默认全选已授权店铺）
    if shop_ids:
        edit_data["collectBoxDetailShopList"] = [{"shopId": sid} for sid in shop_ids]
    else:
        # 如果没有获取到店铺列表，使用默认店铺
        edit_data["collectBoxDetailShopList"] = [{"shopId": "9134811"}]

    # 外包装图片
    outer_package_url = uploaded_files.get("outer_package_url")
    if outer_package_url:
        # 需要两张图片（正面和背面）
        edit_data["outerPackageImgUrls"] = [outer_package_url, outer_package_url]
        if outer_package_shape is not None:
            edit_data["outerPackageShape"] = str(outer_package_shape)
        if outer_package_type is not None:
            edit_data["outerPackageType"] = str(outer_package_type)

    # 产品说明书
    product_guide_url = uploaded_files.get("product_guide_url")
    if product_guide_url:
        edit_data["productGuideFileUrl"] = product_guide_url

    return edit_data


def _map_category_attrs(attrs: dict[str, Any]) -> list[dict[str, Any]]:
    """映射类目属性到 API 格式.

    Args:
        attrs: 业务层类目属性字典

    Returns:
        API 格式的属性列表
    """
    attr_list = []

    for key, value in attrs.items():
        if value:
            attr_list.append(
                {
                    "attrName": key,
                    "attrValue": value,
                }
            )

    return attr_list
