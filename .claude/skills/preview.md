---
name: preview
description: DeepInsight 看板与 demo 的本地预览。在不动 gh-pages 的前提下，build 出 dist/ 并自动在浏览器里打开。触发词：本地预览 / 我要本地看一下 / 跑下本地版 / 看效果 / 预览看板 / 预览 demo。
---

# 本地预览

把"想本地看一眼"翻译成"build + 自动开浏览器"，**全程用户不输任何命令**。

## 触发词

- "我要本地预览一下" / "本地预览"
- "本地看一下效果" / "看下效果"
- "跑下本地版" / "build 完打开看看"
- "预览看板" / "预览 demo"

不要在用户说"push" / "上传" / "deploy" 时触发 —— 那是 ship 的活。

## 执行流程

### 步骤 1：环境检查

```bash
ls package.json node_modules 2>&1 | head -3
```

- `package.json` 不存在 → 不在仓根，先 `cd` 到 `$CLAUDE_PROJECT_DIR`
- `node_modules` 不存在 → 跑 `npm install`（提示用户："首次本地预览，先装依赖（约 20 秒）"）

### 步骤 2：build

```bash
npm run build
```

失败处理：
- `Cannot find module 'marked'` → `npm install` 后重试
- 其他错误 → 把 stderr 原样贴给用户（**不静默吞**），由用户决定改 md / 改脚本

### 步骤 3：打开浏览器

按平台选命令（Windows 默认）：

```bash
# Windows (Git Bash / cmd / PowerShell)
start "" "dist/index.html"

# macOS
open dist/index.html

# Linux
xdg-open dist/index.html
```

### 步骤 4：一句话回报

> 已打开本地预览（`dist/index.html`）。改完 md / explorations 后再说一次"本地预览"即可重跑 build。要让 7 个同事都看到 → 说"帮我把代码上传"走 ship。

## 反模式

- ✗ **让用户自己跑命令** —— 这个 skill 的 raison d'être 就是不让用户输命令；输命令请走老手的「常用命令」section
- ✗ **触发后顺手 push / deploy** —— 本地预览 ≠ 发布；要发布走 ship
- ✗ **加 watch / dev server** —— 当前 build 几秒，再说一次"本地预览"成本极低；watch 增复杂度，违反"做精不做多"
- ✗ **build 失败时硬塞解决方案** —— 把错误原样给用户，让 ta 决定（避免 agent 越权改代码绕过真问题）

## 与 gh-pages 的关系

| 场景 | 用 preview | 用 ship → CI deploy |
|---|---|---|
| 自己迭代看效果 | ✅ | ❌（太重） |
| 截图截稿 / sync 演示前 | ✅ 看一遍 | ✅ 再 push |
| 7 个同事要看你的 demo | ❌（他们看不到本地） | ✅ |
| 看自己 explorations 的 demo | ✅ 点卡片穿透 | ✅ |

两条路并行，不冲突。
