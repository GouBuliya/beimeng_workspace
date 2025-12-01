"""
@PURPOSE: 应用配置管理,使用 Pydantic Settings 加载环境变量
@OUTLINE:
  - class Settings: 应用配置类,从环境变量或 .env 文件加载
  - get_settings(): 获取配置单例
@DEPENDENCIES:
  - 外部: pydantic_settings, functools
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 数据库配置
    postgres_user: str = "temu_auth"
    postgres_password: str = "temu_auth_password"
    postgres_db: str = "temu_auth_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        """构建 PostgreSQL 连接 URL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        """同步数据库连接 URL(用于 Alembic)."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis 配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str | None = None
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        """构建 Redis 连接 URL."""
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # JWT 配置
    jwt_secret_key: str = "your-super-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 7

    # 服务配置
    # 生产环境建议使用 "127.0.0.1" 或具体 IP 地址
    # 开发环境可以使用 "0.0.0.0" 监听所有接口
    auth_server_host: str = "127.0.0.1"  # nosec B104 - 默认只监听本地
    auth_server_port: int = 8001
    debug: bool = False

    # 初始管理员配置
    init_admin_username: str = "admin"
    init_admin_password: str = "admin123456"


@lru_cache
def get_settings() -> Settings:
    """获取配置单例."""
    return Settings()
