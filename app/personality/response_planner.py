"""
Response Planner for JARVIS.
Classifies user intent, language style, and applies intellectual honesty or conciseness directives.
"""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional

from app.core.language import detect_language_hint


class IntentType(str, Enum):
    PROPOSITION = "proposition"      # Idea, proposal, plan, decision
    QUERY = "query"                  # Factual question, lookup
    ELABORATION = "elaboration"      # Request for detailed explanation
    COMMAND = "command"              # Tool or PC command execution
    CHITCHAT = "chitchat"            # Greeting, casual remark


@dataclass
class PlannedResponseContext:
    """Planning metadata for guiding LLM response generation."""
    intent: IntentType
    target_language: str             # "hi" (Hinglish/Hindi) or "en"
    conciseness_level: str           # "concise", "moderate", "detailed"
    dynamic_directive: str           # LLM steering prompt segment


class ResponsePlanner:
    """Analyzes incoming user query to plan the optimal conversational posture."""

    PROPOSITION_PATTERNS = [
        r"\b(i think|i plan to|my idea|have an idea|got an idea|an idea to|idea for|what if we|should i|thinking of|considering|propose that|suggest that|hypothesis)\b",
        r"\b(mera\s+(?:ek\s+)?(?:plan|idea)|(?:ek\s+)?(?:plan|idea)\s+hai|agar hum|kya lagta hai|soch raha hoon|soch rahi hoon|soch rahe hain)\b",
        r"\b(startup|business idea|project idea|invest in|quit my job|rewrite|pivot|architecture choice)\b",
    ]

    ELABORATION_PATTERNS = [
        r"\b(explain in detail|how does|why does|tell me more|step by step|break down)\b",
        r"\b(vistaar se|detail mein|samjhao|explain karo|batao kaise)\b",
    ]

    COMMAND_PATTERNS = [
        r"\b(open|close|start|launch|set a reminder|delete|search|find)\b",
        r"\b(kholo|band karo|chalao|yaad dilana|reminder set karo|dhoondo)\b",
    ]

    CHITCHAT_PATTERNS = [
        r"\b(hi|hello|hey|good morning|good evening|how are you|kya haal hai|kaise ho)\b",
        r"\b(namaste|kya chal raha hai|kya kar rahe ho)\b",
    ]

    def classify_intent(self, user_text: str) -> IntentType:
        """Classifies the primary intent of the user's message."""
        text_lower = user_text.lower().strip()

        # 1. Check Proposition / Idea (highest priority for intellectual honesty)
        for pat in self.PROPOSITION_PATTERNS:
            if re.search(pat, text_lower):
                return IntentType.PROPOSITION

        # 2. Check Elaboration
        for pat in self.ELABORATION_PATTERNS:
            if re.search(pat, text_lower):
                return IntentType.ELABORATION

        # 3. Check Command
        for pat in self.COMMAND_PATTERNS:
            if re.search(pat, text_lower):
                return IntentType.COMMAND

        # 4. Check Chitchat
        for pat in self.CHITCHAT_PATTERNS:
            if re.search(pat, text_lower):
                return IntentType.CHITCHAT

        # Default: Standard Query
        return IntentType.QUERY

    def plan_response(self, user_text: str) -> PlannedResponseContext:
        """Generates contextual steering metadata for the conversation manager."""
        intent = self.classify_intent(user_text)
        language = detect_language_hint(user_text)

        directives = []

        # Language Directive
        if language == "hi":
            directives.append(
                "COMMUNICATION STYLE: Respond in fluent, conversational Hinglish (natural blend of Hindi and English) "
                "using respectful forms ('Aap', 'Kijiye'). Do not use overly formal or bookish Sanskritized Hindi."
            )
        else:
            directives.append(
                "COMMUNICATION STYLE: Respond in natural, confident, and articulate English."
            )

        # Intent-specific Directive
        if intent == IntentType.PROPOSITION:
            conciseness = "moderate"
            directives.append(
                "INTELLECTUAL HONESTY ACTIVE: The user is proposing an idea, decision, or hypothesis. "
                "Do NOT simply agree or flatter the user. Constructively examine it:\n"
                "1. Identify underlying assumptions.\n"
                "2. Point out real risks or friction points.\n"
                "3. Provide a thoughtful counterargument or alternative angle.\n"
                "4. Suggest what evidence or test would validate this idea.\n"
                "5. Offer practical improvements while remaining supportive and encouraging."
            )
        elif intent == IntentType.QUERY:
            conciseness = "concise"
            directives.append(
                "CONCISENESS: Provide a direct, precise answer in 1 to 3 sentences without filler phrases or pleasantries."
            )
        elif intent == IntentType.ELABORATION:
            conciseness = "detailed"
            directives.append(
                "DEPTH: Provide a clear, well-structured explanation with bullet points or numbered steps as appropriate."
            )
        elif intent == IntentType.COMMAND:
            conciseness = "concise"
            directives.append(
                "ACTION: Acknowledge the requested action cleanly and report outcome or status."
            )
        elif intent == IntentType.CHITCHAT:
            conciseness = "concise"
            directives.append(
                "TONE: Respond with calm warmth and slight, refined wit. Keep it brief."
            )
        else:
            conciseness = "concise"

        dynamic_directive = "\n\n".join(directives)

        return PlannedResponseContext(
            intent=intent,
            target_language=language,
            conciseness_level=conciseness,
            dynamic_directive=dynamic_directive,
        )
