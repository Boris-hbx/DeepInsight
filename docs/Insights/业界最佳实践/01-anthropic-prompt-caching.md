# 01 · Anthropic Prompt Caching

> **来源**：[Anthropic Docs — Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) / [Anthropic News — Prompt caching with Claude](https://www.anthropic.com/news/prompt-caching)
> **抓取日期**：2026-04-24

## 是什么

给 prompt 里**稳定不变**的段落打 `cache_control: {type: "ephemeral"}` 标记；命中缓存时 input token 费用降到基准的 **0.1×**，latency 降最多 85%。

缓存作用域：tools → system → messages，**顺序 + 内容完全一致**才命中（100% 字节级相等）。TTL 默认 5 分钟（可显式写 `ttl: "1h"` 用 1 小时档，写入费用相应上升至 2×）。

## 为什么对 DeepInsight 有用

DeepInsight 的典型调用结构是：
```
[长 system prompt：报告风格 + 输出 schema + few-shot]    ← 不变，应 cache
[长 document：用户上传的 PDF/论文]                        ← 每次不同
[短 query：用户的具体问题 / 追问]                          ← 每次不同
```

一次会话里用户常会对同一份文档**反复追问**。不 cache 每次都付全价；cache 上之后追问的增量成本只在"最后一段未缓存内容"。粗估对长文档场景可省 70–90% token。

## 怎么落地

### Z-3 LLM 调用层的默认写法

在 `web/lib/llm/` 封装一个 `callClaude()`，强制把 `system` 和"已上传文档"段标 cache：

```ts
// web/lib/llm/client.ts（示意）
await client.messages.create({
  model: "claude-opus-4-7",
  system: [
    {
      type: "text",
      text: SYSTEM_PROMPT,                       // 含 schema + few-shot
      cache_control: { type: "ephemeral" },      // ← 稳定，cache
    },
  ],
  messages: [
    {
      role: "user",
      content: [
        {
          type: "document",
          source: { type: "base64", media_type: "application/pdf", data: pdfB64 },
          cache_control: { type: "ephemeral" },  // ← 本次会话反复用，cache
        },
        { type: "text", text: userQuery },       // ← 每次不同，不 cache
      ],
    },
  ],
});
```

### 断点放哪

- `tools` 末尾（如果 tools 稳定）
- `system` 末尾
- 已上传文档段末尾
- **不要**在快速变化的内容前加断点（会稀释命中率）

### 监控

- 用 response 里的 `usage.cache_creation_input_tokens` / `usage.cache_read_input_tokens` 分别统计**写**和**读**
- 按 `user_id / feature / prompt_version` 打 tag（和 Z-5 观测 checklist 对齐）
- 命中率 < 50% 触发告警：多半是 system prompt 里混进了动态内容（当前日期 / user_id 串拼进去了），要挪出来

## 常见坑

1. **把 `Date.now()` 或用户 id 拼进 system** → 每次都 miss。所有动态值放到 messages 里
2. **1h TTL 不是万能药**：写入成本 2×，只有确认高频重用才开；一次性调用反而亏
3. **2026-02 起按 workspace 隔离缓存**：多 workspace 的组织要留意命中边界
4. **5 分钟 TTL 是默认**：用户追问间隔若经常 > 5min，要么 extend 到 1h，要么接受 miss 率

## 行动建议

- [ ] Z-3 守护人：在 `web/lib/llm/` 提供统一的 `callClaude()`，**默认**给 system + document 段打 cache
- [ ] Z-5 守护人：把 `cache_read_tokens / cache_write_tokens` 加到观测 dashboard
- [ ] spec 模板「成本 checklist」加一条："prompt 里哪些段标了 cache_control？命中率目标是多少？"

## 参考

- [Anthropic — Prompt caching docs](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [DEV — Claude Prompt Caching in 2026: The 5-Minute TTL Change](https://dev.to/whoffagents/claude-prompt-caching-in-2026-the-5-minute-ttl-change-thats-costing-you-money-4363)
- [Claude Code Camp — How prompt caching actually works in Claude Code](https://www.claudecodecamp.com/p/how-prompt-caching-actually-works-in-claude-code)
