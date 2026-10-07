"""
AI Provider Factory for JARVIS.
Instantiates and configures AI Providers dynamically from application settings.
"""

from typing import Optional

from app.ai.base import AIProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.local_provider import LocalProvider
from app.core.config import Settings, get_settings
from app.core.logger import get_logger

logger = get_logger("ai.factory")


def create_ai_provider(
    provider_name: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> AIProvider:
    """Creates and returns an AIProvider instance according to configuration."""
    cfg = settings or get_settings()
    selected_name = (provider_name or cfg.ai_provider).lower().strip()

    logger.info(f"Instantiating AI provider: '{selected_name}'")

    if selected_name == "gemini":
        return GeminiProvider(
            api_key=cfg.gemini_api_key,
            model_name=cfg.gemini_model,
            timeout=cfg.ai_timeout,
        )

    elif selected_name == "openai":
        return OpenAIProvider(
            api_key=cfg.openai_api_key,
            model_name=cfg.openai_model,
            timeout=cfg.ai_timeout,
        )

    elif selected_name == "local":
        return LocalProvider(
            base_url=cfg.local_api_base_url,
            model_name=cfg.local_model,
            timeout=cfg.ai_timeout,
        )

    else:
        logger.error(f"Unrecognized AI provider: '{selected_name}'. Falling back to Gemini.")
        return GeminiProvider(
            api_key=cfg.gemini_api_key,
            model_name=cfg.gemini_model,
            timeout=cfg.ai_timeout,
        )
