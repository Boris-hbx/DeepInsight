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

from agent.pipeline.broker import Broker

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
