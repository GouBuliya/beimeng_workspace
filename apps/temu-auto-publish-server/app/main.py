"""
@PURPOSE: FastAPI 应用入口，认证服务器主程序
@OUTLINE:
  - create_app(): FastAPI 应用工厂
  - lifespan(): 应用生命周期管理 (含优雅关闭)
  - init_admin_user(): 初始化管理员用户
  - active_requests_tracker: 中间件追踪活跃请求数
@GOTCHAS:
  - 应用启动时会自动创建数据库表
  - 如果没有管理员用户，会自动创建默认管理员
  - 支持优雅关闭，等待活跃请求完成 (最多 30 秒)
@DEPENDENCIES:
  - 内部: app.core.*, app.auth.router, app.users.router
  - 外部: fastapi, uvicorn
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import select

from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.core.database import async_session_maker, close_db, init_db
from app.core.health import health_checker
from app.core.redis_client import close_redis
from app.core.restart_guard import restart_guard
from app.core.security import get_password_hash
from app.models.user import User
from app.users.router import router as users_router

settings = get_settings()

# 全局状态
shutdown_event = asyncio.Event()
active_requests = 0


async def init_admin_user() -> None:
    """初始化管理员用户.

    如果数据库中没有管理员用户，则创建默认管理员。
    """
    async with async_session_maker() as session:
        # 检查是否已有管理员
        stmt = select(User).where(User.is_superuser == True)  # noqa: E712
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if not admin:
            # 创建默认管理员
            admin_user = User(
                username=settings.init_admin_username,
                hashed_password=get_password_hash(settings.init_admin_password),
                is_active=True,
                is_superuser=True,
            )
            session.add(admin_user)
            await session.commit()
            logger.info(
                f"已创建默认管理员: username={settings.init_admin_username}, "
                f"password={settings.init_admin_password}"
            )
        else:
            logger.info(f"已存在管理员用户: {admin.username}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期管理 (增强版).

    启动时:
      1. 记录重启时间
      2. 检测重启循环
      3. 初始化数据库和默认管理员

    关闭时:
      1. 停止接受新请求
      2. 等待活跃请求完成 (最多 30 秒)
      3. 清理数据库和 Redis 连接
    """
    global active_requests

    logger.info("正在启动认证服务器...")

    # 1. 记录启动时间
    await restart_guard.record_startup()

    # 2. 检测重启循环
    if not await restart_guard.check_restart_loop():
        logger.critical("检测到重启循环! 请检查服务配置和日志")
        # 注意: 这里不会阻止启动,只是记录告警

    # 3. 初始化数据库表
    await init_db()
    logger.info("数据库初始化完成")

    # 4. 初始化管理员用户
    await init_admin_user()

    logger.info("认证服务器启动成功")

    yield

    # ==================== 优雅关闭流程 ====================
    logger.info("开始优雅关闭流程...")

    # 1. 等待活跃请求完成 (最多 30 秒)
    shutdown_timeout = 30
    for i in range(shutdown_timeout):
        if active_requests == 0:
            logger.info("所有活跃请求已完成")
            break
        if i == 0:
            logger.info(f"等待 {active_requests} 个活跃请求完成...")
        elif i % 5 == 0:
            logger.info(f"仍有 {active_requests} 个活跃请求... ({i}/{shutdown_timeout}s)")
        await asyncio.sleep(1)
    else:
        logger.warning(f"优雅关闭超时: 仍有 {active_requests} 个请求未完成")

    # 2. 清理资源
    logger.info("清理数据库连接...")
    await close_db()

    logger.info("清理 Redis 连接...")
    await close_redis()

    logger.info("认证服务器已完全关闭")


def create_app() -> FastAPI:
    """创建 FastAPI 应用.

    Returns:
        FastAPI: 应用实例
    """
    app = FastAPI(
        title="Temu Auto Publish Auth Server",
        description="Temu 自动发布系统认证服务器",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 活跃请求追踪中间件
    @app.middleware("http")
    async def track_active_requests(request: Request, call_next):
        """追踪活跃请求数量，用于优雅关闭."""
        global active_requests

        active_requests += 1
        try:
            response = await call_next(request)
            return response
        finally:
            active_requests -= 1

    # CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 生产环境应该限制
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    app.include_router(auth_router)
    app.include_router(users_router)

    # ==================== 健康检查端点 ====================

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """轻量级健康检查端点 (Liveness Probe).

        仅检查进程是否存活，不检查依赖服务。
        用于 Docker/K8s 的 liveness probe。

        Returns:
            dict: 固定返回 {"status": "ok"}
        """
        return {"status": "ok", "service": "auth-server"}

    @app.get("/health/readiness")
    async def readiness_check():
        """深度健康检查端点 (Readiness Probe).

        检查所有关键依赖服务（数据库、Redis）的连接状态。
        用于 Docker/K8s 的 readiness probe 和负载均衡器。

        Returns:
            HealthStatus: 包含所有依赖检查结果的综合健康状态

        HTTP Status Codes:
            200: 所有依赖服务正常 (healthy)
            503: 任一依赖服务异常 (unhealthy)
        """
        from fastapi import status
        from fastapi.responses import JSONResponse

        health_status = await health_checker.check_overall()

        if health_status.status == "healthy":
            return health_status
        else:
            # 返回 503 Service Unavailable
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health_status.model_dump(),
            )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.auth_server_host,
        port=settings.auth_server_port,
        reload=settings.debug,
    )
