"""
统一日志配置系统
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from .settings import get_logging_config, LOGS_DIR


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    format_str: Optional[str] = None
) -> logging.Logger:
    """
    设置应用日志系统

    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径
        format_str: 日志格式字符串

    Returns:
        配置好的根Logger
    """
    config = get_logging_config()

    if level is None:
        level = config.level
    if format_str is None:
        format_str = config.format
    if log_file is None:
        log_file = config.file_path

    # 确保日志目录存在
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 创建根logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # 清除现有handlers
    root_logger.handlers.clear()

    # 创建格式化器
    formatter = logging.Formatter(format_str)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # Console只显示INFO及以上
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler (带轮转)
    if config.file:
        file_handler = RotatingFileHandler(
            filename=log_file,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # 防止日志传播到Python根logger
    root_logger.propagate = False

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的Logger

    Args:
        name: Logger名称，通常使用 __name__

    Returns:
        Logger实例
    """
    return logging.getLogger(name)


# 快捷装饰器：用于函数调用日志
def log_execution(logger: Optional[logging.Logger] = None):
    """
    装饰器：记录函数执行时间和参数

    Args:
        logger: 使用的Logger，如果为None则使用函数模块的Logger
    """
    import time
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_logger = logger or logging.getLogger(func.__module__)
            func_name = func.__name__

            start_time = time.time()
            func_logger.debug(f"[{func_name}] 开始执行，参数: args={args}, kwargs={kwargs}")

            try:
                result = func(*args, **kwargs)
                elapsed = (time.time() - start_time) * 1000
                func_logger.debug(f"[{func_name}] 执行成功，耗时: {elapsed:.2f}ms")
                return result
            except Exception as e:
                elapsed = (time.time() - start_time) * 1000
                func_logger.error(f"[{func_name}] 执行失败，耗时: {elapsed:.2f}ms, 错误: {str(e)}", exc_info=True)
                raise

        return wrapper
    return decorator


# 快捷装饰器：用于记录函数调用
def log_call(logger: Optional[logging.Logger] = None):
    """
    装饰器：记录函数调用（简化版）

    Args:
        logger: 使用的Logger，如果为None则使用函数模块的Logger
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_logger = logger or logging.getLogger(func.__module__)
            func_name = func.__name__

            func_logger.info(f"[{func_name}] 被调用")

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                func_logger.error(f"[{func_name}] 执行异常: {str(e)}", exc_info=True)
                raise

        return wrapper
    return decorator
