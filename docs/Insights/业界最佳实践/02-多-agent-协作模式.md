# 02 · Orchestrator-Worker 多 agent 模式

> **来源**：[Anthropic Engineering — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) / [Anthropic — Building effective agents](https://www.anthropic.com/research/building-effective-agents)
> **抓取日期**：2026-04-24

## 是什么

Anthropic 的 Research 功能用 **lead agent + 并行 subagent** 架构：
- **Lead (orchestrator)**：分析用户问题 → 产出研究计划 → 把计划存到 Memory（避免 200k 上下文被截断时丢失） → 分发子任务
- **Subagent (worker)**：拿到明确的**目标 / 输出格式 / 可用工具 / 任务边界**，在自己独立的上下文里并行执行 → 返回结构化结果
- **Lead**：汇总、判断是否需要再派、产出终稿

Claude Opus 4 做 lead + Sonnet 4 做 subagent 的组合，**比单 Opus 4 强 90.2%**（Anthropic 内部 eval）。

## 代价

> **多 agent 系统 token 消耗约为单轮对话的 15×**。只在"产出价值远大于 token 成本"的任务上用。

## 为什么对 DeepInsight 有用

DeepInsight 的"洞察报告"场景天然就是个研究任务：
- 一篇 30 页论文 + 2 篇相关博客 + 用户的 3 个具体关注点 → 要并行抽取、交叉验证、归纳结构
- 上下文容易爆：输入拼起来可能 > 200k
- 每一步性质不同：解析重召回 / 抽取重 grounding / 综合重连贯

映射到我们的 pipeline：

| 角色 | 在 DeepInsight 的对应 |
|---|---|
| Lead (Opus) | 主 agent：规划报告大纲、决定需要哪些提取任务、最终组装 |
| Subagent A (Sonnet) | 解析器：PDF → 结构化 chunks |
| Subagent B (Sonnet) | 抽取器：按大纲的每个子主题独立并行抽 claim + citation |
| Subagent C (Sonnet) | 校验器：对 claim 做 grounding check，标不确定度 |
| Lead 回收 | 按模板合成最终报告 |

## 怎么落地

### 什么时候启用多 agent（否则就单 agent）

- 输入总 token > 150k
- 用户明确要"多源综述 / 综合分析"
- 报告大纲包含 ≥ 4 个独立子主题
- 预估产出价值高（用户愿意等 30s+ / 付更高成本）

**MVP 阶段默认单 agent**；多 agent 写在 spec 里当 feature flag 灰度。

### 每个 subagent 的 prompt 必含 4 项

1. **Objective**：一句话讲清楚这个 subagent 要产出什么
2. **Output format**：强制 JSON schema（见 `05-structured-output.md`）
3. **Tools & sources**：允许用哪些工具 / 引用哪些文档段（不要让它自由发挥）
4. **Task boundary**：明确**不做**什么，避免重叠（子任务重叠 = 双倍 token，结果还可能冲突）

### Memory 落地

Lead 的研究计划**必须持久化**到 Memory 文件或外部存储，不能只放在 context 里：
- 本地 MVP：写到 `web/.tmp/plans/<session-id>.json`
- 生产：对象存储 / DB

> 原因：上下文窗口虽然有 1M，但 lead agent 跑到后期 context 会膨胀，**计划本身是最值得保护的状态**。

## 和我们已有设计的连接

- 章程 § 4.1 已提"map-reduce + 1M token fallback"，本范式是其**升级版**（map 并行 + reduce 集中）
- `docs/stewardship.md` Z-7 守护人覆盖"subagent 注册表"，这里的 orchestrator-worker 模式可作为注册表的一个 entry
- `docs/specs/TEMPLATE.md` § 7「Agent 参与度」的"会用 subagent 的子任务"栏，就是填本模式的位置

## 常见坑

1. **过度使用**：简单输入用多 agent 是烧钱。加启用门槛
2. **subagent 任务边界模糊**：导致 subagent 之间大量重叠计算。**每个 subagent 的 objective 必须互斥**
3. **lead 忘了存 plan**：上下文快满时 lead 开始遗忘，产出跑偏
4. **subagent 并行写同一输出槽**：要求每个 subagent 返回独立 namespace 的结果，lead 负责合并

## 行动建议

- [ ] Z-3 守护人：在 `web/lib/llm/orchestrator/` 预留目录骨架 + 接口定义（不急着实现）
- [ ] 等 MVP 单 agent 跑稳后开 spec `spec/xxx/multi-agent-research`，先做一个子主题的 POC
- [ ] Eval 时**一定**同时测单 agent 版本做对照组，别被"多 agent 看起来 fancy"骗

## 参考

- [Anthropic Engineering — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Anthropic — Building effective agents](https://www.anthropic.com/research/building-effective-agents)
- [ByteByteGo — How Anthropic built a multi-agent research system](https://blog.bytebytego.com/p/how-anthropic-built-a-multi-agent)
