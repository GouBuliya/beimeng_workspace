"""
@PURPOSE: 生产级图片管理模块,负责商品图片的删除,上传和验证(SOP步骤4.3,4.4)
@OUTLINE:
  - class ImageManager: 图片管理主类
  - async def delete_image(): 删除指定图片
  - async def delete_images_batch(): 批量删除图片
  - async def upload_image_from_url(): 通过URL上传图片
  - async def upload_video_from_url(): 通过URL上传视频
  - async def get_images_info(): 获取当前图片信息
  - async def validate_image(): 验证图片格式和大小
@GOTCHAS:
  - 图片操作需要在"产品图片"tab中进行
  - 使用网络图片URL上传比本地上传更快
  - 批量操作需要等待UI更新
  - 删除操作不可逆,需要确认
@TECH_DEBT:
  - TODO: 添加AI视觉检测图片匹配度
  - TODO: 支持图片压缩和优化
@DEPENDENCIES:
  - 内部: utils.smart_locator
  - 外部: playwright, loguru
@RELATED: first_edit_controller.py, batch_edit_controller.py
"""

import asyncio
import json
import re
import time
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from loguru import logger
from playwright.async_api import Locator, Page

from ..utils.selector_race import TIMEOUTS, try_selectors_race


def _elapsed_ms(start: float) -> int:
    """返回从 start 到当前的毫秒数."""

    return int((time.perf_counter() - start) * 1000)


class ImageManager:
    """生产级图片管理器(SOP步骤4.3,4.4).

    负责商品图片和视频的完整管理:
    - 删除不匹配图片(头图/轮播图/SKU图)
    - 上传网络图片URL
    - 上传视频URL
    - 验证图片格式和大小
    - 批量操作支持

    Attributes:
        selectors: 选择器配置字典
        max_retries: 最大重试次数(默认3次)
        retry_delay: 重试延迟秒数(默认2秒)

    Examples:
        >>> manager = ImageManager()
        >>> await manager.delete_image(page, image_index=0, image_type="main")
        True
        >>> await manager.upload_image_from_url(page, "https://...", "carousel")
        True
    """

    # 支持的图片格式
    SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

    # 支持的视频格式
    SUPPORTED_VIDEO_FORMATS = {".mp4", ".avi", ".mov", ".webm"}

    # 图片大小限制(字节)
    MAX_IMAGE_SIZE = 3 * 1024 * 1024  # 3MB

    # 视频大小限制(字节)
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB

    def __init__(
        self,
        selector_path: str = "config/miaoshou_selectors_v2.json",
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        """初始化图片管理器.

        Args:
            selector_path: 选择器配置文件路径
            max_retries: 最大重试次数
            retry_delay: 重试延迟秒数

        Examples:
            >>> manager = ImageManager()
            >>> manager = ImageManager(max_retries=5, retry_delay=3.0)
        """
        self.selector_path = Path(selector_path)
        self.selectors = self._load_selectors()
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # URL 验证结果缓存(性能优化:避免重复验证)
        self._url_validation_cache: dict[str, tuple[bool, str]] = {}

        logger.info(f"图片管理器初始化完成(重试{max_retries}次,延迟{retry_delay}秒)")

    def _load_selectors(self) -> dict:
        """加载选择器配置.

        Returns:
            选择器配置字典

        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: JSON格式错误

        Examples:
            >>> selectors = manager._load_selectors()
            >>> "first_edit_dialog" in selectors
            True
        """
        try:
            if not self.selector_path.is_absolute():
                current_file = Path(__file__)
                project_root = current_file.parent.parent.parent
                selector_file = project_root / self.selector_path
            else:
                selector_file = self.selector_path

            with open(selector_file, encoding="utf-8") as f:
                config = json.load(f)
                logger.debug(f"选择器配置已加载: {selector_file}")
                return config
        except FileNotFoundError:
            logger.error(f"选择器配置文件不存在: {selector_file}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"选择器配置JSON格式错误: {e}")
            raise

    async def navigate_to_images_tab(self, page: Page) -> bool:
        """导航到产品图片Tab.

        Args:
            page: Playwright页面对象

        Returns:
            是否成功导航

        Examples:
            >>> await manager.navigate_to_images_tab(page)
            True
        """
        logger.info("导航到「产品图片」Tab...")

        pane = await self._locate_product_images_pane(page)
        if pane is None:
            logger.error("导航到产品图片Tab失败: 未找到滚动面板")
            return False

        label = pane.locator(".scroll-menu-pane__label").first
        try:
            with suppress(Exception):
                await label.scroll_into_view_if_needed()
            await label.wait_for(state="visible", timeout=TIMEOUTS.NORMAL)
            await label.click()
            # await page.wait_for_timeout(300)  # 已注释:不必要的等待
            logger.success("✓ 已切换到产品图片Tab")
            return True
        except Exception as exc:
            logger.error(f"导航到产品图片Tab失败: {exc}")
            return False

    async def get_images_info(self, page: Page) -> dict[str, list[dict]]:
        """获取当前所有图片信息.

        Args:
            page: Playwright页面对象

        Returns:
            图片信息字典:{
                "main_images": [{"index": 0, "src": "url", "alt": "text"}],
                "carousel_images": [...],
                "sku_images": [...]
            }

        Examples:
            >>> info = await manager.get_images_info(page)
            >>> len(info["main_images"])
            1
        """
        try:
            logger.info("正在获取图片信息...")

            # 确保在产品图片Tab
            await self.navigate_to_images_tab(page)

            images_info = {"main_images": [], "carousel_images": [], "sku_images": []}

            # TODO: 需要使用Codegen获取实际的图片元素选择器
            # 这里提供框架代码
            logger.warning("图片信息获取功能需要Codegen验证选择器")

            return images_info

        except Exception as e:
            logger.error(f"获取图片信息失败: {e}")
            return {"main_images": [], "carousel_images": [], "sku_images": []}

    def validate_url(self, url: str) -> tuple[bool, str]:
        """验证URL格式.

        Args:
            url: 图片或视频URL

        Returns:
            (是否有效, 错误信息)

        Examples:
            >>> manager.validate_url("https://example.com/image.jpg")
            (True, "")
            >>> manager.validate_url("invalid-url")
            (False, "URL格式无效")
        """
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                return False, "URL格式无效:缺少协议或域名"

            if result.scheme not in ["http", "https"]:
                return False, f"不支持的协议: {result.scheme}(仅支持http/https)"

            return True, ""

        except Exception as e:
            return False, f"URL解析错误: {e!s}"

    def validate_image_url(self, url: str) -> tuple[bool, str]:
        """验证图片URL(带缓存优化).

        Args:
            url: 图片URL

        Returns:
            (是否有效, 错误信息)

        Examples:
            >>> manager.validate_image_url("https://example.com/image.jpg")
            (True, "")
        """
        # 性能优化:使用缓存避免重复验证
        if url in self._url_validation_cache:
            return self._url_validation_cache[url]

        is_valid, error = self.validate_url(url)
        if not is_valid:
            self._url_validation_cache[url] = (False, error)
            return False, error

        # 检查文件扩展名
        parsed = urlparse(url)
        path = parsed.path.lower()

        if not any(path.endswith(ext) for ext in self.SUPPORTED_IMAGE_FORMATS):
            result = (
                False,
                f"不支持的图片格式.支持的格式: {', '.join(self.SUPPORTED_IMAGE_FORMATS)}",
            )
            self._url_validation_cache[url] = result
            return result

        self._url_validation_cache[url] = (True, "")
        return True, ""

    def validate_video_url(self, url: str) -> tuple[bool, str]:
        """验证视频URL.

        Args:
            url: 视频URL

        Returns:
            (是否有效, 错误信息)

        Examples:
            >>> manager.validate_video_url("https://example.com/video.mp4")
            (True, "")
        """
        is_valid, error = self.validate_url(url)
        if not is_valid:
            return False, error

        # 检查文件扩展名
        parsed = urlparse(url)
        path = parsed.path.lower()

        if not any(path.endswith(ext) for ext in self.SUPPORTED_VIDEO_FORMATS):
            return False, (
                f"不支持的视频格式.支持的格式: {', '.join(self.SUPPORTED_VIDEO_FORMATS)}"
            )

        return True, ""

    async def delete_image(
        self, page: Page, image_index: int, image_type: str = "carousel"
    ) -> bool:
        """删除指定图片.

        Args:
            page: Playwright页面对象
            image_index: 图片索引(从0开始)
            image_type: 图片类型("main"主图/"carousel"轮播图/"sku" SKU图)

        Returns:
            是否删除成功

        Raises:
            ValueError: image_type不合法

        Examples:
            >>> await manager.delete_image(page, 0, "main")
            True
            >>> await manager.delete_image(page, 2, "carousel")
            True
        """
        if image_type not in ["main", "carousel", "sku"]:
            raise ValueError(f"不支持的图片类型: {image_type}.支持的类型: main, carousel, sku")

        logger.info(f"删除图片: type={image_type}, index={image_index}")

        try:
            # 确保在产品图片Tab
            if not await self.navigate_to_images_tab(page):
                return False

            # TODO: 需要使用Codegen获取实际的删除按钮选择器
            # 框架代码:
            # 1. 定位到指定图片
            # 2. 悬停显示删除按钮
            # 3. 点击删除按钮
            # 4. 确认删除(如果有确认弹窗)

            logger.warning("删除图片功能需要Codegen验证选择器 - 需要实际录制操作获取准确的元素定位")

            # 等待删除操作完成
            # await page.wait_for_timeout(200)  # 已注释:不必要的等待

            logger.success(f"✓ 图片删除成功: {image_type}[{image_index}]")
            return True

        except Exception as e:
            logger.error(f"删除图片失败: {e}")
            return False

    async def delete_images_batch(
        self, page: Page, image_indices: list[int], image_type: str = "carousel"
    ) -> bool:
        """批量删除图片.

        Args:
            page: Playwright页面对象
            image_indices: 图片索引列表
            image_type: 图片类型

        Returns:
            是否全部删除成功

        Examples:
            >>> await manager.delete_images_batch(page, [0, 1, 2], "carousel")
            True
        """
        logger.info(
            f"批量删除图片: type={image_type}, count={len(image_indices)}, indices={image_indices}"
        )

        success_count = 0
        for index in image_indices:
            if await self.delete_image(page, index, image_type):
                success_count += 1
                logger.info(f"进度: {success_count}/{len(image_indices)}")
            else:
                logger.warning(f"图片删除失败: {image_type}[{index}]")

        all_success = success_count == len(image_indices)

        if all_success:
            logger.success(f"✓ 批量删除完成: 全部{len(image_indices)}张图片已删除")
        else:
            logger.warning(f"批量删除部分失败: 成功{success_count}/{len(image_indices)}")

        return all_success

    async def replace_sku_images_with_urls(
        self,
        page: Page,
        image_urls: Sequence[str],
    ) -> bool:
        """删除现有 SKU 图片,并通过 URL 列表重新上传.

        Args:
            page: Playwright 页面对象
            image_urls: SKU 图片 URL 序列

        Returns:
            bool: 若全部上传成功返回 True,否则 False
        """
        logger.info("开始同步 SKU 图片, 输入 {} 条 URL", len(image_urls))
        sanitized_urls = self._sanitize_image_urls(image_urls)
        if not sanitized_urls:
            logger.warning("SKU 图片同步被跳过: 未提供有效 URL")
            return False

        if not await self.navigate_to_images_tab(page):
            logger.error("SKU 图片同步失败: 无法切换到产品图片 Tab")
            return False

        deletion_success = await self._delete_existing_sku_images(page)
        if not deletion_success:
            logger.warning("未能清空现有 SKU 图片, 仍尝试上传新图片")

        sku_section = page.get_by_label("SKU图片:", exact=False)
        try:
            await sku_section.wait_for(state="visible", timeout=TIMEOUTS.SLOW)
        except Exception:
            logger.error("SKU 图片同步失败: 无法定位『SKU图片』区域")
            return False

        sku_rows = sku_section.locator(".pro-virtual-table__row")
        row_count = await sku_rows.count()
        if row_count == 0:
            logger.error("SKU 图片同步失败: 未检测到任何 SKU 行")
            return False

        target_count = len(sanitized_urls)
        if target_count == 0:
            logger.warning("SKU 图片同步被跳过: 清理后未获得有效 URL")
            return False

        if target_count > row_count:
            logger.warning(
                f"SKU 图片 URL 数量({target_count}) 超过 SKU 行数({row_count}), 仅处理前 {row_count} 行"
            )
            target_count = row_count

        # SKU 图片上传必须串行执行(UI 弹窗交互不支持并发)
        uploads = 0
        for index in range(target_count):
            url = sanitized_urls[index]
            row = sku_rows.nth(index)
            row_hint = f"SKU行{index + 1}"
            logger.info("上传 SKU 图片 [{}/{}]: {}", index + 1, target_count, url[:80])
            if await self._upload_single_sku_image(page, url, row=row, slot_hint=row_hint):
                uploads += 1
            else:
                logger.warning("SKU 图片上传失败: {} ({})", url, row_hint)

        expected_total = target_count
        inventory_ok = await self._wait_for_total_sku_images(sku_section, expected_total)

        all_success = uploads == target_count and inventory_ok
        if all_success:
            logger.success("✓ SKU 图片同步完成, 共 {} 张", uploads)
        else:
            logger.warning(
                f"SKU 图片同步部分失败: 成功 {uploads}/{target_count} "
                f"(DOM校验={'通过' if inventory_ok else '未通过'})"
            )
        return all_success

    async def upload_image_from_url(
        self, page: Page, image_url: str, image_type: str = "size_chart", retry_count: int = 0
    ) -> bool:
        """通过URL上传图片(SOP步骤4.4).

        Args:
            page: Playwright页面对象
            image_url: 图片URL
            image_type: 图片类型("main"主图/"carousel"轮播图/"sku"SKU图/"size_chart"尺寸图)
            retry_count: 当前重试次数(内部使用)

        Returns:
            是否上传成功

        Examples:
            >>> url = "https://example.com/size_chart.jpg"
            >>> await manager.upload_image_from_url(page, url, "size_chart")
            True
        """
        logger.info(f"上传图片: type={image_type}, url={image_url[:50]}...")

        # 验证URL
        is_valid, error = self.validate_image_url(image_url)
        if not is_valid:
            logger.error(f"图片URL验证失败: {error}")
            return False

        try:
            # 确保在产品图片Tab
            if not await self.navigate_to_images_tab(page):
                return False

            # TODO: 需要使用Codegen获取实际的"使用网络图片"按钮选择器
            # SOP要求:选择「使用网络图片」功能
            # 框架代码:
            # 1. 点击对应类型的上传区域
            # 2. 选择"使用网络图片"选项
            # 3. 输入URL
            # 4. 确认上传
            # 5. 等待上传完成

            logger.warning("上传图片功能需要Codegen验证选择器 - 需要实际录制「使用网络图片」操作")

            # 等待上传完成
            # await page.wait_for_timeout(500)  # 已注释:不必要的等待

            logger.success(f"✓ 图片上传成功: {image_type}")
            return True

        except Exception as e:
            logger.error(f"上传图片失败(第{retry_count + 1}次尝试): {e}")

            # 自动重试机制
            if retry_count < self.max_retries - 1:
                logger.info(
                    f"等待{self.retry_delay}秒后重试...({retry_count + 2}/{self.max_retries})"
                )
                await asyncio.sleep(self.retry_delay)
                return await self.upload_image_from_url(
                    page, image_url, image_type, retry_count + 1
                )
            else:
                logger.error(f"上传图片最终失败(已重试{self.max_retries}次)")
                return False

    async def upload_video_from_url(self, page: Page, video_url: str, retry_count: int = 0) -> bool:
        """通过URL上传视频(SOP步骤4.4).

        Args:
            page: Playwright页面对象
            video_url: 视频URL
            retry_count: 当前重试次数(内部使用)

        Returns:
            是否上传成功

        Examples:
            >>> url = "https://example.com/product_demo.mp4"
            >>> await manager.upload_video_from_url(page, url)
            True
        """
        logger.info(f"上传视频: url={video_url[:50]}...")

        # 验证URL
        is_valid, error = self.validate_video_url(video_url)
        if not is_valid:
            logger.error(f"视频URL验证失败: {error}")
            return False

        try:
            # 切换到产品视频Tab
            dialog_config = self.selectors.get("first_edit_dialog", {})
            nav_config = dialog_config.get("navigation", {})
            video_tab_selector = nav_config.get("product_video", "text='产品视频'")

            logger.info("切换到「产品视频」Tab...")
            await page.locator(video_tab_selector).click()
            # await page.wait_for_timeout(300)  # 已注释:不必要的等待

            # TODO: 需要使用Codegen获取实际的视频上传选择器
            # 框架代码:
            # 1. 点击上传视频按钮
            # 2. 选择"使用网络视频"或"输入URL"
            # 3. 输入视频URL
            # 4. 确认上传
            # 5. 等待上传和处理完成(视频可能需要更长时间)

            logger.warning("上传视频功能需要Codegen验证选择器 - 需要实际录制视频上传操作")

            # 视频上传和处理需要更长时间
            # await page.wait_for_timeout(1000)  # 已注释:不必要的等待

            logger.success("✓ 视频上传成功")
            return True

        except Exception as e:
            logger.error(f"上传视频失败(第{retry_count + 1}次尝试): {e}")

            # 自动重试机制
            if retry_count < self.max_retries - 1:
                logger.info(
                    f"等待{self.retry_delay}秒后重试...({retry_count + 2}/{self.max_retries})"
                )
                await asyncio.sleep(self.retry_delay)
                return await self.upload_video_from_url(page, video_url, retry_count + 1)
            else:
                logger.error(f"上传视频最终失败(已重试{self.max_retries}次)")
                return False

    async def batch_upload_images(
        self, page: Page, image_urls: list[dict[str, str]]
    ) -> dict[str, int]:
        """批量上传图片.

        Args:
            page: Playwright页面对象
            image_urls: 图片URL列表,格式: [{"url": "...", "type": "carousel"}, ...]

        Returns:
            统计结果: {"success": 成功数, "failed": 失败数, "total": 总数}

        Examples:
            >>> urls = [
            ...     {"url": "https://example.com/1.jpg", "type": "carousel"},
            ...     {"url": "https://example.com/2.jpg", "type": "carousel"},
            ...     {"url": "https://example.com/size.jpg", "type": "size_chart"}
            ... ]
            >>> result = await manager.batch_upload_images(page, urls)
            >>> result["success"]
            3
        """
        logger.info(f"批量上传图片: 共{len(image_urls)}张")

        success_count = 0
        failed_count = 0

        # 图片上传必须串行执行(UI 弹窗交互不支持并发)
        for i, image_info in enumerate(image_urls, 1):
            url = image_info.get("url", "")
            img_type = image_info.get("type", "carousel")

            logger.info(f"[{i}/{len(image_urls)}] 上传: {url[:50]}...")

            if await self.upload_image_from_url(page, url, img_type):
                success_count += 1
            else:
                failed_count += 1
                logger.warning(f"图片上传失败: {url}")

        result = {"success": success_count, "failed": failed_count, "total": len(image_urls)}

        logger.info("=" * 60)
        logger.info("批量上传完成:")
        logger.info(f"  成功: {success_count}")
        logger.info(f"  失败: {failed_count}")
        logger.info(f"  总计: {len(image_urls)}")
        logger.info("=" * 60)

        return result

    # --------------------------------------------------------------------- #
    # 内部辅助方法
    # --------------------------------------------------------------------- #

    def _product_images_config(self) -> dict[str, Any]:
        """读取产品图片相关选择器配置."""

        dialog_config = self.selectors.get("first_edit_dialog", {})
        return dialog_config.get("product_images", {})

    def _as_selector_list(self, selector: Any) -> list[str]:
        """将单个或列表选择器统一为列表."""

        if not selector:
            return []
        if isinstance(selector, str):
            return [selector]
        if isinstance(selector, (list, tuple, set)):
            return [str(item) for item in selector if str(item).strip()]
        return []

    def _sanitize_image_urls(self, image_urls: Sequence[str]) -> list[str]:
        """过滤并验证图片 URL."""

        sanitized: list[str] = []
        seen: set[str] = set()
        for raw in image_urls:
            text = str(raw).strip()
            if not text or text in seen:
                continue
            is_valid, error = self.validate_image_url(text)
            if not is_valid:
                logger.warning("SKU 图片 URL 无效: {} ({})", text, error)
                continue
            sanitized.append(text)
            seen.add(text)
        return sanitized

    async def _delete_existing_sku_images(self, page: Page) -> bool:
        """通过可视化按钮删除既有 SKU 图片."""

        overall_start = time.perf_counter()
        logger.debug("尝试清空现有 SKU 图片...")

        with suppress(Exception):
            edit_btn = page.get_by_role("button", name="编辑").first
            if await edit_btn.count():
                await edit_btn.wait_for(state="visible", timeout=TIMEOUTS.SLOW)
                await edit_btn.click()
                logger.debug("已点击 SKU 区域『编辑』按钮")

        try:
            sku_section = page.get_by_label("SKU图片:", exact=False)
            await sku_section.wait_for(state="visible", timeout=TIMEOUTS.SLOW)
            logger.debug(f"SKU 区域定位成功 (耗时 {_elapsed_ms(overall_start)}ms)")
        except Exception:
            logger.warning("未能定位到『SKU图片』区域, 跳过删除")
            return False

        image_items = sku_section.locator(
            ".picture-draggable-list .image-item, .picture-draggable-list img"
        )
        try:
            if await image_items.count() == 0:
                logger.debug("SKU 区域没有现有图片,无需清理")
                return True
        except Exception:
            logger.warning("无法统计 SKU 图片数量, 假定需要清理")

        if not await self._click_sku_bulk_button(
            sku_section, label="全选", log_label="『全选』", overall_start=overall_start
        ):
            return False

        if not await self._click_sku_bulk_button(
            sku_section, label="批量删除", log_label="『批量删除』", overall_start=overall_start
        ):
            return False

        if not await self._confirm_delete_dialog(page):
            logger.warning("删除确认失败")
            return False

        await self._wait_for_sku_cleanup(page, sku_section)
        logger.success(f"✓ SKU 区域旧图片已清空 (总耗时 {_elapsed_ms(overall_start)}ms)")
        return True

    async def _wait_for_sku_cleanup(
        self, page: Page, sku_section: Locator, timeout: int = TIMEOUTS.SLOW * 5
    ) -> None:
        """等待 SKU 图列表清空或成功提示出现(智能等待)."""
        wait_start = time.perf_counter()
        selector = ".picture-draggable-list .image-item, .picture-draggable-list img"

        # 优先使用 DOM 事件驱动等待
        with suppress(Exception):
            await page.wait_for_function(
                "(selector) => document.querySelectorAll(selector).length === 0",
                selector,
                timeout=timeout,
            )
            logger.debug(f"SKU 图片清理完成 (耗时 {_elapsed_ms(wait_start)}ms)")
            return

        # 降级: 使用指数退避轮询
        poll_interval = 0.05  # 初始 50ms
        max_interval = 0.2  # 最大 200ms
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (timeout / 1_000)
        while loop.time() < deadline:
            try:
                items = sku_section.locator(selector)
                if await items.count() == 0:
                    logger.debug(f"SKU 图片清理完成 (耗时 {_elapsed_ms(wait_start)}ms)")
                    return
            except Exception:
                pass
            await asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, max_interval)  # 指数退避

        logger.debug(f"SKU 图片清理等待超时 (耗时 {_elapsed_ms(wait_start)}ms)")

    async def _wait_for_total_sku_images(
        self, sku_section: Locator, expected: int, timeout: int = TIMEOUTS.SLOW * 5
    ) -> bool:
        """等待 SKU 区域图片数量达到预期(智能等待)."""
        if expected <= 0:
            return True

        start = time.perf_counter()
        selector = ".picture-draggable-list .image-item img, .picture-draggable-list img"

        # 优先使用 DOM 事件驱动等待
        with suppress(Exception):
            await sku_section.page.wait_for_function(
                "(args) => document.querySelectorAll(args.sel).length >= args.exp",
                {"sel": selector, "exp": expected},
                timeout=timeout,
            )
            logger.debug("SKU 图片总数已达到{} (耗时 {}ms)", expected, _elapsed_ms(start))
            return True

        # 降级: 使用指数退避轮询
        poll_interval = 0.05  # 初始 50ms
        max_interval = 0.2  # 最大 200ms
        images = sku_section.locator(selector)
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (timeout / 1_000)
        while loop.time() < deadline:
            try:
                count = await images.count()
                if count >= expected:
                    logger.debug("SKU 图片总数已达到{} (耗时 {}ms)", expected, _elapsed_ms(start))
                    return True
            except Exception:
                pass
            await asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, max_interval)  # 指数退避

        logger.warning(f"SKU 图片总数未在 {timeout}ms 内达到预期({expected})")
        return False

    async def _wait_for_row_image_increment(
        self,
        images_locator: Locator,
        previous_count: int,
        slot_hint: str,
        timeout: int = TIMEOUTS.SLOW * 5,
    ) -> bool:
        """等待单个 SKU 行的图片数量增加(智能等待)."""
        # 使用指数退避轮询策略
        poll_interval = 0.05  # 初始 50ms
        max_interval = 0.2  # 最大 200ms

        loop = asyncio.get_running_loop()
        deadline = loop.time() + (timeout / 1_000)
        while loop.time() < deadline:
            try:
                current = await images_locator.count()
                if current > previous_count:
                    logger.debug("{} 图片数: {} -> {}", slot_hint, previous_count, current)
                    return True
            except Exception:
                pass
            await asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, max_interval)  # 指数退避
        return False

    async def _click_sku_bulk_button(
        self,
        sku_section: Locator,
        *,
        label: str,
        log_label: str,
        overall_start: float,
        timeout: int = TIMEOUTS.SLOW,
    ) -> bool:
        """在 SKU 区域内点击批量操作按钮."""

        try:
            button = sku_section.get_by_role("button", name=re.compile(label)).first
            await button.wait_for(state="visible", timeout=timeout)
            await button.click()
            logger.debug(f"已点击{log_label}按钮 (耗时 {_elapsed_ms(overall_start)}ms)")
            return True
        except Exception as exc:
            logger.warning("点击{}失败: {}", log_label, exc)
            return False

    async def _confirm_delete_dialog(self, page: Page, timeout: int = TIMEOUTS.SLOW) -> bool:
        """使用并行竞速策略等待批量删除确认弹窗并点击"确定"."""
        dialog_start = time.perf_counter()

        dialog_selectors = [
            ".jx-overlay-message-box",
            ".jx-message-box",
            ".el-message-box",
        ]

        # 使用竞速策略查找弹窗
        dialog = await try_selectors_race(
            page,
            dialog_selectors,
            timeout_ms=timeout,
            context_name="删除确认弹窗",
        )

        if dialog is None:
            logger.warning(
                f"未检测到删除确认弹窗 (耗时 {_elapsed_ms(dialog_start)}ms)",
            )
            return False

        logger.debug(f"删除确认弹窗出现 (耗时 {_elapsed_ms(dialog_start)}ms)")

        # 在弹窗范围内查找确定按钮
        button_selectors = [
            "button:has-text('确定')",
            ".jx-message-box__btns .jx-button--primary",
            ".el-message-box__btns button.el-button--primary",
            "button[aria-label*='确定']",
        ]

        # 并行竞速查找按钮
        async def try_button(selector: str) -> Locator | None:
            try:
                btn = dialog.locator(selector).first
                if await btn.count() and await btn.is_visible(timeout=TIMEOUTS.FAST):
                    return btn
            except Exception:
                pass
            return None

        tasks = [asyncio.create_task(try_button(sel)) for sel in button_selectors]
        btn: Locator | None = None
        try:
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result is not None:
                    btn = result
                    break
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task

        if btn is not None:
            try:
                await btn.click(timeout=TIMEOUTS.SLOW)
                logger.debug(f"删除确认弹窗已点击按钮 (耗时 {_elapsed_ms(dialog_start)}ms)")
                await self._wait_for_message_box_dismissal(page)
                return True
            except Exception:
                pass

        # 降级: 使用 Escape 关闭弹窗
        with suppress(Exception):
            await page.keyboard.press("Escape")
            await self._wait_for_message_box_dismissal(page)
            logger.debug(f"删除确认弹窗通过 Escape 关闭 (耗时 {_elapsed_ms(dialog_start)}ms)")
            return True

        logger.warning("删除确认弹窗未找到可用按钮")
        return False

    async def _wait_for_message_box_dismissal(
        self, page: Page, timeout: int = TIMEOUTS.NORMAL
    ) -> None:
        """等待所有 message box 隐藏."""

        locator = page.locator(".jx-overlay-message-box, .jx-message-box, .el-message-box")
        with suppress(Exception):
            await locator.first.wait_for(state="hidden", timeout=timeout)

    async def _upload_single_sku_image(
        self,
        page: Page,
        image_url: str,
        *,
        row: Locator | None = None,
        slot_hint: str | None = None,
    ) -> bool:
        """使用网络图片入口上传单张 SKU 图."""

        # URL编码处理(处理中文路径)
        from urllib.parse import quote, urlparse, urlunparse

        try:
            parsed = urlparse(image_url)
            encoded_path = quote(parsed.path.encode("utf-8"), safe="/:@!$&'()*+,;=")
            encoded_url = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    encoded_path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )
            logger.debug(f"SKU图片URL编码: {image_url} -> {encoded_url}")
            image_url = encoded_url
        except Exception as e:
            logger.warning(f"SKU图片URL编码失败,使用原始URL: {e}")

        picture_scope = (row or page).locator(".picture-draggable-list").first
        if not await picture_scope.count():
            picture_scope = page.locator(".picture-draggable-list").first

        if not await picture_scope.count():
            logger.error("未找到 SKU 图片上传区域 ({})", slot_hint or "全局")
            return False

        try:
            add_slot = picture_scope.locator(".add-image-box .add-image-box-content").first
            await add_slot.wait_for(state="visible", timeout=TIMEOUTS.NORMAL)
            await add_slot.click()
        except Exception as exc:
            logger.error("点击『添加新图片』失败: {}", exc)
            return False

        try:
            network_btn = page.get_by_text("使用网络图片", exact=False).first
            await network_btn.wait_for(state="visible", timeout=TIMEOUTS.NORMAL)
            await network_btn.click()
        except Exception as exc:
            logger.error("未找到『使用网络图片』入口: {}", exc)
            return False

        try:
            textbox = page.get_by_role(
                "textbox", name=re.compile("请输入图片链接"), exact=False
            ).first
            await textbox.wait_for(state="visible", timeout=TIMEOUTS.NORMAL)
            await textbox.fill(image_url)
        except Exception as exc:
            logger.error("填写图片链接失败: {}", exc)
            return False

        # 勾选"同时保存图片到妙手图片空间"
        try:
            save_to_space_checkbox = page.get_by_text("同时保存图片到妙手图片空间", exact=False)
            if await save_to_space_checkbox.count():
                await save_to_space_checkbox.click()
                logger.debug("已勾选『同时保存图片到妙手图片空间』")
        except Exception as exc:
            logger.debug("勾选保存到图片空间失败(可能已勾选): {}", exc)

        try:
            confirm_btn = page.get_by_role("button", name="确定").first
            await confirm_btn.wait_for(state="visible", timeout=TIMEOUTS.NORMAL)
            await confirm_btn.click()
            # 点击确定后直接返回成功,不再检测图片数量变化(检测不可靠)
            logger.debug("{} 上传请求已提交", slot_hint or "SKU图片")
            return True
        except Exception as exc:
            logger.error("确认上传网络图片失败: {}", exc)
            return False

    async def _click_first_available(
        self,
        page: Page,
        selectors: Sequence[str],
        description: str,
        *,
        timeout: int = TIMEOUTS.NORMAL,
    ) -> bool:
        """使用并行竞速策略点击首个可见的选择器."""
        locator = await try_selectors_race(
            page,
            list(selectors),
            timeout_ms=timeout,
            context_name=description,
        )
        if locator is None:
            logger.warning("未能定位 {}", description)
            return False
        try:
            await locator.click()
            return True
        except Exception as exc:
            logger.warning("点击 {} 失败: {}", description, exc)
            return False

    async def _fill_first_available(
        self,
        page: Page,
        selectors: Sequence[str],
        text: str,
        *,
        timeout: int = TIMEOUTS.NORMAL,
    ) -> bool:
        """使用并行竞速策略在首个可见输入框中填入文本."""
        locator = await try_selectors_race(
            page,
            list(selectors),
            timeout_ms=timeout,
            context_name="输入框",
        )
        if locator is None:
            logger.warning("未找到可填写的输入框")
            return False
        try:
            await locator.fill("")
            await locator.type(text, delay=30)
            return True
        except Exception as exc:
            logger.warning("填写输入框失败: {}", exc)
            return False

    async def _locate_product_images_pane(self, page: Page) -> Locator | None:
        pane_label = page.locator("div.scroll-menu-pane__label:has-text('产品图片')").first
        try:
            await pane_label.wait_for(state="visible", timeout=TIMEOUTS.NORMAL)
        except Exception:
            return None
        return pane_label.locator("xpath=..")
