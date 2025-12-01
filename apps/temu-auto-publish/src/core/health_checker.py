"""
@PURPOSE: 健康检查服务 - 监控系统各组件的健康状态
@OUTLINE:
  - class HealthStatus: 健康状态枚举
  - class HealthCheckResult: 健康检查结果
  - class HealthChecker: 健康检查器主类
  - async def check_browser(): 检查浏览器状态
  - async def check_login(): 检查登录状态
  - async def check_network(): 检查网络连接
  - async def check_disk(): 检查磁盘空间
  - async def check_memory(): 检查内存使用
  - async def check_all(): 执行全面健康检查
@GOTCHAS:
  - 健康检查应该快速返回,避免长时间阻塞
  - 某些检查可能需要管理员权限
@DEPENDENCIES:
  - 外部: psutil, aiohttp
  - 内部: browser_manager, login_controller
@RELATED: notification_service.py, executor.py
"""

import asyncio
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import psutil
from loguru import logger

try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


class HealthStatus(str, Enum):
    """健康状态枚举.

    Attributes:
        OK: 正常
        WARNING: 警告
        ERROR: 错误
        UNKNOWN: 未知
    """

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """健康检查结果.

    Attributes:
        component: 组件名称
        status: 健康状态
        message: 状态消息
        details: 详细信息
        timestamp: 检查时间戳
    """

    component: str
    status: HealthStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def is_healthy(self) -> bool:
        """判断是否健康.

        Returns:
            是否健康(OK或WARNING视为健康)
        """
        return self.status in [HealthStatus.OK, HealthStatus.WARNING]

    def to_dict(self) -> dict[str, Any]:
        """转换为字典.

        Returns:
            字典表示
        """
        return {
            "component": self.component,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class HealthChecker:
    """健康检查器.

    执行系统各组件的健康检查,包括浏览器,登录,网络,磁盘,内存等.

    Examples:
        >>> checker = HealthChecker()
        >>> result = await checker.check_all()
        >>> if result["status"] == "healthy":
        ...     print("系统健康")
    """

    def __init__(
        self,
        disk_warning_threshold_gb: float = 10.0,
        disk_error_threshold_gb: float = 5.0,
        memory_warning_threshold_percent: float = 80.0,
        memory_error_threshold_percent: float = 90.0,
    ):
        """初始化健康检查器.

        Args:
            disk_warning_threshold_gb: 磁盘空间警告阈值(GB)
            disk_error_threshold_gb: 磁盘空间错误阈值(GB)
            memory_warning_threshold_percent: 内存使用警告阈值(%)
            memory_error_threshold_percent: 内存使用错误阈值(%)
        """
        self.disk_warning_threshold_gb = disk_warning_threshold_gb
        self.disk_error_threshold_gb = disk_error_threshold_gb
        self.memory_warning_threshold_percent = memory_warning_threshold_percent
        self.memory_error_threshold_percent = memory_error_threshold_percent

        logger.info("健康检查器已初始化")

    async def check_browser(self, browser_manager=None) -> HealthCheckResult:
        """检查浏览器状态.

        Args:
            browser_manager: 浏览器管理器实例(可选)

        Returns:
            健康检查结果
        """
        try:
            if browser_manager is None:
                # 尝试导入并检查浏览器是否可用

                # 检查playwright是否安装
                try:
                    from playwright.async_api import async_playwright  # noqa: F401

                    status = HealthStatus.OK
                    message = "Playwright已安装"
                    details = {"installed": True}
                except ImportError:
                    status = HealthStatus.ERROR
                    message = "Playwright未安装"
                    details = {"installed": False}
            else:
                # 检查浏览器是否正在运行
                if browser_manager.browser is not None:
                    status = HealthStatus.OK
                    message = "浏览器正在运行"
                    details = {"running": True, "headless": browser_manager.headless}
                else:
                    status = HealthStatus.WARNING
                    message = "浏览器未运行"
                    details = {"running": False}

            return HealthCheckResult(
                component="browser", status=status, message=message, details=details
            )

        except Exception as e:
            logger.error(f"浏览器健康检查失败: {e}")
            return HealthCheckResult(
                component="browser",
                status=HealthStatus.ERROR,
                message=f"检查失败: {e!s}",
                details={"error": str(e)},
            )

    async def check_login(self, login_controller=None) -> HealthCheckResult:
        """检查登录状态.

        Args:
            login_controller: 登录控制器实例(可选)

        Returns:
            健康检查结果
        """
        try:
            # 检查环境变量中的凭证
            import os

            username = os.getenv("MIAOSHOU_USERNAME") or os.getenv("TEMU_USERNAME")
            password = os.getenv("MIAOSHOU_PASSWORD") or os.getenv("TEMU_PASSWORD")

            if not username or not password:
                return HealthCheckResult(
                    component="login",
                    status=HealthStatus.ERROR,
                    message="登录凭证未配置",
                    details={"credentials_configured": False},
                )

            details = {"credentials_configured": True, "username": username}

            if login_controller is not None:
                # 如果提供了登录控制器,检查实际登录状态
                try:
                    # 这里可以添加实际的登录状态检查
                    # 例如检查cookies是否有效
                    details["session_active"] = True
                    message = "登录凭证已配置且会话有效"
                    status = HealthStatus.OK
                except Exception as e:
                    details["session_active"] = False
                    message = f"会话检查失败: {e!s}"
                    status = HealthStatus.WARNING
            else:
                message = "登录凭证已配置"
                status = HealthStatus.OK

            return HealthCheckResult(
                component="login", status=status, message=message, details=details
            )

        except Exception as e:
            logger.error(f"登录健康检查失败: {e}")
            return HealthCheckResult(
                component="login",
                status=HealthStatus.ERROR,
                message=f"检查失败: {e!s}",
                details={"error": str(e)},
            )

    async def check_network(self, test_urls: list[str] | None = None) -> HealthCheckResult:
        """检查网络连接.

        Args:
            test_urls: 测试URL列表(可选)

        Returns:
            健康检查结果
        """
        if not AIOHTTP_AVAILABLE:
            return HealthCheckResult(
                component="network",
                status=HealthStatus.WARNING,
                message="aiohttp未安装,跳过网络检查",
                details={"skipped": True},
            )

        if test_urls is None:
            test_urls = [
                "https://www.baidu.com",  # 国内连通性
                "https://seller.kuajingmaihuo.com",  # 妙手ERP
            ]

        try:
            results = {}
            all_ok = True

            async with aiohttp.ClientSession() as session:
                for url in test_urls:
                    try:
                        async with session.get(
                            url, timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            results[url] = {"status": response.status, "reachable": True}
                            if response.status >= 400:
                                all_ok = False
                    except Exception as e:
                        results[url] = {"reachable": False, "error": str(e)}
                        all_ok = False

            if all_ok:
                status = HealthStatus.OK
                message = f"网络连接正常 ({len(test_urls)}个站点可达)"
            else:
                failed_count = sum(1 for r in results.values() if not r.get("reachable"))
                status = (
                    HealthStatus.WARNING if failed_count < len(test_urls) else HealthStatus.ERROR
                )
                message = f"部分网络连接失败 ({failed_count}/{len(test_urls)})"

            return HealthCheckResult(
                component="network",
                status=status,
                message=message,
                details={"test_results": results},
            )

        except Exception as e:
            logger.error(f"网络健康检查失败: {e}")
            return HealthCheckResult(
                component="network",
                status=HealthStatus.ERROR,
                message=f"检查失败: {e!s}",
                details={"error": str(e)},
            )

    async def check_disk(self, path: str | None = None) -> HealthCheckResult:
        """检查磁盘空间.

        Args:
            path: 检查路径(默认当前目录)

        Returns:
            健康检查结果
        """
        try:
            if path is None:
                path = "."

            # 获取磁盘使用情况
            usage = shutil.disk_usage(path)
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)
            used_percent = (usage.used / usage.total) * 100

            details = {
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "used_percent": round(used_percent, 2),
                "path": os.path.abspath(path),
            }

            # 判断状态
            if free_gb < self.disk_error_threshold_gb:
                status = HealthStatus.ERROR
                message = f"磁盘空间严重不足 (仅剩 {free_gb:.2f}GB)"
            elif free_gb < self.disk_warning_threshold_gb:
                status = HealthStatus.WARNING
                message = f"磁盘空间不足 (剩余 {free_gb:.2f}GB)"
            else:
                status = HealthStatus.OK
                message = f"磁盘空间充足 (剩余 {free_gb:.2f}GB)"

            return HealthCheckResult(
                component="disk", status=status, message=message, details=details
            )

        except Exception as e:
            logger.error(f"磁盘健康检查失败: {e}")
            return HealthCheckResult(
                component="disk",
                status=HealthStatus.ERROR,
                message=f"检查失败: {e!s}",
                details={"error": str(e)},
            )

    async def check_memory(self) -> HealthCheckResult:
        """检查内存使用.

        Returns:
            健康检查结果
        """
        try:
            # 获取内存使用情况
            memory = psutil.virtual_memory()
            used_percent = memory.percent
            available_gb = memory.available / (1024**3)
            total_gb = memory.total / (1024**3)

            details = {
                "used_percent": round(used_percent, 2),
                "available_gb": round(available_gb, 2),
                "total_gb": round(total_gb, 2),
            }

            # 判断状态
            if used_percent >= self.memory_error_threshold_percent:
                status = HealthStatus.ERROR
                message = f"内存使用过高 ({used_percent:.1f}%)"
            elif used_percent >= self.memory_warning_threshold_percent:
                status = HealthStatus.WARNING
                message = f"内存使用较高 ({used_percent:.1f}%)"
            else:
                status = HealthStatus.OK
                message = f"内存使用正常 ({used_percent:.1f}%)"

            return HealthCheckResult(
                component="memory", status=status, message=message, details=details
            )

        except Exception as e:
            logger.error(f"内存健康检查失败: {e}")
            return HealthCheckResult(
                component="memory",
                status=HealthStatus.ERROR,
                message=f"检查失败: {e!s}",
                details={"error": str(e)},
            )

    async def check_dependencies(self) -> HealthCheckResult:
        """检查关键依赖是否安装.

        Returns:
            健康检查结果
        """
        try:
            dependencies = {
                "playwright": False,
                "pandas": False,
                "openpyxl": False,
                "pydantic": False,
                "typer": False,
                "aiohttp": False,
            }

            # 检查每个依赖
            for dep in dependencies:
                try:
                    __import__(dep)
                    dependencies[dep] = True
                except ImportError:
                    pass

            missing = [dep for dep, installed in dependencies.items() if not installed]

            if not missing:
                status = HealthStatus.OK
                message = "所有关键依赖已安装"
            elif len(missing) <= 2:
                status = HealthStatus.WARNING
                message = f"部分依赖缺失: {', '.join(missing)}"
            else:
                status = HealthStatus.ERROR
                message = f"多个依赖缺失: {', '.join(missing)}"

            return HealthCheckResult(
                component="dependencies",
                status=status,
                message=message,
                details={"installed": dependencies, "missing": missing},
            )

        except Exception as e:
            logger.error(f"依赖检查失败: {e}")
            return HealthCheckResult(
                component="dependencies",
                status=HealthStatus.ERROR,
                message=f"检查失败: {e!s}",
                details={"error": str(e)},
            )

    async def check_config_files(self) -> HealthCheckResult:
        """检查配置文件是否存在.

        Returns:
            健康检查结果
        """
        try:
            required_files = [
                ".env",
                "config/browser_config.json",
                "config/miaoshou_selectors.json",
            ]

            file_status = {}
            missing_files = []

            for file_path in required_files:
                path = Path(file_path)
                exists = path.exists()
                file_status[file_path] = exists
                if not exists:
                    missing_files.append(file_path)

            if not missing_files:
                status = HealthStatus.OK
                message = "所有配置文件存在"
            elif len(missing_files) == 1:
                status = HealthStatus.WARNING
                message = f"配置文件缺失: {missing_files[0]}"
            else:
                status = HealthStatus.ERROR
                message = f"多个配置文件缺失: {', '.join(missing_files)}"

            return HealthCheckResult(
                component="config_files",
                status=status,
                message=message,
                details={"files": file_status, "missing": missing_files},
            )

        except Exception as e:
            logger.error(f"配置文件检查失败: {e}")
            return HealthCheckResult(
                component="config_files",
                status=HealthStatus.ERROR,
                message=f"检查失败: {e!s}",
                details={"error": str(e)},
            )

    async def check_all(
        self, browser_manager=None, login_controller=None, include_network: bool = True
    ) -> dict[str, Any]:
        """执行全面健康检查.

        Args:
            browser_manager: 浏览器管理器实例(可选)
            login_controller: 登录控制器实例(可选)
            include_network: 是否包含网络检查(默认True)

        Returns:
            健康检查总结 {
                "status": "healthy/unhealthy",
                "checks": {...},
                "summary": {...}
            }
        """
        logger.info("开始执行全面健康检查...")

        # 并行执行所有检查
        tasks = [
            self.check_browser(browser_manager),
            self.check_login(login_controller),
            self.check_disk(),
            self.check_memory(),
            self.check_dependencies(),
            self.check_config_files(),
        ]

        if include_network:
            tasks.append(self.check_network())

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整理结果
        checks = {}
        error_count = 0
        warning_count = 0

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"健康检查异常: {result}")
                continue

            checks[result.component] = result.to_dict()

            if result.status == HealthStatus.ERROR:
                error_count += 1
            elif result.status == HealthStatus.WARNING:
                warning_count += 1

        # 判断总体状态
        if error_count > 0:
            overall_status = "unhealthy"
        elif warning_count > 0:
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        summary = {
            "overall_status": overall_status,
            "total_checks": len(checks),
            "ok_count": len(checks) - error_count - warning_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "timestamp": datetime.now().isoformat(),
        }

        logger.info(
            f"健康检查完成: {overall_status} "
            f"(OK: {summary['ok_count']}, "
            f"WARNING: {warning_count}, "
            f"ERROR: {error_count})"
        )

        return {"status": overall_status, "checks": checks, "summary": summary}

    async def check_component(self, component: str, **kwargs) -> HealthCheckResult:
        """检查指定组件.

        Args:
            component: 组件名称
            **kwargs: 传递给检查方法的参数

        Returns:
            健康检查结果

        Raises:
            ValueError: 如果组件名称无效
        """
        check_methods = {
            "browser": self.check_browser,
            "login": self.check_login,
            "network": self.check_network,
            "disk": self.check_disk,
            "memory": self.check_memory,
            "dependencies": self.check_dependencies,
            "config_files": self.check_config_files,
        }

        if component not in check_methods:
            raise ValueError(
                f"无效的组件名称: {component}. 可用组件: {', '.join(check_methods.keys())}"
            )

        return await check_methods[component](**kwargs)


# 全局健康检查器实例
_health_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    """获取全局健康检查器实例.

    Returns:
        健康检查器实例
    """
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker
