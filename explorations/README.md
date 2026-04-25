# 前期探索

> DeepInsight 主 `/web` 启动前的「自由探索期」。每人一片自留地，做自己的洞察 demo，互相参考、不互相干扰。一两周后开**收敛日**，从大家的设计里挑点融入主应用。
> 真源：本目录 + `CLAUDE.md` 的「探索期 Agent 守则」。

## 节奏

- **探索期**：2026-04-25 ~ 2026-05-08（2 周，可延 1 周）
- 每周一次 sync，每人 5 分钟 walkthrough
- **收敛日**：2026-05-09 sync，挑设计点 → 起 ADR → 启动 spec
- 收敛后：本目录不删，进入归档（README 顶部加 `frozen` 标）

## 怎么开始（新人 5 分钟）

```bash
git pull
npm install                 # 看板依赖
npm run init-explore        # 一键：写代号 → 复制模板到 explorations/<代号>/
cd explorations/<你的代号>
open index.html             # macOS, 或 start index.html (Windows)
```

`init-explore` 做了 3 件事：

1. 从 `git config user.email` 反查 `docs/guides/TEAM.md`，自动推断你的代号
2. 写入 `.claude/settings.local.json`（让 agent 知道你是谁，hook 据此判路径）
3. 从 `_template/` 复制起步文件到 `explorations/<代号>/`

## 自由度（前期纯静态）

**不需要 API key，不需要 server，不需要部署**。栈完全自由：

- 纯 HTML/CSS/JS ✓
- D3 / Chart.js / Mermaid 静态可视化 ✓
- Vite / Next / Astro / Vue / Svelte（自己 build，产物放本目录） ✓
- 纯 markdown 渲染的设计稿 ✓

唯一约定：**`explorations/<代号>/index.html` 必须存在**（看板入口）。

## 互相参考

```bash
git pull
cd explorations/阿勇        # 看同事的代码
code .
open index.html
```

**只读**别人的目录。要"借鉴"就在自己 README 的「我借鉴了」section 写一笔，方便沉淀知识流动。

## 看板呈现

看板「前期探索」tab 扫每个 `<代号>/README.md` 的 frontmatter，渲染成 8 张卡片：

```
┌─────────────────────────┐
│ 阿勇 · PDF→引文图谱     │
│ ───────────────────────│
│ [截图缩略]              │
│ 思路：一句话            │
│ tags: D3 · 静态        │
│ cd explorations/阿勇   │
│ && open index.html     │
│ [看代码 ↗]             │
└─────────────────────────┘
```

frontmatter 必填：

```yaml
---
title: <主题>
summary: <一句话思路>
tags: [tag1, tag2]
screenshot: screenshot.png
---
```

push 到 main 后 CI 30-60s 自动刷新。

## 不要做的事

- 改 `/web` 主应用代码（PreToolUse hook 会拦）
- 改其他同事的 `explorations/<other>/`
- 提交大于 200KB 的图片
- 调真 LLM API（前期纯静态，没有 secrets 担忧）

## 收敛日产出

- ≥ 1 份 ADR：「主 `/web` 借鉴了 X 的 Y、Z 的 W、…」
- 1 份 spec：启动主应用第一个垂直切片（参考 `docs/specs/TEMPLATE.md`）
- 本目录所有 README 加 `frozen: 2026-05-09` 字段，进入归档态
