"""
@PURPOSE: Redis 客户端和会话管理，实现单设备登录限制
@OUTLINE:
  - get_redis(): 获取 Redis 连接
  - class SessionManager: 会话管理器，处理登录会话和设备锁定
    - create_session(): 创建新会话，踢出旧会话
    - validate_session(): 验证会话是否有效
    - invalidate_session(): 使会话失效
    - invalidate_all_sessions(): 使用户所有会话失效
    - get_active_session(): 获取用户当前活跃会话
@GOTCHAS:
  - 新登录会自动使该用户的所有旧会话失效（单设备限制）
  - 会话信息存储在 Redis 中，支持过期自动清理
@DEPENDENCIES:
  - 内部: app.core.config
  - 外部: redis
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis
from loguru import logger

from .config import get_settings

settings = get_settings()

# Redis 连接池
_redis_pool: redis.ConnectionPool | None = None


async def get_redis() -> redis.Redis:
    """获取 Redis 连接.

    Returns:
        redis.Redis: Redis 客户端实例
    """
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return redis.Redis(connection_pool=_redis_pool)


async def close_redis() -> None:
    """关闭 Redis 连接池."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.disconnect()
        _redis_pool = None


class SessionManager:
    """会话管理器，实现单设备登录限制."""

    # Redis 键前缀
    SESSION_PREFIX = "session:"  # session:{jti} -> session_data
    USER_SESSION_PREFIX = "user_session:"  # user_session:{user_id} -> jti

    def __init__(self, redis_client: redis.Redis) -> None:
        """初始化会话管理器.

        Args:
            redis_client: Redis 客户端实例
        """
        self.redis = redis_client

    async def create_session(
        self,
        user_id: str,
        jti: str,
        expires_at: datetime,
        token_type: str = "access",
        extra_data: dict[str, Any] | None = None,
    ) -> bool:
        """创建新会话，同时使该用户的所有旧会话失效.

        Args:
            user_id: 用户 ID
            jti: JWT 令牌唯一 ID
            expires_at: 过期时间
            token_type: 令牌类型 (access/refresh)
            extra_data: 额外数据

        Returns:
            bool: 是否创建成功
        """
        try:
            # 1. 先使该用户的旧会话失效（单设备限制）
            await self.invalidate_all_sessions(user_id)

            # 2. 计算过期秒数
            now = datetime.now(timezone.utc)
            ttl_seconds = int((expires_at - now).total_seconds())
            if ttl_seconds <= 0:
                logger.warning(f"会话过期时间无效: user_id={user_id}, expires_at={expires_at}")
                return False

            # 3. 存储会话数据
            session_key = f"{self.SESSION_PREFIX}{jti}"
            session_data = {
                "user_id": user_id,
                "jti": jti,
                "token_type": token_type,
                "created_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                **(extra_data or {}),
            }
            await self.redis.setex(session_key, ttl_seconds, json.dumps(session_data))

            # 4. 记录用户当前会话（用于单设备查询）
            user_session_key = f"{self.USER_SESSION_PREFIX}{user_id}"
            await self.redis.setex(user_session_key, ttl_seconds, jti)

            logger.info(f"创建会话成功: user_id={user_id}, jti={jti}, ttl={ttl_seconds}s")
            return True

        except Exception as e:
            logger.error(f"创建会话失败: user_id={user_id}, error={e}")
            return False

    async def validate_session(self, jti: str) -> dict[str, Any] | None:
        """验证会话是否有效.

        Args:
            jti: JWT 令牌唯一 ID

        Returns:
            dict | None: 会话数据，无效则返回 None
        """
        try:
            session_key = f"{self.SESSION_PREFIX}{jti}"
            session_data = await self.redis.get(session_key)

            if session_data is None:
                return None

            data = json.loads(session_data)

            # 检查是否是当前用户的活跃会话（单设备验证）
            user_id = data.get("user_id")
            if user_id:
                user_session_key = f"{self.USER_SESSION_PREFIX}{user_id}"
                current_jti = await self.redis.get(user_session_key)
                if current_jti != jti:
                    logger.warning(f"会话已被新登录替代: user_id={user_id}, old_jti={jti}")
                    return None

            return data

        except Exception as e:
            logger.error(f"验证会话失败: jti={jti}, error={e}")
            return None

    async def invalidate_session(self, jti: str) -> bool:
        """使指定会话失效.

        Args:
            jti: JWT 令牌唯一 ID

        Returns:
            bool: 是否成功
        """
        try:
            session_key = f"{self.SESSION_PREFIX}{jti}"

            # 获取会话数据以找到用户 ID
            session_data = await self.redis.get(session_key)
            if session_data:
                data = json.loads(session_data)
                user_id = data.get("user_id")

                # 删除会话
                await self.redis.delete(session_key)

                # 如果这是用户当前会话，也清除用户会话记录
                if user_id:
                    user_session_key = f"{self.USER_SESSION_PREFIX}{user_id}"
                    current_jti = await self.redis.get(user_session_key)
                    if current_jti == jti:
                        await self.redis.delete(user_session_key)

                logger.info(f"会话已失效: jti={jti}")
                return True

            return False

        except Exception as e:
            logger.error(f"使会话失效失败: jti={jti}, error={e}")
            return False

    async def invalidate_all_sessions(self, user_id: str) -> int:
        """使用户所有会话失效.

        Args:
            user_id: 用户 ID

        Returns:
            int: 被清除的会话数量
        """
        try:
            count = 0

            # 清除用户会话记录
            user_session_key = f"{self.USER_SESSION_PREFIX}{user_id}"
            old_jti = await self.redis.get(user_session_key)

            if old_jti:
                # 清除旧会话数据
                session_key = f"{self.SESSION_PREFIX}{old_jti}"
                deleted = await self.redis.delete(session_key)
                count += deleted

            # 清除用户会话索引
            await self.redis.delete(user_session_key)

            if count > 0:
                logger.info(f"已清除用户所有会话: user_id={user_id}, count={count}")

            return count

        except Exception as e:
            logger.error(f"清除用户会话失败: user_id={user_id}, error={e}")
            return 0

    async def get_active_session(self, user_id: str) -> dict[str, Any] | None:
        """获取用户当前活跃会话.

        Args:
            user_id: 用户 ID

        Returns:
            dict | None: 会话数据
        """
        try:
            user_session_key = f"{self.USER_SESSION_PREFIX}{user_id}"
            jti = await self.redis.get(user_session_key)

            if jti is None:
                return None

            return await self.validate_session(jti)

        except Exception as e:
            logger.error(f"获取活跃会话失败: user_id={user_id}, error={e}")
            return None

    async def force_logout(self, user_id: str) -> bool:
        """强制用户下线（管理员功能）.

        Args:
            user_id: 用户 ID

        Returns:
            bool: 是否成功
        """
        count = await self.invalidate_all_sessions(user_id)
        return count > 0


async def get_session_manager() -> SessionManager:
    """获取会话管理器实例.

    Returns:
        SessionManager: 会话管理器
    """
    redis_client = await get_redis()
    return SessionManager(redis_client)

