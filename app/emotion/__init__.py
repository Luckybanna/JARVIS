"""
Emotion Subsystem for JARVIS.
Includes internal simulated emotional state vector and user emotion classification.
"""

from app.emotion.state import EmotionState
from app.emotion.detector import UserEmotionDetector, DetectedEmotion, UserEmotionType
from app.emotion.engine import EmotionEngine, get_emotion_engine

__all__ = [
    "EmotionState",
    "UserEmotionDetector",
    "DetectedEmotion",
    "UserEmotionType",
    "EmotionEngine",
    "get_emotion_engine",
]
