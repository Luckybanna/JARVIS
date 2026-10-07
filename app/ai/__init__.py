"""
AI Brain module for JARVIS.
Includes provider abstractions, factory, and concrete implementations.
"""

from app.ai.base import (
    AIProvider,
    AIResponse,
    ChatMessage,
    MessageRole,
    TokenUsage,
)
from app.ai.factory import create_ai_provider
from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.local_provider import LocalProvider

__all__ = [
    "AIProvider",
    "AIResponse",
    "ChatMessage",
    "MessageRole",
    "TokenUsage",
    "create_ai_provider",
    "GeminiProvider",
    "OpenAIProvider",
    "LocalProvider",
]
