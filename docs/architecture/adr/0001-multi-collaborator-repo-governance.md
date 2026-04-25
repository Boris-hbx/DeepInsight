# ADR-0001 · 8 人代码仓治理框架

- **Status**: Draft
- **Date**: 2026-04-25
- **Deciders**: DeepInsight 团队（待 2026-05-09 收敛日 sync 拍板）
- **Supersedes**: —
- **Superseded-by**: —

> **本 ADR 当前是 Draft，不立即生效。** 它列出 8 人代码仓需要决策的 6 层框架，每层给 2-3 个候选方案 + trade-off，让团队有结构化的讨论起点。
> 收敛日（2026-05-09）会基于探索期 2 周的真实经验，对每层做 `Draft → Accepted` 的逐项推进。届时本文件会拆分或保留，依实际而定。

## Context

DeepInsight 是 8 人协作项目，且没有传统 PM。从探索期到收敛后的主 `/web` 联合开发，会逐步遇到：

- 多人改同一份代码 → 谁优先 / 怎么 review
- 8 人改 `package.json` 撞 lockfile
- commit 纪律不一致 → 难统计 agent 协作度（章程 § 4.4 关心的指标）
- 新同事 onboarding 体验断层（探索期 vs 收敛后）

口述传统会让这些问题"出事时再讨论"，对 8 人无 PM 团队是低效。本 ADR 把决策**框架化** —— 每层提前列候选 + trade-off，碰到时直接拍。

**约束**：
- 同事 git / GitHub 熟练度差异大（参考 `CLAUDE.md`「8 人日常协作只用记 3 句话」）
- 探索期 2 周（2026-04-25 ~ 2026-05-08）；收敛日 2026-05-09
- 现有约定散落在草稿 / `CLAUDE.md` / `CONTRIBUTING.md` / `stewardship.md`，本 ADR 不重写它们，**只补缺口**

## Decision

采纳"6 层治理框架"作为后续讨论结构。每层下设 `已有 / 收敛后挑战 / 候选方案 / 决议时点`。

| 层 | 已有 | 主要缺口 | 决议时点 |
|---|---|---|---|
| L1 物理隔离 | `explorations/<代号>/` + PreToolUse hook | 收敛后 `/web` 内部如何隔离 | 收敛日 |
| L2 分支 / PR | 命名规范 + 强制 PR | reviewer 自动路由 | 探索期末观察后 |
| L3 commit 纪律 | 标签 + Assisted-By + commit-msg hook ✅ | （已闭环） | 已 Accepted |
| L4 依赖管理 | 单 lockfile | `/web ↔ /dashboard` 是否拆 workspace | 主 `/web` 第一次升级时 |
| L5 CI | `deploy-dashboard.yml` | 应用 CI 缺口 + path 拆分 | 主 `/web` 启动时 |
| L6 Onboarding | `npm run init-explore` + onboard skill | 收敛后统一 `npm run init` | 收敛日 |

---

### L1 — 物理隔离

**已有**：
- 探索期：`explorations/<代号>/` 8 人物理隔离 + `scripts/check-explore-path.js` PreToolUse hook 拦截越界
- `web/**` 探索期内禁写

**收敛后挑战**：8 人共同改 `/web` 时如何减少撞车 + 保持模块边界清晰？

**候选**：

| 方案 | 描述 | 适合 |
|---|---|---|
| A. feature-folder | `web/features/pdf-summary/` 自带 UI + lib + 测试 | 8 人按特性切片，撞车最少 |
| B. 按层切 | `web/{app,components,lib,server}` | 复用最多，但 8 人易撞同层 |
| C. 混合 | `web/features/*` + `web/shared/{components,lib}` | 平衡，但 shared 范围易争论 |

**trade-off**：A 撞车少 / 复用难；B 反之；C 中间但需明确 shared 准入门槛。

**建议**：探索期内每人给一份"假如 8 人共同实现 PDF→洞察报告，应该怎么切目录"的素描，收敛日表决 A/B/C。

**当前默认（如果不做选择）**：A 方案——`/web/features/<feature>/`。

---

### L2 — 分支 / PR

**已有**（`CLAUDE.md` + `CONTRIBUTING.md`）：
- 分支：`feat|fix|spec|explore|docs/<代号>/<slug>`
- 强制 PR；探索期 self-merge OK；主 `/web` 改动 ≥ 1 review
- `ship` skill 自动起合规分支

**主要缺口**：
- 8 人 + 多守护人区域 → 谁应当 review 谁的 PR？人脑路由会 miss。

**候选**：

| 方案 | 描述 | 何时上 |
|---|---|---|
| A. 不做（人工 @） | PR 作者凭直觉 @ 同事 | 探索期默认（人少） |
| B. CODEOWNERS | GitHub 原生：按路径自动 @ 守护人 / 区域负责人 | 收敛后主 `/web` 启动 |
| C. CODEOWNERS + Auto-assign Action | 在 B 基础上随机分配 review，避免老 reviewer 过载 | 8 人 PR 频率 > 5/天再考虑 |

**前置条件**：B 需要 `docs/guides/TEAM.md` 填齐（8 人代号 ↔ GitHub 用户名映射） + `docs/stewardship.md` 责任田认领完成。

**建议**：
- 探索期内不做（A）。
- 收敛日同步认领责任田后，B 上线（直接抄 `stewardship.md` 的 Z-1 ~ Z-8 → 路径映射）。

**示意 CODEOWNERS**（待 stewardship 认领后实写）：
```
web/components/**         @<Z-1 守护人>
web/lib/llm/**            @<Z-3 守护人>
web/lib/pipeline/**       @<Z-4 守护人>
.github/workflows/**      @<Z-8 守护人>
.claude/**                @<Z-7 守护人>
docs/architecture/adr/**  @<Z-7 守护人>
```

---

### L3 — commit 纪律 ✅ 已闭环

**已有**：
- 标签：`[human] / [pair] / [agent]`（CLAUDE.md § Commit 规范）
- AI 辅助 trailer：`Assisted-By: <model>`（不复用 `Co-Authored-By`，见章程 § 4.4）
- **强校验**：`scripts/git-hooks/commit-msg`（POSIX sh，跨平台）
- **自动启用**：`npm run init-explore` 配 `core.hooksPath = scripts/git-hooks`

**Status**：本层 `Accepted`，无须收敛日重议。

**未来增量**（不阻塞）：
- 标签 + conventional commits 二维统一（`[pair] feat: ...`）—— 等 release-please / changelog 自动化时再上
- 数据回流：`scripts/analyze-trailers.js` 读 git log 统计 agent 参与度时间序列，喂给看板「Agent 协作度」面板（见 `stewardship.md` Z-7 守护人产出）

---

### L4 — 依赖管理

**已有**：
- 仓根 `package.json`：仅看板用（marked + gh-pages）
- 探索期每人 `explorations/<代号>/package.json`（如有）：自管，互不影响
- 主 `/web` 尚未脚手架化（轨道 A2）

**主要缺口**：收敛后 `/web` + `/dashboard` 共一个 lockfile 时——
- 升 `/web` 的 React 版本会触发 lockfile 全量改写
- 8 人各自改 `/web` 依赖 → 撞 lockfile 高频

**候选**：

| 方案 | 描述 | 代价 |
|---|---|---|
| A. 单 package.json | 看板 + `/web` 共一个 | 简单；撞 lockfile |
| B. 两个独立 package.json（不用 workspace） | `package.json`（看板）+ `web/package.json`（应用） | `cd web && npm i` 单独跑；CI 多一步 |
| C. pnpm workspace | 顶层 `pnpm-workspace.yaml` 管两个子包 | hoist 控制好 → 隔离 + 共享；学习成本 |

**trade-off**：
- A：现在最简，未来痛。
- B：现在多一行 install，未来撞车局部化。
- C：现在配置成本高，未来最稳。

**建议**：主 `/web` 第一次需要装依赖时（T-005 脚手架化）走 B。3 个月后看 `/web` 依赖增长情况再决定要不要升 C。**不要现在上 C**（探索期不需要）。

---

### L5 — CI

**已有**：
- `.github/workflows/deploy-dashboard.yml`：push 到 main 触发，构建 + 推 gh-pages
- 触发 paths 已包含 `docs/Insights/**` / `explorations/**` / `dashboard/**` / `scripts/build-dashboard.js`

**主要缺口**：
- **应用 CI 缺**（`/web` lint / typecheck / 单测 / eval）→ task-board T-008 待领
- 主 `/web` 启动后 PR 频率会上升，单一 workflow 跑全量太慢

**候选**（应用 CI 落地后）：

| 方案 | 描述 |
|---|---|
| A. 单 workflow，全量跑 | 简单；改 docs 也跑测试，浪费 |
| B. 按 path 拆 jobs | `web/**` 触发 lint+test，`docs/**` 不触发 |
| C. 按 path 拆 workflows | 多个 workflow 文件，每个独立 |

**建议**：应用 CI 上线（T-008）直接走 B（一个 workflow 多 job + path-based job filter），不拆多文件。

**eval CI**（章程 § 4.2）：
- T-010 落地 `evals/` + 20 条 golden 后，加 `eval.yml`（PR 改 `web/lib/llm/**` 或 `prompts/**` 触发）
- 阈值：citation 准确率、LLM-judge 主观分

---

### L6 — Onboarding

**已有**：
- `npm run init-explore`：写代号 + 复制模板 + 配 git hooks ✅
- `.claude/skills/onboard.md`：agent 接住 "我是新人" → 全自动 ✅

**收敛后挑战**：探索期玩法和主 `/web` 玩法不同，新人需要重学（探索期：写 explorations；收敛后：写 web/features）。

**候选**：

| 方案 | 描述 |
|---|---|
| A. 两个独立脚本：`init-explore` + `init-dev` | 阶段切换显式 |
| B. 统一 `npm run init` | 自动检测当前 phase（看 `EXPLORE_PHASE` 标志或日期）选不同流程 |
| C. 不要脚本，只靠 onboard skill | agent 全包 |

**trade-off**：
- A 清晰但要让用户记两个命令
- B 自动但 phase 切换日有 corner case
- C 最低门槛但依赖 agent 可用

**建议**：收敛日把 `init-explore` 升级为 B（统一 `npm run init`），onboard skill 也同步更新。**现在不要做**（探索期 init-explore 用得正好）。

---

## Consequences

**收益（Draft 即生效）**：

- 8 人有共同的"治理画布"，遇到问题去查表而非临场争论
- 6 层 + 候选 + trade-off 让收敛日 sync 议程清晰（每层 5 分钟拍板）
- L3 已 Accepted，commit 纪律有硬保障
- 新 ADR（如 `0002-feature-folder-structure.md`）可直接 `Refs: ADR-0001 § L1`

**代价**：

- 文档层有点多：CLAUDE.md / 草稿 / CONTRIBUTING / stewardship / 本 ADR 关系网。**约定**：本 ADR 是"未来方向 + 候选 trade-off"；其它文档是"现在怎么做"。读"现在"看前者，读"为什么/将来"看本文。
- Draft 状态有"流于形式"风险：不在收敛日推进就空转。
  - **缓解**：收敛日 sync 议程**强制**包含本 ADR 的 6 层逐项推进；任何一项不决议就保持 Draft 但记录"为何延后"。

**触发更新**：

- 任一层从 Draft 推到 Accepted → 改 status 字段 + 加 `Changelog`
- 新增第 7 层（如 release / 版本号）→ 在「Decision」表加一行
- 某层结论被新 ADR 取代 → 本文加 `Superseded-by: ADR-NNNN § L?`

## References

- `CLAUDE.md` —— 当前协作约定真源
- `项目章程.md` § 1.3 / § 4 —— 协作模式 + 业界最佳实践
- `docs/guides/CONTRIBUTING.md` —— 分支 / PR / commit 流程
- `docs/stewardship.md` —— 8 片责任田划分（L2 CODEOWNERS 的源头）
- `docs/Insights/业界最佳实践/03-spec-driven-development.md` —— SDD 范式（spec 先行 vs 本 ADR 的"治理框架先行"）
- ADR-0000 —— 采纳 ADR 制度本身

## Changelog

- 2026-04-25 初稿（Draft，6 层 + L3 已 Accepted，其余待收敛日决议）
