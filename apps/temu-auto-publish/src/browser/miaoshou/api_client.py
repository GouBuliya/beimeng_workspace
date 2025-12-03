"""
@PURPOSE: 妙手 ERP API 客户端，提供直接 HTTP 调用能力，绕过浏览器自动化
@OUTLINE:
  - class MiaoshouApiClient: API 客户端主类
    - async def from_playwright_context(): 从 Playwright 上下文创建客户端
    - async def from_cookie_file(): 从 Cookie 文件创建客户端
    - async def get_product_list(): 获取采集箱产品列表
    - async def claim_products(): 批量认领产品
    - async def claim_single_product(): 认领单个产品
@DEPENDENCIES:
  - 外部: httpx
  - 内部: ..cookie_manager.CookieManager
@RELATED: claim.py, cookie_manager.py
"""

from __future__ import annotations

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

    # 平台代码映射
    PLATFORM_CODES: ClassVar[dict[str, str]] = {
        "temu": "pddkj",
        "temu全托管": "pddkj",
        "pddkj": "pddkj",
    }

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
        owner_account: str | None = None,
    ) -> dict[str, Any]:
        """获取采集箱产品列表.

        Args:
            tab: 标签页 ("all", "unclaimed", "claimed", "failed")
            page: 页码，从 1 开始
            limit: 每页数量
            owner_account: 创建人员筛选

        Returns:
            API 响应，包含产品列表和总数

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.get_product_list(tab="unclaimed", limit=50)
            >>> print(f"共 {result['data']['total']} 个未认领产品")
        """
        client = await self._get_client()

        # 构建请求参数
        tab_mapping = {
            "all": "",
            "unclaimed": "0",
            "claimed": "1",
            "failed": "2",
        }

        params = {
            "page": page,
            "pageSize": limit,
            "tab": tab_mapping.get(tab, ""),
        }

        if owner_account:
            params["ownerAccount"] = owner_account

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
            owner_account: 创建人员筛选

        Returns:
            包含认领结果的字典

        Examples:
            >>> client = await MiaoshouApiClient.from_cookie_file()
            >>> result = await client.claim_unclaimed_products(count=5)
            >>> print(f"成功认领 {result['claimed_count']} 个产品")
        """
        # 获取未认领产品列表
        list_result = await self.get_product_list(
            tab="unclaimed",
            limit=count,
            owner_account=owner_account,
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

    async def __aenter__(self) -> MiaoshouApiClient:
        """异步上下文管理器入口."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """异步上下文管理器退出，自动关闭客户端."""
        await self.close()
