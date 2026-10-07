"""
Unit and integration tests for JARVIS Emotion Subsystem.
"""

import pytest

from app.emotion.state import EmotionState
from app.emotion.detector import UserEmotionDetector, UserEmotionType, DetectedEmotion
from app.emotion.engine import EmotionEngine
from app.core.events import EventBus, EventType
from app.core.conversation import ConversationManager
from app.ai.base import AIProvider, AIResponse, TokenUsage


class EmotionRecordingAIProvider(AIProvider):
    def __init__(self):
        super().__init__(model_name="emo-rec-v1")
        self.last_system_prompt = ""

    @property
    def provider_name(self) -> str:
        return "emo_recorder"

    def generate(self, messages, system_prompt=None, **kwargs):
        self.last_system_prompt = system_prompt or ""
        return AIResponse(
            content="Understood.",
            model="emo-rec-v1",
            usage=TokenUsage(5, 5, 10),
            latency_ms=10.0,
        )

    def stream(self, *args, **kwargs):
        yield "emo"

    def health_check(self):
        return True, "EmoRecorder OK"


def test_emotion_state_defaults_and_clamping():
    state = EmotionState()
    assert state.happiness == 70
    assert state.sadness == 10
    assert state.anger == 0
    assert state.fear == 0
    assert state.curiosity == 80
    assert state.concern == 20
    assert state.confidence == 85
    assert state.energy == 70
    assert state.trust == 60
    assert state.dominant_emotion() == "calm"

    # Clamping test
    state.happiness = 150
    state.sadness = -20
    state._clamp_all()
    assert state.happiness == 100
    assert state.sadness == 0


def test_emotion_state_decay():
    state = EmotionState(concern=90, happiness=30)
    # Decay toward baseline (baseline concern is 20, baseline happiness is 70)
    state.decay_toward_baseline(rate=0.20)
    assert state.concern < 90
    assert state.happiness > 30


def test_user_emotion_detector_multilingual():
    detector = UserEmotionDetector()

    # English & Hinglish FRUSTRATED
    d1 = detector.detect("This stupid bug isn't working, so annoying!")
    assert d1.emotion == UserEmotionType.FRUSTRATED
    assert d1.confidence >= 0.80

    d1_hi = detector.detect("Mera dimag kharab ho gaya hai is code se")
    assert d1_hi.emotion == UserEmotionType.FRUSTRATED

    # English & Hinglish TIRED
    d2 = detector.detect("I am completely exhausted and need a break")
    assert d2.emotion == UserEmotionType.TIRED
    assert d2.confidence >= 0.80

    d2_hi = detector.detect("Main bahut thak gaya hoon aaj")
    assert d2_hi.emotion == UserEmotionType.TIRED

    # English & Hinglish HAPPY / PRAISE
    d3 = detector.detect("Great job Jarvis, thank you for the help!")
    assert d3.emotion == UserEmotionType.HAPPY

    d3_hi = detector.detect("Shabash Jarvis, accha laga kaam dekh kar")
    assert d3_hi.emotion == UserEmotionType.HAPPY

    # English & Hinglish CURIOUS
    d4 = detector.detect("I wonder how quantum computing really works")
    assert d4.emotion == UserEmotionType.CURIOUS

    d4_hi = detector.detect("Main jaan na chahta hoon ki AI model kaise kaam karta hai")
    assert d4_hi.emotion == UserEmotionType.CURIOUS

    # CONFUSED
    d5 = detector.detect("I don't understand this syntax at all, totally confused")
    assert d5.emotion == UserEmotionType.CONFUSED

    # STRESSED
    d6 = detector.detect("I have too much work pressure and deadline tension")
    assert d6.emotion == UserEmotionType.STRESSED

    # NEUTRAL
    d7 = detector.detect("Open calculator and check system memory")
    assert d7.emotion == UserEmotionType.NEUTRAL


def test_emotion_engine_deterministic_transitions():
    bus = EventBus()
    events = []
    bus.subscribe_all(lambda e: events.append(e.event_type))

    engine = EmotionEngine(event_bus=bus)

    # Initial resting state
    init_happy = engine.state.happiness
    init_conf = engine.state.confidence
    init_concern = engine.state.concern

    # 1. User praises JARVIS -> Happiness & confidence increase
    detected, state = engine.process_user_turn("Great job Jarvis, well done!")
    assert detected.emotion == UserEmotionType.HAPPY
    assert state.happiness > init_happy
    assert state.confidence > init_conf
    assert EventType.USER_EMOTION_DETECTED in events
    assert EventType.EMOTION_STATE_CHANGED in events

    # 2. User is struggling -> Concern increases
    engine.process_user_turn("I am stuck on this frustrating issue, so annoying")
    assert engine.state.concern > init_concern

    # 3. User is curious -> Curiosity increases
    init_curious = engine.state.curiosity
    engine.process_user_turn("I wonder how neural networks optimize gradients")
    assert engine.state.curiosity >= init_curious


def test_conversation_manager_emotion_integration():
    rec_provider = EmotionRecordingAIProvider()
    engine = EmotionEngine()
    conv = ConversationManager(provider=rec_provider, emotion_engine=engine)

    # Send a stressed/frustrated message
    conv.send_user_message("I am so stressed and frustrated with this deadline")

    # Verify PromptBuilder injected the detected user emotion and emotion vector!
    prompt = rec_provider.last_system_prompt
    assert "EMOTION & EMPATHY CONTEXT:" in prompt
    assert "frustrated" in prompt or "stressed" in prompt
    assert "Internal Emotion Vector:" in prompt
    assert "concern" in prompt
