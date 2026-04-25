# 04 · PDF 与长文档处理

> **来源**：[Anthropic Docs — PDF support](https://platform.claude.com/docs/en/build-with-claude/pdf-support) / [Anthropic Cookbook — pdf_upload_summarization](https://github.com/anthropics/anthropic-cookbook/blob/main/misc/pdf_upload_summarization.ipynb) / [Together AI — Contextual RAG from Anthropic](https://docs.together.ai/docs/how-to-implement-contextual-rag-from-anthropic)
> **抓取日期**：2026-04-24

## Claude 原生 PDF 能力（2025-02 后 GA）

- 三种传入方式：**URL / base64 / Files API**（Files API 推荐，payload 小，支持 `file_id` 复用）
- Claude 内部把每页**同时**栅格化为图 + 抽取文本，多模态处理表格 / 图 / 公式 / 图表
- 最适合：有图表 / 公式 / 表格 / 多栏版式的科研论文和技术白皮书 —— **不要**先 PDF→TXT 再喂，会丢视觉信息

## 为什么对 DeepInsight 有用

DeepInsight 核心输入就是 PDF（论文 / 白皮书 / 行业报告）。选型直接决定：
- 能不能准确引用（citation 落到具体页 / 具体表格）
- 能不能分析图表和公式（如果先转 TXT，图就没了）
- 成本（按页扣 token，长 PDF 费钱）

**默认决策：走 Anthropic 原生 PDF + Files API**。传统 PDF 解析（pdf-parse / unpdf）只在"用户上传的是纯文本 PDF 且没有图表"时当 fallback。

## 上下文爆时的分层策略

Claude 上下文 200k（Opus 4.7 可 1M）。真实报告综述场景常超限 → 需要 map-reduce 或 hierarchical：

```
       ┌────────── 完整 PDF（可能 300+ 页） ──────────┐
       │                                                │
  ┌────┴────┐   ┌──────┐   ┌──────┐   ┌──────┐
  │ section │   │ sec  │   │ sec  │   │ sec  │       ← map: 按 section 并行
  │   1     │   │  2   │   │  3   │   │  ... │
  └────┬────┘   └───┬──┘   └───┬──┘   └───┬──┘
       │            │          │          │
       └────── 每 section 抽 claims + citation ────────┐
                                                        │
                                                        ▼
                                       ┌──── reduce 层 ────┐
                                       │ 合成大纲 + 报告   │
                                       └───────────────────┘
```

### 实操要点

1. **分块优先按**"文档自带结构（章 / 节 / 标题）"**分**，别上来就固定 size chunk。结构化分块召回明显高
2. **Anthropic Contextual Retrieval** 对我们场景有用但不是银弹：给每个 chunk 前置一句"本段所在章节 + 与前后关系"，召回可提升，但**需多一次 LLM 调用**。论文结构清晰时收益不大；技术博客 / 行业报告用户上传可以用
3. **Citation 对齐**：map 阶段每个 claim **必须带 `{page, offset}` 或 section id**，reduce 阶段不允许引无锚点的 claim。这条是 Z-6 Eval 的硬指标
4. **PNG 优于 JPEG**：如需栅格化特定页（比如只处理一页表格），无损渲染保留网格线和一像素 tick —— 对表格提取关键
5. **文档 hash 缓存**：用户反复追问同一份文档，用 hash 做 key 缓存 Files API 的 `file_id` + parse 结果，不要每次重传

## 和我们已有设计的连接

- `docs/stewardship.md` Z-4 覆盖"PDF 解析（pdf-parse/unpdf/Files API 选型）"，**推荐 ADR 结论：Files API 为主**
- 章程 § 4.1 提的 Citations API 搭配本实践：Files API 负责输入侧，Citations API 负责输出侧引证
- 和 `02-多-agent-协作模式.md` 的 map-reduce 同构：subagent 跑 map，lead 跑 reduce

## 常见坑

1. **不要自己先 PDF→TXT 再喂**：丢图 / 丢表 / 丢公式。只有在用户明确"纯文本 PDF"时再降级
2. **大 PDF 整份 base64 塞 messages**：payload 臃肿 + 重复传。改 Files API
3. **草书 / 手写体**：Claude 提示不保证能读。上传时检测并在 UI 明示
4. **按 size 一刀切分块**：切到表格中间 / 切到公式中间，后续引用无从恢复。按结构切

## 行动建议

- [ ] Z-4 守护人：开 ADR `adr-00XX-pdf-input-strategy.md`，结论 = 原生 Files API + 结构化分块
- [ ] Z-4 守护人：出一个最小 `web/lib/pipeline/pdf.ts`，封装 `upload → file_id → cache` 三件套
- [ ] Z-6 守护人：把 "citation 必带 {page/section}" 列入 eval 硬指标
- [ ] spec 模板「测试 checklist」加一条：长文档（> 50 页）样本必测

## 参考

- [Anthropic Docs — PDF support](https://platform.claude.com/docs/en/build-with-claude/pdf-support)
- [Anthropic Cookbook — PDF upload and summarization](https://github.com/anthropics/anthropic-cookbook/blob/main/misc/pdf_upload_summarization.ipynb)
- [Anthropic — Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval)（原文链接，配合上文 Together AI 实现）
- [Weaviate — Chunking strategies for RAG](https://weaviate.io/blog/chunking-strategies-for-rag)
