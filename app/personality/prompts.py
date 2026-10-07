"""
Dynamic System Prompt Builder for JARVIS.
Combines base persona, environmental context, emotion state, and dynamic response steering.
"""

from datetime import datetime
import platform
from typing import Dict, List, Optional

from app.personality.persona import JARVISPersona, get_default_persona
from app.personality.response_planner import PlannedResponseContext


class PromptBuilder:
    """Assembles comprehensive, dynamically adapted system prompts for LLM turns."""

    def __init__(self, persona: Optional[JARVISPersona] = None):
        self.persona: JARVISPersona = persona or get_default_persona()

    def build_system_prompt(
        self,
        planned_context: Optional[PlannedResponseContext] = None,
        emotional_context: Optional[Dict[str, any]] = None,
        retrieved_memories: Optional[List[str]] = None,
        user_name: Optional[str] = None,
    ) -> str:
        """Constructs the full system instruction string."""
        sections = []

        # 1. Base Persona
        sections.append(self.persona.to_system_instruction())

        # 2. Environmental & System Context
        now = datetime.now()
        date_str = now.strftime("%A, %d %B %Y, %I:%M %p")
        env_section = (
            f"SYSTEM ENVIRONMENT:\n"
            f"- Current Date & Time: {date_str}\n"
            f"- Host OS: {platform.system()} {platform.release()} ({platform.architecture()[0]})\n"
        )
        if user_name:
            env_section += f"- User: {user_name}\n"
        sections.append(env_section)

        # 3. Emotional State Context (if available)
        if emotional_context:
            simulated_state = emotional_context.get("simulated_state", {})
            user_emotion = emotional_context.get("user_emotion", "neutral")
            confidence = emotional_context.get("confidence", 1.0)

            state_desc = ", ".join(f"{k}: {v}" for k, v in simulated_state.items()) if simulated_state else "Balanced"
            sections.append(
                f"EMOTION & EMPATHY CONTEXT:\n"
                f"- User Detected Emotion: {user_emotion} (Confidence: {confidence:.2f})\n"
                f"- Internal Emotion Vector: {state_desc}\n"
                f"- Guidance: Modulate response warmth and tone appropriately based on user state.\n"
            )

        # 4. Long-Term Memory Context (if available)
        if retrieved_memories:
            memories_list = "\n".join(f"  * {m}" for m in retrieved_memories)
            sections.append(
                f"RELEVANT USER MEMORIES & PREFERENCES:\n"
                f"{memories_list}\n"
                f"Use this knowledge seamlessly without explicitly announcing that you retrieved it.\n"
            )

        # 5. Dynamic Response Planning Directive
        if planned_context and planned_context.dynamic_directive:
            sections.append(
                f"TURN-SPECIFIC EXECUTION DIRECTIVE:\n"
                f"{planned_context.dynamic_directive}\n"
            )

        return "\n\n".join(sections)
