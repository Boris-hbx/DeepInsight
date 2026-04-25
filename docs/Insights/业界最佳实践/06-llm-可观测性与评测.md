# 06 · LLM 可观测性与评测

> **来源**：[Digital Applied — Agent Observability 2026](https://www.digitalapplied.com/blog/agent-observability-2026-evals-traces-cost-guide) / [Braintrust — LangSmith alternatives 2026](https://www.braintrust.dev/articles/langsmith-alternatives-2026) / [OpenTelemetry — GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
> **抓取日期**：2026-04-24

## 三层 Eval（这是基本盘）

> 可靠的 agent 需要三层 eval：
> 1. **Unit eval**：对离散步骤打单点分（"这个 prompt 从这个输入得出的 JSON 对不对"）
> 2. **LLM-as-judge 回归套件**：对主观质量（文风 / 连贯 / 是否捕到关键洞察）打分
> 3. **生产 trace 采样**：线上真实调用采样回看，抓 drift

三层都要有，缺一不可。只有 unit → 主观质量塌了看不见；只有 judge → 客观的东西（比如字段是否存在）靠 judge 不经济。

## 为什么对 DeepInsight 至关重要

DeepInsight 的产出**没有唯一正确答案**。传统单测给不出"这份报告好不好"。必须：
- 逐字段比对（unit：schema 合法性 / citation 存在 / confidence 合理）
- LLM-judge（回归：同一输入产出的报告质量是否不如上一版）
- 线上采样（drift：真实用户输入和 golden 分布差多远）

Z-6 守护人手上的"citation 准确率门禁"就是 unit 层的一例；但**还需要加 judge 和采样**。

## 工具选型（不站队）

| 需求 | 推荐 |
|---|---|
| 开源自托管、MIT、Docker 可起 | **Langfuse**（LLMOps 开源基线） |
| LangChain 深度集成 | LangSmith |
| 严肃 eval 科学 + CI 质量门 | Braintrust |
| **先别接工具，手搓** | `evals/` + 一堆 JSON + GitHub Actions |

**MVP 建议**：**先手搓 `evals/` 目录**（见下），产品起量后再接 Langfuse 或 Braintrust。**不要**一上来接三家。

## OpenTelemetry GenAI 语义约定

> 用 OTel 的 GenAI semantic conventions 打 trace，保持 vendor 无关，未来换 observability 平台零成本

关键属性（span 必打）：

```
gen_ai.system          = "anthropic"
gen_ai.request.model   = "claude-opus-4-7"
gen_ai.usage.input_tokens
gen_ai.usage.output_tokens
gen_ai.usage.cache_read_input_tokens     # ← 命中率
gen_ai.usage.cache_creation_input_tokens # ← 写入
gen_ai.request.temperature
```

业务属性（我们自加）：

```
deepinsight.user_id
deepinsight.feature           = "pdf_summary" / "multi_source_synth"
deepinsight.prompt_version    = "v3"
deepinsight.document_hash
```

→ Z-5 守护人的 dashboard 就是在这些 tag 上做聚合。

## 最容易出事的三类问题

> 生产事故大多来自：**工具调用失败 / 上下文截断 / agent runaway loop**，而**不是**模型本身答错。标准 APM 看不到这些，**必须用 agent-aware instrumentation**。

对 DeepInsight 直接对应：

| 失败模式 | 检测方式 | 兜底 |
|---|---|---|
| Claude tool_call 返回异常 | span.status=error + gen_ai.response.finish_reasons != "end_turn" | 重试 + 用户可见降级文案 |
| 1M context 被截（超 1M） | 上传前预估 token，超阈值拒绝 / 触发 map-reduce | 预检失败前置提示 |
| agent loop 不收敛（subagent 调自己） | 统计 turn 数，> N 熔断 | 熔断后返回部分结果 |

这三项**都**放进 `spec/TEMPLATE.md` § 5.2 reliability checklist。

## 落地路径（循序渐进）

### 阶段 1：MVP（现在 - 6 周）

**手搓 eval**：
```
evals/
├── golden/
│   ├── pdf-summary/
│   │   ├── 001-arxiv-transformers.pdf
│   │   ├── 001-expected.json          # 人工标注的预期报告骨架
│   │   └── 001-judge-prompt.md        # LLM-judge 打分 prompt
│   └── ...
├── runners/
│   ├── run-unit.ts                    # 跑 schema + citation grounding
│   └── run-judge.ts                   # 跑 LLM-as-judge
└── reports/
    └── 2026-04-24-eval.md
```

CI：PR 改 `web/lib/llm/**` 或 `prompts/**` → 自动跑 eval 子集 → 低于阈值阻塞合并。

OTel：用 `@opentelemetry/api` 打 span，先输出到控制台 / 日志文件即可，**不急着接 Jaeger / Grafana**。

### 阶段 2：产品 beta（6 - 12 周）

接 **Langfuse**（开源、MIT、自托管）：
- 所有 span 转发 Langfuse
- 开 LLM-judge 自动评分
- 建 "最近 7 天 citation 准确率" dashboard

### 阶段 3：规模化（12 周后）

看那时需要：
- 如果 eval 科学需求重 → **Braintrust**
- 如果 OTel 生态已成熟 → 保持自托管 + Grafana
- 生产采样率 5–10%，接到 eval 回放

## 行动建议

- [ ] Z-6 守护人：现在就建 `evals/` 目录骨架 + 首批 5 条 golden
- [ ] Z-5 守护人：封装一个 `withGenAiSpan(fn)` helper，所有 Anthropic 调用走它（统一打 OTel attr）
- [ ] spec 模板 § 5.2 加三条失败模式检查（工具调用失败 / 上下文截断 / loop）
- [ ] 不要在 MVP 接 LangSmith / Langfuse / Braintrust 中的任何一家（**过早优化**）

## 参考

- [Digital Applied — Agent Observability 2026: Evals, Traces, Cost Guide](https://www.digitalapplied.com/blog/agent-observability-2026-evals-traces-cost-guide)
- [Firecrawl — Best LLM Observability Tools in 2026](https://www.firecrawl.dev/blog/best-llm-observability-tools)
- [Braintrust — LangSmith alternatives (2026)](https://www.braintrust.dev/articles/langsmith-alternatives-2026)
- [Langfuse](https://langfuse.com/)（开源 LLM observability）
- [OpenTelemetry — Semantic conventions for generative AI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
