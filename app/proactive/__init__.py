"""
Proactive Conversation Engine for JARVIS.
Evaluates contextual triggers, enforces anti-annoyance policies, and initiates conversations safely.
"""

from app.proactive.rules import ProactiveDecision, ProactiveRulePolicy
from app.proactive.triggers import ProactiveTrigger, TriggerType
from app.proactive.engine import ProactiveEngine, get_proactive_engine

__all__ = [
    "ProactiveDecision",
    "ProactiveRulePolicy",
    "ProactiveTrigger",
    "TriggerType",
    "ProactiveEngine",
    "get_proactive_engine",
]
