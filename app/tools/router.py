"""
Natural Language Tool Router for JARVIS.
Translates conversational user intents (Hindi, English, Hinglish) into structured tool invocations
and handles the interactive user confirmation lifecycle.
"""

import ctypes
from datetime import datetime
import os
import re
import subprocess
from typing import Any, Dict, Optional, Tuple
import urllib.parse
import webbrowser

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

        # 2. Time & Date Queries ("aaj time kitna hua hai", "what time is it")
        time_turn = self._handle_time_query(clean, lang)
        if time_turn is not None:
            return time_turn

        # 3. Direct Music & Song Playback ("arijit ka song chalao", "play arijit songs")
        music_turn = self._handle_music_playback(clean, lang)
        if music_turn is not None:
            return music_turn

        # 4. Direct Popular Websites ("open youtube", "open google", "youtube kholo")
        site_turn = self._handle_popular_websites(clean, lang)
        if site_turn is not None:
            return site_turn

        # 5. Quick PC Controls ("open task manager", "lock pc", "google search")
        pc_quick_turn = self._handle_pc_quick_controls(clean, lang)
        if pc_quick_turn is not None:
            return pc_quick_turn

        # 6. System Telemetry / Status & High RAM/CPU Warnings
        if self._matches_system_stats(clean):
            res = self.executor.execute("get_system_stats")
            return res, self._format_system_stats(res, lang)

        # 7. Master Audio Volume
        vol_handled, res = self._handle_volume(clean)
        if vol_handled and res:
            return res, self._format_volume_speech(res, lang)

        # 8. Web Browser URL
        url_match = re.search(r"\b(?:open|browse|visit|go to|kholo)\s+(https?://[^\s]+)", clean)
        if url_match:
            target_url = url_match.group(1)
            res = self.executor.execute("open_url", {"url": target_url})
            return res, self._format_result_speech(res, lang)

        # 9. Application Launching
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

        # 10. Application Closing
        close_match = re.search(
            r"\b(?:close|quit|kill|stop|terminate|band karo)\s+([a-zA-Z0-9_-]+)(?:\s+(?:app|process))?\b",
            clean,
        )
        if close_match:
            target_app = close_match.group(1).lower()
            if target_app not in ("system", "volume", "sound"):
                res = self.executor.execute("close_app", {"process_name": target_app})
                return res, self._format_result_speech(res, lang)

        # 11. File Search
        search_match = re.search(
            r"\b(?:search|find|locate|dhoondo)\s+(?:file|document)?\s*([a-zA-Z0-9_.*-]+\.[a-zA-Z0-9]+)\b",
            clean,
        )
        if search_match:
            query = search_match.group(1)
            res = self.executor.execute("search_files", {"query": query})
            return res, self._format_file_search_speech(res, query, lang)

        return None

    def _handle_time_query(self, clean: str, lang: str) -> Optional[Tuple[ToolResult, str]]:
        time_patterns = [
            r"\b(time kitna hua|kya time ho raha|kitna time hua|time batao|what time is it|current time|what is the time)\b",
            r"\b(aaj ki date|aaj kaunsa din|date and time|time check|ghadi me kitne baje|kitne baje hain)\b",
            r"\b(date kya hai|aaj tareekh kya hai|aaj tarikh kya hai)\b",
        ]
        if not any(re.search(p, clean) for p in time_patterns):
            return None

        now = datetime.now()
        time_12h = now.strftime("%I:%M %p").lstrip("0")
        date_str = now.strftime("%A, %d %B %Y")
        hour = now.hour
        period = "subah" if hour < 12 else ("dopahar" if hour < 16 else "shaam" if hour < 20 else "raat")

        if lang == "hi":
            speech = f"Sir, abhi {period} ke {time_12h} baj rahe hain, aur aaj {date_str} hai."
        else:
            speech = f"It is currently {time_12h} on {date_str}, Sir."

        res = ToolResult(
            tool_name="get_current_time",
            success=True,
            message=speech,
            data={"time": time_12h, "date": date_str},
        )
        return res, speech

    def _handle_music_playback(self, clean: str, lang: str) -> Optional[Tuple[ToolResult, str]]:
        music_patterns = [
            r"\b(?:play|chalao|bajao|lagao|sunao)\s+(?:song\s+)?(.+?)(?:\s+(?:ka\s+)?(?:song|gaana|music|track))?\b",
            r"\b(.+?)\s+(?:ka\s+)?(?:song|gaana|track|music)\s+(?:chalao|bajao|lagao|sunao|play)\b",
            r"\bplay\s+(.+)\b",
        ]
        query = None
        for p in music_patterns:
            m = re.search(p, clean)
            if m:
                extracted = m.group(1).strip()
                if extracted not in ("system", "volume", "sound", "app", "application", "file", "files", "browser", "youtube", "google"):
                    query = extracted
                    break

        if not query:
            return None

        clean_query = re.sub(r"\b(song|gaana|music|track|on youtube|youtube par|chalao|bajao|play|lagao|please|jarvis)\b", "", query, flags=re.IGNORECASE).strip()
        search_term = clean_query if clean_query else query
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(search_term + ' song')}"
        try:
            webbrowser.open(url)
        except Exception as e:
            logger.warning(f"Could not open browser for music: {e}")

        if lang == "hi":
            speech = f"Haanji Sir, YouTube par '{search_term}' ka gaana chala diya hai, enjoy kijiye!"
        else:
            speech = f"Playing '{search_term}' on YouTube for you, Sir!"

        res = ToolResult(
            tool_name="play_music",
            success=True,
            message=speech,
            data={"query": search_term, "url": url},
        )
        return res, speech

    def _handle_popular_websites(self, clean: str, lang: str) -> Optional[Tuple[ToolResult, str]]:
        sites = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "chatgpt": "https://chatgpt.com",
            "github": "https://github.com",
            "instagram": "https://www.instagram.com",
            "twitter": "https://x.com",
            "reddit": "https://www.reddit.com",
            "netflix": "https://www.netflix.com",
            "spotify": "https://open.spotify.com",
            "gmail": "https://mail.google.com",
            "whatsapp": "https://web.whatsapp.com",
        }
        for site_name, site_url in sites.items():
            pattern = rf"\b(?:open|launch|kholo|browse)\s+{site_name}\b|\b{site_name}\s+(?:kholo|open karo)\b"
            if re.search(pattern, clean):
                try:
                    webbrowser.open(site_url)
                except Exception as e:
                    logger.warning(f"Could not open website {site_name}: {e}")
                if lang == "hi":
                    speech = f"Maine {site_name.capitalize()} open kar diya hai, Sir."
                else:
                    speech = f"Opening {site_name.capitalize()} in your browser, Sir."
                res = ToolResult(
                    tool_name="open_website",
                    success=True,
                    message=speech,
                    data={"site": site_name, "url": site_url},
                )
                return res, speech
        return None

    def _handle_pc_quick_controls(self, clean: str, lang: str) -> Optional[Tuple[ToolResult, str]]:
        # 1. Task Manager
        if re.search(r"\b(?:open|launch|kholo|start)\s+(?:the\s+)?(?:task manager|taskmgr)\b|\b(?:task manager|taskmgr)\s+(?:kholo|open karo)\b", clean):
            try:
                os.startfile("taskmgr.exe")
                speech = "Task Manager open kar diya hai, Sir." if lang == "hi" else "Task Manager is now open, Sir."
                return ToolResult(tool_name="task_manager", success=True, message=speech), speech
            except Exception as e:
                speech = f"Task Manager open karne mein samasya: {e}" if lang == "hi" else f"Could not launch Task Manager: {e}"
                return ToolResult(tool_name="task_manager", success=False, message=speech), speech

        # 2. Settings
        if re.search(r"\b(?:open|kholo)\s+(?:windows\s+)?settings\b|\bsettings\s+(?:kholo|open karo)\b", clean):
            try:
                os.system("start ms-settings:")
                speech = "Windows Settings open kar di hain, Sir." if lang == "hi" else "Opening Windows Settings, Sir."
                return ToolResult(tool_name="settings", success=True, message=speech), speech
            except Exception as e:
                return ToolResult(tool_name="settings", success=False, message=str(e)), str(e)

        # 3. Lock Workstation / Screen
        if re.search(r"\b(?:lock\s+(?:pc|computer|screen|workstation)|pc\s+lock\s+karo|screen\s+lock\s+karo)\b", clean):
            try:
                ctypes.windll.user32.LockWorkStation()
                speech = "Screen lock kar di gayi hai, Sir." if lang == "hi" else "PC workstation locked as requested, Sir."
                return ToolResult(tool_name="lock_workstation", success=True, message=speech), speech
            except Exception as e:
                return ToolResult(tool_name="lock_workstation", success=False, message=str(e)), str(e)

        # 4. Web Search
        search_match = re.search(r"\b(?:search\s+(?:for\s+|google\s+for\s+)?|google\s+pe\s+dhoondo\s+|google\s+search\s+)(.+)", clean)
        if search_match:
            search_query = search_match.group(1).strip()
            if search_query and not re.search(r"\b(file|document)\b", clean):
                url = f"https://www.google.com/search?q={urllib.parse.quote_plus(search_query)}"
                try:
                    webbrowser.open(url)
                except Exception as e:
                    logger.warning(f"Could not open Google search: {e}")
                speech = f"Google par '{search_query}' search kar diya hai, Sir." if lang == "hi" else f"Searching Google for '{search_query}', Sir."
                return ToolResult(tool_name="google_search", success=True, message=speech, data={"query": search_query}), speech

        return None

    def _matches_system_stats(self, text: str) -> bool:
        patterns = [
            r"\b(system status|pc status|system telemetry|system specs|system performance)\b",
            r"\b(battery percentage|battery status|battery level|battery kitni)\b",
            r"\b(cpu usage|cpu percent|processor usage)\b",
            r"\b(ram usage|memory usage|ram kitni|free ram)\b",
            r"\b(ram.*cpu|cpu.*ram)\b",
            r"\b(ram.*jyada|cpu.*jyada|high usage|ram alert|cpu alert)\b",
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
        batt_str = f", Battery is at {batt['percent']}%" if batt else ""
        batt_str_hi = f", Battery: {batt['percent']}%" if batt else ""

        is_ram_high = ram_used >= 80.0
        is_cpu_high = cpu >= 80.0

        if is_ram_high or is_cpu_high:
            if lang == "hi":
                warning = f"Sir, dhyan dijiye - RAM usage {ram_used}% hai ({ram_free} MB available) aur CPU usage {cpu}% hai jo kaafi high hai."
                return f"{warning} Uptime: {uptime}{batt_str_hi}."
            else:
                warning = f"Sir, alert: RAM usage is high at {ram_used}% ({ram_free} MB available) and CPU is at {cpu}%."
                return f"{warning} System uptime: {uptime}{batt_str}."

        if lang == "hi":
            return (
                f"Sir, system normal chal raha hai. CPU usage {cpu}%, "
                f"RAM {ram_used}% used ({ram_free} MB available) hai. Uptime: {uptime}{batt_str_hi}."
            )
        else:
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
