"""
Conversation Manager for JARVIS.
Coordinates conversational turn-taking, history tracking, event publishing, and provider interaction.
"""

from typing import List, Optional
import time

from app.ai.base import AIProvider, AIResponse, ChatMessage, MessageRole
from app.core.config import Settings, get_settings
from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.logger import get_logger

logger = get_logger("conversation")

DEFAULT_SYSTEM_PROMPT = (
    "You are JARVIS, a personal AI assistant on Windows. "
    "You are intelligent, calm, observant, respectful, slightly witty, and confident. "
    "You communicate naturally in Hindi, English, or Hinglish depending on what the user speaks. "
    "Keep answers concise by default, but detailed when requested. "
    "You are intellectually honest: if the user proposes an idea, constructively analyze risks, "
    "assumptions, and practical improvements rather than blindly agreeing."
)


class ConversationManager:
    """Manages conversational session, message history, and AI interactions."""

    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        event_bus: Optional[EventBus] = None,
        system_prompt: Optional[str] = None,
        max_history_turns: int = 20,
    ):
        self.settings: Settings = get_settings()
        self.event_bus: EventBus = event_bus or get_event_bus()
        
        if provider is None:
            from app.ai.factory import create_ai_provider
            self.provider: AIProvider = create_ai_provider(settings=self.settings)
        else:
            self.provider = provider

        self.system_prompt: str = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.max_history_turns: int = max_history_turns
        self.history: List[ChatMessage] = []

        # Telemetry
        self.last_latency_ms: float = 0.0
        self.last_token_usage: dict = {}
        self.last_error: Optional[str] = None

    def set_provider(self, provider: AIProvider) -> None:
        """Switch active AI provider dynamically."""
        self.provider = provider
        logger.info(f"Switched AI provider to '{provider.provider_name}' ({provider.model_name})")

    def add_message(self, role: MessageRole, content: str) -> ChatMessage:
        """Adds a message to the in-memory history window."""
        msg = ChatMessage(role=role, content=content)
        self.history.append(msg)
        # Trim history if exceeding max turns
        if len(self.history) > self.max_history_turns * 2:
            self.history = self.history[-(self.max_history_turns * 2):]
        return msg

    def clear_history(self) -> None:
        """Clears conversation history."""
        self.history.clear()
        logger.info("Conversation history cleared")

    def send_user_message(self, user_text: str) -> AIResponse:
        """Processes a user message, emits lifecycle events, and retrieves AI response."""
        cleaned_text = user_text.strip()
        if not cleaned_text:
            return AIResponse(
                content="",
                model=self.provider.model_name,
                error="Empty input provided",
            )

        # Record user message in history
        self.add_message(MessageRole.USER, cleaned_text)

        # Publish User Input Event
        self.event_bus.publish(
            Event(
                event_type=EventType.USER_INPUT_TEXT,
                data={"text": cleaned_text},
                source="conversation_manager",
            )
        )

        # Publish Thinking Start Event
        self.event_bus.publish(
            Event(
                event_type=EventType.JARVIS_THINKING_START,
                data={"provider": self.provider.provider_name, "model": self.provider.model_name},
                source="conversation_manager",
            )
        )

        # Call AI provider
        start_t = time.perf_counter()
        try:
            response = self.provider.generate(
                messages=self.history,
                system_prompt=self.system_prompt,
                temperature=self.settings.ai_temperature,
                max_tokens=self.settings.ai_max_tokens,
            )
            self.last_latency_ms = response.latency_ms
            self.last_token_usage = {
                "prompt": response.usage.prompt_tokens,
                "completion": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            }
            self.last_error = response.error

            # Add assistant message to history if non-empty and no critical error
            if response.content and not response.error:
                self.add_message(MessageRole.ASSISTANT, response.content)

        except Exception as e:
            latency = (time.perf_counter() - start_t) * 1000.0
            self.last_latency_ms = latency
            self.last_error = str(e)
            logger.error(f"Error during conversation generation: {e}", exc_info=True)
            response = AIResponse(
                content=f"[Error: {str(e)}]",
                model=self.provider.model_name,
                latency_ms=latency,
                error=str(e),
            )
            self.event_bus.publish(
                Event(
                    event_type=EventType.ERROR_OCCURRED,
                    data={"error": str(e), "context": "conversation_generation"},
                    source="conversation_manager",
                )
            )

        finally:
            # Publish Thinking Stop Event
            self.event_bus.publish(
                Event(
                    event_type=EventType.JARVIS_THINKING_STOP,
                    data={"latency_ms": self.last_latency_ms},
                    source="conversation_manager",
                )
            )

        # Publish Response Complete Event
        self.event_bus.publish(
            Event(
                event_type=EventType.JARVIS_RESPONSE_COMPLETE,
                data={
                    "text": response.content,
                    "model": response.model,
                    "latency_ms": response.latency_ms,
                    "tokens": self.last_token_usage,
                    "error": response.error,
                },
                source="conversation_manager",
            )
        )

        return response
