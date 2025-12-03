"""
@PURPOSE: 使用通用采集箱 API 执行首次编辑流程，替代 DOM 操作方式
@OUTLINE:
  - async def run_first_edit_via_api(): 主入口函数
  - async def _process_single_product(): 处理单个产品
  - def _update_product_detail(): 更新产品详情字段
@DEPENDENCIES:
  - 内部: api_client.MiaoshouApiClient
  - 外部: playwright
@RELATED: api_client.py, first_edit_dialog_codegen.py, complete_publish_workflow.py
@CHANGELOG:
  - 2025-12-04: 重写使用通用采集箱 API (getEditCommonBoxDetail/saveEditCommonBoxDetail)
  - 2025-12-04: 移除型号匹配逻辑，改为按选品表顺序分配选品数据
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loguru import logger
from playwright.async_api import Page

from ...data_processor.price_calculator import PriceResult
from ...data_processor.random_generator import RandomDataGenerator
from ...data_processor.selection_table_reader import ProductSelectionRow
from .api_client import MiaoshouApiClient

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext


@dataclass
class FirstEditApiResult:
    """首次编辑 API 结果."""

    success: bool
    processed_count: int
    success_count: int
    failed_count: int
    error_details: list[dict[str, Any]]


async def run_first_edit_via_api(
    page: Page,
    selections: list[ProductSelectionRow],
    *,
    filter_owner: str | None = None,
    max_count: int | None = None,
) -> FirstEditApiResult:
    """使用通用采集箱 API 执行首次编辑.

    一次性处理所有选品数据对应的产品，不分轮次。
    产品和选品按顺序一一对应。

    使用的 API:
    - get_product_list(): 获取产品列表
    - get_edit_common_box_detail(): 获取产品编辑信息
    - save_edit_common_box_detail(): 保存产品编辑

    流程:
    1. 从浏览器会话创建 API 客户端
    2. 获取产品列表（按创建人员筛选）
    3. 取前 N 个产品（N = 选品数量或 max_count）
    4. 遍历每个产品，与选品数据一一对应进行编辑

    Args:
        page: Playwright Page 实例，用于获取 Cookie
        selections: 选品数据列表（决定处理数量）
        filter_owner: 筛选的创建人员（可选）
        max_count: 最多处理的产品数量（默认 None = 选品数量）

    Returns:
        FirstEditApiResult 结果对象

    Examples:
        >>> # 一次性处理所有选品
        >>> result = await run_first_edit_via_api(
        ...     page, selections,
        ...     filter_owner="张三",
        ... )
    """
    logger.info("开始使用通用采集箱 API 执行首次编辑...")

    # 从浏览器会话创建 API 客户端
    context: BrowserContext = page.context
    client = await MiaoshouApiClient.from_playwright_context(context)

    error_details: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0

    try:
        # 先查找创建人员的账号 ID（用于 API 筛选）
        owner_account_id: str | None = None
        if filter_owner:
            owner_account_id = await client.find_owner_account_id(filter_owner)
            if owner_account_id:
                logger.info(f"找到创建人员 '{filter_owner}' 的账号 ID: {owner_account_id}")
            else:
                logger.warning(f"未找到创建人员 '{filter_owner}' 的账号 ID，将在结果中筛选")

        # 获取全部产品列表（使用 "all" tab）
        # 如果有 owner_account_id，则在 API 层面筛选
        logger.info("获取产品列表...")
        list_result = await client.get_product_list(
            tab="all",
            limit=100,
            owner_account_id=owner_account_id,
        )

        if list_result.get("result") != "success":
            logger.error(f"获取产品列表失败: {list_result.get('message')}")
            return FirstEditApiResult(
                success=False,
                processed_count=0,
                success_count=0,
                failed_count=0,
                error_details=[{"error": "获取产品列表失败"}],
            )

        product_list = list_result.get("detailList", [])
        logger.info(f"找到 {len(product_list)} 个产品")

        # 调试：打印前几个产品的字段信息
        if product_list:
            sample_product = product_list[0]
            logger.debug(f"产品字段列表: {list(sample_product.keys())}")
            sample_owners = [p.get("ownerSubAccountAliasName", "N/A") for p in product_list[:5]]
            logger.debug(f"产品创建人样例: {sample_owners}")
            sample_ids = [str(p.get("commonCollectBoxDetailId", "N/A")) for p in product_list[:3]]
            logger.debug(f"产品 ID 样例: {sample_ids}")

        # 如果 API 层面未筛选（找不到账号 ID），则在结果中筛选
        if filter_owner and not owner_account_id:
            filtered = []
            for p in product_list:
                owner_name = p.get("ownerSubAccountAliasName") or p.get("ownerName", "")
                # 精确匹配或包含匹配
                if owner_name and (
                    owner_name == filter_owner
                    or filter_owner in owner_name
                    or owner_name in filter_owner
                ):
                    filtered.append(p)
            product_list = filtered
            logger.info(f"按创建人员 '{filter_owner}' 筛选后: {len(product_list)} 个产品")

        # 确定处理数量：优先使用 max_count，否则使用选品数量
        total_available = len(product_list)
        selection_count = len(selections)
        target_count = max_count if max_count is not None else selection_count

        if total_available == 0:
            logger.warning("没有可处理的产品")
            return FirstEditApiResult(
                success=True,
                processed_count=0,
                success_count=0,
                failed_count=0,
                error_details=[],
            )

        # 取产品和选品的较小值
        actual_count = min(target_count, total_available, selection_count)
        products_to_process = product_list[:actual_count]
        working_selections = selections[:actual_count]

        logger.info(
            f"一次性处理 {actual_count} 个产品 "
            f"(可用产品 {total_available} 个，选品 {selection_count} 条)"
        )

        # 按选品表顺序处理产品（不使用型号匹配）
        selection_index = 0

        # 处理每个产品
        for product in products_to_process:
            detail_id = str(product.get("commonCollectBoxDetailId", ""))
            product_title = product.get("title", "未知产品")

            if not detail_id:
                logger.warning(f"产品缺少 commonCollectBoxDetailId: {product_title[:30]}")
                failed_count += 1
                error_details.append(
                    {"detail_id": "unknown", "title": product_title, "error": "缺少产品ID"}
                )
                continue

            # 按顺序获取选品数据（从截取后的 working_selections 中获取）
            selection = (
                working_selections[selection_index]
                if selection_index < len(working_selections)
                else None
            )

            try:
                result = await _process_single_product(
                    client=client,
                    detail_id=detail_id,
                    product_info=product,
                    selection=selection,
                )
                # 无论成功失败，都推进选品索引
                selection_index += 1
                if result:
                    success_count += 1
                    logger.success(f"✓ [{detail_id}] {product_title[:30]} 编辑成功")
                else:
                    failed_count += 1
                    error_details.append(
                        {"detail_id": detail_id, "title": product_title, "error": "编辑失败"}
                    )
            except Exception as e:
                failed_count += 1
                error_details.append(
                    {"detail_id": detail_id, "title": product_title, "error": str(e)}
                )
                logger.error(f"✗ [{detail_id}] 处理失败: {e}")

        logger.info(
            f"首次编辑 API 完成: 成功 {success_count}, 失败 {failed_count}, "
            f"总计 {len(products_to_process)}"
        )

        return FirstEditApiResult(
            success=failed_count == 0,
            processed_count=len(products_to_process),
            success_count=success_count,
            failed_count=failed_count,
            error_details=error_details,
        )

    finally:
        await client.close()


async def _process_single_product(
    *,
    client: MiaoshouApiClient,
    detail_id: str,
    product_info: dict[str, Any],
    selection: ProductSelectionRow | None = None,
) -> bool:
    """处理单个产品的首次编辑.

    按选品表顺序分配选品数据，执行所有编辑操作。

    Args:
        client: API 客户端
        detail_id: 产品详情 ID (commonCollectBoxDetailId)
        product_info: 产品基本信息（来自列表）
        selection: 按顺序分配的选品数据

    Returns:
        是否成功
    """
    # 获取产品完整编辑信息
    info_result = await client.get_edit_common_box_detail(detail_id)

    if info_result.get("result") != "success":
        logger.warning(f"获取产品编辑信息失败: {detail_id} - {info_result.get('message')}")
        return False

    detail = info_result.get("editCommonBoxDetail")
    oss_md5 = info_result.get("ossMd5", "")

    if not detail:
        logger.warning(f"产品编辑信息为空: {detail_id}")
        return False

    original_title = detail.get("title", "")
    logger.debug(f"[{detail_id}] 原标题: {original_title[:50]}...")

    # 打印选品详情用于调试
    if selection:
        logger.debug(
            f"[{detail_id}] 使用选品: 型号={selection.model_number}, "
            f"spec_unit={selection.spec_unit}, "
            f"spec_options={selection.spec_options}, "
            f"sku_image_urls={len(selection.sku_image_urls) if selection.sku_image_urls else 0}个, "
            f"size_chart={bool(selection.size_chart_image_url)}, "
            f"video={bool(selection.product_video_url)}"
        )
    else:
        logger.debug(f"[{detail_id}] 无选品数据可用")

    # 更新产品详情（无论是否有选品数据都执行）
    updated_detail = _update_product_detail(
        detail=detail,
        selection=selection,
    )

    # 调试：打印关键字段的更新后值
    logger.debug(
        f"[{detail_id}] 更新后关键字段: "
        f"colorPropName={updated_detail.get('colorPropName')}, "
        f"sizeChart={updated_detail.get('sizeChart', '')[:50] if updated_detail.get('sizeChart') else '空'}, "
        f"mainImgVideoUrl={updated_detail.get('mainImgVideoUrl', '')[:50] if updated_detail.get('mainImgVideoUrl') else '空'}"
    )

    # 保存编辑
    save_result = await client.save_edit_common_box_detail(updated_detail, oss_md5)

    if save_result.get("result") == "success":
        return True

    logger.warning(f"保存失败: {detail_id} - {save_result.get('message')}")
    return False


def _update_product_detail(
    *,
    detail: dict[str, Any],
    selection: ProductSelectionRow | None,
) -> dict[str, Any]:
    """更新产品详情字段.

    无论是否有选品数据，都会执行以下更新：
    - skuMap: 库存=999, 重量=随机, 尺寸=随机
    - weight/packageLength/packageWidth/packageHeight: 顶层字段

    如果有选品数据，还会更新：
    - title: 标题（追加型号后缀）
    - colorPropName: 规格名称（如"型号"、"层"）
    - colorMap.{id}.name: 规格选项值（如"3层"、"4层"）
    - skuMap.price: SKU 价格
    - colorMap.imgUrls/imgUrl: SKU 图片
    - sizeChart: 尺寸图
    - mainImgVideoUrl: 产品视频

    Args:
        detail: 产品详情对象
        selection: 匹配的选品数据（可能为 None，此时仅更新基础字段）

    Returns:
        更新后的产品详情对象
    """
    # 生成随机数据（与 DOM 模式保持一致）
    random_gen = RandomDataGenerator()
    weight_g = random_gen.generate_weight()  # 5000-9999G
    length_cm, width_cm, height_cm = random_gen.generate_dimensions()  # 50-99cm, 长>宽>高

    # 更新标题（始终执行，即使没有选品数据也添加默认型号后缀）
    # 注意：不使用 title_generator，因为会导致 [TEMU_AI:...] 重复嵌套
    # 参考 DOM 模式的 _fill_title()，直接在原标题后追加型号
    original_title = detail.get("title", "")
    if selection and selection.model_number:
        model_suffix = f" {selection.model_number}"
        # 检查标题是否已包含型号，避免重复添加
        if selection.model_number not in original_title:
            detail["title"] = original_title + model_suffix
            logger.debug(f"更新标题: 追加型号 {selection.model_number}")
    else:
        logger.debug("保持原标题（无选品数据）")

    # 更新规格名称 (colorPropName)
    # DOM 模式使用 fill_first_spec_unit() 填写规格单位名称
    if selection and selection.spec_unit:
        detail["colorPropName"] = selection.spec_unit
        logger.debug(f"更新规格名称: {selection.spec_unit}")

    # 更新规格选项 (colorMap 中每个规格的 name 字段)
    # DOM 模式使用 replace_sku_spec_options() 替换规格选项
    # 注意：如果选品表规格数量 > colorMap 规格数量，需要添加新的规格条目
    if selection and selection.spec_options:
        color_map = detail.get("colorMap", {})
        sku_map = detail.get("skuMap", {})
        spec_options = selection.spec_options
        sku_image_urls = selection.sku_image_urls or []

        if isinstance(color_map, dict):
            existing_color_ids = list(color_map.keys())
            existing_count = len(existing_color_ids)
            needed_count = len(spec_options)

            logger.debug(
                f"规格数量对比: 现有={existing_count}, 需要={needed_count}, "
                f"现有IDs={existing_color_ids}"
            )

            # 更新现有的 colorMap 条目
            for idx, color_id in enumerate(existing_color_ids):
                color_data = color_map[color_id]
                if isinstance(color_data, dict) and idx < needed_count:
                    color_data["name"] = spec_options[idx]
                    # 同时更新图片
                    if idx < len(sku_image_urls):
                        img_url = sku_image_urls[idx]
                        color_data["imgUrls"] = [img_url]
                        color_data["imgUrl"] = img_url

            # 如果需要更多规格，添加新的 colorMap 和 skuMap 条目
            if needed_count > existing_count:
                # 获取模板数据（用于复制结构）
                template_color_data = None
                template_sku_data = None
                if existing_color_ids:
                    first_color_id = existing_color_ids[0]
                    template_color_data = color_map.get(first_color_id, {})
                    # 查找对应的 skuMap 模板
                    for sku_key, sku_data in sku_map.items():
                        if f";{first_color_id};" in sku_key:
                            template_sku_data = sku_data
                            break

                for idx in range(existing_count, needed_count):
                    # 生成新的 color ID（使用时间戳确保唯一）
                    new_color_id = str(int(time.time() * 1000) + idx)

                    # 创建新的 colorMap 条目
                    new_color_data = {
                        "name": spec_options[idx],
                        "imgUrls": [],
                        "imgUrl": "",
                    }
                    # 如果有模板，复制其他字段
                    if template_color_data:
                        for key in template_color_data:
                            if key not in ["name", "imgUrls", "imgUrl"]:
                                new_color_data[key] = template_color_data[key]
                    # 设置图片
                    if idx < len(sku_image_urls):
                        img_url = sku_image_urls[idx]
                        new_color_data["imgUrls"] = [img_url]
                        new_color_data["imgUrl"] = img_url

                    color_map[new_color_id] = new_color_data

                    # 创建新的 skuMap 条目
                    new_sku_key = f";{new_color_id};;"
                    new_sku_data = {
                        "price": "",
                        "stock": "999",
                        "weight": str(weight_g),
                        "packageLength": str(length_cm),
                        "packageWidth": str(width_cm),
                        "packageHeight": str(height_cm),
                    }
                    # 如果有模板，复制其他字段
                    if template_sku_data:
                        for key in template_sku_data:
                            if key not in [
                                "price",
                                "stock",
                                "weight",
                                "packageLength",
                                "packageWidth",
                                "packageHeight",
                            ]:
                                new_sku_data[key] = template_sku_data[key]

                    sku_map[new_sku_key] = new_sku_data
                    logger.debug(
                        f"添加新规格 [{idx}]: colorId={new_color_id}, name={spec_options[idx]}"
                    )

                logger.info(f"扩展规格: 从 {existing_count} 个增加到 {needed_count} 个")

            # 如果现有规格比需要的多，删除多余的（保持与选品表一致）
            elif existing_count > needed_count:
                # 删除多余的 colorMap 和 skuMap 条目
                for idx in range(needed_count, existing_count):
                    color_id = existing_color_ids[idx]
                    del color_map[color_id]
                    # 删除对应的 skuMap 条目
                    sku_keys_to_delete = [k for k in sku_map if f";{color_id};" in k]
                    for sku_key in sku_keys_to_delete:
                        del sku_map[sku_key]
                    logger.debug(f"删除多余规格 [{idx}]: colorId={color_id}")

                logger.info(f"精简规格: 从 {existing_count} 个减少到 {needed_count} 个")

            logger.debug(f"更新规格选项: {spec_options}")

    # 更新 skuMap（始终执行库存、重量、尺寸更新）
    sku_map = detail.get("skuMap", {})
    if isinstance(sku_map, dict) and sku_map:
        # 计算价格（如果有选品数据）
        sale_price = None
        if selection and selection.cost_price:
            price_info = PriceResult.calculate(selection.cost_price)
            sale_price = str(price_info.suggested_price)

        for _sku_key, sku_data in sku_map.items():
            if isinstance(sku_data, dict):
                # 更新价格（仅当有选品数据时）
                if sale_price:
                    sku_data["price"] = sale_price
                # 始终更新库存
                sku_data["stock"] = "999"
                # 始终更新重量
                sku_data["weight"] = str(weight_g)
                # 始终更新尺寸
                sku_data["packageLength"] = str(length_cm)
                sku_data["packageWidth"] = str(width_cm)
                sku_data["packageHeight"] = str(height_cm)

        logger.debug(
            f"更新 SKU: 价格={sale_price or '保持原价'}, 库存=999, "
            f"重量={weight_g}g, 尺寸={length_cm}x{width_cm}x{height_cm}cm"
        )

    # 更新顶层的重量和尺寸（有些 API 需要这个）
    detail["weight"] = str(weight_g)
    detail["packageLength"] = str(length_cm)
    detail["packageWidth"] = str(width_cm)
    detail["packageHeight"] = str(height_cm)

    # 注意：SKU 图片已在规格更新逻辑中一并处理（colorMap.imgUrls/imgUrl）

    # 更新尺寸图
    if selection and selection.size_chart_image_url:
        detail["sizeChart"] = selection.size_chart_image_url
        logger.debug(f"更新尺寸图: {selection.size_chart_image_url}")
    else:
        logger.debug(
            f"跳过尺寸图更新: selection={bool(selection)}, "
            f"size_chart_image_url={selection.size_chart_image_url if selection else 'N/A'}"
        )

    # 更新视频
    if selection and selection.product_video_url:
        detail["mainImgVideoUrl"] = selection.product_video_url
        logger.debug(f"更新视频: {selection.product_video_url}")
    else:
        logger.debug(
            f"跳过视频更新: selection={bool(selection)}, "
            f"product_video_url={selection.product_video_url if selection else 'N/A'}"
        )

    # 注意：供货商链接 (sourceItemUrl) 在通用采集箱 API 中是只读字段
    # 来自 sourceList[].sourceItemUrl，用于记录商品来源
    # DOM 模式的 _fill_supplier_link() 是填写自定义供货商链接
    # 但在 API 中，该字段由系统自动生成，无需手动设置

    return detail
