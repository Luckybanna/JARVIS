"""
Proactive Triggers and Contextual Activity Monitors for JARVIS.
Detects long continuous work sessions, task follow-ups, and scheduled reminder events.
"""

from dataclasses import dataclass, field
from datetime import datetime
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
    CARE_AND_WELLBEING = "care_and_wellbeing"
    RESOURCE_WARNING = "resource_warning"


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


class WellbeingCareTracker:
    """Tracks time of day to offer thoughtful, human-like care check-ins (meals, hydration, late hours)."""

    def __init__(self):
        self._last_care_check: Dict[str, float] = {}

    def check_wellbeing_trigger(self, current_time: Optional[float] = None) -> Optional[ProactiveTrigger]:
        now_ts = current_time or time.time()
        now_dt = datetime.fromtimestamp(now_ts)
        hour = now_dt.hour
        today_str = now_dt.strftime("%Y-%m-%d")

        # 1. Lunch check (13:00 - 15:00)
        if 13 <= hour < 15:
            key = f"lunch_{today_str}"
            if key not in self._last_care_check:
                self._last_care_check[key] = now_ts
                return ProactiveTrigger(
                    trigger_type=TriggerType.CARE_AND_WELLBEING,
                    message="Sir, dopahar ho gayi hai. Khana khaya aapne? Kaam thoda pause karke lunch kar lijiye.",
                    priority=2,
                    context_data={"care_type": "lunch"},
                )

        # 2. Evening tea break (17:00 - 18:30)
        elif 17 <= hour < 19:
            key = f"tea_{today_str}"
            if key not in self._last_care_check:
                self._last_care_check[key] = now_ts
                return ProactiveTrigger(
                    trigger_type=TriggerType.CARE_AND_WELLBEING,
                    message="Sir, kaafi der se kaam kar rahe hain aap. Thodi chai ya coffee ka break le lijiye!",
                    priority=2,
                    context_data={"care_type": "tea"},
                )

        # 3. Dinner check (20:30 - 22:30)
        elif 20 <= hour < 23:
            key = f"dinner_{today_str}"
            if key not in self._last_care_check:
                self._last_care_check[key] = now_ts
                return ProactiveTrigger(
                    trigger_type=TriggerType.CARE_AND_WELLBEING,
                    message="Sir, dinner ka time ho gaya hai. Kya aapne khana kha liya ya abhi kaam mein busy hain?",
                    priority=2,
                    context_data={"care_type": "dinner"},
                )

        # 4. Late night reminder (23:30 - 03:00)
        elif hour >= 23 or hour < 3:
            key = f"latenight_{today_str}"
            if key not in self._last_care_check:
                self._last_care_check[key] = now_ts
                return ProactiveTrigger(
                    trigger_type=TriggerType.CARE_AND_WELLBEING,
                    message="Sir, kafi raat ho gayi hai aur aap abhi tak kaam kar rahe hain. Please zyada der screen ke samne mat baithiye, rest lena bhi zaroori hai.",
                    priority=2,
                    context_data={"care_type": "late_night"},
                )

        return None


class SystemResourceMonitorTracker:
    """Monitors CPU and RAM usage and proactively alerts if resources are heavily constrained."""

    def __init__(self, ram_threshold: float = 85.0, cpu_threshold: float = 85.0, cooldown_seconds: float = 1800.0):
        self.ram_threshold = ram_threshold
        self.cpu_threshold = cpu_threshold
        self.cooldown_seconds = cooldown_seconds
        self.last_alert_time: Optional[float] = None

    def check_resource_warning(self, current_time: Optional[float] = None) -> Optional[ProactiveTrigger]:
        now = current_time or time.time()
        if self.last_alert_time and (now - self.last_alert_time) < self.cooldown_seconds:
            return None

        try:
            import psutil
            mem = psutil.virtual_memory()
            cpu = psutil.cpu_percent(interval=None)
            ram_pct = mem.percent

            if ram_pct >= self.ram_threshold or cpu >= self.cpu_threshold:
                self.last_alert_time = now
                if ram_pct >= self.ram_threshold and cpu >= self.cpu_threshold:
                    msg = f"Sir, system resource alert: RAM usage {ram_pct:.0f}% aur CPU {cpu:.0f}% par hai. System par heavy load chal raha hai."
                elif ram_pct >= self.ram_threshold:
                    free_mb = mem.available // (1024 * 1024)
                    msg = f"Sir, dhyan dijiye - system ki RAM usage {ram_pct:.0f}% ho gayi hai ({free_mb} MB free). Heavy background apps check karun?"
                else:
                    msg = f"Sir, CPU usage {cpu:.0f}% par chal rahi hai, processor par heavy task run ho raha hai."

                return ProactiveTrigger(
                    trigger_type=TriggerType.RESOURCE_WARNING,
                    message=msg,
                    priority=3,
                    context_data={"ram_percent": ram_pct, "cpu_percent": cpu},
                )
        except Exception:
            pass

        return None

