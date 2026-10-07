"""
Unit tests for ConversationManager.
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
from app.core.conversation import ConversationManager
from app.core.events import Event, EventBus, EventType


class StubProvider(AIProvider):
    def __init__(self, should_fail: bool = False):
        super().__init__(model_name="stub-model")
        self.should_fail = should_fail

    @property
    def provider_name(self) -> str:
        return "stub"

    def generate(
        self,
        messages: List[ChatMessage],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AIResponse:
        if self.should_fail:
            raise ConnectionError("Network failure to AI provider")

        last_user_msg = messages[-1].content
        return AIResponse(
            content=f"Processed: {last_user_msg}",
            model="stub-model",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=15, total_tokens=25),
            latency_ms=45.0,
        )

    def stream(self, *args, **kwargs) -> Iterator[str]:
        yield "stream"

    def health_check(self) -> tuple[bool, str]:
        return True, "Healthy"


def test_conversation_manager_turn():
    bus = EventBus()
    events_log = []

    bus.subscribe_all(lambda evt: events_log.append(evt.event_type))

    provider = StubProvider()
    manager = ConversationManager(provider=provider, event_bus=bus)

    resp = manager.send_user_message("Jarvis, what is the plan today?")

    assert resp.content == "Processed: Jarvis, what is the plan today?"
    assert len(manager.history) == 2
    assert manager.history[0].role == MessageRole.USER
    assert manager.history[1].role == MessageRole.ASSISTANT

    # Verify event order
    assert EventType.USER_INPUT_TEXT in events_log
    assert EventType.JARVIS_THINKING_START in events_log
    assert EventType.JARVIS_THINKING_STOP in events_log
    assert EventType.JARVIS_RESPONSE_COMPLETE in events_log


def test_conversation_manager_empty_input():
    manager = ConversationManager(provider=StubProvider())
    resp = manager.send_user_message("   ")
    assert resp.error == "Empty input provided"
    assert len(manager.history) == 0


def test_conversation_manager_provider_failure():
    bus = EventBus()
    errors_received = []
    bus.subscribe(EventType.ERROR_OCCURRED, lambda e: errors_received.append(e))

    failing_provider = StubProvider(should_fail=True)
    manager = ConversationManager(provider=failing_provider, event_bus=bus)

    resp = manager.send_user_message("Hello")
    assert resp.error is not None
    assert "Network failure" in resp.error
    assert len(errors_received) == 1


def test_conversation_manager_history_pruning():
    provider = StubProvider()
    manager = ConversationManager(provider=provider, max_history_turns=2)

    for i in range(5):
        manager.send_user_message(f"Message {i}")

    # Maximum history turns is 2, so maximum items is 4 (2 user + 2 assistant)
    assert len(manager.history) == 4


def test_conversation_manager_clear_history():
    provider = StubProvider()
    manager = ConversationManager(provider=provider)
    manager.send_user_message("Hello")
    assert len(manager.history) == 2

    manager.clear_history()
    assert len(manager.history) == 0
