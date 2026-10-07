"""
Comprehensive Unit Tests for JARVIS Task and Reminder Subsystem.
Tests multilingual date/time parsing, SQLite persistence, background polling,
recurring reminders, and ConversationManager integration.
"""

from datetime import datetime
import time
from unittest.mock import MagicMock

import pytest

from app.ai.base import AIProvider, AIResponse, TokenUsage
from app.core.conversation import ConversationManager
from app.core.events import Event, EventBus, EventType
from app.tasks.manager import TaskManager
from app.tasks.models import ReminderItem, TaskPriority, TaskStatus
from app.tasks.parser import parse_reminder_text


class MockAIProvider(AIProvider):
    def __init__(self):
        super().__init__(model_name="mock-model")

    @property
    def provider_name(self) -> str:
        return "mock"

    def health_check(self) -> bool:
        return True

    def generate(self, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
        return AIResponse(content="Mock response", model=self.model_name)

    def stream(self, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
        yield "Mock"


def test_parser_relative_time_english():
    """Test relative time extraction in English."""
    now = time.time()

    # 10 minutes
    res = parse_reminder_text("JARVIS, please remind me to call Mom in 10 minutes")
    assert res is not None
    title, due = res
    assert "call mom" in title.lower()
    assert 590 <= (due - now) <= 610

    # 2 hours
    res2 = parse_reminder_text("set a reminder to submit report in 2 hours")
    assert res2 is not None
    title2, due2 = res2
    assert "submit report" in title2.lower()
    assert 7190 <= (due2 - now) <= 7210

    # 45 seconds
    res3 = parse_reminder_text("remind me in 45 seconds to check the oven")
    assert res3 is not None
    title3, due3 = res3
    assert "check the oven" in title3.lower()
    assert 40 <= (due3 - now) <= 50


def test_parser_hindi_and_hinglish():
    """Test relative and absolute time extraction in Hindi/Hinglish."""
    now = time.time()

    # 15 minute baad
    res1 = parse_reminder_text("15 minute baad pizza nikalna yaad dilana")
    assert res1 is not None
    title1, due1 = res1
    assert "pizza nikalna" in title1.lower()
    assert 890 <= (due1 - now) <= 910

    # do ghante baad
    res2 = parse_reminder_text("do ghante baad meeting yaad dilao")
    assert res2 is not None
    title2, due2 = res2
    assert "meeting" in title2.lower()
    assert 7190 <= (due2 - now) <= 7210

    # Non-reminder text should return None
    res_none = parse_reminder_text("What is the capital of France?")
    assert res_none is None


def test_task_manager_sqlite_crud(tmp_path):
    """Test SQLite CRUD operations on reminders."""
    db_file = tmp_path / "test_tasks.db"
    bus = EventBus()
    mgr = TaskManager(db_path=db_file, event_bus=bus, auto_start_poller=False)

    now = time.time()
    # 1. Create reminder
    item = mgr.create_reminder(
        title="Deploy release",
        due_timestamp=now + 3600,
        priority=TaskPriority.HIGH,
    )
    assert item.id is not None
    assert item.title == "Deploy release"
    assert item.priority == TaskPriority.HIGH
    assert item.status == TaskStatus.PENDING

    # 2. List reminders
    items = mgr.list_reminders()
    assert len(items) == 1
    assert items[0].id == item.id

    # 3. Get single reminder
    fetched = mgr.get_reminder(item.id)
    assert fetched is not None
    assert fetched.title == "Deploy release"

    # 4. Complete reminder
    completed = mgr.complete_reminder(item.id)
    assert completed is True

    # Active list should now be empty
    active_items = mgr.list_reminders(include_completed=False)
    assert len(active_items) == 0

    all_items = mgr.list_reminders(include_completed=True)
    assert len(all_items) == 1
    assert all_items[0].status == TaskStatus.COMPLETED

    # 5. Delete reminder
    deleted = mgr.delete_reminder(item.id)
    assert deleted is True
    assert mgr.get_reminder(item.id) is None


def test_task_manager_due_events_and_recurring(tmp_path):
    """Test triggering due reminders and recurring intervals."""
    db_file = tmp_path / "test_due.db"
    bus = EventBus()
    mgr = TaskManager(db_path=db_file, event_bus=bus, auto_start_poller=False)

    due_events = []
    bus.subscribe(EventType.REMINDER_DUE, lambda e: due_events.append(e))

    now = time.time()
    # Create reminder already in the past (due immediately)
    item_one_shot = mgr.create_reminder(
        title="Drink water",
        due_timestamp=now - 5,
        is_recurring=False,
    )

    # Create recurring reminder
    item_recurring = mgr.create_reminder(
        title="Stretch legs",
        due_timestamp=now - 2,
        is_recurring=True,
        recurrence_interval_sec=1800,  # 30 mins
    )

    # Execute due check
    triggered = mgr.check_due_reminders()
    assert len(triggered) == 2
    assert len(due_events) == 2

    # Verify event data
    titles = [e.data["title"] for e in due_events]
    assert "Drink water" in titles
    assert "Stretch legs" in titles

    # Verify original items marked as TRIGGERED
    updated_one_shot = mgr.get_reminder(item_one_shot.id)
    assert updated_one_shot.status == TaskStatus.TRIGGERED

    # Verify new recurring instance was scheduled
    active = mgr.list_reminders(include_completed=False)
    assert len(active) == 1
    assert active[0].title == "Stretch legs"
    assert active[0].due_timestamp > now


def test_conversation_manager_task_integration(tmp_path):
    """Test ConversationManager natural language reminder scheduling."""
    db_file = tmp_path / "test_conv_tasks.db"
    bus = EventBus()
    mgr = TaskManager(db_path=db_file, event_bus=bus, auto_start_poller=False)
    provider = MockAIProvider()

    conv = ConversationManager(
        provider=provider,
        event_bus=bus,
        task_manager=mgr,
    )

    # User schedules a reminder
    response = conv.send_user_message("JARVIS, remind me to check the oven in 15 minutes")
    assert response.model == "tasks.manager"
    assert "reminder confirmed" in response.content.lower() or "scheduled" in response.content.lower()
    assert "check the oven" in response.content.lower()

    # Verify reminder exists in database
    active = mgr.list_reminders()
    assert len(active) == 1
    assert "check the oven" in active[0].title.lower()

    # General conversation still falls through to AI provider
    general_resp = conv.send_user_message("Hello, how are you?")
    assert general_resp.model == "mock-model"
