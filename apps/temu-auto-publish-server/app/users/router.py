"""
@PURPOSE: 用户管理路由，提供用户 CRUD 和强制下线等管理员功能
@OUTLINE:
  - GET /users: 获取用户列表（管理员）
  - POST /users: 创建用户（管理员）
  - GET /users/{user_id}: 获取用户详情（管理员）
  - PUT /users/{user_id}: 更新用户（管理员）
  - DELETE /users/{user_id}: 删除用户（管理员）
  - POST /users/{user_id}/force-logout: 强制用户下线（管理员）
@DEPENDENCIES:
  - 内部: app.users.service, app.auth.deps
  - 外部: fastapi
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_superuser
from app.auth.schemas import MessageResponse
from app.core.database import get_db
from app.core.redis_client import get_session_manager
from app.models.user import User

from .schemas import UserCreate, UserDetail, UserList, UserUpdate
from .service import get_user_service

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", response_model=UserList)
async def list_users(
    _: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(default=0, ge=0, description="跳过数量"),
    limit: int = Query(default=100, ge=1, le=1000, description="限制数量"),
) -> UserList:
    """获取用户列表（管理员）.

    Args:
        _: 当前管理员用户
        db: 数据库会话
        skip: 跳过数量
        limit: 限制数量

    Returns:
        UserList: 用户列表
    """
    session_manager = await get_session_manager()
    user_service = await get_user_service(db, session_manager)
    users, total = await user_service.list_users(skip=skip, limit=limit)

    # 检查每个用户的在线状态
    items = []
    for user in users:
        is_online = await user_service.check_user_online(user.id)
        user_detail = UserDetail(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            updated_at=user.updated_at,
            is_online=is_online,
        )
        items.append(user_detail)

    return UserList(total=total, items=items)


@router.post("", response_model=UserDetail, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    _: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDetail:
    """创建用户（管理员）.

    Args:
        user_data: 用户创建数据
        _: 当前管理员用户
        db: 数据库会话

    Returns:
        UserDetail: 创建的用户信息
    """
    session_manager = await get_session_manager()
    user_service = await get_user_service(db, session_manager)

    try:
        user = await user_service.create_user(user_data)
        return UserDetail(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            updated_at=user.updated_at,
            is_online=False,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/{user_id}", response_model=UserDetail)
async def get_user(
    user_id: uuid.UUID,
    _: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDetail:
    """获取用户详情（管理员）.

    Args:
        user_id: 用户 ID
        _: 当前管理员用户
        db: 数据库会话

    Returns:
        UserDetail: 用户详情
    """
    session_manager = await get_session_manager()
    user_service = await get_user_service(db, session_manager)

    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    is_online = await user_service.check_user_online(user_id)
    return UserDetail(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
        is_online=is_online,
    )


@router.put("/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDetail:
    """更新用户（管理员）.

    Args:
        user_id: 用户 ID
        user_data: 用户更新数据
        current_user: 当前管理员用户
        db: 数据库会话

    Returns:
        UserDetail: 更新后的用户信息
    """
    # 不能修改自己的管理员权限
    if user_id == current_user.id and user_data.is_superuser is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能取消自己的管理员权限",
        )

    session_manager = await get_session_manager()
    user_service = await get_user_service(db, session_manager)

    try:
        user = await user_service.update_user(user_id, user_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )

        is_online = await user_service.check_user_online(user_id)
        return UserDetail(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at,
            updated_at=user.updated_at,
            is_online=is_online,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """删除用户（管理员）.

    Args:
        user_id: 用户 ID
        current_user: 当前管理员用户
        db: 数据库会话

    Returns:
        MessageResponse: 删除结果
    """
    # 不能删除自己
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不能删除自己",
        )

    session_manager = await get_session_manager()
    user_service = await get_user_service(db, session_manager)

    success = await user_service.delete_user(user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    return MessageResponse(message="用户删除成功", success=True)


@router.post("/{user_id}/force-logout", response_model=MessageResponse)
async def force_logout_user(
    user_id: uuid.UUID,
    _: Annotated[User, Depends(get_current_superuser)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """强制用户下线（管理员）.

    Args:
        user_id: 用户 ID
        _: 当前管理员用户
        db: 数据库会话

    Returns:
        MessageResponse: 操作结果
    """
    session_manager = await get_session_manager()
    user_service = await get_user_service(db, session_manager)

    # 检查用户是否存在
    user = await user_service.get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在",
        )

    success = await user_service.force_logout(user_id)
    if success:
        return MessageResponse(message=f"用户 {user.username} 已被强制下线", success=True)
    return MessageResponse(message=f"用户 {user.username} 当前不在线", success=False)

