"""
Unit Tests for JARVIS Desktop HUD and Developer Telemetry Panel.
Tests offscreen Qt rendering, audio visualizer, message bubbles,
developer panel telemetry updates, and main window lifecycle.
"""

import os
import sys
import time

# Ensure headless Qt execution in automated test runs
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PyQt6.QtWidgets import QApplication

from app.ai.base import AIProvider, AIResponse, TokenUsage
from app.core.conversation import ConversationManager
from app.core.events import Event, EventBus, EventType
from app.ui.audio_visualizer import AudioVisualizerWidget
from app.ui.chat_feed import ChatFeedWidget
from app.ui.dev_panel import DeveloperPanel
from app.ui.main_window import JarvisMainWindow


class MockAIProvider(AIProvider):
    def __init__(self):
        super().__init__(model_name="mock-model")

    @property
    def provider_name(self) -> str:
        return "mock"

    def health_check(self) -> bool:
        return True

    def generate(self, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
        return AIResponse(content="Yes, Sir.", model=self.model_name, latency_ms=45.0)

    def stream(self, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
        yield "Yes, Sir."


@pytest.fixture(scope="session")
def qapp():
    """Session-level QApplication instance for offscreen widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_audio_visualizer_widget(qapp):
    """Test AudioVisualizerWidget initialization, level setting, and decay."""
    viz = AudioVisualizerWidget(num_bars=16)
    assert viz.num_bars == 16
    assert len(viz._bar_heights) == 16

    # Set audio level
    viz.set_level(0.85)
    assert viz._level == 0.85
    assert any(h > 0 for h in viz._target_heights)

    # Advance tick
    viz._on_tick()
    assert any(h > 0 for h in viz._bar_heights)

    viz.close()


def test_chat_feed_widget(qapp):
    """Test ChatFeedWidget bubble generation and clearing."""
    feed = ChatFeedWidget()
    # Initially 1 item (bottom stretch)
    assert feed.layout.count() >= 1

    # Add user message
    feed.add_user_message("Hello JARVIS")
    assert feed.layout.count() >= 2

    # Add JARVIS message
    feed.add_jarvis_message("Good evening, Sir.", model_tag="GEMINI")
    assert feed.layout.count() >= 3

    # Clear feed
    feed.clear_feed()
    assert feed.layout.count() == 1


def test_developer_panel(qapp):
    """Test DeveloperPanel tabs, emotion bar updates, and event stream."""
    bus = EventBus()
    panel = DeveloperPanel(event_bus=bus)

    assert panel.tabs.count() == 4
    assert len(panel.emotion_bars) == 9

    # Trigger emotion update event
    bus.publish(Event(
        event_type=EventType.EMOTION_STATE_CHANGED,
        data={"state_vector": {"happiness": 85.0, "curiosity": 90.0}},
        source="test",
    ))
    qapp.processEvents()

    assert panel.emotion_bars["happiness"].value() == 85
    assert panel.emotion_bars["curiosity"].value() == 90

    # Trigger AI response complete event
    bus.publish(Event(
        event_type=EventType.JARVIS_RESPONSE_COMPLETE,
        data={
            "latency_ms": 134.5,
            "tokens": {"prompt": 12, "completion": 24, "total": 36},
            "model": "gemini-2.5-flash",
        },
        source="test",
    ))
    qapp.processEvents()

    assert "134.5" in panel.lbl_latency.text()
    assert "gemini-2.5-flash" in panel.lbl_model.text()

    # Verify event logged in list
    assert panel.events_list.count() >= 2

    panel.close()


def test_jarvis_main_window_lifecycle(qapp):
    """Test JarvisMainWindow instantiation, dev panel toggle, and turn dispatch."""
    bus = EventBus()
    provider = MockAIProvider()
    conv = ConversationManager(provider=provider, event_bus=bus)

    window = JarvisMainWindow(
        conversation_manager=conv,
        event_bus=bus,
        show_dev_panel=False,
    )

    assert window.dev_panel.isHidden() is True

    # Toggle Dev Panel
    window._toggle_dev_panel()
    assert window.dev_panel.isHidden() is False

    window._toggle_dev_panel()
    assert window.dev_panel.isHidden() is True

    # Show window and send input
    window.show()
    window._submit_text_input("Run diagnostic check")
    time.sleep(0.1)
    qapp.processEvents()

    assert window.chat_feed.layout.count() >= 3

    window.close()
