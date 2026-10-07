"""
Unit and behavioral tests for JARVIS Proactive Conversation Engine and Anti-Annoyance Policies.
"""

from datetime import datetime
import time
import pytest

from app.core.config import Settings
from app.core.events import Event, EventBus, EventType
from app.proactive.rules import ProactiveDecision, ProactiveRulePolicy
from app.proactive.triggers import (
    ProactiveTrigger,
    TriggerType,
    WorkActivityTracker,
)
from app.proactive.engine import ProactiveEngine


def test_quiet_hours_overnight_logic():
    # 23:00 to 07:00
    t_midnight = datetime(2026, 10, 7, 2, 30)  # 02:30 AM
    assert ProactiveRulePolicy.is_in_quiet_hours("23:00", "07:00", t_midnight) is True

    t_late_night = datetime(2026, 10, 7, 23, 15)  # 11:15 PM
    assert ProactiveRulePolicy.is_in_quiet_hours("23:00", "07:00", t_late_night) is True

    t_morning = datetime(2026, 10, 7, 6, 45)  # 06:45 AM
    assert ProactiveRulePolicy.is_in_quiet_hours("23:00", "07:00", t_morning) is True

    t_daytime = datetime(2026, 10, 7, 14, 00)  # 02:00 PM
    assert ProactiveRulePolicy.is_in_quiet_hours("23:00", "07:00", t_daytime) is False


def test_anti_annoyance_policy_dnd_and_meeting():
    policy = ProactiveRulePolicy()
    settings = Settings()

    # DND Enabled
    settings.do_not_disturb = True
    settings.meeting_mode = False
    allowed, reason = policy.evaluate_interruption_policy(settings=settings)
    assert allowed is False
    assert "Do Not Disturb" in reason

    # Meeting Mode Enabled
    settings.do_not_disturb = False
    settings.meeting_mode = True
    allowed, reason = policy.evaluate_interruption_policy(settings=settings)
    assert allowed is False
    assert "Meeting Mode" in reason


def test_anti_annoyance_user_speaking_block():
    policy = ProactiveRulePolicy()
    settings = Settings()
    settings.do_not_disturb = False
    settings.meeting_mode = False
    settings.quiet_hours_enabled = False

    allowed, reason = policy.evaluate_interruption_policy(
        settings=settings,
        is_user_speaking=True,
    )
    assert allowed is False
    assert "User is actively speaking" in reason


def test_anti_annoyance_cooldown_and_rate_limits():
    policy = ProactiveRulePolicy()
    settings = Settings()
    settings.do_not_disturb = False
    settings.meeting_mode = False
    settings.quiet_hours_enabled = False
    settings.min_proactive_interval_min = 45
    settings.max_proactive_per_hour = 2

    now = 1000000.0

    # Test Cooldown: last message was spoken 15 minutes ago
    history_recent = [now - (15 * 60)]
    allowed, reason = policy.evaluate_interruption_policy(
        settings=settings,
        proactive_history=history_recent,
        current_time=now,
    )
    assert allowed is False
    assert "Cooldown active" in reason

    # Test Hourly Limit: 2 messages already delivered within the last hour
    history_hourly = [now - (50 * 60), now - (46 * 60)]
    allowed, reason = policy.evaluate_interruption_policy(
        settings=settings,
        proactive_history=history_hourly,
        current_time=now,
    )
    assert allowed is False
    assert "Hourly proactive quota reached" in reason

    # Test Allowed: 1 message 60 minutes ago
    history_allowed = [now - (60 * 60)]
    allowed, reason = policy.evaluate_interruption_policy(
        settings=settings,
        proactive_history=history_allowed,
        current_time=now,
    )
    assert allowed is True
    assert "passed" in reason


def test_work_activity_tracker_break_suggestion():
    tracker = WorkActivityTracker(break_threshold_minutes=90)
    base_time = 100000.0
    tracker.session_start_time = base_time
    tracker.last_activity_time = base_time

    # At 45 minutes: no suggestion
    assert tracker.check_break_suggestion_needed(current_time=base_time + (45 * 60)) is None

    # At 95 minutes: suggestion triggered
    trigger = tracker.check_break_suggestion_needed(current_time=base_time + (95 * 60))
    assert trigger is not None
    assert trigger.trigger_type == TriggerType.WORK_BREAK_SUGGESTION
    assert "continuously kaam kar rahe hain" in trigger.message
    assert "break" in trigger.message


def test_proactive_engine_decision_pipeline():
    bus = EventBus()
    events = []
    bus.subscribe_all(lambda e: events.append(e))

    settings = Settings()
    settings.do_not_disturb = False
    settings.meeting_mode = False
    settings.quiet_hours_enabled = False

    engine = ProactiveEngine(settings=settings, event_bus=bus)

    # 1. No trigger -> DO NOT SPEAK
    decision_idle = engine.should_jarvis_speak_now()
    assert decision_idle.should_speak is False
    assert "No active trigger" in decision_idle.reason

    # 2. Candidate trigger when all clear -> ALLOWED
    candidate = ProactiveTrigger(
        trigger_type=TriggerType.WORK_BREAK_SUGGESTION,
        message="Aap kaafi der se kaam kar rahe hain. Break lena hai?",
    )
    decision_allowed = engine.should_jarvis_speak_now(candidate_trigger=candidate)
    assert decision_allowed.should_speak is True
    assert "ALLOWED" in decision_allowed.reason
    assert "Aap kaafi der se" in decision_allowed.proposed_message

    # Verify event bus received trigger evaluated & message proposed
    event_types = [e.event_type for e in events]
    assert EventType.PROACTIVE_TRIGGER_EVALUATED in event_types
    assert EventType.PROACTIVE_MESSAGE_PROPOSED in event_types

    # 3. Simulate DND enabled -> DO NOT SPEAK
    settings.do_not_disturb = True
    decision_blocked = engine.should_jarvis_speak_now(candidate_trigger=candidate)
    assert decision_blocked.should_speak is False
    assert "Do Not Disturb" in decision_blocked.reason
