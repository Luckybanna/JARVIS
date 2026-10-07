"""
Structured logging module for JARVIS.
Provides console and rotating file logging with thread-safety and sensitive data protection.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from pathlib import Path
from typing import Optional

from app.core.config import LOGS_DIR, get_settings


class SensitiveFilter(logging.Filter):
    """Filter that obscures potential API keys or tokens in log outputs."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            settings = get_settings()
            keys_to_mask = [
                settings.gemini_api_key,
                settings.openai_api_key,
            ]
            for key in keys_to_mask:
                if key and len(key) > 6 and key in msg:
                    masked = f"{key[:3]}...{key[-3:]}"
                    record.msg = str(record.msg).replace(key, masked)
        except Exception:
            pass
        return True


def setup_logger(
    name: str = "jarvis",
    log_file: Optional[Path] = None,
    level: Optional[str] = None,
) -> logging.Logger:
    """Configures and returns a logger instance with console and rotating file handlers."""
    logger = logging.getLogger(name)

    # If handlers already configured, return existing logger
    if logger.handlers:
        return logger

    settings = get_settings()
    log_level_name = level or settings.log_level
    log_level = getattr(logging, log_level_name, logging.INFO)
    logger.setLevel(log_level)

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s:%(funcName)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sensitive_filter = SensitiveFilter()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    logger.addHandler(console_handler)

    # Rotating File Handler (Max 10MB per file, keep 5 backups)
    target_log_file = log_file or (LOGS_DIR / "jarvis.log")
    try:
        file_handler = RotatingFileHandler(
            filename=str(target_log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not initialize rotating file logger at {target_log_file}: {e}")

    logger.propagate = False
    return logger


def get_logger(name: str = "jarvis") -> logging.Logger:
    """Retrieves a configured logger child or root instance."""
    setup_logger("jarvis")
    return logging.getLogger(name if name.startswith("jarvis") else f"jarvis.{name}")
