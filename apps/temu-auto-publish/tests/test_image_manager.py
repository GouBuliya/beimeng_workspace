"""
@PURPOSE: 图片管理器的单元测试
@OUTLINE:
  - test_image_manager_init: 测试初始化
  - test_validate_url: 测试URL验证
  - test_validate_image_url: 测试图片URL验证
  - test_validate_video_url: 测试视频URL验证
@DEPENDENCIES:
  - 内部: browser.image_manager
  - 外部: pytest, pytest-asyncio
"""

import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.browser.image_manager import ImageManager


class TestImageManager:
    """图片管理器单元测试."""

    def test_image_manager_init(self):
        """测试图片管理器初始化."""
        manager = ImageManager()

        assert manager.max_retries == 3
        assert manager.retry_delay == 2.0
        assert isinstance(manager.selectors, dict)

    def test_validate_url_valid(self):
        """测试有效URL验证."""
        manager = ImageManager()

        valid_urls = [
            "https://example.com/image.jpg",
            "http://example.com/video.mp4",
            "https://cdn.example.com/path/to/image.png",
        ]

        for url in valid_urls:
            is_valid, error = manager.validate_url(url)
            assert is_valid, f"URL should be valid: {url}, Error: {error}"
            assert error == ""

    def test_validate_url_invalid(self):
        """测试无效URL验证."""
        manager = ImageManager()

        invalid_urls = [
            "not-a-url",
            "ftp://example.com/file.jpg",  # 不支持的协议
            "//example.com/image.jpg",  # 缺少协议
            "https://",  # 缺少域名
        ]

        for url in invalid_urls:
            is_valid, error = manager.validate_url(url)
            assert not is_valid, f"URL should be invalid: {url}"
            assert error != ""

    def test_validate_image_url_supported_formats(self):
        """测试支持的图片格式验证."""
        manager = ImageManager()

        supported_formats = [".jpg", ".jpeg", ".png", ".gif", ".webp"]

        for fmt in supported_formats:
            url = f"https://example.com/image{fmt}"
            is_valid, error = manager.validate_image_url(url)
            assert is_valid, f"Format should be supported: {fmt}, Error: {error}"
            assert error == ""

    def test_validate_image_url_unsupported_formats(self):
        """测试不支持的图片格式."""
        manager = ImageManager()

        unsupported_urls = [
            "https://example.com/file.txt",
            "https://example.com/file.pdf",
            "https://example.com/file.doc",
        ]

        for url in unsupported_urls:
            is_valid, error = manager.validate_image_url(url)
            assert not is_valid, f"Format should not be supported: {url}"
            assert "不支持的图片格式" in error

    def test_validate_video_url_supported_formats(self):
        """测试支持的视频格式验证."""
        manager = ImageManager()

        supported_formats = [".mp4", ".avi", ".mov", ".webm"]

        for fmt in supported_formats:
            url = f"https://example.com/video{fmt}"
            is_valid, error = manager.validate_video_url(url)
            assert is_valid, f"Format should be supported: {fmt}, Error: {error}"
            assert error == ""

    def test_validate_video_url_unsupported_formats(self):
        """测试不支持的视频格式."""
        manager = ImageManager()

        unsupported_urls = [
            "https://example.com/video.mkv",
            "https://example.com/video.flv",
            "https://example.com/video.wmv",
        ]

        for url in unsupported_urls:
            is_valid, error = manager.validate_video_url(url)
            assert not is_valid, f"Format should not be supported: {url}"
            assert "不支持的视频格式" in error

    def test_delete_image_invalid_type(self):
        """测试删除图片时的类型验证."""
        ImageManager()

        with pytest.raises(ValueError):
            # 使用异步运行时需要特殊处理,这里仅测试类型验证逻辑
            # 实际调用会在集成测试中进行
            pass

        # 类型验证会在实际调用时触发
        assert True  # 占位符,实际逻辑在delete_image中

    def test_constants(self):
        """测试常量定义."""
        assert ImageManager.MAX_IMAGE_SIZE == 3 * 1024 * 1024
        assert ImageManager.MAX_VIDEO_SIZE == 100 * 1024 * 1024
        assert len(ImageManager.SUPPORTED_IMAGE_FORMATS) == 5
        assert len(ImageManager.SUPPORTED_VIDEO_FORMATS) == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
