# 业界最佳实践（Industry Best Practices）

> 对 DeepInsight 直接可操作的业界最佳实践笔记。每篇解决一个具体的工程决策。
> 不做综述，只摘能落地的结论。

## 目录

| # | 主题 | 一句话 | 主要受益方 |
|---|---|---|---|
| [01](./01-anthropic-prompt-caching.md) | Prompt Caching | 把稳定的长上下文标 `cache_control`，省 90% 成本 | Z-3 LLM 调用层 |
| [02](./02-多-agent-协作模式.md) | Orchestrator-Worker 多 agent | 主 agent 分解任务 + 子 agent 并行，适合长研究类输入 | Z-3 LLM 调用层 / Z-7 Agent 协作 |
| [03](./03-spec-driven-development.md) | Spec-Driven Development | spec-kit 范式，我们的 spec 流程与之一致可加强 | Z-7 Agent 协作 / Z-8 DevEx |
| [04](./04-pdf-与长文档处理.md) | PDF 原生传入 + 分块策略 | Claude 原生 PDF + 分层分块应对长文 | Z-4 数据 pipeline |
| [05](./05-structured-output.md) | Structured Output | `strict: true` 工具调用 / `output_format` 直出 JSON | Z-3 LLM 调用层 |
| [06](./06-llm-可观测性与评测.md) | LLM 可观测性 + Eval 三层 | OTel trace + unit eval + LLM-judge + 生产采样 | Z-5 运行时保护 / Z-6 测试 |
| [07](./07-claude-code-编程最佳实践.md) | Claude Code 编程最佳实践 | CLAUDE.md / skill / subagent / hook 五条核心实践 | Z-7 Agent 协作 / Z-8 DevEx |

## 怎么用

- 做 spec 前扫一眼相关篇，把建议当"默认起点"，不重造
- 守护人（见 `docs/stewardship.md`）定期 review 自己领域对应的篇目，把新实践补进来
- 如果某篇的建议被我们采纳 → 落地成 spec / ADR → 在该篇末尾加"已落地：spec NNN"链接
- 如果发现建议已过时（模型能力提升、API 变更等）→ 标 `deprecated` + 日期 + 新建议

## 不要做的事

- **不要直接把这里的内容当规范**。规范在 `docs/guides/` 和 spec / ADR
- **不要引用未发布的能力**。只摘已 GA / 已上线的东西
- **不要把它当教程**。教程去看原文链接；这里只谈"我们要不要抄、怎么抄"
