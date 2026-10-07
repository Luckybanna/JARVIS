"""
Unit tests for JARVIS Personality Engine, Response Planner, and Intellectual Honesty.
"""

import pytest

from app.personality.persona import JARVISPersona, get_default_persona
from app.personality.prompts import PromptBuilder
from app.personality.response_planner import IntentType, ResponsePlanner
from app.core.conversation import ConversationManager
from app.ai.base import AIProvider, AIResponse, TokenUsage


class RecordingAIProvider(AIProvider):
    def __init__(self):
        super().__init__(model_name="recording-v1")
        self.last_received_system_prompt = ""
        self.last_received_messages = []

    @property
    def provider_name(self) -> str:
        return "recording"

    def generate(self, messages, system_prompt=None, **kwargs):
        self.last_received_system_prompt = system_prompt or ""
        self.last_received_messages = list(messages)
        return AIResponse(
            content="Answer recorded",
            model="recording-v1",
            usage=TokenUsage(10, 10, 20),
            latency_ms=15.0,
        )

    def stream(self, *args, **kwargs):
        yield "stream"

    def health_check(self):
        return True, "Recording OK"


def test_persona_system_instruction():
    persona = get_default_persona()
    prompt = persona.to_system_instruction()

    assert "JARVIS" in prompt
    assert "CORE PERSONALITY TRAITS:" in prompt
    assert "calm" in prompt
    assert "slightly witty" in prompt
    assert "COMMUNICATION GUIDELINES:" in prompt
    assert "INTELLECTUAL HONESTY & CRITICAL THINKING:" in prompt
    assert "Never blindly flatter or agree" in prompt
    assert "Identify unstated assumptions" in prompt
    assert "counterargument" in prompt


def test_intent_classification():
    planner = ResponsePlanner()

    # Propositions / Ideas
    assert planner.classify_intent("I think we should rewrite the codebase in Go") == IntentType.PROPOSITION
    assert planner.classify_intent("Mera ek idea hai new startup ke liye") == IntentType.PROPOSITION
    assert planner.classify_intent("What if we invest in this new crypto coin?") == IntentType.PROPOSITION
    assert planner.classify_intent("Main soch raha hoon ki job quit kar doon") == IntentType.PROPOSITION

    # Elaboration
    assert planner.classify_intent("Explain in detail how quantum computing works") == IntentType.ELABORATION
    assert planner.classify_intent("Detail mein samjhao please") == IntentType.ELABORATION

    # Commands
    assert planner.classify_intent("Open Chrome browser") == IntentType.COMMAND
    assert planner.classify_intent("Notepad kholo") == IntentType.COMMAND

    # Chitchat
    assert planner.classify_intent("Hello Jarvis, how are you?") == IntentType.CHITCHAT
    assert planner.classify_intent("Namaste bhai kya haal hai") == IntentType.CHITCHAT

    # Standard Queries
    assert planner.classify_intent("What is the capital of Australia?") == IntentType.QUERY
    assert planner.classify_intent("Mera kal ka schedule kya hai?") == IntentType.QUERY


def test_intellectual_honesty_directive_activation():
    planner = ResponsePlanner()
    plan = planner.plan_response("I have an idea to build an autonomous drone delivery business in my city")

    assert plan.intent == IntentType.PROPOSITION
    assert "INTELLECTUAL HONESTY ACTIVE" in plan.dynamic_directive
    assert "assumptions" in plan.dynamic_directive
    assert "risks" in plan.dynamic_directive
    assert "counterargument" in plan.dynamic_directive
    assert "evidence or test" in plan.dynamic_directive
    assert "practical improvements" in plan.dynamic_directive


def test_language_adaptation_hinglish_vs_english():
    planner = ResponsePlanner()

    # Hinglish query
    hi_plan = planner.plan_response("Jarvis aaj mujhe Kota jana hai, train time batao")
    assert hi_plan.target_language == "hi"
    assert "fluent, conversational Hinglish" in hi_plan.dynamic_directive
    assert "Aap" in hi_plan.dynamic_directive

    # English query
    en_plan = planner.plan_response("Jarvis, what is the current CPU utilization?")
    assert en_plan.target_language == "en"
    assert "natural, confident, and articulate English" in en_plan.dynamic_directive


def test_prompt_builder_assembly():
    builder = PromptBuilder()
    planner = ResponsePlanner()
    plan = planner.plan_response("I think we should cancel the cloud subscription")

    prompt = builder.build_system_prompt(
        planned_context=plan,
        emotional_context={
            "user_emotion": "frustrated",
            "confidence": 0.88,
            "simulated_state": {"concern": 45, "happiness": 50},
        },
        retrieved_memories=["User prefers local backups over cloud"],
        user_name="Architect",
    )

    assert "SYSTEM ENVIRONMENT:" in prompt
    assert "Architect" in prompt
    assert "EMOTION & EMPATHY CONTEXT:" in prompt
    assert "frustrated" in prompt
    assert "RELEVANT USER MEMORIES & PREFERENCES:" in prompt
    assert "User prefers local backups over cloud" in prompt
    assert "TURN-SPECIFIC EXECUTION DIRECTIVE:" in prompt
    assert "INTELLECTUAL HONESTY ACTIVE" in prompt


def test_conversation_manager_personality_integration():
    rec_provider = RecordingAIProvider()
    conv = ConversationManager(provider=rec_provider)

    # Proposition message
    conv.send_user_message("I am thinking of rewriting our database engine in C")

    assert conv.last_planned_context is not None
    assert conv.last_planned_context.intent == IntentType.PROPOSITION
    assert "INTELLECTUAL HONESTY ACTIVE" in rec_provider.last_received_system_prompt
    assert "assumptions" in rec_provider.last_received_system_prompt
