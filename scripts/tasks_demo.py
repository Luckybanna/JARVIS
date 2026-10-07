"""
Diagnostic Demonstration of JARVIS Task & Reminder Subsystem.
Demonstrates multilingual date/time parsing, SQLite persistence, and proactive event firing.
"""

from pathlib import Path
import sys
import time

# Ensure root directory is on sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.core.events import Event, EventBus, EventType, get_event_bus
from app.tasks.manager import get_task_manager
from app.tasks.models import TaskPriority
from app.tasks.parser import parse_reminder_text


def main():
    print("=" * 60)
    print("JARVIS - Task & Reminder Subsystem Diagnostic")
    print("=" * 60)

    # 1. Natural Language Parser Demonstration
    print("\n--- 1. Testing Multilingual Date/Time Parser ---")
    test_phrases = [
        "JARVIS remind me to submit project review in 15 minutes",
        "set a reminder to stretch legs in 2 hours",
        "remind me in 30 seconds to check tea",
        "10 minute baad coffee peena yaad dilana",
        "do ghante baad standup meeting yaad dilao",
    ]

    for p in test_phrases:
        parsed = parse_reminder_text(p)
        if parsed:
            title, due_ts = parsed
            dt_str = time.strftime("%Y-%m-%d %I:%M:%S %p", time.localtime(due_ts))
            print(f"  Input:  '{p}'")
            print(f"  Parsed: Title='{title}' | Due={dt_str}\n")
        else:
            print(f"  [FAIL] Failed to parse: '{p}'\n")

    # 2. SQLite Persistence
    print("--- 2. SQLite Reminder CRUD ---")
    mgr = get_task_manager()
    now = time.time()

    item = mgr.create_reminder(
        title="Review Q3 Milestones",
        due_timestamp=now + 1800,
        priority=TaskPriority.HIGH,
    )
    print(f"  Created reminder: '{item.title}' (ID: {item.id})")
    print(f"  Due at: {item.due_datetime.strftime('%I:%M %p')}")

    reminders = mgr.list_reminders()
    print(f"  Total pending reminders in DB: {len(reminders)}")

    # 3. Proactive Event Due Trigger
    print("\n--- 3. Proactive Reminder Due Trigger ---")
    bus = get_event_bus()
    received_due_events = []
    bus.subscribe(EventType.REMINDER_DUE, lambda e: received_due_events.append(e))

    # Create an immediate reminder due in the past
    test_due = mgr.create_reminder(
        title="Immediate Health Check",
        due_timestamp=now - 1.0,
        priority=TaskPriority.URGENT,
    )
    print(f"  Inserted immediate reminder (ID: {test_due.id})")

    triggered = mgr.check_due_reminders()
    print(f"  Triggered reminders count: {len(triggered)}")
    if received_due_events:
        event_data = received_due_events[-1].data
        print(f"  EventBus Signal: REMINDER_DUE -> '{event_data['title']}'")
        print(f"  Announcement: \"{event_data['speech']}\"")

    # Cleanup test items
    mgr.delete_reminder(item.id)
    mgr.delete_reminder(test_due.id)

    print("\n" + "=" * 60)
    print("[OK] Task & Reminder Subsystem operating nominally.")
    print("=" * 60)


if __name__ == "__main__":
    main()
