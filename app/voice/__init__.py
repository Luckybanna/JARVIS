"""
Voice processing subsystem for JARVIS: audio capture, VAD, STT, TTS, and session management.
"""

from app.voice.audio_capture import AudioCapture, AudioUtterance
from app.voice.stt_engine import STTProvider, STTResult, create_stt_provider
from app.voice.tts_engine import TTSProvider, EdgeTTSProvider, SAPIProvider, create_tts_provider
from app.voice.voice_manager import VoiceManager

__all__ = [
    "AudioCapture",
    "AudioUtterance",
    "STTProvider",
    "STTResult",
    "create_stt_provider",
    "TTSProvider",
    "EdgeTTSProvider",
    "SAPIProvider",
    "create_tts_provider",
    "VoiceManager",
]
