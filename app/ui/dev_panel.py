"""
Collapsible Developer Telemetry and Audit Panel for JARVIS.
Provides real-time inspection into AI providers, 9D emotion vector, memory audit,
proactive decisions, and system-wide EventBus signal stream.
"""

from datetime import datetime
import json
import time
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.config import get_settings
from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.logger import get_logger
from app.emotion.engine import get_emotion_engine
from app.emotion.state import EmotionState
from app.memory.manager import get_memory_manager

logger = get_logger("ui.dev_panel")


class DeveloperPanel(QWidget):
    """
    Developer and diagnostics drawer widget for real-time telemetry.
    """
    # Thread-safe Qt signal to dispatch events from background threads onto the GUI thread
    event_received = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None, event_bus: Optional[EventBus] = None):
        super().__init__(parent)
        self.bus = event_bus or get_event_bus()
        self.settings = get_settings()

        self.setMinimumWidth(380)
        self._init_ui()

        # Connect internal signal
        self.event_received.connect(self._on_event_received_gui)

        # Subscribe to all EventBus traffic
        self.bus.subscribe_all(self._on_bus_event)

        # Initial data refresh
        self.refresh_all()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Header Title
        header_layout = QHBoxLayout()
        title_label = QLabel("SYSTEM TELEMETRY & DIAGNOSTICS")
        title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #58a6ff; letter-spacing: 1px;")
        header_layout.addWidget(title_label)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFixedWidth(70)
        self.refresh_btn.clicked.connect(self.refresh_all)
        header_layout.addWidget(self.refresh_btn)

        layout.addLayout(header_layout)

        # Tab Widget
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Tab 1: AI & System Overview
        self.tab_overview = QWidget()
        self._init_tab_overview()
        self.tabs.addTab(self.tab_overview, "Overview")

        # Tab 2: 9D Emotion Vector
        self.tab_emotion = QWidget()
        self._init_tab_emotion()
        self.tabs.addTab(self.tab_emotion, "Emotion")

        # Tab 3: Memory Audit
        self.tab_memory = QWidget()
        self._init_tab_memory()
        self.tabs.addTab(self.tab_memory, "Memory")

        # Tab 4: EventBus Stream
        self.tab_events = QWidget()
        self._init_tab_events()
        self.tabs.addTab(self.tab_events, "Events")

    # -------------------------------------------------------------
    # Tab 1: AI & System Overview
    # -------------------------------------------------------------
    def _init_tab_overview(self):
        layout = QVBoxLayout(self.tab_overview)
        layout.setSpacing(12)

        # Provider Card
        ai_group = QGroupBox("AI Engine & Latency")
        ai_layout = QVBoxLayout(ai_group)
        self.lbl_provider = QLabel(f"Provider: {self.settings.ai_provider.upper()}")
        self.lbl_model = QLabel(f"Model: {self.settings.gemini_model if self.settings.ai_provider == 'gemini' else 'default'}")
        self.lbl_latency = QLabel("Last Latency: 0.0 ms")
        self.lbl_tokens = QLabel("Token Usage: prompt=0 | completion=0 | total=0")

        ai_layout.addWidget(self.lbl_provider)
        ai_layout.addWidget(self.lbl_model)
        ai_layout.addWidget(self.lbl_latency)
        ai_layout.addWidget(self.lbl_tokens)
        layout.addWidget(ai_group)

        # Proactive Policy Card
        proactive_group = QGroupBox("Proactive Rules & Policy")
        p_layout = QVBoxLayout(proactive_group)
        self.lbl_dnd = QLabel(f"DND Mode: {'Active' if self.settings.do_not_disturb else 'Off'}")
        self.lbl_meeting = QLabel(f"Meeting Mode: {'Active' if self.settings.meeting_mode else 'Off'}")
        self.lbl_quiet = QLabel(f"Quiet Hours ({self.settings.quiet_hours_start}-{self.settings.quiet_hours_end}): {'Enabled' if self.settings.quiet_hours_enabled else 'Off'}")
        self.lbl_cooldown = QLabel(f"Cooldown Interval: {self.settings.min_proactive_interval_min}m | Hourly Quota: {self.settings.max_proactive_per_hour}/hr")

        p_layout.addWidget(self.lbl_dnd)
        p_layout.addWidget(self.lbl_meeting)
        p_layout.addWidget(self.lbl_quiet)
        p_layout.addWidget(self.lbl_cooldown)
        layout.addWidget(proactive_group)

        layout.addStretch()

    # -------------------------------------------------------------
    # Tab 2: 9D Emotion Vector
    # -------------------------------------------------------------
    def _init_tab_emotion(self):
        layout = QVBoxLayout(self.tab_emotion)
        layout.setSpacing(8)

        self.emotion_bars = {}
        self.emotion_labels = {}

        dimensions = [
            "happiness",
            "sadness",
            "anger",
            "fear",
            "curiosity",
            "concern",
            "confidence",
            "energy",
            "trust",
        ]

        for dim in dimensions:
            row_layout = QHBoxLayout()
            name_lbl = QLabel(dim.capitalize())
            name_lbl.setFixedWidth(80)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(50)
            bar.setTextVisible(False)
            bar.setFixedHeight(12)

            val_lbl = QLabel("50.0")
            val_lbl.setFixedWidth(35)
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

            row_layout.addWidget(name_lbl)
            row_layout.addWidget(bar)
            row_layout.addWidget(val_lbl)
            layout.addLayout(row_layout)

            self.emotion_bars[dim] = bar
            self.emotion_labels[dim] = val_lbl

        layout.addStretch()

    # -------------------------------------------------------------
    # Tab 3: Memory Audit
    # -------------------------------------------------------------
    def _init_tab_memory(self):
        layout = QVBoxLayout(self.tab_memory)
        layout.setSpacing(8)

        # Filter bar
        filter_layout = QHBoxLayout()
        self.mem_search_input = QLineEdit()
        self.mem_search_input.setPlaceholderText("Filter memories...")
        self.mem_search_input.textChanged.connect(self._filter_memories)
        filter_layout.addWidget(self.mem_search_input)

        self.purge_mem_btn = QPushButton("Wipe All")
        self.purge_mem_btn.setStyleSheet("color: #ff7b72; border-color: #ff7b72;")
        self.purge_mem_btn.clicked.connect(self._purge_memories)
        filter_layout.addWidget(self.purge_mem_btn)

        layout.addLayout(filter_layout)

        # Memory Table
        self.mem_table = QTableWidget(0, 3)
        self.mem_table.setHorizontalHeaderLabels(["Category", "Content", "Created"])
        self.mem_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.mem_table.setStyleSheet("background-color: #0d1117; border: 1px solid #21262d; font-size: 11px;")
        layout.addWidget(self.mem_table)

    # -------------------------------------------------------------
    # Tab 4: EventBus Stream
    # -------------------------------------------------------------
    def _init_tab_events(self):
        layout = QVBoxLayout(self.tab_events)
        layout.setSpacing(8)

        btn_layout = QHBoxLayout()
        self.clear_events_btn = QPushButton("Clear Stream")
        self.clear_events_btn.clicked.connect(self._clear_events)
        btn_layout.addWidget(self.clear_events_btn)
        layout.addLayout(btn_layout)

        self.events_list = QListWidget()
        self.events_list.setStyleSheet("""
            background-color: #0d1117;
            border: 1px solid #21262d;
            font-family: 'Consolas', monospace;
            font-size: 11px;
            color: #79c0ff;
        """)
        layout.addWidget(self.events_list)

    # -------------------------------------------------------------
    # Live Refresh and Event Integration
    # -------------------------------------------------------------
    def _on_bus_event(self, event: Event) -> None:
        """Dispatches bus event onto the Qt signal thread."""
        try:
            self.event_received.emit(event)
        except Exception:
            pass

    def _on_event_received_gui(self, event: Event) -> None:
        """Runs on the Qt GUI thread to update widgets in real time."""
        # 1. Append to Events Stream (keep last 100)
        time_str = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S")
        entry = f"[{time_str}] [{event.source}] {event.event_type.value}"
        self.events_list.insertItem(0, entry)
        if self.events_list.count() > 100:
            self.events_list.takeItem(100)

        # 2. Update Emotion Bars if emotion changed
        if event.event_type == EventType.EMOTION_STATE_CHANGED:
            vector = event.data.get("state_vector", {})
            self._update_emotion_display(vector)

        # 3. Update AI Telemetry if response completed
        elif event.event_type == EventType.JARVIS_RESPONSE_COMPLETE:
            latency = event.data.get("latency_ms", 0.0)
            tokens = event.data.get("tokens", {})
            model = event.data.get("model", "unknown")
            self.lbl_latency.setText(f"Last Latency: {latency:.1f} ms")
            self.lbl_model.setText(f"Model: {model}")
            p_tok = tokens.get("prompt", 0)
            c_tok = tokens.get("completion", 0)
            t_tok = tokens.get("total", 0)
            self.lbl_tokens.setText(f"Token Usage: prompt={p_tok} | completion={c_tok} | total={t_tok}")

        # 4. Refresh memories if a new memory turn was processed
        elif event.event_type == EventType.USER_INPUT_TEXT:
            self._load_memories()

    def refresh_all(self) -> None:
        """Refreshes all panel tabs."""
        try:
            engine = get_emotion_engine()
            self._update_emotion_display(engine.get_state_vector())
        except Exception:
            pass

        self._load_memories()

    def _update_emotion_display(self, vector: dict):
        for dim_name, val in vector.items():
            if dim_name in self.emotion_bars:
                int_val = int(round(val))
                self.emotion_bars[dim_name].setValue(int_val)
                self.emotion_labels[dim_name].setText(f"{val:.1f}")

    def _load_memories(self, query: str = ""):
        try:
            mgr = get_memory_manager()
            if query.strip():
                items = mgr.search_memories(query.strip())
            else:
                items = mgr.get_all_memories()

            self.mem_table.setRowCount(len(items))
            for row, item in enumerate(items):
                self.mem_table.setItem(row, 0, QTableWidgetItem(item.category))
                self.mem_table.setItem(row, 1, QTableWidgetItem(item.content))
                self.mem_table.setItem(row, 2, QTableWidgetItem(item.created_at[:16]))
        except Exception as e:
            logger.debug(f"Unable to load memories in dev panel: {e}")

    def _filter_memories(self, text: str):
        self._load_memories(text)

    def _purge_memories(self):
        try:
            mgr = get_memory_manager()
            mgr.purge_all_memories()
            self._load_memories()
            logger.info("Purged all memories via Developer Panel")
        except Exception as e:
            logger.error(f"Error purging memories: {e}")

    def _clear_events(self):
        self.events_list.clear()

    def closeEvent(self, event):
        self.bus.unsubscribe_all(self._on_bus_event)
        super().closeEvent(event)
