# 03 · Spec-Driven Development（SDD）

> **来源**：[GitHub Blog — Spec-driven development with AI](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/) / [github/spec-kit](https://github.com/github/spec-kit) / [Martin Fowler — Exploring Gen AI: SDD tools](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)
> **抓取日期**：2026-04-24

## 是什么

> Spec-Driven Development：**先写 spec，后写代码**。spec 是人与 agent 的共同真源，代码 / 测试 / 文档都从 spec 派生。

GitHub 的 spec-kit 把它工具化：一个 CLI 为 Copilot / Claude Code / Gemini CLI 创建 workspace，内含：
- **constitution**：项目级不可变原则（相当于我们的 CLAUDE.md + 章程 § 核心约定）
- **spec**：每个特性的规格，含行为 / 约束 / 接口 / 需求
- workflow：spec → 评审 → agent 实现 → 测试

思想不新（Amazon 6-pager、Kiro IDE 都是变体），新在"**agent 时代，spec 是人机共享的 interface**"。Agent 不会瞎猜意图，人审 spec 比审 diff 效率高得多。

## 为什么对 DeepInsight 有用

我们**已经在做**（章程 § 确立了"每个 PR 关联一个 spec"的流程）。这篇不是告诉我们"要不要做"，而是对照业界成熟方案查漏补缺。

### 我们已有的对应项

| SDD 要素 | DeepInsight 当前 |
|---|---|
| Constitution | `CLAUDE.md` + `项目章程.md` |
| Spec 模板 | `docs/specs/TEMPLATE.md`（含 9 个必填章节） |
| 评审流程 | `docs/guides/CONTRIBUTING.md` § 3 |
| Agent 输入 | `.claude/skills/` + `.claude/agents/`（Z-7 守护） |
| 决策记录 | `docs/architecture/adr/` |

### 我们可以加强的点

1. **把 constitution 显式化**：目前 CLAUDE.md + 草稿分散了"不可变原则"。**动作**：在 CLAUDE.md 顶部加一个"红线（不可变）"章节，列 5–10 条真的绝不妥协的事（如"API key 严禁提交"、"`main` 禁止直推"、"不伪造数据"）。
2. **Spec 模板加「验收场景」栏**：spec-kit 的 spec 要包含 Given/When/Then 的可执行场景。我们模板的 § 6「验收标准」太抽象，可细化为"场景表"。
3. **Spec → test 的直接派生**：spec-kit 鼓励 agent 从 spec 自动派生单测骨架。我们可以在 `.claude/skills/spec-to-tests.md` 里固化这个流程。
4. **Spec 版本化**：spec 合并后不是冻结，而是跟随实现演进。每次变更加 `## Changelog` 条目（我们模板已有，关键是**强制真写**，不流于形式）。

## 怎么落地（不大改的微调）

### 短平快（本周）
- [ ] 在 `CLAUDE.md` 顶部加 10 行以内的「红线」节选
- [ ] 在 `docs/specs/TEMPLATE.md` § 6 下加「6.1 验收场景（Given/When/Then）」小节

### 中期（MVP 之后）
- [ ] `.claude/skills/spec-to-tests.md`：输入 spec → 产出 test skeleton
- [ ] `.claude/skills/spec-lint.md`：检查 spec 是否每个 checklist 都非 N/A、changelog 是否更新
- [ ] spec 评审阶段增加"agent 自读"步骤：让 agent 列出它从 spec 推出的 3 个不确定点，作者必答

### 不要做
- 不要引入 spec-kit CLI 本身。我们的流程已经比它轻 & 对 Claude Code 更贴，强加 CLI 只会徒增依赖。
- 不要把 spec 变成设计文档大全。保持模板目前的篇幅上限（~2 页）。

## 反模式警示

- **Spec 写得太详细 → 变成"低效的代码"**：描述该做什么，而不是怎么做。怎么做属于实现。
- **Spec 写得太空 → agent 自由发挥**：每个必填栏要真填，"N/A"要带原因一行。
- **Spec 和代码脱节**：合并后代码改了但 spec 没同步。建议：PR 模板加一句"本 PR 对 spec 的影响是？"（即使是 no-op 也要显式写 no-op）

## 参考

- [github/spec-kit](https://github.com/github/spec-kit)
- [GitHub Blog — Spec-driven development with AI](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-with-ai-get-started-with-a-new-open-source-toolkit/)
- [Martin Fowler — Understanding Spec-Driven Development: Kiro, spec-kit, and Tessl](https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html)
- [Microsoft Dev Blog — Diving into Spec-Driven Development with GitHub Spec Kit](https://developer.microsoft.com/blog/spec-driven-development-spec-kit)
