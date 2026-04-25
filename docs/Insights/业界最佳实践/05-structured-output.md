# 05 · Structured Output（结构化输出）

> **来源**：[Anthropic Docs — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) / [Anthropic Cookbook — Extracting structured JSON](https://github.com/anthropics/anthropic-cookbook/blob/main/tool_use/extracting_structured_json.ipynb)
> **抓取日期**：2026-04-24

## 是什么

Claude 现在有两种"强制输出匹配 schema"的官方手段：

1. **JSON output mode**：`output_format` 参数，返回严格匹配 schema 的 JSON 落在 `response.content[0].text`。适合数据抽取 / 报告结构生成
2. **Strict tool use**：工具定义加 `strict: true`，Claude 调用工具时参数**严格**匹配 `input_schema`

两者底层机制一致：**把 JSON schema 编译成语法，在采样阶段限制 token 生成**。不是 prompt "请输出 JSON"这种软约束，是硬约束。

支持模型：Opus 4.7 / 4.6 / 4.5、Sonnet 4.6 / 4.5、Haiku 4.5 等。

## 为什么对 DeepInsight 至关重要

报告生成的**每一步输出都应是结构化数据，不是自由文本**：

- 解析阶段 → `Chunk[]`（含 section_id、page、text、type）
- 抽取阶段 → `Claim[]`（含 text、citation、confidence）
- 综合阶段 → `Report`（含 sections、claims、sources、locale）
- 渲染阶段 → 前端按 `Report` schema 渲染成 UI

没有结构化约束：
- 轻则偶发 JSON 不合法 → 前端崩
- 重则 schema 漂移 → UI 和后端对不上 → 回归
- 更重要：**没 schema 就没 eval**。eval 的基础是能逐字段比对 golden

## 两条路线怎么选

| 场景 | 推荐路线 |
|---|---|
| 最终产出 = 一份结构化报告 | **JSON output mode**（`output_format`） |
| agent 中间调工具做事（搜索 / 读库） | **Strict tool use** |
| 既要工具调用又要结构化产出 | 工具 strict + 最后一步 output_format |

## 怎么落地

### Report schema 先行

在 `web/lib/llm/schemas/` 用 zod（或等价）定义**所有**结构化输出：

```ts
// web/lib/llm/schemas/report.ts（示意）
export const CitationSchema = z.object({
  document_id: z.string(),
  page: z.number().int().positive().optional(),
  section_id: z.string().optional(),
  quote: z.string(),                   // 原文抄录，作为 grounding 证据
});

export const ClaimSchema = z.object({
  text: z.string(),
  confidence: z.enum(["high", "medium", "low"]),
  citations: z.array(CitationSchema).min(1),  // 强制至少 1 条引证
});

export const ReportSchema = z.object({
  locale: z.enum(["zh-CN", "en-US"]),
  title: z.string(),
  sections: z.array(z.object({
    heading: z.string(),
    claims: z.array(ClaimSchema),
  })),
  sources: z.array(z.object({ id: z.string(), type: z.enum(["pdf", "url"]), title: z.string() })),
});
```

zod → JSON schema → 传给 Claude 的 `output_format.schema`。**一个源头，多处使用**（API 约束 + 前端 props 类型 + eval 比对）。

### 必含字段

- **Claim 必带 ≥ 1 条 citation + quote**：这是反幻觉的硬门槛。quote 是原文抄录（非改写），用于 grounding 自动校验
- **confidence 枚举**：模型自报不确定度，下游可视化时标灰
- **locale**：预留国际化

### 监控

- 监 `stop_reason`：出现 `max_tokens` / `refusal` 占比突增 → schema 可能过严或 prompt 有问题
- 监**字段空值率**：比如 `citations` 为空占比 > 0.1% 就告警 → 回溯到模型抄近路绕 grounding

## 反模式

1. **prompt 里写"请输出 JSON"但不开 structured output**：仍会偶发坏 JSON。用硬约束
2. **schema 放得太宽**（用 `string` / `any`）：约束失效。**每个字段都尽量窄**（enum / 整数范围 / 正则）
3. **schema 和前端 props 各写一份**：必漂移。一个源头（zod），前后端共享
4. **allow `additionalProperties: true`**：模型会塞"创造"字段，后续跑 eval 噪声大。默认关掉

## 和其他最佳实践的连接

- `04-pdf-与长文档处理.md` 的 citation 硬要求 ← 在这里落地为 schema `min(1)` 约束
- `06-llm-可观测性与评测.md` 的 eval 可逐字段比对 ← 基于本 schema
- `02-多-agent-协作模式.md` 的 subagent 输出边界 ← 每个 subagent 有独立子 schema

## 行动建议

- [ ] Z-3 守护人：先定 `Report` + `Claim` + `Citation` 三个 schema，放 `web/lib/llm/schemas/`
- [ ] 同步在 `docs/architecture/data-model.md` 落一份人类可读版本
- [ ] MVP 第一个 Claude 调用就必须走 output_format，不走"prompt 求 JSON"

## 参考

- [Anthropic Docs — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic Cookbook — Extracting structured JSON](https://github.com/anthropics/anthropic-cookbook/blob/main/tool_use/extracting_structured_json.ipynb)
- [Thomas Wiegold — Claude API structured output complete guide](https://thomas-wiegold.com/blog/claude-api-structured-output/)
