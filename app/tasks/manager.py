"""
Persistent SQLite Task and Reminder Manager for JARVIS.
Handles reminder scheduling, natural language generation, background poller, and EventBus emission.
"""

from datetime import datetime
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional

from app.core.config import DATA_DIR, get_settings
from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.language import detect_language_hint
from app.core.logger import get_logger
from app.tasks.models import ReminderItem, TaskPriority, TaskStatus
from app.tasks.parser import parse_reminder_text

logger = get_logger("tasks.manager")


class TaskManager:
    """
    Manages persistent reminders, background polling for due events, and natural language creation.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        event_bus: Optional[EventBus] = None,
        poll_interval_sec: float = 2.0,
        auto_start_poller: bool = True,
    ):
        self.db_path = Path(db_path).resolve() if db_path else (DATA_DIR / "jarvis_memory.db")
        self.bus = event_bus or get_event_bus()
        self.poll_interval = poll_interval_sec

        self._lock = threading.RLock()
        self._poller_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._init_db()

        if auto_start_poller:
            self.start_poller()

        logger.info(f"TaskManager initialized with DB at {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initializes reminders schema."""
        with self._lock, self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_timestamp REAL NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    completed_at REAL,
                    is_recurring INTEGER DEFAULT 0,
                    recurrence_interval_sec REAL DEFAULT 0.0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_due_status ON reminders(due_timestamp, status)")
            conn.commit()

    def create_reminder(
        self,
        title: str,
        due_timestamp: float,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        is_recurring: bool = False,
        recurrence_interval_sec: float = 0.0,
    ) -> ReminderItem:
        """Creates and stores a new scheduled reminder."""
        item = ReminderItem(
            title=title.strip(),
            due_timestamp=due_timestamp,
            description=description.strip(),
            priority=priority,
            status=TaskStatus.PENDING,
            is_recurring=is_recurring,
            recurrence_interval_sec=recurrence_interval_sec,
        )

        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO reminders (
                    id, title, description, due_timestamp, priority, status,
                    created_at, completed_at, is_recurring, recurrence_interval_sec
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.title,
                    item.description,
                    item.due_timestamp,
                    item.priority.value,
                    item.status.value,
                    item.created_at,
                    item.completed_at,
                    1 if item.is_recurring else 0,
                    item.recurrence_interval_sec,
                ),
            )
            conn.commit()

        logger.info(f"Created reminder '{item.title}' due at {item.due_datetime} (id: {item.id})")
        self.bus.publish(Event(
            event_type=EventType.TASK_CREATED,
            data=item.to_dict(),
            source="tasks.manager",
        ))
        return item

    def list_reminders(self, include_completed: bool = False) -> List[ReminderItem]:
        """Lists active or all reminders ordered by due date."""
        query = "SELECT * FROM reminders"
        if not include_completed:
            query += " WHERE status = 'pending'"
        query += " ORDER BY due_timestamp ASC"

        with self._lock, self._get_connection() as conn:
            rows = conn.execute(query).fetchall()

        items = []
        for r in rows:
            items.append(
                ReminderItem(
                    id=r["id"],
                    title=r["title"],
                    description=r["description"] or "",
                    due_timestamp=r["due_timestamp"],
                    priority=TaskPriority(r["priority"]),
                    status=TaskStatus(r["status"]),
                    created_at=r["created_at"],
                    completed_at=r["completed_at"],
                    is_recurring=bool(r["is_recurring"]),
                    recurrence_interval_sec=r["recurrence_interval_sec"],
                )
            )
        return items

    def get_reminder(self, reminder_id: str) -> Optional[ReminderItem]:
        """Retrieves a reminder by ID."""
        with self._lock, self._get_connection() as conn:
            r = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
            if not r:
                return None
            return ReminderItem(
                id=r["id"],
                title=r["title"],
                description=r["description"] or "",
                due_timestamp=r["due_timestamp"],
                priority=TaskPriority(r["priority"]),
                status=TaskStatus(r["status"]),
                created_at=r["created_at"],
                completed_at=r["completed_at"],
                is_recurring=bool(r["is_recurring"]),
                recurrence_interval_sec=r["recurrence_interval_sec"],
            )

    def complete_reminder(self, reminder_id: str) -> bool:
        """Marks a reminder as completed."""
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                "UPDATE reminders SET status = ?, completed_at = ? WHERE id = ?",
                (TaskStatus.COMPLETED.value, time.time(), reminder_id),
            )
            conn.commit()
            return cur.rowcount > 0

    def delete_reminder(self, reminder_id: str) -> bool:
        """Removes a reminder from SQLite."""
        with self._lock, self._get_connection() as conn:
            cur = conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            conn.commit()
            return cur.rowcount > 0

    def clear_all(self) -> None:
        """Deletes all reminders (used for tests/reset)."""
        with self._lock, self._get_connection() as conn:
            conn.execute("DELETE FROM reminders")
            conn.commit()

    def process_turn(self, user_text: str) -> Optional[str]:
        """
        Parses user message for reminder requests.
        If found, schedules the reminder and returns a conversational response string.
        """
        parsed = parse_reminder_text(user_text)
        if not parsed:
            return None

        title, due_ts = parsed
        item = self.create_reminder(title=title, due_timestamp=due_ts)
        lang = detect_language_hint(user_text)

        dt_str = item.due_datetime.strftime("%I:%M %p on %d %b")
        if lang == "hi":
            return f"Sir, maine '{item.title}' ke liye reminder set kar diya hai ({dt_str})."
        return f"Reminder confirmed, Sir: '{item.title}' scheduled for {dt_str}."

    def check_due_reminders(self) -> List[ReminderItem]:
        """Checks for due reminders and dispatches events."""
        now = time.time()
        with self._lock, self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE status = 'pending' AND due_timestamp <= ?",
                (now,),
            ).fetchall()

            triggered_items: List[ReminderItem] = []
            for r in rows:
                item = ReminderItem(
                    id=r["id"],
                    title=r["title"],
                    description=r["description"] or "",
                    due_timestamp=r["due_timestamp"],
                    priority=TaskPriority(r["priority"]),
                    status=TaskStatus.TRIGGERED,
                    created_at=r["created_at"],
                    completed_at=None,
                    is_recurring=bool(r["is_recurring"]),
                    recurrence_interval_sec=r["recurrence_interval_sec"],
                )
                triggered_items.append(item)

                # Update status
                conn.execute(
                    "UPDATE reminders SET status = ? WHERE id = ?",
                    (TaskStatus.TRIGGERED.value, item.id),
                )

                # If recurring, insert next iteration
                if item.is_recurring and item.recurrence_interval_sec > 0:
                    next_ts = item.due_timestamp + item.recurrence_interval_sec
                    conn.execute(
                        """
                        INSERT INTO reminders (
                            id, title, description, due_timestamp, priority, status,
                            created_at, completed_at, is_recurring, recurrence_interval_sec
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            f"{item.id}_rec",
                            item.title,
                            item.description,
                            next_ts,
                            item.priority.value,
                            TaskStatus.PENDING.value,
                            time.time(),
                            None,
                            1,
                            item.recurrence_interval_sec,
                        ),
                    )

            conn.commit()

        # Emit events outside DB transaction
        for item in triggered_items:
            logger.info(f"Reminder DUE: '{item.title}' (id: {item.id})")
            self.bus.publish(Event(
                event_type=EventType.REMINDER_DUE,
                data={
                    "id": item.id,
                    "title": item.title,
                    "due_timestamp": item.due_timestamp,
                    "speech": f"Sir, reminder for you: {item.title}.",
                },
                source="tasks.manager",
            ))

        return triggered_items

    def start_poller(self) -> None:
        """Starts background poller thread."""
        if self._poller_thread and self._poller_thread.is_alive():
            return

        self._stop_event.clear()
        self._poller_thread = threading.Thread(target=self._run_poller, daemon=True, name="JarvisReminderPoller")
        self._poller_thread.start()
        logger.debug("Reminder poller thread started.")

    def stop_poller(self) -> None:
        """Stops background poller thread."""
        self._stop_event.set()
        if self._poller_thread and self._poller_thread.is_alive():
            self._poller_thread.join(timeout=1.0)
            self._poller_thread = None
        logger.debug("Reminder poller thread stopped.")

    def _run_poller(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.check_due_reminders()
            except Exception as e:
                logger.error(f"Error in reminder poller: {e}", exc_info=True)
            self._stop_event.wait(self.poll_interval)


_task_manager_instance: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Singleton getter for TaskManager."""
    global _task_manager_instance
    if _task_manager_instance is None:
        _task_manager_instance = TaskManager()
    return _task_manager_instance
