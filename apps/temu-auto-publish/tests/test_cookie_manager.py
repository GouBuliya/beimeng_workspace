"""
@PURPOSE: 测试 CookieManager Cookie管理器
@OUTLINE:
  - TestCookieManager: 测试Cookie管理器主类
  - TestCookieManagerPersistence: 测试持久化功能
  - TestCookieManagerValidation: 测试验证功能
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


class TestCookieManagerPersistence:
    """测试持久化功能"""
    
    @pytest.fixture
    def manager(self, tmp_path):
        cookie_file = tmp_path / "cookies.json"
        return CookieManager(str(cookie_file))
    
    def test_save_cookies(self, manager):
        """测试保存Cookie"""
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
    
    def test_load_cookies(self, manager):
        """测试加载Cookie"""
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
        data = {
            "cookies": "expired_cookie",
            "timestamp": expired_time.isoformat()
        }
        
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
    
    def test_is_valid_missing_timestamp(self, manager):
        """测试缺少时间戳无效"""
        manager.cookie_file.parent.mkdir(parents=True, exist_ok=True)
        with open(manager.cookie_file, "w", encoding="utf-8") as f:
            json.dump({"cookies": "test"}, f)
        
        assert manager.is_valid() is False


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
        data = {
            "cookies": "boundary_cookie",
            "timestamp": just_valid_time.isoformat()
        }
        
        cookie_file.parent.mkdir(parents=True, exist_ok=True)
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        assert manager.is_valid() is True








