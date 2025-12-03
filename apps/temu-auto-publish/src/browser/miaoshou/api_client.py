"""
@PURPOSE: 妙手 ERP API 客户端，提供直接 HTTP 调用能力，绕过浏览器自动化
@OUTLINE:
  - class MiaoshouApiClient: API 客户端主类
    - 工厂方法:
      - async def from_playwright_context(): 从 Playwright 上下文创建客户端
      - async def from_cookie_file(): 从 Cookie 文件创建客户端
    - 认领 API:
      - async def get_product_list(): 获取通用采集箱产品列表
      - async def claim_products(): 批量认领产品
      - async def claim_single_product(): 认领单个产品
      - async def claim_unclaimed_products(): 获取并认领未认领产品
    - 批量编辑 API:
      - async def search_temu_collect_box(): 搜索 Temu 平台采集箱
      - async def get_collect_item_info(): 获取产品编辑信息
      - async def save_collect_item_info(): 保存产品编辑信息
      - async def batch_edit_products(): 批量编辑产品（高级方法）
      - async def batch_edit_single_product(): 编辑单个产品
    - 文件上传 API:
      - async def upload_picture_file(): 上传图片（外包装图、轮播图等）
      - async def upload_attach_file(): 上传附件（产品说明书 PDF）
      - async def get_item_options(): 获取商品选项（外包装形状/类型）
@DEPENDENCIES:
  - 外部: httpx, json
  - 内部: ..cookie_manager.CookieManager
@RELATED: claim.py, cookie_manager.py, batch_edit_codegen.py
@CHANGELOG:
  - 2025-12-03: 新增批量编辑 API (search_temu_collect_box, get/save_collect_item_info)
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

import httpx
from loguru import logger
from playwright.async_api import BrowserContext

from ..cookie_manager import CookieManager


class MiaoshouApiClient:
    """妙手 ERP API 客户端.

    提供直接 HTTP 调用能力，可用于：
    - 批量认领产品（绕过浏览器虚拟列表定位）
    - 获取产品列表
    - 其他 API 操作

    Examples:
        >>> # 从 Playwright 上下文创建
        >>> client = await MiaoshouApiClient.from_playwright_context(context)
        >>> products = await client.get_product_list(limit=20)
        >>> await client.claim_products(product_ids=["123", "456"], platform="pddkj")

        >>> # 从 Cookie 文件创建
        >>> client = await MiaoshouApiClient.from_cookie_file("data/cookies.json")
        >>> await client.claim_single_product(detail_id="123", platform="pddkj")
    """

    BASE_URL: ClassVar[str] = "https://erp.91miaoshou.com"
    API_PREFIX: ClassVar[str] = "/api/move/common_collect_box"
    # 批量编辑 API 前缀（平台特定）
    BATCH_EDIT_API_PREFIX: ClassVar[str] = "/api/platform/pddkj/move/collect_box"

    # 平台代码映射
    PLATFORM_CODES: ClassVar[dict[str, str]] = {
        "temu": "pddkj",
        "temu全托管": "pddkj",
        "pddkj": "pddkj",
    }

    # 批量编辑可用字段
    BATCH_EDIT_FIELDS: ClassVar[list[str]] = [
        "title",  # 标题
        "cid",  # 类目 ID
        "breadcrumb",  # 类目面包屑
        "multiLanguageTitleMap",  # 多语言标题（英语标题等）
        "attributes",  # 类目属性
        "itemNum",  # 主货号
        "productOriginCountry",  # 产地国家
        "productOriginProvince",  # 产地省份
        "productOriginCertFiles",  # 产地证明文件
        "outerPackageImgUrls",  # 外包装图片
        "outerPackageShape",  # 外包装形状
        "outerPackageType",  # 外包装类型
        "personalizationSwitch",  # 定制品开关
        "technologyType",  # 工艺类型（敏感属性）
        "firstType",  # 一级类型（敏感属性）
        "twiceType",  # 二级类型（敏感属性）
        "skuMap",  # SKU 数据（含重量/尺寸/价格）
        "saleAttributes",  # 销售属性
        "sizeCharts",  # 尺码表
        "collectShowSizeTemplateIds",  # 尺码模板 ID
        "thumbnail",  # 缩略图
        "collectBoxDetailShopList",  # 店铺列表
        "productGuideFileUrl",  # 产品说明书 PDF URL
    ]

    def __init__(self, cookies: list[dict[str, Any]]) -> None:
        """初始化 API 客户端.

        Args:
            cookies: Playwright 格式的 Cookie 列表
        """
        self._playwright_cookies = cookies
        self._http_cookies = self._convert_cookies(cookies)
        self._client: httpx.AsyncClient | None = None

    def _convert_cookies(self, playwright_cookies: list[dict[str, Any]]) -> dict[str, str]:
        """将 Playwright Cookie 转换为 httpx 可用格式.

        Args:
            playwright_cookies: Playwright context.cookies() 返回的列表

        Returns:
            简单的 {name: value} 字典
        """
        return {cookie["name"]: cookie["value"] for cookie in playwright_cookies}

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                cookies=self._http_cookies,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": self.BASE_URL,
                    "Referer": f"{self.BASE_URL}/common_collect_box/items",
                },
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """关闭 HTTP 客户端."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @classmethod
    async def from_playwright_context(cls, context: BrowserContext) -> MiaoshouApiClient:
        """从 Playwright 浏览器上下文创建 API 客户端.

        Args:
            context: Playwright BrowserContext 实例

        Returns:
            配置好的 API 客户端实例

        Examples:
            >>> async with async_playwright() as p:
            ...     browser = await p.chromium.launch()
            ...     context = await browser.new_context()
            ...     # ... 登录操作 ...
            ...     client = await MiaoshouApiClient.from_playwright_context(context)
        """
        cookies = await context.cookies()
        logger.debug(f"从 Playwright 上下文获取到 {len(cookies)} 个 Cookie")
        return cls(cookies)

    @classmethod
    async def from_cookie_file(
        cls, cookie_file: str = "data/temp/miaoshou_cookies.json"
    ) -> MiaoshouApiClient | None:
        """从 Cookie 文件创建 API 客户端.

        Args:
            cookie_file: Cookie 文件路径

        Returns:
            API 客户端实例，如果 Cookie 无效则返回 None

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> if client:
            ...     products = await client.get_product_list()
        """
        manager = CookieManager(cookie_file)
        cookies = manager.load_playwright_cookies()

        if not cookies:
            logger.warning(f"无法从 {cookie_file} 加载有效的 Cookie")
            return None

        logger.debug(f"从文件加载了 {len(cookies)} 个 Cookie")
        return cls(cookies)

    async def get_product_list(
        self,
        *,
        tab: str = "all",
        page: int = 1,
        limit: int = 20,
        owner_account_id: str | None = None,
    ) -> dict[str, Any]:
        """获取采集箱产品列表.

        Args:
            tab: 标签页 ("all", "unclaimed", "claimed", "failed")
            page: 页码，从 1 开始
            limit: 每页数量
            owner_account_id: 创建人员账号 ID (如 "151538")

        Returns:
            API 响应，包含产品列表和总数

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.get_product_list(tab="unclaimed", limit=50)
            >>> print(f"共 {result['data']['total']} 个未认领产品")
        """
        client = await self._get_client()

        # 构建请求参数 - 使用实际抓取的 API 格式
        tab_mapping = {
            "all": "all",
            "unclaimed": "noClaimed",
            "claimed": "claimed",
            "failed": "failed",
        }

        params: dict[str, Any] = {
            "pageNo": page,
            "pageSize": limit,
            "filter[tabPaneName]": tab_mapping.get(tab, "all"),
        }

        if owner_account_id:
            params["filter[ownerAccountIds][0]"] = owner_account_id

        try:
            response = await client.post(
                f"{self.API_PREFIX}/searchDetailList",
                data=params,
            )
            response.raise_for_status()
            result = response.json()

            # API 响应格式: {result: 'success', detailList: [...], total: N}
            # 或 {code: 0, data: {list: [...], total: N}}
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
                logger.info(f"获取产品列表成功: {len(items)} 条 / 共 {total} 条")
            else:
                logger.warning(f"API 返回错误: {result.get('message', '未知错误')}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"获取产品列表失败: {e}")
            raise

    async def get_sub_accounts(self) -> dict[str, Any]:
        """获取子账号列表（用于映射名字到账号 ID）.

        Returns:
            API 响应，包含子账号列表

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.get_sub_accounts()
            >>> for acc in result.get("list", []):
            ...     print(f"{acc['aliasName']}: {acc['subAppAccountId']}")
        """
        client = await self._get_client()

        try:
            # 需要 POST 请求带上空 body
            response = await client.post(
                "/api/move/common_collect_box/getSubAccountList",
                data={},  # 空 body，但确保发送 POST
            )
            response.raise_for_status()

            # 调试：检查响应内容
            text = response.text
            if not text:
                logger.warning("get_sub_accounts: 响应为空")
                return {"result": "error", "message": "空响应", "list": []}

            try:
                result = response.json()
            except Exception as json_err:
                logger.error(f"get_sub_accounts JSON 解析失败: {json_err}")
                logger.debug(f"原始响应: {text[:500]}")
                return {"result": "error", "message": f"JSON 解析失败: {json_err}", "list": []}

            if result.get("result") == "success":
                accounts = result.get("list", [])
                logger.info(f"获取子账号列表成功: {len(accounts)} 个账号")
            else:
                logger.warning(f"获取子账号失败: {result.get('message')}")

            return result

        except Exception as e:
            logger.error(f"获取子账号列表失败: {e}")
            return {"result": "error", "message": str(e), "list": []}

    async def find_owner_account_id(self, owner_name: str) -> str | None:
        """根据创建人员名字查找账号 ID.

        Args:
            owner_name: 创建人员名字 (如 "李英亮" 或 "李英亮(lyl123456789)")

        Returns:
            账号 ID 或 None
        """
        # 提取名字部分
        name_part = owner_name.strip()
        if "(" in name_part:
            name_part = name_part.split("(")[0].strip()

        try:
            result = await self.get_sub_accounts()
            if result.get("result") == "success":
                for acc in result.get("list", []):
                    alias_name = acc.get("aliasName", "")
                    # 尝试匹配 aliasName 或 name
                    if name_part in alias_name or name_part == acc.get("name", ""):
                        account_id = str(acc.get("subAppAccountId", ""))
                        logger.info(f"找到账号: {alias_name} -> ID {account_id}")
                        return account_id
            logger.warning(f"未找到创建人员 '{name_part}' 的账号 ID")
            return None
        except Exception as e:
            logger.error(f"查找账号 ID 失败: {e}")
            return None

    async def claim_products(
        self,
        *,
        detail_ids: list[str],
        platform: str = "pddkj",
    ) -> dict[str, Any]:
        """批量认领产品.

        Args:
            detail_ids: 采集箱产品 ID 列表
            platform: 平台代码 ("pddkj" = Temu全托管)

        Returns:
            API 响应

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.claim_products(
            ...     detail_ids=["3049643700", "3049643667"],
            ...     platform="pddkj"
            ... )
            >>> print(f"认领结果: {result}")
        """
        # 规范化平台代码
        platform_code = self.PLATFORM_CODES.get(platform.lower(), platform)

        client = await self._get_client()

        # 构建表单数据
        # 格式: detailSerialNumberPlatformList[0][detailId]=xxx&...
        form_data: dict[str, str] = {}
        for idx, detail_id in enumerate(detail_ids):
            prefix = f"detailSerialNumberPlatformList[{idx}]"
            form_data[f"{prefix}[detailId]"] = str(detail_id)
            form_data[f"{prefix}[platform]"] = platform_code
            form_data[f"{prefix}[serialNumber]"] = str(idx + 1)

        try:
            response = await client.post(
                f"{self.API_PREFIX}/claimed",
                data=form_data,
            )
            response.raise_for_status()
            result = response.json()

            # 兼容两种响应格式
            is_success = result.get("result") == "success" or result.get("code") == 0
            if is_success:
                logger.success(f"批量认领成功: {len(detail_ids)} 个产品")
            else:
                logger.warning(f"认领失败: {result.get('message', '未知错误')}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"批量认领失败: {e}")
            raise

    async def claim_single_product(
        self,
        *,
        detail_id: str,
        platform: str = "pddkj",
    ) -> dict[str, Any]:
        """认领单个产品.

        Args:
            detail_id: 采集箱产品 ID
            platform: 平台代码

        Returns:
            API 响应

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.claim_single_product(
            ...     detail_id="3049643700",
            ...     platform="pddkj"
            ... )
        """
        return await self.claim_products(detail_ids=[detail_id], platform=platform)

    async def claim_unclaimed_products(
        self,
        *,
        count: int = 10,
        platform: str = "pddkj",
        owner_account: str | None = None,
    ) -> dict[str, Any]:
        """获取并认领指定数量的未认领产品.

        这是一个便捷方法，组合了获取列表和认领操作。

        Args:
            count: 要认领的产品数量
            platform: 平台代码
            owner_account: 创建人员筛选（支持部分匹配，如 "陈昊" 将匹配 "陈昊（新）(CHENHAO123)"）

        Returns:
            包含认领结果的字典

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.claim_unclaimed_products(count=5)
            >>> print(f"成功认领 {result['claimed_count']} 个产品")
        """
        # 如果需要按人员筛选，获取更多产品然后客户端过滤
        # API 不支持 owner 筛选参数，需要在客户端过滤
        fetch_limit = count * 5 if owner_account else count  # 多获取一些以便筛选

        # 获取未认领产品列表
        list_result = await self.get_product_list(
            tab="unclaimed",
            limit=fetch_limit,
        )

        # 兼容两种响应格式
        is_success = list_result.get("result") == "success" or list_result.get("code") == 0
        if not is_success:
            return {
                "success": False,
                "message": f"获取产品列表失败: {list_result.get('message')}",
                "claimed_count": 0,
            }

        # 兼容两种响应格式: detailList 或 data.list
        if "detailList" in list_result:
            items = list_result.get("detailList", [])
        else:
            items = list_result.get("data", {}).get("list", [])

        if not items:
            return {
                "success": True,
                "message": "没有未认领的产品",
                "claimed_count": 0,
            }

        # 客户端筛选：如果指定了 owner_account，按 ownerSubAccountAliasName 过滤
        if owner_account:
            # 提取名字部分（去掉账号），支持 "李英亮(lyl123456789)" 格式
            owner_filter = owner_account.strip()
            if "(" in owner_filter:
                owner_filter = owner_filter.split("(")[0].strip()

            filtered_items = [
                item
                for item in items
                if owner_filter in (item.get("ownerSubAccountAliasName") or "")
            ]
            if filtered_items:
                logger.info(
                    f"按创建人员筛选: '{owner_filter}' 匹配到 {len(filtered_items)}/{len(items)} 个产品"
                )
                items = filtered_items[:count]  # 只取需要的数量
            else:
                logger.warning(f"未找到匹配 '{owner_filter}' 的产品")
                return {
                    "success": False,
                    "message": f"未找到创建人员 '{owner_filter}' 的产品",
                    "claimed_count": 0,
                }
        else:
            items = items[:count]

        # 提取产品 ID (使用 commonCollectBoxDetailId 或 detailId)
        detail_ids = [
            str(item.get("commonCollectBoxDetailId") or item.get("detailId") or item.get("id"))
            for item in items
        ]
        detail_ids = [did for did in detail_ids if did and did != "None"]

        if not detail_ids:
            return {
                "success": False,
                "message": "无法提取产品 ID",
                "claimed_count": 0,
            }

        # 执行认领
        claim_result = await self.claim_products(detail_ids=detail_ids, platform=platform)

        # 兼容认领响应格式
        claim_success = claim_result.get("result") == "success" or claim_result.get("code") == 0
        return {
            "success": claim_success,
            "message": claim_result.get("message", "认领完成"),
            "claimed_count": len(detail_ids) if claim_success else 0,
            "detail_ids": detail_ids,
            "api_response": claim_result,
        }

    # ===== 批量编辑 API =====

    async def search_temu_collect_box(
        self,
        *,
        status: str = "notPublished",
        claim_status: str = "published",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """搜索 Temu 平台采集箱产品列表.

        注意：此 API 返回的是已认领到 Temu 平台的产品，
        其 collectBoxDetailId 可用于 get_collect_item_info 和 save_collect_item_info。

        Args:
            status: 发布状态 ("notPublished", "published", "fail")
            claim_status: 认领状态 ("published" = 已认领)
            page: 页码
            page_size: 每页数量

        Returns:
            包含产品列表的响应，每个产品有 collectBoxDetailId 字段

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.search_temu_collect_box(page_size=50)
            >>> for item in result.get("detailList", []):
            ...     print(f"{item['collectBoxDetailId']}: {item.get('cid')}")
        """
        client = await self._get_client()

        form_data = {
            "claimPublishShopStatus": claim_status,
            "status": status,
            "pageNo": str(page),
            "pageSize": str(page_size),
        }

        try:
            response = await client.post(
                f"{self.BATCH_EDIT_API_PREFIX}/searchCollectBoxDetail",
                data=form_data,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("result") == "success":
                items = result.get("detailList", [])
                logger.debug(f"搜索 Temu 采集箱成功: {len(items)} 个产品")
            else:
                logger.warning(f"搜索失败: {result.get('message', '未知错误')}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"搜索 Temu 采集箱失败: {e}")
            raise

    async def get_collect_item_info(
        self,
        *,
        detail_ids: list[str],
        fields: list[str] | None = None,
        site: str = "PDDKJ",
    ) -> dict[str, Any]:
        """获取产品编辑信息（用于批量编辑）.

        Args:
            detail_ids: 产品 ID 列表
            fields: 要获取的字段列表，默认获取 title 和 cid
            site: 平台站点代码

        Returns:
            包含产品编辑信息的响应

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.get_collect_item_info(
            ...     detail_ids=["2478360327", "2478360326"],
            ...     fields=["title", "cid", "attributes"]
            ... )
            >>> for item in result.get("collectItemInfoList", []):
            ...     print(f"{item['detailId']}: {item['title']}")
        """
        if fields is None:
            fields = ["title", "cid"]

        client = await self._get_client()

        # 构建表单数据
        # 格式: sites[0]=PDDKJ&detailIds[0]=xxx&detailIds[1]=xxx&fields[0]=title
        form_data: dict[str, str] = {"sites[0]": site}
        for idx, detail_id in enumerate(detail_ids):
            form_data[f"detailIds[{idx}]"] = str(detail_id)
        for idx, field in enumerate(fields):
            form_data[f"fields[{idx}]"] = field

        try:
            response = await client.post(
                f"{self.BATCH_EDIT_API_PREFIX}/getCollectItemInfoList",
                data=form_data,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("result") == "success":
                items = result.get("collectItemInfoList", [])
                logger.debug(f"获取产品编辑信息成功: {len(items)} 个产品")
            else:
                logger.warning(f"获取产品编辑信息失败: {result.get('message', '未知错误')}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"获取产品编辑信息失败: {e}")
            raise

    async def save_collect_item_info(
        self,
        *,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """保存产品编辑信息（批量编辑核心 API）.

        Args:
            items: 产品信息列表，每个项目至少包含 site 和 detailId，
                   可包含其他要更新的字段（如 title, cid, attributes 等）

        Returns:
            API 响应，包含 successNum 和 failNum

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.save_collect_item_info(items=[
            ...     {
            ...         "site": "PDDKJ",
            ...         "detailId": "2478360327",
            ...         "title": "新标题",
            ...         "cid": "32233"
            ...     }
            ... ])
            >>> print(f"成功: {result['successNum']}, 失败: {result['failNum']}")
        """
        client = await self._get_client()

        # 构建表单数据
        # 格式: collectItemInfoList=[{...JSON...}]
        form_data = {"collectItemInfoList": json.dumps(items, ensure_ascii=False)}

        try:
            response = await client.post(
                f"{self.BATCH_EDIT_API_PREFIX}/saveCollectItemInfoList",
                data=form_data,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("result") == "success":
                success_num = result.get("successNum", 0)
                fail_num = result.get("failNum", 0)
                logger.info(f"保存产品编辑信息: 成功 {success_num}, 失败 {fail_num}")
                if result.get("errorMap"):
                    logger.warning(f"错误详情: {result['errorMap']}")
            else:
                logger.warning(f"保存失败: {result.get('message', '未知错误')}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"保存产品编辑信息失败: {e}")
            raise

    async def batch_edit_products(
        self,
        *,
        detail_ids: list[str],
        edits: dict[str, Any],
        site: str = "PDDKJ",
    ) -> dict[str, Any]:
        """批量编辑产品（高级方法，对所有产品应用相同的编辑）.

        这是一个便捷方法，对指定的所有产品应用相同的编辑内容。

        Args:
            detail_ids: 产品 ID 列表
            edits: 要应用的编辑内容，可包含以下字段：
                - title: 标题
                - cid: 类目 ID
                - breadcrumb: 类目面包屑
                - multiLanguageTitleMap: 多语言标题 {"en": "English title"}
                - attributes: 类目属性列表
                - itemNum: 主货号
                - productOriginCountry/Province: 产地
                - outerPackageImgUrls/Shape/Type: 外包装
                - personalizationSwitch: 定制品开关 (0/1)
                - technologyType/firstType/twiceType: 敏感属性
                - skuMap: SKU 数据
                - saleAttributes: 销售属性
                - sizeCharts: 尺码表
            site: 平台站点代码

        Returns:
            包含成功/失败统计的结果

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> # 批量更新标题
            >>> result = await client.batch_edit_products(
            ...     detail_ids=["123", "456", "789"],
            ...     edits={"title": "统一的新标题"}
            ... )
            >>> # 批量更新产地
            >>> result = await client.batch_edit_products(
            ...     detail_ids=["123", "456"],
            ...     edits={
            ...         "productOriginCountry": "CN",
            ...         "productOriginProvince": "广东省"
            ...     }
            ... )
        """
        # 构建每个产品的编辑数据
        items = []
        for detail_id in detail_ids:
            item = {"site": site, "detailId": str(detail_id)}
            item.update(edits)
            items.append(item)

        # 调用保存 API
        result = await self.save_collect_item_info(items=items)

        # 构建统一的返回格式
        is_success = result.get("result") == "success"
        return {
            "success": is_success,
            "total": len(detail_ids),
            "success_count": result.get("successNum", 0) if is_success else 0,
            "fail_count": result.get("failNum", 0) if is_success else len(detail_ids),
            "error_map": result.get("errorMap", {}),
            "api_response": result,
        }

    async def batch_edit_single_product(
        self,
        *,
        detail_id: str,
        edits: dict[str, Any],
        site: str = "PDDKJ",
    ) -> dict[str, Any]:
        """编辑单个产品.

        Args:
            detail_id: 产品 ID
            edits: 要应用的编辑内容
            site: 平台站点代码

        Returns:
            API 响应

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.batch_edit_single_product(
            ...     detail_id="2478360327",
            ...     edits={"title": "新标题", "cid": "32233"}
            ... )
        """
        return await self.batch_edit_products(detail_ids=[detail_id], edits=edits, site=site)

    # ===== 文件上传 API =====

    async def upload_picture_file(
        self,
        *,
        file_path: str,
    ) -> dict[str, Any]:
        """上传图片文件（用于外包装图、轮播图、颜色图等）.

        Args:
            file_path: 图片文件的本地路径

        Returns:
            API 响应，包含:
            - picturePath: 图片 URL
            - appPictureId: 图片 ID
            - width/height: 图片尺寸
            - md5: 文件 MD5

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.upload_picture_file(file_path="/path/to/image.jpg")
            >>> print(f"图片 URL: {result['picturePath']}")
        """
        import mimetypes
        from pathlib import Path

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {"result": "error", "message": f"文件不存在: {file_path}"}

        # 获取 MIME 类型
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = "image/jpeg"

        client = await self._get_client()

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path_obj.name, f, mime_type)}
                # 文件上传需要不同的 Content-Type，移除默认的
                response = await client.post(
                    "/api/picture/picture/uploadPictureFile",
                    files=files,
                    headers={"Content-Type": None},  # 让 httpx 自动设置 multipart
                )
            response.raise_for_status()
            result = response.json()

            if result.get("result") == "success":
                logger.debug(f"图片上传成功: {result.get('picturePath')}")
            else:
                logger.warning(f"图片上传失败: {result.get('message', '未知错误')}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"图片上传失败: {e}")
            raise

    async def upload_attach_file(
        self,
        *,
        file_path: str,
        platform: str = "pddkj",
    ) -> dict[str, Any]:
        """上传附件文件（用于产品说明书等 PDF 文档）.

        Args:
            file_path: 文件的本地路径
            platform: 平台代码

        Returns:
            API 响应，包含:
            - fileUrl: 文件 URL
            - appAttachFileId: 文件 ID
            - ossPath: OSS 路径

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.upload_attach_file(file_path="/path/to/manual.pdf")
            >>> print(f"说明书 URL: {result['fileUrl']}")
        """
        import mimetypes
        from pathlib import Path

        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {"result": "error", "message": f"文件不存在: {file_path}"}

        # 获取 MIME 类型
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            mime_type = "application/pdf"

        client = await self._get_client()

        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_path_obj.name, f, mime_type)}
                data = {"platform": platform}
                response = await client.post(
                    "/api/appAttachFile/app_attach_file/upload_attach_file",
                    files=files,
                    data=data,
                    headers={"Content-Type": None},
                )
            response.raise_for_status()
            result = response.json()

            if result.get("result") == "success":
                logger.debug(f"附件上传成功: {result.get('fileUrl')}")
            else:
                logger.warning(f"附件上传失败: {result.get('message', '未知错误')}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"附件上传失败: {e}")
            raise

    async def get_item_options(self) -> dict[str, Any]:
        """获取商品编辑选项（外包装形状、类型等）.

        Returns:
            API 响应，包含:
            - outerPackageShapeOptions: 外包装形状选项列表
            - outerPackageTypeOptions: 外包装类型选项列表

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> options = await client.get_item_options()
            >>> for opt in options.get("outerPackageShapeOptions", []):
            ...     print(f"{opt['key']}: {opt['value']}")
        """
        client = await self._get_client()

        try:
            response = await client.get(
                f"{self.BATCH_EDIT_API_PREFIX}/getItemOptions",
            )
            response.raise_for_status()
            result = response.json()

            if result.get("result") == "success":
                logger.debug("获取商品选项成功")
            else:
                logger.warning(f"获取商品选项失败: {result.get('message', '未知错误')}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"获取商品选项失败: {e}")
            raise

    async def publish_to_shop(
        self,
        *,
        detail_ids: list[str],
        shop_id: str = "9134811",
    ) -> dict[str, Any]:
        """发布产品到店铺.

        Args:
            detail_ids: 产品 collectBoxDetailId 列表
            shop_id: 店铺 ID（默认 9134811）

        Returns:
            API 响应，包含:
            - result: "success" 或 "error"
            - message: 错误信息（如果有）

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.publish_to_shop(
            ...     detail_ids=["123", "456"],
            ...     shop_id="9134811"
            ... )
        """
        client = await self._get_client()

        # 构建表单数据
        form_data: dict[str, Any] = {}
        for i, detail_id in enumerate(detail_ids):
            form_data[f"detailIds[{i}]"] = detail_id
        form_data["shopIds[0]"] = shop_id

        try:
            # 调用发布 API
            response = await client.post(
                "/api/platform/pddkj/move/move_collect/saveMoveCollectTask",
                data=form_data,
            )
            response.raise_for_status()
            result = response.json()

            if result.get("result") == "success":
                logger.info(f"发布任务创建成功: {len(detail_ids)} 个产品")
            else:
                logger.warning(f"发布失败: {result.get('message', '未知错误')}")

            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误: {e.response.status_code}")
            return {"result": "error", "message": f"HTTP {e.response.status_code}"}
        except Exception as e:
            logger.error(f"发布失败: {e}")
            return {"result": "error", "message": str(e)}

    async def __aenter__(self) -> MiaoshouApiClient:
        """异步上下文管理器入口."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """异步上下文管理器退出，自动关闭客户端."""
        await self.close()
