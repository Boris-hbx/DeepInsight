# 对标分析：OpenClaw AI Daily

- **来源**：https://gitcode.com/ninjaer/AI-Daily-report
- **抓取日期**：2026-04-24
- **一句话**：Node.js + SQLite 的 **AI 行业新闻日报自动化系统**，RSS / 博客 / Brave 搜索 / Twitter 四通道采集 → LLM 去重合并 → 中英双语日报输出

## 它在做什么

| 维度 | OpenClaw AI Daily | DeepInsight |
|---|---|---|
| 输入 | 多通道 **持续拉取**（RSS/blog/search/twitter） | 用户 **按需上传**（PDF/论文链接/博客链接） |
| LLM 用途 | 跨源去重、多源合并、分类、摘要、翻译 | 解析、结构化、多模态洞察报告生成 |
| 输出 | Markdown + JSON + HTML + REST API（含中英） | 多模态结构化报告（Web 优先，未来移动） |
| 技术栈 | Node.js + Express + SQLite | Next.js App Router + Anthropic SDK |
| 范式 | 配置驱动定时批处理 | 交互式 on-demand |

不是同类产品，但**工程范式上有明显交集**：都是"多源异构输入 → LLM 多阶段处理 → 结构化输出"。

## 值得借鉴的 7 点

### 1. YAML 驱动的"信源配置" → 映射到我们的"输入模板"
OpenClaw 把 RSS / blog / search keywords / twitter targets 都抽到 `config/*.yaml`，**非开发者也能扩**。
→ DeepInsight 可参考：把"洞察模板"（研究综述 / 竞品扫读 / 会议纪要）抽成 YAML，让非研发同事加新模板不必改代码。**候选 spec**：`spec/阿宝/insight-templates`。

### 2. 三层表结构：raw → items → reports
- `raw_items`：原始爬取数据
- `items`：LLM 处理后的条目（标题/摘要 ~150 字/相关度/时间戳/来源数组）
- `reports`：最终聚合产物
→ DeepInsight 未来加持久化时直接抄这个三层：`raw_input`（上传原件） / `parsed_chunks`（解析 + 分块后的中间态） / `insight_report`（终稿）。中间态独立存，方便回溯 & 重跑。

### 3. RSS-first，LLM-fallback 的成本优化
RSS 能直接拿到结构化数据，就**不调 LLM**；只有 blog 全文提取才回落到 LLM。
→ DeepInsight 应采纳：PDF 若自带完整 TOC/书签、arxiv 抽 abstract 页、GitHub README 这类结构清晰的输入，**跳过 LLM 解析步骤**直接走 deterministic 抽取。在 spec 的「成本 checklist」里明确要求作者说明"为什么必须走 LLM"。

### 4. 多源归并 + 来源保留：`📰 多源报道` + 二级来源链接
跨源识别同一事件、合并后**保留所有来源**作为脚注。
→ DeepInsight 的报告如果未来支持"多篇论文综述同一课题"，这套做法直接可用。Citations API 已在章程 § 4.1 提到，但**「合并后如何保留来源」是它不解决的事**，需要我们自己在报告模板里预留"多源归属"槽位。

### 5. 多阶段 LLM pipeline
collection → dedup → merge → categorize → summarize → translate，每一步是**独立的 prompt + 独立的评估点**。
→ 和 Anthropic 多 agent 范式同构（见 `业界最佳实践/02-多-agent-协作模式.md`）。DeepInsight 的 PDF→报告 pipeline 应显式划分：parse → extract claims → structure → synthesize → render。每步单独 eval，不要一个巨无霸 prompt。

### 6. 三件套输出：Markdown + HTML + REST API
内容和呈现分离。同一份 `items/reports` 喂给不同前端。
→ DeepInsight 报告也要这样设计：**报告数据模型 ≠ 呈现**。未来卡片视图 / PDF 导出 / 移动端都从同一个 schema 渲染。早期就把 `report` 的 JSON schema 定清楚，别让 UI 把 schema 拉歪。

### 7. 中英双语
对中文团队做中英双版输出的参考范例。
→ DeepInsight 虽然 MVP 是中文优先，但**数据模型可以先预留 locale 字段**，避免未来国际化时动刀。成本很低。

## 不适用 / 可跳过的

- **定时批处理架构**：DeepInsight 是交互式，不需要调度器
- **Express + SQLite**：我们已定 Next.js + 未来可能 Supabase/Postgres，不改栈
- **RSS / Twitter 爬取**：输入类型不同
- **Apify 依赖**：外部抓取服务，和我们场景无关

## 行动项（建议）

- [ ] 在 `docs/specs/` 开 `spec/xxx/insight-templates` 讨论 YAML 化输入模板（借鉴 1）
- [ ] 在 Z-4 数据 pipeline 守护人的 ADR 中明确 raw/parsed/report 三层（借鉴 2、5）
- [ ] 在 spec 模板的「成本 checklist」加一条："LLM 是必须的吗？有没有结构化输入可走 deterministic 路径？"（借鉴 3）
- [ ] 在报告数据 schema 里预留 `sources: Source[]` + `locale` 字段（借鉴 4、7）

——以上 4 条动作预计半天量，拆成 4 个 P2 task 排期。
