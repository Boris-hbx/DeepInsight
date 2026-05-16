"""CedarPDP — Policy Decision Point + tamper-evident audit (spec 001, Phase 0).

设计要点(决策已锁定 2026-05-15,见 agent/policies/DECISIONS-REQUIRED.md):
- ① 信任锚 = Git:启动 attest 工作区 agent.cedar vs HEAD blob;运行中本文件
  sha 偏离启动基线 / 缺失 → 永久 latch deny-all-dangerous(「删=自锁」)。
- ② 审计链头 = stderr:每次决策 `CEDAR-AUDIT seq= hash=` 打 stderr。
- log-or-deny:decide() 返回前必写审计;所有 sink 失败 → 强制 DENY。
- 防注入:不可信值(path / source_code)作为【结构化实体属性】传入,
  绝不字符串拼进策略/EUID 文本;EUID id 仅用受校验的安全 token。
- 三态:命中带 @gate("approval") 的 permit → REQUIRE_APPROVAL。

cedarpy 缺失 / 策略缺失 / 解析失败 → deny-all-dangerous(fail-closed)。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]                 # repo root
POLICY_PATH = ROOT / "agent" / "policies" / "agent.cedar"
AUDIT_DIR = ROOT / "agent" / ".audit"
POLICY_GIT_PATH = "agent/policies/agent.cedar"             # git uses '/'

DANGEROUS_ACTIONS = {
    "create_tool", "register_tool", "execute_tool",
    "write_file", "delete_file", "move_file", "chmod",
    "read_file", "net_egress",
}

_TYPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_PRINCIPAL_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
_ACTION_RE = re.compile(r"^[a-z_]{1,40}$")
_EUID_FORBIDDEN = re.compile(r'["\\\x00-\x1f]')

# Cedar 评估时实体属性/上下文的默认值 —— 提供并集,避免 policy 引用缺失属性报错
_RESOURCE_DEFAULTS: dict[str, Any] = {"path": "", "source_code": "", "registered": False}
_CONTEXT_DEFAULTS: dict[str, Any] = {
    "trust": "user", "tools_created_this_run": 0, "steps_done": 0,
    "skip_blue": False, "net_allowed": False, "domain": "",
}


class PDPError(Exception):
    """Configuration / refusal error (e.g. enforce while sentinel present)."""


class PDPInjection(PDPError):
    """Untrusted value tried to break out of an EUID literal."""


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass
class PDPResult:
    decision: Decision
    matched: list[str]
    reason: str
    mode: str
    anchor_state: str
    seq: int = -1


# ── Audit: append-only JSONL + hash chain + stderr 链头 ──────────────────

class AuditLog:
    """log-or-deny 的写入端。≥1 sink 成功 = 记录成功;全失败 → write() 返回 False。"""

    def __init__(self, audit_dir: Path = AUDIT_DIR) -> None:
        self.dir = audit_dir
        self._seq, self._prev = self._load_tail()

    def _file(self) -> Path:
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.dir / f"decisions-{day}.jsonl"

    def _load_tail(self) -> tuple[int, str]:
        f = self._file()
        try:
            if f.exists():
                last = ""
                for line in f.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        last = line
                if last:
                    rec = json.loads(last)
                    return int(rec.get("seq", 0)), str(rec.get("hash", "0" * 64))
        except Exception:
            # 读尾失败不致命;从 0 起,链断点本身即证据
            pass
        return 0, "0" * 64

    @staticmethod
    def _canon(d: dict) -> str:
        return json.dumps(d, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def write(self, record: dict) -> bool:
        """填 seq/prev_hash/hash,写文件 + stderr。返回是否 ≥1 sink 成功。"""
        seq = self._seq + 1
        record = dict(record)
        record["seq"] = seq
        record["prev_hash"] = self._prev
        record["hash"] = hashlib.sha256(self._canon(record).encode("utf-8")).hexdigest()
        line = self._canon(record)

        file_ok = False
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            f = self._file()
            with open(f, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                if record.get("severity") == "high":      # DENY / APPROVAL 必落盘
                    os.fsync(fh.fileno())
            file_ok = True
        except Exception:
            file_ok = False

        # ② 链头外锚:stderr(harness/终端捕获,子进程改不了已 flush 的)
        stderr_ok = False
        try:
            sys.stderr.write(
                f"CEDAR-AUDIT seq={seq} hash={record['hash'][:12]} "
                f"decision={record.get('decision')} policy={record.get('matched')} "
                f"mode={record.get('mode')}\n"
            )
            sys.stderr.flush()
            stderr_ok = True
        except Exception:
            stderr_ok = False

        if file_ok or stderr_ok:
            self._seq, self._prev = seq, record["hash"]
            return True
        return False


# ── CedarPDP ────────────────────────────────────────────────────────────

class CedarPDP:
    def __init__(
        self,
        mode: str = "shadow",
        policy_path: Path = POLICY_PATH,
        audit_dir: Path = AUDIT_DIR,
    ) -> None:
        if mode not in ("shadow", "enforce"):
            raise PDPError(f"unknown mode: {mode}")
        self.mode = mode
        self.policy_path = policy_path
        self._deny_all = False
        self._deny_reason = ""
        self._approval_ids: set[str] = set()
        self.audit = AuditLog(audit_dir)

        # cedarpy(import 失败 = fail-closed)
        try:
            from cedarpy import Decision as _CD, is_authorized as _ia
            self._is_authorized = _ia
            self._CD = _CD
        except Exception as e:                       # pragma: no cover
            self._is_authorized = None
            self._CD = None
            self._latch(f"cedarpy-unavailable: {e}")

        # 策略文本 + 启动基线 sha
        try:
            text = policy_path.read_text(encoding="utf-8")
            self._baseline_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            self._policy_text = text
        except Exception as e:
            self._baseline_sha = ""
            self._policy_text = ""
            self._latch(f"policy-unreadable: {e}")
            text = ""

        # sentinel 守卫:决策未决 + enforce → 拒绝启动(结构性防遗忘)
        if "UNRESOLVED-DECISION" in text and mode == "enforce":
            raise PDPError(
                "agent.cedar 含 UNRESOLVED-DECISION sentinel,拒绝以 enforce 启动"
                "(见 agent/policies/DECISIONS-REQUIRED.md)"
            )

        self._approval_ids = self._parse_approval_ids(text)
        self.anchor_state = self._attest_git(text)
        if self.mode == "enforce" and self.anchor_state == "git-unavailable":
            self._latch("git-anchor-unavailable")

        # 启动事件入审计(用于运维可见 anchor 状态)
        self.audit.write({
            "ts_wall": _now(), "ts_mono": time.monotonic(), "event": "pdp_start",
            "mode": self.mode, "anchor_state": self.anchor_state,
            "deny_all": self._deny_all, "deny_reason": self._deny_reason,
            "policy_sha256": self._baseline_sha, "decision": "-",
            "matched": [], "severity": "low",
        })

    # -- 内部 ----------------------------------------------------------------

    def _latch(self, reason: str) -> None:
        """进入并锁死 deny-all-dangerous。一旦 latch 不再解除(本进程内)。"""
        self._deny_all = True
        if not self._deny_reason:
            self._deny_reason = reason

    @staticmethod
    def _parse_approval_ids(text: str) -> set[str]:
        """扫描:带 @gate("approval") 的策略,取其 @id 值。"""
        ids: set[str] = set()
        pend_id: str | None = None
        pend_gate = False
        for raw in text.splitlines():
            s = raw.strip()
            if s.startswith("//") or not s:
                continue
            m = re.match(r'@id\("([^"]+)"\)', s)
            if m:
                pend_id = m.group(1)
                continue
            if re.match(r'@gate\("approval"\)', s):
                pend_gate = True
                continue
            if s.startswith("permit") or s.startswith("forbid"):
                if pend_gate and pend_id:
                    ids.add(pend_id)
            if ";" in s:                              # 语句结束,重置待定注解
                pend_id, pend_gate = None, False
        return ids

    def _attest_git(self, working_text: str) -> str:
        """committed | uncommitted-diff | git-unavailable。"""
        try:
            out = subprocess.run(
                ["git", "show", f"HEAD:{POLICY_GIT_PATH}"],
                cwd=str(ROOT), capture_output=True, timeout=10,
            )
            if out.returncode != 0:
                return "git-unavailable"
            committed_sha = hashlib.sha256(out.stdout).hexdigest()
            work_sha = hashlib.sha256(working_text.encode("utf-8")).hexdigest()
            return "committed" if committed_sha == work_sha else "uncommitted-diff"
        except Exception:
            return "git-unavailable"

    def _recheck(self) -> None:
        """每次决策前:策略文件仍在且未变?变/缺 → 永久 latch(删=自锁)。"""
        try:
            cur = self.policy_path.read_text(encoding="utf-8")
        except Exception:
            self._latch("policy-file-missing-at-runtime")
            return
        if hashlib.sha256(cur.encode("utf-8")).hexdigest() != self._baseline_sha:
            self._latch("policy-file-mutated-at-runtime")

    @staticmethod
    def _euid(type_name: str, ident: str) -> str:
        if not _TYPE_RE.match(type_name):
            raise PDPInjection(f"bad entity type: {type_name!r}")
        if _EUID_FORBIDDEN.search(ident) or len(ident) > 200:
            raise PDPInjection(f"unsafe EUID id: {ident!r}")
        return f'{type_name}::"{ident}"'

    # -- 主入口 --------------------------------------------------------------

    def decide(
        self,
        principal_type: str,
        principal_id: str,
        action: str,
        resource_type: str,
        resource_attrs: dict | None = None,
        context: dict | None = None,
    ) -> PDPResult:
        t0 = time.monotonic()
        self._recheck()

        res_attrs = {**_RESOURCE_DEFAULTS, **(resource_attrs or {})}
        ctx = {**_CONTEXT_DEFAULTS, **(context or {})}

        decision = Decision.DENY
        matched: list[str] = []
        reason = ""

        try:
            if not _ACTION_RE.match(action):
                raise PDPInjection(f"bad action name: {action!r}")
            p_euid = self._euid(principal_type, principal_id)   # 校验 principal
            r_euid = self._euid(resource_type, "req")           # 不可信值走 attrs

            if self._deny_all:
                decision = Decision.DENY
                matched = ["deny-all-dangerous"]
                reason = f"fail-closed: {self._deny_reason}"
            else:
                entities = [
                    {"uid": {"type": principal_type, "id": principal_id},
                     "attrs": {}, "parents": []},
                    {"uid": {"type": resource_type, "id": "req"},
                     "attrs": res_attrs, "parents": []},
                ]
                request = {
                    "principal": p_euid,
                    "action": f'Action::"{action}"',
                    "resource": r_euid,
                    "context": ctx,
                }
                r = self._is_authorized(request, self._policy_text, entities)
                diag = r.diagnostics
                ann = dict(getattr(diag, "id_annotations_by_reason", {}) or {})
                reasons = list(getattr(diag, "reasons", []) or [])
                ids = [ann.get(p, p) for p in reasons]

                if r.decision == self._CD.Allow:
                    if any(i in self._approval_ids for i in ids):
                        decision = Decision.REQUIRE_APPROVAL
                        reason = "permit + @gate(approval)"
                    else:
                        decision = Decision.ALLOW
                        reason = "permit"
                    matched = ids
                else:  # Deny / NoDecision
                    decision = Decision.DENY
                    if reasons:
                        matched = ids
                        reason = f"forbid: {ids[0]}"
                    else:
                        matched = ["default-deny"]
                        reason = "default-deny (no permit matched)"
        except PDPInjection as e:
            decision, matched, reason = Decision.DENY, ["pdp-injection"], str(e)
        except Exception as e:                        # 任何评估异常 → fail-closed
            decision, matched, reason = Decision.DENY, ["pdp-error"], repr(e)

        severity = "high" if decision in (Decision.DENY, Decision.REQUIRE_APPROVAL) else "low"
        record = {
            "ts_wall": _now(),
            "ts_mono": round(time.monotonic(), 6),
            "latency_ms": round((time.monotonic() - t0) * 1000, 3),
            "mode": self.mode,
            "anchor_state": self.anchor_state,
            "principal": f"{principal_type}::{principal_id}",
            "action": action,
            "resource_type": resource_type,
            "resource": {k: res_attrs[k] for k in res_attrs if res_attrs[k] not in ("", False)},
            "context": ctx,
            "decision": decision.value,
            "severity": severity,
            "matched": matched,
            "reason": reason,
            "policy_sha256": self._baseline_sha,
        }

        ok = self.audit.write(record)
        if not ok:
            # log-or-deny:记不下就不放行
            decision = Decision.DENY
            matched = ["audit-sink-failed"]
            reason = "audit-sink-failed: 所有 sink 写失败,强制 DENY"
            try:                                       # 紧急兜底再喊一声
                sys.stderr.write("CEDAR-AUDIT EMERGENCY audit-sink-failed -> DENY\n")
                sys.stderr.flush()
            except Exception:
                pass

        return PDPResult(decision, matched, reason, self.mode,
                         self.anchor_state, self.audit._seq)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
