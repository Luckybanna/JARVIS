"""
User Emotion Detection and Sentiment Classification for JARVIS.
Analyzes user inputs across English, Hindi, and Hinglish for emotional context with confidence scores.
NOTE: Purely conversational/interaction classification; no medical or psychological diagnosis.
"""

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import List, Tuple


class UserEmotionType(str, Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FRUSTRATED = "frustrated"
    ANXIOUS = "anxious"
    EXCITED = "excited"
    CONFUSED = "confused"
    TIRED = "tired"
    CURIOUS = "curious"
    STRESSED = "stressed"


@dataclass
class DetectedEmotion:
    """Emotional classification of user utterance."""
    emotion: UserEmotionType
    confidence: float
    trigger_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "emotion": self.emotion.value,
            "confidence": round(self.confidence, 2),
            "triggers": self.trigger_keywords,
        }


class UserEmotionDetector:
    """Multi-lingual emotion detector using rule-based lexicons with scoring."""

    # Emotion keywords and patterns across English and Hindi/Hinglish
    PATTERNS: List[Tuple[UserEmotionType, List[str], float]] = [
        # FRUSTRATED
        (
            UserEmotionType.FRUSTRATED,
            [
                r"\b(frustrated|frustrating|annoying|annoyed|irritating|stuck|stupid bug|doesn't work|not working)\b",
                r"\b(pareshan|dimag kharab|tang aa gaya|chidh|chal nahi raha|gadbad|bekaar)\b",
            ],
            0.85,
        ),
        # STRESSED
        (
            UserEmotionType.STRESSED,
            [
                r"\b(stressed|stressful|overwhelmed|too much work|pressure|deadline|burnout)\b",
                r"\b(bahut tension|badi tension|bojh|dabav|pagal ho raha)\b",
            ],
            0.86,
        ),
        # ANXIOUS
        (
            UserEmotionType.ANXIOUS,
            [
                r"\b(anxious|anxiety|worried|nervous|scared|dread|fear|panicking)\b",
                r"\b(chinta|dar lag raha|ghabrahat|fidgety|nervous hoon)\b",
            ],
            0.83,
        ),
        # TIRED
        (
            UserEmotionType.TIRED,
            [
                r"\b(tired|exhausted|sleepy|drained|fatigued|need a break|need sleep)\b",
                r"\b(thak gaya|thak gayi|thaka hua|neend aa rahi|exhaust ho gaya|break chahiye)\b",
            ],
            0.88,
        ),
        # CONFUSED
        (
            UserEmotionType.CONFUSED,
            [
                r"\b(confused|confusing|don't understand|makes no sense|lost|unclear|puzzled)\b",
                r"\b(samajh nahi aa raha|kuch samajh nahi|confuse ho gaya|bhatak gaya)\b",
            ],
            0.84,
        ),
        # EXCITED
        (
            UserEmotionType.EXCITED,
            [
                r"\b(excited|incredible|awesome|brilliant|fantastic|let's go|epic|amazing|huge win)\b",
                r"\b(maza aa gaya|shandar|zabardast|kamaal|super excited|dhamaka)\b",
            ],
            0.87,
        ),
        # HAPPY (Includes praise for JARVIS)
        (
            UserEmotionType.HAPPY,
            [
                r"\b(happy|glad|delighted|pleased|great job|thank you jarvis|well done|good work)\b",
                r"\b(khush|badiya|accha laga|shabash|dhanyawad|sukoon)\b",
            ],
            0.85,
        ),
        # SAD
        (
            UserEmotionType.SAD,
            [
                r"\b(sad|depressed|unhappy|down|feeling low|heartbroken|hopeless)\b",
                r"\b(udas|dukhi|rona aa raha|man udas|bura lag raha)\b",
            ],
            0.85,
        ),
        # ANGRY
        (
            UserEmotionType.ANGRY,
            [
                r"\b(angry|furious|mad|rage|hate this|shut up|useless)\b",
                r"\b(gussa|gusse mein|bakwas|chup raho)\b",
            ],
            0.88,
        ),
        # CURIOUS
        (
            UserEmotionType.CURIOUS,
            [
                r"\b(curious|i wonder|how does|why does|what if|fascinating|tell me how)\b",
                r"\b(jaan na chahta|soch raha tha|kaise kaam karta|kya wajah)\b",
            ],
            0.80,
        ),
    ]

    def detect(self, text: str) -> DetectedEmotion:
        """Classifies the emotion of a given user input with confidence scoring."""
        cleaned = text.strip().lower()
        if not cleaned:
            return DetectedEmotion(emotion=UserEmotionType.NEUTRAL, confidence=1.0)

        best_emotion = UserEmotionType.NEUTRAL
        best_confidence = 0.50
        matched_triggers = []

        for emotion_type, patterns, base_conf in self.PATTERNS:
            for pat in patterns:
                matches = re.findall(pat, cleaned, re.IGNORECASE)
                if matches:
                    # Flatten matches
                    triggers = [m if isinstance(m, str) else m[0] for m in matches]
                    matched_triggers.extend(triggers)

                    # Boost confidence slightly with multiple matching triggers
                    boosted_conf = min(0.98, base_conf + (0.04 * (len(triggers) - 1)))
                    if boosted_conf > best_confidence:
                        best_confidence = boosted_conf
                        best_emotion = emotion_type

        if best_emotion == UserEmotionType.NEUTRAL:
            return DetectedEmotion(
                emotion=UserEmotionType.NEUTRAL,
                confidence=0.80,
                trigger_keywords=[],
            )

        return DetectedEmotion(
            emotion=best_emotion,
            confidence=best_confidence,
            trigger_keywords=matched_triggers,
        )
