"""Tool sandbox — Tier A 硬化启动器 + Tier B OS 隔离(spec 002)。

让 spec 001 的 Cedar 红线在子进程级真正起作用。

Tier A(跨平台、免管理员,始终可用):
  预防:env 净化 / 凭证不可达(HOME→jail)/ cwd-jail / wall-timeout /
       POSIX rlimit / Linux `unshare -n`
  侦测:受保护路径(policies/audit/凭证)前后 sha256 比对 → violation;
       enforce 下 violation/超时 → fail-closed
  advisory(Tier A 挡不住):绝对路径写 jail 外、裸 socket 出网 = 事后侦测

Tier B(强隔离,需 OS 能力,能力自适应):
  - 容器(docker/podman):--network none --read-only --cap-drop ALL
    --security-opt no-new-privileges,只读挂载脚本,jail 作工作区
  - bubblewrap(Linux 无容器):--unshare-all+net --die-with-parent
    --new-session,tmpfs HOME,只 ro-bind 系统目录与脚本(repo/凭证不可见)
  能力不足 → **诚实回退 Tier A**(不伪装 B);report.tier 反映实际运行档。
  env 净化 / jail / 完整性侦测 / 超时 在所有档位仍作纵深防御。

Tier C(broker 中介)未实现,见 spec 002 §4.2。
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

_SECRET_PREFIXES = ("ANTHROPIC", "AWS", "CLAUDE", "OPENAI", "AZURE", "GOOGLE")
_SECRET_NAMES = {"GH_TOKEN", "GITHUB_TOKEN", "HF_TOKEN", "OPENAI_API_KEY",
                 "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"}
_KEEP = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR",
         "LANG", "LC_ALL", "TZ", "PATHEXT", "COMSPEC", "NUMBER_OF_PROCESSORS"}


@dataclass
class SandboxReport:
    tier: str = "A"
    backend: str = "tierA-launcher"
    enforcing: list[str] = field(default_factory=list)
    advisory: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    timed_out: bool = False

    def as_dict(self) -> dict:
        return {"sandbox_tier": self.tier, "sandbox_backend": self.backend,
                "sandbox_enforcing": self.enforcing,
                "sandbox_advisory": self.advisory,
                "sandbox_violations": self.violations,
                "sandbox_timed_out": self.timed_out}


def _which(x: str) -> str | None:
    return shutil.which(x)


def detect_backend() -> tuple[str, str]:
    """返回 (tier, backend_name) —— 当前环境实际能提供的最强档。"""
    if _which("docker"):
        return "B", "container:docker"
    if _which("podman"):
        return "B", "container:podman"
    if sys.platform.startswith("linux") and _which("bwrap"):
        return "B", "bubblewrap"
    return "A", "tierA-launcher"


def detect_tier() -> str:
    return detect_backend()[0]


def _hash_target(p: Path) -> dict[str, str]:
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
    if sys.platform == "win32":
        sysroot = src.get("SYSTEMROOT", r"C:\Windows")
        env["PATH"] = os.pathsep.join([sysroot, f"{sysroot}\\System32"])
    else:
        env["PATH"] = "/usr/bin:/bin"
    js = str(jail)
    env["HOME"] = js
    env["USERPROFILE"] = js
    env["XDG_CONFIG_HOME"] = str(jail / ".config")
    env["APPDATA"] = str(jail / "AppData")
    env["TEMP"] = env["TMP"] = env["TMPDIR"] = js
    env["HTTP_PROXY"] = env["HTTPS_PROXY"] = env["ALL_PROXY"] = "http://127.0.0.1:9"
    env["http_proxy"] = env["https_proxy"] = env["all_proxy"] = "http://127.0.0.1:9"
    env["NO_PROXY"] = ""
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["OUT_DIR"] = str(jail / "out")
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


def _script_of(cmd: list[str]) -> str | None:
    """cmd 形如 [python, script.py, ...] → 取脚本路径(用于 ro-bind/mount)。"""
    if len(cmd) >= 2 and cmd[1] not in ("-c", "-m", "-") and Path(cmd[1]).exists():
        return str(Path(cmd[1]).resolve())
    return None


def bwrap_argv(cmd: list[str], jail: Path, script: str | None) -> list[str]:
    """Linux bubblewrap:unshare 全部(含网络),只读系统 + 脚本,jail 可写。

    repo / 凭证 **不 bind** → 子进程不可见(强预防,非事后侦测)。
    """
    a = ["bwrap", "--die-with-parent", "--new-session", "--unshare-all",
         "--proc", "/proc", "--dev", "/dev",
         "--tmpfs", str(jail.parent if jail.parent != jail else jail),
         "--bind", str(jail), str(jail), "--chdir", str(jail)]
    for d in ("/usr", "/bin", "/lib", "/lib64", "/etc/alternatives"):
        if Path(d).exists():
            a += ["--ro-bind", d, d]
    if script:
        a += ["--ro-bind", script, script]
    a += ["--"]
    a += cmd
    return a


def container_argv(cmd: list[str], jail: Path, script: str | None,
                   runtime: str, image: str) -> list[str]:
    """docker/podman:无网络、只读 rootfs、丢能力、非 root、资源上限。

    只读挂载脚本;jail 作可写工作区。repo / 凭证不挂载 → 不可见。
    """
    a = [runtime, "run", "--rm", "--network", "none", "--read-only",
         "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
         "--pids-limit", "64", "--memory", "512m", "-u", "65534:65534",
         "--tmpfs", "/work:rw,size=64m", "-w", "/work",
         "-v", f"{jail}:/work"]
    inner = list(cmd)
    if script:
        a += ["-v", f"{script}:/sbx/tool:ro"]
        inner = [cmd[0], "/sbx/tool"] + cmd[2:]
    a += [image] + inner
    return a


def run_sandboxed(
    cmd: list[str],
    *,
    mode: str = "advisory",
    jail_root: Path | None = None,
    timeout: int = 60,
    protect_paths: list[Path] | None = None,
    tier: str = "auto",
):
    """在沙箱内跑 cmd。返回 (rc, stdout, stderr, SandboxReport)。

    tier: 'auto'(默认,选可用最强)| 'A'(强制硬化启动器)| 'B'(要强隔离;
          不可用则**诚实回退 A** + advisory,绝不伪装)。
    mode: 'advisory'=施加控制+记录;'enforce'=另:violation/超时 → fail-closed。
    """
    report = SandboxReport()
    protected = protect_paths if protect_paths is not None else _default_protected()
    pre = {str(p): _hash_target(p) for p in protected}

    jail = Path(jail_root) if jail_root else Path(tempfile.mkdtemp(prefix="ds-jail-"))
    (jail / "out").mkdir(parents=True, exist_ok=True)
    cleanup = jail_root is None
    env = _clean_env(jail)

    want = (tier or "auto").strip().upper()
    avail_tier, avail_backend = detect_backend()
    script = _script_of(cmd)

    # 档位决策:诚实——不可用就回退 A,不伪装
    use_b = False
    if want in ("AUTO", "B") and avail_tier == "B":
        use_b = True
    elif want == "B" and avail_tier != "B":
        report.advisory.append(f"requested Tier B 但不可用({avail_backend});回退 Tier A")

    # 所有档位通用的纵深防御
    report.enforcing += ["env-sanitized", "creds-unreachable(HOME→jail)",
                         "cwd-jail", "wall-timeout",
                         "integrity-monitor(protected paths sha256)"]

    run_cmd = list(cmd)
    preexec = None

    if use_b:
        report.tier = "B"
        report.backend = avail_backend
        if avail_backend.startswith("container:"):
            rt = avail_backend.split(":", 1)[1]
            image = os.environ.get("DEEPINSIGHT_SANDBOX_IMAGE", "python:3-slim")
            run_cmd = container_argv(cmd, jail, script, rt, image)
            report.enforcing += ["container:network-none", "container:read-only-rootfs",
                                 "container:cap-drop-all", "container:no-new-privileges",
                                 "container:non-root", "container:pids/mem-limit",
                                 "repo+creds:not-mounted"]
        else:  # bubblewrap
            run_cmd = bwrap_argv(cmd, jail, script)
            report.enforcing += ["bwrap:unshare-all+net", "bwrap:die-with-parent",
                                 "bwrap:new-session", "repo+creds:not-bound"]
    else:
        report.tier = "A"
        report.backend = "tierA-launcher"
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
        rc, err = 127, f"[sandbox] cmd/runtime not found: {e}"
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
