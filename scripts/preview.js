#!/usr/bin/env node
/**
 * 一键本地预览
 *
 * 流程：
 *   1. 跑 npm run build（确保 dist/ 是最新）
 *   2. 跨平台用系统默认浏览器打开 dist/index.html
 *
 * 跨平台细节（Git Bash / cmd / PowerShell / macOS / Linux 都得能跑）：
 *   - Windows：用 spawn('cmd', ['/c', 'start', '', file], { detached: true }) — 解决 Git Bash 下 `start` 不在 PATH 的问题
 *   - macOS：open <file>
 *   - Linux：xdg-open <file>
 *
 * 设计原则：用户说一句"本地预览"就完事，不让 ta 输任何命令、不让 ta 自己点 dist/index.html。
 */

const { spawn, spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const os = require('os');

const ROOT = path.resolve(__dirname, '..');
const DIST_INDEX = path.join(ROOT, 'dist', 'index.html');

main();

function main() {
  // 1. build
  console.log('[preview] 1/2 跑 npm run build ...');
  const buildResult = spawnSync('npm', ['run', 'build'], {
    cwd: ROOT,
    stdio: 'inherit',
    shell: true                              // Windows 上 npm 是 .cmd，需要 shell
  });
  if (buildResult.status !== 0) {
    console.error('[preview] ✗ build 失败，停在这。修了再跑「本地预览」。');
    process.exit(buildResult.status || 1);
  }
  if (!fs.existsSync(DIST_INDEX)) {
    console.error('[preview] ✗ build 完了但找不到 dist/index.html，看上面的 [build] 日志。');
    process.exit(1);
  }

  // 2. 打开浏览器（detached，不阻塞当前进程）
  console.log('[preview] 2/2 用默认浏览器打开 ' + path.relative(ROOT, DIST_INDEX) + ' ...');
  openInBrowser(DIST_INDEX);
  console.log('[preview] ✓ 已打开。改完 md / explorations 后再说一次「本地预览」即可重跑。');
}

function openInBrowser(target) {
  const platform = os.platform();
  let cmd, args;
  if (platform === 'win32') {
    // cmd /c start "" "<file>" —— 第一对引号是 start 的「窗口标题」占位，必须有
    cmd = 'cmd';
    args = ['/c', 'start', '""', target];
  } else if (platform === 'darwin') {
    cmd = 'open';
    args = [target];
  } else {
    cmd = 'xdg-open';
    args = [target];
  }
  try {
    const child = spawn(cmd, args, {
      detached: true,
      stdio: 'ignore'
    });
    child.unref();
  } catch (e) {
    console.error('[preview] ✗ 无法启动浏览器：' + (e && e.message ? e.message : e));
    console.error('[preview]   手动打开：' + target);
    process.exit(1);
  }
}
