"""
Conversation Manager for JARVIS.
Coordinates conversational turn-taking, history tracking, event publishing, and provider interaction.
"""

from typing import List, Optional
import time

from app.ai.base import AIProvider, AIResponse, ChatMessage, MessageRole
from app.core.config import Settings, get_settings
from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.logger import get_logger
from app.personality.persona import JARVISPersona, get_default_persona
from app.personality.prompts import PromptBuilder
from app.personality.response_planner import ResponsePlanner, PlannedResponseContext

logger = get_logger("conversation")


class ConversationManager:
    """Manages conversational session, message history, dynamic prompt building, and AI interactions."""

    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        event_bus: Optional[EventBus] = None,
        system_prompt: Optional[str] = None,
        persona: Optional[JARVISPersona] = None,
        response_planner: Optional[ResponsePlanner] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        memory_manager: Optional[any] = None,
        emotion_engine: Optional[any] = None,
        tool_router: Optional[any] = None,
        task_manager: Optional[any] = None,
        max_history_turns: int = 20,
    ):
        self.settings: Settings = get_settings()
        self.event_bus: EventBus = event_bus or get_event_bus()
        
        if provider is None:
            from app.ai.factory import create_ai_provider
            self.provider: AIProvider = create_ai_provider(settings=self.settings)
        else:
            self.provider = provider

        self.persona = persona or get_default_persona()
        self.response_planner = response_planner or ResponsePlanner()
        self.prompt_builder = prompt_builder or PromptBuilder(persona=self.persona)
        self.custom_system_prompt = system_prompt
        self.max_history_turns: int = max_history_turns
        self.history: List[ChatMessage] = []

        # Memory Subsystem
        if memory_manager is not None:
            self.memory_manager = memory_manager
        else:
            try:
                from app.memory.manager import get_memory_manager
                self.memory_manager = get_memory_manager()
            except Exception:
                self.memory_manager = None

        # Emotion Subsystem
        if emotion_engine is not None:
            self.emotion_engine = emotion_engine
        else:
            try:
                from app.emotion.engine import get_emotion_engine
                self.emotion_engine = get_emotion_engine()
            except Exception:
                self.emotion_engine = None

        # Tools Subsystem
        if tool_router is not None:
            self.tool_router = tool_router
        else:
            try:
                from app.tools.executor import get_tool_executor
                from app.tools.router import ToolRouter
                self.tool_router = ToolRouter(executor=get_tool_executor(event_bus=self.event_bus))
            except Exception:
                self.tool_router = None

        # Tasks & Reminder Subsystem
        if task_manager is not None:
            self.task_manager = task_manager
        else:
            try:
                from app.tasks.manager import get_task_manager
                self.task_manager = get_task_manager()
            except Exception:
                self.task_manager = None

        # Context hooks for emotion and memory engines
        self.emotion_hook = (
            self.emotion_engine.get_context_for_prompt if self.emotion_engine else None
        )
        self.memory_hook = (
            self.memory_manager.retrieve_context_for_prompt if self.memory_manager else None
        )

        # Telemetry
        self.last_latency_ms: float = 0.0
        self.last_token_usage: dict = {}
        self.last_error: Optional[str] = None
        self.last_planned_context: Optional[PlannedResponseContext] = None

    @property
    def system_prompt(self) -> str:
        """Returns the base or custom system prompt."""
        return self.custom_system_prompt or self.prompt_builder.build_system_prompt()

    def set_provider(self, provider: AIProvider) -> None:
        """Switch active AI provider dynamically."""
        self.provider = provider
        logger.info(f"Switched AI provider to '{provider.provider_name}' ({provider.model_name})")

    def add_message(self, role: MessageRole, content: str) -> ChatMessage:
        """Adds a message to the in-memory history window."""
        msg = ChatMessage(role=role, content=content)
        self.history.append(msg)
        # Trim history if exceeding max turns
        if len(self.history) > self.max_history_turns * 2:
            self.history = self.history[-(self.max_history_turns * 2):]
        return msg

    def clear_history(self) -> None:
        """Clears conversation history."""
        self.history.clear()
        logger.info("Conversation history cleared")

    def send_user_message(self, user_text: str) -> AIResponse:
        """Processes a user message, emits lifecycle events, and retrieves AI response."""
        cleaned_text = user_text.strip()
        if not cleaned_text:
            return AIResponse(
                content="",
                model=self.provider.model_name,
                error="Empty input provided",
            )

        # Record user message in history
        self.add_message(MessageRole.USER, cleaned_text)

        # Extract and persist durable user memory if present
        if self.memory_manager:
            try:
                self.memory_manager.process_turn(cleaned_text)
            except Exception as e:
                logger.error(f"Error processing memory extraction: {e}")

        # Process emotional state shift from user turn
        if self.emotion_engine:
            try:
                self.emotion_engine.process_user_turn(cleaned_text)
            except Exception as e:
                logger.error(f"Error processing emotion: {e}")

        # Check PC Tool Routing
        if self.tool_router:
            tool_match = self.tool_router.route_and_execute(cleaned_text)
            if tool_match is not None:
                tool_res, speech = tool_match
                self.add_message(MessageRole.ASSISTANT, speech)
                self.last_latency_ms = tool_res.execution_time_ms
                self.last_error = None if (tool_res.success or tool_res.requires_confirmation) else tool_res.message
                self.event_bus.publish(
                    Event(
                        event_type=EventType.USER_INPUT_TEXT,
                        data={"text": cleaned_text, "intent": "command", "language": "auto"},
                        source="conversation_manager",
                    )
                )
                self.event_bus.publish(
                    Event(
                        event_type=EventType.JARVIS_RESPONSE_COMPLETE,
                        data={
                            "text": speech,
                            "model": f"tools.{tool_res.tool_name}",
                            "latency_ms": tool_res.execution_time_ms,
                            "tokens": {},
                            "error": self.last_error,
                        },
                        source="conversation_manager",
                    )
                )
                return AIResponse(
                    content=speech,
                    model=f"tools.{tool_res.tool_name}",
                    latency_ms=tool_res.execution_time_ms,
                    error=self.last_error,
                )

        # Check Task & Reminder Scheduling
        if self.task_manager:
            try:
                reminder_speech = self.task_manager.process_turn(cleaned_text)
                if reminder_speech:
                    self.add_message(MessageRole.ASSISTANT, reminder_speech)
                    self.last_latency_ms = 5.0
                    self.last_error = None
                    self.event_bus.publish(
                        Event(
                            event_type=EventType.USER_INPUT_TEXT,
                            data={"text": cleaned_text, "intent": "command", "language": "auto"},
                            source="conversation_manager",
                        )
                    )
                    self.event_bus.publish(
                        Event(
                            event_type=EventType.JARVIS_RESPONSE_COMPLETE,
                            data={
                                "text": reminder_speech,
                                "model": "tasks.manager",
                                "latency_ms": 5.0,
                                "tokens": {},
                                "error": None,
                            },
                            source="conversation_manager",
                        )
                    )
                    return AIResponse(
                        content=reminder_speech,
                        model="tasks.manager",
                        latency_ms=5.0,
                    )
            except Exception as e:
                logger.error(f"Error processing task reminder: {e}")

        # Plan response intent, language, and conciseness
        plan = self.response_planner.plan_response(cleaned_text)
        self.last_planned_context = plan


        # Assemble turn system prompt
        emotional_ctx = self.emotion_hook() if callable(self.emotion_hook) else None
        retrieved_mems = self.memory_hook(cleaned_text) if callable(self.memory_hook) else None
        turn_prompt = self.custom_system_prompt or self.prompt_builder.build_system_prompt(
            planned_context=plan,
            emotional_context=emotional_ctx,
            retrieved_memories=retrieved_mems,
        )

        # Publish User Input Event
        self.event_bus.publish(
            Event(
                event_type=EventType.USER_INPUT_TEXT,
                data={"text": cleaned_text, "intent": plan.intent.value, "language": plan.target_language},
                source="conversation_manager",
            )
        )

        # Publish Thinking Start Event with planning telemetry
        self.event_bus.publish(
            Event(
                event_type=EventType.JARVIS_THINKING_START,
                data={
                    "provider": self.provider.provider_name,
                    "model": self.provider.model_name,
                    "intent": plan.intent.value,
                    "language": plan.target_language,
                    "conciseness": plan.conciseness_level,
                },
                source="conversation_manager",
            )
        )

        # Call AI provider
        start_t = time.perf_counter()
        try:
            response = self.provider.generate(
                messages=self.history,
                system_prompt=turn_prompt,
                temperature=self.settings.ai_temperature,
                max_tokens=self.settings.ai_max_tokens,
            )
            self.last_latency_ms = response.latency_ms
            self.last_token_usage = {
                "prompt": response.usage.prompt_tokens,
                "completion": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            }
            self.last_error = response.error

            # Add assistant message to history if non-empty and no critical error
            if response.content and not response.error:
                self.add_message(MessageRole.ASSISTANT, response.content)

        except Exception as e:
            latency = (time.perf_counter() - start_t) * 1000.0
            self.last_latency_ms = latency
            self.last_error = str(e)
            logger.error(f"Error during conversation generation: {e}", exc_info=True)
            response = AIResponse(
                content=f"[Error: {str(e)}]",
                model=self.provider.model_name,
                latency_ms=latency,
                error=str(e),
            )
            self.event_bus.publish(
                Event(
                    event_type=EventType.ERROR_OCCURRED,
                    data={"error": str(e), "context": "conversation_generation"},
                    source="conversation_manager",
                )
            )

        finally:
            # Publish Thinking Stop Event
            self.event_bus.publish(
                Event(
                    event_type=EventType.JARVIS_THINKING_STOP,
                    data={"latency_ms": self.last_latency_ms},
                    source="conversation_manager",
                )
            )

        # Publish Response Complete Event
        self.event_bus.publish(
            Event(
                event_type=EventType.JARVIS_RESPONSE_COMPLETE,
                data={
                    "text": response.content,
                    "model": response.model,
                    "latency_ms": response.latency_ms,
                    "tokens": self.last_token_usage,
                    "error": response.error,
                },
                source="conversation_manager",
            )
        )

        return response
