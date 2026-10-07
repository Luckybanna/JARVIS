"""
System Telemetry and Audio Hardware Control Tools for JARVIS.
Provides real-time CPU, RAM, disk, battery metrics, process listings, and master volume controls.
"""

from datetime import datetime, timezone
import os
import platform
import time
from typing import Any, Dict, List, Optional

import psutil

from app.core.logger import get_logger

logger = get_logger("tools.system")


def _get_endpoint_volume():
    """Helper to retrieve Windows pycaw master EndpointVolume object safely."""
    try:
        from pycaw.pycaw import AudioUtilities
        devices = AudioUtilities.GetSpeakers()
        if devices and hasattr(devices, "EndpointVolume"):
            return devices.EndpointVolume
    except Exception as e:
        logger.warning(f"Unable to access Windows audio endpoint: {e}")
    return None


def get_system_stats() -> Dict[str, Any]:
    """
    Returns real-time Windows system telemetry: CPU, RAM, disk, battery, and uptime.
    Permission Tier: SAFE.
    """
    # CPU
    cpu_pct = psutil.cpu_percent(interval=0.05)
    cpu_count_logical = psutil.cpu_count(logical=True)
    cpu_count_physical = psutil.cpu_count(logical=False)

    # Virtual Memory (RAM)
    vm = psutil.virtual_memory()
    total_ram_mb = int(vm.total / (1024 * 1024))
    available_ram_mb = int(vm.available / (1024 * 1024))
    ram_pct = vm.percent

    # Disk Space (Root C: and Active Drive)
    disks = {}
    for drive in ["C:\\"]:
        try:
            usage = psutil.disk_usage(drive)
            disks[drive] = {
                "total_gb": round(usage.total / (1024 ** 3), 1),
                "free_gb": round(usage.free / (1024 ** 3), 1),
                "used_percent": usage.percent,
            }
        except Exception:
            pass

    # Battery
    battery = psutil.sensors_battery()
    battery_info = None
    if battery is not None:
        battery_info = {
            "percent": round(battery.percent, 1),
            "power_plugged": battery.power_plugged,
            "seconds_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1,
        }

    # Uptime
    boot_time = psutil.boot_time()
    uptime_sec = time.time() - boot_time
    hours, remainder = divmod(int(uptime_sec), 3600)
    minutes, _ = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m"

    return {
        "os": f"{platform.system()} {platform.release()} ({platform.architecture()[0]})",
        "cpu": {
            "usage_percent": cpu_pct,
            "logical_cores": cpu_count_logical,
            "physical_cores": cpu_count_physical,
        },
        "memory": {
            "total_mb": total_ram_mb,
            "available_mb": available_ram_mb,
            "used_percent": ram_pct,
        },
        "disk": disks,
        "battery": battery_info,
        "uptime": uptime_str,
        "process_count": len(psutil.pids()),
    }


def get_volume() -> Dict[str, Any]:
    """
    Returns current master audio volume (0-100) and mute status.
    Permission Tier: SAFE.
    """
    vol = _get_endpoint_volume()
    if vol is None:
        return {"volume_percent": 50, "muted": False, "device_available": False}

    try:
        scalar = vol.GetMasterVolumeLevelScalar()
        muted = bool(vol.GetMute())
        return {
            "volume_percent": round(scalar * 100),
            "muted": muted,
            "device_available": True,
        }
    except Exception as e:
        logger.error(f"Failed to query master volume: {e}")
        return {"volume_percent": 0, "muted": False, "error": str(e), "device_available": False}


def set_volume(level: int) -> Dict[str, Any]:
    """
    Sets master audio volume to a target percentage (0-100) and automatically unmutes.
    Permission Tier: SAFE.
    """
    vol = _get_endpoint_volume()
    clamped = max(0, min(100, int(level)))
    scalar = clamped / 100.0

    if vol is None:
        return {"volume_percent": clamped, "muted": False, "device_available": False}

    try:
        vol.SetMasterVolumeLevelScalar(scalar, None)
        # If user sets volume > 0, make sure it is unmuted
        if clamped > 0 and vol.GetMute():
            vol.SetMute(0, None)

        return {
            "volume_percent": clamped,
            "muted": bool(vol.GetMute()),
            "device_available": True,
        }
    except Exception as e:
        logger.error(f"Failed to set master volume to {level}: {e}")
        return {"volume_percent": clamped, "error": str(e), "device_available": False}


def mute_volume(mute: bool = True) -> Dict[str, Any]:
    """
    Mutes or unmutes master audio output.
    Permission Tier: SAFE.
    """
    vol = _get_endpoint_volume()
    if vol is None:
        return {"muted": mute, "device_available": False}

    try:
        vol.SetMute(1 if mute else 0, None)
        scalar = vol.GetMasterVolumeLevelScalar()
        return {
            "volume_percent": round(scalar * 100),
            "muted": bool(vol.GetMute()),
            "device_available": True,
        }
    except Exception as e:
        logger.error(f"Failed to set mute status to {mute}: {e}")
        return {"muted": mute, "error": str(e), "device_available": False}


def list_running_processes(top_n: int = 10, sort_by: str = "cpu") -> List[Dict[str, Any]]:
    """
    Lists top running applications/processes sorted by CPU or memory usage.
    Permission Tier: SAFE.
    """
    results: List[Dict[str, Any]] = []

    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = proc.info
            name = info.get("name") or "Unknown"
            pid = info.get("pid")
            cpu = info.get("cpu_percent") or 0.0
            mem_info = info.get("memory_info")
            mem_mb = round(mem_info.rss / (1024 * 1024), 1) if mem_info else 0.0

            results.append({
                "pid": pid,
                "name": name,
                "cpu_percent": cpu,
                "memory_mb": mem_mb,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    sort_key = "cpu_percent" if sort_by.lower() == "cpu" else "memory_mb"
    results.sort(key=lambda p: p.get(sort_key, 0.0), reverse=True)
    return results[: max(1, min(50, top_n))]
