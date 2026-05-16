# 洞察报告 — 用 AWS Cedar 给 DeepInsight Agent 套上确定性缰绳

> 你的 agent 现在唯一的安全机制是「LLM 看着 LLM」(BlueAgent)——概率性的,不可审计。Cedar 是 AWS 开源的确定性鉴权引擎,可以在不杀死 agent 的前提下把它圈进「可行域」里执行。
>
> 类型:deep-read / 主题研究 · 数据源:5 个 · 落点:`agent/pipeline/gate.py`(已留好接入缝)与 `agent/loop.py`(真正的风险面,目前零闸门)

---

## 1. 问题 / 动机

DeepInsight 的 `agent/loop.py` 是一个 self-evolving loop:它会**让 LLM 生成任意 Python 代码,写进 `agent/tools/*.py`,注册进可执行列表,然后当子进程跑**(`_create_tool` L443、`tm.execute` L403)。整个过程唯一的拦截是 BlueAgent——一个 LLM 去质疑另一个 LLM 的产物。

这正是「失控」的来源。Bedrock AgentCore 官方文档把这个问题说得很直白:

> *"大语言模型是概率性的。它们不执行规则;它们预测下一个最可能的 token。"*

BlueAgent「通常」会拦住坏行为,但没有任何保证、不可复现、不可回归测试、不可审计。需要的是一道**确定性**的闸门,与概率性的判断分工协作。

## 2. Cedar 是什么

Cedar 是 AWS 开源的**策略语言 + 鉴权引擎**(Rust 内核,亚毫秒级评估,基准比 OPA/Rego 快 40–60×),也是 Amazon Verified Permissions 与 Bedrock AgentCore 的底层引擎。

决策模型极简——每次回答:**Principal**(谁)能否对 **Resource**(什么)执行 **Action**(操作),在给定 **Context**(情境)下?

两条规则决定了它适合管 agent:

- **默认拒绝**:无 `permit` 命中 → `Deny`。
- **forbid 压倒 permit**:任一 `forbid` 命中 → 一票否决,permit 救不回来。

```cedar
forbid (principal, action, resource)
when   { resource.private }
unless { principal == resource.owner };
```

## 3. 方案 / 设计

### 3.1 PARC 映射到本项目

| Cedar | Pipeline(声明式 workflow) | AgentLoop(self-evolving) |
|---|---|---|
| **Principal** | `Workflow::"daily-radar"` | `Agent::"deepinsight"` |
| **Action** | step 名:`Action::"fetch_url"` `"render"` `"critique"` | `Action::"create_tool"` `"execute_tool"` `"write_file"` |
| **Resource** | `Source::"hn"`、`Path::"data/reports"`、URL 域名 | `ToolScript::"<name>"`、`Path::"agent/tools"` |
| **Context** | task 文本、已执行步数、token 预算、`skip_blue` | 计划步数、是否首次见到该域名、本轮已建工具数 |

### 3.2 两个接入点(关键发现)

**接入点 A — Pipeline:已经留好缝。** `agent/pipeline/gate.py` 自带注释 *"Pass-through now, Cedar later. Subclass to integrate Cedar."*,`engine.py:116` 每个 step 前都调 `self.gate.check()`。接 Cedar 是填空题。

**接入点 B — AgentLoop:真正的风险面,零闸门。** `loop.py` 完全没有 gate,而它恰恰做最危险的三件事:自建工具、子进程执行、按 LLM 给的路径写文件。**「失控」的具体含义就是 B 这三件事,而它们目前只被一个概率闸门看着。**

### 3.3 优先用 `forbid` 锁死的三条红线

```cedar
// 1. 自建工具不许碰危险模块(确定性,不依赖 BlueAgent 心情)
forbid (principal, action == Action::"create_tool", resource)
when { resource.source_code like "*subprocess*"
    || resource.source_code like "*os.system*"
    || resource.source_code like "*eval(*" };

// 2. 写文件只许进白名单目录
forbid (principal, action == Action::"write_file", resource)
unless { resource.path like "data/reports/*"
      || resource.path like "agent/tools/.tmp/*" };

// 3. 每轮自建工具上限(防失控自我增殖)
forbid (principal, action == Action::"create_tool", resource)
when { context.tools_created_this_run >= 2 };
```

`permit` 侧白名单正常 step。注意「默认拒绝」意味着没写进 permit 的 step 跑不起来——这是特性,但第一版策略要付「策略引导」成本:把全部合法 step 显式放行。

### 3.4 落地代码

依赖:`pip install cedarpy`(社区绑定 k9securityio,v4.8.0 / 2025-12,支持 Py 3.9–3.14)。

`gate.py` 从 stub 变实现(对齐 cedarpy 真实 API `is_authorized(request, policies, entities)`):

```python
from cedarpy import is_authorized
from pathlib import Path

class CedarGate(PolicyGate):
    def __init__(self, policy_file: str):
        self.policies = Path(policy_file).read_text(encoding="utf-8")

    def check(self, step_name: str, ctx: "PipelineContext") -> GateResult:
        request = {
            "principal": f'Workflow::"{ctx.metadata.get("workflow","?")}"',
            "action":    f'Action::"{step_name}"',
            "resource":  f'Source::"{step_name}"',
            "context":   {"steps_done": len(ctx.log),
                          "skip_blue": bool(ctx.metadata.get("skip_blue"))},
        }
        r = is_authorized(request, self.policies, entities=[])
        return GateResult.ALLOW if r.allowed else GateResult.DENY
```

`engine.py` 不用动(已在调 `gate.check`)。给 `AgentLoop` 新增 `self.gate`,在 `_create_tool` / `tm.execute` / 写文件**之前**调一次——这是新增的、真正重要的接入点。

### 3.5 拒绝 ≠ 杀死(Windley 的关键洞察)

现在 `engine.py:118` 是 `DENY → raise`(直接崩整条 pipeline)。声明式 pipeline 崩掉可接受;但 **AgentLoop 会重新规划**,所以那里应把拒绝**当结构化反馈喂回 plan**(附「为什么拒 + 什么被允许」),让它换条安全路径继续干活。

> *"拒绝作为可观测数据返回给 agent……触发向更安全替代方案的重新规划。"* —— Phil Windley, Policy-Aware Agent Loop

这才是「按要求执行而不失控」的精确含义:不是把 agent 打死,是把它**圈进可行域里继续工作**。

## 4. 一个诚实的权衡

`cedarpy` 是社区维护(k9securityio)的 Rust 绑定,**非 AWS 官方 Python 包**。官方 Python 路径是调 Amazon Verified Permissions(AWS 收费托管服务,且给离线 agent 引入网络依赖,讽刺)。看守者本身的供应链可信度,对「不失控」是个真问题。三选项:`cedarpy`(本地/免费/够用,需信任该绑定)/ AVP(官方/收费/联网)/ Cedar 官方 Rust CLI 子进程(最保守)。对个人项目,`cedarpy` 是务实选择。

## 5. 建议下一步

1. **优先做接入点 B**:它是真正的风险面,价值最高。但需信任 `cedarpy` 绑定 + 设计「拒绝反馈回 plan」的环。
2. 接入点 A 作为低风险预热(填空题,半天)。
3. 按 `docs/specs/TEMPLATE.md` 补一份正式 spec(`docs/specs/001-cedar-policy-gate.md`)——你的 specs 目录目前为空,这会是第一份。

---

## 蓝军视角(自我反驳)

- **「确定性闸门」也可能误杀。** 默认拒绝 + 静态策略意味着任何策略没覆盖的合法新行为都会被挡——self-evolving agent 的价值正在于产生未预见的行为。Cedar 收紧的同时也削弱了「self-evolving」。缓解:策略分层,危险操作 `forbid` 收紧、探索性操作 `REQUIRE_APPROVAL` 而非 `DENY`。
- **策略本身成为新的攻击面 / 维护负担。** 策略写错(漏一条 permit)→ 整条 workflow 静默失败;策略文件若可被 agent 写入 → 自我提权。策略文件必须是 agent 不可写的红线资源。
- **`like` 字符串匹配挡不住决心。** `*subprocess*` 拦不住 `__import__('sub'+'process')`。Cedar 是纵深防御的一层,不是沙箱替代品——真正的隔离仍需进程/容器级。

---

**Sources:**
- [What is Cedar? — Cedar Reference Guide](https://docs.cedarpolicy.com/) · [Cedar policy syntax](https://docs.cedarpolicy.com/policies/syntax-policy.html)
- [Understanding Cedar policies — Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/policy-understanding-cedar.html)
- [A Policy-Aware Agent Loop with Cedar and OpenClaw — Phil Windley](https://www.windley.com/archives/2026/02/a_policy-aware_agent_loop_with_cedar_and_openclaw.shtml)
- [cedarpy — PyPI](https://pypi.org/project/cedarpy/) · [k9securityio/cedar-py — GitHub](https://github.com/k9securityio/cedar-py)
- [Why Cedar Policies Matter for Bedrock AgentCore Gateway — Xebia](https://xebia.com/blog/cedar-policies-for-amazon-bedrock-agentcore-gateway/)

*生成:2026-05-15 · DeepInsight 洞察分析*
