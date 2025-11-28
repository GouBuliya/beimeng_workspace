"""
@PURPOSE: 首次编辑媒体上传逻辑.
@OUTLINE:
  - class FirstEditMediaMixin: 上传尺寸图与产品视频
"""

from __future__ import annotations

from loguru import logger
from playwright.async_api import Page

from ..first_edit_dialog_codegen import upload_product_video_via_url, upload_size_chart_via_url
from .base import FirstEditBase


class FirstEditMediaMixin(FirstEditBase):
    """封装首次编辑中尺寸图与视频上传能力."""

    async def upload_size_chart(self, page: Page, image_url: str) -> bool:
        """上传尺寸图(SOP 步骤 4.5 补充)."""
        logger.info("SOP 4.5: 上传尺寸图 -> {}...", image_url[:50])

        try:
            success = await upload_size_chart_via_url(page, image_url)
            if success:
                logger.success("尺寸图已上传(复用 codegen 实现)")
            else:
                logger.warning("尺寸图上传失败或被跳过")
            return success
        except Exception as exc:
            logger.error(f"上传尺寸图失败: {exc}")
            return False

    async def upload_product_video(self, page: Page, video_url: str) -> bool:
        """上传产品视频(SOP 步骤 4.5 补充)."""
        logger.info("SOP 4.5: 上传产品视频 -> {}...", video_url[:50])

        try:
            result = await upload_product_video_via_url(page, video_url)
            if result is True:
                logger.success("产品视频已上传(复用 codegen 实现)")
                return True
            if result is None:
                logger.info("检测到已有视频并已处理,跳过上传")
                return True
            logger.warning("产品视频上传失败或被跳过")
            return False
        except Exception as exc:
            logger.error(f"上传产品视频失败: {exc}")
            logger.info("提示:视频上传功能可能需要在实际环境中调试")
            return False

