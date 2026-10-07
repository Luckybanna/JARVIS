"""
Tool Executor and Confirmation Manager for JARVIS.
Enforces security tiers, handles user confirmation workflow, and emits execution events.
"""

import threading
import time
from typing import Any, Dict, Optional
import uuid

from app.core.events import Event, EventBus, EventType, get_event_bus
from app.core.logger import get_logger
from app.tools.base import PendingConfirmation, ToolResult, ToolTier
from app.tools.registry import ToolRegistry, get_tool_registry

logger = get_logger("tools.executor")


class ToolExecutor:
    """
    Executes tools in compliance with security tiers and confirmation requirements.
    """

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        event_bus: Optional[EventBus] = None,
        confirmation_ttl_seconds: float = 60.0,
    ):
        self.registry = registry or get_tool_registry()
        self.bus = event_bus or get_event_bus()
        self.confirmation_ttl = confirmation_ttl_seconds
        self._pending_confirmations: Dict[str, PendingConfirmation] = {}
        self._lock = threading.RLock()

    def execute(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        pre_confirmed: bool = False,
    ) -> ToolResult:
        """
        Executes a registered tool or requests confirmation if required by its tier.
        """
        args = arguments or {}
        tool = self.registry.get(tool_name)

        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                message=f"Tool '{tool_name}' is not recognized.",
                tier=ToolTier.SAFE,
            )

        # 1. Tier: BLOCKED -> Immediate rejection
        if tool.tier == ToolTier.BLOCKED:
            logger.warning(f"Blocked attempt to execute prohibited tool: {tool_name}")
            return ToolResult(
                tool_name=tool_name,
                success=False,
                message=f"Execution blocked: Action '{tool_name}' is strictly prohibited by JARVIS safety policy.",
                tier=ToolTier.BLOCKED,
            )

        # 2. Tier: CONFIRM_REQUIRED -> Check confirmation
        if tool.tier == ToolTier.CONFIRM_REQUIRED and not pre_confirmed:
            confirmation_id = str(uuid.uuid4())[:8]
            expires_at = time.time() + self.confirmation_ttl
            pending = PendingConfirmation(
                confirmation_id=confirmation_id,
                tool_name=tool.name,
                arguments=args,
                tier=tool.tier,
                description=f"Request to execute '{tool.name}' with arguments: {args}",
                expires_at=expires_at,
            )

            with self._lock:
                self._pending_confirmations[confirmation_id] = pending

            logger.info(f"Confirmation required for '{tool.name}' (id: {confirmation_id})")
            self.bus.publish(Event(
                event_type=EventType.TOOL_CONFIRMATION_REQUIRED,
                data={
                    "confirmation_id": confirmation_id,
                    "tool_name": tool.name,
                    "arguments": args,
                    "description": pending.description,
                    "expires_at": expires_at,
                },
                source="tools.executor",
            ))

            return ToolResult(
                tool_name=tool.name,
                success=False,
                requires_confirmation=True,
                confirmation_id=confirmation_id,
                message=f"Action '{tool.name}' requires explicit user confirmation. Confirmation ID: {confirmation_id}",
                tier=tool.tier,
            )

        # 3. Execution (SAFE or CONFIRM_REQUIRED with approval)
        return self._run_tool(tool.name, tool.handler, args, tool.tier)

    def confirm_and_execute(self, confirmation_id: str) -> ToolResult:
        """
        Confirms a pending action by its confirmation ID and executes it.
        """
        with self._lock:
            pending = self._pending_confirmations.pop(confirmation_id, None)

        if not pending:
            return ToolResult(
                tool_name="unknown",
                success=False,
                message=f"Invalid or expired confirmation ID '{confirmation_id}'.",
                tier=ToolTier.CONFIRM_REQUIRED,
            )

        if pending.is_expired():
            return ToolResult(
                tool_name=pending.tool_name,
                success=False,
                message=f"Confirmation for '{pending.tool_name}' has expired.",
                tier=pending.tier,
            )

        tool = self.registry.get(pending.tool_name)
        if not tool:
            return ToolResult(
                tool_name=pending.tool_name,
                success=False,
                message=f"Tool '{pending.tool_name}' is no longer registered.",
                tier=pending.tier,
            )

        logger.info(f"Executing confirmed tool '{pending.tool_name}' (id: {confirmation_id})")
        return self._run_tool(tool.name, tool.handler, pending.arguments, tool.tier)

    def reject_confirmation(self, confirmation_id: str) -> bool:
        """Rejects and cancels a pending confirmation request."""
        with self._lock:
            pending = self._pending_confirmations.pop(confirmation_id, None)
        if pending:
            logger.info(f"Cancelled pending tool confirmation '{confirmation_id}' for '{pending.tool_name}'")
            return True
        return False

    def list_pending_confirmations(self) -> Dict[str, PendingConfirmation]:
        """Returns all currently active unexpired confirmations."""
        with self._lock:
            now = time.time()
            return {k: v for k, v in self._pending_confirmations.items() if v.expires_at > now}

    def _run_tool(self, tool_name: str, handler: Any, args: Dict[str, Any], tier: ToolTier) -> ToolResult:
        """Performs invocation with timing, logging, and EventBus telemetry."""
        start_time = time.perf_counter()

        self.bus.publish(Event(
            event_type=EventType.TOOL_EXECUTION_START,
            data={"tool_name": tool_name, "arguments": args, "tier": tier.value},
            source="tools.executor",
        ))

        try:
            output = handler(**args)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            result = ToolResult(
                tool_name=tool_name,
                success=True,
                data=output,
                message=f"Successfully executed '{tool_name}'.",
                tier=tier,
                execution_time_ms=elapsed_ms,
            )

            self.bus.publish(Event(
                event_type=EventType.TOOL_EXECUTION_COMPLETE,
                data={"tool_name": tool_name, "success": True, "elapsed_ms": elapsed_ms},
                source="tools.executor",
            ))
            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(f"Execution failed for tool '{tool_name}': {e}", exc_info=True)

            result = ToolResult(
                tool_name=tool_name,
                success=False,
                data=None,
                message=f"Tool error in '{tool_name}': {str(e)}",
                tier=tier,
                execution_time_ms=elapsed_ms,
            )

            self.bus.publish(Event(
                event_type=EventType.TOOL_EXECUTION_COMPLETE,
                data={"tool_name": tool_name, "success": False, "error": str(e), "elapsed_ms": elapsed_ms},
                source="tools.executor",
            ))
            return result


_executor_instance: Optional[ToolExecutor] = None


def get_tool_executor(
    registry: Optional[ToolRegistry] = None,
    event_bus: Optional[EventBus] = None,
) -> ToolExecutor:
    """Singleton getter for the global ToolExecutor."""
    global _executor_instance
    if _executor_instance is None:
        _executor_instance = ToolExecutor(registry=registry, event_bus=event_bus)
    return _executor_instance
