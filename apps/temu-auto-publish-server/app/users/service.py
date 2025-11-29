"""
@PURPOSE: 用户管理业务逻辑服务
@OUTLINE:
  - class UserService: 用户管理服务类
    - list_users(): 获取用户列表
    - get_user(): 获取单个用户
    - create_user(): 创建用户
    - update_user(): 更新用户
    - delete_user(): 删除用户
    - force_logout(): 强制用户下线
    - check_user_online(): 检查用户是否在线
@DEPENDENCIES:
  - 内部: app.core.security, app.core.redis_client, app.models.user
  - 外部: sqlalchemy, uuid
"""

from __future__ import annotations

import uuid

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import SessionManager
from app.core.security import get_password_hash
from app.models.user import User

from .schemas import UserCreate, UserUpdate


class UserService:
    """用户管理服务类."""

    def __init__(self, db: AsyncSession, session_manager: SessionManager) -> None:
        """初始化用户管理服务.

        Args:
            db: 数据库会话
            session_manager: Redis 会话管理器
        """
        self.db = db
        self.session_manager = session_manager

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[User], int]:
        """获取用户列表.

        Args:
            skip: 跳过数量
            limit: 限制数量

        Returns:
            tuple[list[User], int]: (用户列表, 总数)
        """
        # 获取总数
        count_stmt = select(func.count()).select_from(User)
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar() or 0

        # 获取列表
        stmt = select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
        result = await self.db.execute(stmt)
        users = list(result.scalars().all())

        return users, total

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        """获取单个用户.

        Args:
            user_id: 用户 ID

        Returns:
            User | None: 用户对象
        """
        stmt = select(User).where(User.id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserCreate) -> User:
        """创建用户.

        Args:
            user_data: 用户创建数据

        Returns:
            User: 创建的用户对象

        Raises:
            ValueError: 用户名或邮箱已存在
        """
        # 检查用户名是否已存在
        stmt = select(User).where(User.username == user_data.username)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError("用户名已存在")

        # 检查邮箱是否已存在
        if user_data.email:
            stmt = select(User).where(User.email == user_data.email)
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                raise ValueError("邮箱已被使用")

        # 创建用户
        hashed_password = get_password_hash(user_data.password)
        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            is_active=user_data.is_active,
            is_superuser=user_data.is_superuser,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"管理员创建用户: username={user.username}, id={user.id}")
        return user

    async def update_user(self, user_id: uuid.UUID, user_data: UserUpdate) -> User | None:
        """更新用户.

        Args:
            user_id: 用户 ID
            user_data: 用户更新数据

        Returns:
            User | None: 更新后的用户对象

        Raises:
            ValueError: 邮箱已被使用
        """
        user = await self.get_user(user_id)
        if not user:
            return None

        # 检查邮箱是否已被其他用户使用
        if user_data.email is not None and user_data.email != user.email:
            stmt = select(User).where(User.email == user_data.email, User.id != user_id)
            result = await self.db.execute(stmt)
            if result.scalar_one_or_none():
                raise ValueError("邮箱已被使用")
            user.email = user_data.email

        if user_data.is_active is not None:
            user.is_active = user_data.is_active
            # 如果禁用用户，强制下线
            if not user_data.is_active:
                await self.force_logout(user_id)

        if user_data.is_superuser is not None:
            user.is_superuser = user_data.is_superuser

        if user_data.password is not None:
            user.hashed_password = get_password_hash(user_data.password)
            # 密码修改后强制下线
            await self.force_logout(user_id)

        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"管理员更新用户: username={user.username}, id={user.id}")
        return user

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        """删除用户.

        Args:
            user_id: 用户 ID

        Returns:
            bool: 是否成功
        """
        user = await self.get_user(user_id)
        if not user:
            return False

        # 先强制下线
        await self.force_logout(user_id)

        # 删除用户
        await self.db.delete(user)
        await self.db.commit()

        logger.info(f"管理员删除用户: username={user.username}, id={user.id}")
        return True

    async def force_logout(self, user_id: uuid.UUID) -> bool:
        """强制用户下线.

        Args:
            user_id: 用户 ID

        Returns:
            bool: 是否成功
        """
        result = await self.session_manager.force_logout(str(user_id))
        if result:
            logger.info(f"管理员强制用户下线: user_id={user_id}")
        return result

    async def check_user_online(self, user_id: uuid.UUID) -> bool:
        """检查用户是否在线.

        Args:
            user_id: 用户 ID

        Returns:
            bool: 是否在线
        """
        session = await self.session_manager.get_active_session(str(user_id))
        return session is not None


async def get_user_service(db: AsyncSession, session_manager: SessionManager) -> UserService:
    """获取用户管理服务实例.

    Args:
        db: 数据库会话
        session_manager: 会话管理器

    Returns:
        UserService: 用户管理服务实例
    """
    return UserService(db, session_manager)

