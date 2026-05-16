---
id: 001
title: Cedar 策略闸门 — agent 可控加固方案
author: 阿宝
reviewers: []
status: draft          # draft | review | approved | building | done | rejected
created: 2026-05-15
updated: 2026-05-15  # v6 Phase 2 LoopGuard+ToolManager PEP+DenialFeedback；v5 Phase 1；v4 决策锁定+Phase 0
related_adrs: []
related_tasks: []
---

# 001 · Cedar 策略闸门 — agent 可控加固方案

> 配套洞察:`data/reports/2026-05-15-cedar-agent-governance.md`
>
> **实现状态(2026-05-15)**:策略脚手架已抢跑创建于 `agent/policies/`
> (`agent.cedar` + `schema.cedarschema`)及审计目录 `agent/.audit/`,
> **先于 git/sequencing**(`agent/` 尚未纳入版本控制)。两个阻塞决策见
> `agent/policies/DECISIONS-REQUIRED.md`:**① 信任锚位置 ② 审计链头外锚**。
> **2026-05-15 决策锁定**:① 信任锚 = **Git**(PDP attest 工作区 vs HEAD blob;
> 运行中被改/删 → deny-all-dangerous)② 审计链头 = **stderr**。sentinel 已移除,
> DECISIONS-REQUIRED.md 两项打勾。**Phase 0 已落地**:`agent/pipeline/pdp.py`
> (`CedarPDP` + `AuditLog`)+ `CedarGate`(shadow 非阻断)+ 测试。`CedarPDP`
> 保留 sentinel 守卫代码:若 `agent.cedar` 再现 `UNRESOLVED-DECISION` 且 mode=enforce → 拒绝启动。

## 1. 问题 / 动机

`agent/loop.py` 是一个 self-evolving loop:它让 LLM **生成任意 Python 写入 `agent/tools/*.py`,注册进可执行列表,再当子进程运行**(`_create_tool` L443、经 `ToolManager.execute` 的 `subprocess.run` L104）。它还按 LLM 给定的路径写文件(`_save_report` L542、`_append_changelog` L476）。

这条链路目前唯一的拦截是 **BlueAgent —— 一个 LLM 质疑另一个 LLM**。LLM 是概率性的:它不执行规则,只预测下一个 token。BlueAgent「通常」拦得住,但不可复现、不可回归、不可审计。

`agent/pipeline/gate.py` 已自带注释 *"Pass-through now, Cedar later. Subclass to integrate Cedar."*,且 `engine.py:116` 每个 step 前都调 `gate.check()` —— 设计意图已在,实现是空的(永远 `ALLOW`)。**这个静默放行本身就是当前最大的漏洞面。**

本方案用 Cedar(AWS 开源、确定性、亚毫秒)给 agent 配一道**确定性闸门**,与概率性的 BlueAgent 分工:BlueAgent 判断「这想法好不好」,Cedar 保证「无论想法多好,这条红线不能越」。

## 2. 目标(Goals）

- [ ] AgentLoop 中 `create_tool` / `execute_tool` / `write_file` 三类操作 **100% 经过 PDP**(无 0 旁路路径,由代码审计 + 测试断言）
- [ ] 默认拒绝可验证:未被任何 `permit` 命中的 step → `DENY`(golden case)
- [ ] ≥ 3 条红线 `forbid` 规则,每条 ≥ 3 条对抗用例全部拦截
- [ ] 移除 `gate.py` 的静默 `ALLOW`:引擎/PDP 故障时危险操作 **fail-closed**
- [ ] **log-or-deny 不变式**:经 PDP 的每个判定 100% 在返回前产生审计记录;所有 sink 写失败 → 强制 `DENY`(无记录则无动作,golden case)
- [ ] 策略文件保护覆盖**一切变更动作**(写/删/改名/改权限),不止 `write_file`(golden case)
- [ ] 策略文件被删/被篡改 → PDP 进入 **deny-all-dangerous**(「删 = 自锁」),且校验锚**不在 agent 可达范围**
- [ ] 生成工具在**沙箱**内运行(无仓库写、策略只读、出网受控)—— 列为 Phase 2 强制前置
- [ ] Cedar 请求经**结构化实体**构造,非字符串拼接(防 Cedar 注入,golden case)
- [ ] 路径在进 PDP 前**规范化**(解析 `..`、符号链接、绝对化);穿越/软链一律拒
- [ ] 单次决策 p95 < 5ms(Cedar 亚毫秒,留足余量)
- [ ] 提供 **shadow 模式**:只判定+记录、不阻断,用于零破坏地收集策略缺口

## 3. 非目标(Non-Goals）

- 本 spec **不实现**进程/容器级沙箱本体,但将其列为 **Phase 2 enforce 的强制前置依赖**(单独 spec 002）。Cedar 是应用层决策闸门,只能看见经过 PEP 的决策,**看不见子进程自身的 syscall**;脱离沙箱,Cedar 对「铁了心绕过文件系统的 agent」无效。这不是可推迟项,是 Phase 2 的硬门槛。
- 不替换 BlueAgent(二者互补:概率判断 + 确定性红线)
- 不接 Amazon Verified Permissions / 任何云(本地 `cedarpy`,避免给离线 agent 引入网络依赖)
- 不覆盖 `/web` Next.js 应用(本 spec 只管 `/agent`)
- 不做策略可视化/管理 UI(策略即代码,纯文件;推迟)

## 4. 方案 / 设计

### 4.1 用户视角

对正常使用者**无感**:合法 workflow / 工具照跑。变化只在越界时发生:

- **Pipeline**:被拒的 step 不再静默跳过,日志显式打出 `DENY` + 命中的策略 id。
- **AgentLoop**:被拒不再崩溃。拒绝作为**结构化反馈**回灌 `_plan_task`,agent 换条安全路径重规划(上限 2 次,仍不行则干净中止并报明原因)。
- **审批层**:命中 `@gate("approval")` 的操作(如新建工具)在交互场景提示确认,非交互场景按 `REQUIRE_APPROVAL` 跳过并记录。

### 4.2 技术设计

**新增 / 改动模块**

| 文件 | 改动 |
|---|---|
| `agent/policies/agent.cedar` | 新增:策略文件(forbid 红线 + permit 白名单 + approval 层) |
| `agent/policies/schema.cedarschema` | 新增:实体/动作 schema,供 `validate_policies` 在 CI 校验 |
| `agent/pipeline/pdp.py` | 新增:`CedarPDP` —— 封装 `cedarpy.is_authorized`,加载策略/schema,统一 `decide()`;pipeline 与 loop 共用 |
| `agent/pipeline/gate.py` | 实现 `CedarGate(PolicyGate)`,调用 `CedarPDP`,映射 step → PARC,产出三态 |
| `agent/tool_manager.py` | `execute()` / `register()` 入口加 PEP(扼颈点防御,而非散落调用点) |
| `agent/loop.py` | 注入 gate;写文件前加 PEP;`DENY` → 构造 `DenialFeedback` 回灌 plan |

**PARC 映射**

| | Pipeline | AgentLoop |
|---|---|---|
| Principal | `Workflow::"<name>"`(`ctx.metadata["workflow"]`) | `Agent::"deepinsight"` |
| Action | `Action::"<step_name>"` | `Action::"create_tool"` / `"execute_tool"` / `"write_file"` |
| Resource | `Step::"<step_name>"` | `ToolScript::"<name>"`(带 `source_code` 属性)/ `Path::"<path>"` |
| Context | `{steps_done, skip_blue, date, trust}` | `{tools_created_this_run, total_tools, first_seen_domain, trust}` |

> **`context.trust`**:动作来源信任级。`"user"` = 用户直接指令;`"untrusted"` = 由抓取的网页/外部内容驱动(deep-read 抓回的 URL 文本里若含指令,落入此级)。principal 是静态的 `Agent::"deepinsight"`,**无法区分「用户让我做」和「网页让我做」**——`trust` 补这个缺口,injection 落到 `"untrusted"` 即被钉死。该值由 PEP 依据「当前 step 是否在处理外部抓取内容」判定,**不取自 LLM 输出**。
>
> **请求构造防注入**:P/A/R/C 一律用 `cedarpy` 的**结构化实体(entity dicts)**传入,**严禁**把 `workflow` 名、路径等不可信值字符串拼进策略/实体文本(否则 `workflow="x\"; permit(...)"` 即可越狱,等同 SQL 注入)。
>
> **路径规范化**:`resource.path` 必须是 PEP **规范化后的绝对路径**(解析 `..`、`~`、符号链接)。`like "data/reports/*"` 对未规范化的 `data/reports/../../.env` 会**误判为白名单**——规范化 + 拒绝软链/穿越是 forbid 规则生效的前提,不是可选项。

**三态决策**:Cedar 原生只回 `Allow`/`Deny`。第三态(`REQUIRE_APPROVAL`)用**策略注解**实现 —— `permit` 策略带 `@gate("approval")`,`CedarPDP` 从 `is_authorized` 的 diagnostics 取命中策略 id,若该策略有此注解则 `gate.check` 返回 `REQUIRE_APPROVAL` 而非 `ALLOW`。这样三态全部由策略文件声明,不散在代码里。

**策略分层(具体)**

```cedar
// ── 红线:forbid 压倒一切 ────────────────────────────────
// ⚠ 字符串黑名单是【advisory】层:混淆(`"sub"+"process"`、base64、getattr)
//   必然绕得过。真正的控制是「低信任 forbid + 强制沙箱」,见下。
forbid (principal, action == Action::"create_tool", resource)
when { resource.source_code like "*subprocess*"
    || resource.source_code like "*os.system*"
    || resource.source_code like "*eval(*"
    || resource.source_code like "*__import__*"
    || resource.source_code like "*os.remove*"
    || resource.source_code like "*shutil.rmtree*" };

// 策略文件 / 凭证 / git 配置 = 不可【变更】红线(自我提权防护)
// 覆盖一切变更动作:写 / 删 / 改名 / 改权限 —— 不止 write_file
// (resource.path 已由 PEP 规范化;穿越/软链在进 PDP 前已拒)
forbid (principal,
        action in [Action::"write_file", Action::"delete_file",
                   Action::"move_file", Action::"chmod"],
        resource)
when { resource.path like "agent/policies/*"
    || resource.path like "agent/.audit/*"
    || resource.path like "*/.env*"
    || resource.path like "*/.git/*" };

// 写白名单同样扩到全部变更动作
forbid (principal,
        action in [Action::"write_file", Action::"delete_file", Action::"move_file"],
        resource)
unless { resource.path like "data/reports/*"
      || resource.path like "agent/tools/.tmp/*" };

forbid (principal, action == Action::"create_tool", resource)
when { context.tools_created_this_run >= 2 };

// 低信任上下文(injection 来源):禁一切自我演化 / 文件变更 / 执行
forbid (principal,
        action in [Action::"create_tool", Action::"write_file",
                   Action::"delete_file", Action::"execute_tool"],
        resource)
when { context.trust == "untrusted" };

// registration 本身是受控动作(防止把恶意脚本标记为「已注册」绕白名单)
@gate("approval")
permit (principal == Agent::"deepinsight",
        action == Action::"register_tool", resource);

// ── 白名单:默认拒绝,显式放行已知 step ──────────────────
permit (principal == Workflow::"daily-radar",
        action in [Action::"fetch_sources", Action::"fetch_hn",
                   Action::"dedup", Action::"filter_date", Action::"rank",
                   Action::"summarize", Action::"critique", Action::"render"],
        resource);

// ── 审批层:允许但需确认 ─────────────────────────────────
@gate("approval")
permit (principal == Agent::"deepinsight",
        action == Action::"create_tool", resource);
```

**拒绝即反馈(不杀 agent)**:`engine.py:118` 现在 `DENY → raise`(pipeline 是固定 DAG,崩可接受)。但 AgentLoop 会重规划,故 PEP 抛 `PolicyDenied` 后,loop 捕获并构造:

```python
DenialFeedback(action, resource, reason, matched_policy_id, hint)
```

把它拼进下一轮 `_plan_task` 的 prompt(「上一步被策略拒绝:<reason>;被允许的替代:<hint>」),重规划上限 2 次,超限则中止并在报告中明示。

**fail-closed-on-missing(删 = 自锁,核心安全性质)**:`CedarPDP` 启动时把策略文本读进内存并计算校验和;**每次决策前**校验磁盘上的策略文件仍在、内容未变。一旦发现**被删 / 被改 / 解析失败 / `cedarpy` import 失败** → PDP 进入 **deny-all-dangerous**:`create_tool`/`execute_tool`/任何 mutation 一律 `DENY`,大声报错,**绝不静默 ALLOW**。

> 含义:**agent 破坏缰绳的动作,后果是把自己钉死,而不是获得自由**。删策略文件 ≠ 解锁 = 全面锁死。
>
> **信任锚位置**(关键):期望校验和**不能**和策略文件放一起(否则 agent 两个一起删/改即绕过)。锚必须在 agent 不可达处——编译进代码常量 / 环境注入 / 宿主只读挂载。开放问题见 §9。
>
> **自我 DoS 缓解**:策略文件正被人编辑时也会触发锁死。提供:① 明确的运维信号(日志 + 退出码可辨)② 人工 `--policy-override <path>` 显式旁路(仅人可用,需有意为之)。

**强制沙箱(Phase 2 硬前置)**:生成的工具以子进程运行,其 syscall **不经过 Cedar**——它能直接 `Path("agent/policies/...").unlink()`。因此 Phase 2 enforce **必须**先具备:生成工具运行在沙箱内,**无仓库写权限、策略目录只读挂载、出网仅经宿主控制的代理白名单**。无沙箱则 Cedar 对决心绕过者无效。沙箱本体见 spec 002。

**审批层在无人值守场景**:`@gate("approval")` 命中且**非交互(cron / daily-radar 自动跑)→ 默认 `DENY`**,不是「skip 后自由重规划」。否则自动化场景里审批形同虚设,或被诱导绕到一条恰好自动放行的路径。无人时:宁可任务失败,不可降级放行。

**registration 是受控动作**:`resource.registered` 必须由**可信 registry**(`tool_manager` 读 `registry.json`)提供,**绝不取自 agent 输入**;`register_tool` 本身走 approval(见上策略块)——否则 agent 「自注册」恶意脚本即可绕过 `permit.known_registered_tool` 白名单。

#### 审计日志:log-or-deny(每次必记)

**核心不变式**:`CedarPDP.decide()` 在**返回判定之前**写审计记录;**所有 sink 写失败 → 判定强制改为 `DENY`**。即「记不下 = 不放行」——把"必须记录"和"允许通过"焊死,使"每个经 PDP 的判定都被记"成为结构性不变式,而非尽力而为。

```python
def decide(req):
    decision, policy_ids = cedar_eval(req)            # Cedar 评估
    record = build_record(req, decision, policy_ids)  # 含 prev_hash/hash
    if not audit.write(record):                       # 同步、多 sink
        return DENY, "audit-sink-failed"              # ← 记不下即拒
    return decision, policy_ids
```

- **全判定都记,不只 forbid**:`ALLOW`/`APPROVAL` 同记,forbid 命中标 `severity=high`。只记 DENY 会让人看不见"什么被悄悄放行"。
- **与执法解耦**:shadow 模式不阻断但**照记**(这正是 shadow 的全部价值)。记录无条件,执法才有条件。
- **单一扼颈点**:只在 `CedarPDP.decide()` 实现,pipeline gate 与 loop PEP 共调 → 一处保证全局生效。**不复用** `benchmark/metrics.jsonl`(agent 可写、仓库内、跑完才写一次)。

**冗余 sink**(`audit.write` 语义:≥1 个 durable sink 成功 = 记录成功;全失败 = fail-closed `DENY`):

| Sink | 角色 | agent 可达 |
|---|---|---|
| `agent/.audit/*` append-only 文件 | 主审计流 | 否(写白名单外 + 受上方 forbid 保护) |
| stderr / stdout | 实时,飞出进程即不可改 | 否(harness/运维捕获) |
| 宿主侧 / off-box(可选) | 离线留证 | 否 |

**防篡改(挡不住删,但让删留疤)**:每条带 `seq`(连续递增)+ `prev_hash`/`hash`(哈希链)。删/改任一条 → 链断或缺号 → 校验即暴露。链头哈希定期外锚到 agent 够不着处(stderr / 宿主)。

**记录 schema**(逐条 JSON):`seq, ts_wall, ts_mono, run_id, mode, principal, action, resource(规范化后), context(含 trust), decision, severity, matched_policy[], policy_sha256, prev_hash, hash`。`policy_sha256` 与 fail-closed-on-missing 的校验和同源,可事后确认"该判定用的哪版策略"。

**fsync 策略**:`DENY`/`APPROVAL` 每条 fsync(不丢关键证据);`ALLOW` 可缓冲 + 周期刷。agent 决策频率不高,全程 fsync 亦可接受。

**诚实边界**:本机制只保证**经过 PDP 的判定**必记。绕过 PDP 的子进程 syscall(`os.remove` 等)**没有"判定"可记** —— 唯一真解仍是沙箱(spec 002)把文件/网络操作收回到受 PDP 中介的接口。事后篡改:**detect,非 prevent**。

**灰度上线**

- **Phase 0 — shadow**:`CedarPDP` 判定 + 落日志,**不阻断**。跑现有 3 个 workflow + 若干 loop 任务,收集「本会被拒的合法操作」→ 补 permit。解决默认拒绝的「策略引导/误杀」风险,且产出 golden 数据。
- **Phase 1 — enforce pipeline**:✅ **已落地**。`engine.py._resolve_gate` 按 `--cedar-mode` / env `DEEPINSIGHT_CEDAR_MODE` 选闸门(`off`=pass-through / `shadow`=判定+审计不阻断【默认】/ `enforce`=DENY→raise、APPROVAL→skip);`shadow` 构造失败回退 pass-through,`enforce` 构造失败抛出(fail-closed)。`__main__.py` 加 `--cedar-mode`。3 个 workflow 的 step 已全在 `agent.cedar` 白名单,enforce 不误杀。
- **Phase 2 — enforce AgentLoop**:✅ **已落地(默认 shadow)**。`LoopGuard`(gate.py)封装 CedarPDP;`ToolManager(policy=)` 扼颈点 PEP(`execute`→execute_tool、`register`→register_tool);`loop.py` `_create_tool` 前过 create_tool 闸门、`_save_report`/`_append_changelog` 过 write_file;`DenialFeedback` + `_create_tool_with_replan`(上限 2 次,超限干净降级不杀 agent)。**⚠ enforce 但沙箱(spec 002)未实现**:`LoopGuard` 启动即 loud WARN + 审计 `sandbox=absent` —— Cedar 确定性红线+审计生效,但生成工具子进程 syscall 不经 Cedar,**防御纵深不完整**,诚实标注。策略缺口 `agent/changelog.md` 经 shadow-first 发现并补入白名单。
- **Phase 3 — CI**:`validate_policies(schema)` 进 CI;策略改动需评审。

### 4.3 备选方案

1. **PEP 散在 loop.py 各调用点**(`_create_tool`/`_execute_single_step`/`_save_report` 分别加)。淘汰:易漏、与未来调用方不一致。改为**扼颈点防御**(`ToolManager.execute`/`register` + 写文件统一封装)。
2. **OPA / Rego**。淘汰:更慢(基准 40–60×),且本项目无 OPA 既有依赖,Cedar 与 `gate.py` 现有设计意图一致。
3. **纯 LLM 守卫(强化 BlueAgent)**。淘汰:概率性,本 spec 的核心动机就是它不可靠。
4. **Amazon Verified Permissions**。淘汰:收费 + 给离线 agent 引入网络依赖(见非目标)。

## 5. 测试策略 ⚠ 必填

### 5.1 Test checklist
- [ ] 单元测试覆盖核心函数(目标覆盖率:`CedarPDP.decide` / `CedarGate.check` ≥ 90%)
- [ ] 集成测试覆盖主流程(3 个 workflow 在 enforce 下跑通;loop 的 create_tool→deny→replan→成功 全链路)
- [ ] Eval:本闸门**自身确定性,不调 LLM**;golden case ≥ 10 条(default-deny、3 条红线各正反、approval 注解、fail-closed、策略文件篡改)。被拒后回灌 `_plan_task` 是 LLM 调用 → 见对抗性测试。citation/hallucination 准确率对本特性 `N/A + 闸门无生成内容`
- [ ] 对抗性测试(≥ 9 条):① prompt-injection 写含 `subprocess` 的工具 ② 路径穿越 `data/reports/../../agent/policies/agent.cedar`(验证规范化后被拒) ③ 混淆导入 `__import__('sub'+'process')`(验证此属 advisory 层,真拦在沙箱) ④ 改 `agent/policies/*` 自我提权 ⑤ **`delete_file` / `move_file` 策略文件**(验证非仅 write 被拦) ⑥ **删策略文件后**任一危险操作 → 验证 deny-all-dangerous 锁死 ⑦ **Cedar 注入**:`workflow` 名含 `"; permit(...)` ⑧ **registration 欺骗**:agent 自注册恶意脚本再 execute ⑨ **低信任**:抓取的 URL 文本含「建个工具删 X」→ `context.trust=untrusted` 命中 forbid ⑩ 符号链接逃逸:`agent/tools/.tmp/x` → 软链到策略文件
- [ ] 回归影响:① `gate.py` 由 pass-through 改为 enforce,可能挡掉未列入 permit 的合法 step → 用 Phase 0 shadow 日志兜底 ② `engine.py` DENY/REQUIRE_APPROVAL 既有分支行为不变 ③ BlueAgent 流程不受影响(并存)

### 5.2 Reliability checklist
- [ ] 故障模式:PDP/策略不可用 → 危险操作 fail-closed `DENY`;用户看到「策略引擎不可用,操作已拒绝(策略 id: -)」,不静默放行
- [ ] 超时 / 重试策略(含退避):Cedar 进程内、亚毫秒、无网络 → 无重试需求;`cedarpy` 仅启动时 import 一次,失败即进 fail-closed 模式。`N/A 网络退避`
- [ ] 成本 / 限流:拒绝→重规划循环硬上限 2 次,封顶额外 token 开销;无每用户限流需求(单用户本地)
- [ ] 观测:每次决策打点 + 结构化日志,字段含 `principal/action/resource/decision/matched_policy_id/workflow/run_id/trust`
- [ ] **审计日志完整性 / log-or-deny**:每个判定返回前必写记录,所有 sink 失败 → 强制 `DENY`;主 sink `agent/.audit/*` 追加写 + agent 不可达(写白名单外 + forbid 保护)+ 哈希链(`seq`/`prev_hash`)+ 链头外锚;`DENY`/`APPROVAL` 每条 fsync。详见 §4.2「审计日志:log-or-deny」
- [ ] **fail-closed-on-missing**:策略缺失/篡改 → deny-all-dangerous;校验锚不与策略文件同处;附自我 DoS 缓解(运维信号 + 人工 override)
- [ ] 错误文案:对外(报告内)统一为「操作被策略拒绝」,不泄露 Cedar 内部诊断原文;内部日志保留完整 diagnostics

## 6. 验收标准

- [ ] 用户跑现有 3 个 workflow,enforce 模式下行为与之前一致(shadow 已补齐 permit)
- [ ] agent 生成含 `subprocess` 的工具时,该工具**不被写盘、不被注册**,loop 收到结构化拒绝并重规划
- [ ] agent 试图写 `agent/policies/` 或 `web/.env*` 时被拒,且事件入 metrics
- [ ] PDP 故障注入下,`create_tool` 返回 `DENY`,无任何工具落盘
- [ ] **每个判定都能在 `agent/.audit/` 找到对应记录**;注入 sink 故障 → 判定被强制 `DENY` 且无动作执行(log-or-deny)
- [ ] 手动删/改一条审计记录 → 链校验报告断点(篡改可检出)
- [ ] 单次决策 p95 < 5ms(benchmark 实测)
- [ ] `docs/specs/` 与策略文件一致;`validate_policies` 在 CI 绿

## 7. Agent 参与度(预估)

- 预估主要模式:`[pair]`(策略设计与 fail-closed 边界需人确认),实现细节 `[agent]`
- 会用 subagent 的子任务:批量生成对抗性测试用例;扫描 loop.py 旁路路径
- 是否新增 / 修改 skill:暂不;若 enforce 上线后需常态化「策略评审」可再评估加 skill

## 8. 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| 默认拒绝误杀合法新行为,削弱 self-evolving | 高 | 中 | Phase 0 shadow 先收集;探索性操作走 `REQUIRE_APPROVAL` 而非 `DENY` |
| 策略文件本身成攻击面 / 自我提权 | 中 | 高 | `agent/policies/*` 列为不可写红线(forbid + 写白名单双重);CI 校验;文件权限 |
| `like` 字符串匹配被混淆绕过 | 高 | 高 | 明确定位为 advisory 层;真控制 = 低信任 forbid + **强制沙箱**(Phase 2 硬前置) |
| 子进程 syscall 绕开 Cedar(删策略/读凭证/出网) | 高 | 高 | fail-closed-on-missing(删=自锁)+ 强制沙箱 + OS 只读 + 出网代理白名单 |
| 路径穿越 / 符号链接绕白名单 | 中 | 高 | PEP 进 PDP 前**规范化**绝对路径 + 拒软链;对抗用例覆盖 |
| Cedar 请求字符串拼接 → 策略注入 | 中 | 高 | 一律结构化实体构造,不可信值绝不拼进策略/实体文本;golden case |
| injection 在「允许集」内挑动作组合作恶(SSRF/DoS) | 中 | 高 | `context.trust` 降级钉死;按工具**参数**约束而非仅工具名白名单(§9) |
| 审批层在无人值守被绕(skip→自由重规划) | 中 | 高 | 非交互命中 approval → 默认 `DENY`,宁可失败不降级 |
| 审计日志被攻陷工具篡改/删除 | 中 | 中 | log-or-deny(记不下=不放行)+ 追加写 + agent 不可达 + 哈希链让删/改留疤 + 链头外锚 |
| 审计 sink 故障使决策无证可查 | 低 | 高 | log-or-deny:所有 sink 失败即强制 `DENY`,无记录则无动作 |
| fail-closed 引发自我 DoS(人编辑策略时锁死) | 中 | 中 | 运维信号 + 人工 `--policy-override` |
| `cedarpy` 为社区绑定(非官方)+ 被 agent 改 site-packages | 低 | 中 | pin + hash 校验;沙箱内无 pip/无写 site-packages;接口隔离在 `CedarPDP` |
| 策略写错导致 workflow 静默失败 | 中 | 中 | 显式日志(不静默)+ shadow 阶段验证 + golden case |

## 9. 开放问题

- [x] **信任锚放哪** → **已决 2026-05-15:Git 作锚**。PDP 启动 attest 工作区 `agent.cedar` vs `HEAD` blob(committed/uncommitted-diff/git-unavailable 三态记日志;enforce 下 git-unavailable → deny-all-dangerous);运行中文件 sha 偏离启动基线 → 永久 latch deny-all-dangerous
- [ ] **沙箱技术选型**(spec 002):受限子进程 + seccomp / venv + import 钩子 / 容器 / Firejail?Windows 上的等价物?
- [ ] **信任分级粒度**:`user`/`untrusted` 两级够吗?是否要 `tool_output`、`prior_agent` 等中间级
- [ ] **按参数约束工具**:`permit.known_registered_tool` 现在放行该工具的任意参数(SSRF/DoS 风险)。是否需 per-tool 参数 schema 进 Cedar context
- [x] **审计链头锚定到哪** → **已决 2026-05-15:stderr**(harness/终端捕获)。每次决策 `CEDAR-AUDIT seq=.. hash=..` 打 stderr;主存 `agent/.audit/*.jsonl` append-only + 哈希链
- [ ] **Windows append 单写者**:`O_APPEND` 原子性在 Windows 与 POSIX 不同,所有 sink 写须经单一串行 logger;与「Windows 沙箱选型」同属一类环境问题
- [ ] 三态用「策略注解」vs「独立 query」—— 需确认 `cedarpy` diagnostics 能稳定取到命中策略 id
- [ ] 只读 pipeline step 在 PDP 故障时:fail-closed(默认)vs fail-open —— 需阿宝拍板
- [ ] 是否需要一份 ADR 记录「确定性闸门 + 概率守卫并存」(建议:是)
- [ ] `agent/` 当前未纳入 git —— 本 spec 落地前必须先纳入版本控制

---

## Changelog
- 2026-05-15 初稿(阿宝 / pair with Claude）
- 2026-05-15 v2 加固(阿宝 / pair):① 策略文件保护扩到删/改名/改权限(原仅 write）② fail-closed-on-missing「删=自锁」+ 信任锚 ③ 强制沙箱升为 Phase 2 硬前置 ④ 防 Cedar 注入(结构化实体)⑤ 路径规范化防穿越/软链 ⑥ `context.trust` 信任分级钉死 injection ⑦ registration 受控 ⑧ 审批层无人值守默认 DENY ⑨ 审计日志完整性。新增 6 条风险、7 条对抗用例、4 个开放问题。
- 2026-05-15 v6 Phase 2 落地(阿宝 / pair):`LoopGuard` + `ToolManager` 扼颈点 PEP(execute/register)+ `loop.py` PEP(create_tool / save_report / append_changelog)+ `DenialFeedback` 有界重规划(cap 2,超限干净降级)。enforce 但无沙箱 → loud WARN + 审计 `sandbox=absent`(诚实标注防御纵深不完整,待 spec 002)。shadow-first 发现并修策略缺口:`agent/changelog.md` 入白名单。`agent/tests/test_phase2.py` 12 用例;全套 **38 用例过**。Phase 2 默认 shadow,`loop.py` 旧行为不变(policy=None 不介入)。
- 2026-05-15 v5 Phase 1 落地(阿宝 / pair):`CedarGate` 接入 `PipelineEngine`。`engine._resolve_gate`(off/shadow/enforce,默认 shadow,优先级 显式>CLI>env>默认);`__main__.py --cedar-mode`;`CedarGate` 加 `audit_dir`;`agent/tests/test_engine_gate.py` 8 用例(选择优先级 + 端到端 enforce 阻断/放行/shadow 不阻断)。全套 26 用例过。Phase 1 仅 pipeline;loop.py(Phase 2)未动。
- 2026-05-15 v4 决策锁定 + Phase 0 落地(阿宝 / pair):两阻塞决策定为 ① Git 锚 ② stderr 链头;sentinel 移除、DECISIONS-REQUIRED 打勾;agent.cedar 每条加 `@id`;实现 `agent/pipeline/pdp.py`(`CedarPDP`+`AuditLog`)、`CedarGate`(shadow)、`agent/tests/` golden/对抗用例;cedarpy 入 requirements。
- 2026-05-15 v3 审计设计(阿宝 / pair):新增 §4.2「审计日志:log-or-deny」—— 记录是放行的前提(记不下即拒)、全判定都记、冗余 sink、哈希链防篡改、逐条 schema、fsync 策略、诚实边界。`agent/.audit/*` 纳入不可变更红线;§2/§5.2/§6/§8/§9 同步细化。
