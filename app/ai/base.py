"""
Abstract Base Classes and Data Models for AI Providers.
Ensures provider independence across Gemini, OpenAI, and Local models.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, Iterator, List, Optional


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


@dataclass
class ChatMessage:
    role: MessageRole
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role.value if isinstance(self.role, MessageRole) else str(self.role), "content": self.content}

    @classmethod
    def user(cls, text: str) -> "ChatMessage":
        return cls(role=MessageRole.USER, content=text)

    @classmethod
    def assistant(cls, text: str) -> "ChatMessage":
        return cls(role=MessageRole.ASSISTANT, content=text)

    @classmethod
    def system(cls, text: str) -> "ChatMessage":
        return cls(role=MessageRole.SYSTEM, content=text)


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AIResponse:
    content: str
    model: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    latency_ms: float = 0.0
    finish_reason: str = "stop"
    raw_response: Any = None
    error: Optional[str] = None


class AIProvider(ABC):
    """Abstract interface that all AI Brain backends must implement."""

    def __init__(self, model_name: str, timeout: float = 30.0):
        self.model_name = model_name
        self.timeout = timeout

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the provider (e.g. 'gemini', 'openai', 'local')."""
        pass

    @abstractmethod
    def generate(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        """Generates a synchronous response from the model."""
        pass

    @abstractmethod
    def stream(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Iterator[str]:
        """Streams response tokens synchronously."""
        pass

    @abstractmethod
    def health_check(self) -> tuple[bool, str]:
        """Tests connectivity and credentials with the provider."""
        pass
