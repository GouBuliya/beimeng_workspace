"""
@PURPOSE: 提供深度健康检查功能,检测应用及依赖服务的运行状态
@OUTLINE:
  - class HealthStatus: 健康状态模型
  - class CheckResult: 单项检查结果模型
  - class HealthChecker: 健康检查管理器
    - check_database(): 检测 PostgreSQL 连接
    - check_redis(): 检测 Redis 连接
    - check_overall(): 综合健康检查
@DEPENDENCIES:
  - 内部: app.core.database, app.core.redis_client
  - 外部: sqlalchemy, redis, pydantic
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Literal

from loguru import logger
from pydantic import BaseModel
from sqlalchemy import text

from .database import engine
from .redis_client import get_redis


class CheckResult(BaseModel):
    """单项检查结果."""

    status: bool
    latency_ms: float
    message: str | None = None


class HealthStatus(BaseModel):
    """综合健康状态."""

    status: Literal["healthy", "degraded", "unhealthy"]
    checks: dict[str, CheckResult]
    timestamp: datetime


class HealthChecker:
    """健康检查管理器.

    提供对数据库、Redis 等依赖服务的健康检查功能。
    """

    async def check_database(self) -> CheckResult:
        """检测 PostgreSQL 数据库连接.

        执行简单的 SELECT 1 查询来验证数据库连接是否正常。

        Returns:
            CheckResult: 检查结果，包含状态、延迟和消息
        """
        start_time = time.time()
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            latency_ms = (time.time() - start_time) * 1000

            logger.debug(f"数据库健康检查成功: latency={latency_ms:.2f}ms")
            return CheckResult(
                status=True,
                latency_ms=round(latency_ms, 2),
                message="Database connection is healthy",
            )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"数据库健康检查失败: error={e}, latency={latency_ms:.2f}ms")
            return CheckResult(
                status=False,
                latency_ms=round(latency_ms, 2),
                message=f"Database connection failed: {str(e)}",
            )

    async def check_redis(self) -> CheckResult:
        """检测 Redis 连接.

        执行 PING 命令来验证 Redis 连接是否正常。

        Returns:
            CheckResult: 检查结果，包含状态、延迟和消息
        """
        start_time = time.time()
        try:
            redis_client = await get_redis()
            result = await redis_client.ping()
            latency_ms = (time.time() - start_time) * 1000

            if result:
                logger.debug(f"Redis 健康检查成功: latency={latency_ms:.2f}ms")
                return CheckResult(
                    status=True,
                    latency_ms=round(latency_ms, 2),
                    message="Redis connection is healthy",
                )
            else:
                logger.error(f"Redis PING 返回异常: result={result}")
                return CheckResult(
                    status=False,
                    latency_ms=round(latency_ms, 2),
                    message="Redis PING returned unexpected response",
                )
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Redis 健康检查失败: error={e}, latency={latency_ms:.2f}ms")
            return CheckResult(
                status=False,
                latency_ms=round(latency_ms, 2),
                message=f"Redis connection failed: {str(e)}",
            )

    async def check_overall(self) -> HealthStatus:
        """综合健康检查.

        检查所有依赖服务（数据库、Redis）的健康状态，
        并返回总体健康状态。

        Returns:
            HealthStatus: 综合健康状态，包含所有检查结果

        状态判定规则:
            - healthy: 所有依赖服务正常
            - unhealthy: 任一关键依赖服务异常
        """
        # 并发执行所有检查
        db_check = await self.check_database()
        redis_check = await self.check_redis()

        checks = {
            "database": db_check,
            "redis": redis_check,
        }

        # 判断总体状态
        all_healthy = all(check.status for check in checks.values())

        if all_healthy:
            overall_status = "healthy"
        else:
            # 任一依赖失败都视为 unhealthy
            overall_status = "unhealthy"

        health_status = HealthStatus(
            status=overall_status,
            checks=checks,
            timestamp=datetime.now(timezone.utc),
        )

        if overall_status != "healthy":
            failed_services = [name for name, check in checks.items() if not check.status]
            logger.warning(f"健康检查失败: status={overall_status}, failed={failed_services}")
        else:
            logger.debug(f"健康检查成功: status={overall_status}")

        return health_status


# 创建单例实例
health_checker = HealthChecker()
