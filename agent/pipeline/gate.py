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


class CedarGate(PolicyGate):
    """Cedar 闸门(spec 001 Phase 0)。

    mode='shadow'(默认):**永不阻断**,只让 CedarPDP 判定 + 审计,用于
    零破坏地收集策略缺口。mode='enforce':按 PDP 三态映射 GateResult。
    默认 PolicyGate 仍是 pass-through,本类需显式启用,不影响既有流程。
    """

    def __init__(self, mode: str = "shadow") -> None:
        from .pdp import CedarPDP, Decision
        self._pdp = CedarPDP(mode=mode)
        self._D = Decision
        self.mode = mode

    def check(self, step_name: str, ctx: "PipelineContext") -> GateResult:
        result = self._pdp.decide(
            principal_type="Workflow",
            principal_id=str(ctx.metadata.get("workflow", "unknown")),
            action=step_name,
            resource_type="Step",
            resource_attrs={},
            context={
                "trust": str(ctx.metadata.get("trust", "user")),
                "steps_done": len(ctx.log),
                "skip_blue": bool(ctx.metadata.get("skip_blue", False)),
            },
        )
        if self.mode == "shadow":
            return GateResult.ALLOW          # 非阻断;decide() 已审计
        return {
            self._D.ALLOW: GateResult.ALLOW,
            self._D.DENY: GateResult.DENY,
            self._D.REQUIRE_APPROVAL: GateResult.REQUIRE_APPROVAL,
        }[result.decision]
