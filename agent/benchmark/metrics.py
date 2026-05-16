#!/usr/bin/env python3
"""
metrics.py — Collect and persist per-run metrics for the self-evolving agent.

Appends one JSON line per run to benchmark/metrics.jsonl.
"""

import json
import time
from datetime import date
from pathlib import Path
from typing import Any

METRICS_FILE = Path(__file__).resolve().parent / "metrics.jsonl"


class RunMetrics:
    def __init__(self, task: str, workflow: str = "unknown") -> None:
        self.task = task
        self.workflow = workflow
        self._start = time.monotonic()
        self.token_input = 0
        self.token_output = 0
        self.steps_executed = 0
        self.tools_used: list[str] = []
        self.new_tools: list[str] = []
        self.blue_challenges = 0
        self.blue_blocks = 0
        self.structure_ok: bool | None = None
        self.url_valid_rate: float | None = None
        self.workflow_fit: str = ""
        self.extra: dict[str, Any] = {}

    def add_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        self.token_input += input_tokens
        self.token_output += output_tokens

    def add_tool_used(self, name: str) -> None:
        if name not in self.tools_used:
            self.tools_used.append(name)

    def add_new_tool(self, name: str) -> None:
        self.new_tools.append(name)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": date.today().isoformat(),
            "task": self.task[:120],
            "workflow": self.workflow,
            "duration_s": round(time.monotonic() - self._start, 1),
            "token_input": self.token_input,
            "token_output": self.token_output,
            "token_total": self.token_input + self.token_output,
            "steps_executed": self.steps_executed,
            "tools_used": self.tools_used,
            "tools_used_count": len(self.tools_used),
            "new_tools": self.new_tools,
            "new_tools_count": len(self.new_tools),
            "blue_challenges": self.blue_challenges,
            "blue_blocks": self.blue_blocks,
            "structure_ok": self.structure_ok,
            "url_valid_rate": self.url_valid_rate,
            "workflow_fit": self.workflow_fit,
            **self.extra,
        }

    def save(self) -> None:
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(METRICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.to_dict(), ensure_ascii=False) + "\n")
