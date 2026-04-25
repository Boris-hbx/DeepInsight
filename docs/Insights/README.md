# Insights —— 外部参考与对标

> 本目录收纳**对 DeepInsight 有借鉴价值**的外部资料：业界最佳实践、相关开源项目对标、论文与工程博客摘要。
> 不是真源，真源在草稿 / spec / ADR。这里是"外面的人在怎么做，我们挑哪些抄"的笔记本。

## 目录

```
docs/Insights/
├── README.md                          # 本文件
├── 对标分析-OpenClaw-AI-Daily.md       # gitcode.com/ninjaer/AI-Daily-report 对标
└── 业界最佳实践/
    ├── README.md                      # 索引
    ├── 01-anthropic-prompt-caching.md
    ├── 02-多-agent-协作模式.md
    ├── 03-spec-driven-development.md
    ├── 04-pdf-与长文档处理.md
    ├── 05-structured-output.md
    └── 06-llm-可观测性与评测.md
```

## 约定

- 每篇独立可读；顶部 200 字内说清**是什么 / 为什么对 DeepInsight 有用 / 怎么落地**
- 引用原文**带链接 + 原文发布日期**；不引别人还没发布的东西
- 只摘对我们项目**直接可操作**的结论，不做综述。综述去看原文
- 如果某条实践被我们采纳并落地成 spec / ADR，在本文件对应条目下加 `→ 已落地：docs/specs/NNN-*.md` 的链接

## 和其他目录的关系

| 目录 | 作用 |
|---|---|
| `docs/specs/` | 我们自己的方案真源（要做什么） |
| `docs/architecture/adr/` | 我们自己的决策记录（为什么这样选） |
| **`docs/Insights/`** | **外部怎么做的（别人这么选，供我们参考）** |
| `docs/guides/` | 我们自己的流程规范 |

Insight → Spec → ADR → 代码。从"别人怎么做"到"我们决定怎么做"到"我们怎么做的"。

## 维护

- 谁读到有价值的新内容，就加进来（commit 标签 `[human]` 或 `[pair]`）
- 每季度回看一次：过时的标 `deprecated`，已落地的补链接，不再参考的删掉
- 篇幅上限：每篇 ≤ 200 行；超了就拆或做删减
