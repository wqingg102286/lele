import logging
import os
from .path_tool import get_abs_path
from datetime import datetime

# 日志保存的根目录
LOG_ROOT = get_abs_path("logs")

# 确保日志的目录存在
os.makedirs(LOG_ROOT, exist_ok=True)

# 日志的格式配置
DEFAULT_LOG_FORMAT = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)

def get_logger(
        name: str ="agent",
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG,
        log_file = None
)-> logging.Logger:
    """
    获取日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # 如果日志记录器已经存在处理器，则返回
    if logger.handlers:
        return logger

    # 屏幕控制台Handler
    console_handler = logging.StreamHandler()       # 创建一个 StreamHandler（流处理器），负责把日志显示在 IDE 终端里。
    console_handler.setLevel(console_level)         # 设置日志级别
    console_handler.setFormatter(DEFAULT_LOG_FORMAT)    # 设置日志格式
    logger.addHandler(console_handler)              # 添加处理器

    # 文件Handler
    if log_file is None:
        log_file = os.path.join(LOG_ROOT, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")      # 负责把日志写入文件
    file_handler.setLevel(file_level)
    file_handler.setFormatter(DEFAULT_LOG_FORMAT)

    logger.addHandler(file_handler)

    return logger


# 快捷获取日志记录器
logger = get_logger()

if __name__ == "__main__":
    logger.info("hello world")
    logger.error("error")
    logger.debug("debug")
    logger.warning("warning")
