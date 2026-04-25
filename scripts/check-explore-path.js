#!/usr/bin/env node
/**
 * Claude Code PreToolUse hook · 探索期路径守门
 *
 * 调用时机：agent 调用 Write/Edit/MultiEdit/NotebookEdit 之前
 * 输入：stdin 的 JSON（hook 协议），含 tool_name + tool_input.file_path
 * 输出：
 *   - exit 0 = 允许
 *   - exit 2 = 阻止（stderr 写理由 → 模型会看到，自动改路径）
 *
 * 探索期约束：
 *   ✗ 禁写 web/**                 （主应用未启动）
 *   ✗ 禁写 explorations/<other>/  （不能改别人目录）
 *   ✓ 允许写 explorations/<自己>/、docs/、dashboard/、scripts/、.claude/、顶层 md / 配置
 *   代号读自环境变量 DEEPINSIGHT_HANDLE（由 npm run init-explore 写入 .claude/settings.local.json）
 *
 * 设计原则：宁漏判不误伤。任何意外（解析失败、路径不在仓内）都放行。
 */

const path = require('path');

let raw = '';
process.stdin.setEncoding('utf-8');
process.stdin.on('data', (chunk) => (raw += chunk));
process.stdin.on('end', () => {
  try {
    if (!raw.trim()) return process.exit(0);
    const ev = JSON.parse(raw);
    const input = ev.tool_input || {};
    const filePath = input.file_path || input.path || input.notebook_path || '';
    if (!filePath) return process.exit(0);

    const rel = relativeToRepo(filePath);
    if (rel === null) return process.exit(0); // 仓外文件不管

    const handle = (process.env.DEEPINSIGHT_HANDLE || '').trim();
    const verdict = checkPath(rel, handle);
    if (verdict.allow) return process.exit(0);

    // Block + 给模型解释
    process.stderr.write(verdict.reason + '\n');
    process.exit(2);
  } catch (_) {
    // 任何异常都放行：hook 不应该误伤正常工作流
    process.exit(0);
  }
});

function relativeToRepo(absPath) {
  const root = path.resolve(__dirname, '..');
  const norm = path.resolve(absPath);
  let rel = path.relative(root, norm).split(path.sep).join('/');
  if (rel.startsWith('..') || path.isAbsolute(rel)) return null;
  return rel;
}

function checkPath(rel, handle) {
  // 始终允许的目录前缀（基建、文档、看板、脚本、agent 配置）
  const ALLOW = [
    'docs/', 'dashboard/', 'scripts/', '.claude/', '.github/', 'evals/'
  ];
  for (const p of ALLOW) {
    if (rel.startsWith(p)) return { allow: true };
  }

  // 顶层文件（README、CLAUDE.md、草稿、package.json、.gitignore 等）放行
  if (!rel.includes('/')) return { allow: true };

  // 探索期禁写主应用
  if (rel.startsWith('web/')) {
    return {
      allow: false,
      reason:
        '🚧 探索期约束：禁止修改 /web 主应用代码。\n' +
        '主 /web 在收敛日（2026-05-09）之后才开始动。\n' +
        '请把代码写到 explorations/' + (handle || '<你的代号>') + '/。'
    };
  }

  // 探索期内 explorations/ 只能写自己的目录
  if (rel.startsWith('explorations/')) {
    const parts = rel.split('/');
    const owner = parts[1] || '';

    // 模板和元文件放行
    if (owner === '_template' || owner === 'README.md' || owner.startsWith('_') || owner.startsWith('.')) {
      return { allow: true };
    }

    if (!handle) {
      return {
        allow: false,
        reason:
          '🚧 探索期约束：未设代号，无法判断目标目录归属。\n' +
          '请先在仓库根跑 `npm run init-explore`（会写 .claude/settings.local.json 注入 DEEPINSIGHT_HANDLE）。'
      };
    }
    if (owner === handle) return { allow: true };

    return {
      allow: false,
      reason:
        '🚧 探索期约束：禁止修改其他同事的探索目录。\n' +
        '你的代号：' + handle + '\n' +
        '路径属主：' + owner + '\n' +
        '请把改动写到 explorations/' + handle + '/。借鉴别人代码 OK，但只读不写。'
    };
  }

  // 其他路径默认放行
  return { allow: true };
}
