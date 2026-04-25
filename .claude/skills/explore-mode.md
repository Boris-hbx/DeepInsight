---
name: explore-mode
description: DeepInsight 探索期工作模式。当用户在探索期内做新 demo、试想法、写实验代码时触发，自动归档到 explorations/<代号>/。触发词：做一个 demo / 试一个想法 / 做个洞察界面 / 我想验证 / 实验一下 / 探索...
---

# 探索期工作模式

当前是 DeepInsight 探索期（2026-04-25 ~ 2026-05-08）。每位同事在 `explorations/<代号>/` 下做自己的洞察 demo。

## 触发条件

用户的任意"做点东西"指令，且当前未指定明确路径。常见信号：

- "做一个 ... demo / 界面 / 原型"
- "试一下用 X 做 Y"
- "我想验证一个想法"
- "搞个静态可视化看看 ..."
- 以及任何在 `web/` 之外、感觉像"实验性"的代码改动

## 执行流程

### 1. 确认代号

```bash
echo $DEEPINSIGHT_HANDLE
```

- **空** → 提示用户跑 `npm run init-explore`，**停止**后续操作
- **有值** → 记下作为当前活动用户（如 `阿勇`）

### 2. 确认目标目录

```bash
ls explorations/$DEEPINSIGHT_HANDLE
```

- **不存在** → 提示用户先跑 `npm run init-explore`，**停止**
- **存在** → 所有新文件、改动**默认**写到该目录内

### 3. 默认行为

| 用户说 | 默认理解 | 默认动作 |
|---|---|---|
| "做一个 PDF 摘要 demo" | 在 `explorations/$HANDLE/` 内做静态 demo | 直接动手 |
| "试一下用 D3 画引文图" | 同上 | 直接动手 |
| "在主应用里加 X" | 在 `/web` 改代码 | **先反问**："是要在你的 exploration 里做，还是真的要进 /web？前者 99% 概率" |
| "改一下阿勇的卡片样式" | 改别人目录 | **拒绝**，建议本地 git fetch 后看代码、不改 |

### 4. 强约束

- ✗ **禁写** `web/**`（PreToolUse hook 也会兜底拦截）
- ✗ **禁写** `explorations/<other>/**`（同事目录只读）
- ✓ 允许写 `explorations/$HANDLE/**`、`docs/**`、`dashboard/**`、`scripts/**`、`.claude/**`、顶层 md
- ⚠ **不调真实 LLM API**：前期纯静态，用 mock 数据。需要"看起来像 LLM 输出"的内容时，写死字符串或 fixture。

### 5. 入口约定

`explorations/$HANDLE/index.html` 必须存在 —— 看板「前期探索」tab 扫这个文件。

如果用户用了 Vite/Next/Astro 等需要构建：
- 让用户自己运行 build
- 把构建产物（含 `index.html`）放到 `explorations/$HANDLE/` 根
- 或者保留 source 在子目录、主目录用一个简单 `index.html` 嵌套指向

### 6. 收尾

完成一个想法后：

1. 更新 `explorations/$HANDLE/README.md`：
   - frontmatter 的 `title` / `summary` / `tags` / `screenshot`
   - 「思路」section 补一段
   - 「我借鉴了」section 列引用过的同事
2. 截图保存到 `screenshot.png`（≤ 200KB；可用 `pngquant` 或 ImageMagick 压）
3. 提示用户：

   ```bash
   git add explorations/$DEEPINSIGHT_HANDLE
   git commit -m "[pair] 阶段性探索：<一句话>"
   git push
   ```

   commit 标签按 `docs/guides/CONTRIBUTING.md` 的规矩；agent 主导时加 `Assisted-By: Claude Opus 4.7 (1M context)` trailer。

## 反模式

- 用户说"做个 demo"时直接在 `/web` 或仓库根写文件 → **错**。永远默认 `explorations/$HANDLE/`
- 看到别的同事代码很好，主动改 → **错**。借鉴写到自己 README，**不改对方文件**
- 调真 Anthropic API → **错**。前期没 key 也不该有 key（同事各自本地 mock）
- 只交付源代码不交付 `index.html` → **错**。看板扫不到 = 同事看不到 = 等于没做

## 收敛日（2026-05-09）

探索期结束后本 skill **不再触发**——届时 `CLAUDE.md` 会更新，移除探索期段落。`explorations/` 目录冻结归档，新代码全在 `/web`。
