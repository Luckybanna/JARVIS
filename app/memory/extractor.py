"""
Memory Extraction Engine for JARVIS.
Distinguishes transient conversational queries from durable user facts, preferences, and projects.
"""

from dataclasses import dataclass
import re
from typing import Optional


@dataclass
class ExtractedMemory:
    """A single piece of information identified as worth remembering."""
    content: str
    category: str  # "preference", "user_fact", "project", "decision", "general"
    importance: int  # 1 to 5
    confidence: float  # 0.0 to 1.0


class MemoryExtractor:
    """Analyzes user statements and determines whether durable memory should be created."""

    # Transient questions and conversational fillers that should NEVER be stored
    TRANSIENT_PATTERNS = [
        r"^(what time|what is the time|kya samay|kitne baje|time kya hai)",
        r"^(how is the weather|weather today|mausam kaisa hai|temperature)",
        r"^(what is|who is|where is|when was|how to|define|calculate|translate)",
        r"^(hello|hi|hey|good morning|good night|namaste|kaise ho|kya haal hai)",
        r"^(thank you|thanks|shukriya|dhanyawad|bye|goodbye|see you)",
        r"^(open|launch|close|search|find|play|volume|screen)",
        r"^(yes|no|ok|okay|sure|theek hai|accha|hanji)",
    ]

    # Explicit and high-signal patterns for durable memories
    EXTRACTION_RULES = [
        # Explicit user instructions
        (
            r"\b(?:please\s+)?(?:remember\s+that|don't\s+forget\s+that|keep\s+in\s+mind\s+that)\s+(.+)",
            "user_fact",
            5,
            0.98,
        ),
        (
            r"\b(?:yaad\s+rakhna\s+ki|bhoolna\s+mat\s+ki|dhyan\s+rakhna\s+ki)\s+(.+)",
            "user_fact",
            5,
            0.98,
        ),
        # User Identity & Personal details
        (
            r"\b(?:my\s+name\s+is|call\s+me|i\s+am\s+called)\s+([A-Za-z]+)\b",
            "user_fact",
            5,
            0.95,
        ),
        (
            r"\b(?:mera\s+naam|mujhe)\s+([A-Za-z]+)\s+(?:hai|bulao)",
            "user_fact",
            5,
            0.95,
        ),
        (
            r"\b(?:i\s+live\s+in|i\s+am\s+from|my\s+city\s+is)\s+(.+)",
            "user_fact",
            4,
            0.90,
        ),
        (
            r"\b(?:main\s+([A-Za-z\s]+)\s+mein\s+rehta\s+hoon|mera\s+shehar\s+([A-Za-z\s]+)\s+hai)",
            "user_fact",
            4,
            0.90,
        ),
        # Preferences
        (
            r"\b(?:my\s+favorite\s+(?:programming\s+)?([a-zA-Z\s]+)\s+is\s+(.+))",
            "preference",
            4,
            0.92,
        ),
        (
            r"\b(?:mera\s+favorite\s+([a-zA-Z\s]+)\s+(.+)\s+hai)",
            "preference",
            4,
            0.92,
        ),
        (
            r"\b(?:i\s+prefer\s+(.+)|i\s+like\s+(.+)\s+better|i\s+always\s+use\s+(.+))",
            "preference",
            4,
            0.88,
        ),
        (
            r"\b(?:mujhe\s+(.+)\s+pasand\s+hai|main\s+hamesha\s+(.+)\s+use\s+karta\s+hoon)",
            "preference",
            4,
            0.88,
        ),
        # Projects & Current work
        (
            r"\b(?:i\s+am\s+working\s+on|my\s+project\s+is|we\s+are\s+building)\s+(.+)",
            "project",
            4,
            0.90,
        ),
        (
            r"\b(?:main\s+(.+)\s+(?:project|app|code)\s+par\s+kaam\s+kar\s+raha\s+hoon)",
            "project",
            4,
            0.90,
        ),
        # Decisions
        (
            r"\b(?:we\s+decided\s+to|i\s+have\s+decided\s+to|my\s+decision\s+is\s+to)\s+(.+)",
            "decision",
            4,
            0.90,
        ),
        (
            r"\b(?:maine\s+decide\s+kiya\s+hai\s+ki|humne\s+faisla\s+kiya\s+ki)\s+(.+)",
            "decision",
            4,
            0.90,
        ),
    ]

    def is_transient(self, text: str) -> bool:
        """Checks if the statement is a transient query or greeting."""
        text_lower = text.lower().strip()
        for pat in self.TRANSIENT_PATTERNS:
            if re.search(pat, text_lower):
                return True
        return False

    def extract(self, text: str) -> Optional[ExtractedMemory]:
        """Examines user text and returns an ExtractedMemory if worthy, otherwise None."""
        cleaned = text.strip()
        if not cleaned:
            return None

        # Check transient filter first
        if self.is_transient(cleaned):
            return None

        text_lower = cleaned.lower()

        # Check explicit and high-signal rules
        for pattern, category, importance, confidence in self.EXTRACTION_RULES:
            match = re.search(pattern, cleaned, re.IGNORECASE)
            if match:
                # Format clean representation
                captured_groups = [g.strip() for g in match.groups() if g and g.strip()]
                if not captured_groups:
                    continue

                # If it's a "remember that X" command, extract X
                if re.search(r"\b(?:remember\s+that|yaad\s+rakhna\s+ki)\b", cleaned, re.IGNORECASE):
                    fact = captured_groups[0]
                    # Strip trailing punctuation
                    fact = re.sub(r"[.?!]+$", "", fact).strip()
                    # Capitalize first letter
                    fact = fact[0].upper() + fact[1:] if len(fact) > 1 else fact
                    return ExtractedMemory(
                        content=fact,
                        category=category,
                        importance=importance,
                        confidence=confidence,
                    )

                # Format preference or statement
                content = cleaned
                # Strip trailing punctuation
                content = re.sub(r"[.?!]+$", "", content).strip()

                return ExtractedMemory(
                    content=content,
                    category=category,
                    importance=importance,
                    confidence=confidence,
                )

        return None
