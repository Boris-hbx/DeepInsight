<!--
感谢贡献。请填以下清单。
提交人即为"接令人"，对所关联 spec 的验收标准负责。
-->

## 摘要

<!-- 1-3 句：为什么做这个 PR。代码已经告诉 reviewer"做了什么"；你要说清楚"为什么"。 -->

## 关联

- Spec：`docs/specs/NNN-<slug>.md`
- Task 令：`T-xxx`（如有）
- 相关 ADR：`docs/architecture/adr/NNNN-*.md`（如有）

## 参与度

<!-- 选一个，决定 commit 的 [tag]。 -->

- [ ] `[human]` 纯人工
- [ ] `[pair]` 人机协作（主要模式）
- [ ] `[agent]` agent 主导、我只 review

## 自检清单

### 代码
- [ ] 本地跑通相关命令（build / dev / test）
- [ ] Lint 与 typecheck 通过
- [ ] 新增 / 变更的函数、组件有测试

### Spec 验收
- [ ] Spec § 5 测试策略 已执行
- [ ] Spec § 5.1 test checklist 勾完（N/A 必附理由）
- [ ] Spec § 5.2 reliability checklist 勾完（N/A 必附理由）
- [ ] Spec § 6 验收标准 全部满足

### Agent 相关（如有）
- [ ] 若变更 prompt / skill，附了 A/B eval diff
- [ ] 新增 / 修改 skill 或 subagent，更新 `.claude/` 对应文件（含 SKILL.md frontmatter）
- [ ] commit 末尾有 `Assisted-By:` trailer（**不**用 `Co-Authored-By`）

### 边界
- [ ] 没有提交 `.env*` 或任何 API key / 密钥
- [ ] 没有动 `dist/` 等 gitignored 产物
- [ ] 没有绕过 CI / review 合并

## 演示 / 截图

<!-- UI 改动请附 screenshot。放 docs/assets/screenshots/YYYY-MM-DD-desc.png。 -->

## Reviewer 指引

<!-- 告诉 reviewer 看哪、怎么验证。 -->
