#!/usr/bin/env node
/**
 * DeepInsight 看板构建脚本
 *
 * 流程：
 *   1. 读 项目初始化草稿.md
 *   2. marked 渲染为 HTML
 *   3. 组装 data 对象（含占位面板消息）
 *   4. 注入 dashboard/index.html 模板 → dist/index.html
 *   5. 复制 dashboard/assets/* → dist/assets/
 *   6. 写 dist/.nojekyll（阻止 GitHub Pages 用 Jekyll 处理）
 */

const fs = require('fs');
const path = require('path');
const { marked } = require('marked');

const ROOT = path.resolve(__dirname, '..');
const DRAFT_PATH = path.join(ROOT, '项目初始化草稿.md');
const DASHBOARD_DIR = path.join(ROOT, 'dashboard');
const DIST_DIR = path.join(ROOT, 'dist');

const log = (msg) => console.log('[build] ' + msg);
const warn = (msg) => console.warn('[build] ⚠ ' + msg);

function readDraft() {
  if (!fs.existsSync(DRAFT_PATH)) {
    warn('未找到 项目初始化草稿.md，看板将用空运作手册');
    return '';
  }
  const raw = fs.readFileSync(DRAFT_PATH, 'utf-8');
  log('读取草稿：' + raw.length + ' 字符');
  return raw;
}

function renderMarkdown(raw) {
  marked.setOptions({
    breaks: false,
    gfm: true
  });
  return marked.parse(raw || '');
}

function buildData(manualHtml) {
  return {
    generatedAt: new Date().toISOString(),
    title: 'DeepInsight 项目运作看板',
    version: 'v1.0',
    repoUrl: 'https://github.com/Boris-hbx/DeepInsight',
    pagesUrl: 'https://boris-hbx.github.io/DeepInsight/',
    manualHtml: manualHtml,
    sliceWall: {
      placeholder: true,
      message: '等待首批 spec 提交（docs/specs/NNN-*.md）。本面板将自动按负责人分列，显示每人切片的 spec → build → test → demo 状态。'
    },
    agentMetrics: {
      placeholder: true,
      message: '等待首批带 [human] / [pair] / [agent] trailer 的 commit。本面板将展示 agent 协作参与度的时间序列与比例。'
    },
    adrIndex: {
      placeholder: true,
      message: '等待首批 ADR 入仓（docs/architecture/adr/NNNN-*.md）。本面板将按编号列出所有已接纳 / 被取代的决策。'
    },
    skillRegistry: {
      placeholder: true,
      message: '等待 .claude/skills/ 下的 skill 注册。本面板将展示项目级 skill 的版本、作者、eval 分数。'
    }
  };
}

function prepareDist() {
  fs.rmSync(DIST_DIR, { recursive: true, force: true });
  fs.mkdirSync(DIST_DIR, { recursive: true });
  log('清理 dist/ 完成');
}

function writeIndexHtml(data) {
  const tplPath = path.join(DASHBOARD_DIR, 'index.html');
  const tpl = fs.readFileSync(tplPath, 'utf-8');
  // JSON.stringify + escape < 防止 </script> 提前闭合标签
  const jsonStr = JSON.stringify(data).replace(/</g, '\\u003c');
  const out = tpl.replace('/*DATA_PLACEHOLDER*/{}', jsonStr);
  if (out === tpl) {
    throw new Error('模板中未找到 /*DATA_PLACEHOLDER*/{} 占位符，注入失败');
  }
  const outPath = path.join(DIST_DIR, 'index.html');
  fs.writeFileSync(outPath, out);
  log('写入 dist/index.html（模板 ' + tpl.length + ' + 数据 ' + jsonStr.length + ' 字符）');
}

function copyAssets() {
  const src = path.join(DASHBOARD_DIR, 'assets');
  const dst = path.join(DIST_DIR, 'assets');
  fs.mkdirSync(dst, { recursive: true });
  const files = fs.readdirSync(src);
  files.forEach((f) => fs.copyFileSync(path.join(src, f), path.join(dst, f)));
  log('复制 ' + files.length + ' 个资源文件到 dist/assets/');
}

function writeNoJekyll() {
  fs.writeFileSync(path.join(DIST_DIR, '.nojekyll'), '');
  log('写入 dist/.nojekyll');
}

function main() {
  const raw = readDraft();
  const manualHtml = renderMarkdown(raw);
  const data = buildData(manualHtml);
  prepareDist();
  writeIndexHtml(data);
  copyAssets();
  writeNoJekyll();
  log('✓ 构建完成。本地预览：双击打开 dist/index.html');
  log('  发布到 GitHub Pages：npm run deploy');
}

main();
