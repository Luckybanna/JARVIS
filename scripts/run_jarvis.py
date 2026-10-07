"""
Master Desktop Application Launcher for JARVIS.
Bootstraps full subsystem: Voice, HUD Canvas, Avatar, Memory, Emotion, Proactive Scheduler, and Dev Panel.
"""

import argparse
from pathlib import Path
import sys

# Ensure root directory is on sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PyQt6.QtWidgets import QApplication

from app.avatar.controller import get_avatar_controller
from app.core.config import get_settings
from app.core.conversation import ConversationManager
from app.core.events import Event, EventType, get_event_bus
from app.core.logger import get_logger
from app.emotion.engine import get_emotion_engine
from app.memory.manager import get_memory_manager
from app.proactive.engine import get_proactive_engine
from app.tasks.manager import get_task_manager
from app.tools.executor import get_tool_executor
from app.tools.router import ToolRouter
from app.ui.main_window import JarvisMainWindow

logger = get_logger("launcher")


def main():
    parser = argparse.ArgumentParser(description="JARVIS Personal AI Desktop Assistant")
    parser.add_argument("--no-voice", action="store_true", help="Launch in silent text-only mode (no mic/TTS)")
    parser.add_argument("--dev-open", action="store_true", help="Launch with Developer Telemetry panel expanded")
    args = parser.parse_args()

    print("=" * 65)
    print("           J.A.R.V.I.S. - DESKTOP AI ASSISTANT")
    print("=" * 65)
    print("[1/6] Loading Configuration & Logging Subsystem...")
    settings = get_settings()
    bus = get_event_bus()

    print(f"[2/6] Initializing AI Provider ({settings.ai_provider.upper()}) & Memory DB...")
    mem_mgr = get_memory_manager()
    emotion_eng = get_emotion_engine()
    task_mgr = get_task_manager()
    tool_exec = get_tool_executor(event_bus=bus)
    tool_router = ToolRouter(executor=tool_exec)

    conv_mgr = ConversationManager(
        event_bus=bus,
        memory_manager=mem_mgr,
        emotion_engine=emotion_eng,
        tool_router=tool_router,
        task_manager=task_mgr,
    )

    print("[3/6] Starting Proactive Conversation Engine...")
    proactive_eng = get_proactive_engine()

    voice_mgr = None
    if not args.no_voice:
        print("[4/6] Initializing Voice Capture & Neural Speech Synthesizer...")
        try:
            from app.voice.voice_manager import get_voice_manager
            voice_mgr = get_voice_manager(event_bus=bus, conversation_manager=conv_mgr)
            print("      Voice Hardware: READY")
        except Exception as e:
            logger.warning(f"Voice manager could not be started: {e}")
            print(f"      [WARN] Voice pipeline unavailable: {e}")
    else:
        print("[4/6] Voice disabled via --no-voice (Text-Only Mode active).")

    print("[5/6] Initializing Arc-Reactor Avatar & HUD Interface...")
    avatar_ctrl = get_avatar_controller(event_bus=bus)

    app = QApplication(sys.argv)
    window = JarvisMainWindow(
        conversation_manager=conv_mgr,
        event_bus=bus,
        voice_manager=voice_mgr,
        show_dev_panel=args.dev_open,
    )

    # Publish system startup event
    bus.publish(Event(
        event_type=EventType.SYSTEM_STARTUP,
        data={"version": "1.0.0", "ai_provider": settings.ai_provider},
        source="launcher",
    ))

    print("[6/6] Launching GUI Desktop Window. Ready, Sir.")
    print("=" * 65)

    window.show()
    exit_code = app.exec()

    # Teardown on exit
    print("\nShutting down JARVIS subsystems...")
    task_mgr.stop_poller()
    bus.publish(Event(event_type=EventType.SYSTEM_SHUTDOWN, source="launcher"))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
