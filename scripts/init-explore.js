#!/usr/bin/env node
/**
 * 一键探索期初始化
 *
 * 流程：
 *   1. 读 git config 推断当前用户（与 docs/guides/TEAM.md 对照）
 *   2. 询问/确认代号
 *   3. 写 .claude/settings.local.json（注入 DEEPINSIGHT_HANDLE，hook 据此判路径）
 *   4. 创建 explorations/<代号>/，从 _template/ 复制起步文件
 *   5. 输出下一步指引
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const readline = require('readline');

const ROOT = path.resolve(__dirname, '..');
const TEAM_PATH = path.join(ROOT, 'docs', 'guides', 'TEAM.md');
const TEMPLATE_DIR = path.join(ROOT, 'explorations', '_template');
const SETTINGS_LOCAL = path.join(ROOT, '.claude', 'settings.local.json');
const EXPLORATIONS = path.join(ROOT, 'explorations');

main().catch((e) => {
  console.error('✗ 初始化失败：' + (e && e.message ? e.message : e));
  process.exit(1);
});

async function main() {
  console.log('');
  console.log('🚀 DeepInsight · 探索期初始化');
  console.log('───────────────────────────────────');

  const gitName = safeExec('git config user.name');
  const gitEmail = safeExec('git config user.email');
  if (gitName) console.log('  git user.name  = ' + gitName);
  if (gitEmail) console.log('  git user.email = ' + gitEmail);

  const guess = guessFromTeamMd(gitName, gitEmail);
  if (guess) {
    console.log('  → 从 docs/guides/TEAM.md 推断代号：' + guess);
  } else {
    console.log('  ⚠ TEAM.md 中未找到匹配，需要手动输入代号');
    console.log('    （也可以先去 docs/guides/TEAM.md 里登记自己的 GitHub 用户名/邮箱再回来跑）');
  }
  console.log('');

  const handle = await prompt(
    guess ? '代号 [回车确认 ' + guess + ']: ' : '代号（如 阿勇 / 阿伟 / 阿杰 / 阿智 / 阿栋 / 阿隽 / 阿锋 / 阿宝）: ',
    guess
  );
  if (!handle) {
    console.error('✗ 未输入代号，退出。');
    process.exit(1);
  }

  // 1. 写 settings.local.json
  writeSettingsLocal(handle);
  console.log('✓ 写入 .claude/settings.local.json（DEEPINSIGHT_HANDLE=' + handle + '）');

  // 2. 配 git hooks 路径（让 commit-msg hook 生效）
  const hooksDir = path.join(ROOT, 'scripts', 'git-hooks');
  if (fs.existsSync(hooksDir)) {
    safeExec('git config core.hooksPath scripts/git-hooks');
    // POSIX 系统下确保 hook 可执行（Windows 下无效但不报错）
    try {
      const hookPath = path.join(hooksDir, 'commit-msg');
      if (fs.existsSync(hookPath)) fs.chmodSync(hookPath, 0o755);
    } catch (_) { /* Windows 上 chmod 是 noop */ }
    console.log('✓ 配置 git hooks（core.hooksPath = scripts/git-hooks）');
  }

  // 3. 创建探索目录
  const myDir = path.join(EXPLORATIONS, handle);
  const created = fs.existsSync(myDir);
  if (!created) {
    fs.mkdirSync(myDir, { recursive: true });
    if (fs.existsSync(TEMPLATE_DIR)) {
      copyDir(TEMPLATE_DIR, myDir);
      // README 模板替换占位符
      const readmePath = path.join(myDir, 'README.md');
      if (fs.existsSync(readmePath)) {
        let r = fs.readFileSync(readmePath, 'utf-8');
        r = r.replace(/\{\{HANDLE\}\}/g, handle);
        r = r.replace(/\{\{DATE\}\}/g, new Date().toISOString().slice(0, 10));
        fs.writeFileSync(readmePath, r);
      }
      console.log('✓ 创建 explorations/' + handle + '/（已从 _template 复制起步文件）');
    } else {
      console.log('✓ 创建 explorations/' + handle + '/（_template 不存在，仅创建空目录）');
    }
  } else {
    console.log('• explorations/' + handle + '/ 已存在，跳过模板复制');
  }

  console.log('');
  console.log('🎉 完成！下一步：');
  console.log('  1. cd explorations/' + handle);
  console.log('  2. 编辑 README.md 填写你的「思路」「截图」');
  console.log('  3. 改 index.html 做你的探索（纯静态、用 mock 数据）');
  console.log('  4. 本地预览：');
  console.log('       open index.html      # macOS');
  console.log('       start index.html     # Windows');
  console.log('       xdg-open index.html  # Linux');
  console.log('  5. 看看同事进展：cd ../<其他代号> && open index.html');
  console.log('');
  console.log('看板「前期探索」tab 会在 push 到 main 后由 CI 自动刷新（30-60s）。');
  console.log('');
}

function safeExec(cmd) {
  try {
    return execSync(cmd, { encoding: 'utf-8' }).trim();
  } catch (_) {
    return '';
  }
}

function guessFromTeamMd(gitName, gitEmail) {
  if (!fs.existsSync(TEAM_PATH)) return '';
  const md = fs.readFileSync(TEAM_PATH, 'utf-8');
  const lines = md.split('\n');
  for (const line of lines) {
    // 匹配 markdown 表格行：| 代号 | github 用户名 | 邮箱 | ... |
    const cells = line.split('|').map((c) => c.trim());
    if (cells.length < 4) continue;
    const handle = stripBold(cells[1]);
    const gh = stripBold(cells[2]);
    const email = stripBold(cells[3]);
    if (!handle || handle === '代号' || handle.startsWith('---')) continue;
    if (gitName && gh && gh === gitName) return handle;
    if (gitEmail && email && email === gitEmail) return handle;
  }
  return '';
}

function stripBold(s) {
  return (s || '').replace(/^\*+|\*+$/g, '').trim();
}

function writeSettingsLocal(handle) {
  let cur = {};
  if (fs.existsSync(SETTINGS_LOCAL)) {
    try {
      cur = JSON.parse(fs.readFileSync(SETTINGS_LOCAL, 'utf-8'));
    } catch (_) { /* 解析失败就当空对象 */ }
  }
  cur.env = cur.env || {};
  cur.env.DEEPINSIGHT_HANDLE = handle;
  fs.mkdirSync(path.dirname(SETTINGS_LOCAL), { recursive: true });
  fs.writeFileSync(SETTINGS_LOCAL, JSON.stringify(cur, null, 2) + '\n');
}

function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const e of entries) {
    const s = path.join(src, e.name);
    const d = path.join(dst, e.name);
    if (e.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

function prompt(question, def) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
    rl.question(question, (ans) => {
      rl.close();
      resolve((ans || '').trim() || def || '');
    });
  });
}
