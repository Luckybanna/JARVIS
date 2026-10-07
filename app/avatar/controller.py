"""
Avatar Controller for JARVIS.
Synchronizes visual avatar states and audio reactivity with EventBus lifecycle and emotion events.
"""

from dataclasses import asdict
import threading
import time
from typing import Any, Dict, Optional

from app.avatar.state import AvatarState, AvatarTheme, StateVisualConfig
from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.logger import get_logger

logger = get_logger("avatar.controller")


class AvatarController:
    """
    Manages current avatar visual state, emotion mapping, and audio reactivity.
    Listens to system-wide EventBus events to autonomously drive avatar animations.
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._bus = event_bus or get_event_bus()
        self._lock = threading.RLock()
        self._current_state: AvatarState = AvatarState.IDLE
        self._base_state: AvatarState = AvatarState.IDLE
        self._audio_level: float = 0.0  # Normalized 0.0 to 1.0
        self._temporary_state_timer: Optional[threading.Timer] = None
        self._is_subscribed: bool = False

        self._subscribe_events()
        logger.info(f"AvatarController initialized with state={self._current_state.value}")

    @property
    def current_state(self) -> AvatarState:
        with self._lock:
            return self._current_state

    @property
    def visual_config(self) -> StateVisualConfig:
        with self._lock:
            return AvatarTheme.get_config(self._current_state)

    @property
    def audio_level(self) -> float:
        with self._lock:
            return self._audio_level

    def set_audio_level(self, level: float) -> None:
        """Sets the audio reactivity amplitude (clamped to [0.0, 1.0])."""
        with self._lock:
            self._audio_level = max(0.0, min(1.0, float(level)))

    def set_state(self, state: AvatarState, duration: Optional[float] = None) -> None:
        """
        Explicitly sets the avatar state.
        If duration is provided, reverts to base_state after duration seconds.
        """
        with self._lock:
            if self._temporary_state_timer is not None:
                self._temporary_state_timer.cancel()
                self._temporary_state_timer = None

            old_state = self._current_state
            self._current_state = state

            if duration is not None and duration > 0:
                self._temporary_state_timer = threading.Timer(duration, self._revert_temporary_state)
                self._temporary_state_timer.daemon = True
                self._temporary_state_timer.start()
            else:
                self._base_state = state

        if old_state != state:
            logger.debug(f"Avatar state changed: {old_state.value} -> {state.value}")
            self._publish_state_change(old_state, state)

    def _revert_temporary_state(self) -> None:
        """Reverts from a timed emotional reaction back to the base state."""
        with self._lock:
            self._temporary_state_timer = None
            old_state = self._current_state
            self._current_state = self._base_state

        if old_state != self._current_state:
            logger.debug(f"Avatar temporary state reverted: {old_state.value} -> {self._current_state.value}")
            self._publish_state_change(old_state, self._current_state)

    def reset(self) -> None:
        """Resets avatar state to IDLE and clears audio level."""
        with self._lock:
            if self._temporary_state_timer is not None:
                self._temporary_state_timer.cancel()
                self._temporary_state_timer = None
            old_state = self._current_state
            self._current_state = AvatarState.IDLE
            self._base_state = AvatarState.IDLE
            self._audio_level = 0.0

        if old_state != AvatarState.IDLE:
            self._publish_state_change(old_state, AvatarState.IDLE)

    def _publish_state_change(self, old_state: AvatarState, new_state: AvatarState) -> None:
        """Publishes AVATAR_STATE_CHANGED event on the EventBus."""
        cfg = AvatarTheme.get_config(new_state)
        event = Event(
            event_type=EventType.AVATAR_STATE_CHANGED,
            data={
                "old_state": old_state.value,
                "new_state": new_state.value,
                "config": asdict(cfg),
            },
            source="avatar.controller",
        )
        self._bus.publish(event)

    def _subscribe_events(self) -> None:
        """Subscribes to relevant lifecycle and conversational events."""
        if self._is_subscribed:
            return

        self._bus.subscribe(EventType.MIC_LISTENING_START, self._on_mic_start)
        self._bus.subscribe(EventType.MIC_LISTENING_STOP, self._on_mic_stop)
        self._bus.subscribe(EventType.SPEECH_DETECTED, self._on_speech_detected)
        self._bus.subscribe(EventType.JARVIS_THINKING_START, self._on_thinking_start)
        self._bus.subscribe(EventType.JARVIS_THINKING_STOP, self._on_thinking_stop)
        self._bus.subscribe(EventType.TTS_SPEAKING_START, self._on_tts_start)
        self._bus.subscribe(EventType.TTS_SPEAKING_STOP, self._on_tts_stop)
        self._bus.subscribe(EventType.TTS_INTERRUPTED, self._on_tts_interrupted)
        self._bus.subscribe(EventType.EMOTION_STATE_CHANGED, self._on_emotion_state_changed)
        self._bus.subscribe(EventType.USER_EMOTION_DETECTED, self._on_user_emotion_detected)

        self._is_subscribed = True

    def unsubscribe_events(self) -> None:
        """Unsubscribes all event handlers from the EventBus."""
        if not self._is_subscribed:
            return

        self._bus.unsubscribe(EventType.MIC_LISTENING_START, self._on_mic_start)
        self._bus.unsubscribe(EventType.MIC_LISTENING_STOP, self._on_mic_stop)
        self._bus.unsubscribe(EventType.SPEECH_DETECTED, self._on_speech_detected)
        self._bus.unsubscribe(EventType.JARVIS_THINKING_START, self._on_thinking_start)
        self._bus.unsubscribe(EventType.JARVIS_THINKING_STOP, self._on_thinking_stop)
        self._bus.unsubscribe(EventType.TTS_SPEAKING_START, self._on_tts_start)
        self._bus.unsubscribe(EventType.TTS_SPEAKING_STOP, self._on_tts_stop)
        self._bus.unsubscribe(EventType.TTS_INTERRUPTED, self._on_tts_interrupted)
        self._bus.unsubscribe(EventType.EMOTION_STATE_CHANGED, self._on_emotion_state_changed)
        self._bus.unsubscribe(EventType.USER_EMOTION_DETECTED, self._on_user_emotion_detected)

        self._is_subscribed = False

    # Event handlers
    def _on_mic_start(self, event: Event) -> None:
        self.set_state(AvatarState.LISTENING)

    def _on_mic_stop(self, event: Event) -> None:
        if self._current_state == AvatarState.LISTENING:
            self.set_state(AvatarState.IDLE)
            self.set_audio_level(0.0)

    def _on_speech_detected(self, event: Event) -> None:
        rms = event.data.get("rms", 0.0)
        # Normalize typical RMS (0 to 3000) to 0.0 - 1.0
        normalized = min(1.0, float(rms) / 2500.0) if rms else 0.4
        self.set_audio_level(normalized)

    def _on_thinking_start(self, event: Event) -> None:
        self.set_state(AvatarState.THINKING)

    def _on_thinking_stop(self, event: Event) -> None:
        if self._current_state == AvatarState.THINKING:
            self.set_state(AvatarState.IDLE)

    def _on_tts_start(self, event: Event) -> None:
        self.set_state(AvatarState.SPEAKING)

    def _on_tts_stop(self, event: Event) -> None:
        if self._current_state == AvatarState.SPEAKING:
            self.set_state(AvatarState.IDLE)
            self.set_audio_level(0.0)

    def _on_tts_interrupted(self, event: Event) -> None:
        self.set_state(AvatarState.IDLE)
        self.set_audio_level(0.0)

    def _on_emotion_state_changed(self, event: Event) -> None:
        """Adapts baseline resting visual state based on JARVIS's internal emotional state."""
        # Only adjust resting base state if not in an active conversational turn (thinking/speaking/listening)
        if self._current_state in (AvatarState.SPEAKING, AvatarState.THINKING, AvatarState.LISTENING):
            return

        vector = event.data.get("state_vector", {})
        if not vector:
            return

        sadness = vector.get("sadness", 0.0)
        anger = vector.get("anger", 0.0)
        concern = vector.get("concern", 0.0)
        happiness = vector.get("happiness", 0.0)

        new_state = AvatarState.IDLE
        if anger > 40.0:
            new_state = AvatarState.ANGRY
        elif sadness > 40.0:
            new_state = AvatarState.SAD
        elif concern > 50.0:
            new_state = AvatarState.CONCERNED
        elif happiness > 80.0:
            new_state = AvatarState.HAPPY

        self.set_state(new_state)

    def _on_user_emotion_detected(self, event: Event) -> None:
        """Triggers a brief empathetic visual reaction when user emotion is detected."""
        detected = event.data.get("detected_emotion", "").lower()
        if not detected:
            return

        # Brief 2.5 second emotional reaction
        if detected in ("frustrated", "angry"):
            self.set_state(AvatarState.CONCERNED, duration=2.5)
        elif detected in ("sad", "disappointed", "lonely"):
            self.set_state(AvatarState.SAD, duration=2.5)
        elif detected in ("excited", "joyful", "happy", "grateful"):
            self.set_state(AvatarState.HAPPY, duration=2.5)
        elif detected in ("surprised", "confused"):
            self.set_state(AvatarState.SURPRISED, duration=2.5)


_controller_instance: Optional[AvatarController] = None


def get_avatar_controller(event_bus: Optional[EventBus] = None) -> AvatarController:
    """Singleton getter for AvatarController."""
    global _controller_instance
    if _controller_instance is None:
        _controller_instance = AvatarController(event_bus=event_bus)
    return _controller_instance
