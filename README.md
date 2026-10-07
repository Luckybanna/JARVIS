# J.A.R.V.I.S. — Windows Desktop Proactive AI Assistant

JARVIS is a real, production-quality Windows desktop personal AI assistant and proactive companion. It speaks naturally in English, Hindi, and Hinglish, maintains simulated emotional awareness (9-dimensional vector), remembers personal context across sessions in local SQLite, proactively engages with anti-annoyance filters, safely automates Windows controls with permission tiers, and displays a 60 FPS reactive Arc-Reactor avatar.

---

## High-Level Architecture

```
User (Voice / Text)
  │
  ▼
Microphone Capture (sounddevice + RMS VAD)
  │
  ▼
Speech-to-Text (Whisper / Gemini Multimodal Audio)
  │
  ▼
Event Bus (Thread-safe Decoupled PubSub)
  │
  ▼
Conversation Manager ─── Persistent Long-term Memory (SQLite: jarvis_memory.db)
  │                  ─── Emotion Engine (Simulated 9-dim State Vector + Decay)
  │                  ─── Personality Engine (Intellectual Honesty, Wit, Hinglish)
  │                  ─── Proactive Engine (ShouldJarvisSpeakNow, Anti-annoyance)
  │                  ─── Task & Reminder Subsystem (NLP Date/Time Parser)
  │                  ─── Safe PC Automation (SAFE / CONFIRM_REQUIRED / BLOCKED)
  ▼
AI Brain Provider (Google Gemini 2.5 Flash / OpenAI / Local HTTP)
  │
  ├── Text-to-Speech (Microsoft Edge Neural hi-IN / en-US + SAPI fallback)
  │
  ├── Animated Avatar (PyQt6 60 FPS Geometric Arc-Reactor HUD)
  │
  └── Developer Telemetry Panel (Tokens, 9D Bars, Memory Audit, Event Stream)
```

---

## All 10 Phases Completed

1. **Phase 1: Project Foundation & Core Infrastructure** (`commit 52ef065`)
   - AI Provider interface (`GeminiProvider`, `OpenAIProvider`, `LocalProvider`).
   - Secure config system (`.env` and `default_config.json`) with API key masking.
   - Decoupled, thread-safe PubSub `EventBus`.
   - Structured rotating file/console logging.
   - CLI harness: `scripts/cli_chat.py`.

2. **Phase 2: Voice Pipeline & Interruption** (`commit 5e19e89`)
   - Microphone capture with RMS/VAD and in-memory WAV packaging.
   - Multilingual STT Engine for Hindi, English, and Hinglish.
   - Natural Microsoft Edge Neural TTS (`hi-IN-MadhurNeural`, `en-US-GuyNeural`) with SAPI fallback.
   - Full barge-in interruption cancellation. Diagnostic: `scripts/voice_demo.py`.

3. **Phase 3: Personality Engine & Response Planner** (`commit 76b74cd`)
   - Persona with calm wit, concise communication, and mandatory intellectual honesty framework.
   - Intent classification (`PROPOSITION`, `QUERY`, `ELABORATION`, `COMMAND`, `CHITCHAT`).
   - Dynamic prompt synthesis adapting to English or Hinglish.

4. **Phase 4: Persistent Memory System** (`commit 1cbded4`)
   - SQLite local database at `data/jarvis_memory.db` with CRUD and keyword search.
   - Heuristic fact extraction rejecting transient queries while storing durable user facts.
   - Privacy purge capability and context retrieval injection.

5. **Phase 5: Emotion Engine & User Detection** (`commit 480f38d`)
   - Simulated 9D state vector (Happiness, Sadness, Anger, Fear, Curiosity, Concern, Confidence, Energy, Trust).
   - Multilingual user emotion detector (11 states) and deterministic transitions.
   - Natural exponential decay towards baseline anchors.

6. **Phase 6: Proactive Conversation Engine** (`commit 162df54`)
   - `ShouldJarvisSpeakNow()` decision evaluator.
   - Anti-annoyance filters: DND, meeting mode, quiet hours (23:00-07:00), user speaking check, cooldown interval (45m), and hourly quota (2/hr).
   - Continuous work break suggestions (90m) and memory project follow-ups.

7. **Phase 7: Animated Avatar Core** (`commit c9d50b7`)
   - 10 distinct visual states (`IDLE`, `LISTENING`, `THINKING`, `SPEAKING`, `HAPPY`, `CONCERNED`, `SAD`, `ANGRY`, `SURPRISED`, `SLEEPING`).
   - Geometric Arc-Reactor HUD (concentric counter-rotating rings, glowing radial gradients, audio-reactive amplitude scaling).
   - Smooth color/scale interpolation. Interactive preview: `scripts/avatar_preview.py`.

8. **Phase 8: PC Automation Tools & Safety Tiers** (`commit dc99ba1`)
   - Permission tiers: `SAFE` (immediate), `CONFIRM_REQUIRED` (explicit approval), `BLOCKED` (strict safety policy).
   - Real-time system telemetry via `psutil` (CPU, RAM, disk, battery, uptime).
   - Audio hardware control via `pycaw` (master volume, mute/unmute).
   - Approved app launcher, process manager, and verified URL navigator.
   - Natural language command routing with confirmation lifecycle. Diagnostic: `scripts/tools_demo.py`.

9. **Phase 9: Task & Reminder Subsystem** (`commit 995639d`)
   - Multilingual natural language date/time parser (relative/absolute times in English, Hindi, and Hinglish).
   - SQLite persistence and recurring reminder scheduling.
   - Background poller triggering proactive `REMINDER_DUE` announcements. Diagnostic: `scripts/tasks_demo.py`.

10. **Phase 10: Desktop HUD & Developer Telemetry Panel** (`commit 9695577`)
    - Primary PyQt6 desktop HUD integrating the Avatar, audio equalizer spectrum, conversation feed, and input controls.
    - Collapsible Developer Telemetry drawer (`F12`) displaying real-time AI latency/tokens, 9D emotion vector bars, memory audit table with purge, and live EventBus signal log.
    - Master application launcher: `scripts/run_jarvis.py`.

---

## Quickstart

### 1. Requirements & Setup
- Windows 10/11 64-bit
- Python 3.10+ (tested on Python 3.13)
- Dependencies installed via:
```bash
python -m pip install -r requirements.txt
```

### 2. Configure API Keys
Configure your `.env` file in the project root:
```env
GEMINI_API_KEY="your-google-gemini-api-key"
AI_PROVIDER="gemini"
GEMINI_MODEL="gemini-2.5-flash"
LOG_LEVEL="INFO"
```

### 3. Launching JARVIS Desktop Application

- **Full Mode (Voice + Animated HUD + Dev Panel):**
  ```bash
  python scripts/run_jarvis.py
  ```

- **Launch with Developer Telemetry Panel Expanded:**
  ```bash
  python scripts/run_jarvis.py --dev-open
  ```

- **Silent / Text-Only Mode (No microphone or TTS hardware required):**
  ```bash
  python scripts/run_jarvis.py --no-voice
  ```

---

## Diagnostics & Visual Previews

| Script | Purpose |
| :--- | :--- |
| `python scripts/avatar_preview.py` | Interactive preview of the Arc-Reactor avatar, state toggles, and audio reactivity waveform |
| `python scripts/tools_demo.py` | Diagnostic run for system telemetry, audio control, file search, and confirmation lifecycle |
| `python scripts/tasks_demo.py` | Diagnostic test for English/Hindi/Hinglish date-time parser and SQLite reminders |
| `python scripts/voice_demo.py` | Audio pipeline test for microphone capture, STT, and neural TTS synthesis |
| `python scripts/cli_chat.py` | Lightweight terminal CLI for conversational testing with emotion and memory audit |

---

## Automated Test Suite

All 77 unit and integration tests across all 10 phases pass:
```bash
python -m pytest tests/ -v
```
