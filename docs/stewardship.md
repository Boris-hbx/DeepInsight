# DeepInsight 责任田（守护人制度）

> **双轴 ownership**：主轴是「人人端到端的垂直切片」（章程 §1.3），本文件定义**副轴** —— 每人额外守护一片横向领域。
> 守护人 ≠ PR 审批网关（章程 §1.3 的禁区），守护人 = 该领域的**规范/工具/fixture 作者** + **默认 reviewer** + **问题路由节点**。
> 最近更新：2026-04-23
> 真源：本文件。看板的「责任田」Tab 是视图，改此 md → `npm run build` 重渲染。

---

## 守护人能做什么 / 不能做什么

**能做（杠杆点）：**
- 起草本领域的 `docs/specs/TEMPLATE.md` 检查项槽位、`.claude/skills/` 下的 skill、CI hook、ADR
- 作为本领域 PR 的**默认 reviewer**（他人可以加 reviewer，但守护人被自动 @）
- 作为本领域问题的**路由节点**（"UI 抖动找谁" → 找前端守护人）
- 维护本领域的 fixture / golden case / 参考实现

**不能做（§1.3 禁区）：**
- 审批/否决他人 PR（只能留意见；最终合并权属于 slice owner + 任一其他同事的 review）
- 垄断本领域的实现（slice owner 可以自己写；守护人只在"是否符合规范"层面发表意见）
- 阻塞开工（守护人请假 ≠ 相关 slice 停工）

**冲突兜底**：守护人 vs slice owner 意见不一致 → 走章程 §6 开放问题，团队共识决，不一票否决。

---

## 8 片责任田（初版，分配待认领）

> 分配原则：开工会议上**自由认领**。一人一片为主；体量小的（如 Z-2 移动端二期）可以与另一片搭售。

### Z-1 前端 / Web UX
- **守护人**：待认领
- **覆盖**：shadcn/Tailwind 视觉规范、流式 UX 组件（`stop`/`reload`/`onError`）、a11y、响应式、空状态/加载/错误文案、citation 点击回原文的交互
- **主要杠杆产出**：
  - `docs/guides/ui-conventions.md`：颜色/间距/排版/暗色模式约定
  - `web/components/ui/` 下的共享组件
  - `docs/specs/TEMPLATE.md` 的「UI 交互 checklist」槽位
  - a11y 自测清单（键盘、screen reader、对比度）
- **被 @ 默认 reviewer 触发条件**：PR 改到 `web/app/**` 或 `web/components/**`

### Z-2 移动端（二期预研 → 执行）
- **守护人**：待认领
- **覆盖**：React Native / Expo 可行性研究、Web 组件可迁移性评估；二期启动时接手 mobile 应用本体
- **主要杠杆产出**：
  - ADR：二期技术栈选型（Expo vs 纯 RN vs 原生 + WebView）
  - 可行性 POC：把 Web 端一个小组件迁到 RN 跑通
  - `docs/architecture/mobile-strategy.md`
- **当前阶段**：低频（每月 ~1 次 POC），可与其他责任田兼任
- **被 @ 默认 reviewer 触发条件**：PR 改到 `web/components/**` 的组件抽象层（影响未来可迁移性）

### Z-3 LLM 调用层
- **守护人**：待认领
- **覆盖**：Anthropic SDK 封装、prompt 版本化管理、Citations API 集成、工具调用 loop、多模态（PDF 直传/base64/URL）、长上下文策略（1M token fallback、map-reduce）
- **主要杠杆产出**：
  - `web/lib/llm/` 的抽象层（统一 provider 入口，禁止散落调用）
  - `prompts/` 目录 + 版本号前缀约定
  - ADR：Citations API vs 自研 PDF 分块（章程 §4.1）
  - Model/token 成本基线文档
- **被 @ 默认 reviewer 触发条件**：PR 改到 `web/lib/llm/**` 或 `prompts/**`

### Z-4 数据 pipeline
- **守护人**：待认领
- **覆盖**：PDF 解析（pdf-parse/unpdf/Files API 选型）、URL 抓取（readability + jsdom）、分块策略、citation 对齐、未来的用户数据存储 schema（账号/历史/收藏）
- **主要杠杆产出**：
  - `web/lib/pipeline/` 抽象（输入 → 规范化 → 分块 → 送 LLM）
  - ADR：PDF 解析选型、URL 抓取选型
  - 未来 DB schema 草案（`docs/architecture/data-model.md`）
- **被 @ 默认 reviewer 触发条件**：PR 改到 `web/lib/pipeline/**` 或新增数据模型

### Z-5 运行时保护（可靠性 + 安全 + 成本）
- **守护人**：待认领
- **覆盖**：
  - 可靠性：错误处理、超时、指数退避重试、降级
  - 安全：OWASP LLM01 prompt injection 防御（`<untrusted>` 标签）、PII 脱敏、上传 MIME/magic bytes 校验、API key 管理
  - 观测 & 成本：OpenTelemetry span tag（`user_id` / `feature` / `prompt_version`）、token-based 限流、每用户日预算
- **主要杠杆产出**：
  - `.claude/skills/reliability-review.md`（retry/timeout/错误面 checklist）
  - `.claude/skills/security-review.md`（injection/PII/上传校验）
  - 监控基线 dashboard 或日志查询模板
  - `docs/specs/TEMPLATE.md` 的「可靠性 checklist」「安全 checklist」槽位
- **被 @ 默认 reviewer 触发条件**：PR 涉及外部调用、用户输入、上传、auth

### Z-6 测试 & Eval
- **守护人**：待认领
- **覆盖**：单测/集成测试规范、LLM-as-judge、golden case（含对抗性 prompt injection 样本 3-5 条）、citation 准确率门禁、CI 测试 gate
- **主要杠杆产出**：
  - `evals/` 目录结构 + 20 条首批 golden
  - `docs/specs/TEMPLATE.md` 的「测试 checklist」槽位
  - CI：LLM-as-judge + citation 准确率阈值
  - `evals/reports/YYYY-MM-DD.md` 的结果归档格式
- **被 @ 默认 reviewer 触发条件**：PR 改到 `evals/**`、`**/*.test.ts`、`**/*.spec.ts`、`.github/workflows/**`

### Z-7 Agent 协作基建
- **守护人**：待认领
- **覆盖**：`.claude/skills`、`.claude/agents`、subagent 注册表、skill eval 模式、commit trailer 规范（`[human]`/`[pair]`/`[agent]`）、spec 制度本身的维护
- **主要杠杆产出**：
  - `.claude/skills/` 下的基础 skill（会被其他守护人 fork）
  - `docs/specs/TEMPLATE.md` 主结构（各守护人填自己的 checklist 槽位）
  - subagent 注册表与使用案例库
  - `scripts/analyze-trailers.js`：统计 `[human]/[pair]/[agent]` 比例，喂给看板
- **被 @ 默认 reviewer 触发条件**：PR 改到 `.claude/**`、`docs/specs/TEMPLATE.md`、`.github/PULL_REQUEST_TEMPLATE.md`

### Z-8 DevEx + 运作看板
- **守护人**：待认领
- **覆盖**：dashboard（`dashboard/`、`scripts/build-dashboard.js`）、CI/CD workflow、本地 dev 脚本、git/GitHub hooks、部署、GitHub Pages 配置、贡献者文档
- **主要杠杆产出**：
  - `docs/guides/CONTRIBUTING.md`：分支、PR、review、commit trailer、dev 启动
  - `dashboard/` 本身的迭代
  - `.github/workflows/deploy-dashboard.yml` & 未来的 `ci.yml`
  - 本地一键 dev 脚本（如 `npm run setup`）
- **被 @ 默认 reviewer 触发条件**：PR 改到 `dashboard/**`、`scripts/**`、`.github/**`、`.claude/settings.json`

---

## 认领规则

1. 开工会议上每人**优先挑 1 片**作为主守护；
2. Z-2 移动端当前体量小，可以与另一片搭售（由认领者并带）；
3. 一人只能守护**最多 2 片**；
4. 认领后在本文件对应 Z-N 的「守护人」字段改为代号（如 `阿勇`）；
5. 改后 push → GitHub Actions 自动重部看板 → 8 人即时看到更新。

## 交接

守护人想转让时：
1. 在本文件对应字段改为 `{原守护人} → {新守护人}（交接中）`
2. 新守护人补交接文档（至少一条 spec 或 skill 的贡献）到仓库
3. 完成后改为 `{新守护人}`
4. 发一条 T-xxx `[治理]` 通知全员

## 变更记录

- 2026-04-23 初版：8 片划分完毕，分配待开工会议认领
