"""
Natural Language Tool Router for JARVIS.
Translates conversational user intents (Hindi, English, Hinglish) into structured tool invocations
and handles the interactive user confirmation lifecycle.
"""

import re
from typing import Any, Dict, Optional, Tuple

from app.core.language import detect_language_hint
from app.core.logger import get_logger
from app.tools.base import ToolResult, ToolTier
from app.tools.executor import ToolExecutor, get_tool_executor

logger = get_logger("tools.router")


class ToolRouter:
    """
    Parses conversational user commands and executes the appropriate tool via ToolExecutor.
    """

    def __init__(self, executor: Optional[ToolExecutor] = None):
        self.executor = executor or get_tool_executor()

    def route_and_execute(self, user_text: str) -> Optional[Tuple[ToolResult, str]]:
        """
        Attempts to route the user message to a tool.
        Returns (ToolResult, formatted_conversational_response) if handled, or None if message is general conversation.
        """
        clean = user_text.strip().lower()
        lang = detect_language_hint(user_text)

        # 1. Handle Pending Confirmation Approvals / Rejections
        pending_list = self.executor.list_pending_confirmations()
        if pending_list:
            # Check for confirmation approval: "confirm [id]", "yes", "proceed", "haan", "ha"
            confirm_match = re.search(r"\b(confirm|yes|proceed|approve|haan|ha|theek hai|kardo|kar do)\b(?:\s+([a-zA-Z0-9]+))?", clean)
            if confirm_match:
                token = confirm_match.group(2)
                # If token is omitted or not an active confirmation ID, pick the latest pending one
                if not token or token not in pending_list:
                    token = list(pending_list.keys())[-1]

                res = self.executor.confirm_and_execute(token)
                msg = self._format_result_speech(res, lang)
                return res, msg

            # Check for rejection: "cancel [id]", "no", "reject", "nahi", "mat karo"
            reject_match = re.search(r"\b(cancel|no|reject|abort|nahi|mat karo|chhod do)\b(?:\s+([a-zA-Z0-9]+))?", clean)
            if reject_match:
                token = reject_match.group(2)
                if not token or token not in pending_list:
                    token = list(pending_list.keys())[-1]

                cancelled = self.executor.reject_confirmation(token)
                if cancelled:
                    reply = (
                        "Action cancelled as requested, Sir."
                        if lang != "hi"
                        else "Action cancel kar diya gaya hai, Sir."
                    )
                    res = ToolResult(tool_name="confirmation", success=True, message=reply)
                    return res, reply

        # 2. System Telemetry / Status
        if self._matches_system_stats(clean):
            res = self.executor.execute("get_system_stats")
            return res, self._format_system_stats(res, lang)

        # 3. Master Audio Volume
        vol_handled, res = self._handle_volume(clean)
        if vol_handled and res:
            return res, self._format_volume_speech(res, lang)

        # 4. Web Browser URL
        url_match = re.search(r"\b(?:open|browse|visit|go to|kholo)\s+(https?://[^\s]+)", clean)
        if url_match:
            target_url = url_match.group(1)
            res = self.executor.execute("open_url", {"url": target_url})
            return res, self._format_result_speech(res, lang)

        # 5. Application Launching
        launch_match = re.search(
            r"\b(?:open|launch|start|run|kholo|chalao)\s+([a-zA-Z0-9_-]+)(?:\s+(?:app|application))?\b",
            clean,
        )
        if launch_match:
            target_app = launch_match.group(1).lower()
            # Exclude non-app words
            if target_app not in ("system", "volume", "url", "browser", "website", "file", "files"):
                res = self.executor.execute("launch_app", {"app_name": target_app})
                return res, self._format_result_speech(res, lang)

        # 6. Application Closing
        close_match = re.search(
            r"\b(?:close|quit|kill|stop|terminate|band karo)\s+([a-zA-Z0-9_-]+)(?:\s+(?:app|process))?\b",
            clean,
        )
        if close_match:
            target_app = close_match.group(1).lower()
            if target_app not in ("system", "volume", "sound"):
                res = self.executor.execute("close_app", {"process_name": target_app})
                return res, self._format_result_speech(res, lang)

        # 7. File Search
        search_match = re.search(
            r"\b(?:search|find|locate|dhoondo)\s+(?:file|document)?\s*([a-zA-Z0-9_.*-]+\.[a-zA-Z0-9]+)\b",
            clean,
        )
        if search_match:
            query = search_match.group(1)
            res = self.executor.execute("search_files", {"query": query})
            return res, self._format_file_search_speech(res, query, lang)

        return None

    def _matches_system_stats(self, text: str) -> bool:
        patterns = [
            r"\b(system status|pc status|system telemetry|system specs|system performance)\b",
            r"\b(battery percentage|battery status|battery level|battery kitni)\b",
            r"\b(cpu usage|cpu percent|processor usage)\b",
            r"\b(ram usage|memory usage|ram kitni|free ram)\b",
        ]
        return any(re.search(p, text) for p in patterns)

    def _handle_volume(self, text: str) -> Tuple[bool, Optional[ToolResult]]:
        # Mute
        if re.search(r"\b(mute sound|mute volume|mute karo|awaaz band|sound off)\b", text):
            return True, self.executor.execute("mute_volume", {"mute": True})

        # Unmute
        if re.search(r"\b(unmute sound|unmute volume|unmute karo|awaaz kholo|sound on)\b", text):
            return True, self.executor.execute("mute_volume", {"mute": False})

        # Set Volume percentage: e.g. "set volume to 80", "volume 60%", "awaaz 50 kar do"
        vol_pct_match = re.search(r"\b(?:volume|sound|awaaz)\s*(?:ko|to|at)?\s*(\d{1,3})\s*%?", text)
        if vol_pct_match:
            val = int(vol_pct_match.group(1))
            return True, self.executor.execute("set_volume", {"level": val})

        # Query volume
        if re.search(r"\b(get volume|what is the volume|current volume|volume kitna hai|awaaz kitni hai)\b", text):
            return True, self.executor.execute("get_volume")

        return False, None

    def _format_system_stats(self, res: ToolResult, lang: str) -> str:
        if not res.success or not res.data:
            return "Unable to retrieve system metrics at this moment."

        d = res.data
        cpu = d["cpu"]["usage_percent"]
        ram_used = d["memory"]["used_percent"]
        ram_free = d["memory"]["available_mb"]
        uptime = d["uptime"]
        batt = d.get("battery")

        if lang == "hi":
            batt_str = f", Battery: {batt['percent']}%" if batt else ""
            return (
                f"Sir, system normal chal raha hai. CPU usage {cpu}%, "
                f"RAM {ram_used}% used ({ram_free} MB available) hai. Uptime: {uptime}{batt_str}."
            )
        else:
            batt_str = f", Battery is at {batt['percent']}%" if batt else ""
            return (
                f"System status is nominal, Sir. CPU is at {cpu}%, "
                f"RAM usage is {ram_used}% with {ram_free} MB available. System uptime: {uptime}{batt_str}."
            )

    def _format_volume_speech(self, res: ToolResult, lang: str) -> str:
        d = res.data or {}
        pct = d.get("volume_percent", 0)
        muted = d.get("muted", False)

        if muted:
            return "Master audio is currently muted, Sir." if lang != "hi" else "Sir, audio mute kar diya gaya hai."

        if lang == "hi":
            return f"Volume {pct}% par set hai, Sir."
        return f"Master volume is set to {pct}%, Sir."

    def _format_file_search_speech(self, res: ToolResult, query: str, lang: str) -> str:
        items = res.data or []
        if not items:
            return (
                f"No files matching '{query}' were found in the permitted directories, Sir."
                if lang != "hi"
                else f"Sir, '{query}' naam ki koi file nahi mili."
            )
        count = len(items)
        first_path = items[0]["path"]
        if lang == "hi":
            return f"Sir, '{query}' ke liye {count} file mili hain. Pehli file: {first_path}"
        return f"Found {count} matching file(s) for '{query}', Sir. First location: {first_path}"

    def _format_result_speech(self, res: ToolResult, lang: str) -> str:
        if res.requires_confirmation:
            if lang == "hi":
                return (
                    f"Sir, '{res.tool_name}' chalane ke liye aapki confirmation ki zaroorat hai. "
                    f"Kripya 'confirm' ya 'cancel' bolein (ID: {res.confirmation_id})."
                )
            return (
                f"Sir, executing '{res.tool_name}' requires your explicit confirmation. "
                f"Please say 'confirm' to proceed or 'cancel' to abort (ID: {res.confirmation_id})."
            )

        if res.tier == ToolTier.BLOCKED:
            if lang == "hi":
                return f"Maaf kijiye Sir, yeh action safety policy dwara strictly block kiya gaya hai."
            return "Action blocked: This operation is classified as dangerous and strictly prohibited by security policy."

        if res.success:
            if lang == "hi":
                return f"Aapka request safaltapoorvak poora ho gaya hai, Sir: {res.message}"
            return f"Operation completed, Sir: {res.message}"
        else:
            if lang == "hi":
                return f"Sir, request poori karne mein samasya aayi: {res.message}"
            return f"I encountered an issue executing this action, Sir: {res.message}"
