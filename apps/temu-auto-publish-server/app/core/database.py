"""
@PURPOSE: 数据库连接管理，提供异步 SQLAlchemy 引擎和会话
@OUTLINE:
  - engine: 异步数据库引擎
  - async_session_maker: 异步会话工厂
  - get_db(): FastAPI 依赖注入获取数据库会话
  - init_db(): 初始化数据库表
@DEPENDENCIES:
  - 内部: app.core.config
  - 外部: sqlalchemy, sqlalchemy.ext.asyncio
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings

settings = get_settings()

# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖注入：获取数据库会话.

    Yields:
        AsyncSession: 数据库会话对象
    """
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库表."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库连接."""
    await engine.dispose()

