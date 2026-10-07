"""
Unit tests for JARVIS structured logging and security filter.
"""

import logging
from pathlib import Path
import pytest

from app.core.config import get_settings
from app.core.logger import get_logger, setup_logger, SensitiveFilter


def test_logger_creation():
    logger = get_logger("test_module")
    assert logger is not None
    assert logger.name == "jarvis.test_module"


def test_sensitive_filter_masks_keys(monkeypatch):
    settings = get_settings()
    secret_key = "AIzaSySecretTestingKey123456"
    settings.gemini_api_key = secret_key

    record = logging.LogRecord(
        name="jarvis.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg=f"Calling API with key: {secret_key}",
        args=(),
        exc_info=None,
    )

    filt = SensitiveFilter()
    filt.filter(record)

    assert secret_key not in record.msg
    assert "AIz...456" in record.msg
