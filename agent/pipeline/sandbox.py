"""Tool sandbox — Tier A 硬化启动器(spec 002)。

让 spec 001 的 Cedar 红线在子进程级真正起作用的第一档。Tier A 是
**跨平台、免管理员、cheap-but-real** 的子集:

  预防(preventive,真生效):
    - env 净化:剥离 ANTHROPIC_*/AWS_*/CLAUDE*/密钥类
    - 凭证不可达:HOME/USERPROFILE 重定向到 jail → ~/.claude 落空目录
    - cwd 关进一次性 jail;OUT_DIR 显式
    - wall-timeout 强杀;POSIX 下 rlimit(CPU/内存/句柄/进程)
    - Linux 有 `unshare` → 真网络命名空间隔离

  侦测(detective,真生效,即使无 OS 隔离):
    - 受保护路径(agent/policies、agent/.audit、~/.claude)运行前后
      sha256 快照比对;改动即 violation。enforce 模式下 violation/超时
      → 结果 fail-closed。这与 spec 001「删=自锁」同源。

  诚实边界(advisory,Tier A 挡不住,需 Tier B/C):
    - 绝对路径写到 jail 外:**事后侦测,非事前阻止**
    - 原始 socket 出网:env 代理中和只挡守规矩的库,挡不住裸 socket
    - 读取并外泄非凭证数据

强隔离见 spec 002 Tier B(容器/namespace)/ Tier C(broker 中介)。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]                 # repo root

# 需净化的 env 前缀/名(密钥承载者)
_SECRET_PREFIXES = ("ANTHROPIC", "AWS", "CLAUDE", "OPENAI", "AZURE", "GOOGLE")
_SECRET_NAMES = {"GH_TOKEN", "GITHUB_TOKEN", "HF_TOKEN", "OPENAI_API_KEY",
                 "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"}
# 子进程保留的最小 env 键(值会被重写/透传安全部分)
_KEEP = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR",
         "LANG", "LC_ALL", "TZ", "PATHEXT", "COMSPEC", "NUMBER_OF_PROCESSORS"}


@dataclass
class SandboxReport:
    tier: str = "A"
    enforcing: list[str] = field(default_factory=list)   # 真预防/侦测的控制
    advisory: list[str] = field(default_factory=list)    # 已知绕得过的
    violations: list[str] = field(default_factory=list)  # 侦测到的越界
    timed_out: bool = False

    def as_dict(self) -> dict:
        return {"sandbox_tier": self.tier, "sandbox_enforcing": self.enforcing,
                "sandbox_advisory": self.advisory,
                "sandbox_violations": self.violations,
                "sandbox_timed_out": self.timed_out}


def detect_tier() -> str:
    """当前能提供的最高档。Tier B/C 未实现 → 始终 'A'。"""
    return "A"


def _hash_target(p: Path) -> dict[str, str]:
    """文件 → {rel: sha256};目录 → 递归。缺失 → 空(也是一种状态)。"""
    out: dict[str, str] = {}
    try:
        if p.is_file():
            out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    try:
                        out[str(f)] = hashlib.sha256(f.read_bytes()).hexdigest()
                    except Exception:
                        out[str(f)] = "<unreadable>"
    except Exception:
        pass
    return out


def _default_protected() -> list[Path]:
    return [
        ROOT / "agent" / "policies",
        ROOT / "agent" / ".audit",
        Path(os.path.expanduser("~")) / ".claude" / ".credentials.json",
    ]


def _clean_env(jail: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    src = os.environ
    for k in _KEEP:
        if k in src:
            env[k] = src[k]
    # PATH 精简:只留系统目录(够跑 python/标准工具),去掉用户/项目注入
    if sys.platform == "win32":
        sysroot = src.get("SYSTEMROOT", r"C:\Windows")
        env["PATH"] = os.pathsep.join([sysroot, f"{sysroot}\\System32"])
    else:
        env["PATH"] = "/usr/bin:/bin"
    # 凭证不可达:home 指向 jail(空)→ ~/.claude/.credentials.json 落空
    js = str(jail)
    env["HOME"] = js
    env["USERPROFILE"] = js
    env["XDG_CONFIG_HOME"] = str(jail / ".config")
    env["APPDATA"] = str(jail / "AppData")
    env["TEMP"] = js
    env["TMP"] = js
    env["TMPDIR"] = js
    # 网络代理中和(advisory:只挡守规矩的 http 库)
    env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["ALL_PROXY"] = "http://127.0.0.1:9"
    env["http_proxy"] = env["https_proxy"] = env["all_proxy"] = "http://127.0.0.1:9"
    env["NO_PROXY"] = ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["OUT_DIR"] = str(jail / "out")
    # 显式抹掉密钥类(防御性,_clean_env 是白名单本不该带进来,双保险)
    for k in list(env):
        if k.upper() in _SECRET_NAMES or k.upper().startswith(_SECRET_PREFIXES):
            del env[k]
    return env


def _posix_rlimits():  # pragma: no cover - 平台相关
    try:
        import resource
    except Exception:
        return None

    def _apply():
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
        _512m = 512 * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (_512m, _512m))
        except Exception:
            pass
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        except Exception:
            pass
    return _apply


def run_sandboxed(
    cmd: list[str],
    *,
    mode: str = "advisory",
    jail_root: Path | None = None,
    timeout: int = 60,
    protect_paths: list[Path] | None = None,
):
    """在 Tier A 沙箱内跑 cmd。返回 (rc, stdout, stderr, SandboxReport)。

    mode='advisory':施加所有控制,侦测 violation 只记录不改判。
    mode='enforce' :额外 —— 侦测到 violation 或超时 → 结果 fail-closed
                     (rc=126/124,stderr 标注),决心绕过者至少留痕且被判失败。
    """
    report = SandboxReport(tier=detect_tier())
    protected = protect_paths if protect_paths is not None else _default_protected()
    pre = {str(p): _hash_target(p) for p in protected}

    jail = Path(jail_root) if jail_root else Path(tempfile.mkdtemp(prefix="ds-jail-"))
    (jail / "out").mkdir(parents=True, exist_ok=True)
    cleanup = jail_root is None
    env = _clean_env(jail)

    report.enforcing += ["env-sanitized", "creds-unreachable(HOME→jail)",
                         "cwd-jail", "wall-timeout"]
    run_cmd = list(cmd)
    preexec = None
    if sys.platform != "win32":
        preexec = _posix_rlimits()
        if preexec:
            report.enforcing.append("rlimit(cpu/mem/nofile/nproc)")
        if shutil.which("unshare"):
            run_cmd = ["unshare", "-n", "--"] + run_cmd
            report.enforcing.append("net-namespace(unshare -n)")
        else:
            report.advisory.append("net:proxy-neuter(裸 socket 挡不住)")
    else:
        report.advisory += ["net:proxy-neuter(裸 socket 挡不住)",
                            "no-rlimit(Windows;靠 wall-timeout)"]
    report.advisory.append("fs-write:cwd-jail + 事后侦测(绝对路径写非事前阻止)")
    report.enforcing.append("integrity-monitor(protected paths sha256)")

    rc, out, err = 0, "", ""
    try:
        kw = {}
        if preexec:
            kw["preexec_fn"] = preexec
        proc = subprocess.run(
            run_cmd, cwd=str(jail), env=env, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=timeout, **kw,
        )
        rc, out, err = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        report.timed_out = True
        rc, out = 124, (e.stdout or "")
        err = f"[sandbox] timeout after {timeout}s, killed"
    except FileNotFoundError as e:
        rc, err = 127, f"[sandbox] cmd not found: {e}"
    finally:
        post = {str(p): _hash_target(p) for p in protected}
        for key in pre:
            if pre[key] != post[key]:
                report.violations.append(f"protected-path-changed: {key}")
        if cleanup:
            shutil.rmtree(jail, ignore_errors=True)

    if mode == "enforce" and (report.violations or report.timed_out):
        why = "integrity-violation" if report.violations else "timeout"
        if rc == 0:
            rc = 126
        err = (err + f"\n[sandbox] FAIL-CLOSED ({why}): "
               f"{report.violations or 'timed_out'}").strip()

    return rc, out, err, report
