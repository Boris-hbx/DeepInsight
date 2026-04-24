---
id: NNN
title: <特性标题>
author: <你的名字>
reviewers: []
status: draft          # draft | review | approved | building | done | rejected
created: YYYY-MM-DD
updated: YYYY-MM-DD
related_adrs: []
related_tasks: []
---

# NNN · <特性标题>

> 复制本文件为 `docs/specs/NNN-<short-slug>.md`，NNN 取当前最大 + 1（001 起）。
> 每个章节都要填；不适用写 `N/A` 并附一句理由。

## 1. 问题 / 动机

描述要解决的问题。1-3 段。引用用户诉求 / bug / 业务目标。

## 2. 目标（Goals）

- [ ] 可测量目标 1
- [ ] 可测量目标 2

## 3. 非目标（Non-Goals）

明确**不**做什么，避免 scope creep。

- 不做 X（理由：...）
- 暂不做 Y（推迟到 spec NNN 再做）

## 4. 方案 / 设计

### 4.1 用户视角
流程 / 截图 / 用例。截图放 `docs/assets/screenshots/YYYY-MM-DD-*.png`，引用相对路径。

### 4.2 技术设计
- 涉及模块 / 文件
- 核心数据结构
- 接口 / API
- 依赖（新增、变更、删除）

### 4.3 备选方案
列 2-3 个被淘汰的方案 + 淘汰理由。

## 5. 测试策略 ⚠ 必填

> 以下两个 checklist 由横向 test / reliability 同事维护，新增 spec 时**照抄**。不适用的条目写 `N/A + 原因`，不要默删。

### 5.1 Test checklist
- [ ] 单元测试覆盖核心函数（目标覆盖率：__%）
- [ ] 集成测试覆盖主流程
- [ ] Eval：如涉及 LLM 调用，golden case ≥ 10 条 + 给出 citation 准确率 / hallucination 率指标
- [ ] 对抗性测试：prompt injection / 恶意上传 / 边界输入（≥ 3 条样本）
- [ ] 回归影响：列出可能影响的既有特性 + 对应回归用例

### 5.2 Reliability checklist
- [ ] 故障模式：失败时系统如何行为？用户看到什么错误？
- [ ] 超时 / 重试策略（含退避）
- [ ] 成本 / 限流：token budget、用户速率限制
- [ ] 观测：关键指标打点（含 `user_id` / `feature` / `prompt_version` tag）
- [ ] 错误文案：对外统一，不泄露 provider 原始报错

## 6. 验收标准

从用户视角列可验证条件，每条 ≤ 1 句。

- [ ] 用户能 X
- [ ] 在 Y 情况下显示 Z
- [ ] 性能：P95 < ___ ms

## 7. Agent 参与度（预估）

- 预估主要模式：`[human]` / `[pair]` / `[agent]`
- 会用 subagent 的子任务：
- 是否新增 / 修改 skill：

## 8. 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| ... | 低/中/高 | ... | ... |

## 9. 开放问题

- [ ] 待讨论 1
- [ ] 待讨论 2

---

## Changelog
- YYYY-MM-DD 初稿（<author>）
