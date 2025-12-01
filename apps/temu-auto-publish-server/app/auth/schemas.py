"""
@PURPOSE: 认证相关的 Pydantic 模型定义
@OUTLINE:
  - class UserRegister: 用户注册请求
  - class UserLogin: 用户登录请求
  - class Token: 令牌响应
  - class TokenVerify: 令牌验证响应
  - class UserResponse: 用户信息响应
@DEPENDENCIES:
  - 外部: pydantic, uuid, datetime
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserRegister(BaseModel):
    """用户注册请求."""

    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=100, description="密码")
    email: EmailStr | None = Field(default=None, description="邮箱(可选)")


class UserLogin(BaseModel):
    """用户登录请求."""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class Token(BaseModel):
    """令牌响应."""

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(..., description="访问令牌过期时间(秒)")


class TokenRefresh(BaseModel):
    """令牌刷新请求."""

    refresh_token: str = Field(..., description="刷新令牌")


class TokenVerifyRequest(BaseModel):
    """令牌验证请求."""

    token: str = Field(..., description="要验证的令牌")


class TokenVerifyResponse(BaseModel):
    """令牌验证响应."""

    valid: bool = Field(..., description="令牌是否有效")
    user_id: str | None = Field(default=None, description="用户 ID")
    username: str | None = Field(default=None, description="用户名")
    is_superuser: bool = Field(default=False, description="是否是管理员")
    message: str | None = Field(default=None, description="验证结果消息")


class UserResponse(BaseModel):
    """用户信息响应."""

    id: uuid.UUID = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    email: str | None = Field(default=None, description="邮箱")
    is_active: bool = Field(..., description="是否激活")
    is_superuser: bool = Field(..., description="是否是管理员")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    """密码修改请求."""

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=100, description="新密码")


class MessageResponse(BaseModel):
    """通用消息响应."""

    message: str = Field(..., description="消息内容")
    success: bool = Field(default=True, description="是否成功")
