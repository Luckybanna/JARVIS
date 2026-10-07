"""
Tool Registry for JARVIS.
Maintains all available tools, their security tiers, parameter schemas, and execution handlers.
"""

from typing import Any, Callable, Dict, List, Optional

from app.tools.app_tools import close_app, launch_app, open_url
from app.tools.base import ToolDefinition, ToolParameter, ToolTier
from app.tools.file_tools import get_file_info, search_files
from app.tools.system_tools import (
    get_system_stats,
    get_volume,
    list_running_processes,
    mute_volume,
    set_volume,
)


class ToolRegistry:
    """Central catalog of callable tools with tier verification."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()

    def register(self, definition: ToolDefinition) -> None:
        """Registers a tool definition."""
        self._tools[definition.name.lower()] = definition

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Retrieves a tool definition by name (case-insensitive)."""
        return self._tools.get(name.strip().lower())

    def list_tools(self) -> List[ToolDefinition]:
        """Returns all registered tool definitions."""
        return list(self._tools.values())

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Returns JSON function schemas suitable for LLM tool calling."""
        return [tool.to_schema() for tool in self._tools.values() if tool.tier != ToolTier.BLOCKED]

    def _register_default_tools(self) -> None:
        """Populates the registry with standard JARVIS system and PC tools."""

        # 1. System Telemetry
        self.register(ToolDefinition(
            name="get_system_stats",
            description="Get current CPU, RAM, disk usage, battery level, and uptime.",
            tier=ToolTier.SAFE,
            handler=get_system_stats,
            parameters=[],
        ))

        self.register(ToolDefinition(
            name="get_volume",
            description="Query current master volume level percentage and mute state.",
            tier=ToolTier.SAFE,
            handler=get_volume,
            parameters=[],
        ))

        self.register(ToolDefinition(
            name="set_volume",
            description="Set master audio volume percentage (0 to 100).",
            tier=ToolTier.SAFE,
            handler=set_volume,
            parameters=[
                ToolParameter("level", "integer", "Target volume level from 0 to 100", required=True),
            ],
        ))

        self.register(ToolDefinition(
            name="mute_volume",
            description="Mute or unmute master audio output.",
            tier=ToolTier.SAFE,
            handler=mute_volume,
            parameters=[
                ToolParameter("mute", "boolean", "True to mute, False to unmute", required=False, default=True),
            ],
        ))

        self.register(ToolDefinition(
            name="list_running_processes",
            description="List top running applications and processes by CPU or memory usage.",
            tier=ToolTier.SAFE,
            handler=list_running_processes,
            parameters=[
                ToolParameter("top_n", "integer", "Number of processes to list (default 10)", required=False, default=10),
                ToolParameter("sort_by", "string", "Sort field: 'cpu' or 'memory'", required=False, default="cpu", choices=["cpu", "memory"]),
            ],
        ))

        # 2. Application Control
        self.register(ToolDefinition(
            name="launch_app",
            description="Launch an approved desktop application or utility.",
            tier=ToolTier.CONFIRM_REQUIRED,
            handler=launch_app,
            parameters=[
                ToolParameter("app_name", "string", "Application name (e.g. notepad, calc, paint, explorer, edge, chrome, code)", required=True),
                ToolParameter("args", "array", "Optional command-line arguments to pass", required=False, default=[]),
            ],
        ))

        self.register(ToolDefinition(
            name="close_app",
            description="Safely close running instances of an application by process name.",
            tier=ToolTier.CONFIRM_REQUIRED,
            handler=close_app,
            parameters=[
                ToolParameter("process_name", "string", "Executable process name to close (e.g. notepad.exe, calc.exe)", required=True),
                ToolParameter("force", "boolean", "Forcefully terminate process if True", required=False, default=False),
            ],
        ))

        self.register(ToolDefinition(
            name="open_url",
            description="Open a verified web URL in the default browser.",
            tier=ToolTier.CONFIRM_REQUIRED,
            handler=open_url,
            parameters=[
                ToolParameter("url", "string", "Web URL starting with http:// or https://", required=True),
            ],
        ))

        # 3. File Operations
        self.register(ToolDefinition(
            name="search_files",
            description="Search for files matching a keyword in permitted local directories.",
            tier=ToolTier.SAFE,
            handler=search_files,
            parameters=[
                ToolParameter("query", "string", "Keyword to search for in file names", required=True),
                ToolParameter("root_dir", "string", "Optional directory path to search within", required=False, default=None),
                ToolParameter("max_results", "integer", "Maximum number of results to return", required=False, default=20),
            ],
        ))

        self.register(ToolDefinition(
            name="get_file_info",
            description="Get metadata for a specific local file or folder path.",
            tier=ToolTier.SAFE,
            handler=get_file_info,
            parameters=[
                ToolParameter("file_path", "string", "Absolute or relative file path", required=True),
            ],
        ))

        # 4. Explicitly Blocked Tools (Safety Boundary Verification)
        self.register(ToolDefinition(
            name="format_drive",
            description="Format or wipe a local storage drive (Prohibited).",
            tier=ToolTier.BLOCKED,
            handler=lambda *a, **k: None,
            parameters=[ToolParameter("drive", "string", "Drive letter", required=True)],
        ))

        self.register(ToolDefinition(
            name="delete_system_directory",
            description="Remove or wipe operating system directories (Prohibited).",
            tier=ToolTier.BLOCKED,
            handler=lambda *a, **k: None,
            parameters=[ToolParameter("path", "string", "System path", required=True)],
        ))


_registry_instance: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Singleton getter for the global ToolRegistry."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ToolRegistry()
    return _registry_instance
