# 贡献指南

> DeepInsight 是 8 人协作项目，既是产品又是方法论沙盒。请遵守以下流程，让同事（和 agent）能顺畅地和你协作。

## 1. 准备

### 1.1 Git 身份

团队每人用自己的 GitHub 账号邮箱提交。本仓库已为 **阿宝** 设置 per-repo config。其他同事在本地各自执行一次：

```bash
cd /path/to/DeepInsight
git config user.name  "<GitHub 用户名>"
git config user.email "<GitHub 账号绑定邮箱>"
```

或设全局（推荐，一次到位）：`git config --global user.email ...`。

### 1.2 Anthropic API Key（仅 `/web` 开发者需要）

去 https://console.anthropic.com 申请个人 API key，放进 `web/.env.local`：

```
ANTHROPIC_API_KEY=sk-ant-...
```

`.env.local` 已在 `.gitignore`。**严禁提交**。当前阶段每人用自己的 key（见章程 § 5）。

## 2. 分支

- `main`：受保护，禁止直推
- 特性：`feat/<你>/<slug>`（如 `feat/阿宝/pdf-summary`）
- 修复：`fix/<你>/<slug>`
- 仅 spec：`spec/<你>/<slug>`（只提 spec、不动代码）

## 3. Spec 流程

**每个 PR 必须关联一个 spec**，位于 `docs/specs/NNN-<slug>.md`。

1. **Proposal**：复制 `docs/specs/TEMPLATE.md` → `docs/specs/NNN-<slug>.md`（NNN = 当前最大 + 1）
2. **Review**：开 PR（`spec/...` 分支），至少 1 人 comment；reliability / test 背景同事补 checklist
3. **Build**：spec approved 后在 `feat/...` 分支实现，PR 正文链回 spec
4. **Test**：按 spec § 5 策略执行
5. **Demo**：合并后团队 sync 演示

## 4. Commit 规范

### 4.1 参与度标签

subject 开头加：

| 标签 | 含义 |
|---|---|
| `[human]` | 纯人工 |
| `[pair]` | 人机协作（主要模式） |
| `[agent]` | agent 主导、你只 review |

示例：`[pair] 实现 PDF 摘要前端（spec/003）`

### 4.2 AI 辅助 trailer

用了 agent 辅助，末尾加：

```
Assisted-By: Claude Opus 4.7 (1M context)
```

**不要**复用 `Co-Authored-By:`（理由：章程 § 4.4）。

## 5. PR 要求

- 标题 ≤ 70 字符，描述写"为什么"而非"是什么"
- 关联一个 spec（`Refs docs/specs/NNN-*.md`）
- ≥ 1 位同事 approve
- CI 绿（CI 就绪前至少本地 lint + typecheck）
- prompt / skill 变更附 A/B eval diff

## 6. 任务令（task-board）

任务令真源在 `docs/task-board.md`，格式：

```markdown
### T-xxx [类型] 标题
- **日期**：YYYY-MM-DD
- **发起**：@someone
- **接令**：@assignee
- **优先级**：P0 | P1 | P2
- **状态**：🔴 待接令 | 🟡 进行中 | 🟢 已完成
```

**接令**：状态改 🟡 + 填"接令时间"，`npm run build && npm run deploy`。
**完成**：状态改 🟢 + 填"完成时间"，把令从"待接令"移到"已结令" section。

## 7. 看板更新

任何人改动草稿 / spec / ADR / task-board 后：

```bash
npm run build     # 本地预览 dist/index.html
npm run deploy    # 推到 gh-pages（30-60 秒线上生效）
```

## 8. 有疑问

- 方案问题 → 在草稿相应章节的 PR 上评论
- 流程问题 → 开 issue 或 sync 提出
- "规范不清晰"本身也是我们要探索的一部分 —— 提出来就是贡献
