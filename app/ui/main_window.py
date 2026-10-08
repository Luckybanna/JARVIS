"""
Main Desktop HUD Window for JARVIS.
Integrates Arc-Reactor avatar, reactive audio visualizer, conversation feed,
speech/text input controls, collapsible developer panel, and EventBus synchronization.
"""

import sys
import threading
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.avatar.controller import get_avatar_controller
from app.avatar.renderer import AvatarRendererWidget
from app.core.config import get_settings
from app.core.conversation import ConversationManager
from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.logger import get_logger
from app.ui.audio_visualizer import AudioVisualizerWidget
from app.ui.chat_feed import ChatFeedWidget
from app.ui.dev_panel import DeveloperPanel
from app.ui.styles import HUD_STYLESHEET

logger = get_logger("ui.main")


class JarvisMainWindow(QMainWindow):
    """
    Primary desktop HUD window for JARVIS AI assistant.
    """
    # Signals for thread-safe UI updates
    user_message_signal = pyqtSignal(str)
    jarvis_response_signal = pyqtSignal(str, str)
    audio_level_signal = pyqtSignal(float)
    status_update_signal = pyqtSignal(str)

    def __init__(
        self,
        conversation_manager: Optional[ConversationManager] = None,
        event_bus: Optional[EventBus] = None,
        voice_manager: Optional[any] = None,
        show_dev_panel: bool = False,
    ):
        super().__init__()
        self.settings = get_settings()
        self.bus = event_bus or get_event_bus()
        self.conversation_manager = conversation_manager or ConversationManager(event_bus=self.bus)
        if voice_manager is not None:
            self.voice_manager = voice_manager
        else:
            try:
                from app.voice.voice_manager import get_voice_manager
                self.voice_manager = get_voice_manager(event_bus=self.bus, conversation_manager=self.conversation_manager)
            except Exception as e:
                logger.warning(f"Voice manager fallback failed: {e}")
                self.voice_manager = None
        self.avatar_controller = get_avatar_controller(event_bus=self.bus)

        self.setWindowTitle("J.A.R.V.I.S. - Advanced Artificial Intelligence")
        self.resize(1100, 780)
        self.setMinimumSize(850, 600)
        self.setStyleSheet(HUD_STYLESHEET)

        self._init_ui(show_dev_panel)
        self._connect_signals()
        self._subscribe_events()

        logger.info("JarvisMainWindow initialized successfully.")

    def _init_ui(self, show_dev_panel: bool):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Splitter dividing main HUD and collapsible Dev Panel
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.splitter)

        # -------------------------------------------------------------
        # Left Side: Primary HUD Canvas
        # -------------------------------------------------------------
        hud_container = QWidget()
        hud_layout = QVBoxLayout(hud_container)
        hud_layout.setContentsMargins(16, 16, 16, 16)
        hud_layout.setSpacing(10)

        # 1. Avatar Core Widget
        avatar_container = QWidget()
        avatar_layout = QVBoxLayout(avatar_container)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.setSpacing(6)
        avatar_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.avatar_widget = AvatarRendererWidget(controller=self.avatar_controller)
        self.avatar_widget.setFixedSize(180, 180)
        avatar_layout.addWidget(self.avatar_widget)

        # 2. Audio Visualizer Spectrum
        self.audio_viz = AudioVisualizerWidget()
        avatar_layout.addWidget(self.audio_viz)

        hud_layout.addWidget(avatar_container)

        # 3. Conversation History Feed
        self.chat_feed = ChatFeedWidget()
        hud_layout.addWidget(self.chat_feed, stretch=1)

        # Add initial welcome greeting
        from datetime import datetime as _dt
        _h = _dt.now().hour
        _salutation = 'Good morning Sir!' if _h < 12 else ('Good afternoon Sir!' if _h < 17 else 'Good evening Sir!')
        welcome_text = f'{_salutation} Aaj kya plan hai? Main aapki poori madad ke liye taiyaar hoon.'
        self.chat_feed.add_jarvis_message(
            welcome_text,
            model_tag=self.settings.ai_provider.upper(),
        )
        if self.voice_manager:
            threading.Thread(
                target=lambda: self.voice_manager.speak_manual(welcome_text),
                daemon=True,
                name="WelcomeSpeechWorker",
            ).start()


        # 4. Quick Action Shortcut Bar
        shortcuts_layout = QHBoxLayout()
        shortcuts_layout.setSpacing(8)

        btn_specs = QPushButton("System Status")
        btn_specs.clicked.connect(lambda: self._submit_text_input("JARVIS what is the system status?"))
        shortcuts_layout.addWidget(btn_specs)

        btn_mute = QPushButton("Toggle Mute")
        btn_mute.clicked.connect(lambda: self._submit_text_input("mute sound"))
        shortcuts_layout.addWidget(btn_mute)

        btn_reminders = QPushButton("List Reminders")
        btn_reminders.clicked.connect(lambda: self._submit_text_input("list my reminders"))
        shortcuts_layout.addWidget(btn_reminders)

        btn_clear = QPushButton("Clear Feed")
        btn_clear.clicked.connect(self.chat_feed.clear_feed)
        shortcuts_layout.addWidget(btn_clear)

        shortcuts_layout.addStretch()
        hud_layout.addLayout(shortcuts_layout)

        # 5. Bottom Input Bar
        input_layout = QHBoxLayout()
        input_layout.setSpacing(10)

        # Microphone Toggle Button
        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setObjectName("mic_btn")
        self.mic_btn.setToolTip("Toggle Speech Capture")
        self.mic_btn.clicked.connect(self._toggle_voice_capture)
        input_layout.addWidget(self.mic_btn)

        # Text Line Edit
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Ask JARVIS anything or type a PC command... (Enter to send)")
        self.input_edit.returnPressed.connect(self._on_send_pressed)
        input_layout.addWidget(self.input_edit, stretch=1)

        # Send Button
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send_pressed)
        input_layout.addWidget(self.send_btn)

        hud_layout.addLayout(input_layout)
        self.splitter.addWidget(hud_container)

        # -------------------------------------------------------------
        # Right Side: Developer Telemetry Drawer
        # -------------------------------------------------------------
        self.dev_panel = DeveloperPanel(event_bus=self.bus)
        self.splitter.addWidget(self.dev_panel)

        # Initial visibility of Dev Panel
        self.dev_panel.setVisible(show_dev_panel)
        self.splitter.setSizes([720, 380])

        # -------------------------------------------------------------
        # Status Bar
        # -------------------------------------------------------------
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.lbl_status_ai = QLabel(f"AI: {self.settings.ai_provider.upper()} ({self.settings.gemini_model})")
        self.lbl_status_voice = QLabel("Voice: READY")
        self.lbl_status_latency = QLabel("Latency: 0 ms")

        self.btn_toggle_dev = QPushButton("Telemetry [F12]")
        self.btn_toggle_dev.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_toggle_dev.clicked.connect(self._toggle_dev_panel)

        self.status_bar.addWidget(self.lbl_status_ai)
        self.status_bar.addWidget(QLabel(" | "))
        self.status_bar.addWidget(self.lbl_status_voice)
        self.status_bar.addWidget(QLabel(" | "))
        self.status_bar.addWidget(self.lbl_status_latency)
        self.status_bar.addPermanentWidget(self.btn_toggle_dev)

        # Keyboard Shortcut: F12 to toggle Dev Panel
        shortcut_f12 = QShortcut(QKeySequence("F12"), self)
        shortcut_f12.activated.connect(self._toggle_dev_panel)

    def _connect_signals(self):
        """Connects Qt pyqtSignals for safe GUI thread updates."""
        self.user_message_signal.connect(self.chat_feed.add_user_message)
        self.jarvis_response_signal.connect(self.chat_feed.add_jarvis_message)
        self.audio_level_signal.connect(self.audio_viz.set_level)
        self.status_update_signal.connect(self.lbl_status_latency.setText)

    def _subscribe_events(self):
        """Subscribes to system events to update status bar and audio visualizer."""
        self.bus.subscribe(EventType.SPEECH_DETECTED, self._on_speech_detected)
        self.bus.subscribe(EventType.TTS_SPEAKING_START, lambda e: self.lbl_status_voice.setText("Voice: SPEAKING"))
        self.bus.subscribe(EventType.TTS_SPEAKING_STOP, lambda e: self.lbl_status_voice.setText("Voice: READY"))
        self.bus.subscribe(EventType.MIC_LISTENING_START, lambda e: self._update_mic_state(True))
        self.bus.subscribe(EventType.MIC_LISTENING_STOP, lambda e: self._update_mic_state(False))
        self.bus.subscribe(EventType.PROACTIVE_MESSAGE_PROPOSED, self._on_proactive_message)

    def _on_proactive_message(self, event: Event):
        msg = event.data.get("message", "")
        if not msg:
            return
        self.jarvis_response_signal.emit(msg, "COMPANION")
        if self.voice_manager:
            threading.Thread(
                target=lambda: self.voice_manager.speak_manual(msg),
                daemon=True,
                name="ProactiveSpeechWorker",
            ).start()
        try:
            from app.proactive.engine import get_proactive_engine
            get_proactive_engine().record_proactive_speech()
        except Exception:
            pass

    def _on_speech_detected(self, event: Event):
        rms = event.data.get("rms", 0.0)
        norm = min(1.0, float(rms) / 2500.0) if rms else 0.3
        self.audio_level_signal.emit(norm)

    def _update_mic_state(self, is_listening: bool):
        self.mic_btn.setProperty("listening", "true" if is_listening else "false")
        self.mic_btn.style().unpolish(self.mic_btn)
        self.mic_btn.style().polish(self.mic_btn)
        self.lbl_status_voice.setText("Voice: LISTENING" if is_listening else "Voice: READY")

    def _toggle_dev_panel(self):
        """Toggles developer panel drawer visibility."""
        is_visible = not self.dev_panel.isHidden()
        self.dev_panel.setVisible(not is_visible)
        if not is_visible:
            self.splitter.setSizes([700, 380])

    def _toggle_voice_capture(self):
        """Toggles microphone capture on VoiceManager if available."""
        if not self.voice_manager:
            self.chat_feed.add_jarvis_message("Voice input hardware is currently unavailable or disabled.")
            return

        if getattr(self.voice_manager, "is_listening", False):
            self.voice_manager.stop_listening()
        else:
            self.voice_manager.start_listening_async()

    def _on_send_pressed(self):
        text = self.input_edit.text().strip()
        if not text:
            return
        self.input_edit.clear()
        self._submit_text_input(text)

    def _submit_text_input(self, text: str):
        """Asynchronously dispatches user turn to ConversationManager."""
        self.user_message_signal.emit(text)

        # Worker thread so UI never hangs during LLM API calls or tool actions
        def _worker():
            try:
                response = self.conversation_manager.send_user_message(text)
                model_tag = response.model or self.settings.ai_provider.upper()
                self.jarvis_response_signal.emit(response.content, model_tag)
                self.status_update_signal.emit(f"Latency: {response.latency_ms:.0f} ms")

                # Voice output: Speak assistant response aloud
                if self.voice_manager and response.content:
                    if not response.content.startswith("[Error"):
                        self.voice_manager.speak_manual(response.content)
                    else:
                        self.voice_manager.speak_manual("Sir, I encountered an issue contacting the AI model. Please check your settings.")
            except Exception as e:
                logger.error(f"Error handling user turn: {e}", exc_info=True)
                self.jarvis_response_signal.emit(f"I encountered an error processing your request: {e}", "ERROR")
                if self.voice_manager:
                    self.voice_manager.speak_manual("I encountered an error processing your request, sir.")

        t = threading.Thread(target=_worker, daemon=True, name="JarvisTurnWorker")
        t.start()

    def closeEvent(self, event):
        """Clean teardown on window close."""
        self.dev_panel.close()
        self.avatar_widget.close()
        self.audio_viz.close()
        super().closeEvent(event)
