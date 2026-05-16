"""Tier C broker — Cedar 真正中介每个 fs/net 操作(spec 002)。

Tier A/B 让工具子进程**没有**直接 fs/net(OS 隔离)。Tier C 给它唯一一条
出路:经 IPC 向受信 broker 请求;**broker 对每个请求过 CedarPDP**,
ALLOW 才代为执行。于是工具能实际做的每个文件/网络操作都被 Cedar 决定 —
spec 001 红线在子进程级**彻底闭环**(不再 advisory / 事后侦测)。

诚实边界:Tier C 的"彻底"成立**当且仅当与 Tier B 组合**(Tier B 阻断
裸 syscall,使 broker 通道是唯一出路)。单独 Tier C 对**协作**工具完整
中介 + 全审计;对**恶意**绕开 client 直接 open()/socket() 的代码,需 B
兜底。详见 spec 002 §4.2 / §9。
"""

from __future__ import annotations

import json
import secrets
import socket
import threading
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .pdp import CedarPDP, Decision

ROOT = Path(__file__).resolve().parents[2]
_MAX_READ = 1_000_000  # 单次读上限,防内存炸


def _repo_rel(p: Path) -> str:
    """绝对/相对 → 仓库相对 posix(供 Cedar like 匹配);repo 外退回 posix 绝对。"""
    try:
        return Path(p).resolve().relative_to(ROOT.resolve()).as_posix()
    except Exception:
        return Path(p).as_posix()


def _default_fetcher(url: str) -> tuple[int, bytes]:  # pragma: no cover - 真网络
    req = urllib.request.Request(url, headers={"User-Agent": "deepinsight-broker"})
    with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310
        return r.status, r.read(_MAX_READ)


class Broker:
    """每个 op → CedarPDP.decide → ALLOW 才代办。default-deny。"""

    def __init__(
        self,
        pdp: CedarPDP | None = None,
        root: Path | None = None,
        net_allow: set[str] | None = None,
        fetcher: Callable[[str], tuple[int, bytes]] | None = None,
        audit_dir: Path | None = None,
    ) -> None:
        from .pdp import AUDIT_DIR
        self.pdp = pdp or CedarPDP(mode="enforce",
                                   audit_dir=audit_dir or AUDIT_DIR)
        self.root = Path(root) if root else ROOT
        self.net_allow = {d.lower() for d in (net_allow or set())}
        self.fetcher = fetcher or _default_fetcher

    # -- 决策 ---------------------------------------------------------------

    def _ok(self, action: str, rtype: str, rattrs: dict, ctx: dict) -> tuple[bool, Any]:
        res = self.pdp.decide("Agent", "deepinsight", action, rtype, rattrs, ctx)
        return res.decision is Decision.ALLOW, res

    @staticmethod
    def _norm(p: str) -> str:
        """请求路径 → posix 归一(保留 .. / 绝对,以便 forbid 命中)。"""
        import posixpath
        return posixpath.normpath(str(p).replace("\\", "/"))

    def _resolve(self, p: str) -> Path | None:
        """实际目标必须落在 broker root 内,否则 None(预防越界)。"""
        base = self.root.resolve()
        tgt = (self.root / p).resolve()
        try:
            tgt.relative_to(base)
        except Exception:
            return None
        return tgt

    # -- op 处理 ------------------------------------------------------------

    def handle(self, req: dict) -> dict:
        op = req.get("op")
        try:
            if op == "read_file":
                return self._read(req)
            if op in ("write_file", "write_out"):
                return self._write(req)
            if op == "net_get":
                return self._net(req)
        except Exception as e:                       # 永不把宿主异常细节漏给工具
            return {"ok": False, "error": f"broker-error: {type(e).__name__}"}
        return {"ok": False, "error": f"unknown-op: {op!r}"}   # default-deny

    def _read(self, req: dict) -> dict:
        rel = self._norm(req.get("path", ""))
        ok, res = self._ok("read_file", "Path", {"path": rel}, {})
        if not ok:
            return {"ok": False, "error": f"DENY read {rel}: {res.matched}"}
        target = self._resolve(req.get("path", ""))
        if target is None:
            return {"ok": False, "error": f"DENY read {rel}: path-escape"}
        try:
            data = target.read_bytes()[:_MAX_READ]
        except Exception:
            return {"ok": False, "error": f"read-failed: {rel}"}
        return {"ok": True, "data": data.decode("utf-8", "replace")}

    def _write(self, req: dict) -> dict:
        rel = self._norm(req.get("path", ""))
        ok, res = self._ok("write_file", "Path", {"path": rel}, {})
        if not ok:
            return {"ok": False, "error": f"DENY write {rel}: {res.matched}"}
        target = self._resolve(req.get("path", ""))
        if target is None:
            return {"ok": False, "error": f"DENY write {rel}: path-escape"}
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(str(req.get("data", "")), encoding="utf-8")
        except Exception:
            return {"ok": False, "error": f"write-failed: {rel}"}
        return {"ok": True, "bytes": len(str(req.get("data", "")))}

    def _net(self, req: dict) -> dict:
        url = str(req.get("url", ""))
        host = ""
        try:
            from urllib.parse import urlparse
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            host = ""
        allowed = host in self.net_allow and host != ""
        ok, res = self._ok("net_egress", "Net", {"domain": host},
                           {"net_allowed": allowed, "domain": host})
        if not ok:
            return {"ok": False,
                    "error": f"DENY net {host or url}: {res.matched}"}
        try:
            status, body = self.fetcher(url)
        except Exception:
            return {"ok": False, "error": f"fetch-failed: {host}"}
        return {"ok": True, "status": status,
                "data": body[:_MAX_READ].decode("utf-8", "replace")}

    # -- 传输:127.0.0.1 token 鉴权 socket(跨平台,Tier C 独立态)--------

    def serve_socket(self, host: str = "127.0.0.1") -> tuple[str, int, str, threading.Thread]:
        """启动后台 socket 服务。返回 (host, port, token, thread)。
        与 Tier B `--network none` 组合需改 UDS/管道传输(spec 002 §9)。"""
        token = secrets.token_hex(16)
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind((host, 0))
        srv.listen(8)
        srv.settimeout(0.5)
        port = srv.getsockname()[1]
        self._stop = threading.Event()

        def _loop():
            while not self._stop.is_set():
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with conn:
                    f = conn.makefile("rwb")
                    line = f.readline()
                    try:
                        req = json.loads(line or b"{}")
                    except Exception:
                        req = {}
                    if req.get("token") != token:
                        resp = {"ok": False, "error": "bad-token"}
                    else:
                        resp = self.handle(req)
                    f.write((json.dumps(resp) + "\n").encode("utf-8"))
                    f.flush()
            srv.close()

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        self._srv = srv
        return host, port, token, t

    def stop(self) -> None:
        ev = getattr(self, "_stop", None)
        if ev:
            ev.set()
