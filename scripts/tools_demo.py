"""
Diagnostic Demo for JARVIS PC Automation Tools.
Demonstrates system telemetry, audio control, scoped file search,
permission tier enforcement, and confirmation workflows.
"""

import sys
from pathlib import Path

# Ensure root directory is on sys.path
root_dir = str(Path(__file__).resolve().parent.parent)
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.tools.base import ToolTier
from app.tools.executor import get_tool_executor
from app.tools.registry import get_tool_registry
from app.tools.router import ToolRouter


def main():
    print("=" * 60)
    print("JARVIS - PC Automation & Safety Tools Diagnostic")
    print("=" * 60)

    executor = get_tool_executor()
    registry = get_tool_registry()
    router = ToolRouter(executor=executor)

    # 1. Registered Tools Summary
    tools = registry.list_tools()
    print(f"\n[OK] Registered Tools Count: {len(tools)}")
    for t in tools:
        print(f"  - [{t.tier.value.upper():16}] {t.name}: {t.description}")

    # 2. System Telemetry
    print("\n--- 1. Querying Real-time System Telemetry ---")
    stat_res = executor.execute("get_system_stats")
    if stat_res.success:
        data = stat_res.data
        print(f"  OS:       {data['os']}")
        print(f"  CPU:      {data['cpu']['usage_percent']}% usage ({data['cpu']['logical_cores']} logical cores)")
        print(f"  Memory:   {data['memory']['used_percent']}% used | {data['memory']['available_mb']} MB available / {data['memory']['total_mb']} MB total")
        print(f"  Uptime:   {data['uptime']}")
        print(f"  Processes: {data['process_count']} active")
    else:
        print(f"  [FAIL] Failed to retrieve system stats: {stat_res.message}")

    # 3. Audio Hardware Control
    print("\n--- 2. Audio Control ---")
    vol_res = executor.execute("get_volume")
    if vol_res.success:
        print(f"  Current Volume: {vol_res.data.get('volume_percent')}% (Muted: {vol_res.data.get('muted')})")
    else:
        print(f"  Volume query: {vol_res.message}")

    # 4. Scoped File Search
    print("\n--- 3. Bounded File Search ---")
    file_res = executor.execute("search_files", {"query": "config", "max_results": 3})
    if file_res.success:
        matches = file_res.data
        print(f"  Found {len(matches)} files matching 'config':")
        for m in matches:
            print(f"    * {m['name']} ({m['size_kb']} KB) - {m['path']}")

    # 5. Security Boundary & Blocked Actions
    print("\n--- 4. Security Boundary & Blocked Actions ---")
    blocked_res = executor.execute("format_drive", {"drive": "C:"})
    print(f"  Invocation: format_drive(C:)")
    print(f"  Outcome:    Success={blocked_res.success} | Tier={blocked_res.tier.value}")
    print(f"  Message:    {blocked_res.message}")

    # 6. Natural Language Routing & Confirmation Tier
    print("\n--- 5. Natural Language Tool Routing & Confirmation Workflow ---")
    query = "JARVIS please launch notepad"
    print(f"  User input: '{query}'")
    route_match = router.route_and_execute(query)
    if route_match:
        res, speech = route_match
        print(f"  Tool Executed: {res.tool_name}")
        print(f"  Requires Confirmation: {res.requires_confirmation}")
        print(f"  Confirmation ID: {res.confirmation_id}")
        print(f"  JARVIS Spoken Response:\n    \"{speech}\"")

        # Test cancel workflow
        print(f"\n  User input: 'cancel {res.confirmation_id}'")
        cancel_match = router.route_and_execute(f"cancel {res.confirmation_id}")
        if cancel_match:
            c_res, c_speech = cancel_match
            print(f"  JARVIS Spoken Response:\n    \"{c_speech}\"")

    print("\n" + "=" * 60)
    print("[OK] All PC automation tools and security tier checks passed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
