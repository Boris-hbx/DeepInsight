"""Step base class and registry."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .context import PipelineContext


class Step(ABC):
    name: str = ""
    inputs: list[str] = []
    outputs: list[str] = []

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    @abstractmethod
    def run(self, ctx: PipelineContext) -> None:
        ...

    def skip_condition(self, ctx: PipelineContext) -> bool:
        return False


class StepRegistry:
    _steps: dict[str, type[Step]] = {}

    @classmethod
    def register(cls, step_class: type[Step]) -> type[Step]:
        cls._steps[step_class.name] = step_class
        return step_class

    @classmethod
    def get(cls, name: str) -> type[Step]:
        if name not in cls._steps:
            raise KeyError(f"Step '{name}' not registered. Available: {list(cls._steps.keys())}")
        return cls._steps[name]

    @classmethod
    def list_all(cls) -> list[str]:
        return list(cls._steps.keys())
