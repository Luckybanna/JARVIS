"""
Unit tests for AI providers and abstractions.
"""

from typing import Iterator, List, Optional
import pytest

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
from app.core.config import Settings


class MockProvider(AIProvider):
    """Mock provider for deterministic testing."""

    @property
    def provider_name(self) -> str:
        return "mock"

    def generate(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        last_msg = messages[-1].content if messages else ""
        return AIResponse(
            content=f"Echo: {last_msg}",
            model="mock-v1",
            usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            latency_ms=12.5,
        )

    def stream(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        yield "Echo: "
        yield messages[-1].content if messages else ""

    def health_check(self) -> tuple[bool, str]:
        return True, "Mock is healthy"


def test_chat_message_models():
    u_msg = ChatMessage.user("Hello")
    assert u_msg.role == MessageRole.USER
    assert u_msg.content == "Hello"
    assert u_msg.to_dict() == {"role": "user", "content": "Hello"}

    a_msg = ChatMessage.assistant("Greetings")
    assert a_msg.role == MessageRole.ASSISTANT
    assert a_msg.to_dict() == {"role": "assistant", "content": "Greetings"}

    s_msg = ChatMessage.system("Rules")
    assert s_msg.role == MessageRole.SYSTEM
    assert s_msg.to_dict() == {"role": "system", "content": "Rules"}


def test_factory_instantiation():
    settings = Settings()
    settings.gemini_api_key = "dummy-key"
    settings.openai_api_key = "dummy-key"

    prov_gemini = create_ai_provider("gemini", settings=settings)
    assert isinstance(prov_gemini, GeminiProvider)
    assert prov_gemini.provider_name == "gemini"

    prov_openai = create_ai_provider("openai", settings=settings)
    assert isinstance(prov_openai, OpenAIProvider)
    assert prov_openai.provider_name == "openai"

    prov_local = create_ai_provider("local", settings=settings)
    assert isinstance(prov_local, LocalProvider)
    assert prov_local.provider_name == "local"

    # Fallback on unknown
    prov_unknown = create_ai_provider("unknown_prov", settings=settings)
    assert isinstance(prov_unknown, GeminiProvider)


def test_mock_provider_generation_and_stream():
    provider = MockProvider(model_name="mock-v1")
    resp = provider.generate([ChatMessage.user("Test question")])

    assert resp.content == "Echo: Test question"
    assert resp.model == "mock-v1"
    assert resp.usage.total_tokens == 10
    assert resp.latency_ms == 12.5
    assert resp.error is None

    chunks = list(provider.stream([ChatMessage.user("Test question")]))
    assert "".join(chunks) == "Echo: Test question"

    healthy, msg = provider.health_check()
    assert healthy
    assert "Mock is healthy" in msg


def test_gemini_missing_api_key_error_handling():
    provider = GeminiProvider(api_key="", model_name="gemini-2.5-flash")
    resp = provider.generate([ChatMessage.user("Hi")])
    assert resp.error is not None
    assert "GEMINI_API_KEY is missing" in resp.content

    healthy, reason = provider.health_check()
    assert not healthy
    assert "not configured" in reason


def test_openai_missing_api_key_error_handling():
    provider = OpenAIProvider(api_key="", model_name="gpt-4o-mini")
    resp = provider.generate([ChatMessage.user("Hi")])
    assert resp.error is not None
    assert "OPENAI_API_KEY is missing" in resp.content

    healthy, reason = provider.health_check()
    assert not healthy
    assert "not configured" in reason
