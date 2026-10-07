"""
Emotion Engine for JARVIS.
Applies deterministic state transition rules and broadcasts emotional state telemetry.
"""

import threading
from typing import Dict, Optional, Tuple

from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.logger import get_logger
from app.emotion.detector import DetectedEmotion, UserEmotionDetector, UserEmotionType
from app.emotion.state import EmotionState

logger = get_logger("emotion.engine")


class EmotionEngine:
    """Manages simulated emotional dynamics, deterministic transitions, and telemetry."""

    def __init__(
        self,
        initial_state: Optional[EmotionState] = None,
        detector: Optional[UserEmotionDetector] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.state: EmotionState = initial_state or EmotionState()
        self.detector: UserEmotionDetector = detector or UserEmotionDetector()
        self.event_bus: EventBus = event_bus or get_event_bus()
        self._lock = threading.RLock()
        self.last_detected_user_emotion: Optional[DetectedEmotion] = None

    def process_user_turn(self, user_text: str) -> Tuple[DetectedEmotion, EmotionState]:
        """Analyzes user input, classifies emotion, and deterministically shifts internal state."""
        with self._lock:
            # 1. Detect User Emotion
            detected = self.detector.detect(user_text)
            self.last_detected_user_emotion = detected

            # Publish User Emotion Event
            self.event_bus.publish(
                Event(
                    event_type=EventType.USER_EMOTION_DETECTED,
                    data=detected.to_dict(),
                    source="emotion_engine",
                )
            )

            # 2. Apply Deterministic State Transition Rules
            prev_dominant = self.state.dominant_emotion()
            self._apply_transition_rules(detected, user_text)

            # 3. Publish State Changed Event
            self.event_bus.publish(
                Event(
                    event_type=EventType.EMOTION_STATE_CHANGED,
                    data={
                        "state": self.state.to_dict(),
                        "dominant": self.state.dominant_emotion(),
                        "user_emotion": detected.emotion.value,
                    },
                    source="emotion_engine",
                )
            )

            curr_dominant = self.state.dominant_emotion()
            logger.info(
                f"User Emotion: {detected.emotion.value} ({detected.confidence:.2f}) -> "
                f"JARVIS State: dominant={curr_dominant} (concern={self.state.concern}, "
                f"happiness={self.state.happiness}, curiosity={self.state.curiosity})"
            )

            return detected, self.state

    def _apply_transition_rules(self, detected: DetectedEmotion, user_text: str) -> None:
        """Deterministic state updates based on classified emotion and context."""
        emotion = detected.emotion

        # First, decay slightly towards baseline so values don't stick forever at extremes
        self.state.decay_toward_baseline(rate=0.10)

        if emotion == UserEmotionType.HAPPY:
            # Praise or positivity: happiness, confidence, and trust increase
            self.state.happiness += 12
            self.state.confidence += 8
            self.state.trust += 5
            self.state.concern -= 5

        elif emotion in (UserEmotionType.FRUSTRATED, UserEmotionType.STRESSED):
            # User struggling: concern increases, warmth increases, happiness dampens
            self.state.concern += 20
            self.state.happiness -= 8
            self.state.curiosity += 5

        elif emotion == UserEmotionType.SAD:
            # Empathy mode: concern jumps, sadness reflects mildly, energy softens
            self.state.concern += 25
            self.state.sadness += 10
            self.state.happiness -= 15
            self.state.energy -= 10

        elif emotion == UserEmotionType.ANGRY:
            # User irritated: concern increases, confidence slightly checks itself
            self.state.concern += 30
            self.state.confidence -= 10
            self.state.happiness -= 15

        elif emotion == UserEmotionType.TIRED:
            # User fatigued: concern rises, energy drops to match calmer speaking posture
            self.state.concern += 18
            self.state.energy -= 20
            self.state.happiness -= 5

        elif emotion == UserEmotionType.CURIOUS:
            # Intellectual engagement: curiosity spikes, energy rises
            self.state.curiosity += 18
            self.state.energy += 8
            self.state.confidence += 5

        elif emotion == UserEmotionType.EXCITED:
            # Shared enthusiasm: energy and happiness surge
            self.state.happiness += 15
            self.state.energy += 15
            self.state.confidence += 8

        elif emotion == UserEmotionType.CONFUSED:
            # User needs guidance: curiosity and concern rise
            self.state.concern += 12
            self.state.curiosity += 10

        # Ensure all fields remain strictly within [0, 100]
        self.state._clamp_all()

    def get_context_for_prompt(self) -> Dict[str, any]:
        """Provides snapshot data formatted for PromptBuilder."""
        with self._lock:
            user_emo = self.last_detected_user_emotion.emotion.value if self.last_detected_user_emotion else "neutral"
            conf = self.last_detected_user_emotion.confidence if self.last_detected_user_emotion else 1.0
            return {
                "user_emotion": user_emo,
                "confidence": conf,
                "simulated_state": self.state.to_dict(),
                "dominant_emotion": self.state.dominant_emotion(),
            }

    def get_state_dict(self) -> Dict[str, int]:
        with self._lock:
            return self.state.to_dict()


_engine_instance: Optional[EmotionEngine] = None


def get_emotion_engine() -> EmotionEngine:
    """Singleton getter for the global EmotionEngine."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = EmotionEngine()
    return _engine_instance
