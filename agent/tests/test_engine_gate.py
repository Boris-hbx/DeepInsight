"""spec 001 Phase 1 — CedarGate 接入 PipelineEngine(enforce pipeline)。

跑:  python -m pytest agent/tests/ -q
"""

from __future__ import annotations

import pytest

pytest.importorskip("cedarpy")

from agent.pipeline.context import PipelineContext
from agent.pipeline.engine import PipelineEngine, _resolve_gate
from agent.pipeline.gate import CedarGate, PolicyDenied, PolicyGate
from agent.pipeline.step import Step, StepRegistry


# ── 闸门选择优先级 ──────────────────────────────────────────────────────

def test_mode_off_is_passthrough():
    eng = PipelineEngine(cedar_mode="off")
    assert type(eng.gate) is PolicyGate


def test_mode_shadow_default():
    eng = PipelineEngine(cedar_mode="shadow")
    assert isinstance(eng.gate, CedarGate) and eng.gate.mode == "shadow"


def test_mode_enforce():
    eng = PipelineEngine(cedar_mode="enforce")
    assert isinstance(eng.gate, CedarGate) and eng.gate.mode == "enforce"


def test_env_var_respected(monkeypatch):
    monkeypatch.setenv("DEEPINSIGHT_CEDAR_MODE", "off")
    assert type(_resolve_gate(None)) is PolicyGate
    monkeypatch.setenv("DEEPINSIGHT_CEDAR_MODE", "enforce")
    g = _resolve_gate(None)
    assert isinstance(g, CedarGate) and g.mode == "enforce"


def test_explicit_gate_wins():
    sentinel = PolicyGate()
    eng = PipelineEngine(gate=sentinel, cedar_mode="enforce")
    assert eng.gate is sentinel


# ── 端到端:enforce 真阻断,shadow 不阻断 ───────────────────────────────

class _DummyStep(Step):
    name = "_dummy"
    def run(self, ctx): ctx.put("ran", True)


def _register(name):
    StepRegistry.register(type(f"S_{name}", (_DummyStep,), {"name": name}))


def _wf(tmp_path, wf_name, step_name):
    _register(step_name)
    p = tmp_path / "wf.yaml"
    p.write_text(f"name: {wf_name}\nsteps:\n  - step: {step_name}\n", encoding="utf-8")
    return p


def _engine(mode, tmp_path):
    eng = PipelineEngine(gate=CedarGate(mode=mode, audit_dir=tmp_path / "audit"))
    return eng


def test_enforce_blocks_non_whitelisted_step(tmp_path):
    # daily-radar 未声明 'noopx' → 默认拒绝 → engine 抛 PolicyDenied
    wf = _wf(tmp_path, "daily-radar", "noopx")
    eng = _engine("enforce", tmp_path)
    with pytest.raises(PolicyDenied):
        eng.run(wf, task="t")


def test_enforce_allows_whitelisted_step(tmp_path):
    # daily-radar/render 在白名单 → 放行 → step 执行
    wf = _wf(tmp_path, "daily-radar", "render")
    eng = _engine("enforce", tmp_path)
    ctx = eng.run(wf, task="t")
    assert ctx.has("ran") and ctx.get("ran") is True


def test_shadow_does_not_block(tmp_path):
    # 同样未声明的 step,shadow 下不阻断,step 照跑(只审计)
    wf = _wf(tmp_path, "daily-radar", "shadowx")
    eng = _engine("shadow", tmp_path)
    ctx = eng.run(wf, task="t")
    assert ctx.has("ran") and ctx.get("ran") is True
