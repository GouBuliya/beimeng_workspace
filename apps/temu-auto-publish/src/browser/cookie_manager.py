"""
@PURPOSE: Cookie管理器,负责登录Cookie的保存,加载和验证,支持Playwright原生格式
@OUTLINE:
  - class CookieManager: Cookie管理器主类
  - def save(): 保存Cookie到文件(支持字符串和Playwright数组格式)
  - def save_playwright_cookies(): 保存Playwright格式Cookie
  - def load(): 从文件加载Cookie
  - def load_playwright_cookies(): 加载Playwright格式Cookie
  - def is_valid(): 检查Cookie是否有效
  - def clear(): 清除Cookie
  - def update_timestamp(): 更新Cookie时间戳
@DEPENDENCIES:
  - 标准库: json, datetime, pathlib
@RELATED: browser_manager.py, login_controller.py
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger


class CookieManager:
    """Cookie 管理器.

    管理登录 Cookie,支持两种格式:
    1. 简单字符串格式(旧版兼容)
    2. Playwright 原生 JSON 数组格式(推荐)

    Attributes:
        cookie_file: Cookie 文件路径
        max_age: Cookie 最大有效期

    Examples:
        >>> manager = CookieManager()
        >>> manager.is_valid()
        False
    """

    # 元数据文件后缀
    METADATA_SUFFIX = ".meta.json"

    def __init__(
        self, cookie_file: str = "data/temp/miaoshou_cookies.json", max_age_hours: int = 24
    ):
        """初始化管理器.

        Args:
            cookie_file: Cookie 文件路径
            max_age_hours: Cookie 最大有效期(小时)
        """
        self.cookie_file = Path(cookie_file)
        self.max_age = timedelta(hours=max_age_hours)

    @property
    def metadata_file(self) -> Path:
        """获取元数据文件路径."""
        return self.cookie_file.with_suffix(self.cookie_file.suffix + self.METADATA_SUFFIX)

    def is_valid(self) -> bool:
        """检查 Cookie 是否有效.

        支持两种格式的检查:
        1. 旧格式:JSON 文件中包含 timestamp 字段
        2. 新格式:独立的元数据文件存储时间戳

        Returns:
            True 如果 Cookie 存在且未过期

        Examples:
            >>> manager = CookieManager()
            >>> if manager.is_valid():
            ...     print("Cookie 有效")
        """
        if not self.cookie_file.exists():
            logger.info("Cookie 文件不存在: {}", self.cookie_file)
            return False

        try:
            # 首先尝试从元数据文件读取时间戳(新格式)
            if self.metadata_file.exists():
                with open(self.metadata_file, encoding="utf-8") as f:
                    metadata = json.load(f)
                saved_time = datetime.fromisoformat(metadata["timestamp"])
            else:
                # 尝试从 cookie 文件本身读取时间戳(旧格式兼容)
                with open(self.cookie_file, encoding="utf-8") as f:
                    data = json.load(f)

                if "timestamp" in data:
                    saved_time = datetime.fromisoformat(data["timestamp"])
                else:
                    # 如果是 Playwright 格式(数组),使用文件修改时间
                    if isinstance(data, list):
                        mtime = self.cookie_file.stat().st_mtime
                        saved_time = datetime.fromtimestamp(mtime)
                    else:
                        logger.warning("Cookie 文件格式无法识别,缺少时间戳")
                        return False

            age = datetime.now() - saved_time

            if age > self.max_age:
                logger.info(f"Cookie 已过期({age.total_seconds() / 3600:.1f} 小时)")
                return False

            logger.success(f"Cookie 有效(已保存 {age.total_seconds() / 3600:.1f} 小时)")
            return True

        except Exception as e:
            logger.error(f"读取 Cookie 失败: {e}")
            return False

    def save(self, cookies: str | list[dict[str, Any]]) -> None:
        """保存 Cookie.

        自动检测并保存两种格式:
        - 字符串:保存为旧格式(带 timestamp)
        - 列表:保存为 Playwright 格式,时间戳存入元数据文件

        Args:
            cookies: Cookie 字符串或 Playwright 格式的 Cookie 列表

        Examples:
            >>> manager = CookieManager()
            >>> manager.save("session=abc123")  # 旧格式
            >>> manager.save([{"name": "session", "value": "abc"}])  # Playwright 格式
        """
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)

        if isinstance(cookies, list):
            # Playwright 格式:Cookie 数组
            self.save_playwright_cookies(cookies)
        else:
            # 旧格式:字符串
            data = {"cookies": cookies, "timestamp": datetime.now().isoformat()}
            with open(self.cookie_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Cookie(字符串格式)已保存到: {self.cookie_file}")

    def save_playwright_cookies(self, cookies: list[dict[str, Any]]) -> None:
        """保存 Playwright 格式的 Cookie.

        Args:
            cookies: Playwright context.cookies() 返回的 Cookie 列表

        Examples:
            >>> manager = CookieManager()
            >>> cookies = [{"name": "session", "value": "abc", "domain": ".example.com"}]
            >>> manager.save_playwright_cookies(cookies)
        """
        self.cookie_file.parent.mkdir(parents=True, exist_ok=True)

        # 保存 Cookie 数据
        with open(self.cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        # 保存元数据(时间戳)
        self._save_metadata()

        logger.info(f"Cookie(Playwright 格式,{len(cookies)} 条)已保存到: {self.cookie_file}")

    def _save_metadata(self) -> None:
        """保存元数据文件(包含时间戳)."""
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "format": "playwright",
        }
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

    def update_timestamp(self) -> None:
        """更新 Cookie 时间戳(不重新保存 Cookie 数据).

        当 Cookie 验证成功后调用此方法可以延长有效期.

        Examples:
            >>> manager = CookieManager()
            >>> if manager.is_valid():
            ...     manager.update_timestamp()  # 延长有效期
        """
        if not self.cookie_file.exists():
            logger.warning("Cookie 文件不存在,无法更新时间戳")
            return

        self._save_metadata()
        logger.debug("Cookie 时间戳已更新")

    def load(self) -> str | list[dict[str, Any]] | None:
        """加载 Cookie.

        自动检测格式并返回对应类型.

        Returns:
            Cookie 字符串或 Playwright 格式列表,如果不存在或无效则返回 None

        Examples:
            >>> manager = CookieManager()
            >>> cookies = manager.load()
        """
        if not self.is_valid():
            return None

        with open(self.cookie_file, encoding="utf-8") as f:
            data = json.load(f)

        # 如果是列表,直接返回(Playwright 格式)
        if isinstance(data, list):
            return data

        # 旧格式:返回 cookies 字段
        return data.get("cookies")

    def load_playwright_cookies(self) -> list[dict[str, Any]] | None:
        """加载 Playwright 格式的 Cookie.

        Returns:
            Playwright 格式的 Cookie 列表,如果不存在或无效则返回 None

        Examples:
            >>> manager = CookieManager()
            >>> cookies = manager.load_playwright_cookies()
            >>> if cookies:
            ...     await context.add_cookies(cookies)
        """
        if not self.is_valid():
            return None

        try:
            with open(self.cookie_file, encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, list):
                return data

            logger.warning("Cookie 文件不是 Playwright 格式")
            return None

        except Exception as e:
            logger.error(f"加载 Playwright Cookie 失败: {e}")
            return None

    def clear(self) -> None:
        """清除 Cookie 文件和元数据.

        Examples:
            >>> manager = CookieManager()
            >>> manager.clear()
        """
        if self.cookie_file.exists():
            self.cookie_file.unlink()
            logger.info("Cookie 已清除")

        if self.metadata_file.exists():
            self.metadata_file.unlink()
            logger.debug("Cookie 元数据已清除")


# 测试代码
if __name__ == "__main__":
    manager = CookieManager()

    if manager.is_valid():
        print("✓ Cookie 有效,可以跳过登录")
    else:
        print("✗ Cookie 无效,需要重新登录")
