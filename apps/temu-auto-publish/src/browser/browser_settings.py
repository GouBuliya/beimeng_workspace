"""
@PURPOSE: 统一 Playwright 浏览器配置与路径解析, 确保源码/打包环境下配置一致并可校验版本
@OUTLINE:
  - detect_base_dir(): 识别应用运行根目录(兼容 PyInstaller 打包)
  - class BrowserSettings: 从 .env 读取浏览器配置, 解析路径并设置运行时环境变量
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def detect_base_dir() -> Path:
    """识别应用根目录, 兼容源码运行与 PyInstaller 打包场景.

    Returns:
        应用根目录路径.

    Examples:
        >>> detect_base_dir().exists()
        True
    """

    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


class BrowserSettings(BaseSettings):
    """浏览器配置, 统一 Playwright 路径、版本预期与运行参数.

    Attributes:
        browser_name: 浏览器类型.
        expected_playwright_version: 预期 Playwright 包版本.
        expected_browser_version: 预期浏览器可执行版本, 为空则跳过校验.
        browsers_path: 浏览器安装缓存目录.
        storage_state_path: Storage State 文件路径.
        downloads_dir: 下载目录.
        user_data_dir: 用户数据目录.
        launch_args: 追加的浏览器启动参数.
        locale: 语言区域.
        timezone_id: 时区.
        headless: 是否强制无头模式, None 表示遵循 JSON 配置.
    """

    model_config = SettingsConfigDict(
        env_prefix="BROWSER_",
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    browser_name: str = Field(default="chromium", description="浏览器类型: chromium/firefox/webkit")
    expected_playwright_version: str = Field(
        default="1.49.0",
        description="期望的 Playwright 包版本, 不一致时拒绝启动以保证一致性",
    )
    expected_browser_version: str | None = Field(
        default=None,
        description="期望的浏览器可执行版本, 为空则仅记录实际版本",
    )
    browsers_path: str = Field(
        default=".playwright-browsers",
        description="PLAYWRIGHT_BROWSERS_PATH, 统一浏览器安装缓存目录",
    )
    storage_state_path: str = Field(
        default="data/browser/storage_state.json",
        description="Storage State 文件路径, 存在则在启动时加载",
    )
    downloads_dir: str = Field(
        default="data/downloads",
        description="下载文件目录, 便于团队共享一致的落盘位置",
    )
    user_data_dir: str = Field(
        default="data/browser/user_data",
        description="用户数据目录, 预留给持久化上下文使用",
    )
    launch_args: list[str] = Field(
        default_factory=list,
        description="附加的浏览器启动参数",
    )
    locale: str = Field(default="zh-CN", description="语言区域")
    timezone_id: str = Field(default="Asia/Shanghai", description="时区 ID")
    headless: bool | None = Field(
        default=None, description="覆盖无头模式; None 表示沿用 JSON 配置"
    )

    def resolve_path(self, path: str | Path) -> Path:
        """将相对路径解析为绝对路径(相对于应用根目录).

        Args:
            path: 需要解析的路径.

        Returns:
            解析后的绝对路径.

        Examples:
            >>> BrowserSettings().resolve_path("data").is_absolute()
            True
        """

        path_obj = Path(path)
        if path_obj.is_absolute():
            return path_obj
        return detect_base_dir() / path_obj

    def ensure_directories(self) -> None:
        """确保运行所需目录存在.

        Examples:
            >>> settings = BrowserSettings()
            >>> settings.ensure_directories()
        """

        for target in self._directories_to_create():
            target.mkdir(parents=True, exist_ok=True)

    def apply_environment(self) -> None:
        """写入 Playwright 相关环境变量, 确保运行/打包一致.

        Examples:
            >>> settings = BrowserSettings()
            >>> settings.apply_environment()
            >>> "PLAYWRIGHT_BROWSERS_PATH" in os.environ
            True
        """

        browsers_root = self.resolve_path(self.browsers_path)
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers_root))

    def _directories_to_create(self) -> Iterable[Path]:
        """待创建目录列表.

        Returns:
            需要确保存在的目录迭代器.
        """

        return [
            self.resolve_path(self.browsers_path),
            self.resolve_path(self.downloads_dir),
            self.resolve_path(self.user_data_dir),
            self.resolve_path(self.storage_state_path).parent,
        ]
