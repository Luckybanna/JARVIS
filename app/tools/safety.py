"""
Safety Policy and Heuristic Validator for JARVIS PC Automation Tools.
Enforces strict security boundaries to prevent destructive or unauthorized operations.
"""

import os
from pathlib import Path
import re
from typing import List, Tuple
from urllib.parse import urlparse

# Patterns strictly blocked by JARVIS safety policy
BLOCKED_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\bdiskpart\b", re.IGNORECASE),
    re.compile(r"\brmdir\s+/[sq]\s+", re.IGNORECASE),
    re.compile(r"\bdel\s+/[fsq]\s+", re.IGNORECASE),
    re.compile(r"\bRemove-Item\b.*(-Recurse|-Force)", re.IGNORECASE),
    re.compile(r"\breg\s+(delete|add)\b", re.IGNORECASE),
    re.compile(r"\bbcdedit\b", re.IGNORECASE),
    re.compile(r"\bvssadmin\s+delete\b", re.IGNORECASE),
    re.compile(r"\bnet\s+user\b", re.IGNORECASE),
    re.compile(r"\bnet\s+localgroup\b", re.IGNORECASE),
    re.compile(r"\bicacls\b.*(/grant|/deny|/remove)", re.IGNORECASE),
    re.compile(r"\b(iex|Invoke-Expression)\b", re.IGNORECASE),
    re.compile(r"\b(curl|wget|iwr)\b.*\|\s*(iex|sh|bash|cmd|powershell)", re.IGNORECASE),
    re.compile(r"\btaskkill\s+/f\s+/im\s+(svchost|csrss|lsass|explorer|services)\.exe", re.IGNORECASE),
]

# System directories that can never be modified or recursively traversed
RESTRICTED_SYSTEM_DIRS: List[str] = [
    os.environ.get("SystemRoot", "C:\\Windows").lower(),
    os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32").lower(),
    os.environ.get("ProgramFiles", "C:\\Program Files").lower(),
    os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)").lower(),
]

ALLOWED_URL_SCHEMES = {"http", "https"}


class SafetyValidator:
    """Enforces safety constraints on tools, paths, and URLs."""

    @classmethod
    def check_command_safety(cls, cmd_string: str) -> Tuple[bool, str]:
        """
        Validates whether a shell or execution string contains prohibited patterns.
        Returns (is_safe, refusal_reason).
        """
        if not cmd_string or not cmd_string.strip():
            return False, "Command string is empty."

        clean_cmd = cmd_string.strip()

        for pattern in BLOCKED_PATTERNS:
            if pattern.search(clean_cmd):
                return False, f"Action blocked by safety policy: contains restricted instruction '{pattern.pattern}'."

        return True, "Safe"

    @classmethod
    def check_url_safety(cls, url: str) -> Tuple[bool, str]:
        """
        Validates URL schemes to prevent arbitrary code execution or local file access.
        """
        if not url or not url.strip():
            return False, "URL cannot be empty."

        try:
            parsed = urlparse(url.strip())
            if not parsed.scheme:
                return False, "URL is missing scheme (must start with http:// or https://)."

            if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
                return False, f"URL scheme '{parsed.scheme}' is prohibited. Only http and https are allowed."

            if not parsed.netloc:
                return False, "Invalid URL host/domain."

            return True, "Safe"
        except Exception as e:
            return False, f"Malformed URL: {e}"

    @classmethod
    def check_path_safety(cls, path_str: str, allow_write: bool = False) -> Tuple[bool, str]:
        """
        Validates filesystem paths against restricted OS system roots.
        """
        if not path_str or not path_str.strip():
            return False, "Path is empty."

        try:
            resolved = Path(path_str).resolve()
            resolved_lower = str(resolved).lower()

            for sys_dir in RESTRICTED_SYSTEM_DIRS:
                if resolved_lower == sys_dir or resolved_lower.startswith(sys_dir + os.sep):
                    if allow_write:
                        return False, f"Write access to system directory '{sys_dir}' is strictly blocked."

            # Block root of drive wiping
            if str(resolved).endswith(":\\") or str(resolved).endswith(":/"):
                if allow_write:
                    return False, "Modifying or deleting drive root is strictly blocked."

            return True, "Safe"
        except Exception as e:
            return False, f"Invalid path resolution: {e}"
