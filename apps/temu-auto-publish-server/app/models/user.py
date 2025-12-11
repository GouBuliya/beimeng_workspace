"""
@PURPOSE: 用户数据库模型定义
@OUTLINE:
  - class User: 用户表模型,包含用户名,密码哈希,权限等字段
@DEPENDENCIES:
  - 内部: app.core.database
  - 外部: sqlalchemy, uuid, datetime
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """用户表模型."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # 绑定的妙手账号（用于验证用户使用的账号是否与后台绑定一致）
    bound_miaoshou_username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
        comment="绑定的妙手账号",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, is_superuser={self.is_superuser})>"
