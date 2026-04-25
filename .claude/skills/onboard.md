---
name: onboard
description: DeepInsight 新人首次进项目的引导。当用户说"我是新人"、"怎么开始"、"first time"、"刚 clone 仓库"、"环境怎么搭"，或 agent 在仓库内首次会话且检测到环境未初始化（DEEPINSIGHT_HANDLE 为空、explorations/<代号>/ 不存在、node_modules/ 不存在）时触发。
---

# 新人首次进项目引导

零命令记忆。agent 检查环境 → 缺什么补什么 → 引导用户进入"做 demo"或"提交"。

## 触发条件

任一即触发：

1. 用户说："我是新人 / 怎么开始 / first time / 刚 clone / 环境怎么搭 / 我什么都没装"
2. agent 在仓库根的首次会话，且环境检查不通过（见步骤 1）

## 执行流程

### 步骤 1：环境健康检查

按顺序跑，逐项报告状态。**不要静默修，每一步先告知用户在做什么**。

```bash
# 1.1 git 身份是否设了
git config user.name
git config user.email
```
- 都为空 → 提示："请先在终端跑：`git config --global user.email '<你的邮箱>'` 和 `git config --global user.name '<你的名字>'`，然后回来。"

```bash
# 1.2 node 装了吗
node -v
```
- 报错或版本 < 20 → 提示："请装 Node.js 20+（https://nodejs.org/），装完回来。"

```bash
# 1.3 看板依赖装了吗
ls node_modules >/dev/null 2>&1 || echo MISSING
```
- 缺 → 跑 `npm install`，告诉用户"在装看板依赖（一次性，30 秒）"。

```bash
# 1.4 代号设了吗
echo "$DEEPINSIGHT_HANDLE"
```
- 空 → 进入步骤 2。

### 步骤 2：跑 init-explore（不直接调脚本，而是手把手走）

不要直接 `npm run init-explore`（脚本是交互式 readline，agent 接不上）。改为**agent 手动模拟其行为**：

1. **推断代号**：
   ```bash
   git config user.email
   ```
   去 `docs/guides/TEAM.md` 表里找匹配的邮箱 / GitHub 用户名 → 拿到代号。
   - 找不到 → 询问用户："你的代号是？（参考表 阿勇/阿伟/阿杰/阿智/阿栋/阿隽/阿锋/阿宝）"

2. **跟用户确认**："我看到你是 \<代号\>，对吗？"
   - 确认后才下一步

3. **写 .claude/settings.local.json**：
   ```json
   {
     "env": {
       "DEEPINSIGHT_HANDLE": "<代号>"
     }
   }
   ```
   如果文件已存在，merge `env.DEEPINSIGHT_HANDLE`，不覆盖其它字段。

4. **创建探索目录**：
   ```bash
   mkdir -p explorations/<代号>
   cp -r explorations/_template/* explorations/<代号>/
   ```
   然后替换 README.md 里的 `{{HANDLE}}` 为代号、`{{DATE}}` 为今天。

5. **配 git hooks 路径**（让 commit-msg hook 生效）：
   ```bash
   git config core.hooksPath scripts/git-hooks
   ```

6. **重启 Claude Code 提示**：写完 settings.local.json 后**必须**告诉用户：
   > "✅ 初始化完成。请**关闭当前 Claude Code 会话再开一个**，让 `$DEEPINSIGHT_HANDLE` 环境变量生效。重开后跟我说『我要做一个 \<X\> 的 demo』。"

### 步骤 3：补 TEAM.md（如果用户的代号在表里没填 GitHub 用户名）

读 `docs/guides/TEAM.md`，看用户那一行是否还是 `_待补_`：
- 是 → 询问用户："要顺手把你的 GitHub 用户名 + 邮箱 + 关注方向填到 TEAM.md 吗？这样下次别人跑 init-explore 时能自动认到你。"
- 已填 → 跳过

填完后**走 ship skill** 提交（避免要求用户记 git 命令）。

## 常见问题

| 用户说 | 怎么回 |
|---|---|
| "我没 GitHub 账号" | 引导去 https://github.com/ 注册，回来后让阿宝把账号加到仓库 collaborators |
| "我装不了 Node" | 提供 nvm 链接（https://github.com/nvm-sh/nvm） / Windows 用 winget 装 |
| "init-explore 报错" | 看 stderr，多半是 git config 没设或 node 版本太低，回到步骤 1 重检 |
| "我代号是什么" | 查 git config user.email → docs/guides/TEAM.md 反查；查不到就问用户希望叫什么 |

## 完成判据

```bash
test -n "$DEEPINSIGHT_HANDLE" && \
test -d "explorations/$DEEPINSIGHT_HANDLE" && \
test -f "explorations/$DEEPINSIGHT_HANDLE/index.html"
```

三条都 true → onboard 完成 → 引导用户："试着说『我要做一个 \<某主题\> 的 demo』"。

## 反模式

- ❌ 直接跑 `npm run init-explore` 然后等：脚本是交互式的，agent 拿不到 prompt 输入
- ❌ 一次性把 7 个文件都改了不告诉用户：每步告知，让用户随时能 pause
- ❌ 写完 settings.local.json 不提醒重启 Claude Code：env 变量不生效，后续 hook 还是认不到代号
- ❌ 对没装 Node 的用户硬塞命令：先确认环境，再 do
