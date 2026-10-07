"""
Unit and integration tests for the Voice subsystem (Capture, VAD, STT, TTS, Interruption).
"""

import io
import threading
import time
import wave
import numpy as np
import pytest

from app.core.events import Event, EventBus, EventType
from app.voice.audio_capture import AudioCapture, AudioUtterance
from app.voice.stt_engine import (
    MockSTTProvider,
    WhisperSTTProvider,
    GeminiSTTProvider,
    STTResult,
)
from app.voice.tts_engine import (
    EdgeTTSProvider,
    MockTTSProvider,
    SAPIProvider,
    detect_language_hint,
)
from app.voice.voice_manager import VoiceManager
from app.core.conversation import ConversationManager
from app.ai.base import AIProvider, AIResponse, ChatMessage, TokenUsage


class EchoAIProvider(AIProvider):
    def __init__(self, model_name: str = "echo-v1"):
        super().__init__(model_name=model_name)

    @property
    def provider_name(self) -> str:
        return "echo"

    def generate(self, messages, **kwargs):
        last_msg = messages[-1].content
        return AIResponse(
            content=f"Jarvis says: {last_msg}",
            model="echo-v1",
            usage=TokenUsage(1, 1, 2),
            latency_ms=10.0,
        )

    def stream(self, messages, **kwargs):
        yield "echo"

    def health_check(self):
        return True, "Echo OK"


def test_audio_capture_rms_and_wav_encoding():
    capture = AudioCapture(sample_rate=16000)

    # Pure silence
    silence = np.zeros(1024, dtype=np.int16)
    assert capture._calculate_rms(silence) == 0.0

    # Loud sine wave
    t = np.linspace(0, 1, 16000)
    sine = (np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16)
    rms_sine = capture._calculate_rms(sine)
    assert rms_sine > 5000.0

    # Encode to WAV bytes
    wav_bytes = capture._numpy_to_wav(sine, 16000)
    assert len(wav_bytes) > 44
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"

    # Verify wave can read back properties
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000


def test_stt_providers():
    mock_stt = MockSTTProvider("Jarvis aaj mujhe Kota jana hai")
    res = mock_stt.transcribe(b"DUMMY_WAV_BYTES")
    assert res.text == "Jarvis aaj mujhe Kota jana hai"
    assert res.error is None

    # Empty bytes test
    empty_res = mock_stt.transcribe(b"")
    assert empty_res.error == "Empty audio bytes"

    # Missing API keys
    whisper_no_key = WhisperSTTProvider(api_key="")
    w_res = whisper_no_key.transcribe(b"bytes")
    assert "OPENAI_API_KEY is not set" in w_res.error

    gemini_no_key = GeminiSTTProvider(api_key="")
    g_res = gemini_no_key.transcribe(b"bytes")
    assert "GEMINI_API_KEY is not set" in g_res.error


def test_language_detection_heuristic():
    # Romanized Hindi / Hinglish
    assert detect_language_hint("Jarvis aaj mujhe Kota jana hai") == "hi"
    assert detect_language_hint("Aap kaise ho bhai") == "hi"

    # Devanagari script
    assert detect_language_hint("नमस्ते जार्विस, आप कैसे हैं?") == "hi"

    # English
    assert detect_language_hint("Jarvis, what is the current system memory status?") == "en"
    assert detect_language_hint("Please open my browser and search for news.") == "en"


def test_edge_tts_voice_selection():
    edge_provider = EdgeTTSProvider(
        hindi_voice="hi-IN-MadhurNeural",
        english_voice="en-US-GuyNeural",
    )
    assert edge_provider.select_voice_for_text("नमस्ते जार्विस") == "hi-IN-MadhurNeural"
    assert edge_provider.select_voice_for_text("Aap kaise ho") == "hi-IN-MadhurNeural"
    assert edge_provider.select_voice_for_text("Hello Jarvis, open Chrome") == "en-US-GuyNeural"


def test_mock_tts_speak_and_interruption():
    bus = EventBus()
    events = []
    bus.subscribe_all(lambda e: events.append(e.event_type))

    tts = MockTTSProvider(event_bus=bus)

    # Normal speech
    finished = tts.speak("Test speech")
    assert finished is True
    assert "Test speech" in tts.spoken_texts
    assert EventType.TTS_SPEAKING_START in events
    assert EventType.TTS_SPEAKING_STOP in events

    # Interrupted speech
    interrupt_flag = threading.Event()
    interrupt_flag.set()
    finished = tts.speak("Interrupted speech", interrupt_flag=interrupt_flag)
    assert finished is False
    assert EventType.TTS_INTERRUPTED in events


def test_voice_manager_pipeline_execution():
    bus = EventBus()
    events = []
    bus.subscribe_all(lambda e: events.append(e.event_type))

    conv_manager = ConversationManager(provider=EchoAIProvider(), event_bus=bus)
    mock_stt = MockSTTProvider("Jarvis kal ka schedule kya hai?")
    mock_tts = MockTTSProvider(event_bus=bus)

    voice_manager = VoiceManager(
        conversation_manager=conv_manager,
        stt_provider=mock_stt,
        tts_provider=mock_tts,
        event_bus=bus,
    )

    utterance = AudioUtterance(
        wav_bytes=b"RIFF_FAKE_WAV",
        duration_seconds=1.5,
        sample_rate=16000,
        channels=1,
        rms_peak=1500.0,
    )

    # Process utterance directly (synchronously)
    voice_manager._process_utterance_pipeline(utterance)

    # Check STT resulted in user voice event
    assert EventType.USER_INPUT_VOICE in events
    # Check conversation manager processed response
    assert EventType.JARVIS_RESPONSE_COMPLETE in events
    # Check TTS spoke response
    assert len(mock_tts.spoken_texts) == 1
    assert "Jarvis says: Jarvis kal ka schedule kya hai?" in mock_tts.spoken_texts[0]


def test_voice_manager_barge_in_interruption():
    bus = EventBus()
    tts = MockTTSProvider(event_bus=bus)
    voice_manager = VoiceManager(tts_provider=tts, event_bus=bus)

    # Simulate TTS currently speaking
    tts._is_speaking = True
    assert voice_manager.is_speaking is True

    # User speaks -> SPEECH_DETECTED fired
    bus.publish(Event(event_type=EventType.SPEECH_DETECTED, data={"rms": 800}))

    # Barge-in handler should have called tts.stop()
    assert tts._stop_event.is_set()
