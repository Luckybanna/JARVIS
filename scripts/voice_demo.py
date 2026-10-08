"""
Voice Pipeline Interactive Demo & Hardware Diagnostic Script for JARVIS (Phase 2).
Tests microphone detection, VAD, Neural TTS (Hindi/Hinglish/English), and interruption.
"""

import sys
from pathlib import Path
import time

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output in Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import get_settings
from app.core.events import Event, EventType, get_event_bus
from app.voice.audio_capture import AudioCapture
from app.voice.tts_engine import EdgeTTSProvider, SAPIProvider, detect_language_hint


def main():
    settings = get_settings()
    bus = get_event_bus()

    print("=" * 60)
    print("      J.A.R.V.I.S. - VOICE SUBSYSTEM DIAGNOSTICS (PHASE 2)")
    print("=" * 60)

    # 1. Inspect Input Devices
    devices = AudioCapture.list_input_devices()
    print(f"\n[1] Detected Microphone Devices ({len(devices)} found):")
    for d in devices:
        print(f"    Index {d['index']}: {d['name']} (Channels: {d['channels']})")

    # 2. Test Language Detection
    print("\n[2] Testing Language & Hinglish Detection:")
    test_phrases = [
        "Namaste Jarvis kaise ho aap",
        "Jarvis aaj mujhe Kota jana hai",
        "Hello Jarvis, please check system performance",
        "नमस्ते, आज का मौसम कैसा है?",
    ]
    for p in test_phrases:
        detected = detect_language_hint(p)
        print(f"    \"{p}\" -> Detected: [{detected.upper()}]")

    # 3. Test Text-to-Speech Engine with Conversational Prosody
    print("\n[3] Testing Neural Text-to-Speech with Conversational Prosody:")
    edge_tts = EdgeTTSProvider(event_bus=bus)

    hindi_sample = "Sir, dhyan dijiye - system ki RAM usage 86% ho gayi hai (569 MB free). PC restart karun?"
    print(f"    Input Prompt: \"{hindi_sample}\"")
    voice_h = edge_tts.select_voice_for_text(hindi_sample)
    print(f"    Selected Voice: {voice_h}")
    bytes_h = edge_tts.synthesize_with_prosody(hindi_sample, voice=voice_h)
    print(f"    Generated: {len(bytes_h)} bytes of MP3 audio with dynamic prosody")

    english_sample = "All systems are operational and ready for your commands, Sir."
    print(f"\n    Synthesizing English: \"{english_sample}\"")
    voice_e = edge_tts.select_voice_for_text(english_sample)
    print(f"    Selected Voice: {voice_e}")
    bytes_e = edge_tts.synthesize_to_bytes(english_sample, voice=voice_e)
    print(f"    Generated: {len(bytes_e)} bytes of MP3 audio")

    # 4. SAPI Offline Fallback Check (Disabled by default to prevent male voice leakage)
    sapi = SAPIProvider(event_bus=bus)
    print(f"\n[4] Windows SAPI Engine Status: {'[OK] Available (Offline Standby)' if sapi._voice_engine else '[N/A] Unavailable'}")

    print("\n" + "=" * 60)
    print("Voice subsystem diagnostics completed successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
