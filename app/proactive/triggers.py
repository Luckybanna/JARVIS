"""
Proactive Triggers and Contextual Activity Monitors for JARVIS.
Detects long continuous work sessions, task follow-ups, and scheduled reminder events.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Dict, List, Optional

from app.core.config import Settings, get_settings
from app.memory.manager import MemoryManager, get_memory_manager


class TriggerType(str, Enum):
    WORK_BREAK_SUGGESTION = "work_break_suggestion"
    TASK_FOLLOWUP = "task_followup"
    REMINDER_ALERT = "reminder_alert"
    SYSTEM_NOTIFICATION = "system_notification"


@dataclass
class ProactiveTrigger:
    """Represents a potential reason for JARVIS to initiate a conversation."""
    trigger_type: TriggerType
    message: str
    priority: int = 3  # 1 (lowest) to 5 (highest, e.g. urgent reminder)
    context_data: Dict[str, any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class WorkActivityTracker:
    """Tracks continuous user activity to suggest healthy breaks without annoyance."""

    def __init__(self, break_threshold_minutes: Optional[int] = None):
        settings = get_settings()
        self.threshold_minutes = (
            break_threshold_minutes or settings.break_suggestion_work_min
        )
        self.session_start_time = time.time()
        self.last_activity_time = time.time()
        self.last_break_suggested_time: Optional[float] = None

    def record_activity(self) -> None:
        """Called whenever the user interacts with JARVIS or system activity is detected."""
        now = time.time()
        # If user was inactive for > 20 minutes, assume they took a break and reset session
        if (now - self.last_activity_time) > (20 * 60):
            self.session_start_time = now
        self.last_activity_time = now

    def check_break_suggestion_needed(self, current_time: Optional[float] = None) -> Optional[ProactiveTrigger]:
        """Evaluates whether continuous work duration exceeds the suggestion threshold."""
        now = current_time or time.time()
        active_minutes = (now - self.session_start_time) / 60.0

        if active_minutes >= self.threshold_minutes:
            # Check if we already suggested a break in this continuous window
            if self.last_break_suggested_time is None or (now - self.last_break_suggested_time) > (self.threshold_minutes * 60):
                self.last_break_suggested_time = now
                msg = (
                    f"Aap kaafi der se ({int(active_minutes)} minutes) continuously kaam kar rahe hain. "
                    "Ek short break lena useful ho sakta hai."
                )
                return ProactiveTrigger(
                    trigger_type=TriggerType.WORK_BREAK_SUGGESTION,
                    message=msg,
                    priority=2,
                    context_data={"continuous_minutes": int(active_minutes)},
                )
        return None


class TaskFollowupTracker:
    """Checks stored user projects and tasks to propose natural, contextual follow-ups."""

    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory_manager = memory_manager or get_memory_manager()
        self.last_followup_time: Optional[float] = None

    def check_project_followup(self, current_time: Optional[float] = None) -> Optional[ProactiveTrigger]:
        """Looks for recorded projects in long-term memory to formulate a helpful follow-up."""
        projects = self.memory_manager.get_all_memories(category="project")
        if not projects:
            return None

        # Pick the most important or recent project
        top_project = projects[0]
        msg = f"Aapne jo project '{top_project.content}' mention kiya tha, kya uska status review karna hai?"

        return ProactiveTrigger(
            trigger_type=TriggerType.TASK_FOLLOWUP,
            message=msg,
            priority=2,
            context_data={"project": top_project.content},
        )
