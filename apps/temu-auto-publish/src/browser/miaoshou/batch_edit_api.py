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
    skip_ai_attrs: bool = False,
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
        skip_ai_attrs: 是否跳过 AI 属性补全（用于多轮编辑时只在首轮执行）

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

            # Step 4: 上传文件（如果提供）- 需要先导航到编辑页面获取上传组件
            uploaded_files = await _upload_files_for_products(
                page,
                client,
                outer_package_image=outer_package_image,
                product_guide_pdf=product_guide_pdf,
                detail_ids=detail_ids,
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

            # Step 7: 构建基础编辑数据
            logger.info("API 批量编辑: 构建编辑数据...")
            base_edit_data = _build_edit_payload(
                payload,
                uploaded_files=uploaded_files,
                outer_package_shape=outer_package_shape,
                outer_package_type=outer_package_type,
                shop_ids=shop_ids,
            )

            # Step 7.5: AI 属性补全（如果启用且非跳过）
            ai_attrs_map: dict[str, list[dict[str, Any]]] = {}
            use_ai_attrs = payload.get("use_ai_attrs", True) and not skip_ai_attrs

            if skip_ai_attrs:
                logger.info("API 批量编辑: 跳过 AI 属性补全（非首轮）")

            if use_ai_attrs:
                from ...data_processor.ai_category_attr_filler import (
                    AICategoryAttrFiller,
                    ProductAttrContext,
                )

                logger.info("API 批量编辑: 开始 AI 属性补全...")

                # 获取产品的类目、标题和现有属性信息
                attr_info_result = await client.get_collect_item_info(
                    detail_ids=detail_ids,
                    fields=["title", "cid", "attributes"],
                )

                if attr_info_result.get("result") == "success":
                    attr_filler = AICategoryAttrFiller(client)

                    # 建立 title -> collectBoxDetailId 映射（用于后续转换）
                    title_to_collect_box_id: dict[str, str] = {}
                    for search_item in items:
                        title = search_item.get("title", "")
                        collect_box_id = str(search_item.get("collectBoxDetailId", ""))
                        if title and collect_box_id:
                            title_to_collect_box_id[title] = collect_box_id
                    logger.info(
                        f"title 映射建立: {len(title_to_collect_box_id)} 个 "
                        f"(搜索结果 {len(items)} 个)"
                    )

                    # 构建产品上下文列表，同时建立 detailId -> collectBoxDetailId 映射
                    detail_id_to_collect_box_id: dict[str, str] = {}
                    contexts = []
                    for item in attr_info_result.get("collectItemInfoList", []):
                        detail_id = str(item.get("detailId"))
                        item_title = item.get("title", "")
                        cid = item.get("cid", "")

                        # 通过 title 找到对应的 collectBoxDetailId
                        collect_box_id = title_to_collect_box_id.get(item_title)
                        if collect_box_id:
                            detail_id_to_collect_box_id[detail_id] = collect_box_id
                        else:
                            # title 匹配失败，打印警告帮助诊断
                            logger.warning(
                                f"title 匹配失败: detailId={detail_id}, "
                                f"title='{item_title[:60]}...'"
                            )

                        # 从搜索结果中查找 breadcrumb
                        breadcrumb = ""
                        for search_item in items:
                            if search_item.get("title") == item_title:
                                cat_map = search_item.get("siteAndCatMap", {}).get("PDDKJ", {})
                                breadcrumb = cat_map.get("breadcrumb", "")
                                break

                        contexts.append(
                            ProductAttrContext(
                                detail_id=detail_id,
                                title=item_title,
                                cid=cid,
                                breadcrumb=breadcrumb,
                                existing_attrs=item.get("attributes", []),
                            )
                        )

                    logger.debug(f"ID 映射建立完成: {len(detail_id_to_collect_box_id)} 个产品")

                    # 批量补全属性
                    if contexts:
                        ai_attrs_raw = await attr_filler.fill_batch_attrs(contexts)
                        logger.info(f"AI 属性补全完成: {len(ai_attrs_raw)} 个产品")

                        # 转换为 API 格式，使用 collectBoxDetailId 作为键
                        cid_map = {str(ctx.detail_id): ctx.cid for ctx in contexts}
                        for detail_id, attrs in ai_attrs_raw.items():
                            str_id = str(detail_id)
                            cid = cid_map.get(str_id)
                            if cid:
                                api_attrs = attr_filler.convert_to_api_format(cid, attrs)
                                # 转换为 collectBoxDetailId 作为键
                                collect_box_id = detail_id_to_collect_box_id.get(str_id)
                                if collect_box_id:
                                    ai_attrs_map[collect_box_id] = api_attrs
                                else:
                                    logger.warning(f"无法找到 detailId={str_id} 对应的 collectBoxDetailId")
                        logger.info(f"属性格式转换完成: {len(ai_attrs_map)} 个产品")
                        # 调试日志：检查 ID 匹配情况
                        if ai_attrs_map and detail_ids:
                            sample_key = next(iter(ai_attrs_map.keys()))
                            logger.debug(
                                f"ID 匹配检查: ai_attrs_map 键={sample_key} "
                                f"(type={type(sample_key).__name__}), "
                                f"detail_ids[0]={detail_ids[0]} "
                                f"(type={type(detail_ids[0]).__name__})"
                            )
                            if ai_attrs_map.get(sample_key):
                                logger.debug(f"属性值样例: {ai_attrs_map[sample_key][:2]}")
                else:
                    logger.warning("获取产品属性信息失败，跳过 AI 属性补全")

            # Step 8: 获取每个产品的 SKU 信息并计算价格
            logger.info("API 批量编辑: 获取产品 SKU 信息...")
            item_info_result = await client.get_collect_item_info(
                detail_ids=detail_ids,
                fields=["skuMap"],
            )

            # 构建每个产品的编辑数据（包含价格 ×10 的 skuMap 和 AI 属性）
            # 统计 AI 属性应用情况
            ai_matched = sum(1 for d in detail_ids if str(d) in ai_attrs_map)
            ai_missing = len(detail_ids) - ai_matched
            logger.info(
                f"AI 属性匹配统计: ai_attrs_map={len(ai_attrs_map)} 个, "
                f"detail_ids={len(detail_ids)} 个, "
                f"匹配成功={ai_matched}, 未匹配={ai_missing}"
            )
            if ai_missing > 0:
                # 打印前 5 个未匹配的 ID 帮助诊断
                missing_ids = [str(d) for d in detail_ids if str(d) not in ai_attrs_map][:5]
                ai_keys = list(ai_attrs_map.keys())[:5]
                logger.warning(
                    f"未匹配 ID 样例: {missing_ids}, "
                    f"ai_attrs_map 键样例: {ai_keys}"
                )

            items_to_save = []
            if item_info_result.get("result") == "success":
                # 通过 title 建立 collectBoxDetailId -> SKU 信息映射
                item_info_list = item_info_result.get("collectItemInfoList", [])
                item_info_map: dict[str, dict] = {}
                for item in item_info_list:
                    item_title = item.get("title", "")
                    # 从搜索结果中通过 title 找到 collectBoxDetailId
                    for search_item in items:
                        if search_item.get("title") == item_title:
                            collect_box_id = str(search_item.get("collectBoxDetailId", ""))
                            if collect_box_id:
                                item_info_map[collect_box_id] = item
                            break

                for detail_id in detail_ids:
                    item_data = {"site": "PDDKJ", "detailId": str(detail_id)}
                    item_data.update(base_edit_data)

                    # 合并 AI 推断的属性（优先于静态配置）
                    str_detail_id = str(detail_id)
                    if str_detail_id in ai_attrs_map:
                        item_data["attributes"] = ai_attrs_map[str_detail_id]
                        logger.debug(
                            f"产品 {detail_id}: 设置 {len(ai_attrs_map[str_detail_id])} 个 AI 属性"
                        )

                    # 获取该产品的 SKU 信息并计算价格
                    product_info = item_info_map.get(str(detail_id), {})
                    sku_map = product_info.get("skuMap", {})
                    if sku_map:
                        updated_sku_map = _update_sku_prices(sku_map)
                        item_data["skuMap"] = updated_sku_map
                        logger.debug(f"产品 {detail_id}: 更新 {len(sku_map)} 个 SKU 价格")

                    items_to_save.append(item_data)
            else:
                # 如果获取 SKU 信息失败，使用基础编辑数据
                logger.warning("获取 SKU 信息失败，跳过价格计算")
                for detail_id in detail_ids:
                    item_data = {"site": "PDDKJ", "detailId": str(detail_id)}
                    item_data.update(base_edit_data)
                    # 合并 AI 推断的属性
                    str_detail_id = str(detail_id)
                    if str_detail_id in ai_attrs_map:
                        item_data["attributes"] = ai_attrs_map[str_detail_id]
                        logger.debug(
                            f"产品 {detail_id}: 设置 {len(ai_attrs_map[str_detail_id])} 个 AI 属性"
                        )
                    items_to_save.append(item_data)

            # Step 9: 批量保存编辑
            logger.info(f"API 批量编辑: 保存 {len(items_to_save)} 个产品...")
            edit_result = await client.save_collect_item_info(items=items_to_save)

            if edit_result.get("result") == "success":
                result["success"] = True
                result["edited_count"] = edit_result.get("successNum", len(detail_ids))
                logger.success(
                    f"API 批量编辑完成: 成功 {result['edited_count']}/{result['total_count']}"
                )
            else:
                result["error"] = f"保存编辑失败: {edit_result.get('errorMap', {})}"
                result["edited_count"] = edit_result.get("successNum", 0)
                logger.warning(result["error"])

    except Exception as e:
        result["error"] = f"API 批量编辑异常: {e}"
        logger.exception(result["error"])

    return result


async def _upload_pdf_via_page(page: Page, pdf_path: str) -> dict[str, Any]:
    """通过页面的 axios 上传 PDF 文件.

    Args:
        page: Playwright Page 对象
        pdf_path: PDF 文件的本地路径

    Returns:
        上传结果，包含 result, fileUrl 等字段
    """
    import asyncio
    import base64

    result: dict[str, Any] = {"result": "error", "message": "上传未完成"}

    # 设置响应监听器
    upload_response: dict[str, Any] = {}

    async def handle_response(response):
        if "upload_attach_file" in response.url:
            try:
                body = await response.json()
                upload_response.update(body)
            except Exception:
                pass

    page.on("response", handle_response)

    try:
        # 读取文件并转为 base64
        with open(pdf_path, "rb") as f:
            file_data = base64.b64encode(f.read()).decode("utf-8")

        file_name = Path(pdf_path).name

        # 使用页面的 axios 发送请求
        await page.evaluate(
            """
            async (params) => {
                try {
                    // 将 base64 转换为 Blob
                    const binaryString = atob(params.fileData);
                    const bytes = new Uint8Array(binaryString.length);
                    for (let i = 0; i < binaryString.length; i++) {
                        bytes[i] = binaryString.charCodeAt(i);
                    }
                    const file = new File([bytes], params.fileName, { type: 'application/pdf' });

                    // 创建 FormData
                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('platform', 'pddkj');

                    // 使用页面的 axios 发送请求（会经过拦截器）
                    if (window.axios) {
                        await window.axios.post(
                            '/api/appAttachFile/app_attach_file/upload_attach_file',
                            formData
                        );
                    }
                } catch (e) {
                    console.error('PDF上传失败:', e);
                }
            }
            """,
            {
                "fileData": file_data,
                "fileName": file_name,
            },
        )

        # 等待上传完成
        for _ in range(30):  # 最多等待 3 秒
            await asyncio.sleep(0.1)
            if upload_response:
                break

        result = upload_response or {"result": "error", "message": "上传超时"}

    except Exception as e:
        result = {"result": "error", "message": str(e)}
    finally:
        page.remove_listener("response", handle_response)

    return result


async def _wait_for_loading_mask(page: Page, timeout: int = 10000) -> None:
    """等待加载遮罩消失.

    Args:
        page: Playwright Page 对象
        timeout: 超时时间（毫秒）
    """
    loading_selectors = [
        ".jx-loading-mask",
        ".el-loading-mask",
        ".loading-mask",
    ]

    for selector in loading_selectors:
        try:
            mask = page.locator(selector)
            if await mask.count() > 0 and await mask.first.is_visible():
                logger.debug(f"等待加载遮罩消失: {selector}")
                await mask.first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass


async def _close_popups(page: Page) -> int:
    """关闭页面上的各种弹窗.

    Returns:
        关闭的弹窗数量
    """
    closed = 0

    # 先等待加载遮罩消失
    await _wait_for_loading_mask(page)

    # jx-overlay 公告弹窗的关闭按钮
    overlay_close_selectors = [
        ".jx-overlay .jx-icon-close",
        ".jx-overlay [class*='close']",
        ".jx-overlay button:has-text('关闭')",
        ".jx-overlay button:has-text('我知道了')",
    ]

    # 常规弹窗关闭按钮
    popup_buttons = [
        "text='我知道了'",
        "text='知道了'",
        "text='确定'",
        "text='关闭'",
        "text='我已知晓'",
        "text='跳过'",
        "text='下次再说'",
        "button:has-text('我已知晓')",
        "button:has-text('跳过')",
        ".el-dialog__headerbtn",
        ".jx-dialog__headerbtn",
        "button[aria-label='关闭']",
        ".el-icon-close",
        ".jx-icon-close",
    ]

    # 先尝试关闭 overlay 弹窗
    for selector in overlay_close_selectors:
        try:
            locator = page.locator(selector)
            count = await locator.count()
            if count > 0:
                for i in range(count):
                    try:
                        btn = locator.nth(i)
                        if await btn.is_visible():
                            await btn.click(timeout=1000)
                            closed += 1
                            logger.debug(f"关闭 overlay 弹窗: {selector}")
                            await page.wait_for_timeout(500)
                    except Exception:
                        pass
        except Exception:
            pass

    # 再关闭常规弹窗
    for selector in popup_buttons:
        try:
            locator = page.locator(selector)
            count = await locator.count()
            if count > 0:
                for i in range(count):
                    try:
                        btn = locator.nth(i)
                        if await btn.is_visible():
                            await btn.click(timeout=1000)
                            closed += 1
                            logger.debug(f"关闭弹窗: {selector}")
                            await page.wait_for_timeout(300)
                    except Exception:
                        pass
        except Exception:
            pass

    return closed


async def _upload_image_via_page(
    page: Page, image_path: str, detail_ids: list[str] | None = None
) -> dict[str, Any]:
    """通过打开批量编辑对话框上传图片.

    流程：
    1. 确保在采集箱列表页面
    2. 关闭各种弹窗
    3. 点击"批量编辑"打开对话框
    4. 在对话框中找到图片上传组件
    5. 使用 set_input_files 上传图片

    Args:
        page: Playwright Page 对象
        image_path: 图片文件的本地路径
        detail_ids: 产品 ID 列表（未使用，保留兼容性）

    Returns:
        上传结果，包含 result, picturePath 等字段
    """
    import asyncio

    result: dict[str, Any] = {"result": "error", "message": "上传未完成"}

    # 设置响应监听器
    upload_response: dict[str, Any] = {}

    async def handle_response(response):
        if "uploadPictureFile" in response.url:
            try:
                body = await response.json()
                upload_response.update(body)
            except Exception:
                pass

    page.on("response", handle_response)

    try:
        # 确保在采集箱列表页
        current_url = page.url
        if "collect_box/items" not in current_url:
            logger.debug("不在采集箱列表页，先导航到列表页")
            await page.goto("https://erp.91miaoshou.com/pddkj/collect_box/items")
            await page.wait_for_timeout(2000)

        # 等待加载遮罩消失
        await _wait_for_loading_mask(page, timeout=15000)

        # 关闭各种弹窗（多次尝试，确保所有弹窗都关闭）
        for _ in range(10):
            closed = await _close_popups(page)
            if closed == 0:
                # 额外等待一下，看是否有新弹窗出现
                await page.wait_for_timeout(500)
                closed = await _close_popups(page)
                if closed == 0:
                    break
            await page.wait_for_timeout(500)

        # 再次等待加载遮罩消失
        await _wait_for_loading_mask(page, timeout=5000)

        # 等待表格加载完成
        table_selector = ".el-table, .jx-table, table"
        try:
            await page.wait_for_selector(table_selector, timeout=10000)
            logger.debug("表格已加载")
        except Exception:
            logger.warning("等待表格超时，继续尝试")

        # 先勾选第一个产品（批量编辑按钮需要先选中产品）
        checkbox_selectors = [
            ".el-table__body .el-checkbox__input:not(.is-checked)",
            ".jx-table__body .jx-checkbox__input:not(.is-checked)",
            "table tbody input[type='checkbox']:not(:checked)",
            ".el-checkbox__inner",
            ".jx-checkbox__inner",
        ]

        checkbox_clicked = False
        for selector in checkbox_selectors:
            try:
                checkboxes = page.locator(selector)
                count = await checkboxes.count()
                if count > 0:
                    # 点击第一个未选中的复选框
                    first_checkbox = checkboxes.first
                    if await first_checkbox.is_visible():
                        await first_checkbox.click(timeout=3000)
                        checkbox_clicked = True
                        logger.debug(f"已勾选第一个产品: {selector}")
                        await page.wait_for_timeout(500)
                        break
            except Exception as e:
                logger.debug(f"勾选产品失败 ({selector}): {e}")

        if not checkbox_clicked:
            logger.warning("未能勾选产品，尝试直接点击批量编辑按钮")

        # 点击"批量编辑"按钮（带重试）
        batch_edit_selectors = [
            "button:has-text('批量编辑')",
            ".el-button:has-text('批量编辑')",
            ".jx-button:has-text('批量编辑')",
            "text='批量编辑'",
        ]

        clicked = False
        for _ in range(3):
            for selector in batch_edit_selectors:
                try:
                    btn = page.locator(selector)
                    if await btn.count() > 0 and await btn.first.is_visible():
                        await btn.first.click(timeout=5000)
                        logger.debug(f"已点击批量编辑按钮: {selector}")
                        clicked = True
                        break
                except Exception as e:
                    logger.debug(f"点击批量编辑按钮失败 ({selector}): {e}")

            if clicked:
                break

            # 重试前再次尝试关闭弹窗和勾选产品
            await _close_popups(page)
            await _wait_for_loading_mask(page, timeout=3000)
            await page.wait_for_timeout(1000)

            # 如果没勾选成功，再试一次勾选
            if not checkbox_clicked:
                for selector in checkbox_selectors:
                    try:
                        checkboxes = page.locator(selector)
                        if await checkboxes.count() > 0:
                            await checkboxes.first.click(timeout=2000)
                            checkbox_clicked = True
                            logger.debug(f"重试勾选产品成功: {selector}")
                            await page.wait_for_timeout(500)
                            break
                    except Exception:
                        pass

        if not clicked:
            result = {"result": "error", "message": "无法点击批量编辑按钮"}
            return result

        await page.wait_for_timeout(2000)

        # 查找文件上传 input
        file_inputs = page.locator('input[type="file"]')
        count = await file_inputs.count()
        logger.debug(f"找到 {count} 个文件上传 input")

        if count == 0:
            result = {"result": "error", "message": "页面上没有可用的上传组件"}
            return result

        # 使用最后一个 file input（通常是外包装图片的）
        await file_inputs.last.set_input_files(image_path)
        logger.debug(f"已设置文件: {image_path}")

        # 等待上传完成（增加超时时间到 15 秒）
        for _ in range(150):  # 最多等待 15 秒
            await asyncio.sleep(0.1)
            if upload_response:
                break

        if upload_response:
            result = upload_response
            logger.info(f"图片上传成功: {result.get('picturePath')}")
        else:
            result = {"result": "error", "message": "上传超时（15秒）"}
            logger.error("外包装图片上传超时，请检查网络连接")

    except Exception as e:
        result = {"result": "error", "message": str(e)}
        logger.error(f"上传异常: {e}")
    finally:
        # 移除监听器
        page.remove_listener("response", handle_response)

        # 关闭对话框
        await _close_popups(page)

        # 刷新页面回到干净状态
        await page.reload()
        await page.wait_for_timeout(1000)

    return result


async def _upload_files_for_products(
    page: Page,
    client: MiaoshouApiClient,
    *,
    outer_package_image: str | None = None,
    product_guide_pdf: str | None = None,
    detail_ids: list[str] | None = None,
) -> dict[str, Any]:
    """为产品上传所需文件.

    Args:
        page: Playwright Page 对象，用于浏览器端上传
        client: API 客户端（备用）
        outer_package_image: 外包装图片路径
        product_guide_pdf: 产品说明书 PDF 路径
        detail_ids: 产品 ID 列表，用于导航到编辑页面获取上传组件

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

    # 上传外包装图片（使用页面 el-upload 组件的 file input，带重试机制）
    if outer_package_image and Path(outer_package_image).exists():
        logger.info(f"API 批量编辑: 上传外包装图片 {outer_package_image}...")
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                # 需要导航到编辑页面以获取上传组件
                upload_result = await _upload_image_via_page(page, outer_package_image, detail_ids)
                if upload_result and upload_result.get("result") == "success":
                    uploaded["outer_package_url"] = upload_result.get("picturePath")
                    logger.info(f"外包装图片上传成功: {uploaded['outer_package_url']}")
                    break
                else:
                    logger.warning(
                        f"外包装图片上传失败 (尝试 {attempt}/{max_retries}): {upload_result}"
                    )
                    if attempt < max_retries:
                        logger.info("等待 2 秒后重试...")
                        import asyncio

                        await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"外包装图片上传异常 (尝试 {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    import asyncio

                    await asyncio.sleep(2)

        if not uploaded["outer_package_url"]:
            logger.error(f"外包装图片上传失败，已重试 {max_retries} 次")

    # 上传产品说明书（使用页面的 axios）
    if product_guide_pdf and Path(product_guide_pdf).exists():
        logger.info(f"API 批量编辑: 上传产品说明书 {product_guide_pdf}...")
        try:
            upload_result = await _upload_pdf_via_page(page, product_guide_pdf)
            if upload_result and upload_result.get("result") == "success":
                uploaded["product_guide_url"] = upload_result.get("fileUrl")
                logger.info(f"产品说明书上传成功: {uploaded['product_guide_url']}")
            else:
                logger.warning(f"产品说明书上传失败: {upload_result}")
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
    logger.info("设置英语标题为空格")

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

    # 重量设置为固定值 9527 克（与首次编辑保持一致）
    edit_data["weight"] = "9527"
    logger.info("设置产品重量: 9527g")

    return edit_data


def _update_sku_prices(sku_map: dict[str, Any]) -> dict[str, Any]:
    """更新 SKU 价格、重量、尺寸等信息.

    Args:
        sku_map: 原始 SKU 映射

    Returns:
        更新后的 SKU 映射
    """
    import random

    updated_map = {}

    # 生成随机尺寸（与首次编辑保持一致：50-99cm，长>宽>高）
    dimensions = [random.randint(50, 99) for _ in range(3)]
    dimensions.sort(reverse=True)
    length_cm, width_cm, height_cm = dimensions

    for sku_key, sku_data in sku_map.items():
        if not isinstance(sku_data, dict):
            updated_map[sku_key] = sku_data
            continue

        # 复制 SKU 数据
        new_sku = dict(sku_data)

        # 获取供货价（尝试多个字段名，优先使用 originPrice）
        current_price = None
        for field_name in ["originPrice", "supplyPrice", "supplierPrice", "costPrice", "price"]:
            field_value = sku_data.get(field_name)
            if field_value:
                try:
                    current_price = float(field_value)
                    break
                except (ValueError, TypeError):
                    continue

        if current_price:
            # 建议售价 = 供货价 × 10
            suggested_price = round(current_price * 10, 2)
            new_sku["suggestedPrice"] = str(int(suggested_price))
            new_sku["suggestedPriceCurrencyType"] = "CNY"
            # 确保货源价格被设置，API 需要同时设置 oriPrice 和 originPrice
            ori_price_str = (
                str(int(current_price))
                if current_price == int(current_price)
                else str(current_price)
            )
            new_sku["oriPrice"] = ori_price_str
            new_sku["originPrice"] = str(current_price)
            logger.debug(f"SKU 价格更新: oriPrice={ori_price_str}, originPrice={current_price}")
        else:
            # 如果没有找到供货价，设置一个默认值
            default_price = 100
            new_sku["oriPrice"] = str(default_price)
            new_sku["originPrice"] = str(default_price)
            new_sku["suggestedPrice"] = str(default_price * 10)
            new_sku["suggestedPriceCurrencyType"] = "CNY"
            logger.warning(f"无法获取供货价，使用默认值 {default_price}")

        # SKU 分类设置为"单品 1 件"
        new_sku["skuClassification"] = 1  # 单品
        new_sku["numberOfPieces"] = "1"  # 1 件
        new_sku["pieceUnitCode"] = 1  # 件

        # 重量设置为固定值 9527 克
        new_sku["weight"] = "9527"

        # 库存设置为 999
        new_sku["stock"] = "999"

        # 尺寸设置（随机 50-99cm，长>宽>高）
        new_sku["packageLength"] = str(length_cm)
        new_sku["packageWidth"] = str(width_cm)
        new_sku["packageHeight"] = str(height_cm)

        # 平台 SKU（自定义编码）设置为空格
        new_sku["itemNum"] = " "

        updated_map[sku_key] = new_sku

    if updated_map:
        logger.info(
            f"更新 {len(updated_map)} 个 SKU: 重量=9527g, 库存=999, "
            f"尺寸={length_cm}x{width_cm}x{height_cm}cm"
        )

    return updated_map


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
