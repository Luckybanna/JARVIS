"""
Conversational Prosody and Speech Normalization Engine for JARVIS.
Provides dynamic pitch, rhythm variation, question intonations, and Hinglish normalization.
"""

from dataclasses import dataclass
import re
from typing import List


@dataclass
class SentenceProsody:
    """Represents a speech unit with prosodic instructions."""
    text: str
    pitch: str
    rate: str
    sentence_type: str
    pause_after_ms: int = 180


# Conversational markers for Hindi/Hinglish and English
GREETING_PATTERNS = [
    r"\b(hello|hi|hey|namaste|good morning|good afternoon|good evening|haanji|arre|suneye|welcome)\b",
]

QUESTION_PATTERNS = [
    r"\?$",
    r"\b(kya|kaise|kyun|kab|kaha|kiska|kiski|kitna|kitni|kaun|batao|bataiye)\b",
    r"\b(what|why|how|when|where|who|is it|can you|would you|should we|shall we)\b",
]

EMPATHY_PATTERNS = [
    r"\b(khana|rest|break|aaram|thoda|tired|thak|tabiyat|paani|health|care|take care|so jao)\b",
]

CONFIRMATION_PATTERNS = [
    r"\b(kar diya|chala diya|open kar diya|ho gaya|done|playing|opened|launching|switched)\b",
]

# Complete Hinglish number mappings for natural spoken delivery (0-99)
HINDI_NUMBERS = {
    0: "zero", 1: "ek", 2: "do", 3: "teen", 4: "chaar", 5: "paanch",
    6: "chhe", 7: "saat", 8: "aath", 9: "nau", 10: "das",
    11: "gyarah", 12: "barah", 13: "terah", 14: "chaudah", 15: "pandrah",
    16: "solah", 17: "satrah", 18: "athaarah", 19: "unnis",
    20: "bees", 21: "ikkis", 22: "baais", 23: "teis", 24: "chaubees",
    25: "pachchis", 26: "chhabbees", 27: "sattaais", 28: "atthaais", 29: "untees",
    30: "tees", 31: "ikattees", 32: "battees", 33: "teintees", 34: "chautees",
    35: "paintees", 36: "chhattees", 37: "saintees", 38: "adhtees", 39: "unchaalis",
    40: "chaalis", 41: "iktaalis", 42: "bayaalis", 43: "teintaalis", 44: "chawalis",
    45: "paintaalis", 46: "chhiyaalis", 47: "saintaalis", 48: "adhtaalis", 49: "unchaas",
    50: "pachaas", 51: "ikyaawan", 52: "baawan", 53: "tirepan", 54: "chawwan",
    55: "pachpan", 56: "chhappan", 57: "sattaawan", 58: "atthaawan", 59: "unsath",
    60: "saath", 61: "iksath", 62: "baasath", 63: "tirsath", 64: "chaunsath",
    65: "painsath", 66: "chhiyaasath", 67: "sadsath", 68: "adhsath", 69: "unhattar",
    70: "sattar", 71: "ikhattar", 72: "bahattar", 73: "tihattar", 74: "chauhattar",
    75: "pachhattar", 76: "chhihattar", 77: "sathattar", 78: "athahattar", 79: "unasi",
    80: "assi", 81: "ikyaasi", 82: "bayaasi", 83: "tiraasi", 84: "chauraasi",
    85: "pachaasi", 86: "chhiyaasi", 87: "sattaasi", 88: "atthaasi", 89: "nawaasi",
    90: "nabbe", 91: "ikyaanwe", 92: "baanwe", 93: "tiraanwe", 94: "chauraanwe",
    95: "pachaanwe", 96: "chhiyaanwe", 97: "sattaanwe", 98: "atthaanwe", 99: "ninyaanwe",
    100: "sau",
}


def number_to_hindi_words(n: int) -> str:
    """Converts integers (0-99999) to natural spoken Hindi words."""
    if n in HINDI_NUMBERS:
        return HINDI_NUMBERS[n]
    if n < 1000:
        hundreds = n // 100
        remainder = n % 100
        h_str = f"{HINDI_NUMBERS.get(hundreds, str(hundreds))} sau"
        if remainder > 0:
            return f"{h_str} {HINDI_NUMBERS.get(remainder, str(remainder))}"
        return h_str
    if n < 100000:
        thousands = n // 1000
        remainder = n % 1000
        t_str = f"{HINDI_NUMBERS.get(thousands, str(thousands))} hazaar"
        if remainder > 0:
            if remainder >= 100:
                return f"{t_str} {number_to_hindi_words(remainder)}"
            return f"{t_str} {HINDI_NUMBERS.get(remainder, str(remainder))}"
        return t_str
    return str(n)


def normalize_hinglish_speech_text(text: str) -> str:
    """
    Cleans and normalizes text for natural, human-sounding speech.
    Converts tech abbreviations, numbers, percentages, and strips speech-distorting symbols.
    """
    if not text:
        return ""

    # 1. Remove code blocks and inline code
    t = re.sub(r"```[\s\S]*?```", "", text)
    t = re.sub(r"`([^`]+)`", r"\1", t)

    # 2. Remove markdown links and URLs
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = re.sub(r"https?://\S+|www\.\S+", "", t)

    # 3. Remove markdown headers, bold, italics, bullets, list numbers
    t = re.sub(r"[*_~#>]", "", t)
    t = re.sub(r"^\s*[\d\.\-\*•]+\s*", "", t, flags=re.MULTILINE)

    # 4. Remove emojis and unsupported unicode glyphs
    t = re.sub(r"[\U00010000-\U0010ffff]", "", t)
    t = re.sub(r"[\u2600-\u27bf\u2300-\u23ff]", "", t)

    # 5. Expand technical abbreviations for natural phonetic articulation
    t = re.sub(r"\bPC\b", "P C", t)
    t = re.sub(r"\bCPU\b", "C P U", t)
    t = re.sub(r"\bGPU\b", "G P U", t)
    t = re.sub(r"\bRAM\b", "Ram", t)
    t = re.sub(r"\bROM\b", "Rom", t)
    t = re.sub(r"\bSSD\b", "S S D", t)
    t = re.sub(r"\bHDD\b", "H D D", t)
    t = re.sub(r"\bUSB\b", "U S B", t)
    t = re.sub(r"\bMB\b", "M B", t)
    t = re.sub(r"\bGB\b", "G B", t)
    t = re.sub(r"\bTB\b", "T B", t)
    t = re.sub(r"\bKB\b", "K B", t)
    t = re.sub(r"\bGHz\b", "G H z", t)
    t = re.sub(r"\bMHz\b", "M H z", t)
    t = re.sub(r"\bFPS\b", "F P S", t)
    t = re.sub(r"\bUI\b", "U I", t)
    t = re.sub(r"\bOS\b", "O S", t)
    t = re.sub(r"\bAPI\b", "A P I", t)
    t = re.sub(r"\bURL\b", "U R L", t)
    t = re.sub(r"\bAI\b", "A I", t)
    t = re.sub(r"\bmin\b", "minute", t)
    t = re.sub(r"\bsec\b", "second", t)
    t = re.sub(r"\bhr\b", "ghante", t)

    # 6. Normalize percentages in speech (e.g. 86% -> chhiyaasi percent)
    def _pct_replace(match):
        num_str = match.group(1)
        try:
            val = int(num_str)
            return f"{number_to_hindi_words(val)} percent"
        except Exception:
            return f"{num_str} percent"

    t = re.sub(r"(\d+)%", _pct_replace, t)

    # 7. Convert numbers before computer units to natural Hindi words (e.g. 569 MB -> paanch sau unhattar M B)
    def _unit_num_replace(match):
        num_val = int(match.group(1))
        unit_str = match.group(2)
        return f"{number_to_hindi_words(num_val)} {unit_str}"

    t = re.sub(r"\b(\d+)\s*(M B|G B|T B|K B|percent|minute|second|ghante)\b", _unit_num_replace, t)

    # 8. Smooth punctuation: convert dashes/colons into natural conversational pauses
    t = re.sub(r"[-–—]", ", ", t)
    t = re.sub(r"[:;]", ", ", t)
    t = re.sub(r"[()\[\]{}]", ", ", t)
    t = re.sub(r"\.{3,}", "... ", t)
    t = re.sub(r"\.{2}", ". ", t)
    t = re.sub(r"[!]+", ".", t)

    # 9. Clean extra whitespace and punctuation clusters
    t = re.sub(r"\s*,\s*", ", ", t)
    t = re.sub(r",(\s*,)+", ", ", t)
    t = re.sub(r"\s*\.\s*", ". ", t)
    t = re.sub(r"\s*\?\s*", "? ", t)
    t = re.sub(r"\s+", " ", t).strip()

    return t


def classify_sentence(sentence: str) -> str:
    """Classifies sentence into a conversational speech category."""
    s_lower = sentence.lower().strip()

    # Question check (highest prosodic distinctiveness)
    for p in QUESTION_PATTERNS:
        if re.search(p, s_lower):
            return "question"

    # Caring / wellbeing check
    for p in EMPATHY_PATTERNS:
        if re.search(p, s_lower):
            return "empathy"

    # Greeting check
    for p in GREETING_PATTERNS:
        if re.search(p, s_lower):
            return "greeting"

    # Confirmation check
    for p in CONFIRMATION_PATTERNS:
        if re.search(p, s_lower):
            return "confirmation"

    return "statement"


def get_sentence_prosody(sentence: str, is_first: bool = False, is_last: bool = False) -> SentenceProsody:
    """
    Computes dynamic pitch, rate, and pause for a given sentence.
    Adds human-like pitch inflection (rising for questions, warm for greetings).
    """
    category = classify_sentence(sentence)

    if category == "greeting":
        # Warm, friendly, slightly lively (+2Hz)
        return SentenceProsody(
            text=sentence,
            pitch="+2Hz",
            rate="+0%",
            sentence_type="greeting",
            pause_after_ms=160,
        )
    elif category == "question":
        # Inquisitive with rising vocal inflection (+3Hz)
        return SentenceProsody(
            text=sentence,
            pitch="+3Hz",
            rate="-1%",
            sentence_type="question",
            pause_after_ms=220,
        )
    elif category == "empathy":
        # Gentle, caring, warm tone (-1Hz, calm tempo)
        return SentenceProsody(
            text=sentence,
            pitch="-1Hz",
            rate="-2%",
            sentence_type="empathy",
            pause_after_ms=200,
        )
    elif category == "confirmation":
        # Crisp, reassuring, responsive (+1Hz, brisk)
        return SentenceProsody(
            text=sentence,
            pitch="+1Hz",
            rate="+2%",
            sentence_type="confirmation",
            pause_after_ms=150,
        )
    else:
        # Balanced statement with subtle natural baseline (+0Hz)
        return SentenceProsody(
            text=sentence,
            pitch="+0Hz",
            rate="+0%",
            sentence_type="statement",
            pause_after_ms=180,
        )


def split_into_conversational_chunks(text: str) -> List[str]:
    """
    Splits text into naturally spoken sentences or major conversational clauses.
    Preserves question marks and sentence boundaries.
    """
    if not text:
        return []

    # Split by full stops or question marks
    raw_chunks = re.split(r"(?<=[.?])\s+", text)
    chunks = []
    for c in raw_chunks:
        clean_c = c.strip()
        if clean_c:
            chunks.append(clean_c)

    return chunks if chunks else [text]


def prepare_prosody_plan(text: str) -> List[SentenceProsody]:
    """
    Takes raw dialogue text, normalizes it, and builds a sentence-by-sentence
    prosody plan with dynamic human intonation parameters.
    """
    cleaned = normalize_hinglish_speech_text(text)
    if not cleaned:
        return []

    chunks = split_into_conversational_chunks(cleaned)
    total = len(chunks)
    plan = []

    for idx, chunk in enumerate(chunks):
        is_first = (idx == 0)
        is_last = (idx == total - 1)
        prosody = get_sentence_prosody(chunk, is_first=is_first, is_last=is_last)
        plan.append(prosody)

    return plan
