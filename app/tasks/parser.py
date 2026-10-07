"""
Multilingual Natural Language Date/Time and Reminder Parser for JARVIS.
Extracts target reminder titles and computes execution timestamps from English, Hindi, and Hinglish.
"""

from datetime import datetime, timedelta
import re
import time
from typing import Optional, Tuple

from app.core.logger import get_logger

logger = get_logger("tasks.parser")

HINDI_NUMBERS = {
    "ek": 1,
    "do": 2,
    "teen": 3,
    "char": 4,
    "chaar": 4,
    "paanch": 5,
    "panch": 5,
    "che": 6,
    "chhe": 6,
    "saat": 7,
    "aath": 8,
    "nau": 9,
    "dus": 10,
    "das": 10,
    "pandrah": 15,
    "bees": 20,
    "tees": 30,
}


def parse_reminder_text(text: str) -> Optional[Tuple[str, float]]:
    """
    Parses a conversational reminder request into (title, due_timestamp).
    Returns None if text does not contain a recognizable reminder or time expression.
    """
    clean = text.strip()
    if not clean:
        return None

    # Step 1: Detect and calculate due timestamp
    due_ts, matched_time_phrase = _extract_due_timestamp(clean)
    if due_ts is None:
        return None

    # Step 2: Extract reminder subject / title by stripping out trigger & time phrases
    title = _extract_reminder_title(clean, matched_time_phrase)
    if not title:
        title = "Scheduled Reminder"

    return title, due_ts


def _extract_due_timestamp(text: str) -> Tuple[Optional[float], Optional[str]]:
    """Identifies relative or absolute time expressions and calculates timestamp."""
    now = datetime.now()
    clean = text.lower()

    # Pattern 1: Relative minutes/hours/seconds in English
    # e.g., "in 15 minutes", "in 2 hours", "in 45 seconds"
    m_rel_en = re.search(r"\bin\s+(\d+|an?|one|two|three|four|five|ten|fifteen|thirty)\s+(seconds?|secs?|minutes?|mins?|hours?|hrs?|days?)\b", clean)
    if m_rel_en:
        matched_str = m_rel_en.group(0)
        num_str = m_rel_en.group(1)
        unit = m_rel_en.group(2)

        val = 1
        if num_str.isdigit():
            val = int(num_str)
        elif num_str in ("a", "an", "one"):
            val = 1
        elif num_str == "two":
            val = 2
        elif num_str == "three":
            val = 3
        elif num_str == "four":
            val = 4
        elif num_str == "five":
            val = 5
        elif num_str == "ten":
            val = 10
        elif num_str == "fifteen":
            val = 15
        elif num_str == "thirty":
            val = 30

        delta = timedelta()
        if "sec" in unit:
            delta = timedelta(seconds=val)
        elif "min" in unit:
            delta = timedelta(minutes=val)
        elif "hour" in unit or "hr" in unit:
            delta = timedelta(hours=val)
        elif "day" in unit:
            delta = timedelta(days=val)

        return (now + delta).timestamp(), matched_str

    # Pattern 2: Relative time in Hindi/Hinglish
    # e.g., "10 minute baad", "do ghante baad", "aadha ghanta baad", "pandrah min baad"
    m_rel_hi = re.search(r"\b(\d+|ek|do|teen|chaar|char|paanch|panch|das|dus|pandrah|bees|tees|aadha|adha)\s+(minute|min|ghante?|ghanta|seconds?)\s+baad\b", clean)
    if m_rel_hi:
        matched_str = m_rel_hi.group(0)
        num_word = m_rel_hi.group(1)
        unit = m_rel_hi.group(2)

        if num_word.isdigit():
            val = float(num_word)
        elif num_word in ("aadha", "adha"):
            val = 0.5
        else:
            val = float(HINDI_NUMBERS.get(num_word, 1))

        delta = timedelta()
        if "sec" in unit:
            delta = timedelta(seconds=val)
        elif "min" in unit:
            delta = timedelta(minutes=val)
        elif "ghant" in unit:
            delta = timedelta(hours=val)

        return (now + delta).timestamp(), matched_str

    # Pattern 3: Specific time of day with AM/PM (e.g. "at 5:30 pm", "at 9 am", "at 18:00")
    m_time_en = re.search(r"\b(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", clean)
    if m_time_en:
        matched_str = m_time_en.group(0)
        hour = int(m_time_en.group(1))
        minute = int(m_time_en.group(2)) if m_time_en.group(2) else 0
        ampm = m_time_en.group(3)

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        is_tomorrow = "tomorrow" in clean or "kal" in clean
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if is_tomorrow or target <= now:
            target += timedelta(days=1)

        return target.timestamp(), matched_str

    # Pattern 4: Hindi specific time of day (e.g. "subah 9 baje", "shaam 6 baje", "raat 10 baje", "4 baje")
    m_time_hi = re.search(r"\b(subah|dopahar|shaam|raat)?\s*(\d{1,2}|ek|do|teen|chaar|char|paanch|panch|che|chhe|saat|aath|nau|das|dus)\s*baje\b", clean)
    if m_time_hi:
        matched_str = m_time_hi.group(0)
        period = m_time_hi.group(1) or ""
        hour_word = m_time_hi.group(2)

        hour = int(hour_word) if hour_word.isdigit() else HINDI_NUMBERS.get(hour_word, 1)

        if period in ("shaam", "raat") and hour < 12:
            hour += 12
        elif period == "dopahar" and hour in (1, 2, 3, 4):
            hour += 12

        is_tomorrow = "kal" in clean or "tomorrow" in clean
        target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if is_tomorrow or target <= now:
            target += timedelta(days=1)

        return target.timestamp(), matched_str

    return None, None


def _extract_reminder_title(text: str, time_phrase: Optional[str]) -> str:
    """Cleans command prefixes and the matched time phrase to isolate the reminder content."""
    clean = text

    # Remove matched time expression
    if time_phrase:
        clean = re.sub(re.escape(time_phrase), "", clean, flags=re.IGNORECASE)

    # Remove standard reminder boilerplate prefixes
    prefixes = [
        r"^(?:jarvis\s*,?\s*)?",
        r"(?:please\s+)?(?:remind\s+me\s+(?:to\s+|that\s+|about\s+)?|set\s+(?:a\s+)?reminder\s+(?:to\s+|for\s+)?|create\s+(?:a\s+)?reminder\s+(?:for\s+)?)",
        r"(?:yaad\s+dilana|yaad\s+dilao|reminder\s+set\s+karo|mujhe\s+yaad\s+dilana|ek\s+reminder\s+lagao)",
    ]

    for p in prefixes:
        clean = re.sub(p, "", clean, flags=re.IGNORECASE).strip()

    # Remove trailing reminder tokens (Hindi: "yaad dilana", "yaad rakhna")
    clean = re.sub(r"\b(yaad\s+dilana|yaad\s+dilao|yaad\s+rakhna|remind\s+me)\b", "", clean, flags=re.IGNORECASE).strip()

    # Clean whitespace and punctuation
    clean = re.sub(r"\s+", " ", clean).strip(" ,.-:;")
    return clean if clean else "Reminder"
