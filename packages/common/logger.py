"""日志配置模块

提供统一的日志配置和管理功能。

Examples:
    基础使用::

        from packages.common.logger import setup_logger

        logger = setup_logger("my_app")
        logger.info("应用启动")
"""

import sys

from loguru import logger


def setup_logger(
    name: str,
    level: str = "INFO",
    format_string: str | None = None,
) -> logger:
    """配置并返回 logger

    Args:
        name: logger 名称
        level: 日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        format_string: 自定义格式字符串（可选）

    Returns:
        配置好的 loguru logger

    Examples:
        >>> logger = setup_logger("my_app", level="DEBUG")
        >>> logger.info("测试消息")
    """
    # 移除默认 handler
    logger.remove()

    # 默认格式
    if format_string is None:
        format_string = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    # 添加新的 handler
    logger.add(
        sys.stderr,
        format=format_string,
        level=level,
        colorize=True,
    )

    # 绑定名称
    return logger.bind(name=name)


def setup_file_logger(
    name: str,
    log_file: str,
    level: str = "INFO",
    rotation: str = "1 day",
    retention: str = "7 days",
) -> logger:
    """配置文件日志

    Args:
        name: logger 名称
        log_file: 日志文件路径
        level: 日志级别
        rotation: 日志轮转规则
        retention: 日志保留时间

    Returns:
        配置好的 logger

    Examples:
        >>> logger = setup_file_logger("my_app", "logs/app.log")
        >>> logger.info("写入文件")
    """
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        level=level,
        rotation=rotation,
        retention=retention,
        compression="zip",
    )

    return logger.bind(name=name)

