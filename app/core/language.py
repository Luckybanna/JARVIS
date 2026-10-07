"""
Language and script detection utilities for JARVIS.
Detects Devanagari script and colloquial Hinglish vocabulary.
"""

import re

HINGLISH_KEYWORDS = {
    "aap", "aapko", "aapka", "aapki", "kaise", "kya", "kyun", "kab", "kaha",
    "hai", "hain", "karo", "karna", "rahe", "rahi", "kaam", "nahi", "accha",
    "theek", "shukriya", "namaste", "dhanyawad", "kal", "aaj", "jana", "mera", "meri",
    "batao", "bataiye", "bata", "kholo", "chalao", "band", "dhoondo", "bolo", "suno", "haan", "mat",
}


def detect_language_hint(text: str) -> str:
    """Detects whether text is Hindi/Hinglish ('hi') or English ('en')."""
    if not text:
        return "en"

    # Check Devanagari script (U+0900 to U+097F)
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"

    # Check Romanized Hinglish tokens
    words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
    if not words:
        return "en"

    hinglish_matches = sum(1 for w in words if w in HINGLISH_KEYWORDS)
    if (hinglish_matches / len(words)) >= 0.15:
        return "hi"

    return "en"
