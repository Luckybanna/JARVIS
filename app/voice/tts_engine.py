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
            logger.info("Windows SAPI voice initialized")
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

        clean_text = text.strip()
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
        hindi_voice: Optional[str] = None,
        english_voice: Optional[str] = None,
        event_bus: Optional[EventBus] = None,
    ):
        super().__init__(event_bus=event_bus)
        settings = get_settings()
        self.hindi_voice = hindi_voice or settings.edge_tts_voice_hindi
        self.english_voice = english_voice or settings.edge_tts_voice_english
        self.cache_dir = DATA_DIR / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sapi_fallback = SAPIProvider(event_bus=self.event_bus) if settings.sapi_fallback_enabled else None

    @property
    def provider_name(self) -> str:
        return "edge_tts"

    def select_voice_for_text(self, text: str) -> str:
        """Selects appropriate neural voice based on language and script."""
        lang = detect_language_hint(text)
        if lang == "hi":
            return self.hindi_voice
        return self.english_voice

    def synthesize_to_bytes(
        self,
        text: str,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
    ) -> bytes:
        """Asynchronously synthesizes speech using edge-tts and gathers MP3 bytes."""
        import edge_tts

        selected_voice = voice or self.select_voice_for_text(text)
        selected_rate = rate or "+0%"

        async def _synthesize():
            communicate = edge_tts.Communicate(
                text=text,
                voice=selected_voice,
                rate=selected_rate,
            )
            data = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    data.extend(chunk["data"])
            return bytes(data)

        try:
            return asyncio.run(_synthesize())
        except Exception as e:
            logger.error(f"EdgeTTS synthesis error: {e}")
            return b""

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
        clean_text = text.strip()
        if not clean_text:
            return True

        selected_voice = voice or self.select_voice_for_text(clean_text)
        logger.info(f"Synthesizing speech with voice: {selected_voice}")

        audio_bytes = self.synthesize_to_bytes(clean_text, voice=selected_voice, rate=rate)

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

        # Play using WMPlayer.OCX
        try:
            import win32com.client
            wmp = win32com.client.Dispatch("WMPlayer.OCX")
            media = wmp.newMedia(str(temp_audio_file.resolve()))
            wmp.currentMedia = media
            wmp.controls.play()

            # Poll for playback completion or interruption
            # playState: 3 = Playing, 1 = Stopped, 8 = MediaEnded, 10 = Ready
            while True:
                if self._stop_event.is_set() or (interrupt_flag and interrupt_flag.is_set()):
                    wmp.controls.stop()
                    logger.info("EdgeTTS playback interrupted")
                    self.event_bus.publish(
                        Event(
                            event_type=EventType.TTS_INTERRUPTED,
                            source="tts",
                        )
                    )
                    return False

                state = wmp.playState
                # Once started (state 3), if it transitions to 1 (Stopped) or 8 (MediaEnded), we are done
                if state in (1, 8):
                    break
                time.sleep(0.05)

            return True

        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            if self.sapi_fallback:
                return self.sapi_fallback.speak(clean_text, interrupt_flag=interrupt_flag)
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
