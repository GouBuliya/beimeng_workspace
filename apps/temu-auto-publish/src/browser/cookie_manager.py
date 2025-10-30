"""
@PURPOSE: Cookie管理器，负责Temu登录Cookie的保存、加载和验证
@OUTLINE:
  - class CookieManager: Cookie管理器主类
  - def save(): 保存Cookie到文件
  - def load(): 从文件加载Cookie
  - def is_valid(): 检查Cookie是否有效
  - def clear(): 清除Cookie
@DEPENDENCIES:
  - 标准库: json, datetime, pathlib
@RELATED: browser_manager.py, login_controller.py
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger


class CookieManager:
    """Cookie 管理器.

    管理 Temu 登录 Cookie，避免频繁登录。

    Attributes:
        cookie_file: Cookie 文件路径
        max_age: Cookie 最大有效期

    Examples:
        >>> manager = CookieManager()
        >>> manager.is_valid()
        False
    """

    def __init__(self, cookie_file: str = "data/temp/temu_cookies.json", max_age_hours: int = 24):
        """初始化管理器.

        Args:
            cookie_file: Cookie 文件路径
            max_age_hours: Cookie 最大有效期（小时）
        """
        self.cookie_file = Path(cookie_file)
        self.max_age = timedelta(hours=max_age_hours)

    def is_valid(self) -> bool:
        """检查 Cookie 是否有效.

        Returns:
            True 如果 Cookie 存在且未过期

        Examples:
            >>> manager = CookieManager()
            >>> if manager.is_valid():
            ...     print("Cookie 有效")
        """
        if not self.cookie_file.exists():
            logger.info("Cookie 文件不存在")
            return False

        try:
            with open(self.cookie_file, encoding="utf-8") as f:
                data = json.load(f)

            # 检查时间戳
            saved_time = datetime.fromisoformat(data["timestamp"])
            age = datetime.now() - saved_time

            if age > self.max_age:
                logger.info(f"Cookie 已过期（{age.total_seconds() / 3600:.1f} 小时）")
                return False

            logger.success(f"Cookie 有效（已保存 {age.total_seconds() / 3600:.1f} 小时）")
            return True

        except Exception as e:
            logger.error(f"读取 Cookie 失败: {e}")
            return False

    def save(self, cookies: str) -> None:
        """保存 Cookie.

        Args:
            cookies: Cookie 字符串

        Examples:
            >>> manager = CookieManager()
            >>> manager.save("session=abc123")
        """
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)

        data = {"cookies": cookies, "timestamp": datetime.now().isoformat()}

        with open(self.cookie_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Cookie 已保存到: {self.cookie_file}")

    def load(self) -> str | None:
        """加载 Cookie.

        Returns:
            Cookie 字符串，如果不存在或无效则返回 None

        Examples:
            >>> manager = CookieManager()
            >>> cookies = manager.load()
        """
        if not self.is_valid():
            return None

        with open(self.cookie_file, encoding="utf-8") as f:
            data = json.load(f)

        return data.get("cookies")

    def clear(self) -> None:
        """清除 Cookie 文件.

        Examples:
            >>> manager = CookieManager()
            >>> manager.clear()
        """
        if self.cookie_file.exists():
            self.cookie_file.unlink()
            logger.info("Cookie 已清除")


# 测试代码
if __name__ == "__main__":
    manager = CookieManager()

    if manager.is_valid():
        print("✓ Cookie 有效，可以跳过登录")
    else:
        print("✗ Cookie 无效，需要重新登录")
