import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from app.config import settings

def setup_logging():
    # Base formatter for logs
    log_format = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s:%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    logger = logging.getLogger("photomind")
    logger.setLevel(settings.LOG_LEVEL)
    logger.handlers.clear()

    # Console Handler
    console_handler = sys.stdout
    stdout_handler = logging.StreamHandler(console_handler)
    stdout_handler.setFormatter(log_format)
    logger.addHandler(stdout_handler)

    # File Handler (only if STORAGE_PATH exists or is writeable)
    log_dir = os.path.join(settings.STORAGE_PATH, "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, "photomind.log")
        
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setFormatter(log_format)
        logger.addHandler(file_handler)
        logger.info(f"Logging initialized. Log file active at: {log_file_path}")
    except Exception as e:
        logger.warning(f"Could not initialize file logging: {e}. Falling back to console logging only.")

    return logger

# Active logger instance
logger = setup_logging()
