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

    def __init__(self, mode: str = "shadow", audit_dir=None) -> None:
        from .pdp import AUDIT_DIR, CedarPDP, Decision
        self._pdp = CedarPDP(mode=mode, audit_dir=audit_dir or AUDIT_DIR)
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


class LoopGuard:
    """AgentLoop 的 PEP 助手(spec 001 Phase 2 接入点 B,扼颈点防御)。

    - off    → 完全不介入(返回 None;ToolManager 行为不变)
    - shadow → 判定 + 审计,**永不 raise**(默认;安全收集)
    - enforce→ DENY 或「非交互命中 @gate(approval)」→ raise PolicyDenied
               (loop 捕获后走 DenialFeedback 重规划;不杀 agent)

    ⚠ enforce 但沙箱(spec 002)未实现:Cedar 确定性红线 + 审计仍生效,
    但生成工具子进程的 syscall 不经 Cedar —— 防御纵深不完整。启动即 loud
    WARN + 审计 `sandbox=absent`,诚实记录(spec 001 §4.2 强制沙箱)。
    """

    def __init__(self, mode: str | None = None, audit_dir=None,
                 interactive: bool = False) -> None:
        import os
        import sys
        from datetime import datetime, timezone

        from .pdp import AUDIT_DIR, CedarPDP, Decision

        m = (mode or os.environ.get("DEEPINSIGHT_CEDAR_MODE", "shadow")).strip().lower()
        if m not in ("off", "shadow", "enforce"):
            m = "shadow"
        self.mode = m
        self.interactive = interactive
        self._D = Decision
        if m == "off":
            self._pdp = None
            return
        self._pdp = CedarPDP(mode=m, audit_dir=audit_dir or AUDIT_DIR)
        if m == "enforce":
            sys.stderr.write(
                "[LoopGuard] ⚠ enforce 但沙箱(spec 002)未实现:Cedar 红线+审计"
                "生效,但生成工具子进程 syscall 不经 Cedar,防御纵深不完整。\n")
            sys.stderr.flush()
            try:
                self._pdp.audit.write({
                    "ts_wall": datetime.now(timezone.utc).isoformat(),
                    "event": "loop_enforce_unsandboxed", "mode": "enforce",
                    "sandbox": "absent", "decision": "-", "matched": [],
                    "severity": "high",
                })
            except Exception:
                pass

    def guard(self, action: str, resource_type: str, resource_attrs: dict,
              context: dict, label: str = ""):
        """返回 PDPResult(off → None)。enforce 阻断时 raise PolicyDenied。"""
        if self._pdp is None:                       # off
            return None
        res = self._pdp.decide("Agent", "deepinsight", action,
                               resource_type, resource_attrs, context)
        if self.mode == "shadow":
            return res                              # 非阻断;已审计
        block = res.decision is self._D.DENY or (
            res.decision is self._D.REQUIRE_APPROVAL and not self.interactive)
        if block:
            raise PolicyDenied(label or action,
                               f"{res.decision.value}: {res.reason} {res.matched}")
        return res
