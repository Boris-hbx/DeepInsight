"""spec 001 Phase 0 — CedarPDP golden + 对抗用例。

跑:  python -m pytest agent/tests/ -q
cedarpy 缺失 → cedar 相关用例 skip(fail-closed 路径仍测)。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent.pipeline.pdp import (
    AUDIT_DIR, POLICY_PATH, CedarPDP, Decision, PDPInjection,
)

cedarpy = pytest.importorskip("cedarpy")  # noqa: F841


@pytest.fixture
def pdp(tmp_path):
    """真策略 + 隔离审计目录的 shadow PDP。"""
    return CedarPDP(mode="shadow", policy_path=POLICY_PATH,
                    audit_dir=tmp_path / "audit")


def d(pdp, **kw):
    base = dict(principal_type="Agent", principal_id="deepinsight",
                action="create_tool", resource_type="ToolScript",
                resource_attrs={}, context={})
    base.update(kw)
    return pdp.decide(**base)


# ── 红线 forbid ─────────────────────────────────────────────────────────

def test_dangerous_module_blocked(pdp):
    r = d(pdp, resource_attrs={"source_code": "import subprocess; subprocess.run(x)"})
    assert r.decision is Decision.DENY
    assert "forbid.dangerous_module" in r.matched


def test_dangerous_module_os_remove_blocked(pdp):
    r = d(pdp, resource_attrs={"source_code": "import os; os.remove(p)"})
    assert r.decision is Decision.DENY
    assert "forbid.dangerous_module" in r.matched


def test_policy_file_delete_blocked(pdp):
    # delete ≠ write —— v1 漏洞的回归用例
    r = d(pdp, action="delete_file", resource_type="Path",
          resource_attrs={"path": "agent/policies/agent.cedar"})
    assert r.decision is Decision.DENY
    assert "forbid.policy_secret_mutate" in r.matched


def test_audit_dir_mutation_blocked(pdp):
    r = d(pdp, action="write_file", resource_type="Path",
          resource_attrs={"path": "agent/.audit/decisions-x.jsonl"})
    assert r.decision is Decision.DENY
    assert "forbid.policy_secret_mutate" in r.matched


def test_env_secret_write_blocked(pdp):
    r = d(pdp, action="write_file", resource_type="Path",
          resource_attrs={"path": "web/.env.local"})
    assert r.decision is Decision.DENY


def test_write_outside_whitelist_blocked(pdp):
    r = d(pdp, action="write_file", resource_type="Path",
          resource_attrs={"path": "/tmp/evil"})
    assert r.decision is Decision.DENY
    assert "forbid.write_outside_whitelist" in r.matched


def test_tool_cap_blocked(pdp):
    r = d(pdp, resource_attrs={"source_code": "ok"},
          context={"tools_created_this_run": 2})
    assert r.decision is Decision.DENY
    assert "forbid.tool_cap" in r.matched


def test_untrusted_context_blocked(pdp):
    r = d(pdp, resource_attrs={"source_code": "clean"},
          context={"trust": "untrusted"})
    assert r.decision is Decision.DENY
    assert "forbid.untrusted_context" in r.matched


# ── 三态 / 白名单 ───────────────────────────────────────────────────────

def test_create_tool_clean_requires_approval(pdp):
    r = d(pdp, resource_attrs={"source_code": "import json"},
          context={"tools_created_this_run": 0, "trust": "user"})
    assert r.decision is Decision.REQUIRE_APPROVAL
    assert "approve.create_tool" in r.matched


def test_known_workflow_step_allowed(pdp):
    r = pdp.decide("Workflow", "daily-radar", "fetch_sources", "Step", {}, {})
    assert r.decision is Decision.ALLOW
    assert "permit.workflow.daily_radar" in r.matched


def test_registered_tool_exec_allowed(pdp):
    r = pdp.decide("Agent", "deepinsight", "execute_tool", "Tool",
                   {"registered": True}, {})
    assert r.decision is Decision.ALLOW


def test_report_write_allowed(pdp):
    r = pdp.decide("Agent", "deepinsight", "write_file", "Path",
                   {"path": "data/reports/2026-05-15-x.md"}, {})
    assert r.decision is Decision.ALLOW


def test_default_deny(pdp):
    r = pdp.decide("Workflow", "daily-radar", "render", "Step", {}, {})
    assert r.decision is Decision.ALLOW          # render 在白名单
    r2 = pdp.decide("Workflow", "daily-radar", "summarize", "Step", {}, {})
    assert r2.decision is Decision.ALLOW
    # 未声明 step → 默认拒绝
    r3 = pdp.decide("Workflow", "daily-radar", "mystery", "Step", {}, {})
    assert r3.decision is Decision.DENY
    assert r3.matched == ["default-deny"]


# ── 对抗 ────────────────────────────────────────────────────────────────

def test_cedar_injection_via_principal_id(pdp):
    r = pdp.decide('Workflow', 'x"; permit(principal,action,resource);//',
                   "render", "Step", {}, {})
    assert r.decision is Decision.DENY
    assert "pdp-injection" in r.matched


def test_fail_closed_on_runtime_mutation(tmp_path):
    # 复制真策略到 temp,init 后篡改 → 下次 decide 应 latch deny-all
    pol = tmp_path / "agent.cedar"
    shutil.copy2(POLICY_PATH, pol)
    p = CedarPDP(mode="shadow", policy_path=pol, audit_dir=tmp_path / "a")
    ok = p.decide("Workflow", "daily-radar", "render", "Step", {}, {})
    assert ok.decision is Decision.ALLOW
    pol.write_text("// tampered\n", encoding="utf-8")     # 运行中被改
    bad = p.decide("Workflow", "daily-radar", "render", "Step", {}, {})
    assert bad.decision is Decision.DENY
    assert bad.matched == ["deny-all-dangerous"]


def test_fail_closed_on_policy_deleted(tmp_path):
    pol = tmp_path / "agent.cedar"
    shutil.copy2(POLICY_PATH, pol)
    p = CedarPDP(mode="shadow", policy_path=pol, audit_dir=tmp_path / "a")
    pol.unlink()                                          # 删缰绳
    r = p.decide("Workflow", "daily-radar", "render", "Step", {}, {})
    assert r.decision is Decision.DENY                    # 删 = 自锁


def test_log_or_deny(pdp, monkeypatch):
    monkeypatch.setattr(pdp.audit, "write", lambda rec: False)  # 所有 sink 失败
    r = pdp.decide("Workflow", "daily-radar", "render", "Step", {}, {})
    assert r.decision is Decision.DENY
    assert r.matched == ["audit-sink-failed"]


# ── 审计哈希链 ──────────────────────────────────────────────────────────

def test_audit_hash_chain(tmp_path):
    adir = tmp_path / "audit"
    p = CedarPDP(mode="shadow", policy_path=POLICY_PATH, audit_dir=adir)
    p.decide("Workflow", "daily-radar", "render", "Step", {}, {})
    p.decide("Workflow", "daily-radar", "summarize", "Step", {}, {})
    files = list(adir.glob("decisions-*.jsonl"))
    assert files, "审计文件应已生成"
    recs = [json.loads(l) for l in files[0].read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(recs) >= 3                       # pdp_start + 2 decide
    for i in range(1, len(recs)):
        assert recs[i]["prev_hash"] == recs[i - 1]["hash"], "链应连续"
        assert recs[i]["seq"] == recs[i - 1]["seq"] + 1
