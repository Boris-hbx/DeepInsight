"""PolicyGate — step-level authorization check point. Pass-through now, Cedar later."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context import PipelineContext


class GateResult(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyDenied(Exception):
    def __init__(self, step_name: str, reason: str = "") -> None:
        self.step_name = step_name
        self.reason = reason
        super().__init__(f"Policy denied step '{step_name}': {reason}")


class PolicyGate:
    """Default pass-through gate. Subclass to integrate Cedar."""

    def check(self, step_name: str, ctx: PipelineContext) -> GateResult:
        return GateResult.ALLOW
