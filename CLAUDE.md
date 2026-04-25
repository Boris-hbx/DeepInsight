# CLAUDE.md — DeepInsight 项目指引

> 这是给 Claude Code / agent 的项目级说明。进入本项目先读这个。

## 8 人日常协作只用记 4 句话

| 场景 | 跟 agent 说什么 |
|---|---|
| 第一次进项目 | **"我是新人，怎么开始？"** |
| 想做探索 demo | **"我要做一个洞察 demo，主题是 \<X\>"** |
| 想本地看效果 | **"我要本地预览一下"** |
| 想提交代码 | **"帮我把代码上传"** |

不熟 git / GitHub / 命令行的同事**完全不需要记任何命令**。老手仍可命令行操作，几套并行。

支撑 skill：
- `.claude/skills/onboard.md`（首次进项目）
- `.claude/skills/explore-mode.md`（探索期归档）
- `.claude/skills/preview.md`（本地 build + 浏览器打开看板与 demo）
- `.claude/skills/ship.md`（自动起分支 + commit + push + PR）

底层规则在「探索期 Agent 守则」（本文末）和 `docs/guides/CONTRIBUTING.md`。

## 项目一页纸

**DeepInsight**：洞察分析应用（PDF / 论文链接 / 博客链接 → 多模态结构化报告）。

- 8 人团队，跨领域（研发范式 / SE / 系统设计 / 可靠性 / 测试）
- 双重目标：① 交付真实产品；② 作为多人 + 多 agent 协作方法论的沙盒
- 项目内用户自称 **阿宝**（不是 Boris）；GitHub 账号为 `Boris-hbx`

## 三件必读文件

1. **`项目章程.md`** —— 项目元决策的根本记录（"为什么这样设计"）。新约定 → CLAUDE.md / CONTRIBUTING；新架构决策 → ADR；不在章程里加新内容。
2. **`docs/task-board.md`** —— 任务令真源。接令 / 回写状态改这里，然后 `npm run build && npm run deploy`。
3. **`docs/guides/CONTRIBUTING.md`** —— 分支、PR、commit、review 流程。

## 关键约定

### 技术栈
- **应用本体** (`/web`)：Next.js App Router + TypeScript + Tailwind + shadcn/ui + Anthropic TS SDK。**尚未脚手架化**（轨道 A2）。
- **运作看板** (`/dashboard`)：纯 HTML/CSS/JS，markdown 驱动，部署到 `gh-pages` 分支。

### 仓库
- 单 repo，**公开**。`main` 受保护，禁止直推。
- 分支：`feat/<name>/<slug>` / `fix/<name>/<slug>` / `spec/<name>/<slug>`。
- PR 必须关联 `docs/specs/NNN-*.md`。≥ 1 位 review + CI 绿才能合并。

### 目录红线
- `/docs` = **开发文档**（specs / ADR / guides / assets / task-board）。**不是** GitHub Pages 目录。
- `/dist` = **看板构建产物**。gitignored，只推到 `gh-pages` 分支。
- `/web/.env.local` = **每人自己**的 Anthropic API key，严禁提交。

### Commit 规范
- 开头标签：`[human]` / `[pair]` / `[agent]`。
- AI 辅助时加 trailer：`Assisted-By: <model>`（**不**复用 `Co-Authored-By`，见章程 § 4.4）。

### Spec 流程
`docs/specs/NNN-*.md` 提案 → 同事 review → `feat/*` 分支实现 → 合 `main` → 在 sync 演示。Spec 模板见 `docs/specs/TEMPLATE.md`。

## Agent 行为边界

1. **最小权限优先**：能 Edit 就不 Write；能 Glob/Grep 就不 Bash `find`/`grep`。
2. **高风险操作人工卡点**：force push、`rm -rf`、push `main`（绕过 PR）、改 git **全局** config —— **先征求同意**。
3. **看板变更必经构建**：改完 md → `npm run build` → `npm run deploy`。**不要**绕过 build 直接 commit `dist/`。
4. **不要伪造数据**：B2 状态面板（切片墙 / Agent 协作度 / ADR / Skill）要等真实 spec/commit 产生后自动填充，**不要 hardcode**。
5. **Skill / subagent 变更** 按 prompt A/B eval 流程（见章程 § 4.4 `anthropics/skills` 参考）。

## 探索期 Agent 守则（2026-04-25 ~ 2026-05-08）

> 主 `/web` 应用启动前的「自由探索期」。每位同事在 `explorations/<代号>/` 下做自己的洞察 demo。详见 `explorations/README.md`。

### Agent 默认行为

1. **代号取自 `$DEEPINSIGHT_HANDLE`**（由 `npm run init-explore` 写入 `.claude/settings.local.json`）。未设时**先提示用户跑 `npm run init-explore`**，再开工。
2. **模糊指令默认归档到 `explorations/$DEEPINSIGHT_HANDLE/`**：
   - 例："做一个 PDF 摘要 demo" → 默认在自己 explorations 子目录里做，**不**进 `/web`
   - 用户明确说"在主应用里加 X"且当前是探索期 → **先反问**确认意图，99% 概率是要在 exploration 里
3. **`web/**` 禁写**（PreToolUse hook 兜底拦截）；改主应用要等收敛日（2026-05-09）后
4. **`explorations/<other>/` 只读不写**（不能改其他同事目录）；要"借鉴"就写到自己 `README.md` 的「我借鉴了」section
5. **入口约定**：`explorations/$DEEPINSIGHT_HANDLE/index.html` 必须存在（看板「前期探索」tab 扫这个文件）
6. **纯静态、不调真实 LLM API**：用 mock 数据展示思路。前期没 secrets 担忧
7. **触发场景化指引**：见 `.claude/skills/explore-mode.md`（任何"做一个 demo / 试想法"指令都应自动套用）

### 收敛日（2026-05-09）后

本节会被移除，hook 解封 `/web/**`，`explorations/` 进入归档（不删）。

## 常用命令

```bash
# 看板开发
npm install
npm run build              # → dist/
npm run deploy             # → gh-pages 分支

# 探索期初始化（新人 clone 后第一件事）
npm run init-explore       # 写代号 + 复制 explorations/_template 到 explorations/<代号>/

# Git 身份确认
git config --local --list | grep user

# 看自己的代号
echo $DEEPINSIGHT_HANDLE   # bash/zsh
echo %DEEPINSIGHT_HANDLE%  # cmd
$env:DEEPINSIGHT_HANDLE    # PowerShell
```

## 有疑问先看

| 疑问 | 去哪看 |
|---|---|
| 目录为什么这样组织？ | 章程 § 2 |
| 8 人怎么分工？ | 章程 § 1.3（人人端到端 + 横向规范作者） |
| API key 怎么管？ | 章程 § 5 |
| 怎么加 ADR？ | 抄 `docs/architecture/adr/0000-record-architecture-decisions.md` |
| 业界最佳实践参考？ | 章程 § 4 |
| 为什么不部署 `/web`？ | 章程 § 5（MVP 阶段纯本地） |
