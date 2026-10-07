"""
Unit tests for JARVIS configuration management.
"""

import os
from pathlib import Path
import pytest

from app.core.config import Settings, get_settings


def test_default_config_loads_properly():
    settings = Settings()
    assert settings.assistant_name == "JARVIS"
    assert settings.primary_language in ("hinglish", "en", "hi")
    assert isinstance(settings.supported_languages, list)
    assert settings.ai_provider in ("gemini", "openai", "local")
    assert settings.ai_timeout > 0
    assert settings.ai_temperature >= 0.0


def test_key_masking():
    settings = Settings()
    assert settings.mask_key("") == "[NOT SET]"
    assert settings.mask_key("short") == "***"
    assert settings.mask_key("AIzaSyD-1234567890abcdef") == "AIza...cdef"


def test_validate_provider_config_missing_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    
    settings = Settings()
    settings.gemini_api_key = ""
    settings.openai_api_key = ""

    valid, reason = settings.validate_provider_config("gemini")
    assert not valid
    assert "GEMINI_API_KEY" in reason

    valid, reason = settings.validate_provider_config("openai")
    assert not valid
    assert "OPENAI_API_KEY" in reason

    valid, reason = settings.validate_provider_config("local")
    assert valid

    valid, reason = settings.validate_provider_config("invalid_provider")
    assert not valid
    assert "Unknown AI provider" in reason


def test_validate_provider_config_with_keys():
    settings = Settings()
    settings.gemini_api_key = "test-gemini-key"
    settings.openai_api_key = "test-openai-key"

    valid, _ = settings.validate_provider_config("gemini")
    assert valid

    valid, _ = settings.validate_provider_config("openai")
    assert valid


def test_singleton_get_settings():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2

    s3 = get_settings(reload=True)
    assert s3 is not None
