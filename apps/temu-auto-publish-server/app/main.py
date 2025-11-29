"""
@PURPOSE: FastAPI 应用入口，认证服务器主程序
@OUTLINE:
  - create_app(): FastAPI 应用工厂
  - lifespan(): 应用生命周期管理
  - init_admin_user(): 初始化管理员用户
@GOTCHAS:
  - 应用启动时会自动创建数据库表
  - 如果没有管理员用户，会自动创建默认管理员
@DEPENDENCIES:
  - 内部: app.core.*, app.auth.router, app.users.router
  - 外部: fastapi, uvicorn
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import select

from app.auth.router import router as auth_router
from app.core.config import get_settings
from app.core.database import async_session_maker, close_db, init_db
from app.core.redis_client import close_redis
from app.core.security import get_password_hash
from app.models.user import User
from app.users.router import router as users_router

settings = get_settings()


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
    """应用生命周期管理.

    启动时初始化数据库和默认管理员，
    关闭时清理数据库和 Redis 连接。
    """
    logger.info("正在启动认证服务器...")

    # 初始化数据库表
    await init_db()
    logger.info("数据库初始化完成")

    # 初始化管理员用户
    await init_admin_user()

    yield

    # 关闭连接
    await close_db()
    await close_redis()
    logger.info("认证服务器已关闭")


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

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """健康检查端点."""
        return {"status": "ok", "service": "auth-server"}

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

