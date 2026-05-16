"""spec 001 Phase 2 — LoopGuard + ToolManager 扼颈点 PEP + DenialFeedback 重规划。

不触发真实 Anthropic API:只测 seam(LoopGuard / ToolManager.register /
_create_tool_with_replan 逻辑)。跑:python -m pytest agent/tests/ -q
"""

from __future__ import annotations

import pytest

pytest.importorskip("cedarpy")

from agent.loop import AgentLoop, DenialFeedback
from agent.pipeline.gate import LoopGuard, PolicyDenied
from agent.tool_manager import ToolManager


@pytest.fixture
def guard_enforce(tmp_path):
    return LoopGuard(mode="enforce", audit_dir=tmp_path / "a")


@pytest.fixture
def guard_shadow(tmp_path):
    return LoopGuard(mode="shadow", audit_dir=tmp_path / "a")


# ── LoopGuard 三模式 ────────────────────────────────────────────────────

def test_off_returns_none():
    g = LoopGuard(mode="off")
    assert g.guard("create_tool", "ToolScript", {"source_code": "import subprocess"}, {}) is None


def test_shadow_never_raises_even_dangerous(guard_shadow):
    # 危险源码,shadow 也不阻断(只判定+审计)
    r = guard_shadow.guard("create_tool", "ToolScript",
                           {"source_code": "import subprocess; subprocess.run(x)"},
                           {"trust": "user"}, label="evil")
    assert r is not None and r.decision.value == "DENY"   # 判为 DENY 但不 raise


def test_enforce_dangerous_create_tool_denied(guard_enforce):
    with pytest.raises(PolicyDenied):
        guard_enforce.guard("create_tool", "ToolScript",
                            {"source_code": "import subprocess; subprocess.run(x)"},
                            {"trust": "user"}, label="evil")


def test_enforce_clean_create_tool_blocks_noninteractive(guard_enforce):
    # 干净源码 → @gate(approval) → 非交互 enforce 默认 DENY(spec:无人值守不降级)
    with pytest.raises(PolicyDenied):
        guard_enforce.guard("create_tool", "ToolScript",
                            {"source_code": "import json"},
                            {"tools_created_this_run": 0, "trust": "user"})


def test_enforce_interactive_allows_approval(tmp_path):
    g = LoopGuard(mode="enforce", audit_dir=tmp_path / "a", interactive=True)
    r = g.guard("create_tool", "ToolScript", {"source_code": "import json"},
                {"tools_created_this_run": 0, "trust": "user"})
    assert r.decision.value == "REQUIRE_APPROVAL"          # interactive 不阻断


def test_enforce_report_write_allowed(guard_enforce):
    r = guard_enforce.guard("write_file", "Path",
                            {"path": "data/reports/2026-05-15-x.md"},
                            {"trust": "user"}, label="save_report")
    assert r.decision.value == "ALLOW"


def test_enforce_changelog_write_allowed(guard_enforce):
    # 任务 7 策略缺口修复的回归:agent/changelog.md 现已在白名单
    r = guard_enforce.guard("write_file", "Path",
                            {"path": "agent/changelog.md"},
                            {"trust": "user"}, label="append_changelog")
    assert r.decision.value == "ALLOW"


# ── ToolManager 扼颈点 PEP ──────────────────────────────────────────────

def test_toolmanager_stores_policy():
    g = LoopGuard(mode="off")
    tm = ToolManager(policy=g)
    assert tm.policy is g


def test_toolmanager_register_denied_in_enforce(guard_enforce):
    # register_tool 为 @gate(approval) → enforce 非交互 → PolicyDenied
    # (guard 在 register 体首,raise 早于任何 registry 变更,无副作用)
    tm = ToolManager(policy=guard_enforce)
    with pytest.raises(PolicyDenied):
        tm.register(name="evil", description="x", path="tools/evil.py",
                    language="python", args_schema="")


def test_toolmanager_no_policy_unchanged():
    tm = ToolManager()
    assert tm.policy is None


# ── DenialFeedback + 有界重规划 ─────────────────────────────────────────

class _Metrics:
    def __init__(self): self.added = []
    def add_new_tool(self, n): self.added.append(n)


class _LoopStub:
    """只借 _create_tool_with_replan 逻辑,不构造真 AgentLoop(免 API)。"""
    _create_tool_with_replan = AgentLoop._create_tool_with_replan

    def __init__(self, fail_times: int):
        self.calls = 0
        self.fail_times = fail_times
        self._last_denial = None

    def _create_tool(self, task, spec):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise PolicyDenied("create_tool", "DENY: forbid.dangerous_module")


def test_replan_succeeds_within_cap():
    s = _LoopStub(fail_times=2)
    m = _Metrics()
    ok = s._create_tool_with_replan("t", {"name": "x"}, m, max_replans=2)
    assert ok is True
    assert s.calls == 3                       # 2 拒 + 第 3 次成功
    assert m.added == ["x"]


def test_replan_gives_up_cleanly_not_crash():
    s = _LoopStub(fail_times=99)              # 永远被拒
    m = _Metrics()
    ok = s._create_tool_with_replan("t", {"name": "x"}, m, max_replans=2)
    assert ok is False                        # 干净降级,不抛
    assert isinstance(s._last_denial, DenialFeedback)
    assert s._last_denial.action == "create_tool"
    assert m.added == []                      # 没建工具
