"""
Proactive Conversation Engine for JARVIS.
Decides when JARVIS should autonomously initiate conversation using ShouldJarvisSpeakNow().
"""

import threading
import time
from typing import List, Optional

from app.core.config import Settings, get_settings
from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.logger import get_logger
from app.proactive.rules import ProactiveDecision, ProactiveRulePolicy
from app.proactive.triggers import (
    ProactiveTrigger,
    SystemResourceMonitorTracker,
    TaskFollowupTracker,
    TriggerType,
    WellbeingCareTracker,
    WorkActivityTracker,
)

logger = get_logger("proactive.engine")


class ProactiveEngine:
    """Evaluator and manager for autonomous JARVIS conversational initiations."""

    def __init__(
        self,
        rule_policy: Optional[ProactiveRulePolicy] = None,
        activity_tracker: Optional[WorkActivityTracker] = None,
        followup_tracker: Optional[TaskFollowupTracker] = None,
        event_bus: Optional[EventBus] = None,
        settings: Optional[Settings] = None,
    ):
        self.settings: Settings = settings or get_settings()
        self.event_bus: EventBus = event_bus or get_event_bus()
        self.policy: ProactiveRulePolicy = rule_policy or ProactiveRulePolicy()
        self.activity_tracker: WorkActivityTracker = activity_tracker or WorkActivityTracker()
        self.followup_tracker: TaskFollowupTracker = followup_tracker or TaskFollowupTracker()
        self.wellbeing_tracker: WellbeingCareTracker = WellbeingCareTracker()
        self.resource_tracker: SystemResourceMonitorTracker = SystemResourceMonitorTracker()

        self._lock = threading.RLock()
        self.proactive_history: List[float] = []
        self.last_decision: Optional[ProactiveDecision] = None
        self.is_user_speaking: bool = False

        # Background monitor thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False

        # Listen for audio/speech events to update user speaking status
        self.event_bus.subscribe(EventType.SPEECH_DETECTED, self._on_speech_detected)
        self.event_bus.subscribe(EventType.MIC_LISTENING_STOP, self._on_mic_stopped)
        self.event_bus.subscribe(EventType.USER_INPUT_TEXT, self._on_user_interacted)

    def _on_speech_detected(self, event: Event) -> None:
        self.is_user_speaking = True
        self.activity_tracker.record_activity()

    def _on_mic_stopped(self, event: Event) -> None:
        self.is_user_speaking = False

    def _on_user_interacted(self, event: Event) -> None:
        self.activity_tracker.record_activity()

    def should_jarvis_speak_now(
        self,
        candidate_trigger: Optional[ProactiveTrigger] = None,
        current_time: Optional[float] = None,
    ) -> ProactiveDecision:
        """
        Core decision function ShouldJarvisSpeakNow().
        Evaluates triggers, anti-annoyance filters, rate limits, and quiet hours.
        """
        now = current_time or time.time()

        with self._lock:
            # 1. Determine trigger
            trigger = candidate_trigger
            if trigger is None:
                # Check work break suggestion
                trigger = self.activity_tracker.check_break_suggestion_needed(current_time=now)

            if trigger is None:
                # If still no trigger, check if any follow-up is relevant
                decision = ProactiveDecision(
                    should_speak=False,
                    reason="DO NOT SPEAK: No active trigger or meaningful reason to speak",
                    trigger_type=None,
                    proposed_message=None,
                    timestamp=now,
                )
                self.last_decision = decision
                return decision

            # 2. Evaluate Anti-Annoyance Policies
            allowed, policy_reason = self.policy.evaluate_interruption_policy(
                settings=self.settings,
                is_user_speaking=self.is_user_speaking,
                proactive_history=self.proactive_history,
                current_time=now,
            )

            if not allowed:
                decision = ProactiveDecision(
                    should_speak=False,
                    reason=f"DO NOT SPEAK: {policy_reason}",
                    trigger_type=trigger.trigger_type.value,
                    proposed_message=trigger.message,
                    timestamp=now,
                )
                self.last_decision = decision
                self.event_bus.publish(
                    Event(
                        event_type=EventType.PROACTIVE_TRIGGER_EVALUATED,
                        data=decision.to_dict(),
                        source="proactive_engine",
                    )
                )
                logger.info(f"Proactive decision: {decision.reason}")
                return decision

            # 3. Decision Allowed
            decision = ProactiveDecision(
                should_speak=True,
                reason=f"ALLOWED: {trigger.trigger_type.value} passed all filters",
                trigger_type=trigger.trigger_type.value,
                proposed_message=trigger.message,
                timestamp=now,
            )
            self.last_decision = decision

            # Publish event
            self.event_bus.publish(
                Event(
                    event_type=EventType.PROACTIVE_TRIGGER_EVALUATED,
                    data=decision.to_dict(),
                    source="proactive_engine",
                )
            )
            self.event_bus.publish(
                Event(
                    event_type=EventType.PROACTIVE_MESSAGE_PROPOSED,
                    data={"message": trigger.message, "trigger": trigger.trigger_type.value},
                    source="proactive_engine",
                )
            )

            logger.info(f"Proactive message APPROVED: '{trigger.message}'")
            return decision

    def record_proactive_speech(self, timestamp: Optional[float] = None) -> None:
        """Records that a proactive message was delivered aloud, updating cooldown timers."""
        with self._lock:
            ts = timestamp or time.time()
            self.proactive_history.append(ts)
            # Retain only last 50 entries
            if len(self.proactive_history) > 50:
                self.proactive_history = self.proactive_history[-50:]

    def check_active_triggers(self, current_time: Optional[float] = None) -> Optional[ProactiveTrigger]:
        """Evaluates all registered proactive monitors (system load, caring companion check-ins, break suggestions)."""
        now = current_time or time.time()
        # 1. System resource warning (RAM / CPU > 85%)
        res_trigger = self.resource_tracker.check_resource_warning(current_time=now)
        if res_trigger:
            return res_trigger

        # 2. Wellbeing & Caring Companion (meals, tea, late hours)
        well_trigger = self.wellbeing_tracker.check_wellbeing_trigger(current_time=now)
        if well_trigger:
            return well_trigger

        # 3. Work activity break suggestion
        break_trigger = self.activity_tracker.check_break_suggestion_needed(current_time=now)
        if break_trigger:
            return break_trigger

        return None

    def start(self, interval_seconds: float = 30.0) -> None:
        """Starts background periodic proactive evaluation thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                args=(interval_seconds,),
                daemon=True,
                name="ProactiveMonitorWorker",
            )
            self._monitor_thread.start()
            logger.info("ProactiveEngine background monitor started")

    def stop(self) -> None:
        """Stops background monitor loop."""
        with self._lock:
            self._running = False

    def _monitor_loop(self, interval_seconds: float) -> None:
        """Periodic loop that evaluates autonomous triggers without blocking the main loop."""
        while self._running:
            try:
                time.sleep(interval_seconds)
                if not self._running:
                    break
                trigger = self.check_active_triggers()
                if trigger:
                    self.should_jarvis_speak_now(candidate_trigger=trigger)
            except Exception as e:
                logger.error(f"Error in proactive monitor loop: {e}", exc_info=True)

    def get_last_decision(self) -> Optional[ProactiveDecision]:
        with self._lock:
            return self.last_decision


_engine_instance: Optional[ProactiveEngine] = None


def get_proactive_engine() -> ProactiveEngine:
    """Singleton getter for the global ProactiveEngine."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProactiveEngine()
    return _engine_instance
