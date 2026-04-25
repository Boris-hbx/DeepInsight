# DeepInsight

洞察分析应用 —— 用户上传 PDF、粘贴论文或博客链接，多模态生成结构化洞察报告。

> 8 人跨领域团队（研发范式 / 软件工程 / 系统设计 / 可靠性 / 测试）共同开发，同时将本项目作为 **Claude Code 多人 + 多 agent 协作方法** 的探索沙盒。

## 快速链接

| 资源 | 地址 |
|---|---|
| 运作看板（实时） | https://boris-hbx.github.io/DeepInsight/ |
| 初始化草稿 / 决策说明 | [`项目章程.md`](./项目章程.md) · [HTML 版](./项目章程.html) |
| 任务令板 | [`docs/task-board.md`](./docs/task-board.md) |
| 贡献指南 | [`docs/guides/CONTRIBUTING.md`](./docs/guides/CONTRIBUTING.md) |
| Spec 模板 | [`docs/specs/TEMPLATE.md`](./docs/specs/TEMPLATE.md) |
| ADR 索引 | [`docs/architecture/adr/`](./docs/architecture/adr/) |
| 项目级 Claude 指引 | [`CLAUDE.md`](./CLAUDE.md) |

## 开发

### 运作看板（`/dashboard`）

```bash
npm install
npm run build        # 构建到 dist/
npm run deploy       # 推到 gh-pages 分支（自动发布）
```

本地预览：双击 `dist/index.html`，无需起服务器（数据已内嵌）。

### 应用本体（`/web`）

尚未脚手架化（轨道 A2，见 [章程 § 3](./项目章程.md)）。目标栈：

**Next.js (App Router) + TypeScript + Tailwind CSS + shadcn/ui + Anthropic TS SDK**

## 提交规范（摘）

commit subject 开头加参与度标签：`[human]` / `[pair]` / `[agent]`。
AI 辅助用 `Assisted-By: <model>` trailer，**不**复用 `Co-Authored-By`。

详见 [`docs/guides/CONTRIBUTING.md`](./docs/guides/CONTRIBUTING.md)。
