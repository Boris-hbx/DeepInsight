"""spec 002 Tier A — 硬化启动器测试(跨平台,免管理员子集)。

跑:python -m pytest agent/tests/ -q
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from agent.pipeline.sandbox import detect_tier, run_sandboxed

PY = sys.executable


def _run(code, *, mode="advisory", jail_root=None, timeout=30, protect=None, argv=()):
    cmd = [PY, "-c", code, *map(str, argv)]
    return run_sandboxed(cmd, mode=mode, jail_root=jail_root,
                         timeout=timeout, protect_paths=protect)


# ── env / 凭证 / cwd 隔离(预防,真生效)──────────────────────────────

def test_secret_env_stripped(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-SECRET")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-SECRET")
    rc, out, err, rep = _run(
        "import os;print(os.environ.get('ANTHROPIC_API_KEY','MISSING'),"
        "os.environ.get('AWS_SECRET_ACCESS_KEY','MISSING'))",
        jail_root=tmp_path)
    assert rc == 0
    assert "MISSING MISSING" in out
    assert "env-sanitized" in rep.enforcing


def test_credentials_unreachable(tmp_path):
    # HOME/USERPROFILE 重定向到 jail → Path.home() 落空目录,~/.claude 不可达
    rc, out, err, rep = _run(
        "import pathlib;h=pathlib.Path.home();"
        "print(h);print((h/'.claude'/'.credentials.json').exists())",
        jail_root=tmp_path)
    assert rc == 0
    lines = out.strip().splitlines()
    assert Path(lines[0]) == tmp_path            # home 就是 jail
    assert lines[1] == "False"                   # 凭证不可达
    assert "creds-unreachable(HOME→jail)" in rep.enforcing


def test_cwd_is_jail(tmp_path):
    rc, out, err, rep = _run("import os;print(os.getcwd())", jail_root=tmp_path)
    assert Path(out.strip()) == tmp_path


# ── 资源上限 / 超时 ─────────────────────────────────────────────────

def test_wall_timeout_kills(tmp_path):
    rc, out, err, rep = _run("import time;time.sleep(10)",
                             mode="advisory", jail_root=tmp_path, timeout=1)
    assert rep.timed_out is True
    assert rc == 124
    assert "timeout" in err


def test_timeout_enforce_failclosed(tmp_path):
    rc, out, err, rep = _run("import time;time.sleep(10)",
                             mode="enforce", jail_root=tmp_path, timeout=1)
    assert rep.timed_out and rc in (124, 126)
    assert "FAIL-CLOSED" in err


# ── 完整性侦测(detective,即使无 OS 隔离也真生效)──────────────────

def test_integrity_violation_detected_advisory(tmp_path):
    secret = tmp_path / "protected.txt"
    secret.write_text("original", encoding="utf-8")
    jail = tmp_path / "jail"; jail.mkdir()
    rc, out, err, rep = _run(
        "import sys;open(sys.argv[1],'a',encoding='utf-8').write('TAMPER')",
        mode="advisory", jail_root=jail, protect=[secret], argv=[secret])
    assert any("protected-path-changed" in v for v in rep.violations)
    assert rc == 0                               # advisory:只记录不改判


def test_integrity_violation_failclosed_enforce(tmp_path):
    secret = tmp_path / "policy.cedar"
    secret.write_text("forbid(...);", encoding="utf-8")
    jail = tmp_path / "jail"; jail.mkdir()
    rc, out, err, rep = _run(
        "import sys;open(sys.argv[1],'w',encoding='utf-8').write('pwned')",
        mode="enforce", jail_root=jail, protect=[secret], argv=[secret])
    assert rep.violations
    assert rc == 126
    assert "FAIL-CLOSED" in err and "integrity-violation" in err


def test_clean_run_no_violation(tmp_path):
    secret = tmp_path / "p.txt"; secret.write_text("x", encoding="utf-8")
    jail = tmp_path / "jail"; jail.mkdir()
    rc, out, err, rep = _run("print('ok')", mode="enforce",
                             jail_root=jail, protect=[secret])
    assert rc == 0 and not rep.violations
    assert rep.tier == "A"
    assert "integrity-monitor(protected paths sha256)" in rep.enforcing


# ── ToolManager 接线(opt-in,默认 off 行为不变)──────────────────────

def test_toolmanager_off_is_raw(monkeypatch):
    monkeypatch.delenv("DEEPINSIGHT_SANDBOX", raising=False)
    from agent.tool_manager import ROOT as A_ROOT, ToolManager
    script = A_ROOT / "tools" / ".tmp" / "_sboff.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("print('RAW_OK')", encoding="utf-8")
    try:
        tm = ToolManager()
        monkeypatch.setattr(tm, "find_tool",
                            lambda n: {"name": n, "path": "tools/.tmp/_sboff.py"})
        rc, out, err = tm.execute("_sboff")
        assert rc == 0 and "RAW_OK" in out
    finally:
        script.unlink(missing_ok=True)


def test_toolmanager_advisory_runs_sandboxed(monkeypatch):
    monkeypatch.setenv("DEEPINSIGHT_SANDBOX", "advisory")
    from agent.tool_manager import ROOT as A_ROOT, ToolManager
    script = A_ROOT / "tools" / ".tmp" / "_sbadv.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    # 沙箱内 ~/.claude 应不可达,证明确实走了 run_sandboxed
    script.write_text(
        "import os,pathlib;print('SBOK');"
        "print(os.environ.get('ANTHROPIC_API_KEY','MISSING'))",
        encoding="utf-8")
    try:
        tm = ToolManager()
        monkeypatch.setattr(tm, "find_tool",
                            lambda n: {"name": n, "path": "tools/.tmp/_sbadv.py"})
        rc, out, err = tm.execute("_sbadv")
        assert rc == 0 and "SBOK" in out and "MISSING" in out
    finally:
        script.unlink(missing_ok=True)


def test_invalid_sandbox_mode_treated_off(monkeypatch):
    monkeypatch.setenv("DEEPINSIGHT_SANDBOX", "garbage")
    from agent.tool_manager import ROOT as A_ROOT, ToolManager
    script = A_ROOT / "tools" / ".tmp" / "_sbgrb.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("print('RAW2')", encoding="utf-8")
    try:
        tm = ToolManager()
        monkeypatch.setattr(tm, "find_tool",
                            lambda n: {"name": n, "path": "tools/.tmp/_sbgrb.py"})
        rc, out, err = tm.execute("_sbgrb")
        assert rc == 0 and "RAW2" in out
    finally:
        script.unlink(missing_ok=True)


def test_detect_tier_is_A():
    assert detect_tier() == "A"
