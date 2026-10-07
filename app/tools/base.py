"""
Base types and data models for JARVIS PC Automation Tools.
Defines security tiers, tool definitions, execution results, and confirmation requests.
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Callable, Dict, List, Optional


class ToolTier(str, Enum):
    """Safety and permission classification for PC automation tools."""
    SAFE = "safe"                          # Read-only or benign actions; executes immediately
    CONFIRM_REQUIRED = "confirm_required"  # Visible side-effects; requires user confirmation
    BLOCKED = "blocked"                    # Destructive or security hazard; strictly prohibited


@dataclass
class ToolParameter:
    """Specification of a parameter for tool-calling models."""
    name: str
    param_type: str
    description: str
    required: bool = True
    default: Any = None
    choices: Optional[List[str]] = None


@dataclass
class ToolDefinition:
    """Schema and execution wrapper for a tool."""
    name: str
    description: str
    tier: ToolTier
    handler: Callable[..., Any]
    parameters: List[ToolParameter] = field(default_factory=list)

    def to_schema(self) -> Dict[str, Any]:
        """Converts definition into standard JSON schema for LLM function calling."""
        properties = {}
        required_params = []

        for p in self.parameters:
            prop: Dict[str, Any] = {
                "type": p.param_type,
                "description": p.description,
            }
            if p.choices:
                prop["enum"] = p.choices
            if p.default is not None:
                prop["default"] = p.default
            properties[p.name] = prop

            if p.required:
                required_params.append(p.name)

        return {
            "name": self.name,
            "description": f"[{self.tier.value.upper()}] {self.description}",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required_params,
            },
        }


@dataclass
class ToolResult:
    """Standard outcome packet returned by ToolExecutor."""
    tool_name: str
    success: bool
    data: Any = None
    message: str = ""
    tier: ToolTier = ToolTier.SAFE
    requires_confirmation: bool = False
    confirmation_id: Optional[str] = None
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "tier": self.tier.value,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_id": self.confirmation_id,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }


@dataclass
class PendingConfirmation:
    """Record of an action awaiting explicit user confirmation."""
    confirmation_id: str
    tool_name: str
    arguments: Dict[str, Any]
    tier: ToolTier
    description: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def is_expired(self) -> bool:
        return time.time() > self.expires_at
