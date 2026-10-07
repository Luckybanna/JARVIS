"""
Speech-to-Text (STT) Engine for JARVIS.
Provides provider abstraction supporting Hindi, English, and Hinglish transcription.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import io
import time
from typing import Optional

from app.core.config import Settings, get_settings
from app.core.logger import get_logger

logger = get_logger("voice.stt")


@dataclass
class STTResult:
    """Result of speech-to-text transcription."""
    text: str
    language: str = "auto"
    confidence: float = 1.0
    latency_ms: float = 0.0
    error: Optional[str] = None


class STTProvider(ABC):
    """Abstract interface for speech-to-text engines."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def transcribe(
        self,
        wav_bytes: bytes,
        language_hint: Optional[str] = None,
    ) -> STTResult:
        """Converts WAV audio bytes to text."""
        pass


class WhisperSTTProvider(STTProvider):
    """OpenAI Whisper API transcription engine."""

    def __init__(self, api_key: str, model_name: str = "whisper-1"):
        self.api_key = api_key.strip() if api_key else ""
        self.model_name = model_name

    @property
    def provider_name(self) -> str:
        return "whisper"

    def transcribe(
        self,
        wav_bytes: bytes,
        language_hint: Optional[str] = None,
    ) -> STTResult:
        if not self.api_key:
            return STTResult(
                text="",
                error="OPENAI_API_KEY is not set for Whisper STT",
            )

        if not wav_bytes:
            return STTResult(text="", error="Empty audio bytes provided")

        start_time = time.perf_counter()
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            # Package in-memory bytes into a named buffer for the API
            audio_file = io.BytesIO(wav_bytes)
            audio_file.name = "speech.wav"

            prompt_hint = "Jarvis Hindi Hinglish English conversation, colloquial words"
            resp = client.audio.transcriptions.create(
                model=self.model_name,
                file=audio_file,
                prompt=prompt_hint,
                language=language_hint if language_hint in ("hi", "en") else None,
            )

            latency = (time.perf_counter() - start_time) * 1000.0
            text = resp.text.strip() if hasattr(resp, "text") else ""

            return STTResult(
                text=text,
                language=language_hint or "auto",
                confidence=0.95,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Whisper STT transcription failed: {e}")
            return STTResult(
                text="",
                latency_ms=latency,
                error=str(e),
            )


class GeminiSTTProvider(STTProvider):
    """Gemini Multimodal Audio transcription engine."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key.strip() if api_key else ""
        self.model_name = model_name

    @property
    def provider_name(self) -> str:
        return "gemini_audio"

    def transcribe(
        self,
        wav_bytes: bytes,
        language_hint: Optional[str] = None,
    ) -> STTResult:
        if not self.api_key:
            return STTResult(
                text="",
                error="GEMINI_API_KEY is not set for Gemini Audio STT",
            )

        if not wav_bytes:
            return STTResult(text="", error="Empty audio bytes provided")

        start_time = time.perf_counter()
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)

            model = genai.GenerativeModel(model_name=self.model_name)

            prompt = (
                "Transcribe the spoken audio faithfully and verbatim. "
                "If the speaker uses Hindi, English, or mixed Hinglish (e.g. 'Jarvis aaj mujhe Kota jana hai'), "
                "preserve the exact words. Output ONLY the transcription text, nothing else."
            )

            audio_part = {
                "mime_type": "audio/wav",
                "data": wav_bytes,
            }

            response = model.generate_content([prompt, audio_part])
            latency = (time.perf_counter() - start_time) * 1000.0

            transcription = response.text.strip() if response and hasattr(response, "text") else ""

            return STTResult(
                text=transcription,
                language=language_hint or "auto",
                confidence=0.92,
                latency_ms=latency,
            )

        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Gemini Audio STT failed: {e}")
            return STTResult(
                text="",
                latency_ms=latency,
                error=str(e),
            )


class MockSTTProvider(STTProvider):
    """Deterministic mock STT provider for tests and offline simulation."""

    def __init__(self, fixed_text: str = "Jarvis aaj mujhe Kota jana hai"):
        self.fixed_text = fixed_text

    @property
    def provider_name(self) -> str:
        return "mock"

    def transcribe(
        self,
        wav_bytes: bytes,
        language_hint: Optional[str] = None,
    ) -> STTResult:
        if not wav_bytes:
            return STTResult(text="", error="Empty audio bytes")
        return STTResult(
            text=self.fixed_text,
            language="hinglish",
            confidence=1.0,
            latency_ms=10.0,
        )


def create_stt_provider(settings: Optional[Settings] = None) -> STTProvider:
    """Instantiates STT provider according to available keys and settings."""
    cfg = settings or get_settings()

    # Prioritize based on available configured keys
    if cfg.ai_provider == "gemini" and cfg.gemini_api_key:
        logger.info("Using Gemini Multimodal STT provider")
        return GeminiSTTProvider(api_key=cfg.gemini_api_key, model_name=cfg.gemini_model)
    elif cfg.openai_api_key:
        logger.info("Using Whisper STT provider")
        return WhisperSTTProvider(api_key=cfg.openai_api_key)
    elif cfg.gemini_api_key:
        logger.info("Using Gemini Multimodal STT provider")
        return GeminiSTTProvider(api_key=cfg.gemini_api_key, model_name=cfg.gemini_model)
    else:
        logger.warning("No STT cloud API key found. Using mock fallback.")
        return MockSTTProvider()
