#!/usr/bin/env python3
"""
ToolManager — register, discover, execute, and archive tools.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent  # agent/
REGISTRY_PATH = ROOT / "tools" / "registry.json"
TOOLS_DIR = ROOT / "tools"
ARCHIVE_DIR = TOOLS_DIR / "archive"


def _load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.exists():
        return {"tools": []}
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _save_registry(reg: dict[str, Any]) -> None:
    REGISTRY_PATH.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


class ToolManager:
    def __init__(self) -> None:
        self.registry = _load_registry()
        self.tools_dir = TOOLS_DIR
        self.archive_dir = ARCHIVE_DIR

    def list_tools(self) -> list[dict[str, Any]]:
        return self.registry.get("tools", [])

    def find_tool(self, name: str) -> dict[str, Any] | None:
        for t in self.registry.get("tools", []):
            if t["name"] == name:
                return t
        return None

    def register(
        self,
        name: str,
        description: str,
        path: str,
        language: str,
        args_schema: str = "",
    ) -> None:
        tools = self.registry.setdefault("tools", [])
        existing = self.find_tool(name)
        if existing:
            self._archive_tool(name)
            existing["description"] = description
            existing["path"] = path
            existing["language"] = language
            existing["args_schema"] = args_schema
            existing["updated_at"] = str(date.today())
            existing["version"] = existing.get("version", 1) + 1
        else:
            tools.append(
                {
                    "name": name,
                    "description": description,
                    "path": path,
                    "language": language,
                    "args_schema": args_schema,
                    "created_at": str(date.today()),
                    "updated_at": str(date.today()),
                    "version": 1,
                    "usage_count": 0,
                }
            )
        _save_registry(self.registry)

    def _archive_tool(self, name: str) -> None:
        tool = self.find_tool(name)
        if not tool:
            return
        tool_path = ROOT / tool["path"]
        if not tool_path.exists():
            return
        archive_sub = self.archive_dir / name
        archive_sub.mkdir(parents=True, exist_ok=True)
        v = tool.get("version", 1)
        arch_name = f"v{v}_{date.today()}.py"
        shutil.copy2(tool_path, archive_sub / arch_name)

    def execute(self, name: str, args: list[str] | None = None) -> tuple[int, str, str]:
        tool = self.find_tool(name)
        if not tool:
            raise KeyError(f"Tool not found: {name}")
        tool_path = ROOT / tool["path"]
        if not tool_path.exists():
            raise FileNotFoundError(f"Tool script not found: {tool_path}")

        cmd = [sys.executable, str(tool_path)] + (args or [])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self._increment_usage(name)
        return result.returncode, result.stdout, result.stderr

    def _increment_usage(self, name: str) -> None:
        for t in self.registry.get("tools", []):
            if t["name"] == name:
                t["usage_count"] = t.get("usage_count", 0) + 1
                _save_registry(self.registry)
                break