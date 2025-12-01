"""
@PURPOSE: 认证路由，提供登录、注册、登出、令牌刷新等 API
@OUTLINE:
  - POST /auth/register: 用户注册
  - POST /auth/login: 用户登录
  - POST /auth/logout: 用户登出
  - POST /auth/refresh: 刷新令牌
  - POST /auth/verify: 验证令牌
  - GET /auth/me: 获取当前用户信息
  - PUT /auth/password: 修改密码
@DEPENDENCIES:
  - 内部: app.auth.service, app.auth.deps, app.auth.schemas
  - 外部: fastapi
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User

from .deps import get_current_active_user, oauth2_scheme
from .schemas import (
    MessageResponse,
    PasswordChange,
    Token,
    TokenRefresh,
    TokenVerifyRequest,
    TokenVerifyResponse,
    UserRegister,
    UserResponse,
)
from .service import get_auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """用户注册.

    Args:
        user_data: 用户注册数据
        db: 数据库会话

    Returns:
        User: 创建的用户信息
    """
    auth_service = await get_auth_service(db)
    try:
        user = await auth_service.register(user_data)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """用户登录.

    使用用户名和密码登录，返回访问令牌和刷新令牌。
    新登录会使该用户之前的所有会话失效（单设备限制）。

    Args:
        form_data: OAuth2 表单数据
        db: 数据库会话

    Returns:
        Token: 令牌响应
    """
    auth_service = await get_auth_service(db)
    user = await auth_service.authenticate(form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await auth_service.create_tokens(user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """用户登出.

    Args:
        token: Bearer 令牌
        db: 数据库会话

    Returns:
        MessageResponse: 登出结果
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供令牌",
        )

    auth_service = await get_auth_service(db)
    success = await auth_service.logout(token)

    if success:
        return MessageResponse(message="登出成功", success=True)
    return MessageResponse(message="登出失败，令牌可能已失效", success=False)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    """刷新访问令牌.

    Args:
        token_data: 刷新令牌数据
        db: 数据库会话

    Returns:
        Token: 新的令牌响应
    """
    auth_service = await get_auth_service(db)
    tokens = await auth_service.refresh_tokens(token_data.refresh_token)

    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌无效或已过期",
        )

    return tokens


@router.post("/verify", response_model=TokenVerifyResponse)
async def verify_token(
    token_data: TokenVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenVerifyResponse:
    """验证令牌是否有效.

    此接口供客户端调用，验证令牌的有效性。

    Args:
        token_data: 要验证的令牌
        db: 数据库会话

    Returns:
        TokenVerifyResponse: 验证结果
    """
    auth_service = await get_auth_service(db)
    return await auth_service.verify_token(token_data.token)


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """获取当前用户信息.

    Args:
        current_user: 当前登录用户

    Returns:
        User: 用户信息
    """
    return current_user


@router.put("/password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """修改密码.

    修改密码后，所有会话将失效，需要重新登录。

    Args:
        password_data: 密码修改数据
        current_user: 当前登录用户
        db: 数据库会话

    Returns:
        MessageResponse: 修改结果
    """
    auth_service = await get_auth_service(db)
    try:
        await auth_service.change_password(
            current_user,
            password_data.old_password,
            password_data.new_password,
        )
        return MessageResponse(message="密码修改成功，请重新登录", success=True)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
