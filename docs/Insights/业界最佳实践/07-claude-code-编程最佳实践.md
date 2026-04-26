# 07 · Claude Code 编程最佳实践

> **来源**：[Anthropic Docs — Claude Code overview](https://docs.claude.com/en/docs/claude-code/overview) / [Anthropic Engineering — Claude Code: Best practices for agentic coding](https://www.anthropic.com/engineering/claude-code-best-practices) / [anthropics/claude-code（GitHub）](https://github.com/anthropics/claude-code) / [anthropics/skills（参考实现）](https://github.com/anthropics/skills)
> **抓取日期**：2026-04-25

## 是什么

Claude Code 是 Anthropic 官方的 agentic CLI：在终端 / IDE / Web 里跑一个有完整工具集（Read / Edit / Glob / Grep / Bash / Agent / WebFetch / Task...）的 Claude 实例，按"读 → 改 → 验"的循环推进任务。它跟 Copilot 那种"补全式"AI 的本质区别：

- **Agentic**：自己规划、自己执行多步操作，不只是回答
- **可观测、可约束**：所有动作走工具调用 → 可被 hooks 拦截 / 审计
- **项目可定制**：通过 `CLAUDE.md` / `.claude/skills/` / `.claude/agents/` / `settings.json` 把团队约定教给 agent，新人和 agent 共享同一份 onboarding

它是 DeepInsight 的**主要协作介质**：8 人团队 + N 个 agent 的工作流全部经它发生。这篇梳理我们已经做对的、还没做的、和明确要避免的。

## 为什么对 DeepInsight 有用

我们项目里 agent 的数量、调用频率、能动到的代码面都比"传统 AI 辅助"高一个数量级。同样的最佳实践放别人项目是"建议"，放我们这是"基础设施"——因为：

1. 8 人各自有 N 个 agent 会话同时改仓库，**缺约束 = 立刻失控**
2. 探索期默认行为靠的是 agent 自己读 `CLAUDE.md` 后路由到 `explorations/<代号>/`，**没有 agent 配置 = 没有这套机制**
3. 章程 § 4.4 已确立"prompt / skill / agent 走 A/B eval"——但前提是有一套规范的 prompt 资产可以被 eval

## 五条已被业界验证的核心实践

### 实践 1：CLAUDE.md 是 agent 的项目 onboarding

Claude Code 启动时自动加载工作目录下的 `CLAUDE.md` + 用户级 `~/.claude/CLAUDE.md`。它**不是**普通 README——它是写给 agent 看的"先读这个再开工"指令集。Anthropic 自家工程团队把它当作"团队 onboarding doc 给非人类成员"。

**好的 CLAUDE.md 三特征**：

- **可执行约定 ≠ 解释**：写"`web/**` 禁写"而不是"`web` 目录是主应用，请谨慎修改"。后者 agent 会自己加权衡，前者它只会照做。
- **触发场景而非堆全集**：每条规则配上"什么时候该想起这条"。我们 CLAUDE.md 用 4 句话路由到 4 个 skill，就是这个范式。
- **新约定随写随加**：用户重复说同一句修正 ≥ 2 次 → 该进 CLAUDE.md（或更具体的 skill）。

我们当前的 `CLAUDE.md` 整体合格，但有可改进点（见「常见坑」3）。

### 实践 2：Skill = 触发条件 + 工作流

Skill 是"agent 在某类场景下应该走的步骤"。和 CLAUDE.md 的差异：

| | CLAUDE.md | Skill |
|---|---|---|
| 加载时机 | 每次启动 | 触发条件命中时 |
| 长度上限 | 紧凑（< 200 行） | 可详尽（包含示例 / 反模式 / 决策树） |
| 适合放 | 全局红线 + 路由 | 具体工作流 / 决策点 |

**写好 skill 的要点**（参考 `anthropics/skills` 仓库）：

- frontmatter `description` 写得让模型一眼能匹配场景。我们 explore-mode 的 description 列了 6 个触发短语 + "/" 关键词，很标准
- 提供"反模式"小节比只说"应该怎么做"更管用——agent 容易死板套规则，反例能让它有判断力
- 一个 skill 只解决**一个**任务，跨任务的"通用流程"应拆

我们已有 `onboard / explore-mode / preview / ship` 四个支柱 skill，覆盖 80% 日常路径。

### 实践 3：Subagent 隔离 context，按需 spawn

`Agent` 工具开一个独立 context 的 worker。三个真实价值：

- **保护主 context**：研究 / 大量文件搜索的中间产物不污染主对话——只回流结论
- **专精分工**：用 `subagent_type` 选定预设角色（Explore / Plan / 自定义如 code-reviewer）
- **并行化**：独立任务一条消息内多个 Agent 调用 → 真并行

**判断标准**（业界共识）：

- 任务跨 ≥ 3 轮 grep / 读文件才能回答 → spawn Explore
- 任务需要完整设计步骤 → spawn Plan
- 单点查询、目标已知 → 直接用 Read / Grep，不要无脑套 subagent（多此一举且增延迟）

prompt 给 subagent 时**带完整背景**：它看不到主对话历史，"基于上下文继续"这种含糊指令必失败。

### 实践 4：Hooks 是兜底，不是主防线

`settings.json` 里的 PreToolUse / PostToolUse / UserPromptSubmit hooks 在 agent 工具调用前后跑外部脚本——可以否决工具调用、注入提示。

我们已经在用：探索期 `PreToolUse` 拦截 `web/**` 写入。这是**正确用法**：

- agent 已经被 CLAUDE.md 教过别动 `/web`，但万一某次 agent 走神 / 被 prompt 注入 → hook 兜底
- hook 失败不耗 token，比让 agent 跑完才发现快得多

**不要**把 hook 当主要规则源——理由：

- agent 不读 hook 脚本，所以"为什么被拦了"它无法解释给用户。**正确做法**：CLAUDE.md / skill 把规则讲明白，hook 只做强制
- hook 失败信息有限，会让 agent 反复重试同样的错事

### 实践 5：用工具优先级表 / TaskCreate 控制行为

Claude Code 有几条**默认偏好**值得团队加固：

- **能 Edit 不 Write**：精确改动 vs 整文件覆盖，前者更安全可审
- **能 Glob/Grep 不 Bash find/grep**：dedicated 工具有权限和性能优化
- **TaskCreate 提早暴露计划**：≥ 3 步任务先建 task list，让用户看见 agent 的拆解
- **并行无依赖工具调用**：一条消息内多个 tool_use block；不要串行等待

这些都已写进我们 `CLAUDE.md` 「Agent 行为边界」节，但执行情况要看 PR review 时盯一下。

## 我们已经做对的 / 该补的

| 实践 | 现状 | 待办 |
|---|---|---|
| CLAUDE.md 当 onboarding doc | ✅ 已用 4 句路由 + 探索期守则 | — |
| 项目级 skill 体系 | ✅ onboard / explore-mode / preview / ship | 加 `spec-to-tests`（见 03 篇）/ `insight-author`（写本目录的 md 标准化） |
| Subagent 用法 | ⚠ 章程提到但缺示例 | `.claude/agents/` 下补 `code-reviewer` / `spec-linter` |
| Hooks 兜底 | ✅ 探索期 web/ 拦截 | 收敛日后改成"未关联 spec 的 PR push 拦截" |
| Memory 用法 | ⚠ 个人 `~/.claude/memory/` 有但项目层没规范 | 在 `.claude/skills/onboard.md` 补一条"用户偏好记到 user 层而不是 CLAUDE.md" |
| 工具优先级 | ✅ 已写入 CLAUDE.md | review checklist 加"agent 是否用了 Bash 跑 grep / find"自检 |
| Prompt eval | ❌ 章程承诺但未落 | 收敛日后建 `.claude/evals/`，每次改 skill 跑一遍最小 case 集 |

## 怎么落地（短平快 ≤ 1 周）

- [ ] **Z-7（agent 协作守护人）** 在 `.claude/agents/` 下加一个 `insight-author.md` subagent：输入"主题 + 来源链接"，输出 `docs/Insights/<分类>/NN-*.md` 草稿，强制套本目录的六段结构。**收益**：本篇之后再写 8 / 9 / 10 篇时不用每次手抄风格
- [ ] **Z-8（DevEx）** 在 `docs/guides/CONTRIBUTING.md` 的 commit 标签节，把 `Assisted-By` trailer 的写法明确成一行模板，agent 才好统一执行
- [ ] **review checklist 增项**："本 PR 改的 skill / hook / agent，是否在 PR 描述里写了变更前后行为差异？"对应章程 § 4.4 的 A/B eval 起步

## 中期（MVP 收敛后）

- [ ] **建立最小 prompt eval 集**：`.claude/evals/<skill-name>/cases.jsonl` + 一个 `npm run eval-skills` 跑所有改动过的 skill。每个 case 是 `<input prompt, expected behavior>`，借鉴 `anthropics/skills` 仓库的 eval 结构
- [ ] **Subagent 模板化**：每个非平凡子任务先看 `.claude/agents/` 有没有专精 agent，没有就先写 agent 再做事。避免每次都现编 prompt
- [ ] **Memory 分层规范**：项目级事实进 `CLAUDE.md` / `docs/`；用户级偏好进 `~/.claude/memory/`；会话内临时状态用 TaskCreate。明确边界后才能避免 CLAUDE.md 越长越臃肿

## 常见坑

1. **CLAUDE.md 写成"说明书"而不是"指令"**：列了一堆"我们项目用 Next.js、TypeScript、Tailwind..."这些 agent 自己 grep package.json 就知道。**修正**：只写它推不出来的——团队约定、红线、当前阶段特殊规则。
2. **Skill 和 CLAUDE.md 重复**：同一条规则两边都写，更新一边忘另一边。**修正**：CLAUDE.md 只写指针（"探索期守则见 explore-mode skill"），细节在 skill 里。
3. **CLAUDE.md 越加越长**：我们目前 ~110 行还可控，但每次 PR 加几行很快 200+。**修正**：超过一个章节的内容外迁到 `docs/guides/<topic>.md`，CLAUDE.md 留指针。设硬上限：**CLAUDE.md 主体 ≤ 150 行**。
4. **Hook 替代教 agent**：发现 agent 老犯同一个错 → 加 hook 拦掉 → agent 学不到。**修正**：先在 CLAUDE.md / skill 里把"为什么不能"说清楚，hook 做最后兜底。
5. **滥用 subagent**：什么都甩 Agent 工具，结果延迟翻倍 + 多个 subagent 互相不知道对方做了什么。**修正**：单次查询、目标明确 → 直接用 Read / Grep。
6. **不调真 LLM API 的探索期把 mock 写得像真返回**：本身没问题，但容易让人误以为 demo 已经接通。**修正**：mock 数据顶部加注释 `// MOCK — 收敛日后接 web/lib/llm/`，命名变量带 `_MOCK` 后缀。
7. **prompt 改了不留 changelog**：skill / agent 改 prompt 等于改代码逻辑，但因为是 md 容易随手提交。**修正**：改 prompt 类文件的 PR 必须带 before/after 行为对比。

## 行动建议

- [ ] **Z-7 守护人**：本周内出一个 `.claude/agents/insight-author.md`，并用它来生成下一篇 Insight（dogfooding）
- [ ] **Z-8 守护人**：CLAUDE.md 加一行硬上限「主体 ≤ 150 行，超出外迁」
- [ ] **每位同事**：记住一句"看见 agent 反复犯错先想着是不是 CLAUDE.md / skill 没说清楚，最后才是 hook"
- [ ] **章程 § 4.4** 的 prompt eval 在收敛日（2026-05-09）当天起把"改 skill 必跑 eval"列入 PR 模板硬性栏

## 参考

- [Anthropic — Claude Code overview](https://docs.claude.com/en/docs/claude-code/overview)
- [Anthropic Engineering — Claude Code: Best practices for agentic coding](https://www.anthropic.com/engineering/claude-code-best-practices)
- [anthropics/skills](https://github.com/anthropics/skills) —— skill / subagent / eval 的官方参考实现
- 项目内交叉：本目录 02（多 agent 模式）、03（Spec-Driven Development）、06（LLM 可观测性 + Eval）
