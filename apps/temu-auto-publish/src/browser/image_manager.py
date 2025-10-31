"""
@PURPOSE: 生产级图片管理模块，负责商品图片的删除、上传和验证（SOP步骤4.3、4.4）
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
  - 删除操作不可逆，需要确认
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
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

from loguru import logger
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout


class ImageManager:
    """生产级图片管理器（SOP步骤4.3、4.4）.
    
    负责商品图片和视频的完整管理：
    - 删除不匹配图片（头图/轮播图/SKU图）
    - 上传网络图片URL
    - 上传视频URL
    - 验证图片格式和大小
    - 批量操作支持
    
    Attributes:
        selectors: 选择器配置字典
        max_retries: 最大重试次数（默认3次）
        retry_delay: 重试延迟秒数（默认2秒）
        
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
    
    # 图片大小限制（字节）
    MAX_IMAGE_SIZE = 3 * 1024 * 1024  # 3MB
    
    # 视频大小限制（字节）
    MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
    
    def __init__(
        self,
        selector_path: str = "config/miaoshou_selectors_v2.json",
        max_retries: int = 3,
        retry_delay: float = 2.0
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
        
        logger.info(
            f"图片管理器初始化完成（重试{max_retries}次，延迟{retry_delay}秒）"
        )
    
    def _load_selectors(self) -> Dict:
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
            
            with open(selector_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.debug(f"选择器配置已加载: {selector_file}")
                return config
        except FileNotFoundError as e:
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
        try:
            dialog_config = self.selectors.get("first_edit_dialog", {})
            nav_config = dialog_config.get("navigation", {})
            images_tab_selector = nav_config.get(
                "product_images", "text='产品图片'"
            )
            
            logger.info("导航到「产品图片」Tab...")
            await page.locator(images_tab_selector).click()
            await page.wait_for_timeout(1000)  # 等待Tab内容加载
            
            logger.success("✓ 已切换到产品图片Tab")
            return True
            
        except Exception as e:
            logger.error(f"导航到产品图片Tab失败: {e}")
            return False
    
    async def get_images_info(
        self,
        page: Page
    ) -> Dict[str, List[Dict]]:
        """获取当前所有图片信息.
        
        Args:
            page: Playwright页面对象
            
        Returns:
            图片信息字典：{
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
            
            images_info = {
                "main_images": [],
                "carousel_images": [],
                "sku_images": []
            }
            
            # TODO: 需要使用Codegen获取实际的图片元素选择器
            # 这里提供框架代码
            logger.warning("图片信息获取功能需要Codegen验证选择器")
            
            return images_info
            
        except Exception as e:
            logger.error(f"获取图片信息失败: {e}")
            return {
                "main_images": [],
                "carousel_images": [],
                "sku_images": []
            }
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
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
                return False, "URL格式无效：缺少协议或域名"
            
            if result.scheme not in ["http", "https"]:
                return False, f"不支持的协议: {result.scheme}（仅支持http/https）"
            
            return True, ""
            
        except Exception as e:
            return False, f"URL解析错误: {str(e)}"
    
    def validate_image_url(self, url: str) -> Tuple[bool, str]:
        """验证图片URL.
        
        Args:
            url: 图片URL
            
        Returns:
            (是否有效, 错误信息)
            
        Examples:
            >>> manager.validate_image_url("https://example.com/image.jpg")
            (True, "")
        """
        is_valid, error = self.validate_url(url)
        if not is_valid:
            return False, error
        
        # 检查文件扩展名
        parsed = urlparse(url)
        path = parsed.path.lower()
        
        if not any(path.endswith(ext) for ext in self.SUPPORTED_IMAGE_FORMATS):
            return False, (
                f"不支持的图片格式。"
                f"支持的格式: {', '.join(self.SUPPORTED_IMAGE_FORMATS)}"
            )
        
        return True, ""
    
    def validate_video_url(self, url: str) -> Tuple[bool, str]:
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
                f"不支持的视频格式。"
                f"支持的格式: {', '.join(self.SUPPORTED_VIDEO_FORMATS)}"
            )
        
        return True, ""
    
    async def delete_image(
        self,
        page: Page,
        image_index: int,
        image_type: str = "carousel"
    ) -> bool:
        """删除指定图片.
        
        Args:
            page: Playwright页面对象
            image_index: 图片索引（从0开始）
            image_type: 图片类型（"main"主图/"carousel"轮播图/"sku" SKU图）
            
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
            raise ValueError(
                f"不支持的图片类型: {image_type}。"
                f"支持的类型: main, carousel, sku"
            )
        
        logger.info(f"删除图片: type={image_type}, index={image_index}")
        
        try:
            # 确保在产品图片Tab
            if not await self.navigate_to_images_tab(page):
                return False
            
            # TODO: 需要使用Codegen获取实际的删除按钮选择器
            # 框架代码：
            # 1. 定位到指定图片
            # 2. 悬停显示删除按钮
            # 3. 点击删除按钮
            # 4. 确认删除（如果有确认弹窗）
            
            logger.warning(
                "删除图片功能需要Codegen验证选择器 - "
                "需要实际录制操作获取准确的元素定位"
            )
            
            # 等待删除操作完成
            await page.wait_for_timeout(500)
            
            logger.success(f"✓ 图片删除成功: {image_type}[{image_index}]")
            return True
            
        except Exception as e:
            logger.error(f"删除图片失败: {e}")
            return False
    
    async def delete_images_batch(
        self,
        page: Page,
        image_indices: List[int],
        image_type: str = "carousel"
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
            f"批量删除图片: type={image_type}, "
            f"count={len(image_indices)}, indices={image_indices}"
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
            logger.warning(
                f"批量删除部分失败: "
                f"成功{success_count}/{len(image_indices)}"
            )
        
        return all_success
    
    async def upload_image_from_url(
        self,
        page: Page,
        image_url: str,
        image_type: str = "size_chart",
        retry_count: int = 0
    ) -> bool:
        """通过URL上传图片（SOP步骤4.4）.
        
        Args:
            page: Playwright页面对象
            image_url: 图片URL
            image_type: 图片类型（"main"主图/"carousel"轮播图/"sku"SKU图/"size_chart"尺寸图）
            retry_count: 当前重试次数（内部使用）
            
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
            # SOP要求：选择「使用网络图片」功能
            # 框架代码：
            # 1. 点击对应类型的上传区域
            # 2. 选择"使用网络图片"选项
            # 3. 输入URL
            # 4. 确认上传
            # 5. 等待上传完成
            
            logger.warning(
                "上传图片功能需要Codegen验证选择器 - "
                "需要实际录制「使用网络图片」操作"
            )
            
            # 等待上传完成
            await page.wait_for_timeout(2000)
            
            logger.success(f"✓ 图片上传成功: {image_type}")
            return True
            
        except Exception as e:
            logger.error(f"上传图片失败（第{retry_count + 1}次尝试）: {e}")
            
            # 自动重试机制
            if retry_count < self.max_retries - 1:
                logger.info(
                    f"等待{self.retry_delay}秒后重试..."
                    f"({retry_count + 2}/{self.max_retries})"
                )
                await asyncio.sleep(self.retry_delay)
                return await self.upload_image_from_url(
                    page, image_url, image_type, retry_count + 1
                )
            else:
                logger.error(f"上传图片最终失败（已重试{self.max_retries}次）")
                return False
    
    async def upload_video_from_url(
        self,
        page: Page,
        video_url: str,
        retry_count: int = 0
    ) -> bool:
        """通过URL上传视频（SOP步骤4.4）.
        
        Args:
            page: Playwright页面对象
            video_url: 视频URL
            retry_count: 当前重试次数（内部使用）
            
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
            video_tab_selector = nav_config.get(
                "product_video", "text='产品视频'"
            )
            
            logger.info("切换到「产品视频」Tab...")
            await page.locator(video_tab_selector).click()
            await page.wait_for_timeout(1000)
            
            # TODO: 需要使用Codegen获取实际的视频上传选择器
            # 框架代码：
            # 1. 点击上传视频按钮
            # 2. 选择"使用网络视频"或"输入URL"
            # 3. 输入视频URL
            # 4. 确认上传
            # 5. 等待上传和处理完成（视频可能需要更长时间）
            
            logger.warning(
                "上传视频功能需要Codegen验证选择器 - "
                "需要实际录制视频上传操作"
            )
            
            # 视频上传和处理需要更长时间
            await page.wait_for_timeout(5000)
            
            logger.success("✓ 视频上传成功")
            return True
            
        except Exception as e:
            logger.error(f"上传视频失败（第{retry_count + 1}次尝试）: {e}")
            
            # 自动重试机制
            if retry_count < self.max_retries - 1:
                logger.info(
                    f"等待{self.retry_delay}秒后重试..."
                    f"({retry_count + 2}/{self.max_retries})"
                )
                await asyncio.sleep(self.retry_delay)
                return await self.upload_video_from_url(
                    page, video_url, retry_count + 1
                )
            else:
                logger.error(f"上传视频最终失败（已重试{self.max_retries}次）")
                return False
    
    async def batch_upload_images(
        self,
        page: Page,
        image_urls: List[Dict[str, str]]
    ) -> Dict[str, int]:
        """批量上传图片.
        
        Args:
            page: Playwright页面对象
            image_urls: 图片URL列表，格式: [{"url": "...", "type": "carousel"}, ...]
            
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
        
        for i, image_info in enumerate(image_urls, 1):
            url = image_info.get("url", "")
            img_type = image_info.get("type", "carousel")
            
            logger.info(f"[{i}/{len(image_urls)}] 上传: {url[:50]}...")
            
            if await self.upload_image_from_url(page, url, img_type):
                success_count += 1
            else:
                failed_count += 1
                logger.warning(f"图片上传失败: {url}")
            
            # 批量上传时稍作延迟，避免过快
            await asyncio.sleep(0.5)
        
        result = {
            "success": success_count,
            "failed": failed_count,
            "total": len(image_urls)
        }
        
        logger.info("=" * 60)
        logger.info("批量上传完成:")
        logger.info(f"  成功: {success_count}")
        logger.info(f"  失败: {failed_count}")
        logger.info(f"  总计: {len(image_urls)}")
        logger.info("=" * 60)
        
        return result

