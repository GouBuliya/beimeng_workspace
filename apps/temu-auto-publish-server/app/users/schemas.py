"""
@PURPOSE: 用户管理相关的 Pydantic 模型定义
@OUTLINE:
  - class UserCreate: 管理员创建用户请求
  - class UserUpdate: 用户更新请求
  - class UserList: 用户列表响应
  - class UserDetail: 用户详情响应
@DEPENDENCIES:
  - 外部: pydantic, uuid, datetime
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """管理员创建用户请求."""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    email: EmailStr | None = Field(default=None, description="邮箱(可选)")
    is_active: bool = Field(default=True, description="是否激活")
    is_superuser: bool = Field(default=False, description="是否是管理员")


class UserUpdate(BaseModel):
    """用户更新请求."""

    email: EmailStr | None = Field(default=None, description="邮箱")
    is_active: bool | None = Field(default=None, description="是否激活")
    is_superuser: bool | None = Field(default=None, description="是否是管理员")
    password: str | None = Field(default=None, min_length=6, max_length=100, description="新密码")


class UserDetail(BaseModel):
    """用户详情响应."""

    id: uuid.UUID = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    email: str | None = Field(default=None, description="邮箱")
    is_active: bool = Field(..., description="是否激活")
    is_superuser: bool = Field(..., description="是否是管理员")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    is_online: bool = Field(default=False, description="是否在线")

    model_config = {"from_attributes": True}


class UserList(BaseModel):
    """用户列表响应."""

    total: int = Field(..., description="总数")
    items: list[UserDetail] = Field(..., description="用户列表")


class ForceLogoutRequest(BaseModel):
    """强制下线请求."""

    user_id: uuid.UUID = Field(..., description="要下线的用户 ID")
