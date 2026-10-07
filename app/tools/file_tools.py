"""
File Search and Metadata Tools for JARVIS.
Provides safe, scoped filesystem searching and file inspection within permitted boundaries.
"""

from datetime import datetime
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.tools.safety import SafetyValidator

logger = get_logger("tools.files")

# Directories skipped during recursive scans to prevent hanging or indexing system internals
EXCLUDED_DIR_NAMES = {
    ".git",
    ".gemini",
    "__pycache__",
    "node_modules",
    "appdata",
    "windows",
    "system volume information",
    "$recycle.bin",
    "recovery",
    ".pytest_cache",
    ".venv",
    "venv",
}


def search_files(
    query: str,
    root_dir: Optional[str] = None,
    max_results: int = 20,
    extensions: Optional[List[str]] = None,
    max_depth: int = 4,
) -> List[Dict[str, Any]]:
    """
    Searches for files matching a keyword query within allowed local directories.
    Permission Tier: SAFE.
    """
    if not query or not query.strip():
        return []

    target_root = Path(root_dir).resolve() if root_dir else Path.cwd()
    is_safe, reason = SafetyValidator.check_path_safety(str(target_root), allow_write=False)
    if not is_safe:
        logger.warning(f"File search rejected for path '{target_root}': {reason}")
        return []

    if not target_root.exists() or not target_root.is_dir():
        return []

    clean_query = query.strip().lower()
    norm_exts = [e.lower() if e.startswith(".") else f".{e.lower()}" for e in extensions] if extensions else None

    results: List[Dict[str, Any]] = []
    root_depth = len(target_root.parts)

    try:
        for current_root, dirs, files in os.walk(target_root):
            curr_path = Path(current_root)
            depth = len(curr_path.parts) - root_depth

            if depth > max_depth:
                dirs.clear()
                continue

            # Filter out ignored directories in-place
            dirs[:] = [d for d in dirs if d.lower() not in EXCLUDED_DIR_NAMES and not d.startswith(".")]

            for file in files:
                fname_lower = file.lower()
                if clean_query in fname_lower:
                    if norm_exts and not any(fname_lower.endswith(ext) for ext in norm_exts):
                        continue

                    full_path = curr_path / file
                    try:
                        stat = full_path.stat()
                        results.append({
                            "name": file,
                            "path": str(full_path),
                            "size_kb": round(stat.st_size / 1024, 1),
                            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        })
                    except (PermissionError, OSError):
                        continue

                    if len(results) >= max_results:
                        return results
    except Exception as e:
        logger.error(f"Error during file search: {e}")

    return results


def get_file_info(file_path: str) -> Dict[str, Any]:
    """
    Retrieves safe metadata for a target file or folder.
    Permission Tier: SAFE.
    """
    p = Path(file_path).resolve()
    is_safe, reason = SafetyValidator.check_path_safety(str(p), allow_write=False)
    if not is_safe:
        return {"exists": False, "error": reason}

    if not p.exists():
        return {"exists": False, "path": str(p)}

    try:
        stat = p.stat()
        return {
            "exists": True,
            "path": str(p),
            "name": p.name,
            "is_file": p.is_file(),
            "is_dir": p.is_dir(),
            "size_bytes": stat.st_size,
            "size_kb": round(stat.st_size / 1024, 2),
            "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        return {"exists": True, "path": str(p), "error": str(e)}
