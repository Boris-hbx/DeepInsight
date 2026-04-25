# DeepInsight 任务看板

> **唯一任务看板** —— 所有任务在此发布、接令、回写。dashboard 的「任务看板」Tab 是本文件的视图，改 md → `npm run build` 重渲染。
> 项目：DeepInsight（洞察分析应用 · agent 协作沙盒）
> ID 体系：统一 `T-xxx`，全局递增，不分端、不重置
> 最近更新：2026-04-23

---

## 角色名单（8 人）

| 代号 | 关注方向（占位，由本人在 PR 中 claim） |
|---|---|
| **阿勇** | — |
| **阿伟** | — |
| **阿杰** | — |
| **阿智** | — |
| **阿邱** | — |
| **阿隽** | — |
| **阿锋** | — |
| **阿宝** | — |

> DeepInsight 采用「人人端到端」协作模式（见章程 §1.3），**没有中央 PM**。任何人都可以发令，包括对自己发令（"认领"一条任务）。横向规范（reliability/test/SE）通过 skill、spec 模板、CI hook 落地，不当审批网关。

---

## 令规

每条令必须包含以下字段：

```
### T-xxx [类型] 简要标题
- **日期**：YYYY-MM-DD
- **发起**：阿勇 / 阿伟 / 阿杰 / 阿智 / 阿邱 / 阿隽 / 阿锋 / 阿宝 / 无（自认领）
- **接令**：@阿伟 / @All / 未分配
- **关联**：spec/NNN-xxx / ADR-NNNN / 章程 §x.y / 无
- **依赖**：T-xxx / 无（前置令未 🟢 前不要开工）
- **优先级**：P0（阻塞） / P1（正常） / P2（低优）
- **状态**：🔴 待接令 / 🟡 进行中 / 🟢 已完成
- **接令时间**：YYYY-MM-DD（可选）
- **完成时间**：YYYY-MM-DD（可选）

正文：做什么、验收标准、参考材料
```

**类型**：`治理` / `特性` / `spec` / `ADR` / `skill` / `infra` / `研究` / `review`

**状态流转**：
```
🔴 待接令 → 🟡 进行中（接令方自行改）→ 🟢 已完成（PR 合并后改）
```

**规矩**：
- 新令加在「待接令」顶部（最新在前）
- 只改状态，不删除令；完成后整条令挪到「已结令」末尾
- 接令方开工前必须把状态从 🔴 → 🟡，避免两人撞车
- 合并 PR 时 commit message 关联 `T-xxx`，看板可据此回链 git 历史

---

## 待接令

### T-008 [infra] CI 工作流（lint + typecheck + test）
- **日期**：2026-04-23
- **发起**：无（自认领）
- **接令**：@阿宝
- **关联**：章程 §3 轨道 A A3、§4.2 eval 起步
- **依赖**：T-005
- **优先级**：P2
- **状态**：🔴 待接令

建 `.github/workflows/ci.yml`，对 `/web` 跑 `pnpm lint` / `tsc --noEmit` / 单测。预留 eval job 的 stub（后续 T-010 填充）。

---

### T-007 [特性] 第一个垂直切片：PDF → 洞察摘要
- **日期**：2026-04-23
- **发起**：无（自认领）
- **接令**：@阿锋
- **关联**：章程 §3 轨道 A A3、§4.1 Citations API 建议
- **依赖**：T-005、T-006
- **优先级**：P1
- **状态**：🔴 待接令

端到端最薄切片：上传 PDF → 调 Anthropic Citations API → 渲染带引用的摘要。先不做账号、存储、历史；目标是把"spec → build → test → demo" 的流程走一遍。

---

### T-006 [ADR] 首批架构决策（多模态后端、LLM 封装位置、状态管理）
- **日期**：2026-04-23
- **发起**：无（自认领）
- **接令**：@阿隽
- **关联**：章程 §3 轨道 A A2
- **依赖**：T-004
- **优先级**：P1
- **状态**：🔴 待接令

起草 3 份 ADR：
- `0001-multimodal-backend.md`：Citations API vs 自研 PDF 分块
- `0002-llm-wrapper-location.md`：server action / route handler / 独立 service
- `0003-state-management.md`：RSC + Server Actions 下的客户端状态约定

---

### T-005 [infra] `/web` Next.js 脚手架（TS + Tailwind + shadcn/ui）
- **日期**：2026-04-23
- **发起**：无（自认领）
- **接令**：@阿邱
- **关联**：章程 §1.1、§3 轨道 A A2
- **依赖**：T-001
- **优先级**：P1
- **状态**：🔴 待接令

`create-next-app` 起步，TS 严格模式、Tailwind、shadcn/ui 初始化；落 `.eslintrc` / `prettier` / `tsconfig`。`.env.local.example` 列出 `ANTHROPIC_API_KEY`（真实 key 禁止提交，见章程 §5）。

---

### T-004 [治理] ADR-0000 + PR 模板
- **日期**：2026-04-23
- **发起**：无（自认领）
- **接令**：@阿智
- **关联**：章程 §2、§3 轨道 A A1
- **依赖**：无
- **优先级**：P1
- **状态**：🔴 待接令

- `docs/architecture/adr/0000-record-architecture-decisions.md`（采纳 ADR 制度本身）
- `.github/PULL_REQUEST_TEMPLATE.md`：强制关联 spec / ADR / T-xxx、勾选 reliability/test checklist

---

### T-003 [治理] docs/guides/CONTRIBUTING.md
- **日期**：2026-04-23
- **发起**：无（自认领）
- **接令**：@阿杰
- **关联**：章程 §1.2、§1.4、§3 轨道 A A1
- **依赖**：无
- **优先级**：P1
- **状态**：🔴 待接令

分支命名、PR 流程、review 规则、commit trailer（`[human]` / `[pair]` / `[agent]`）、本地 dev 启动步骤、API key 自管要点。

---

### T-002 [治理] docs/specs/TEMPLATE.md（含可靠性/测试 checklist 槽位）
- **日期**：2026-04-23
- **发起**：无（自认领）
- **接令**：@阿伟
- **关联**：章程 §1.3、§3 轨道 A A1
- **依赖**：无
- **优先级**：P1
- **状态**：🔴 待接令

spec 模板，字段：背景、方案、非目标、**可靠性 checklist**（失败面、超时、retry）、**测试 checklist**（unit/integration/eval）、rollout、open questions。产出将被所有后续 spec 继承，是横向影响力的主要杠杆点（章程 §1.3）。

---

### T-001 [治理] README.md + .gitignore
- **日期**：2026-04-23
- **发起**：无（自认领）
- **接令**：@阿勇
- **关联**：章程 §3 轨道 A A1
- **依赖**：无
- **优先级**：P1
- **状态**：🔴 待接令

- `README.md`：项目简介、运作看板链接、快速开始、API key 说明
- `.gitignore`：Node/Next.js + IDE + OS + `dashboard/data.json` + `dist/` + `.env.local`

---

### T-009 [研究] 团队名册 docs/guides/TEAM.md
- **日期**：2026-04-23
- **发起**：无（自认领）
- **接令**：@All
- **关联**：章程 §6 开放问题 4
- **依赖**：无
- **优先级**：P2
- **状态**：🔴 待接令

每人在 PR 中补一行：GitHub 账号、邮箱、关注方向（研发范式 / SE / 系统设计 / 可靠性 / 测试 / 其他）。用于 agent 在 review 时检索"该改动应由谁 review"。

---

### T-010 [特性] evals/ 目录 + 首批 20 条 golden case
- **日期**：2026-04-23
- **发起**：无（自认领）
- **接令**：@阿伟
- **关联**：章程 §4.2、§4.5 建议 2
- **依赖**：T-007
- **优先级**：P2
- **状态**：🔴 待接令

仓库根 `evals/`：20 条 golden（含 3-5 条对抗性 PDF prompt injection 样本）；CI 跑 LLM-as-judge + citation 准确率阈值；结果入 `evals/reports/YYYY-MM-DD.md`。

---

## 已结令

（暂无。合并 T-xxx 相关 PR 后把令从"待接令"整条挪到此处，状态改 🟢，补 `完成时间`。）
