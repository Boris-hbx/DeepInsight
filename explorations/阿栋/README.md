---
title: Skill 最佳实践 · 一份可执行的洞察
summary: 把 .claude/skills 里的 explore-mode / onboard / ship 拆成"触发 · 流程 · 边界"三件套，反推怎么写一个能跑的 Skill
tags: [skill, agent-design, dx, 自指]
screenshot: screenshot.png
---

# 阿栋 的前期探索

## 思路

**核心问题**：怎样写一个 Skill 让 agent 真的会用？

把本仓库 `.claude/skills/` 下三个真实 skill 当样本，对照 Anthropic 公开 `anthropics/skills` 的范式，反向提炼出三条可机械检查的设计原则：

1. **触发要写信号词**——description 是 agent 的路由器，越具体的触发词，越少误命中
2. **流程要可机械执行**——把"步骤 → 默认动作 → 反例"做成表格，agent 不需要 reasoning 也能跑对
3. **边界要符号化**——✓ 允许 / ✗ 禁止 / ⚠ 注意 三个符号比一段话有效一百倍

页面用 mock 打分给三个仓内 skill 做了一次「触发 / 流程 / 边界」雷达对比，目的是展示**未来真实洞察应用的输出长什么样**——给一段输入（三份 skill md），出一份带量化、有引用、能行动的报告。

## 怎么本地查看

```bash
cd explorations/阿栋
open index.html        # macOS
```

## 我借鉴了

- `.claude/skills/explore-mode.md`：表格化的"用户说 / 默认理解 / 默认动作"结构，直接抄过来当 demo 的 schema
- `.claude/skills/onboard.md` / `ship.md`：作为对比样本

## 自检

- [x] `index.html` 存在且能本地打开
- [x] `README.md` frontmatter 已填
- [ ] 截图已放到 `screenshot.png`（≤ 200KB）
- [x] 没改 `/web` 或其他同事目录
- [x] 不调真 LLM API（数据全为基于真实 skill 的人工 mock）

## 变更记录

- 2026-04-25 初始化，落地 v0：单页洞察报告
