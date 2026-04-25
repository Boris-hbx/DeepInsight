# ADR-0000 · 采纳 ADR（Architecture Decision Records）

- **Status**: Accepted
- **Date**: 2026-04-23
- **Deciders**: DeepInsight 团队
- **Supersedes**: —
- **Superseded-by**: —

## Context

DeepInsight 是 8 人协作项目，前期会在数周内集中产生大量架构 / 技术 / 流程决策。若依赖"口述传统"会导致：

- 新同事（或 agent）拿不到决策的来龙去脉
- 几周后原作者自己也忘了为什么选 A 不选 B
- 被淘汰的方案反复被 rediscovery 再讨论一遍

业界通用解法是 [Architecture Decision Records (ADR)](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)，由 Michael Nygard 提出的轻量 markdown 格式。

## Decision

采纳 ADR，规则如下：

1. **位置**：`docs/architecture/adr/NNNN-<kebab-title>.md`，`NNNN` 为 4 位数字，单调递增，从 `0000` 起
2. **格式**：本文件即模板（Context / Decision / Consequences 三节）
3. **状态机**：`Proposed` → `Accepted` → 可进一步 `Deprecated` 或 `Superseded by NNNN`
4. **粒度**：一个 ADR 记录**一个**架构决策，不要合并
5. **触发条件**（满足任一写 ADR）：
   - 跨模块的技术选型（DB / RPC / 核心框架）
   - 影响长期演进的约定（API 风格、错误处理模式、观测规范）
   - 改变既有 ADR（新 ADR 需 `Supersedes: NNNN` 指向旧的）
6. **ADR ≠ Spec ≠ RFC**（见章程 § 4.3）：
   - **RFC**：回答"要不要做、怎么做"（可选，8 人团队门槛下调）
   - **Spec**：回答"要做什么、怎么验收"（每个特性一个）
   - **ADR**：回答"为什么选了这条路"（单个决策点，短小）

## Consequences

**收益：**
- 新成员 / agent 通过读 `docs/architecture/adr/` 快速理解技术栈的"为什么"
- 淘汰方案有案可查，不反复讨论
- 决策变更可溯源（新 ADR 用 `Supersedes: NNNN` 明示）

**代价：**
- 每个决策多写 10-30 行 markdown
- PR review 需判断"这算不算一个 ADR 时刻"

**降低摩擦：**
- 模板极简（三节够用）
- Agent 可在 review 中主动提示"此处建议写 ADR"

## References

- [Documenting Architecture Decisions — Michael Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- [ADR GitHub org](https://adr.github.io/)
- `项目章程.md` § 4.3
