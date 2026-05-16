#!/usr/bin/env python3
"""
tool_health.py — Analyze tool registry health metrics.

CLI:  python -m agent.benchmark.tool_health
"""

import json
import sys
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "tools" / "registry.json"


def load_registry() -> list[dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        return []
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return data.get("tools", [])


def analyze(tools: list[dict[str, Any]]) -> dict[str, Any]:
    if not tools:
        return {"total": 0}

    total = len(tools)
    used = [t for t in tools if t.get("usage_count", 0) > 0]
    reused = [t for t in tools if t.get("usage_count", 0) > 1]
    zero_use = [t["name"] for t in tools if t.get("usage_count", 0) == 0]
    total_usage = sum(t.get("usage_count", 0) for t in tools)
    top_used = sorted(tools, key=lambda t: t.get("usage_count", 0), reverse=True)[:3]

    return {
        "total": total,
        "used_at_least_once": len(used),
        "reused_more_than_once": len(reused),
        "reuse_rate": round(len(reused) / total, 3) if total else 0,
        "zero_use_tools": zero_use,
        "total_usage_count": total_usage,
        "avg_usage": round(total_usage / total, 1) if total else 0,
        "top_3": [{"name": t["name"], "usage": t.get("usage_count", 0)} for t in top_used],
        "multi_version": [t["name"] for t in tools if t.get("version", 1) > 1],
    }


def main() -> None:
    tools = load_registry()
    result = analyze(tools)

    print("=== Tool Health Report ===\n")
    print(f"Total tools:       {result['total']}")
    print(f"Used (>0):         {result.get('used_at_least_once', 0)}")
    print(f"Reused (>1):       {result.get('reused_more_than_once', 0)}")
    print(f"Reuse rate:        {result.get('reuse_rate', 0):.0%}")
    print(f"Total invocations: {result.get('total_usage_count', 0)}")
    print(f"Avg usage/tool:    {result.get('avg_usage', 0)}")

    if result.get("zero_use_tools"):
        print(f"\nZero-use tools ({len(result['zero_use_tools'])}):")
        for name in result["zero_use_tools"]:
            print(f"  - {name}")

    if result.get("top_3"):
        print(f"\nTop 3 most used:")
        for t in result["top_3"]:
            print(f"  - {t['name']}: {t['usage']} calls")

    if result.get("multi_version"):
        print(f"\nMulti-version tools:")
        for name in result["multi_version"]:
            print(f"  - {name}")


if __name__ == "__main__":
    main()
