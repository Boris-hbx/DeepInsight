"""spec 002 Tier C — broker:Cedar 中介每个 fs/net,default-deny,全审计。

不触发真网络(fetcher 注入假实现)/ 不触发真 API。
跑:python -m pytest agent/tests/ -q
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytest.importorskip("cedarpy")

from agent.pipeline import broker as bmod
from agent.pipeline import sandbox as sbx
from agent.pipeline.broker import Broker, uds_supported
from agent.pipeline.sandbox import _compose_plan, bwrap_argv, container_argv

REPO = Path(__file__).resolve().parents[2]


def _fake_fetch(url):
    return 200, b"FAKE-PAYLOAD"


@pytest.fixture
def broker(tmp_path):
    return Broker(root=tmp_path, audit_dir=tmp_path / "audit",
                  net_allow={"example.com"}, fetcher=_fake_fetch)


# ── 读:Cedar 决定 ──────────────────────────────────────────────────────

def test_read_policy_denied(broker):
    r = broker.handle({"op": "read_file", "path": "agent/policies/agent.cedar"})
    assert r["ok"] is False
    assert "forbid.read_secrets" in r["error"]


def test_read_credentials_denied(broker):
    r = broker.handle({"op": "read_file", "path": "sub/.credentials.json"})
    assert r["ok"] is False and "DENY" in r["error"]


def test_read_repo_data_allowed(broker, tmp_path):
    f = tmp_path / "data" / "note.txt"
    f.parent.mkdir(parents=True)
    f.write_text("HELLO", encoding="utf-8")
    r = broker.handle({"op": "read_file", "path": "data/note.txt"})
    assert r["ok"] is True and r["data"] == "HELLO"


def test_read_path_escape_denied(broker):
    r = broker.handle({"op": "read_file", "path": "../../etc/passwd"})
    assert r["ok"] is False


# ── 写:复用 spec 001 写策略 ────────────────────────────────────────────

def test_write_report_allowed(broker, tmp_path):
    r = broker.handle({"op": "write_file", "path": "data/reports/o.md",
                       "data": "hi"})
    assert r["ok"] is True
    assert (tmp_path / "data" / "reports" / "o.md").read_text() == "hi"


def test_write_policy_denied(broker):
    r = broker.handle({"op": "write_file",
                       "path": "agent/policies/evil.cedar", "data": "x"})
    assert r["ok"] is False and "DENY" in r["error"]


# ── 出网:默认拒绝,仅域名白名单放行 ────────────────────────────────────

def test_net_default_deny(broker):
    r = broker.handle({"op": "net_get", "url": "http://evil.example.net/x"})
    assert r["ok"] is False
    assert "DENY net" in r["error"]


def test_net_allowlisted(broker):
    r = broker.handle({"op": "net_get", "url": "http://example.com/y"})
    assert r["ok"] is True and r["data"] == "FAKE-PAYLOAD"


def test_unknown_op_default_deny(broker):
    r = broker.handle({"op": "frobnicate"})
    assert r["ok"] is False and "unknown-op" in r["error"]


# ── 审计:每个 op 都留痕(log-or-deny 沿用 spec 001)────────────────────

def test_every_op_audited(broker, tmp_path):
    broker.handle({"op": "read_file", "path": "agent/policies/agent.cedar"})
    broker.handle({"op": "net_get", "url": "http://example.com/y"})
    files = list((tmp_path / "audit").glob("decisions-*.jsonl"))
    assert files
    recs = [json.loads(x) for x in files[0].read_text(encoding="utf-8").splitlines() if x.strip()]
    acts = [r.get("action") for r in recs]
    assert "read_file" in acts and "net_egress" in acts


# ── 端到端:真子进程 + sandbox_client + token socket ───────────────────

def test_end_to_end_socket(tmp_path):
    br = Broker(root=tmp_path, audit_dir=tmp_path / "a",
                net_allow=set(), fetcher=_fake_fetch)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "ok.txt").write_text("E2E-OK", encoding="utf-8")
    host, port, token, _ = br.serve_socket()
    try:
        code = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, r"{REPO}")
            from agent.pipeline import sandbox_client as c
            print("ALLOW=" + c.read_file("data/ok.txt"))
            try:
                c.read_file("agent/policies/agent.cedar")
                print("LEAK")
            except c.BrokerDenied:
                print("DENIED-OK")
        """)
        env = dict(os.environ)
        env["DS_BROKER_ADDR"] = f"{host}:{port}"
        env["DS_BROKER_TOKEN"] = token
        p = subprocess.run([sys.executable, "-c", code], capture_output=True,
                           text=True, timeout=30, env=env)
        assert "ALLOW=E2E-OK" in p.stdout, p.stderr
        assert "DENIED-OK" in p.stdout
        assert "LEAK" not in p.stdout
    finally:
        br.stop()


# ── Tier C ↔ B 组合:UDS 传输 + 组合决策 ────────────────────────────────

def test_compose_plan_composed(monkeypatch):
    monkeypatch.setattr(sbx, "detect_backend", lambda: ("B", "container:docker"))
    monkeypatch.setattr(bmod, "uds_supported", lambda: True)
    composed, backend, reason = _compose_plan()
    assert composed is True and backend == "container:docker"


def test_compose_plan_no_strong_backend(monkeypatch):
    monkeypatch.setattr(sbx, "detect_backend", lambda: ("A", "tierA-launcher"))
    composed, backend, reason = _compose_plan()
    assert composed is False and "无强后端" in reason


def test_compose_plan_b_but_no_uds(monkeypatch):
    monkeypatch.setattr(sbx, "detect_backend", lambda: ("B", "bubblewrap"))
    monkeypatch.setattr(bmod, "uds_supported", lambda: False)
    composed, backend, reason = _compose_plan()
    assert composed is False and "UDS 不支持" in reason


def test_container_argv_broker_uds_mounts_and_env(tmp_path):
    a = container_argv(["py", "/x/t.py"], tmp_path, "/x/t.py", "docker",
                       "python:3-slim", broker_uds="/tmp/b.sock",
                       extra_env={"DS_BROKER_UDS": "/tmp/b.sock",
                                  "DS_BROKER_TOKEN": "tk"})
    assert "--network" in a and "none" in a               # 网络仍隔离
    assert "/tmp/b.sock:/sbx/broker.sock" in a            # UDS bind-mount
    assert "DS_BROKER_UDS=/sbx/broker.sock" in a          # 容器内路径
    assert "DS_BROKER_TOKEN=tk" in a


def test_bwrap_argv_broker_uds_bound(tmp_path):
    a = bwrap_argv(["py", "/x/t.py"], tmp_path, "/x/t.py",
                   broker_uds="/tmp/b.sock")
    i = a.index("--bind")
    assert "/tmp/b.sock" in a and "--unshare-all" in a


def test_client_connect_selection(monkeypatch):
    import agent.pipeline.sandbox_client as cli
    monkeypatch.delenv("DS_BROKER_UDS", raising=False)
    monkeypatch.delenv("DS_BROKER_ADDR", raising=False)
    with pytest.raises(cli.BrokerDenied):                  # 两者皆无 → 拒
        cli._connect()
    monkeypatch.setenv("DS_BROKER_ADDR", "127.0.0.1:1")    # TCP 分支(连不上)
    with pytest.raises(OSError):
        cli._connect()


@pytest.mark.skipif(not uds_supported(),
                    reason="AF_UNIX 不支持(Windows)—— UDS 用例在 Linux/CI 跑")
def test_uds_end_to_end(tmp_path, monkeypatch):
    import agent.pipeline.sandbox_client as cli
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "u.txt").write_text("UDS-OK", encoding="utf-8")
    br = Broker(root=tmp_path, audit_dir=tmp_path / "a", fetcher=_fake_fetch)
    sock = tmp_path / "b.sock"
    _, token, _ = br.serve_uds(sock)
    try:
        monkeypatch.setenv("DS_BROKER_UDS", str(sock))
        monkeypatch.setenv("DS_BROKER_TOKEN", token)
        assert cli.read_file("data/u.txt") == "UDS-OK"
        with pytest.raises(cli.BrokerDenied):
            cli.read_file("agent/policies/agent.cedar")
    finally:
        br.stop()
