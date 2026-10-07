"""
Microphone Audio Capture and Real-time Voice Activity Detection (VAD) for JARVIS.
Captures mono PCM audio, segments utterances by silence detection, and outputs WAV bytes.
"""

from dataclasses import dataclass
import io
import math
import struct
import threading
import time
from typing import Callable, List, Optional
import wave

import numpy as np
import sounddevice as sd

from app.core.config import get_settings
from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.logger import get_logger

logger = get_logger("voice.capture")


@dataclass
class AudioUtterance:
    """Represents a captured spoken phrase with metadata."""
    wav_bytes: bytes
    duration_seconds: float
    sample_rate: int
    channels: int
    rms_peak: float


class AudioCapture:
    """Background microphone recorder with real-time energy-based VAD."""

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        energy_threshold: Optional[int] = None,
        silence_timeout: Optional[float] = None,
        min_speech_duration: float = 0.5,
        max_utterance_duration: float = 15.0,
        event_bus: Optional[EventBus] = None,
        device_index: Optional[int] = None,
    ):
        settings = get_settings()
        self.sample_rate = sample_rate
        self.channels = channels
        self.energy_threshold = energy_threshold or settings.mic_energy_threshold
        self.silence_timeout = silence_timeout or settings.mic_silence_timeout_seconds
        self.min_speech_duration = min_speech_duration
        self.max_utterance_duration = max_utterance_duration
        self.device_index = device_index
        self.event_bus = event_bus or get_event_bus()

        self._stream: Optional[sd.InputStream] = None
        self._running = False
        self._lock = threading.Lock()

        # State machine
        self._is_speaking = False
        self._speech_buffer: List[np.ndarray] = []
        self._silence_start_time: Optional[float] = None
        self._utterance_start_time: Optional[float] = None
        self._on_utterance_callback: Optional[Callable[[AudioUtterance], None]] = None

    @staticmethod
    def list_input_devices() -> List[dict]:
        """Lists available audio recording devices."""
        devices = []
        try:
            device_list = sd.query_devices()
            for idx, dev in enumerate(device_list):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append({
                        "index": idx,
                        "name": dev.get("name"),
                        "channels": dev.get("max_input_channels"),
                        "default_samplerate": dev.get("default_samplerate"),
                    })
        except Exception as e:
            logger.error(f"Error listing audio devices: {e}")
        return devices

    def set_on_utterance_callback(self, callback: Callable[[AudioUtterance], None]) -> None:
        """Sets the listener callback invoked when a speech utterance finishes."""
        self._on_utterance_callback = callback

    def _calculate_rms(self, block: np.ndarray) -> float:
        """Calculates Root-Mean-Square energy of an audio buffer."""
        if len(block) == 0:
            return 0.0
        # Convert to float64 to avoid overflow
        block_f = block.astype(np.float64)
        mean_sq = np.mean(block_f ** 2)
        return float(np.sqrt(mean_sq))

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        """Invoked by sounddevice in high-priority audio thread."""
        if status:
            logger.debug(f"Audio stream status: {status}")

        if not self._running:
            return

        rms = self._calculate_rms(indata)
        current_time = time.time()

        if not self._is_speaking:
            # Check for speech onset
            if rms > self.energy_threshold:
                self._is_speaking = True
                self._utterance_start_time = current_time
                self._silence_start_time = None
                self._speech_buffer = [indata.copy()]
                logger.debug(f"Speech detected (RMS: {rms:.1f} > {self.energy_threshold})")
                self.event_bus.publish(
                    Event(
                        event_type=EventType.SPEECH_DETECTED,
                        data={"rms": rms},
                        source="audio_capture",
                    )
                )
        else:
            # Speech currently active
            self._speech_buffer.append(indata.copy())
            utterance_len = current_time - (self._utterance_start_time or current_time)

            if rms > self.energy_threshold:
                # Reset silence counter
                self._silence_start_time = None
            else:
                # Silence frame
                if self._silence_start_time is None:
                    self._silence_start_time = current_time
                elif (current_time - self._silence_start_time) >= self.silence_timeout or utterance_len >= self.max_utterance_duration:
                    # Utterance complete
                    self._finalize_utterance(utterance_len)

    def _finalize_utterance(self, duration: float) -> None:
        """Converts raw audio chunks to an AudioUtterance and triggers callback."""
        if duration >= self.min_speech_duration and self._speech_buffer:
            combined = np.concatenate(self._speech_buffer, axis=0)
            wav_bytes = self._numpy_to_wav(combined, self.sample_rate)
            peak_rms = self._calculate_rms(combined)

            utterance = AudioUtterance(
                wav_bytes=wav_bytes,
                duration_seconds=duration,
                sample_rate=self.sample_rate,
                channels=self.channels,
                rms_peak=peak_rms,
            )
            logger.info(f"Captured utterance: {duration:.2f}s, size={len(wav_bytes)} bytes")

            if self._on_utterance_callback:
                try:
                    self._on_utterance_callback(utterance)
                except Exception as e:
                    logger.error(f"Error in utterance callback: {e}", exc_info=True)

        # Reset states
        self._is_speaking = False
        self._speech_buffer = []
        self._silence_start_time = None
        self._utterance_start_time = None

    @staticmethod
    def _numpy_to_wav(audio_data: np.ndarray, sample_rate: int) -> bytes:
        """Encodes numpy int16 array to standard PCM WAV bytes in memory."""
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit PCM = 2 bytes
            wf.setframerate(sample_rate)
            wf.writeframes(audio_data.astype(np.int16).tobytes())
        return wav_io.getvalue()

    def start(self) -> bool:
        """Starts background microphone stream."""
        with self._lock:
            if self._running:
                return True

            try:
                self._stream = sd.InputStream(
                    samplerate=self.sample_rate,
                    channels=self.channels,
                    dtype="int16",
                    blocksize=1024,
                    device=self.device_index,
                    callback=self._audio_callback,
                )
                self._stream.start()
                self._running = True
                logger.info("Microphone stream started successfully")
                self.event_bus.publish(
                    Event(
                        event_type=EventType.MIC_LISTENING_START,
                        data={"device_index": self.device_index},
                        source="audio_capture",
                    )
                )
                return True
            except Exception as e:
                logger.error(f"Failed to start microphone stream: {e}", exc_info=True)
                self._running = False
                self._stream = None
                return False

    def stop(self) -> None:
        """Stops microphone stream."""
        with self._lock:
            if not self._running:
                return

            self._running = False
            if self._stream:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:
                    logger.debug(f"Error closing audio stream: {e}")
                self._stream = None

            self.event_bus.publish(
                Event(
                    event_type=EventType.MIC_LISTENING_STOP,
                    source="audio_capture",
                )
            )
            logger.info("Microphone stream stopped")

    @property
    def is_listening(self) -> bool:
        return self._running
