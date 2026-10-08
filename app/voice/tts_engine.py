"""
Text-to-Speech (TTS) Engine for JARVIS.
Features natural Microsoft Edge Neural TTS with Hindi/Hinglish/English voice adaptation,
Windows SAPI offline fallback, and real-time interruption handling.
"""

from abc import ABC, abstractmethod
import asyncio
from pathlib import Path
import re
import threading
import time
from typing import Optional

from app.core.config import DATA_DIR, Settings, get_settings
from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.language import detect_language_hint, HINGLISH_KEYWORDS
from app.core.logger import get_logger

logger = get_logger("voice.tts")


def clean_text_for_tts(text: str) -> str:
    """Strips markdown syntax, emojis, and normalizes speech using the unified prosody engine."""
    if not text:
        return ""
    from app.voice.prosody import normalize_hinglish_speech_text
    return normalize_hinglish_speech_text(text)


class TTSProvider(ABC):
    """Abstract interface for text-to-speech providers."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus or get_event_bus()
        self._is_speaking = False
        self._stop_event = threading.Event()

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def stop(self) -> None:
        """Signals active speech to halt immediately."""
        self._stop_event.set()

    @abstractmethod
    def synthesize_to_bytes(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
    ) -> bytes:
        """Synthesizes speech to audio bytes."""
        pass

    @abstractmethod
    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        interrupt_flag: Optional[threading.Event] = None,
    ) -> bool:
        """Speaks text aloud with interruption support. Returns True if finished, False if interrupted."""
        pass


class SAPIProvider(TTSProvider):
    """Offline Windows SAPI Text-to-Speech fallback provider."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        super().__init__(event_bus=event_bus)
        self._voice_engine = None
        self._init_engine()

    @property
    def provider_name(self) -> str:
        return "sapi"

    def _init_engine(self) -> None:
        try:
            import win32com.client
            self._voice_engine = win32com.client.Dispatch("SAPI.SpVoice")
            # Strictly select female voice (Zira/Kalpana/Heera), NEVER male voice (David)
            for v in self._voice_engine.GetVoices():
                desc = v.GetDescription().lower()
                if any(kw in desc for kw in ["zira", "female", "heera", "kalpana", "harita"]):
                    self._voice_engine.Voice = v
                    logger.info(f"SAPI voice set to female: {v.GetDescription()}")
                    break
            logger.info("Windows SAPI female voice initialized")
        except Exception as e:
            logger.error(f"Failed to initialize SAPI: {e}")
            self._voice_engine = None

    def synthesize_to_bytes(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
    ) -> bytes:
        return b""

    def stop(self) -> None:
        super().stop()
        if self._voice_engine:
            try:
                # Flag 2 = SVSFPurgeBeforeSpeak, immediately terminates current speech
                self._voice_engine.Speak("", 2)
            except Exception as e:
                logger.debug(f"Error purging SAPI: {e}")

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        interrupt_flag: Optional[threading.Event] = None,
    ) -> bool:
        if not self._voice_engine:
            self._init_engine()
        if not self._voice_engine:
            return False

        clean_text = clean_text_for_tts(text)
        if not clean_text:
            return True

        self._stop_event.clear()
        self._is_speaking = True
        self.event_bus.publish(
            Event(
                event_type=EventType.TTS_SPEAKING_START,
                data={"text": clean_text, "provider": "sapi"},
                source="tts",
            )
        )

        try:
            # 1 = SVSFlagsAsync
            self._voice_engine.Speak(clean_text, 1)

            # Monitor completion or interruption
            while True:
                if self._stop_event.is_set() or (interrupt_flag and interrupt_flag.is_set()):
                    self._voice_engine.Speak("", 2)
                    logger.info("SAPI speech interrupted")
                    self.event_bus.publish(
                        Event(
                            event_type=EventType.TTS_INTERRUPTED,
                            source="tts",
                        )
                    )
                    return False

                # SAPI SpVoice.Status: RunningState 1 = Done, 2 = Reading
                status = getattr(self._voice_engine, "Status", None)
                if status and status.RunningState == 1:
                    break
                time.sleep(0.05)

            return True

        except Exception as e:
            logger.error(f"SAPI speak error: {e}")
            return False
        finally:
            self._is_speaking = False
            self.event_bus.publish(
                Event(
                    event_type=EventType.TTS_SPEAKING_STOP,
                    source="tts",
                )
            )


class EdgeTTSProvider(TTSProvider):
    """High quality Microsoft Edge Neural Text-to-Speech provider."""

    def __init__(
        self,
        hindi_voice: Optional[str] = "en-US-AvaMultilingualNeural",
        english_voice: Optional[str] = "en-US-AvaMultilingualNeural",
        event_bus: Optional[EventBus] = None,
    ):
        super().__init__(event_bus=event_bus)
        settings = get_settings()
        self.hindi_voice = hindi_voice or settings.edge_tts_voice_hindi or "en-US-AvaMultilingualNeural"
        self.english_voice = english_voice or settings.edge_tts_voice_english or "en-US-AvaMultilingualNeural"
        self.speech_rate = settings.speech_rate or "+0%"
        self.cache_dir = DATA_DIR / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sapi_fallback = None  # Strictly disabled to prevent any dual voice / male voice overlap

    @property
    def provider_name(self) -> str:
        return "edge_tts"

    def select_voice_for_text(self, text: str) -> str:
        """Selects appropriate neural voice based on language and script."""
        lang = detect_language_hint(text)
        if lang == "hi":
            return self.hindi_voice
        return self.english_voice

    def get_locale_for_text(self, text: str) -> str:
        """Returns target SSML xml:lang locale ('hi-IN' for Hindi/Hinglish, 'en-US' for English)."""
        words = re.findall(r"\b[a-zA-Z]+\b", text.lower())
        non_sir_words = [w for w in words if w != "sir"]
        if non_sir_words:
            lang = detect_language_hint(" ".join(non_sir_words))
        else:
            lang = detect_language_hint(text)
        return "hi-IN" if lang == "hi" else "en-US"

    def synthesize_to_bytes(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        locale: Optional[str] = None,
    ) -> bytes:
        """Asynchronously synthesizes speech using edge-tts with dynamic locale handling."""
        import edge_tts
        import edge_tts.communicate

        selected_voice = voice or self.select_voice_for_text(text)
        selected_rate = rate or self.speech_rate or "+0%"
        selected_pitch = pitch or "+0Hz"
        target_locale = locale or self.get_locale_for_text(text)

        logger.info(
            f"[TTS] Synthesizing speech with voice: {selected_voice} | "
            f"Locale: {target_locale} | Rate: {selected_rate} | Pitch: {selected_pitch}"
        )

        def _custom_mkssml(tc_obj, escaped_text):
            if isinstance(escaped_text, bytes):
                raw_t = escaped_text.decode("utf-8")
            else:
                raw_t = str(escaped_text)
            return (
                f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{target_locale}'>"
                f"<voice name='{tc_obj.voice}'>"
                f"<prosody pitch='{tc_obj.pitch}' rate='{tc_obj.rate}' volume='{tc_obj.volume}'>"
                f"{raw_t}"
                "</prosody>"
                "</voice>"
                "</speak>"
            )

        async def _synthesize():
            orig_mkssml = edge_tts.communicate.mkssml
            edge_tts.communicate.mkssml = _custom_mkssml
            try:
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=selected_voice,
                    rate=selected_rate,
                    pitch=selected_pitch,
                )
                data = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        data.extend(chunk["data"])
                return bytes(data)
            finally:
                edge_tts.communicate.mkssml = orig_mkssml

        try:
            return asyncio.run(_synthesize())
        except Exception as e:
            logger.error(f"EdgeTTS synthesis error: {e}")
            return b""

    def synthesize_with_prosody(
        self,
        text: str,
        voice: Optional[str] = None,
    ) -> bytes:
        """
        Synthesizes speech using the conversational prosody plan.
        Varies pitch and rate per sentence for lifelike human intonation.
        Uses single-pass for coherent statements to maintain neural cross-sentence flow,
        and concurrent parallel requests for diverse pitch profiles to minimize latency.
        """
        from app.voice.prosody import prepare_prosody_plan
        plan = prepare_prosody_plan(text)
        if not plan:
            return b""

        selected_voice = voice or self.select_voice_for_text(text)

        # Single short sentence
        if len(plan) == 1:
            item = plan[0]
            return self.synthesize_to_bytes(
                item.text,
                voice=selected_voice,
                rate=item.rate,
                pitch=item.pitch,
            )

        # Check if all sentences share identical pitch and rate
        distinct_pitches = {item.pitch for item in plan}
        distinct_rates = {item.rate for item in plan}
        if len(distinct_pitches) == 1 and len(distinct_rates) == 1:
            # Single-pass: preserves natural cross-sentence neural attention and breath flow
            full_text = " ".join(item.text for item in plan)
            return self.synthesize_to_bytes(
                full_text,
                voice=selected_voice,
                rate=plan[0].rate,
                pitch=plan[0].pitch,
            )

        # Diverse prosody profile: synthesize in parallel using asyncio.gather for low latency
        import edge_tts
        import edge_tts.communicate

        async def _synth_chunk(item):
            chunk_locale = self.get_locale_for_text(item.text)
            def _chunk_mkssml(tc_obj, escaped_text):
                if isinstance(escaped_text, bytes):
                    raw_t = escaped_text.decode("utf-8")
                else:
                    raw_t = str(escaped_text)
                return (
                    f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{chunk_locale}'>"
                    f"<voice name='{tc_obj.voice}'>"
                    f"<prosody pitch='{tc_obj.pitch}' rate='{tc_obj.rate}' volume='{tc_obj.volume}'>"
                    f"{raw_t}"
                    "</prosody>"
                    "</voice>"
                    "</speak>"
                )

            orig_mkssml = edge_tts.communicate.mkssml
            edge_tts.communicate.mkssml = _chunk_mkssml
            try:
                communicate = edge_tts.Communicate(
                    text=item.text,
                    voice=selected_voice,
                    rate=item.rate,
                    pitch=item.pitch,
                )
                data = bytearray()
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        data.extend(chunk["data"])
                return bytes(data)
            finally:
                edge_tts.communicate.mkssml = orig_mkssml

        async def _synth_all():
            return await asyncio.gather(*(_synth_chunk(item) for item in plan))

        try:
            chunks = asyncio.run(_synth_all())
            combined_audio = bytearray()
            for chunk in chunks:
                if chunk:
                    combined_audio.extend(chunk)
            return bytes(combined_audio)
        except Exception as e:
            logger.error(f"Parallel EdgeTTS synthesis error: {e}")
            # Fallback to sequential synthesis
            combined_audio = bytearray()
            for item in plan:
                if self._stop_event.is_set():
                    break
                chunk_bytes = self.synthesize_to_bytes(
                    item.text,
                    voice=selected_voice,
                    rate=item.rate,
                    pitch=item.pitch,
                )
                if chunk_bytes:
                    combined_audio.extend(chunk_bytes)
            return bytes(combined_audio)

    def stop(self) -> None:
        super().stop()
        if self.sapi_fallback:
            self.sapi_fallback.stop()

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        interrupt_flag: Optional[threading.Event] = None,
    ) -> bool:
        from app.voice.prosody import normalize_hinglish_speech_text
        clean_text = normalize_hinglish_speech_text(text)
        if not clean_text:
            return True

        selected_voice = voice or self.select_voice_for_text(clean_text)
        logger.info(f"Synthesizing natural conversational speech with voice: {selected_voice}")

        audio_bytes = self.synthesize_with_prosody(clean_text, voice=selected_voice)

        # Fallback to SAPI if edge-tts fails (e.g. offline)
        if not audio_bytes:
            if self.sapi_fallback:
                logger.warning("EdgeTTS failed or offline. Falling back to Windows SAPI.")
                return self.sapi_fallback.speak(clean_text, interrupt_flag=interrupt_flag)
            return False

        # Save to temporary cache file
        temp_audio_file = self.cache_dir / f"tts_output_{int(time.time() * 1000)}.mp3"
        try:
            temp_audio_file.write_bytes(audio_bytes)
        except Exception as e:
            logger.error(f"Error saving temp audio file: {e}")
            return False

        self._stop_event.clear()
        self._is_speaking = True
        self.event_bus.publish(
            Event(
                event_type=EventType.TTS_SPEAKING_START,
                data={"text": clean_text, "voice": selected_voice, "provider": "edge_tts"},
                source="tts",
            )
        )

        # Play using Windows native Multimedia MCI (winmm.dll)
        try:
            import ctypes
            winmm = ctypes.windll.winmm
            alias = f"tts_{int(time.time() * 1000)}"
            winmm.mciSendStringW(f'open "{temp_audio_file.resolve()}" type mpegvideo alias {alias}', None, 0, None)
            winmm.mciSendStringW(f'play {alias}', None, 0, None)

            buf = ctypes.create_unicode_buffer(64)
            while True:
                if self._stop_event.is_set() or (interrupt_flag and interrupt_flag.is_set()):
                    winmm.mciSendStringW(f'stop {alias}', None, 0, None)
                    winmm.mciSendStringW(f'close {alias}', None, 0, None)
                    logger.info("EdgeTTS playback interrupted")
                    self.event_bus.publish(
                        Event(
                            event_type=EventType.TTS_INTERRUPTED,
                            source="tts",
                        )
                    )
                    return False

                winmm.mciSendStringW(f'status {alias} mode', buf, 64, None)
                if buf.value != "playing":
                    break
                time.sleep(0.04)

            winmm.mciSendStringW(f'close {alias}', None, 0, None)
            return True

        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            return False

        finally:
            self._is_speaking = False
            self.event_bus.publish(
                Event(
                    event_type=EventType.TTS_SPEAKING_STOP,
                    source="tts",
                )
            )
            # Cleanup temp file
            try:
                if temp_audio_file.exists():
                    temp_audio_file.unlink(missing_ok=True)
            except Exception:
                pass


class MockTTSProvider(TTSProvider):
    """Deterministic Mock TTS Provider for automated tests without audio hardware."""

    def __init__(self, event_bus: Optional[EventBus] = None):
        super().__init__(event_bus=event_bus)
        self.spoken_texts = []

    @property
    def provider_name(self) -> str:
        return "mock"

    def synthesize_to_bytes(self, text: str, voice: Optional[str] = None, rate: Optional[str] = None) -> bytes:
        return b"MOCK_AUDIO_BYTES"

    def speak(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        interrupt_flag: Optional[threading.Event] = None,
    ) -> bool:
        self.spoken_texts.append(text)
        self._is_speaking = True
        self.event_bus.publish(
            Event(
                event_type=EventType.TTS_SPEAKING_START,
                data={"text": text, "provider": "mock"},
                source="tts",
            )
        )
        if interrupt_flag and interrupt_flag.is_set():
            self._is_speaking = False
            self.event_bus.publish(Event(event_type=EventType.TTS_INTERRUPTED, source="tts"))
            return False

        self._is_speaking = False
        self.event_bus.publish(Event(event_type=EventType.TTS_SPEAKING_STOP, source="tts"))
        return True


def create_tts_provider(settings: Optional[Settings] = None, event_bus: Optional[EventBus] = None) -> TTSProvider:
    """Instantiates the configured TTS provider."""
    cfg = settings or get_settings()
    if cfg.tts_provider == "edge_tts":
        return EdgeTTSProvider(
            hindi_voice=cfg.edge_tts_voice_hindi,
            english_voice=cfg.edge_tts_voice_english,
            event_bus=event_bus,
        )
    elif cfg.tts_provider == "sapi":
        return SAPIProvider(event_bus=event_bus)
    else:
        return EdgeTTSProvider(event_bus=event_bus)
