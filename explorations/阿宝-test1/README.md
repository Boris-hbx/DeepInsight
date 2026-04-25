---
title: Agent Harness 的解剖 — 模型外面那层"壳"到底做什么
summary: 把 Claude Code / Cursor / Aider / Codex CLI 这类编码 agent 的运行时拆成 5 个组件，对比、归纳反模式、给 DeepInsight 自己写 harness 时的启示
tags: [insight-report, harness, agent-runtime, mock-demo]
screenshot: screenshot.png
---

# 阿宝-test1 的前期探索 · Agent Harness 洞察报告

> **这是 DeepInsight 应用最终产出形态的 demo**：一个"读完一堆资料 → 输出结构化多模态洞察报告"的样子。
> 内容是真的（关于 agent harness 的实际归纳），数据是 mock 的（对比表里的具体数字偏向示意），不调真 LLM API。

## 思路

DeepInsight 的核心 UX 是：用户丢一堆资料（PDF / 链接 / 博客），出一份 **可读、可导航、有结构、有图表** 的洞察报告。

我用一个我们自己关心的话题 —— "agent harness 是什么、长什么样" —— 去**预演**这份报告应该是什么形态：

- **TL;DR + 目录** 让人 30 秒内决定要不要往下看
- **结构化分节** 每节有定义、表格/图、引用
- **可视化卡片**（雷达图 / 矩阵 / 时间轴）替代纯文字
- **来源面板** 每条结论可追溯到原始资料
- **元数据栏** 输入资料数、生成耗时、置信度（mock）

设计上参考了 Notion AI 的报告导出、Anthropic Engineering 博客的排版、Stripe Docs 的右侧 TOC，但**没有抄具体页面**。

## 怎么本地查看

```bash
cd explorations/阿宝-test1
start index.html       # Windows
open index.html        # macOS
```

单文件 HTML（CSS/JS 内联），双击就能看，无构建依赖。

## 我借鉴了

> 暂无（首位提交，后续同事的探索可在此补充）

## 自检

- [x] `index.html` 存在且能本地打开
- [x] `README.md` frontmatter 已填
- [ ] 截图 `screenshot.png`（可后补，先让 demo 跑起来）
- [x] 没改 `/web` 或其他同事目录

## 变更记录

- 2026-04-25 初始化 + 第一版 harness 洞察报告 demo
