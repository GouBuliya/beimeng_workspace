"""
@PURPOSE: 资源管理器 - 监控和控制系统资源使用
@OUTLINE:
  - @dataclass ResourceLimits: 资源限制配置
  - @dataclass ResourceStatus: 资源状态
  - class ResourceManager: 资源管理主类
    - def check_memory(): 检查内存使用
    - def check_disk(): 检查磁盘空间
    - async def enforce_limits(): 强制执行资源限制
    - async def cleanup_temp_files(): 清理临时文件
    - def trigger_gc(): 触发垃圾回收
@GOTCHAS:
  - 内存检查依赖 psutil 库
  - GC 不保证立即释放内存
  - 临时文件清理使用文件修改时间判断
@DEPENDENCIES:
  - 外部: psutil, gc
  - 内部: browser_manager
@RELATED: browser_watchdog.py, health_checker.py
"""

from __future__ import annotations

import gc
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

if TYPE_CHECKING:
    from ..browser.browser_manager import BrowserManager


@dataclass
class ResourceLimits:
    """资源限制配置.

    Attributes:
        max_memory_mb: 最大内存限制(MB)，超过此值触发清理
        min_disk_free_gb: 最小磁盘空间(GB)
        max_page_count: 最大页面数
        max_temp_file_age_hours: 临时文件最大保留时间(小时)
        gc_trigger_memory_mb: 触发 GC 的内存阈值(MB)
        enable_auto_gc: 是否启用自动 GC
    """

    max_memory_mb: int = 4096  # 用户确认: 4GB
    min_disk_free_gb: float = 5.0
    max_page_count: int = 3
    max_temp_file_age_hours: int = 24
    gc_trigger_memory_mb: int = 3072  # 3GB 时触发 GC
    enable_auto_gc: bool = True


@dataclass
class ResourceStatus:
    """资源状态.

    Attributes:
        memory_ok: 内存是否在限制内
        disk_ok: 磁盘是否在限制内
        memory_usage_mb: 当前内存使用(MB)
        disk_free_gb: 磁盘可用空间(GB)
        gc_triggered: 是否触发了 GC
        pages_closed: 关闭的页面数
        temp_files_cleaned: 清理的临时文件数
        timestamp: 检查时间
    """

    memory_ok: bool = True
    disk_ok: bool = True
    memory_usage_mb: int = 0
    disk_free_gb: float = 0.0
    gc_triggered: bool = False
    pages_closed: int = 0
    temp_files_cleaned: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ResourceManager:
    """资源管理器.

    功能:
    1. 监控内存和磁盘使用
    2. 自动触发垃圾回收
    3. 清理多余页面和临时文件
    4. 防止资源泄漏

    Examples:
        >>> manager = ResourceManager()
        >>> status = await manager.enforce_limits(browser_manager)
        >>> if not status.memory_ok:
        ...     print(f"内存超限: {status.memory_usage_mb}MB")
    """

    # 默认临时目录
    DEFAULT_TEMP_DIRS = [
        Path("data/temp"),
        Path("data/debug"),
        Path("data/debug/html"),
    ]

    def __init__(
        self,
        limits: ResourceLimits | None = None,
        temp_dirs: list[Path] | None = None,
    ):
        """初始化资源管理器.

        Args:
            limits: 资源限制配置
            temp_dirs: 临时目录列表
        """
        self.limits = limits or ResourceLimits()
        self.temp_dirs = temp_dirs or self.DEFAULT_TEMP_DIRS
        self._last_gc_time: float = 0.0

    def check_memory(self) -> tuple[bool, dict[str, Any]]:
        """检查内存使用情况.

        Returns:
            (是否在限制内, 详细信息)
        """
        if not PSUTIL_AVAILABLE:
            return True, {"error": "psutil not available", "skipped": True}

        try:
            # 获取当前进程内存
            process = psutil.Process()
            process_memory = process.memory_info()
            process_mb = process_memory.rss // (1024 * 1024)

            # 获取系统内存
            system_memory = psutil.virtual_memory()

            within_limit = process_mb < self.limits.max_memory_mb

            return within_limit, {
                "process_memory_mb": process_mb,
                "system_used_percent": system_memory.percent,
                "system_available_gb": round(system_memory.available / (1024**3), 2),
                "limit_mb": self.limits.max_memory_mb,
                "within_limit": within_limit,
            }
        except Exception as e:
            logger.warning(f"检查内存失败: {e}")
            return True, {"error": str(e)}

    def check_disk(self, path: str = ".") -> tuple[bool, dict[str, Any]]:
        """检查磁盘空间.

        Args:
            path: 检查路径

        Returns:
            (是否在限制内, 详细信息)
        """
        try:
            usage = shutil.disk_usage(path)
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            used_percent = (usage.used / usage.total) * 100

            within_limit = free_gb >= self.limits.min_disk_free_gb

            return within_limit, {
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "used_percent": round(used_percent, 2),
                "limit_gb": self.limits.min_disk_free_gb,
                "within_limit": within_limit,
            }
        except Exception as e:
            logger.warning(f"检查磁盘失败: {e}")
            return True, {"error": str(e)}

    def trigger_gc(self, force: bool = False) -> bool:
        """触发垃圾回收.

        Args:
            force: 是否强制执行(忽略冷却时间)

        Returns:
            是否执行了 GC
        """
        if not self.limits.enable_auto_gc and not force:
            return False

        # GC 冷却时间: 60秒
        now = time.time()
        if not force and (now - self._last_gc_time) < 60:
            return False

        try:
            collected = gc.collect()
            self._last_gc_time = now
            logger.info(f"[ResourceManager] GC 已执行，回收 {collected} 个对象")
            return True
        except Exception as e:
            logger.warning(f"GC 执行失败: {e}")
            return False

    async def cleanup_temp_files(self) -> int:
        """清理过期临时文件.

        Returns:
            清理的文件数量
        """
        cutoff = time.time() - (self.limits.max_temp_file_age_hours * 3600)
        cleaned = 0

        for temp_dir in self.temp_dirs:
            if not temp_dir.exists():
                continue

            try:
                for file_path in temp_dir.rglob("*"):
                    if not file_path.is_file():
                        continue

                    try:
                        # 检查文件修改时间
                        if file_path.stat().st_mtime < cutoff:
                            file_path.unlink()
                            cleaned += 1
                    except (OSError, PermissionError):
                        pass
            except Exception as e:
                logger.debug(f"清理目录 {temp_dir} 时出错: {e}")

        if cleaned > 0:
            logger.info(f"[ResourceManager] 已清理 {cleaned} 个过期临时文件")

        return cleaned

    async def close_extra_pages(self, browser_manager: "BrowserManager | None") -> int:
        """关闭多余页面.

        Args:
            browser_manager: 浏览器管理器

        Returns:
            关闭的页面数
        """
        if browser_manager is None:
            return 0

        if not hasattr(browser_manager, "close_extra_pages"):
            return 0

        try:
            return await browser_manager.close_extra_pages(keep_count=self.limits.max_page_count)
        except Exception as e:
            logger.warning(f"关闭多余页面失败: {e}")
            return 0

    async def enforce_limits(
        self,
        browser_manager: "BrowserManager | None" = None,
    ) -> ResourceStatus:
        """强制执行资源限制.

        检查所有资源并执行必要的清理操作.

        Args:
            browser_manager: 浏览器管理器(可选)

        Returns:
            资源状态
        """
        status = ResourceStatus()

        # 1. 检查内存
        mem_ok, mem_info = self.check_memory()
        status.memory_ok = mem_ok
        status.memory_usage_mb = mem_info.get("process_memory_mb", 0)

        if not mem_ok:
            logger.warning(
                f"[ResourceManager] 内存超限: {status.memory_usage_mb}MB "
                f"(限制: {self.limits.max_memory_mb}MB)"
            )

            # 触发 GC
            if self.trigger_gc():
                status.gc_triggered = True

            # 关闭多余页面
            if browser_manager:
                status.pages_closed = await self.close_extra_pages(browser_manager)

            # 再次检查
            mem_ok, mem_info = self.check_memory()
            status.memory_ok = mem_ok
            status.memory_usage_mb = mem_info.get("process_memory_mb", 0)

            if not mem_ok:
                logger.warning(
                    f"[ResourceManager] 内存仍超限: {status.memory_usage_mb}MB，建议重启浏览器"
                )

        # 检查是否应该触发预防性 GC
        elif status.memory_usage_mb > self.limits.gc_trigger_memory_mb:
            if self.trigger_gc():
                status.gc_triggered = True

        # 2. 检查磁盘
        disk_ok, disk_info = self.check_disk()
        status.disk_ok = disk_ok
        status.disk_free_gb = disk_info.get("free_gb", 0.0)

        if not disk_ok:
            logger.warning(
                f"[ResourceManager] 磁盘空间不足: {status.disk_free_gb}GB "
                f"(需要: {self.limits.min_disk_free_gb}GB)"
            )

            # 清理临时文件
            status.temp_files_cleaned = await self.cleanup_temp_files()

            # 再次检查
            disk_ok, disk_info = self.check_disk()
            status.disk_ok = disk_ok
            status.disk_free_gb = disk_info.get("free_gb", 0.0)

        return status

    async def get_status(self) -> dict[str, Any]:
        """获取资源状态摘要.

        Returns:
            状态摘要
        """
        mem_ok, mem_info = self.check_memory()
        disk_ok, disk_info = self.check_disk()

        return {
            "memory": {
                "ok": mem_ok,
                **mem_info,
            },
            "disk": {
                "ok": disk_ok,
                **disk_info,
            },
            "limits": {
                "max_memory_mb": self.limits.max_memory_mb,
                "min_disk_free_gb": self.limits.min_disk_free_gb,
                "max_page_count": self.limits.max_page_count,
            },
            "timestamp": datetime.now().isoformat(),
        }


# 便捷工厂函数
def create_resource_manager(**limits_kwargs) -> ResourceManager:
    """创建资源管理器实例.

    Args:
        **limits_kwargs: 资源限制参数

    Returns:
        ResourceManager 实例
    """
    limits = ResourceLimits(**limits_kwargs)
    return ResourceManager(limits=limits)


# 全局实例
_resource_manager: ResourceManager | None = None


def get_resource_manager() -> ResourceManager:
    """获取全局资源管理器实例.

    Returns:
        ResourceManager 实例
    """
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager


# 导出
__all__ = [
    "ResourceLimits",
    "ResourceManager",
    "ResourceStatus",
    "create_resource_manager",
    "get_resource_manager",
]
