# CLAUDE.md — DeepInsight 项目指引

> 这是给 Claude Code / agent 的项目级说明。进入本项目先读这个。

## 项目一页纸

**DeepInsight**：洞察分析应用（PDF / 论文链接 / 博客链接 → 多模态结构化报告）。

- 8 人团队，跨领域（研发范式 / SE / 系统设计 / 可靠性 / 测试）
- 双重目标：① 交付真实产品；② 作为多人 + 多 agent 协作方法论的沙盒
- 项目内用户自称 **阿宝**（不是 Boris）；GitHub 账号为 `Boris-hbx`

## 三件必读文件

1. **`项目初始化草稿.md`** —— 所有决策的真源（目录规范、spec 流程、部署策略、开放问题）。改方案先改这里。
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
- AI 辅助时加 trailer：`Assisted-By: <model>`（**不**复用 `Co-Authored-By`，见草稿 § 4.4）。

### Spec 流程
`docs/specs/NNN-*.md` 提案 → 同事 review → `feat/*` 分支实现 → 合 `main` → 在 sync 演示。Spec 模板见 `docs/specs/TEMPLATE.md`。

## Agent 行为边界

1. **最小权限优先**：能 Edit 就不 Write；能 Glob/Grep 就不 Bash `find`/`grep`。
2. **高风险操作人工卡点**：force push、`rm -rf`、push `main`（绕过 PR）、改 git **全局** config —— **先征求同意**。
3. **看板变更必经构建**：改完 md → `npm run build` → `npm run deploy`。**不要**绕过 build 直接 commit `dist/`。
4. **不要伪造数据**：B2 状态面板（切片墙 / Agent 协作度 / ADR / Skill）要等真实 spec/commit 产生后自动填充，**不要 hardcode**。
5. **Skill / subagent 变更** 按 prompt A/B eval 流程（见草稿 § 4.4 `anthropics/skills` 参考）。

## 常用命令

```bash
# 看板开发
npm install
npm run build              # → dist/
npm run deploy             # → gh-pages 分支

# Git 身份确认
git config --local --list | grep user
```

## 有疑问先看

| 疑问 | 去哪看 |
|---|---|
| 目录为什么这样组织？ | 草稿 § 2 |
| 8 人怎么分工？ | 草稿 § 1.3（人人端到端 + 横向规范作者） |
| API key 怎么管？ | 草稿 § 5 |
| 怎么加 ADR？ | 抄 `docs/architecture/adr/0000-record-architecture-decisions.md` |
| 业界最佳实践参考？ | 草稿 § 4 |
| 为什么不部署 `/web`？ | 草稿 § 5（MVP 阶段纯本地） |
