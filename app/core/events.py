"""
Decoupled Publish/Subscribe Event Bus for JARVIS.
Enables thread-safe, reactive inter-module communication across UI, voice, AI, and avatar.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
from typing import Any, Callable, Dict, List, Optional
import time

from app.core.logger import get_logger

logger = get_logger("events")


class EventType(str, Enum):
    """System-wide event types."""
    # Lifecycle
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    ERROR_OCCURRED = "system.error"

    # User & Conversation
    USER_INPUT_TEXT = "user.input.text"
    USER_INPUT_VOICE = "user.input.voice"
    JARVIS_THINKING_START = "jarvis.thinking.start"
    JARVIS_THINKING_STOP = "jarvis.thinking.stop"
    JARVIS_RESPONSE_CHUNK = "jarvis.response.chunk"
    JARVIS_RESPONSE_COMPLETE = "jarvis.response.complete"

    # Voice / Audio Pipeline
    MIC_LISTENING_START = "voice.mic.listening.start"
    MIC_LISTENING_STOP = "voice.mic.listening.stop"
    SPEECH_DETECTED = "voice.speech.detected"
    TTS_SPEAKING_START = "voice.tts.speaking.start"
    TTS_SPEAKING_STOP = "voice.tts.speaking.stop"
    TTS_INTERRUPTED = "voice.tts.interrupted"

    # Emotion Engine
    EMOTION_STATE_CHANGED = "emotion.state.changed"
    USER_EMOTION_DETECTED = "emotion.user.detected"

    # Proactive Engine
    PROACTIVE_TRIGGER_EVALUATED = "proactive.trigger.evaluated"
    PROACTIVE_MESSAGE_PROPOSED = "proactive.message.proposed"

    # PC Control Tools
    TOOL_EXECUTION_START = "tools.execution.start"
    TOOL_CONFIRMATION_REQUIRED = "tools.confirmation.required"
    TOOL_EXECUTION_COMPLETE = "tools.execution.complete"

    # Tasks & Reminders
    TASK_CREATED = "tasks.created"
    REMINDER_DUE = "tasks.reminder.due"

    # UI & Avatar
    AVATAR_STATE_CHANGED = "avatar.state.changed"


@dataclass
class Event:
    """Standardized event packet."""
    event_type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "core"
    timestamp: float = field(default_factory=time.time)

    @property
    def iso_time(self) -> str:
        return datetime.fromtimestamp(self.timestamp).isoformat()


EventHandler = Callable[[Event], None]


class EventBus:
    """Thread-safe Pub/Sub event distribution bus."""

    def __init__(self):
        self._lock = threading.RLock()
        self._subscribers: Dict[EventType, List[EventHandler]] = {}
        self._global_subscribers: List[EventHandler] = []

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Subscribe a callable to a specific event type."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
                logger.debug(f"Subscribed {handler} to {event_type.value}")

    def subscribe_all(self, handler: EventHandler) -> None:
        """Subscribe a callable to ALL events (useful for loggers, telemetry)."""
        with self._lock:
            if handler not in self._global_subscribers:
                self._global_subscribers.append(handler)

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Remove a subscriber from a specific event type."""
        with self._lock:
            if event_type in self._subscribers and handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    def unsubscribe_all(self, handler: EventHandler) -> None:
        """Remove a global subscriber."""
        with self._lock:
            if handler in self._global_subscribers:
                self._global_subscribers.remove(handler)

    def publish(self, event: Event) -> None:
        """Dispatches an event synchronously to all registered handlers."""
        handlers_to_call: List[EventHandler] = []

        with self._lock:
            # Type-specific handlers
            if event.event_type in self._subscribers:
                handlers_to_call.extend(list(self._subscribers[event.event_type]))
            # Global handlers
            handlers_to_call.extend(list(self._global_subscribers))

        for handler in handlers_to_call:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Error in event handler {handler} for {event.event_type.value}: {e}",
                    exc_info=True,
                )

    def clear(self) -> None:
        """Clear all subscribers (mostly for test isolation)."""
        with self._lock:
            self._subscribers.clear()
            self._global_subscribers.clear()


_bus_instance: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Singleton getter for the global EventBus."""
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = EventBus()
    return _bus_instance
