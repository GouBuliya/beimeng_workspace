"""
@PURPOSE: 日志系统设置 - 配置结构化日志、日志轮转和多级别输出
@OUTLINE:
  - def setup_logger(): 配置全局日志系统
  - def get_logger_with_context(): 获取带上下文的logger
  - def format_detailed(): 详细格式化器
  - def format_json(): JSON格式化器
  - def format_simple(): 简单格式化器
@GOTCHAS:
  - loguru 会自动管理日志轮转
  - 需要在应用启动时调用 setup_logger()
  - JSON 格式适合生产环境日志分析
@TECH_DEBT:
  - TODO: 添加远程日志推送
  - TODO: 添加日志采样（高频日志降采样）
@DEPENDENCIES:
  - 外部: loguru
  - 内部: config.settings
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

from config.settings import settings


# ========== 日志格式化器 ==========

def format_detailed(record: Dict[str, Any]) -> str:
    """详细格式化器（开发环境）.
    
    Args:
        record: 日志记录
        
    Returns:
        格式化后的日志字符串
    """
    # 提取上下文
    extra = record["extra"]
    workflow_id = extra.get("workflow_id", "")
    stage = extra.get("stage", "")
    action = extra.get("action", "")
    
    # 构建上下文字符串
    context_parts = []
    if workflow_id:
        context_parts.append(f"workflow={workflow_id[:8]}")
    if stage:
        context_parts.append(f"stage={stage}")
    if action:
        context_parts.append(f"action={action}")
    
    context_str = f" [{', '.join(context_parts)}]" if context_parts else ""
    
    # 格式化
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan>"
        f"{context_str} - "
        "<level>{message}</level>\n"
        "{exception}"
    )


def format_json(record: Dict[str, Any]) -> str:
    """JSON格式化器（生产环境）.
    
    Args:
        record: 日志记录
        
    Returns:
        JSON格式的日志字符串
    """
    import json
    
    # 构建JSON对象
    log_entry = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "logger": record["name"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
    }
    
    # 添加上下文
    extra = record["extra"]
    if extra:
        log_entry["context"] = {}
        for key in ["workflow_id", "stage", "action", "product_index"]:
            if key in extra:
                log_entry["context"][key] = extra[key]
    
    # 添加异常信息
    if record["exception"]:
        log_entry["exception"] = {
            "type": record["exception"].type.__name__,
            "value": str(record["exception"].value),
        }
    
    return json.dumps(log_entry, ensure_ascii=False) + "\n"


def format_simple(record: Dict[str, Any]) -> str:
    """简单格式化器.
    
    Args:
        record: 日志记录
        
    Returns:
        格式化后的日志字符串
    """
    return (
        "{time:HH:mm:ss} | "
        "{level: <8} | "
        "{message}\n"
    )


# ========== 日志设置 ==========

def setup_logger(
    config: Optional[Any] = None,
    force: bool = False
) -> None:
    """配置全局日志系统.
    
    Args:
        config: 日志配置，默认使用 settings.logging
        force: 是否强制重新配置
        
    Examples:
        >>> from src.utils.logger_setup import setup_logger
        >>> setup_logger()
    """
    if config is None:
        config = settings.logging
    
    # 移除默认处理器
    if force:
        logger.remove()
    
    # 选择格式化器
    if config.format == "json":
        formatter = format_json
    elif config.format == "simple":
        formatter = format_simple
    else:  # detailed
        formatter = format_detailed
    
    # 添加控制台输出
    if "console" in config.output:
        logger.add(
            sys.stderr,
            format=formatter,
            level=config.level,
            colorize=True if config.format != "json" else False,
            backtrace=True,
            diagnose=True,
        )
    
    # 添加文件输出
    if "file" in config.output:
        log_file = settings.get_absolute_path(config.file_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.add(
            str(log_file),
            format=formatter,
            level=config.level,
            rotation=config.rotation,  # 例如: "10 MB"
            retention=config.retention,  # 例如: "7 days"
            compression="zip",  # 压缩旧日志
            backtrace=True,
            diagnose=True,
            encoding="utf-8",
        )
    
    logger.info(f"日志系统已配置: level={config.level}, format={config.format}, output={config.output}")


def get_logger_with_context(**context) -> Any:
    """获取带上下文的logger.
    
    Args:
        **context: 上下文键值对
        
    Returns:
        绑定了上下文的logger
        
    Examples:
        >>> log = get_logger_with_context(
        ...     workflow_id="xxx",
        ...     stage="stage1",
        ...     action="login"
        ... )
        >>> log.info("开始登录")
    """
    return logger.bind(**context)


def log_with_context(
    level: str,
    message: str,
    **context
):
    """记录带上下文的日志.
    
    Args:
        level: 日志级别（debug/info/warning/error）
        message: 日志消息
        **context: 上下文键值对
        
    Examples:
        >>> log_with_context(
        ...     "info",
        ...     "开始处理产品",
        ...     workflow_id="xxx",
        ...     product_index=1
        ... )
    """
    log_func = getattr(logger.bind(**context), level.lower())
    log_func(message)


# ========== 日志装饰器 ==========

def log_function_call(level: str = "debug"):
    """记录函数调用的装饰器.
    
    Args:
        level: 日志级别
        
    Returns:
        装饰器函数
        
    Examples:
        >>> @log_function_call("info")
        ... async def my_function(arg1, arg2):
        ...     pass
    """
    def decorator(func):
        from functools import wraps
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            log_func = getattr(logger, level.lower())
            log_func(f"调用函数: {func.__name__}")
            try:
                result = await func(*args, **kwargs)
                log_func(f"函数完成: {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"函数失败: {func.__name__}, 错误: {e}")
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            log_func = getattr(logger, level.lower())
            log_func(f"调用函数: {func.__name__}")
            try:
                result = func(*args, **kwargs)
                log_func(f"函数完成: {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"函数失败: {func.__name__}, 错误: {e}")
                raise
        
        # 根据函数类型选择包装器
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# ========== 便捷函数 ==========

def log_section(title: str, char: str = "=", width: int = 80):
    """记录分隔行.
    
    Args:
        title: 标题
        char: 分隔字符
        width: 宽度
        
    Examples:
        >>> log_section("开始执行工作流")
        ================================================================================
        开始执行工作流
        ================================================================================
    """
    logger.info(char * width)
    logger.info(title)
    logger.info(char * width)


def log_dict(data: Dict[str, Any], title: Optional[str] = None):
    """记录字典数据.
    
    Args:
        data: 字典数据
        title: 标题（可选）
    """
    if title:
        logger.info(f"{title}:")
    
    for key, value in data.items():
        logger.info(f"  {key}: {value}")


def log_list(items: list, title: Optional[str] = None):
    """记录列表数据.
    
    Args:
        items: 列表数据
        title: 标题（可选）
    """
    if title:
        logger.info(f"{title}:")
    
    for i, item in enumerate(items, 1):
        logger.info(f"  {i}. {item}")


# ========== 初始化 ==========

# 自动配置日志（在模块导入时）
try:
    setup_logger()
except Exception as e:
    # 如果配置失败，使用默认配置
    logger.warning(f"日志配置失败，使用默认配置: {e}")

