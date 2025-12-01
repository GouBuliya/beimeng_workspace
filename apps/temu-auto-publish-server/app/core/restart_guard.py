"""
@PURPOSE: 防止服务陷入重启循环,记录重启历史并触发告警
@OUTLINE:
  - class RestartGuard: 重启保护器
    - record_startup(): 记录启动时间到 Redis
    - check_restart_loop(): 检测是否陷入重启循环
    - get_restart_count(): 获取指定时间窗口内的重启次数
    - clear_history(): 清除重启历史记录 (运维工具)
@DEPENDENCIES:
  - 内部: app.core.redis_client
  - 外部: redis, loguru
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from loguru import logger

from .redis_client import get_redis


class RestartGuard:
    """重启保护器.

    使用 Redis 记录服务重启历史,检测并告警重启循环.
    """

    # Redis 键
    RESTART_HISTORY_KEY = "restart:history"

    # 配置参数
    RESTART_WINDOW_SECONDS = 300  # 时间窗口:5 分钟
    MAX_RESTARTS = 5  # 最大重启次数

    async def record_startup(self) -> None:
        """记录本次启动时间到 Redis.

        将当前时间戳添加到 Redis 列表中,用于后续检测重启循环.
        """
        try:
            redis_client = await get_redis()
            now = time.time()

            # 添加到列表尾部
            await redis_client.rpush(self.RESTART_HISTORY_KEY, str(now))

            # 保留最近 50 条记录 (避免无限增长)
            await redis_client.ltrim(self.RESTART_HISTORY_KEY, -50, -1)

            logger.info(f"记录启动时间: timestamp={now}")

        except Exception as e:
            # 记录失败不应影响服务启动
            logger.warning(f"记录启动时间失败: error={e}")

    async def check_restart_loop(self) -> bool:
        """检测是否陷入重启循环.

        检查最近 5 分钟内的重启次数,如果超过阈值则返回 False
        并记录告警日志.

        Returns:
            bool: True 表示正常启动,False 表示检测到重启循环
        """
        try:
            count = await self.get_restart_count(self.RESTART_WINDOW_SECONDS)

            if count > self.MAX_RESTARTS:
                # 检测到重启循环
                logger.critical(
                    f"检测到重启循环! "
                    f"最近 {self.RESTART_WINDOW_SECONDS}秒 内重启了 {count} 次 "
                    f"(阈值: {self.MAX_RESTARTS})"
                )
                logger.critical("请检查以下可能的原因:")
                logger.critical("  1. 数据库连接配置错误")
                logger.critical("  2. Redis 连接配置错误")
                logger.critical("  3. 环境变量配置错误")
                logger.critical("  4. 端口被占用")
                logger.critical("  5. 资源不足 (内存/CPU)")
                return False

            elif count >= self.MAX_RESTARTS - 1:
                # 接近阈值,发出警告
                logger.warning(
                    f"重启次数接近阈值: "
                    f"{count}/{self.MAX_RESTARTS} "
                    f"(时间窗口: {self.RESTART_WINDOW_SECONDS}秒)"
                )

            return True

        except Exception as e:
            # 检测失败不应影响服务启动
            logger.warning(f"重启循环检测失败: error={e}")
            return True  # 默认允许启动

    async def get_restart_count(self, window_seconds: int = 300) -> int:
        """获取指定时间窗口内的重启次数.

        Args:
            window_seconds: 时间窗口(秒)

        Returns:
            int: 窗口内的重启次数
        """
        try:
            redis_client = await get_redis()

            # 获取所有重启记录
            history = await redis_client.lrange(self.RESTART_HISTORY_KEY, 0, -1)

            if not history:
                return 0

            # 计算窗口起始时间
            now = time.time()
            window_start = now - window_seconds

            # 统计窗口内的重启次数
            count = 0
            for timestamp_str in history:
                try:
                    timestamp = float(timestamp_str)
                    if timestamp >= window_start:
                        count += 1
                except ValueError:
                    logger.warning(f"无效的时间戳格式: {timestamp_str}")
                    continue

            return count

        except Exception as e:
            logger.error(f"获取重启次数失败: error={e}")
            return 0

    async def get_restart_history(self, limit: int = 10) -> list[dict[str, str]]:
        """获取重启历史记录.

        Args:
            limit: 返回最近 N 条记录

        Returns:
            list: 重启历史列表,每项包含 timestamp 和 formatted_time
        """
        try:
            redis_client = await get_redis()
            history = await redis_client.lrange(self.RESTART_HISTORY_KEY, -limit, -1)

            if not history:
                return []

            result = []
            for timestamp_str in reversed(history):  # 最新的在前
                try:
                    timestamp = float(timestamp_str)
                    dt = datetime.fromtimestamp(timestamp, tz=UTC)
                    result.append(
                        {
                            "timestamp": timestamp_str,
                            "formatted_time": dt.isoformat(),
                        }
                    )
                except ValueError:
                    continue

            return result

        except Exception as e:
            logger.error(f"获取重启历史失败: error={e}")
            return []

    async def clear_history(self) -> bool:
        """清除重启历史记录.

        运维工具方法,用于手动清除重启历史.

        Returns:
            bool: 是否清除成功
        """
        try:
            redis_client = await get_redis()
            await redis_client.delete(self.RESTART_HISTORY_KEY)
            logger.info("已清除重启历史记录")
            return True
        except Exception as e:
            logger.error(f"清除重启历史失败: error={e}")
            return False


# 创建单例实例
restart_guard = RestartGuard()
