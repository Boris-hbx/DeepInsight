#!/usr/bin/env node
/**
 * DeepInsight 看板构建脚本
 *
 * 流程：
 *   1. 读 项目章程.md
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
const DRAFT_PATH = path.join(ROOT, '项目章程.md');
const TASKBOARD_PATH = path.join(ROOT, 'docs', 'task-board.md');
const STEWARDSHIP_PATH = path.join(ROOT, 'docs', 'stewardship.md');
const INSIGHTS_DIR = path.join(ROOT, 'docs', 'Insights');
const EXPLORATIONS_DIR = path.join(ROOT, 'explorations');
const ADR_DIR = path.join(ROOT, 'docs', 'architecture', 'adr');
const SKILLS_DIR = path.join(ROOT, '.claude', 'skills');
const DASHBOARD_DIR = path.join(ROOT, 'dashboard');
const DIST_DIR = path.join(ROOT, 'dist');
const SCREENSHOT_MAX_BYTES = 200 * 1024;                  // 200KB 上限，超了 warn 但不 block

const REPO_BLOB_BASE = 'https://github.com/Boris-hbx/DeepInsight/blob/main/';

const TEAM = ['阿勇', '阿伟', '阿杰', '阿智', '阿邱', '阿隽', '阿锋', '阿宝'];

const log = (msg) => console.log('[build] ' + msg);
const warn = (msg) => console.warn('[build] ⚠ ' + msg);

function readDraft() {
  if (!fs.existsSync(DRAFT_PATH)) {
    warn('未找到 项目章程.md，看板将用空运作手册');
    return '';
  }
  const raw = fs.readFileSync(DRAFT_PATH, 'utf-8');
  log('读取章程：' + raw.length + ' 字符');
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

function readStewardship() {
  if (!fs.existsSync(STEWARDSHIP_PATH)) {
    warn('未找到 docs/stewardship.md，责任田将显示占位');
    return '';
  }
  const raw = fs.readFileSync(STEWARDSHIP_PATH, 'utf-8');
  log('读取责任田：' + raw.length + ' 字符');
  return raw;
}

/**
 * 从 docs/stewardship.md 解析 8 片责任田。
 * 每片形状：
 *   ### Z-N 领域名称
 *   - **守护人**：待认领 / 代号
 *   - **覆盖**：单行描述
 *   - **主要杠杆产出**：
 *     - 产出 1
 *     - 产出 2
 *   - **被 @ 默认 reviewer 触发条件**：...
 *
 * 解析策略：按 `### Z-N` 切块，每块抽取「守护人」「覆盖」，以及「主要杠杆产出」下的二级列表。
 */
function parseStewardship(raw) {
  if (!raw) return { zones: [], stats: { total: 0, claimed: 0, open: 0 } };

  const zoneRegex = /^###\s+(Z-\d+)\s+(.+?)\s*$/gm;
  const matches = [...raw.matchAll(zoneRegex)];
  const zones = [];
  for (let i = 0; i < matches.length; i++) {
    const m = matches[i];
    const start = m.index;
    const end = i + 1 < matches.length ? matches[i + 1].index : raw.length;
    const block = raw.slice(start, end);
    zones.push(parseZoneBlock(block, m[1], m[2]));
  }

  const stats = {
    total: zones.length,
    claimed: zones.filter((z) => z.claimed).length,
    open: zones.filter((z) => !z.claimed).length
  };
  log('解析责任田：' + zones.length + ' 片（已认领 ' + stats.claimed + ' · 待认领 ' + stats.open + '）');
  return { zones, stats };
}

function parseZoneBlock(block, id, name) {
  const field = (label) => {
    const re = new RegExp('^- \\*\\*' + label + '\\*\\*[:：]\\s*(.+)$', 'm');
    const m = block.match(re);
    return m ? m[1].trim() : '';
  };

  // 抽「主要杠杆产出」下的二级列表。定位到该字段所在行，往下读缩进的 `  - ...` 直到遇到非缩进行。
  const leverageLines = [];
  const lines = block.split(/\r?\n/);
  let inLeverage = false;
  for (const line of lines) {
    if (/^- \*\*主要杠杆产出\*\*[:：]/.test(line)) {
      inLeverage = true;
      continue;
    }
    if (inLeverage) {
      // 二级列表项：`  - ` 开头
      const subMatch = line.match(/^\s{2,}-\s+(.+)$/);
      if (subMatch) {
        leverageLines.push(subMatch[1].trim());
      } else if (line.startsWith('- ') || line.startsWith('### ') || line.startsWith('## ')) {
        // 进入了下一个字段 / 下一个 zone，停
        break;
      } else if (line.trim() === '') {
        // 空行先跳过，可能列表继续
        continue;
      }
    }
  }

  const guardian = field('守护人');
  return {
    id,
    name,
    guardian,
    claimed: guardian !== '' && guardian !== '待认领',
    coverage: field('覆盖'),
    leverage: leverageLines,
    trigger: field('被 @ 默认 reviewer 触发条件'),
    stage: field('当前阶段')
  };
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

/**
 * 递归扫描 docs/Insights/ 下所有 .md，返回按分类分组的文档清单。
 *
 * 分组策略：
 *   - 顶级子目录作为 category（如「业界最佳实践」）
 *   - Insights/ 根层的 md 归到「项目对标」category
 *   - 每个分类的 README.md 作为该分类的简介（不单列，但附在分类上）
 *
 * 每篇文档提取：
 *   - path        相对 docs/Insights 的 POSIX 路径（用于 GitHub 链接）
 *   - slug        去 .md 的 kebab 形式（URL hash 用）
 *   - title       首个 `# ` header；缺省用文件名
 *   - summary     首段非 blockquote/非代码块文本，≤ 160 字
 *   - html        marked 渲染后的 HTML
 *   - order       文件名首部数字（01-xxx.md → 1），否则 Infinity
 *   - updatedAt   文件 mtime（ISO）
 */
function readInsights() {
  if (!fs.existsSync(INSIGHTS_DIR)) {
    warn('未找到 docs/Insights/，业界参考面板将显示占位');
    return { placeholder: true, categories: [], totalDocs: 0 };
  }

  const files = walkMarkdown(INSIGHTS_DIR);
  if (files.length === 0) {
    warn('docs/Insights/ 下无 .md，业界参考面板将显示占位');
    return { placeholder: true, categories: [], totalDocs: 0 };
  }

  // 以分类为键聚合
  const catMap = new Map();
  const getOrCreateCategory = (key, label) => {
    if (!catMap.has(key)) {
      catMap.set(key, { key, label, readme: null, docs: [] });
    }
    return catMap.get(key);
  };

  files.forEach((absPath) => {
    const relFromInsights = path.relative(INSIGHTS_DIR, absPath).split(path.sep).join('/');
    const parts = relFromInsights.split('/');
    const fileName = parts[parts.length - 1];

    // 跳过 Insights/README.md（它是目录的 README，不进任何分类列表，但单独渲染成「欢迎页」）
    const isInsightsRootReadme = parts.length === 1 && fileName.toLowerCase() === 'readme.md';

    const raw = fs.readFileSync(absPath, 'utf-8');
    const doc = parseInsight(raw, relFromInsights, absPath);

    if (isInsightsRootReadme) {
      // 暂存为整体 welcome，下方统一挂到结果上
      catMap.set('__welcome__', { welcome: doc });
      return;
    }

    // 分类键：顶级目录；若在根层，归「项目对标」
    let categoryKey, categoryLabel;
    if (parts.length === 1) {
      categoryKey = '项目对标';
      categoryLabel = '项目对标';
    } else {
      categoryKey = parts[0];
      categoryLabel = parts[0];
    }

    const cat = getOrCreateCategory(categoryKey, categoryLabel);

    // 分类根的 README.md 挂到 cat.readme
    const isCategoryReadme = parts.length === 2 && fileName.toLowerCase() === 'readme.md';
    if (isCategoryReadme) {
      cat.readme = doc;
      return;
    }

    cat.docs.push(doc);
  });

  // 取 welcome
  const welcomeEntry = catMap.get('__welcome__');
  const welcome = welcomeEntry ? welcomeEntry.welcome : null;
  catMap.delete('__welcome__');

  // 组内按 order 排序；分类顺序：业界最佳实践 优先，然后 项目对标，其余按 label
  const categories = [...catMap.values()];
  categories.forEach((c) => {
    c.docs.sort((a, b) => {
      if (a.order !== b.order) return a.order - b.order;
      return a.title.localeCompare(b.title, 'zh-Hans-CN');
    });
  });
  const priority = { '业界最佳实践': 0, '项目对标': 1 };
  categories.sort((a, b) => {
    const pa = priority[a.key] ?? 99;
    const pb = priority[b.key] ?? 99;
    if (pa !== pb) return pa - pb;
    return a.label.localeCompare(b.label, 'zh-Hans-CN');
  });

  const totalDocs = categories.reduce((sum, c) => sum + c.docs.length, 0);
  log('解析 Insights：' + categories.length + ' 个分类 · ' + totalDocs + ' 篇文档');

  return { placeholder: false, welcome, categories, totalDocs };
}

function walkMarkdown(dir) {
  const out = [];
  const stack = [dir];
  while (stack.length) {
    const cur = stack.pop();
    const entries = fs.readdirSync(cur, { withFileTypes: true });
    for (const e of entries) {
      const p = path.join(cur, e.name);
      if (e.isDirectory()) stack.push(p);
      else if (e.isFile() && e.name.toLowerCase().endsWith('.md')) out.push(p);
    }
  }
  return out;
}

function parseInsight(raw, relFromInsights, absPath) {
  const fileName = path.basename(relFromInsights);
  const title = extractTitle(raw) || fileName.replace(/\.md$/i, '');
  const summary = extractSummary(raw);
  const orderMatch = fileName.match(/^(\d+)/);
  const order = orderMatch ? parseInt(orderMatch[1], 10) : Number.MAX_SAFE_INTEGER;
  const slug = slugify(relFromInsights.replace(/\.md$/i, ''));
  let updatedAt = null;
  try {
    updatedAt = fs.statSync(absPath).mtime.toISOString();
  } catch (_) { /* ignore */ }

  return {
    path: relFromInsights,                                  // 如 "业界最佳实践/01-anthropic-prompt-caching.md"
    slug,                                                   // 如 "yejie-zuijia-shijian-01-anthropic-prompt-caching"（仅 ASCII 友好用；中文保留）
    title,
    summary,
    html: renderMarkdown(raw),
    order,
    updatedAt,
    githubUrl: REPO_BLOB_BASE + encodeURI('docs/Insights/' + relFromInsights)
  };
}

function extractTitle(raw) {
  const m = raw.match(/^#\s+(.+?)\s*$/m);
  if (!m) return '';
  return m[1].replace(/[`*_]/g, '').trim();
}

function extractSummary(raw) {
  // 去掉 frontmatter（如果有）
  let body = raw.replace(/^---\n[\s\S]*?\n---\n?/, '');
  // 去掉第一行 `# title`
  body = body.replace(/^#\s+.+?\n/, '');
  // 按段切，找第一段"普通文字"
  const paragraphs = body.split(/\n{2,}/);
  for (const p of paragraphs) {
    const t = p.trim();
    if (!t) continue;
    if (t.startsWith('>')) continue;            // blockquote（通常是来源/日期）
    if (t.startsWith('```')) continue;          // 代码块
    if (t.startsWith('#')) continue;            // 子标题
    if (t.startsWith('|')) continue;            // 表格
    if (/^[-*]\s/.test(t) || /^\d+\.\s/.test(t)) continue; // 列表
    // 纯文字段
    const clean = t.replace(/[`*_]/g, '').replace(/\s+/g, ' ');
    return clean.length > 160 ? clean.slice(0, 159) + '…' : clean;
  }
  return '';
}

/**
 * 扫描 explorations/<代号>/ 提取每人的探索元数据（前期探索 tab）。
 *
 * 形态：
 *   explorations/
 *     _template/        ← 跳过
 *     <代号>/
 *       README.md       ← frontmatter: title / summary / tags / screenshot
 *       index.html      ← 看板提示用户本地打开
 *       screenshot.png  ← 可选，会被复制到 dist/explorations/<代号>/screenshot.png
 *
 * 返回：
 *   { placeholder: bool, entries: [{ handle, hasReadme, title, summary, tags, screenshotSrc, screenshotPublic, githubUrl }] }
 *   screenshotSrc/Public 在 prepareDist 后由 copyExplorationScreenshots 实际拷贝。
 */
function readExplorations() {
  if (!fs.existsSync(EXPLORATIONS_DIR)) {
    return { placeholder: true, message: '尚未创建 explorations/。新人跑 `npm run init-explore` 即可生成。', entries: [] };
  }

  const dirEntries = fs.readdirSync(EXPLORATIONS_DIR, { withFileTypes: true });
  const entries = [];
  dirEntries.forEach((e) => {
    if (!e.isDirectory()) return;
    if (e.name.startsWith('_') || e.name.startsWith('.')) return;     // 跳过 _template / 隐藏目录
    const handle = e.name;
    const readmePath = path.join(EXPLORATIONS_DIR, handle, 'README.md');
    if (!fs.existsSync(readmePath)) {
      entries.push({ handle, hasReadme: false });
      return;
    }
    const raw = fs.readFileSync(readmePath, 'utf-8');
    const meta = parseExploreFrontmatter(raw);
    let screenshotSrc = null;
    let screenshotPublic = null;
    if (meta.screenshot) {
      const candidate = path.join(EXPLORATIONS_DIR, handle, meta.screenshot);
      if (fs.existsSync(candidate)) {
        const size = fs.statSync(candidate).size;
        if (size > SCREENSHOT_MAX_BYTES) {
          warn('explorations/' + handle + '/' + meta.screenshot + ' 超过 200KB（实测 ' + Math.round(size / 1024) + 'KB），仍会复制但建议压缩');
        }
        screenshotSrc = candidate;
        screenshotPublic = 'explorations/' + handle + '/' + meta.screenshot;
      }
    }
    const hasIndexHtml = fs.existsSync(path.join(EXPLORATIONS_DIR, handle, 'index.html'));
    entries.push({
      handle,
      hasReadme: true,
      title: meta.title || '',
      summary: meta.summary || '',
      tags: Array.isArray(meta.tags) ? meta.tags : (meta.tags ? [meta.tags] : []),
      screenshotSrc,
      screenshotPublic,
      hasIndexHtml,
      demoUrl: hasIndexHtml ? ('explorations/' + handle + '/index.html') : null,
      githubUrl: REPO_BLOB_BASE + 'explorations/' + encodeURIComponent(handle)
    });
  });

  if (entries.length === 0) {
    return {
      placeholder: true,
      message: '探索期已开放，但还没有同事跑过 `npm run init-explore`。第一个跑的人就上看板。',
      entries: []
    };
  }

  const submitted = entries.filter((x) => x.hasReadme).length;
  log('解析探索：' + entries.length + ' 个目录（' + submitted + ' 已提交 README · ' + (entries.length - submitted) + ' 占位）');
  return { placeholder: false, entries };
}

function parseExploreFrontmatter(raw) {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!m) return {};
  const meta = {};
  const lines = m[1].split(/\r?\n/);
  lines.forEach((line) => {
    const kv = line.match(/^([A-Za-z_][\w\-]*)\s*:\s*(.*)$/);
    if (!kv) return;
    let v = kv[2].trim();
    // 数组：[a, b, c] 或 [a]
    if (v.startsWith('[') && v.endsWith(']')) {
      v = v.slice(1, -1)
        .split(',')
        .map((x) => x.replace(/^['"]\s*|\s*['"]$/g, '').trim())
        .filter(Boolean);
    } else {
      v = v.replace(/^['"]|['"]$/g, '');
    }
    meta[kv[1]] = v;
  });
  return meta;
}

/**
 * 扫描 docs/architecture/adr/NNNN-*.md，提取 ADR 元数据。
 * 顶部约定：
 *   # ADR-NNNN · 标题
 *   - **Status**: Accepted / Draft / Proposed / Deprecated / Superseded by NNNN
 *   - **Date**: YYYY-MM-DD
 *   - **Deciders**: ...
 *   - **Supersedes**: NNNN / —
 *   - **Superseded-by**: NNNN / —
 */
function readAdrs() {
  if (!fs.existsSync(ADR_DIR)) {
    return { placeholder: true, message: '等待 docs/architecture/adr/NNNN-*.md 入仓。' };
  }
  const files = fs.readdirSync(ADR_DIR)
    .filter((f) => /^\d{4}-.*\.md$/i.test(f))
    .sort();
  if (files.length === 0) {
    return { placeholder: true, message: '等待 docs/architecture/adr/NNNN-*.md 入仓。' };
  }
  const adrs = files.map((f) => parseAdr(path.join(ADR_DIR, f), f));
  const stats = {
    total: adrs.length,
    accepted: adrs.filter((a) => a.statusKind === 'accepted').length,
    draft: adrs.filter((a) => a.statusKind === 'draft' || a.statusKind === 'proposed').length,
    deprecated: adrs.filter((a) => a.statusKind === 'deprecated' || a.statusKind === 'superseded').length
  };
  log('解析 ADR：' + stats.total + ' 篇（' + stats.accepted + ' Accepted · ' + stats.draft + ' Draft · ' + stats.deprecated + ' 已退役）');
  return { placeholder: false, adrs, stats };
}

function parseAdr(absPath, fileName) {
  const raw = fs.readFileSync(absPath, 'utf-8');
  // 标题：# ADR-NNNN · 标题
  const titleMatch = raw.match(/^#\s+(ADR-\d+)\s*·?\s*(.+?)\s*$/m);
  const id = titleMatch ? titleMatch[1] : fileName.replace(/\.md$/i, '');
  const title = titleMatch ? titleMatch[2].trim() : id;

  const field = (label) => {
    const re = new RegExp('^[-*]\\s+\\*\\*' + label + '\\*\\*[:：]\\s*(.+)$', 'mi');
    const m = raw.match(re);
    return m ? m[1].trim() : '';
  };

  const statusRaw = field('Status');
  const statusKind = classifyAdrStatus(statusRaw);

  // Context 第一段作为摘要
  const ctxMatch = raw.match(/##\s+Context\s*\n+([\s\S]*?)(?=\n##\s|$)/);
  let summary = '';
  if (ctxMatch) {
    const firstPara = ctxMatch[1].split(/\n{2,}/).map((p) => p.trim()).filter(Boolean)[0] || '';
    const clean = firstPara.replace(/[`*_>]/g, '').replace(/\s+/g, ' ');
    summary = clean.length > 180 ? clean.slice(0, 179) + '…' : clean;
  }

  return {
    id,
    title,
    file: fileName,
    status: statusRaw || 'Unknown',
    statusKind,
    date: field('Date'),
    deciders: field('Deciders'),
    supersedes: field('Supersedes').replace(/^[—-]+$/, ''),
    supersededBy: field('Superseded-by').replace(/^[—-]+$/, ''),
    summary,
    githubUrl: REPO_BLOB_BASE + 'docs/architecture/adr/' + encodeURIComponent(fileName)
  };
}

function classifyAdrStatus(s) {
  const lower = (s || '').toLowerCase();
  if (lower.startsWith('accepted')) return 'accepted';
  if (lower.startsWith('draft')) return 'draft';
  if (lower.startsWith('proposed')) return 'proposed';
  if (lower.startsWith('deprecated')) return 'deprecated';
  if (lower.startsWith('superseded')) return 'superseded';
  return 'unknown';
}

/**
 * 扫描 .claude/skills/*.md，提取 skill 元数据。
 * 顶部 frontmatter 约定（标准 Claude Code skill 格式）：
 *   ---
 *   name: <skill 名>
 *   description: <触发条件 / 用途>
 *   ---
 */
function readSkills() {
  if (!fs.existsSync(SKILLS_DIR)) {
    return { placeholder: true, message: '等待 .claude/skills/ 下的 skill 注册。' };
  }
  const files = fs.readdirSync(SKILLS_DIR)
    .filter((f) => f.toLowerCase().endsWith('.md'))
    .sort();
  if (files.length === 0) {
    return { placeholder: true, message: '等待 .claude/skills/ 下的 skill 注册。' };
  }
  const skills = files.map((f) => parseSkill(path.join(SKILLS_DIR, f), f));
  log('解析 Skills：' + skills.length + ' 个');
  return { placeholder: false, skills };
}

function parseSkill(absPath, fileName) {
  const raw = fs.readFileSync(absPath, 'utf-8');
  const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  let name = fileName.replace(/\.md$/i, '');
  let description = '';
  if (fmMatch) {
    const lines = fmMatch[1].split(/\r?\n/);
    lines.forEach((line) => {
      const m = line.match(/^([A-Za-z_][\w\-]*)\s*:\s*(.+)$/);
      if (!m) return;
      const k = m[1];
      const v = m[2].trim().replace(/^['"]|['"]$/g, '');
      if (k === 'name') name = v;
      else if (k === 'description') description = v;
    });
  }
  // 第一个 # 标题后的第一段（如 frontmatter 描述太短，正文起辅助）
  let detail = '';
  const body = raw.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, '');
  const firstH1 = body.match(/^#\s+.+\n+([\s\S]*?)(?=\n##\s|$)/);
  if (firstH1) {
    const firstPara = firstH1[1].split(/\n{2,}/).map((p) => p.trim()).filter(Boolean)[0] || '';
    if (firstPara && !firstPara.startsWith('>')) {
      const clean = firstPara.replace(/[`*_]/g, '').replace(/\s+/g, ' ');
      detail = clean.length > 200 ? clean.slice(0, 199) + '…' : clean;
    }
  }
  return {
    name,
    file: fileName,
    description,
    detail,
    githubUrl: REPO_BLOB_BASE + '.claude/skills/' + encodeURIComponent(fileName)
  };
}

function copyExplorationScreenshots(entries) {
  let copied = 0;
  (entries || []).forEach((e) => {
    if (!e.screenshotSrc || !e.screenshotPublic) return;
    const dst = path.join(DIST_DIR, e.screenshotPublic);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(e.screenshotSrc, dst);
    copied += 1;
  });
  if (copied > 0) log('复制 ' + copied + ' 张探索截图到 dist/explorations/');
}

/**
 * 把每位同事 explorations/<代号>/ 下的 demo 文件（除 README.md / 隐藏文件）
 * 复制到 dist/explorations/<代号>/，使 demo 可在 GitHub Pages 上直接打开：
 *   https://boris-hbx.github.io/DeepInsight/explorations/<代号>/index.html
 *
 * 排除清单：README.md（已被 frontmatter 解析）、以 . / _ 开头的文件、node_modules。
 */
function copyExplorationDemos(entries) {
  let dirCount = 0;
  let fileCount = 0;
  (entries || []).forEach((e) => {
    if (!e.handle || !e.hasReadme) return;
    const srcDir = path.join(EXPLORATIONS_DIR, e.handle);
    const dstDir = path.join(DIST_DIR, 'explorations', e.handle);
    const n = copyDirFiltered(srcDir, dstDir, (name) => {
      if (name.toLowerCase() === 'readme.md') return false;
      if (name.startsWith('.') || name.startsWith('_')) return false;
      if (name === 'node_modules') return false;
      return true;
    });
    if (n > 0) {
      dirCount += 1;
      fileCount += n;
    }
  });
  if (fileCount > 0) log('复制 ' + dirCount + ' 个探索目录 · ' + fileCount + ' 个文件到 dist/explorations/');
}

function copyDirFiltered(src, dst, filter) {
  let n = 0;
  if (!fs.existsSync(src)) return 0;
  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const e of entries) {
    if (!filter(e.name)) continue;
    const s = path.join(src, e.name);
    const d = path.join(dst, e.name);
    if (e.isDirectory()) {
      n += copyDirFiltered(s, d, filter);
    } else if (e.isFile()) {
      fs.mkdirSync(path.dirname(d), { recursive: true });
      fs.copyFileSync(s, d);
      n += 1;
    }
  }
  return n;
}

function slugify(s) {
  return s
    .toLowerCase()
    .replace(/[\/\\]/g, '-')
    .replace(/\s+/g, '-')
    .replace(/[^\w一-鿿\-]/g, '')
    .replace(/-{2,}/g, '-')
    .replace(/^-|-$/g, '');
}

function buildData(manualHtml, taskboard, stewardship, insights, explorations, adrs, skills) {
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
    stewardship: stewardship && stewardship.zones.length > 0
      ? {
          placeholder: false,
          zones: stewardship.zones,
          stats: stewardship.stats
        }
      : {
          placeholder: true,
          message: '等待 docs/stewardship.md 注入责任田划分。'
        },
    insights: insights && !insights.placeholder
      ? {
          placeholder: false,
          welcome: insights.welcome,
          categories: insights.categories,
          totalDocs: insights.totalDocs
        }
      : {
          placeholder: true,
          message: '等待 docs/Insights/ 下放入业界最佳实践与对标分析。新增 .md 后 push 到 main，CI 自动构建并部署到 gh-pages。'
        },
    explorations: explorations && !explorations.placeholder
      ? {
          placeholder: false,
          entries: explorations.entries,
          phase: '2026-04-25 ~ 2026-05-08（探索期）'
        }
      : {
          placeholder: true,
          message: (explorations && explorations.message) || '等待新人跑 `npm run init-explore` 创建首个探索目录。'
        },
    sliceWall: {
      placeholder: true,
      message: '等待首批 spec 提交（docs/specs/NNN-*.md）。本面板将自动按负责人分列，显示每人切片的 spec → build → test → demo 状态。'
    },
    agentMetrics: {
      placeholder: true,
      message: '等待首批带 [human] / [pair] / [agent] trailer 的 commit。本面板将展示 agent 协作参与度的时间序列与比例。'
    },
    adrIndex: adrs && !adrs.placeholder
      ? { placeholder: false, adrs: adrs.adrs, stats: adrs.stats }
      : { placeholder: true, message: (adrs && adrs.message) || '等待首批 ADR 入仓。' },
    skillRegistry: skills && !skills.placeholder
      ? { placeholder: false, skills: skills.skills }
      : { placeholder: true, message: (skills && skills.message) || '等待 .claude/skills/ 下的 skill 注册。' }
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
  const stewardshipRaw = readStewardship();
  const stewardship = parseStewardship(stewardshipRaw);
  const insights = readInsights();
  const explorations = readExplorations();
  const adrs = readAdrs();
  const skills = readSkills();
  const data = buildData(manualHtml, taskboard, stewardship, insights, explorations, adrs, skills);
  prepareDist();
  copyExplorationScreenshots(explorations.entries || []);
  copyExplorationDemos(explorations.entries || []);
  writeIndexHtml(data);
  copyAssets();
  writeNoJekyll();
  log('✓ 构建完成。本地预览：双击打开 dist/index.html');
  log('  发布到 GitHub Pages：npm run deploy');
}

main();
