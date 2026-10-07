# JARVIS — Windows Desktop Proactive AI Assistant

JARVIS is a real, functional Windows desktop personal AI assistant and companion designed to speak naturally (in Hindi, English, and Hinglish), maintain simulated emotional awareness, proactively engage when appropriate, safely control Windows functions, and display a reactive animated avatar.

---

## High-Level Architecture

```
User (Voice / Text)
  │
  ▼
Microphone Capture (sounddevice + VAD)
  │
  ▼
Speech-to-Text (Whisper / Multimodal Cloud)
  │
  ▼
Event Bus (Decoupled PubSub)
  │
  ▼
Conversation Manager ─── Short & Long Term Memory (SQLite)
  │                  ─── Emotion Engine (Simulated 9-dim State)
  │                  ─── Personality Engine (Intellectual honesty, Hinglish)
  │                  ─── Proactive Engine (Anti-annoyance, break alerts)
  ▼
AI Brain Provider (Gemini / OpenAI / Local Ollama)
  │
  ├── Safe PC Automation Tools (SAFE / CONFIRM_REQUIRED / BLOCKED)
  │
  ├── Text-to-Speech (Edge-TTS Hindi/English + SAPI Fallback)
  │
  └── Animated Avatar (PyQt6 Reactive Geometric Core)
```

---

## Features (By Phase)

- **Phase 1 (Completed Foundation):**
  - Modular AI Provider abstraction (`GeminiProvider`, `OpenAIProvider`, `LocalProvider`).
  - Secure configuration management (`.env` and `default_config.json`) with masked key redaction.
  - Thread-safe Pub/Sub Event Bus for all system events.
  - Rotating file and console structured logging.
  - Conversational turn manager with short-term history buffer and telemetry.
  - CLI test harness (`scripts/cli_chat.py`).
  - Automated test suite.

---

## Quickstart

### 1. Requirements & Installation

Python 3.10+ (64-bit) on Windows.

Install dependencies:
```bash
python -m pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env`:
```bash
copy .env.example .env
```

Edit `.env` to supply your API key:
```env
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```
Or for OpenAI:
```env
AI_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

### 3. Run Tests

Execute the automated test suite:
```bash
pytest tests/ -v
```

### 4. Run CLI Harness

```bash
python scripts/cli_chat.py
```
