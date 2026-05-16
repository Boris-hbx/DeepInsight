---
id: 002
title: 工具沙箱 — 让 Cedar 红线在子进程级真正成立
author: 阿宝
reviewers: []
status: draft          # draft | review | approved | building | done | rejected
created: 2026-05-15
updated: 2026-05-16  # Tier A/B/C 全落地(C=broker 中介,默认 off）
related_adrs: []
related_tasks: []
---

# 002 · 工具沙箱 — 让 Cedar 红线在子进程级真正成立

> 前置:`docs/specs/001-cedar-policy-gate.md`(spec 001 多处将本 spec 列为 Phase 2 enforce 的硬前置)
>
> **实现状态(2026-05-16)**:**Tier A 首版已落地**(`agent/pipeline/sandbox.py`,
> opt-in `DEEPINSIGHT_SANDBOX=off|advisory|enforce`,默认 `off` 行为不变)。
> Tier A 真生效:env 净化、凭证不可达(HOME→jail)、cwd-jail、wall-timeout、
> POSIX rlimit、`unshare -n`(Linux)、完整性侦测 + enforce fail-closed。
> **Tier B 后端已落地**(能力自适应,`DEEPINSIGHT_SANDBOX_TIER=auto|A|B`):
> `container:docker/podman`(--network none / --read-only / --cap-drop ALL /
> no-new-privileges / 非 root / pids·mem 限 / repo·凭证不挂载)与 `bubblewrap`
> (--unshare-all+net / die-with-parent / repo·凭证不 bind)。**诚实回退**:
> 无强后端 → 退 Tier A + advisory,`report.tier` 反映实际运行档,绝不伪装。
> **Tier C broker 已落地**(`broker.py` + `sandbox_client.py`):工具经
> token 鉴权 loopback socket 请求,**broker 对每个 read_file/write_file/
> net_egress 过 CedarPDP**(default-deny + 全审计,沿用 spec 001 log-or-deny)。
> agent.cedar 新增 `read_file`/`net_egress` 策略(@id 化)。`run_brokered`
> 以 Tier A 为底座 + broker 通道;`DEEPINSIGHT_SANDBOX_TIER=C` 选用。
> 测试 67 过 / 1 skip,**含真子进程端到端**(child→client→socket→Cedar:
> 允许读得到数据、读 agent/policies 抛 BrokerDenied、无 LEAK)。
>
> 仍**未做**:① Tier C **与 Tier B 组合**(当前 socket 传输与容器
> `--network none` 冲突,需 UDS/管道传输 → 组合后裸 syscall 才被 OS 阻断,
> 闭环才对**恶意**绕开者成立;单独 Tier C 对**协作**工具已完整中介)
> ② Windows 真 fs-write 事前阻止(OS 账户·ACL)与真网络 deny
> ③ spec §9 两环境决策(Windows 隔离选型 / 出网默认)待你定。

## 1. 问题 / 动机

spec 001 把 Cedar 闸门做到了:确定性红线、log-or-deny 审计、删=自锁。但它反复诚实标注一个**根本缺口**:

> Cedar 是**应用层决策点**,只看得见经过 PEP 的决策。`loop.py` 把 LLM 生成的工具当**子进程**跑(`subprocess.run([python, tool.py])`)。那个进程内部的 `os.remove(...)` / `socket` / `open(...,'w')` **不经过 Cedar**。

后果:对一个"决心绕过"的子进程,spec 001 的红线(删策略=自锁、写白名单、凭证保护)是 advisory,不是保证。`LoopGuard` 在 enforce 启动时主动 `WARN + 审计 sandbox=absent` 就是为标注此洞。

**本 spec 补这个洞**:用 OS/进程级隔离,让 spec 001 的红线对子进程**真实成立**,而不是停在字符串黑名单层。

## 2. 目标(Goals）

- [ ] 生成工具子进程**无法**写/删 repo 内除指定 drop 目录外任何文件(OS 级,非 Cedar advisory)
- [ ] 子进程**无法**读 `~/.claude` 凭证 / `ANTHROPIC_*` 等密钥(env 净化 + fs 拒)
- [ ] 子进程网络**默认 deny**,仅经宿主控制的 allowlist 代理出网
- [ ] `agent/policies/*`、`agent/.audit/*` 对子进程**只读或不可达** —— 使 spec 001「删=自锁」「审计不可篡改」「凭证保护」在子进程级真实成立
- [ ] 资源上限:wall timeout、内存、CPU、子进程数
- [ ] 沙箱就绪时 `LoopGuard` 去掉 `sandbox=absent`,审计记 `sandbox_tier=A|B|C`
- [ ] 跨平台:Windows(开发主力)+ Linux(部署/CI)各有**可落地**实现并通过对抗用例

## 3. 非目标(Non-Goals）

- 不做完整 VM / 不把 Docker 列为硬依赖(个人离线项目;容器作为可选强档 Tier B)
- 不沙箱化 pipeline step(那是受信代码,非 LLM 生成,已由 spec 001 Phase 1 Cedar 管)。沙箱只针对**生成工具**与 `execute_tool`
- 不以 RestrictedPython / import 钩子 / `sys.addaudithook` 为主控(同进程、不可信代码可绕,见 §4.3;仅作 advisory 补充)
- 不解决 cedarpy/pip 供应链(另议)

## 4. 方案 / 设计

### 4.1 用户视角

正常工具(fetch_rss / search-web 等:只需出网到已知域名 + 写临时目录)照跑。越界(删策略、读凭证、写 repo、任意出网)被 **OS 拒**,工具拿到错误码,`loop` 走 spec 001 的 `DenialFeedback` 重规划。`LoopGuard` 不再打 `sandbox=absent`,审计记 `sandbox_tier`。

### 4.2 技术设计

新增 `agent/pipeline/sandbox.py`:`run_sandboxed(cmd, jail, net_allow) -> (rc,out,err)`,被 `tool_manager.execute` 和 `loop._create_tool` 产出的脚本执行路径统一调用。后端按平台/能力自适应,**分三档**(强度/工程量递增):

**Tier A — 硬化启动器(跨平台,默认,cheap real wins)**
- env 净化:白名单 env(精简 PATH + 必要项);剥离 `ANTHROPIC_*` / `AWS_*` / `CLAUDE*`;`HOME`/`USERPROFILE` 指向 jail 使 `~/.claude` 不可达
- cwd = 一次性 temp jail;工具只能写 jail 与显式 `OUT_DIR`
- 文件系统隔离:**独立低权限 OS 账户 + ACL**。Windows:专用本地用户 / `CreateRestrictedToken` + `icacls`(对 repo 拒写,对 `agent/policies` `agent/.audit` `*/.env` `.git` 拒读写);Linux:专用 uid + 目录 ACL/mode
- 网络默认 deny:Windows WFP/防火墙按 user/pid;Linux `unshare -n` 或 nftables per-uid。需出网的工具走宿主 allowlist 代理(`HTTPS_PROXY` 指向受控代理,按域名白名单放行)
- 资源上限:wall `timeout=`;Windows Job Object(内存/CPU/进程数),Linux `rlimit`/cgroup

**Tier B — OS 沙箱/容器(强档:Linux/CI 或愿装容器的环境)**
- Linux 无容器:`bubblewrap` + Landlock + seccomp + user/net namespace(只读 bind repo、tmpfs jail、`--unshare-net` + 代理)
- 容器:Podman/Docker,repo 只读挂载除 `/out`,`--network none` 或 egress 代理,非 root,`--cap-drop ALL`,seccomp 默认,只读 rootfs
- macOS:`sandbox-exec` profile(注:已弃用但可用)或容器

**Tier C — broker 中介(北极星,彻底闭环)**
工具进程**无**直接 fs/net;经 IPC 向受信父(broker)请求,broker 对每个请求**再过 CedarPDP**(`read_file`/`write_file`/`net_egress`,resource=路径/域名)。这才是「Cedar 真正中介每个等效 syscall」,把 spec 001 红线在子进程级**完整**成立(不再 advisory)。工程量最大,分阶段。

**选档与接口**:`SandboxBackend` 抽象接口,平台后端分文件;运行时探测能力 → 有容器用 B,否则 A(始终可用),高风险/`untrusted` 路径可强制 C。`LoopGuard` 读实际生效 tier 写审计 `sandbox_tier`;tier≥A 时把 `sandbox=absent` WARN 降级为 info(标注当前 tier 与其边界)。挂载策略保证 `agent/policies`、`agent/.audit`、凭证对子进程不可达 —— 这是让 spec 001 三条红线"真成立"的关键接缝。

### 4.3 备选方案

1. **RestrictedPython / import 钩子 / `sys.addaudithook`(PEP578)**。淘汰为主控:同进程,不可信代码自身加载,可禁用/绕过(与 spec 001「`like` 黑名单可绕」同类教训)。仅作 Tier A 之上 advisory。
2. **强制 Docker**。淘汰为硬依赖(个人/离线/Windows 不友好);作为 Tier B 可选。
3. **gVisor / Firecracker microVM**。最强但过重,留未来。

## 5. 测试策略 ⚠ 必填

### 5.1 Test checklist
- [ ] 单元测试覆盖核心函数(目标覆盖率:`run_sandboxed` env 净化 / jail / tier 选择 ≥ 85%)
- [ ] 集成测试覆盖主流程(fetch_rss / search-web 等现有工具在 Tier A 跑通,workflow 不回归)
- [ ] Eval:本特性**不调 LLM** → `N/A + 沙箱无生成内容`;"被沙箱拒后 loop 重规划"的 LLM 调用见对抗性测试
- [ ] 对抗性测试(≥ 5):① 工具 `os.remove("agent/policies/agent.cedar")` → OS 拒 ② 读 `~/.claude/.credentials.json` 外泄 → 不可达/拒 ③ 任意出网 `requests.get(evil)` → 网络 deny ④ 写 `data/reports/../../.git/config` → jail/ACL 拒 ⑤ fork 炸弹 / 超时 → 资源上限强杀
- [ ] 回归影响:`tool_manager.execute` 改走 `run_sandboxed` → 验证现有注册工具在 Tier A 仍能完成正常职能(出网白名单需含其合法域名);`loop` 旧行为在沙箱不可用时 fail-closed,不静默放行

### 5.2 Reliability checklist
- [ ] 故障模式:沙箱不可用(无权限建受限账户 / 无容器)→ **fail-closed**:`execute_tool`/`create_tool` 拒,`LoopGuard` 维持 `sandbox=absent` + enforce 拒危险;用户见「沙箱不可用,已拒绝执行」
- [ ] 超时 / 重试策略(含退避):工具 wall-timeout 强杀,**无自动重试**(交 loop 决策);代理出网超时按代理策略。`N/A 退避(单次强杀)`
- [ ] 成本 / 限流:沙箱无 token 成本;限并发子进程数 + 资源上限防耗尽
- [ ] 观测:审计加 `sandbox_tier`、`sandbox_violations`(OS 拒事件计数),打点入 `agent/.audit`(沿用 spec 001 哈希链)
- [ ] 错误文案:对工具/对外统一「operation blocked by sandbox」,不泄露宿主路径 / 账户名 / 代理细节

## 6. 验收标准

- [ ] §5.1 五条对抗用例全部在 **OS 级**被拒(非 Cedar advisory),且有 `sandbox_violations` 审计
- [ ] 现有 workflow 与注册工具在 Tier A 正常完成(白名单配齐)
- [ ] 沙箱就绪时 `LoopGuard` 不再打 `sandbox=absent`,审计 `sandbox_tier=A|B|C`
- [ ] 沙箱不可用 → `execute_tool`/`create_tool` fail-closed,日志明确
- [ ] Windows 与 Linux 各至少一个后端通过全部对抗用例

## 7. Agent 参与度(预估)

- 预估主要模式:`[pair]`(OS 权限 / 账户 / 防火墙设计需人确认环境前提),实现 `[agent]`
- 会用 subagent 的子任务:跨平台对抗用例批量跑;现有工具出网域名白名单梳理
- 是否新增 / 修改 skill:暂不

## 8. 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| Windows 受限账户/WFP 配置复杂,需管理员一次性设置 | 高 | 中 | 一键 setup 脚本 + 文档;无管理员时 Tier A 降级为「env 净化+jail cwd+无网」最小集,并 fail-closed 标注 |
| Tier A 非真隔离(同 OS,ACL 可能配错) | 中 | 高 | 明确分档与边界;高风险/untrusted 走 Tier B/C;对抗用例守门 |
| 正常工具误伤(需要的域名/路径被拦) | 高 | 中 | 出网域名 + 路径白名单可配;shadow 式预演收集缺口(沿用 spec 001 Phase 0 思路) |
| Tier C broker 工程量大、IPC 复杂 | 中 | 中 | 分阶段;A/B 先兜底,C 渐进 |
| 跨平台维护负担 | 中 | 中 | `SandboxBackend` 接口 + 平台后端分文件;CI 双平台 |

## 9. 开放问题

- [ ] Windows 隔离选型:独立本地用户+`icacls` vs 受限令牌(Restricted Token) vs AppContainer —— 哪个对个人机器最实际?需阿宝定环境前提(可否建本地用户/是否需管理员)
- [ ] 出网策略默认值:deny-all vs allowlist 代理 —— 多数工具(fetch/search)需网络,默认太严会大面积误伤
- [ ] Tier C broker 的 IPC 形态(stdio 协议 vs 本地 socket)与协议版本化
- [ ] 是否需 ADR 记录「沙箱分档 + Cedar 中介」架构(建议:是,与 spec 001「确定性+概率守卫并存」一并)
- [ ] 与 spec 001 §9「信任分级」联动:`context.trust=untrusted` 来源是否强制 Tier B/C
- [ ] `agent/` 已纳入 git(spec 001 已解决);本 spec building 前确认 cedarpy 同环境可用

---

## Changelog
- 2026-05-15 初稿(阿宝 / pair with Claude）—— 承接 spec 001 Phase 2 诚实标注的子进程 syscall 缺口
- 2026-05-16 Tier C broker(阿宝 / pair):`agent/pipeline/broker.py`(Broker:每 op→CedarPDP.decide→ALLOW 才代办,default-deny,token socket,路径越界预防,审计沿用 log-or-deny)+ `sandbox_client.py`(工具侧 read_file/write_out/http_get,无 broker 即拒,不退回 raw)。`agent.cedar` +3 策略(forbid.read_secrets / permit.read_repo_data / permit.net_allowlisted,均 @id)+ schema 加 read_file/net_egress/Net。`run_brokered`(Tier A 底座+broker;`DEEPINSIGHT_SANDBOX_TIER=C`);`run_sandboxed` tier=C 委派 + `extra_env`。`test_broker.py` 11 用例(读/写/网 allow·deny、unknown default-deny、每 op 审计、**真子进程端到端**)。全套 67 过 / 1 skip。诚实:与 Tier B 组合(UDS 传输)才对恶意绕开者闭环;单独 C 对协作工具完整中介+全审计。
- 2026-05-16 Tier B 后端(阿宝 / pair):`sandbox.py` 加 `detect_backend`、`bwrap_argv`、`container_argv`;`run_sandboxed(tier='auto'|'A'|'B')` 能力自适应 + 诚实回退(无强后端→Tier A+advisory,不伪装);`SandboxReport.backend`;`tool_manager` 读 `DEEPINSIGHT_SANDBOX_TIER`;`test_sandbox.py` +6 用例(argv/探测/回退)+1 skipif 实跑。全套 **56 过 / 1 skip**(live Tier B 仅 CI/Linux)。Tier A 行为完整保留。
- 2026-05-16 Tier A 首版(阿宝 / pair):`agent/pipeline/sandbox.py`(`run_sandboxed`/`SandboxReport`/`detect_tier`)。预防层 env 净化+凭证不可达+cwd-jail+wall-timeout+POSIX rlimit+Linux unshare-net;侦测层 protected-path sha256 前后比对,enforce 下 violation/超时 fail-closed。`tool_manager.execute` opt-in 接入(`DEEPINSIGHT_SANDBOX`,默认 off);`LoopGuard` enforce 按实际 tier 标注(不再恒 `sandbox=absent`)。`test_sandbox.py` 12 用例;全套 50 过。**未实现**:OS 账户/ACL 事前写阻止、Windows 真网络 deny、Tier B/C。
