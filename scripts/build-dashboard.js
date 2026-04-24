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
const TASKBOARD_PATH = path.join(ROOT, 'docs', 'task-board.md');
const DASHBOARD_DIR = path.join(ROOT, 'dashboard');
const DIST_DIR = path.join(ROOT, 'dist');

const TEAM = ['阿勇', '阿伟', '阿杰', '阿智', '阿邱', '阿隽', '阿锋', '阿宝'];

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

function readTaskBoard() {
  if (!fs.existsSync(TASKBOARD_PATH)) {
    warn('未找到 docs/task-board.md，任务看板将显示占位');
    return '';
  }
  const raw = fs.readFileSync(TASKBOARD_PATH, 'utf-8');
  log('读取任务看板：' + raw.length + ' 字符');
  return raw;
}

/**
 * 从 docs/task-board.md 解析任务令。
 *
 * 令的形状（见 task-board.md 的「令规」）：
 *   ### T-001 [类型] 简要标题
 *   - **日期**：...
 *   - **发起**：...
 *   - **接令**：@阿伟
 *   - **关联**：...
 *   - **依赖**：...
 *   - **优先级**：P1
 *   - **状态**：🔴 待接令
 *
 *   正文...
 *
 * 每条令属于 "待接令" 或 "已结令" 一级 section；section 以 `## 待接令` / `## 已结令` 标题切分。
 */
function parseTaskBoard(raw) {
  if (!raw) return { tasks: [], byAssignee: {}, stats: emptyStats() };

  // 切分 section：## 待接令 / ## 已结令
  const sections = {};
  const sectionRegex = /^##\s+(待接令|已结令)\s*$/gm;
  const sectionMatches = [...raw.matchAll(sectionRegex)];
  for (let i = 0; i < sectionMatches.length; i++) {
    const m = sectionMatches[i];
    const end = i + 1 < sectionMatches.length ? sectionMatches[i + 1].index : raw.length;
    sections[m[1]] = raw.slice(m.index, end);
  }

  const tasks = [];
  ['待接令', '已结令'].forEach((sectionName) => {
    const body = sections[sectionName];
    if (!body) return;
    const taskRegex = /^###\s+(T-\d+)\s+(?:\[([^\]]+)\]\s*)?(.+?)\s*$/gm;
    const matches = [...body.matchAll(taskRegex)];
    for (let i = 0; i < matches.length; i++) {
      const m = matches[i];
      const start = m.index;
      const end = i + 1 < matches.length ? matches[i + 1].index : body.length;
      const taskBlock = body.slice(start, end);
      const task = parseTaskBlock(taskBlock, m[1], m[2] || '', m[3] || '');
      task.section = sectionName;
      tasks.push(task);
    }
  });

  const byAssignee = groupByAssignee(tasks);
  const stats = computeStats(tasks);
  log('解析任务令：' + tasks.length + ' 条（待接令 ' + stats.open + ' · 进行中 ' + stats.inProgress + ' · 已结 ' + stats.done + '）');
  return { tasks, byAssignee, stats };
}

function parseTaskBlock(block, id, type, title) {
  const field = (name) => {
    const re = new RegExp('^- \\*\\*' + name + '\\*\\*[:：]\\s*(.+)$', 'm');
    const m = block.match(re);
    return m ? m[1].trim() : '';
  };
  const rawAssignee = field('接令');
  const assigneeList = rawAssignee
    .split(/[、,\/\s]+/)
    .map((s) => s.replace(/^@/, '').trim())
    .filter(Boolean);
  return {
    id,
    type,
    title,
    date: field('日期'),
    issuer: field('发起'),
    assigneeRaw: rawAssignee,
    assignees: assigneeList,
    relation: field('关联'),
    dependency: field('依赖'),
    priority: field('优先级'),
    status: field('状态'),
    startedAt: field('接令时间'),
    finishedAt: field('完成时间')
  };
}

function groupByAssignee(tasks) {
  const map = {};
  TEAM.forEach((name) => { map[name] = []; });
  map['@All'] = [];
  map['未分配'] = [];
  tasks.forEach((t) => {
    if (t.assignees.length === 0) {
      map['未分配'].push(t);
      return;
    }
    // 逐个 assignee 展开；@All / All 归到共享桶
    let placed = false;
    t.assignees.forEach((a) => {
      if (a === 'All' || a === '@All' || a === 'all') {
        map['@All'].push(t);
        placed = true;
      } else if (TEAM.includes(a)) {
        map[a].push(t);
        placed = true;
      }
    });
    if (!placed) map['未分配'].push(t);
  });
  return map;
}

function emptyStats() {
  return { total: 0, open: 0, inProgress: 0, done: 0 };
}

function computeStats(tasks) {
  const s = emptyStats();
  s.total = tasks.length;
  tasks.forEach((t) => {
    if (t.status.includes('🟢') || t.section === '已结令') s.done += 1;
    else if (t.status.includes('🟡')) s.inProgress += 1;
    else s.open += 1;
  });
  return s;
}

function renderMarkdown(raw) {
  marked.setOptions({
    breaks: false,
    gfm: true
  });
  return marked.parse(raw || '');
}

function buildData(manualHtml, taskboard) {
  return {
    generatedAt: new Date().toISOString(),
    title: 'DeepInsight 项目运作看板',
    version: 'v1.0',
    repoUrl: 'https://github.com/Boris-hbx/DeepInsight',
    pagesUrl: 'https://boris-hbx.github.io/DeepInsight/',
    manualHtml: manualHtml,
    team: TEAM,
    taskboard: taskboard && taskboard.tasks.length > 0
      ? {
          placeholder: false,
          tasks: taskboard.tasks,
          byAssignee: taskboard.byAssignee,
          stats: taskboard.stats
        }
      : {
          placeholder: true,
          message: '等待 docs/task-board.md 注入首批任务令。本面板将按 8 位同事分卡片显示各自的 T-xxx 令、状态、优先级。'
        },
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
  const taskboardRaw = readTaskBoard();
  const taskboard = parseTaskBoard(taskboardRaw);
  const data = buildData(manualHtml, taskboard);
  prepareDist();
  writeIndexHtml(data);
  copyAssets();
  writeNoJekyll();
  log('✓ 构建完成。本地预览：双击打开 dist/index.html');
  log('  发布到 GitHub Pages：npm run deploy');
}

main();
