"""
Data models for JARVIS Task and Reminder subsystem.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import time
from typing import Any, Dict, Optional
import uuid


class TaskPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TaskStatus(str, Enum):
    PENDING = "pending"
    TRIGGERED = "triggered"
    COMPLETED = "completed"
    DISMISSED = "dismissed"


@dataclass
class ReminderItem:
    """Representation of a persistent scheduled reminder."""
    title: str
    due_timestamp: float
    description: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    is_recurring: bool = False
    recurrence_interval_sec: float = 0.0

    @property
    def due_datetime(self) -> datetime:
        return datetime.fromtimestamp(self.due_timestamp)

    @property
    def is_due(self) -> bool:
        return self.status == TaskStatus.PENDING and time.time() >= self.due_timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "due_timestamp": self.due_timestamp,
            "due_datetime_str": self.due_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "is_recurring": self.is_recurring,
            "recurrence_interval_sec": self.recurrence_interval_sec,
        }
