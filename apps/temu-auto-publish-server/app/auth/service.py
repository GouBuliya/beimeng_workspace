"""
@PURPOSE: 认证业务逻辑服务
@OUTLINE:
  - class AuthService: 认证服务类
    - register(): 用户注册
    - authenticate(): 用户认证(登录)
    - create_tokens(): 创建访问和刷新令牌
    - refresh_tokens(): 刷新令牌
    - logout(): 用户登出
    - verify_token(): 验证令牌
    - get_user_by_id(): 根据 ID 获取用户
    - get_user_by_username(): 根据用户名获取用户
@DEPENDENCIES:
  - 内部: app.core.security, app.core.redis_client, app.models.user
  - 外部: sqlalchemy, uuid
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis_client import SessionManager, get_session_manager
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.models.user import User

from .schemas import Token, TokenVerifyResponse, UserRegister

settings = get_settings()


class AuthService:
    """认证服务类."""

    def __init__(self, db: AsyncSession, session_manager: SessionManager) -> None:
        """初始化认证服务.

        Args:
            db: 数据库会话
            session_manager: Redis 会话管理器
        """
        self.db = db
        self.session_manager = session_manager

    async def register(self, user_data: UserRegister) -> User:
        """用户注册.

        Args:
            user_data: 用户注册数据

        Returns:
            User: 创建的用户对象

        Raises:
            ValueError: 用户名或邮箱已存在
        """
        # 检查用户名是否已存在
        existing_user = await self.get_user_by_username(user_data.username)
        if existing_user:
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
            is_active=True,
            is_superuser=False,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info(f"用户注册成功: username={user.username}, id={user.id}")
        return user

    async def authenticate(self, username: str, password: str) -> User | None:
        """验证用户凭据.

        Args:
            username: 用户名
            password: 密码

        Returns:
            User | None: 验证通过返回用户对象,否则返回 None
        """
        user = await self.get_user_by_username(username)
        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            logger.warning(f"用户已禁用: username={username}")
            return None

        return user

    async def create_tokens(self, user: User) -> Token:
        """为用户创建访问令牌和刷新令牌.

        这会使该用户之前的所有会话失效(单设备登录限制).

        Args:
            user: 用户对象

        Returns:
            Token: 令牌响应
        """
        user_id = str(user.id)

        # 创建访问令牌
        access_token, access_jti, access_expires = create_access_token(user_id)

        # 创建刷新令牌
        refresh_token, _refresh_jti, _refresh_expires = create_refresh_token(user_id)

        # 在 Redis 中创建会话(会自动清除旧会话)
        await self.session_manager.create_session(
            user_id=user_id,
            jti=access_jti,
            expires_at=access_expires,
            token_type="access",
            extra_data={"username": user.username, "is_superuser": user.is_superuser},
        )

        # 计算过期秒数
        now = datetime.now(UTC)
        expires_in = int((access_expires - now).total_seconds())

        logger.info(f"为用户创建令牌: username={user.username}, expires_in={expires_in}s")

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    async def refresh_tokens(self, refresh_token: str) -> Token | None:
        """使用刷新令牌获取新的访问令牌.

        Args:
            refresh_token: 刷新令牌

        Returns:
            Token | None: 新的令牌,验证失败返回 None
        """
        payload = decode_token(refresh_token)
        if not payload:
            return None

        if payload.token_type != "refresh":
            return None

        user = await self.get_user_by_id(payload.sub)
        if not user or not user.is_active:
            return None

        return await self.create_tokens(user)

    async def logout(self, token: str) -> bool:
        """用户登出,使当前令牌失效.

        Args:
            token: 访问令牌

        Returns:
            bool: 是否成功
        """
        payload = decode_token(token)
        if not payload:
            return False

        result = await self.session_manager.invalidate_session(payload.jti)
        if result:
            logger.info(f"用户登出成功: user_id={payload.sub}")
        return result

    async def verify_token(self, token: str) -> TokenVerifyResponse:
        """验证令牌是否有效.

        Args:
            token: 要验证的令牌

        Returns:
            TokenVerifyResponse: 验证结果
        """
        payload = decode_token(token)
        if not payload:
            return TokenVerifyResponse(valid=False, message="令牌无效或已过期")

        # 验证会话是否在 Redis 中有效(单设备检查)
        session = await self.session_manager.validate_session(payload.jti)
        if not session:
            return TokenVerifyResponse(valid=False, message="会话已失效或被新登录替代")

        # 获取用户信息
        user = await self.get_user_by_id(payload.sub)
        if not user:
            return TokenVerifyResponse(valid=False, message="用户不存在")

        if not user.is_active:
            return TokenVerifyResponse(valid=False, message="用户已被禁用")

        return TokenVerifyResponse(
            valid=True,
            user_id=str(user.id),
            username=user.username,
            is_superuser=user.is_superuser,
            message="令牌有效",
            bound_miaoshou_username=user.bound_miaoshou_username,
        )

    async def get_user_by_id(self, user_id: str | uuid.UUID) -> User | None:
        """根据 ID 获取用户.

        Args:
            user_id: 用户 ID

        Returns:
            User | None: 用户对象
        """
        try:
            uid = uuid.UUID(str(user_id))
            stmt = select(User).where(User.id == uid)
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
        except ValueError:
            return None

    async def get_user_by_username(self, username: str) -> User | None:
        """根据用户名获取用户.

        Args:
            username: 用户名

        Returns:
            User | None: 用户对象
        """
        stmt = select(User).where(User.username == username)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def change_password(self, user: User, old_password: str, new_password: str) -> bool:
        """修改用户密码.

        Args:
            user: 用户对象
            old_password: 旧密码
            new_password: 新密码

        Returns:
            bool: 是否成功

        Raises:
            ValueError: 旧密码不正确
        """
        if not verify_password(old_password, user.hashed_password):
            raise ValueError("旧密码不正确")

        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()

        # 使所有会话失效,要求重新登录
        await self.session_manager.invalidate_all_sessions(str(user.id))

        logger.info(f"用户密码已修改: username={user.username}")
        return True


async def get_auth_service(db: AsyncSession) -> AuthService:
    """获取认证服务实例.

    Args:
        db: 数据库会话

    Returns:
        AuthService: 认证服务实例
    """
    session_manager = await get_session_manager()
    return AuthService(db, session_manager)
