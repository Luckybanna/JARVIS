"""
Strict Interruption and Anti-Annoyance Policies for JARVIS Proactive Behavior.
Enforces Do Not Disturb, Quiet Hours, Meeting Mode, Cooldown, and Hourly Limits.
"""

from dataclasses import dataclass
from datetime import datetime, time as dtime
import time
from typing import List, Optional, Tuple

from app.core.config import Settings, get_settings
from app.core.logger import get_logger

logger = get_logger("proactive.rules")


@dataclass
class ProactiveDecision:
    """Detailed decision on whether JARVIS is allowed to speak autonomously."""
    should_speak: bool
    reason: str
    trigger_type: Optional[str] = None
    proposed_message: Optional[str] = None
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "should_speak": self.should_speak,
            "decision": "ALLOWED" if self.should_speak else "DO NOT SPEAK",
            "reason": self.reason,
            "trigger_type": self.trigger_type,
            "proposed_message": self.proposed_message,
            "timestamp": self.timestamp or time.time(),
        }


class ProactiveRulePolicy:
    """Evaluates safety and annoyance constraints against current environmental state."""

    @staticmethod
    def parse_time_str(time_str: str) -> dtime:
        """Parses 'HH:MM' string to datetime.time."""
        parts = time_str.strip().split(":")
        return dtime(hour=int(parts[0]), minute=int(parts[1]))

    @classmethod
    def is_in_quiet_hours(
        cls,
        start_str: str = "23:00",
        end_str: str = "07:00",
        now_dt: Optional[datetime] = None,
    ) -> bool:
        """Determines if the current time falls within configured quiet hours."""
        now = (now_dt or datetime.now()).time()
        start = cls.parse_time_str(start_str)
        end = cls.parse_time_str(end_str)

        if start <= end:
            # Daytime interval (e.g. 13:00 to 15:00)
            return start <= now <= end
        else:
            # Overnight interval (e.g. 23:00 to 07:00)
            return now >= start or now <= end

    def evaluate_interruption_policy(
        self,
        settings: Optional[Settings] = None,
        is_user_speaking: bool = False,
        proactive_history: Optional[List[float]] = None,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Runs all anti-annoyance filters in order of priority.
        Returns (is_allowed, reason).
        """
        cfg = settings or get_settings()
        now_ts = current_time or time.time()
        history = proactive_history or []

        # 1. Master Toggle
        if not cfg.proactive_enabled:
            return False, "Proactive engine is globally disabled in settings"

        # 2. Do Not Disturb
        if cfg.do_not_disturb:
            return False, "User has enabled Do Not Disturb mode"

        # 3. Meeting Mode
        if cfg.meeting_mode:
            return False, "User is currently in Meeting Mode"

        # 4. User Speaking / Active Audio
        if is_user_speaking:
            return False, "User is actively speaking or microphone is active"

        # 5. Quiet Hours
        if cfg.quiet_hours_enabled:
            if self.is_in_quiet_hours(cfg.quiet_hours_start, cfg.quiet_hours_end):
                return False, f"Quiet hours active ({cfg.quiet_hours_start} - {cfg.quiet_hours_end})"

        # 6. Hourly Rate Limit
        one_hour_ago = now_ts - 3600.0
        recent_in_hour = [t for t in history if t >= one_hour_ago]
        if len(recent_in_hour) >= cfg.max_proactive_per_hour:
            return False, f"Hourly proactive quota reached ({len(recent_in_hour)}/{cfg.max_proactive_per_hour})"

        # 7. Minimum Interval Cooldown
        if history:
            last_msg_ts = history[-1]
            elapsed_minutes = (now_ts - last_msg_ts) / 60.0
            if elapsed_minutes < cfg.min_proactive_interval_min:
                remaining = cfg.min_proactive_interval_min - elapsed_minutes
                return False, f"Cooldown active (last spoken {elapsed_minutes:.1f}m ago, wait {remaining:.1f}m)"

        return True, "All anti-annoyance checks passed"
