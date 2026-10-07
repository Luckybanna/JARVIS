"""
Voice Session Orchestrator for JARVIS.
Integrates Audio Capture, STT, Conversation Brain, and TTS with barge-in interruption.
"""

import threading
import time
from typing import Callable, Optional

from app.core.config import Settings, get_settings
from app.core.conversation import ConversationManager
from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.logger import get_logger
from app.voice.audio_capture import AudioCapture, AudioUtterance
from app.voice.stt_engine import STTProvider, create_stt_provider
from app.voice.tts_engine import TTSProvider, create_tts_provider

logger = get_logger("voice.manager")


class VoiceManager:
    """Coordinates voice interaction cycle and interruptions."""

    def __init__(
        self,
        conversation_manager: Optional[ConversationManager] = None,
        audio_capture: Optional[AudioCapture] = None,
        stt_provider: Optional[STTProvider] = None,
        tts_provider: Optional[TTSProvider] = None,
        event_bus: Optional[EventBus] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings: Settings = settings or get_settings()
        self.event_bus: EventBus = event_bus or get_event_bus()
        self.conversation_manager: ConversationManager = (
            conversation_manager or ConversationManager(event_bus=self.event_bus)
        )
        self.stt: STTProvider = stt_provider or create_stt_provider(self.settings)
        self.tts: TTSProvider = tts_provider or create_tts_provider(self.settings, event_bus=self.event_bus)
        self.audio_capture: AudioCapture = audio_capture or AudioCapture(event_bus=self.event_bus)

        # Wire audio capture callback
        self.audio_capture.set_on_utterance_callback(self._on_utterance_captured)

        # Wire speech detected event for barge-in / interruption
        self.event_bus.subscribe(EventType.SPEECH_DETECTED, self._on_user_speech_detected)

        self._processing_lock = threading.Lock()
        self._is_active = False

    def _on_user_speech_detected(self, event: Event) -> None:
        """Barge-in: If user speaks while assistant is speaking, interrupt TTS immediately."""
        if self.tts.is_speaking:
            logger.info("User interruption detected. Halting assistant speech.")
            self.tts.stop()

    def _on_utterance_captured(self, utterance: AudioUtterance) -> None:
        """Handles a completed speech phrase in a background thread."""
        threading.Thread(
            target=self._process_utterance_pipeline,
            args=(utterance,),
            daemon=True,
            name="VoicePipelineWorker",
        ).start()

    def _process_utterance_pipeline(self, utterance: AudioUtterance) -> None:
        """Pipeline: WAV audio -> STT -> ConversationManager -> TTS speech."""
        with self._processing_lock:
            # Step 1: Speech-to-Text
            logger.info(f"Transcribing audio ({utterance.duration_seconds:.2f}s)...")
            stt_result = self.stt.transcribe(utterance.wav_bytes)

            if stt_result.error:
                logger.error(f"STT Error: {stt_result.error}")
                self.event_bus.publish(
                    Event(
                        event_type=EventType.ERROR_OCCURRED,
                        data={"module": "stt", "error": stt_result.error},
                        source="voice_manager",
                    )
                )
                return

            user_text = stt_result.text.strip()
            if not user_text:
                logger.debug("STT returned empty transcription.")
                return

            logger.info(f"User Spoke: '{user_text}'")
            self.event_bus.publish(
                Event(
                    event_type=EventType.USER_INPUT_VOICE,
                    data={"text": user_text, "latency_ms": stt_result.latency_ms},
                    source="voice_manager",
                )
            )

            # Step 2: Conversation Manager
            response = self.conversation_manager.send_user_message(user_text)

            if response.error:
                logger.warning(f"AI response error: {response.error}")
                # Speak error notice if appropriate
                if response.content:
                    self.tts.speak(response.content)
                return

            # Step 3: Text-to-Speech
            if response.content:
                logger.info(f"Speaking response: '{response.content[:60]}...'")
                self.tts.speak(response.content)

    def start_listening(self) -> bool:
        """Starts continuous microphone listening."""
        self._is_active = True
        return self.audio_capture.start()

    def stop_listening(self) -> None:
        """Stops microphone listening and halts any ongoing speech."""
        self._is_active = False
        self.audio_capture.stop()
        self.tts.stop()

    def speak_manual(self, text: str) -> bool:
        """Speaks arbitrary text directly through the active TTS provider."""
        return self.tts.speak(text)

    @property
    def is_listening(self) -> bool:
        return self.audio_capture.is_listening

    @property
    def is_speaking(self) -> bool:
        return self.tts.is_speaking
