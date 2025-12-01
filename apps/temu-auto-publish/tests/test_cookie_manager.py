"""
@PURPOSE: 测试 CookieManager Cookie管理器
@OUTLINE:
  - TestCookieManager: 测试Cookie管理器主类
  - TestCookieManagerPersistence: 测试持久化功能
  - TestCookieManagerPlaywrightFormat: 测试Playwright格式支持
  - TestCookieManagerValidation: 测试验证功能
  - TestCookieManagerEdgeCases: 测试边界情况
@DEPENDENCIES:
  - 外部: pytest
  - 内部: src.browser.cookie_manager
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.browser.cookie_manager import CookieManager


class TestCookieManager:
    """测试Cookie管理器主类"""

    @pytest.fixture
    def manager(self, tmp_path):
        """创建临时Cookie管理器"""
        cookie_file = tmp_path / "test_cookies.json"
        return CookieManager(str(cookie_file), max_age_hours=24)

    def test_init_default(self):
        """测试默认初始化"""
        manager = CookieManager()

        assert manager.cookie_file is not None
        assert manager.max_age == timedelta(hours=24)
        # 新版默认路径是 miaoshou_cookies.json
        assert "miaoshou_cookies.json" in str(manager.cookie_file)

    def test_init_custom_path(self, tmp_path):
        """测试自定义路径初始化"""
        cookie_file = tmp_path / "custom_cookies.json"
        manager = CookieManager(str(cookie_file))

        assert manager.cookie_file == cookie_file

    def test_init_custom_max_age(self, tmp_path):
        """测试自定义有效期"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file), max_age_hours=48)

        assert manager.max_age == timedelta(hours=48)

    def test_metadata_file_path(self, tmp_path):
        """测试元数据文件路径"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file))

        assert manager.metadata_file == tmp_path / "cookies.json.meta.json"


class TestCookieManagerPersistence:
    """测试持久化功能"""

    @pytest.fixture
    def manager(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        return CookieManager(str(cookie_file))

    def test_save_cookies_string(self, manager):
        """测试保存Cookie字符串（旧格式）"""
        test_cookies = "session=abc123; token=xyz789"

        manager.save(test_cookies)

        assert manager.cookie_file.exists()

        # 验证文件内容
        with open(manager.cookie_file, encoding="utf-8") as f:
            data = json.load(f)

        assert data["cookies"] == test_cookies
        assert "timestamp" in data

    def test_save_creates_directory(self, tmp_path):
        """测试保存时创建目录"""
        cookie_file = tmp_path / "subdir" / "nested" / "cookies.json"
        manager = CookieManager(str(cookie_file))

        manager.save("test_cookie")

        assert cookie_file.exists()
        assert cookie_file.parent.exists()

    def test_load_cookies_string(self, manager):
        """测试加载Cookie字符串"""
        test_cookies = "session=loaded_cookie"
        manager.save(test_cookies)

        loaded = manager.load()

        assert loaded == test_cookies

    def test_load_nonexistent(self, manager):
        """测试加载不存在的Cookie"""
        loaded = manager.load()

        assert loaded is None

    def test_clear_cookies(self, manager):
        """测试清除Cookie"""
        manager.save("test_cookie")
        assert manager.cookie_file.exists()

        manager.clear()

        assert not manager.cookie_file.exists()

    def test_clear_nonexistent(self, manager):
        """测试清除不存在的Cookie"""
        # 不应该抛出异常
        manager.clear()

        assert not manager.cookie_file.exists()

    def test_clear_removes_metadata(self, manager):
        """测试清除时同时删除元数据文件"""
        # 保存 Playwright 格式会创建元数据文件
        cookies = [{"name": "test", "value": "123"}]
        manager.save_playwright_cookies(cookies)

        assert manager.cookie_file.exists()
        assert manager.metadata_file.exists()

        manager.clear()

        assert not manager.cookie_file.exists()
        assert not manager.metadata_file.exists()


class TestCookieManagerPlaywrightFormat:
    """测试Playwright格式支持"""

    @pytest.fixture
    def manager(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        return CookieManager(str(cookie_file))

    @pytest.fixture
    def sample_playwright_cookies(self):
        """Playwright 格式的示例 Cookie"""
        return [
            {
                "name": "session",
                "value": "abc123",
                "domain": ".example.com",
                "path": "/",
                "expires": 1735689600,
                "httpOnly": True,
                "secure": True,
                "sameSite": "Lax",
            },
            {
                "name": "token",
                "value": "xyz789",
                "domain": "www.example.com",
                "path": "/api",
                "expires": -1,
                "httpOnly": False,
                "secure": True,
                "sameSite": "None",
            },
        ]

    def test_save_playwright_cookies(self, manager, sample_playwright_cookies):
        """测试保存Playwright格式Cookie"""
        manager.save_playwright_cookies(sample_playwright_cookies)

        assert manager.cookie_file.exists()
        assert manager.metadata_file.exists()

        # 验证Cookie文件内容
        with open(manager.cookie_file, encoding="utf-8") as f:
            saved_cookies = json.load(f)

        assert isinstance(saved_cookies, list)
        assert len(saved_cookies) == 2
        assert saved_cookies[0]["name"] == "session"

        # 验证元数据文件
        with open(manager.metadata_file, encoding="utf-8") as f:
            metadata = json.load(f)

        assert "timestamp" in metadata
        assert metadata["format"] == "playwright"

    def test_save_auto_detect_list(self, manager, sample_playwright_cookies):
        """测试save方法自动检测列表格式"""
        manager.save(sample_playwright_cookies)

        # 应该自动调用 save_playwright_cookies
        assert manager.metadata_file.exists()

        with open(manager.cookie_file, encoding="utf-8") as f:
            saved = json.load(f)

        assert isinstance(saved, list)

    def test_load_playwright_cookies(self, manager, sample_playwright_cookies):
        """测试加载Playwright格式Cookie"""
        manager.save_playwright_cookies(sample_playwright_cookies)

        loaded = manager.load_playwright_cookies()

        assert loaded is not None
        assert isinstance(loaded, list)
        assert len(loaded) == 2
        assert loaded[0]["name"] == "session"

    def test_load_returns_list_for_playwright(self, manager, sample_playwright_cookies):
        """测试load方法返回Playwright格式列表"""
        manager.save_playwright_cookies(sample_playwright_cookies)

        loaded = manager.load()

        assert isinstance(loaded, list)
        assert len(loaded) == 2

    def test_load_playwright_from_string_format_returns_none(self, manager):
        """测试从字符串格式加载Playwright Cookie返回None"""
        manager.save("session=abc123")

        loaded = manager.load_playwright_cookies()

        assert loaded is None

    def test_is_valid_with_metadata_file(self, manager, sample_playwright_cookies):
        """测试使用元数据文件验证有效期"""
        manager.save_playwright_cookies(sample_playwright_cookies)

        assert manager.is_valid() is True

    def test_is_valid_expired_metadata(self, tmp_path, sample_playwright_cookies):
        """测试元数据文件过期"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file), max_age_hours=1)

        # 保存Cookie
        manager.save_playwright_cookies(sample_playwright_cookies)

        # 手动修改元数据时间戳为过期
        expired_time = datetime.now() - timedelta(hours=2)
        metadata = {"timestamp": expired_time.isoformat(), "format": "playwright"}
        with open(manager.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f)

        assert manager.is_valid() is False

    def test_update_timestamp(self, manager, sample_playwright_cookies):
        """测试更新时间戳"""
        manager.save_playwright_cookies(sample_playwright_cookies)

        # 记录原始时间戳
        with open(manager.metadata_file, encoding="utf-8") as f:
            original = json.load(f)
        original_ts = datetime.fromisoformat(original["timestamp"])

        # 等待一小段时间后更新
        import time

        time.sleep(0.01)
        manager.update_timestamp()

        # 验证时间戳已更新
        with open(manager.metadata_file, encoding="utf-8") as f:
            updated = json.load(f)
        updated_ts = datetime.fromisoformat(updated["timestamp"])

        assert updated_ts > original_ts

    def test_update_timestamp_nonexistent(self, manager):
        """测试更新不存在的Cookie时间戳"""
        # 不应该抛出异常
        manager.update_timestamp()


class TestCookieManagerValidation:
    """测试验证功能"""

    @pytest.fixture
    def manager(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        return CookieManager(str(cookie_file), max_age_hours=1)

    def test_is_valid_fresh_cookie(self, manager):
        """测试新鲜Cookie有效"""
        manager.save("fresh_cookie")

        assert manager.is_valid() is True

    def test_is_valid_no_cookie(self, manager):
        """测试无Cookie无效"""
        assert manager.is_valid() is False

    def test_is_valid_expired_cookie(self, tmp_path):
        """测试过期Cookie无效"""
        cookie_file = tmp_path / "expired_cookies.json"
        manager = CookieManager(str(cookie_file), max_age_hours=1)

        # 手动创建过期的Cookie文件
        expired_time = datetime.now() - timedelta(hours=2)
        data = {"cookies": "expired_cookie", "timestamp": expired_time.isoformat()}

        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        assert manager.is_valid() is False

    def test_is_valid_corrupted_file(self, manager):
        """测试损坏文件无效"""
        manager.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        with open(manager.cookie_file, "w", encoding="utf-8") as f:
            f.write("not valid json {{{")

        assert manager.is_valid() is False

    def test_is_valid_missing_timestamp_dict(self, manager):
        """测试字典格式缺少时间戳无效"""
        manager.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        with open(manager.cookie_file, "w", encoding="utf-8") as f:
            json.dump({"cookies": "test"}, f)

        assert manager.is_valid() is False

    def test_is_valid_playwright_without_metadata_uses_mtime(self, tmp_path):
        """测试Playwright格式无元数据时使用文件修改时间"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file), max_age_hours=24)

        # 直接写入 Playwright 格式（不通过 CookieManager）
        cookies = [{"name": "test", "value": "123"}]
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f)

        # 应该使用文件修改时间判断有效性
        assert manager.is_valid() is True


class TestCookieManagerEdgeCases:
    """测试边界情况"""

    def test_empty_cookie_string(self, tmp_path):
        """测试空Cookie字符串"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file))

        manager.save("")
        loaded = manager.load()

        assert loaded == ""

    def test_special_characters_in_cookie(self, tmp_path):
        """测试Cookie中的特殊字符"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file))

        special_cookie = 'session="quoted"; path=/; domain=.example.com'
        manager.save(special_cookie)
        loaded = manager.load()

        assert loaded == special_cookie

    def test_unicode_in_cookie(self, tmp_path):
        """测试Cookie中的Unicode字符"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file))

        unicode_cookie = "user=测试用户; token=abc123"
        manager.save(unicode_cookie)
        loaded = manager.load()

        assert loaded == unicode_cookie

    def test_very_long_cookie(self, tmp_path):
        """测试超长Cookie"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file))

        long_cookie = "data=" + "x" * 10000
        manager.save(long_cookie)
        loaded = manager.load()

        assert loaded == long_cookie

    def test_max_age_boundary(self, tmp_path):
        """测试有效期边界"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file), max_age_hours=1)

        # 刚好在有效期内
        just_valid_time = datetime.now() - timedelta(minutes=59)
        data = {"cookies": "boundary_cookie", "timestamp": just_valid_time.isoformat()}

        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        assert manager.is_valid() is True

    def test_empty_playwright_list(self, tmp_path):
        """测试空Playwright Cookie列表"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file))

        manager.save_playwright_cookies([])
        loaded = manager.load_playwright_cookies()

        assert loaded == []

    def test_playwright_cookies_with_unicode(self, tmp_path):
        """测试Playwright Cookie中的Unicode"""
        cookie_file = tmp_path / "cookies.json"
        manager = CookieManager(str(cookie_file))

        cookies = [{"name": "user", "value": "测试用户", "domain": ".example.com"}]
        manager.save_playwright_cookies(cookies)
        loaded = manager.load_playwright_cookies()

        assert loaded[0]["value"] == "测试用户"
