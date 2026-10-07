"""
Unit Tests for JARVIS Animated Avatar Subsystem.
Tests visual theme definitions, state transitions, EventBus reactive coordination,
and PyQt6 geometric Arc-Reactor rendering.
"""

import os
import sys
import time

# Ensure headless Qt operation in automated test runs
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PyQt6.QtWidgets import QApplication

from app.avatar.controller import AvatarController
from app.avatar.renderer import AvatarRendererWidget
from app.avatar.state import AvatarState, AvatarTheme, StateVisualConfig
from app.core.events import Event, EventBus, EventType


@pytest.fixture(scope="session")
def qapp():
    """Session-level QApplication instance for offscreen widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def test_avatar_states_and_theme_palette():
    """Verify all 10 avatar states are defined with valid visual configs."""
    expected_states = [
        AvatarState.IDLE,
        AvatarState.LISTENING,
        AvatarState.THINKING,
        AvatarState.SPEAKING,
        AvatarState.HAPPY,
        AvatarState.CONCERNED,
        AvatarState.SAD,
        AvatarState.ANGRY,
        AvatarState.SURPRISED,
        AvatarState.SLEEPING,
    ]
    assert len(expected_states) == 10

    for state in expected_states:
        cfg = AvatarTheme.get_config(state)
        assert isinstance(cfg, StateVisualConfig)
        assert len(cfg.primary_color) == 3
        assert len(cfg.glow_color) == 3
        for val in cfg.primary_color + cfg.glow_color:
            assert 0 <= val <= 255
        assert cfg.rotation_speed >= 0.0
        assert cfg.pulse_freq > 0.0
        assert 0.5 <= cfg.base_scale <= 2.0
        assert len(cfg.description) > 0


def test_avatar_controller_state_and_audio():
    """Test manual state changes, audio level clamping, and temporary revert."""
    bus = EventBus()
    controller = AvatarController(event_bus=bus)

    assert controller.current_state == AvatarState.IDLE
    assert controller.audio_level == 0.0

    # Audio level clamping
    controller.set_audio_level(0.75)
    assert controller.audio_level == 0.75
    controller.set_audio_level(1.5)
    assert controller.audio_level == 1.0
    controller.set_audio_level(-0.2)
    assert controller.audio_level == 0.0

    # Manual state setting
    controller.set_state(AvatarState.THINKING)
    assert controller.current_state == AvatarState.THINKING
    assert controller.visual_config.description == AvatarTheme.get_config(AvatarState.THINKING).description

    # Reset
    controller.reset()
    assert controller.current_state == AvatarState.IDLE
    assert controller.audio_level == 0.0

    # Temporary state revert
    controller.set_state(AvatarState.HAPPY, duration=0.2)
    assert controller.current_state == AvatarState.HAPPY
    time.sleep(0.3)
    assert controller.current_state == AvatarState.IDLE

    controller.unsubscribe_events()


def test_avatar_controller_eventbus_integration():
    """Test automated avatar state transitions driven by EventBus events."""
    bus = EventBus()
    controller = AvatarController(event_bus=bus)

    published_events = []
    bus.subscribe(EventType.AVATAR_STATE_CHANGED, lambda e: published_events.append(e))

    # 1. Mic listening
    bus.publish(Event(event_type=EventType.MIC_LISTENING_START))
    assert controller.current_state == AvatarState.LISTENING

    # Speech detected with RMS amplitude
    bus.publish(Event(event_type=EventType.SPEECH_DETECTED, data={"rms": 1500}))
    assert controller.audio_level > 0.0

    bus.publish(Event(event_type=EventType.MIC_LISTENING_STOP))
    assert controller.current_state == AvatarState.IDLE
    assert controller.audio_level == 0.0

    # 2. Thinking phase
    bus.publish(Event(event_type=EventType.JARVIS_THINKING_START))
    assert controller.current_state == AvatarState.THINKING
    bus.publish(Event(event_type=EventType.JARVIS_THINKING_STOP))
    assert controller.current_state == AvatarState.IDLE

    # 3. Speech synthesis & barge-in
    bus.publish(Event(event_type=EventType.TTS_SPEAKING_START))
    assert controller.current_state == AvatarState.SPEAKING
    bus.publish(Event(event_type=EventType.TTS_INTERRUPTED))
    assert controller.current_state == AvatarState.IDLE

    # 4. Internal emotion integration
    bus.publish(Event(
        event_type=EventType.EMOTION_STATE_CHANGED,
        data={"state_vector": {"anger": 65.0, "sadness": 10.0, "concern": 20.0, "happiness": 10.0}}
    ))
    assert controller.current_state == AvatarState.ANGRY

    # 5. User emotion reaction
    bus.publish(Event(
        event_type=EventType.USER_EMOTION_DETECTED,
        data={"detected_emotion": "frustrated"}
    ))
    assert controller.current_state == AvatarState.CONCERNED

    assert len(published_events) > 0
    controller.unsubscribe_events()


def test_avatar_renderer_widget(qapp):
    """Test AvatarRendererWidget rendering, frame advancing, and pixmap generation."""
    bus = EventBus()
    controller = AvatarController(event_bus=bus)

    widget = AvatarRendererWidget(controller=controller, enable_timer=False)
    assert widget.width() >= 0
    assert widget.height() >= 0

    # Initial state
    assert widget._current_state == AvatarState.IDLE

    # Advance frames and verify rotation & interpolation
    initial_angle = widget._outer_angle
    widget.advance_frame(dt=0.05)
    assert widget._outer_angle != initial_angle

    # Switch state and advance frame
    widget.set_state(AvatarState.THINKING)
    widget.advance_frame(dt=0.1)
    target_primary = AvatarTheme.get_config(AvatarState.THINKING).primary_color
    # Color should be interpolating toward target
    assert widget._current_primary != AvatarTheme.get_config(AvatarState.IDLE).primary_color

    # Audio reactivity
    widget.set_audio_level(0.8)
    assert widget._audio_level == 0.8

    # Render to offscreen QPixmap
    pixmap = widget.render_to_pixmap(240, 240)
    assert not pixmap.isNull()
    assert pixmap.width() == 240
    assert pixmap.height() == 240

    controller.unsubscribe_events()
    widget.close()
