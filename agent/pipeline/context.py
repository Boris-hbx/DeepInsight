"""PipelineContext — artifact store + metadata for step-to-step data flow."""

from __future__ import annotations

import time
from datetime import date
from pathlib import Path
from typing import Any


class PipelineContext:
    def __init__(self, task: str, **kwargs: Any) -> None:
        self.artifacts: dict[str, Any] = {}
        self.metadata: dict[str, Any] = {
            "task": task,
            "date": date.today().isoformat(),
            "start_time": time.time(),
            **kwargs,
        }
        self.log: list[dict[str, Any]] = []

    def put(self, name: str, data: Any) -> None:
        self.artifacts[name] = data

    def get(self, name: str) -> Any:
        if name not in self.artifacts:
            raise KeyError(f"Artifact '{name}' not found. Available: {list(self.artifacts.keys())}")
        return self.artifacts[name]

    def has(self, name: str) -> bool:
        return name in self.artifacts

    def get_all(self, names: list[str]) -> list[Any]:
        return [self.get(n) for n in names]

    def merge_lists(self, names: list[str]) -> list[Any]:
        """Merge multiple list artifacts into one flat list."""
        merged = []
        for name in names:
            val = self.get(name)
            if isinstance(val, list):
                merged.extend(val)
            else:
                merged.append(val)
        return merged

    def elapsed(self) -> float:
        return time.time() - self.metadata["start_time"]

    def add_log(self, step_name: str, status: str, detail: str = "") -> None:
        self.log.append({
            "step": step_name,
            "status": status,
            "detail": detail,
            "elapsed": self.elapsed(),
        })

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent
