"""
@PURPOSE: 认证相关的 FastAPI 依赖注入
@OUTLINE:
  - get_current_user(): 获取当前登录用户
  - get_current_active_user(): 获取当前激活用户
  - get_current_superuser(): 获取当前管理员用户
  - oauth2_scheme: OAuth2 密码模式
@DEPENDENCIES:
  - 内部: app.core.security, app.core.redis_client, app.core.database, app.models.user
  - 外部: fastapi
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import get_session_manager
from app.core.security import decode_token
from app.models.user import User

from .service import AuthService

# OAuth2 密码模式
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """获取当前登录用户.

    Args:
        token: Bearer 令牌
        db: 数据库会话

    Returns:
        User: 当前用户对象

    Raises:
        HTTPException: 未认证或令牌无效
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    # 解码令牌
    payload = decode_token(token)
    if not payload:
        raise credentials_exception

    # 验证会话（单设备检查）
    session_manager = await get_session_manager()
    session = await session_manager.validate_session(payload.jti)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 获取用户
    from .service import get_auth_service

    auth_service = await get_auth_service(db)
    user = await auth_service.get_user_by_id(payload.sub)

    if not user:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """获取当前激活用户.

    Args:
        current_user: 当前用户

    Returns:
        User: 激活的用户对象

    Raises:
        HTTPException: 用户未激活
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="用户已被禁用",
        )
    return current_user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """获取当前管理员用户.

    Args:
        current_user: 当前激活用户

    Returns:
        User: 管理员用户对象

    Raises:
        HTTPException: 非管理员用户
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
