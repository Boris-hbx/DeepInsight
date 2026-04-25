---
name: ship
description: 把当前未提交的改动安全上传到 GitHub。当用户说"帮我把代码上传 / 提交代码 / push / 提个 PR / 把这次改动合上去 / commit and push"等时触发。封装：分析 diff → 选标签 → 起合规分支 → commit → push → 开 PR → （探索期）self-merge。
---

# 自动上传代码

把"想提交"翻译成"分支 + commit + push + PR"，**全程不需要用户记任何 git 命令**。

## 触发词

- "帮我把代码上传"
- "提交一下" / "提交代码"
- "push 一下" / "push 上去"
- "提个 PR" / "开个 PR"
- "保存进度到 GitHub"

## 执行流程（按顺序，每步先报告再执行）

### 步骤 1：盘点现状

```bash
git status --short
git branch --show-current
git diff --stat
```

把结果**简短**汇报给用户：

> 你当前在 `main` 分支，改了 3 个文件（共 +120 −5 行）：
> - explorations/阿勇/index.html (+85 −2)
> - explorations/阿勇/README.md (+30 −0)
> - explorations/阿勇/data.json (+5 −3)
> 我准备做：起 `explore/阿勇/<slug>` 分支 → commit → push → 开 PR → self-merge。OK 吗？

**等用户回 "OK / 嗯 / 继续"**再往下。

### 步骤 2：选分支前缀（按改动路径）

| 改动主要在 | 分支前缀 |
|---|---|
| `explorations/<HANDLE>/` | `explore/<HANDLE>/<slug>` |
| `docs/specs/` | `spec/<HANDLE>/<slug>` |
| `web/` | `feat/<HANDLE>/<slug>`（探索期内 hook 会拦，应该到不了这一步） |
| 修一个 bug | `fix/<HANDLE>/<slug>` |
| `docs/Insights/` / `docs/guides/` / 其他文档 | `docs/<HANDLE>/<slug>` |
| 多个目录混合 | 取**主要**改动的前缀，commit body 里说明 |

`<HANDLE>` 取自 `$DEEPINSIGHT_HANDLE` 环境变量。**不要硬编码代号**。
`<slug>` 从用户最近的对话主题或主要改动文件名生成（kebab-case，3-5 词，纯英文或拼音）。

### 步骤 3：选参与度标签

按本次会话的实际工作分布：

| 情况 | 标签 |
|---|---|
| agent 没写代码，只是用户让 agent 帮忙 commit | `[human]` |
| agent 和用户来回讨论 + agent 写了大部分代码 | `[pair]`（**最常见**） |
| 用户给一个高层目标，agent 全程主导实现 | `[agent]` |

**判断口径**：本次 push 涉及的改动里，有没有 agent 用 Write/Edit 工具写过？
- 没有 → `[human]`
- 有 → `[pair]` 或 `[agent]`（看用户的介入度）

### 步骤 4：起分支

**当前在 main 时绝对禁止直推**：

```bash
git checkout -b <branch>
```

如果 `<branch>` 已存在（比如同一个 slug 提了第二次）：
- `git checkout <branch>` 切过去（不重起）

### 步骤 5：commit

```bash
git add <精确路径>     # 不要 git add -A，避免误带其他改动
git commit -F /tmp/msg
```

`/tmp/msg`（或 Windows 用临时文件）的内容：

```
[<标签>] <一句话主题，≤ 50 字>

<可选：bullet 1>
<可选：bullet 2>

Refs: <spec 路径或 task-board T-xxx>（如有）

Assisted-By: Claude Opus 4.7 (1M context)
```

`Assisted-By:` trailer **仅当**标签是 `[pair]` 或 `[agent]` 时加。`[human]` 不加。

`Refs:` 当且仅当用户提到过具体 spec 编号或 task-board 任务才加。**不要瞎编**。

### 步骤 6：push

```bash
git push -u origin <branch>
```

push 失败（远端有同分支的更新）→ 跑 `git pull --rebase origin <branch>` 再 push。

### 步骤 7：开 PR

优先用 `gh` CLI：

```bash
gh pr create \
  --title "[<标签>] <主题>" \
  --body "$(cat <<'EOF'
## 改动
<bullets>

## 测试方式
<本地怎么看：cd explorations/<HANDLE> && open index.html，等等>

## 关联
- spec：N/A 或 docs/specs/NNN-...
- task-board：N/A 或 T-xxx

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" \
  --base main \
  --head <branch>
```

`gh` 没装 → 输出 PR 创建链接：
```
请到 https://github.com/Boris-hbx/DeepInsight/compare/main...<branch>?expand=1 一键创建 PR。
标题建议：[<标签>] <主题>
```

### 步骤 8：探索期 self-merge

如果改动**全部**在 `explorations/<HANDLE>/`，且仓库 branch protection 不要求 approval（探索期默认）：

```bash
gh pr merge <PR号> --squash --delete-branch
```

**否则**（涉及主仓 / docs / scripts）：
> ✅ PR 已开：\<URL\>。等同事 review + CI 绿后再 merge，**别 self-merge**。

## 边界情况

### 当前在 main 分支
**绝不直推**。先起分支再 push。

### 多个不相关改动堆在一起
询问用户：
> 我看到改动跨了 3 个独立主题（A / B / C）。要 (1) 拆 3 个 commit + 3 个 PR，(2) 合一个 PR 但分 3 个 commit，(3) 全合一起？

默认建议 (2)（分 commit 但一个 PR），保留可读历史 + 减少 PR 数。

### 找不到关联 spec
- 探索期内 + 改动只在 `explorations/<HANDLE>/` → 不强制，PR body 写"explore-only, no spec"
- 其他场景 → 提示用户："这改动应该先开个 spec（`docs/specs/NNN-...`）。要我现在帮你起 spec 草稿吗？"

### CI 失败
不强 merge。报告：
> ⚠ CI 跑失败（\<具体哪步\>）。看一下日志：\<URL\>。修了再跑 ship。

### 用户没装 gh CLI
push 完后给链接让用户网页操作。**不强制装 gh**——探索期内多一步网页点击不致命。

### gh 装了但没登录
```bash
gh auth status || gh auth login
```
登录失败 → 退化到给链接路径。

### commit-msg hook 拦了
hook 会校验标签和 trailer。若 commit 失败：
- 看 stderr 信息修 commit message，**重 commit**
- 不要 `--no-verify` 绕过

### 用户说"我现在不想 push，先 commit 就行"
跳过步骤 6-8，只做 1-5。

## 反模式

- ❌ `git add -A` 后什么都进 commit：可能误带 dist/、node_modules、settings.local.json。永远精确路径
- ❌ 直推 main：禁止
- ❌ `--no-verify` 绕 commit-msg hook：违反约定
- ❌ 编造 `Refs: spec/123-foo`：用户没说过的 spec 不要写
- ❌ 把 8 个不相关改动塞一个 commit：拆开问用户
- ❌ commit message 里写"修复一些问题"：太空，要写具体什么改动 + 为什么

## 完成报告

ship 完成后给用户一个简短总结：

> ✅ 已上传：
> - 分支：`explore/阿勇/pdf-card-demo`
> - PR：https://github.com/.../pull/42
> - 状态：已 self-merged（探索期 OK）
> - 看板会在 30-60 秒内刷新

不啰嗦，让用户能立刻继续手头的事。
