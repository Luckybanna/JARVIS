"""
Application Management and Web Navigation Tools for JARVIS.
Handles launching approved applications, safely terminating processes, and opening verified URLs.
"""

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional
import webbrowser

import psutil

from app.core.logger import get_logger
from app.tools.safety import SafetyValidator

logger = get_logger("tools.apps")

# Whitelist of common, verified Windows desktop utilities
APPROVED_APP_MAP: Dict[str, str] = {
    "notepad": "notepad.exe",
    "notes": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "mspaint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "files": "explorer.exe",
    "taskmgr": "taskmgr.exe",
    "task manager": "taskmgr.exe",
    "cmd": "cmd.exe",
    "command prompt": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "edge": "msedge.exe",
    "browser": "msedge.exe",
    "chrome": "chrome.exe",
    "vscode": "code",
    "code": "code",
    "spotify": "spotify.exe",
}

# Critical system processes that can NEVER be terminated
PROTECTED_PROCESSES = {
    "system",
    "registry",
    "smss.exe",
    "csrss.exe",
    "wininit.exe",
    "services.exe",
    "lsass.exe",
    "svchost.exe",
    "fontdrvhost.exe",
    "dwm.exe",
    "spoolsv.exe",
    "explorer.exe",
    "taskhostw.exe",
    "sihost.exe",
}


def launch_app(app_name: str, args: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Launches an approved application executable.
    Permission Tier: CONFIRM_REQUIRED.
    """
    clean_name = app_name.strip().lower()
    target_exe = APPROVED_APP_MAP.get(clean_name, app_name.strip())

    # Safety check on target executable
    is_safe, reason = SafetyValidator.check_command_safety(target_exe)
    if not is_safe:
        return {"launched": False, "error": reason}

    cmd = [target_exe]
    if args:
        for arg in args:
            is_arg_safe, arg_reason = SafetyValidator.check_command_safety(arg)
            if not is_arg_safe:
                return {"launched": False, "error": f"Prohibited argument: {arg_reason}"}
            cmd.append(arg)

    try:
        # Launch detached from current terminal
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        logger.info(f"Launched application '{target_exe}' with PID {proc.pid}")
        return {
            "launched": True,
            "app_name": app_name,
            "executable": target_exe,
            "pid": proc.pid,
        }
    except FileNotFoundError:
        # Check if executable can be located via shutil.which
        resolved = shutil.which(target_exe)
        if not resolved:
            return {
                "launched": False,
                "error": f"Executable for '{app_name}' ('{target_exe}') could not be found in PATH.",
            }
        try:
            cmd[0] = resolved
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"launched": True, "app_name": app_name, "executable": resolved, "pid": proc.pid}
        except Exception as e:
            return {"launched": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Error launching application '{app_name}': {e}")
        return {"launched": False, "error": str(e)}


def close_app(process_name: str, force: bool = False) -> Dict[str, Any]:
    """
    Closes running instances of an application by process or executable name.
    Permission Tier: CONFIRM_REQUIRED.
    """
    clean_target = process_name.strip().lower()
    if not clean_target.endswith(".exe"):
        clean_target += ".exe"

    if clean_target in PROTECTED_PROCESSES:
        return {
            "closed": False,
            "error": f"Refusing to terminate critical operating system process '{clean_target}'.",
        }

    terminated_pids: List[int] = []
    errors: List[str] = []

    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            if pname == clean_target:
                pid = proc.info["pid"]
                if force:
                    proc.kill()
                else:
                    proc.terminate()
                terminated_pids.append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            errors.append(str(e))

    if not terminated_pids:
        return {
            "closed": False,
            "count": 0,
            "message": f"No active process matching '{clean_target}' was found.",
        }

    logger.info(f"Closed {len(terminated_pids)} instances of '{clean_target}': {terminated_pids}")
    return {
        "closed": True,
        "process_name": clean_target,
        "count": len(terminated_pids),
        "pids": terminated_pids,
    }


def open_url(url: str) -> Dict[str, Any]:
    """
    Opens a verified web URL in the system's default browser.
    Permission Tier: CONFIRM_REQUIRED.
    """
    is_safe, reason = SafetyValidator.check_url_safety(url)
    if not is_safe:
        return {"opened": False, "url": url, "error": reason}

    try:
        opened = webbrowser.open(url.strip())
        logger.info(f"Opened URL '{url}' in default browser: {opened}")
        return {"opened": True, "url": url.strip()}
    except Exception as e:
        logger.error(f"Failed to open URL '{url}': {e}")
        return {"opened": False, "url": url, "error": str(e)}
