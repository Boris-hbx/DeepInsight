(function () {
  'use strict';

  const data = window.DEEPINSIGHT_DATA || {};

  // Hero & footer metadata
  const genDate = data.generatedAt ? new Date(data.generatedAt) : null;
  const fmt = genDate
    ? genDate.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    : '—';
  setText('updated-at', genDate ? '更新于 ' + fmt : '');
  setText('generated-at', fmt);
  setText('version-tag', data.version || '');
  const repoLink = document.getElementById('repo-link');
  if (repoLink && data.repoUrl) repoLink.href = data.repoUrl;

  // Manual panel (rendered markdown)
  const manualBody = document.getElementById('manual-body');
  if (manualBody) {
    if (data.manualHtml) {
      manualBody.innerHTML = data.manualHtml;
      attachPromptCopyButtons(manualBody);
    } else {
      manualBody.innerHTML = '<p style="color:var(--muted)">⚠ 未找到运作手册数据，请确认 <code>项目初始化草稿.md</code> 存在并运行 <code>npm run build</code>。</p>';
    }
  }

  // Task board panel
  renderTaskboard(document.getElementById('taskboard-body'), data);

  // Stewardship panel
  renderStewardship(document.getElementById('stewardship-body'), data);

  // Explorations panel
  renderExplorations(document.getElementById('explorations-body'), data);

  // Insights panel
  const insightsState = renderInsights(document.getElementById('insights-body'), data);

  // Placeholder panels
  const placeholders = {
    slices: { title: '切片墙', data: data.sliceWall },
    agents: { title: 'Agent 协作度', data: data.agentMetrics },
    adr: { title: 'ADR 索引', data: data.adrIndex },
    skills: { title: 'Skill 注册表', data: data.skillRegistry }
  };
  Object.keys(placeholders).forEach(function (key) {
    const cfg = placeholders[key];
    const el = document.getElementById(key + '-body');
    if (!el) return;
    const message = (cfg.data && cfg.data.message) || '等待数据';
    el.innerHTML =
      '<div class="empty-state">' +
      '<div class="empty-icon">⏳</div>' +
      '<h3>' + escapeHtml(cfg.title) + '（尚未填充）</h3>' +
      '<p>' + escapeHtml(message) + '</p>' +
      '<div class="hint">本模块将在轨道 B 第二波（B2）自动填充</div>' +
      '</div>';
  });

  // Tab switching
  const tabs = document.querySelectorAll('.tab');
  const panels = document.querySelectorAll('.panel');
  function activateTab(targetName) {
    tabs.forEach(function (x) { x.classList.toggle('active', x.dataset.tab === targetName); });
    panels.forEach(function (p) { p.classList.toggle('active', p.id === targetName); });
    // Insights tab 需要更宽的 main 以容纳左侧目录 + 右侧正文
    document.body.classList.toggle('ins-wide', targetName === 'insights');
  }
  tabs.forEach(function (t) {
    t.addEventListener('click', function (e) {
      e.preventDefault();
      const target = t.dataset.tab;
      activateTab(target);
      history.replaceState(null, '', '#' + target);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });

  // Honor hash on load: supports "#tab" and "#insights/<category>/<slug>"
  function applyHash() {
    const rawHash = (location.hash || '').replace('#', '');
    if (!rawHash) return;
    const [tabPart, ...rest] = rawHash.split('/');
    const tabEl = document.querySelector('.tab[data-tab="' + tabPart + '"]');
    if (!tabEl) return;
    activateTab(tabPart);
    if (tabPart === 'insights' && rest.length > 0 && insightsState && insightsState.selectByPath) {
      insightsState.selectByPath(rest.join('/'));
    }
  }
  applyHash();
  window.addEventListener('hashchange', applyHash);

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function renderTaskboard(el, data) {
    if (!el) return;
    const tb = data.taskboard || {};
    if (tb.placeholder) {
      el.classList.add('placeholder');
      el.innerHTML =
        '<div class="empty-state">' +
        '<div class="empty-icon">📋</div>' +
        '<h3>任务看板（尚未填充）</h3>' +
        '<p>' + escapeHtml(tb.message || '等待 docs/task-board.md 注入任务令。') + '</p>' +
        '<div class="hint">编辑 <code>docs/task-board.md</code> → <code>npm run build</code> 刷新</div>' +
        '</div>';
      return;
    }
    el.classList.remove('placeholder');

    const team = data.team || [];
    const byAssignee = tb.byAssignee || {};
    const stats = tb.stats || { total: 0, open: 0, inProgress: 0, done: 0 };

    let html = '';
    html += '<div class="tb-summary">';
    html += '<div class="tb-summary-title">任务看板</div>';
    html += '<div class="tb-summary-stats">';
    html += statPill('总数', stats.total, '');
    html += statPill('待接令', stats.open, 'tb-stat-open');
    html += statPill('进行中', stats.inProgress, 'tb-stat-progress');
    html += statPill('已完成', stats.done, 'tb-stat-done');
    html += '</div>';
    html += '<p class="tb-hint">真源：<code>docs/task-board.md</code>。改 md → <code>npm run build</code> 重渲染。</p>';
    html += '</div>';

    html += '<div class="tb-grid">';
    team.forEach(function (name) {
      html += renderAssigneeCard(name, byAssignee[name] || []);
    });
    // 共享 / 未分配
    if ((byAssignee['@All'] || []).length > 0) {
      html += renderAssigneeCard('@All（全员）', byAssignee['@All'], 'tb-card-all');
    }
    if ((byAssignee['未分配'] || []).length > 0) {
      html += renderAssigneeCard('未分配', byAssignee['未分配'], 'tb-card-unassigned');
    }
    html += '</div>';

    el.innerHTML = html;
  }

  function statPill(label, value, cls) {
    return '<span class="tb-stat ' + cls + '">' +
      '<span class="tb-stat-label">' + escapeHtml(label) + '</span>' +
      '<span class="tb-stat-value">' + escapeHtml(String(value)) + '</span>' +
      '</span>';
  }

  function renderAssigneeCard(name, tasks, extraCls) {
    let h = '<div class="tb-card ' + (extraCls || '') + '">';
    h += '<div class="tb-card-head">';
    h += '<span class="tb-card-name">' + escapeHtml(name) + '</span>';
    h += '<span class="tb-card-count">' + tasks.length + '</span>';
    h += '</div>';
    if (tasks.length === 0) {
      h += '<div class="tb-card-empty">暂无令</div>';
    } else {
      h += '<ul class="tb-task-list">';
      tasks.forEach(function (t) { h += renderTaskItem(t); });
      h += '</ul>';
    }
    h += '</div>';
    return h;
  }

  function renderTaskItem(t) {
    const statusCls = statusToClass(t.status);
    const priorityCls = 'tb-pri-' + (t.priority || 'P1').replace(/[^A-Z0-9]/gi, '').slice(0, 2) || 'tb-pri-P1';
    let h = '<li class="tb-task ' + statusCls + '">';
    h += '<div class="tb-task-top">';
    h += '<span class="tb-task-id">' + escapeHtml(t.id) + '</span>';
    if (t.type) h += '<span class="tb-task-type">[' + escapeHtml(t.type) + ']</span>';
    h += '<span class="tb-task-pri ' + priorityCls + '">' + escapeHtml(stripPriority(t.priority)) + '</span>';
    h += '</div>';
    h += '<div class="tb-task-title">' + escapeHtml(t.title) + '</div>';
    const metaBits = [];
    if (t.status) metaBits.push(escapeHtml(t.status));
    if (t.dependency && t.dependency !== '无') metaBits.push('依赖 ' + escapeHtml(t.dependency));
    if (t.relation && t.relation !== '无') metaBits.push(escapeHtml(t.relation));
    if (metaBits.length) h += '<div class="tb-task-meta">' + metaBits.join(' · ') + '</div>';
    h += '</li>';
    return h;
  }

  function statusToClass(status) {
    if (!status) return '';
    if (status.indexOf('🟢') !== -1) return 'tb-status-done';
    if (status.indexOf('🟡') !== -1) return 'tb-status-progress';
    if (status.indexOf('🔴') !== -1) return 'tb-status-open';
    return '';
  }

  function stripPriority(p) {
    const m = (p || '').match(/P\d/);
    return m ? m[0] : (p || '');
  }

  function renderStewardship(el, data) {
    if (!el) return;
    const st = data.stewardship || {};
    if (st.placeholder) {
      el.classList.add('placeholder');
      el.innerHTML =
        '<div class="empty-state">' +
        '<div class="empty-icon">🌾</div>' +
        '<h3>责任田（尚未填充）</h3>' +
        '<p>' + escapeHtml(st.message || '等待 docs/stewardship.md 划分责任田。') + '</p>' +
        '<div class="hint">编辑 <code>docs/stewardship.md</code> → <code>npm run build</code> 刷新</div>' +
        '</div>';
      return;
    }
    el.classList.remove('placeholder');

    const zones = st.zones || [];
    const stats = st.stats || { total: 0, claimed: 0, open: 0 };

    let html = '';
    html += '<div class="tb-summary">';
    html += '<div class="tb-summary-title">责任田（守护人制度）</div>';
    html += '<div class="tb-summary-stats">';
    html += statPill('总片数', stats.total, '');
    html += statPill('已认领', stats.claimed, 'tb-stat-done');
    html += statPill('待认领', stats.open, 'tb-stat-open');
    html += '</div>';
    html += '<p class="tb-hint">双轴 ownership · 守护人 ≠ 审批网关 · 真源：<code>docs/stewardship.md</code></p>';
    html += '</div>';

    html += '<div class="sw-grid">';
    zones.forEach(function (z) { html += renderZoneCard(z); });
    html += '</div>';

    el.innerHTML = html;
  }

  function renderExplorations(el, data) {
    if (!el) return;
    const ex = data.explorations || {};
    const team = data.team || [];

    if (ex.placeholder) {
      el.classList.add('placeholder');
      el.innerHTML =
        '<div class="empty-state">' +
        '<div class="empty-icon">🌱</div>' +
        '<h3>前期探索（尚无人提交）</h3>' +
        '<p>' + escapeHtml(ex.message || '探索期已开放，等待第一位同事提交。') + '</p>' +
        '<div class="hint">新人本地：<code>npm run init-explore</code></div>' +
        '</div>';
      return;
    }
    el.classList.remove('placeholder');

    const entries = ex.entries || [];
    const byHandle = {};
    entries.forEach(function (e) { byHandle[e.handle] = e; });

    const submitted = entries.filter(function (e) { return e.hasReadme; }).length;
    const pending = team.length - submitted;

    let html = '';
    html += '<div class="tb-summary">';
    html += '<div class="tb-summary-title">前期探索 · ' + escapeHtml(ex.phase || '') + '</div>';
    html += '<div class="tb-summary-stats">';
    html += statPill('全员', team.length, '');
    html += statPill('已提交', submitted, 'tb-stat-done');
    html += statPill('待提交', pending, 'tb-stat-open');
    html += '</div>';
    html += '<p class="tb-hint">每人在 <code>explorations/&lt;代号&gt;/</code> 下做静态 demo · push 到 main 后 CI 自动刷新 · 收敛日：2026-05-09</p>';
    html += '</div>';

    html += '<div class="ex-grid">';
    team.forEach(function (name) {
      html += renderExCard(name, byHandle[name]);
    });
    // 名册外的探索者（如有）
    entries.forEach(function (e) {
      if (team.indexOf(e.handle) === -1) {
        html += renderExCard(e.handle, e, true);
      }
    });
    html += '</div>';

    el.innerHTML = html;
  }

  function renderExCard(handle, entry, isExtra) {
    if (!entry || !entry.hasReadme) {
      let h = '<div class="ex-card ex-pending">';
      h += '<div class="ex-card-head">';
      h += '<span class="ex-handle">' + escapeHtml(handle) + '</span>';
      h += '<span class="ex-status">待提交</span>';
      h += '</div>';
      h += '<div class="ex-empty">';
      if (entry && !entry.hasReadme) {
        h += '已建目录但 README 未填。<br>编辑 <code>explorations/' + escapeHtml(handle) + '/README.md</code> 的 frontmatter。';
      } else {
        h += '尚未开始。本地：<br><code>npm run init-explore</code>';
      }
      h += '</div>';
      h += '</div>';
      return h;
    }

    const e = entry;
    let h = '<div class="ex-card ex-active' + (isExtra ? ' ex-extra' : '') + '">';
    h += '<div class="ex-card-head">';
    h += '<span class="ex-handle">' + escapeHtml(handle) + '</span>';
    if (e.tags && e.tags.length) {
      h += '<span class="ex-tags">';
      e.tags.forEach(function (t) {
        h += '<span class="ex-tag">' + escapeHtml(t) + '</span>';
      });
      h += '</span>';
    }
    h += '</div>';

    if (e.title) h += '<div class="ex-title">' + escapeHtml(e.title) + '</div>';

    if (e.screenshotPublic) {
      h += '<a class="ex-shot-link" href="' + escapeHtml(e.githubUrl) + '" target="_blank" rel="noopener">';
      h += '<img class="ex-shot" src="' + escapeHtml(e.screenshotPublic) + '" alt="' + escapeHtml(handle) + ' 探索截图" loading="lazy">';
      h += '</a>';
    } else {
      h += '<div class="ex-shot-placeholder">（暂无截图）</div>';
    }

    if (e.summary) h += '<div class="ex-summary-text">' + escapeHtml(e.summary) + '</div>';

    h += '<div class="ex-actions">';
    h += '<div class="ex-cmd-label">本地查看：</div>';
    h += '<code class="ex-cmd">cd explorations/' + escapeHtml(handle) + ' &amp;&amp; open index.html</code>';
    h += '</div>';

    h += '<div class="ex-meta">';
    if (!e.hasIndexHtml) {
      h += '<span class="ex-warn">⚠ 缺 index.html</span>';
    }
    h += '<a class="ex-link" href="' + escapeHtml(e.githubUrl) + '" target="_blank" rel="noopener">看代码 ↗</a>';
    h += '</div>';

    h += '</div>';
    return h;
  }

  function renderInsights(el, data) {
    if (!el) return null;
    const ins = data.insights || {};
    if (ins.placeholder) {
      el.classList.add('placeholder');
      el.innerHTML =
        '<div class="empty-state">' +
        '<div class="empty-icon">📚</div>' +
        '<h3>业界参考（尚未填充）</h3>' +
        '<p>' + escapeHtml(ins.message || '等待 docs/Insights/ 下的 md 文档。') + '</p>' +
        '<div class="hint">新增 <code>docs/Insights/**/*.md</code> → push 到 main → CI 自动重构建</div>' +
        '</div>';
      return null;
    }
    el.classList.remove('placeholder');

    const categories = ins.categories || [];
    const welcome = ins.welcome || null;
    const total = ins.totalDocs || 0;

    // Flatten for path lookup
    const byPath = {};
    categories.forEach(function (c) {
      (c.docs || []).forEach(function (d) { byPath[d.path] = d; });
      if (c.readme) byPath[c.readme.path] = c.readme;
    });
    if (welcome) byPath[welcome.path] = welcome;

    let html = '';
    html += '<div class="ins-layout">';

    // LEFT: sidebar
    html += '<aside class="ins-nav">';
    html += '<div class="ins-nav-head">';
    html += '<span class="ins-nav-title">业界参考</span>';
    html += '<span class="ins-nav-count">' + total + ' 篇</span>';
    html += '</div>';
    html += '<p class="ins-nav-hint">真源：<code>docs/Insights/</code> · push 到 main 后 CI 自动刷新</p>';

    if (welcome) {
      html += '<div class="ins-group">';
      html += '<div class="ins-group-head">总览</div>';
      html += '<ul class="ins-doc-list">';
      html += renderInsightItem(welcome, 'welcome');
      html += '</ul>';
      html += '</div>';
    }

    categories.forEach(function (c) {
      html += '<div class="ins-group">';
      html += '<div class="ins-group-head">' + escapeHtml(c.label) + '<span class="ins-group-count">' + (c.docs || []).length + '</span></div>';
      html += '<ul class="ins-doc-list">';
      if (c.readme) {
        html += renderInsightItem(c.readme, 'readme');
      }
      (c.docs || []).forEach(function (d) {
        html += renderInsightItem(d, 'doc');
      });
      html += '</ul>';
      html += '</div>';
    });
    html += '</aside>';

    // RIGHT: content
    html += '<article class="ins-article">';
    html += '<div class="ins-breadcrumb" id="ins-breadcrumb"></div>';
    html += '<div class="ins-content" id="ins-content"></div>';
    html += '</article>';

    html += '</div>';
    el.innerHTML = html;

    // Bind item clicks
    const items = el.querySelectorAll('.ins-doc-item');
    items.forEach(function (it) {
      it.addEventListener('click', function (e) {
        e.preventDefault();
        const p = it.dataset.path;
        selectByPath(p, true);
      });
    });

    function selectByPath(p, updateHash) {
      const doc = byPath[p];
      if (!doc) return false;
      // toggle active state
      items.forEach(function (x) { x.classList.toggle('active', x.dataset.path === p); });
      // breadcrumb
      const crumbEl = document.getElementById('ins-breadcrumb');
      if (crumbEl) {
        const segments = doc.path.split('/');
        const crumbHtml = segments.map(function (s, i) {
          const isLast = i === segments.length - 1;
          return '<span class="ins-crumb' + (isLast ? ' ins-crumb-last' : '') + '">' + escapeHtml(s) + '</span>';
        }).join('<span class="ins-crumb-sep">/</span>');
        const updated = doc.updatedAt
          ? '<span class="ins-updated">更新于 ' + escapeHtml(formatDate(doc.updatedAt)) + '</span>'
          : '';
        crumbEl.innerHTML =
          '<div class="ins-crumb-path">📄 ' + crumbHtml + '</div>' +
          '<div class="ins-crumb-actions">' +
          updated +
          '<a class="ins-source-link" href="' + escapeHtml(doc.githubUrl || '#') + '" target="_blank" rel="noopener">在 GitHub 查看 ↗</a>' +
          '</div>';
      }
      // content
      const contentEl = document.getElementById('ins-content');
      if (contentEl) {
        contentEl.innerHTML = doc.html || '';
        contentEl.scrollTop = 0;
      }
      if (updateHash) {
        history.replaceState(null, '', '#insights/' + doc.path);
      }
      return true;
    }

    // Default selection: welcome → first category's first doc → first category's README
    let defaultPath = null;
    if (welcome) defaultPath = welcome.path;
    else if (categories.length > 0) {
      const c = categories[0];
      if (c.docs && c.docs.length > 0) defaultPath = c.docs[0].path;
      else if (c.readme) defaultPath = c.readme.path;
    }
    if (defaultPath) selectByPath(defaultPath, false);

    return { selectByPath: function (p) { return selectByPath(p, false); } };
  }

  function renderInsightItem(doc, kind) {
    const cls = 'ins-doc-item ins-doc-' + kind;
    let h = '<li><a href="#insights/' + escapeHtml(doc.path) + '" class="' + cls + '" data-path="' + escapeHtml(doc.path) + '">';
    h += '<span class="ins-doc-title">' + escapeHtml(doc.title) + '</span>';
    if (doc.summary && kind === 'doc') {
      h += '<span class="ins-doc-summary">' + escapeHtml(doc.summary) + '</span>';
    }
    h += '</a></li>';
    return h;
  }

  function formatDate(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
    } catch (_) { return iso; }
  }

  function renderZoneCard(z) {
    const claimedCls = z.claimed ? 'sw-claimed' : 'sw-open';
    const guardianLabel = z.claimed ? z.guardian : '待认领';
    let h = '<div class="sw-card ' + claimedCls + '">';
    h += '<div class="sw-card-head">';
    h += '<span class="sw-zone-id">' + escapeHtml(z.id) + '</span>';
    h += '<span class="sw-zone-name">' + escapeHtml(z.name) + '</span>';
    h += '</div>';
    h += '<div class="sw-guardian"><span class="sw-guardian-label">守护人</span><span class="sw-guardian-name">' + escapeHtml(guardianLabel) + '</span></div>';
    if (z.coverage) {
      h += '<div class="sw-coverage">' + escapeHtml(z.coverage) + '</div>';
    }
    if (z.leverage && z.leverage.length) {
      h += '<div class="sw-leverage-title">主要杠杆产出</div>';
      h += '<ul class="sw-leverage">';
      z.leverage.forEach(function (x) { h += '<li>' + escapeHtml(x) + '</li>'; });
      h += '</ul>';
    }
    if (z.trigger) {
      h += '<div class="sw-trigger">触发默认 reviewer：' + escapeHtml(z.trigger) + '</div>';
    }
    if (z.stage) {
      h += '<div class="sw-stage">当前阶段：' + escapeHtml(z.stage) + '</div>';
    }
    h += '</div>';
    return h;
  }

  // 在「常用 prompt」section 内的代码块右上角加「复制」按钮。
  // 范围：从 <h2>常用 prompt</h2> 起到下一个 <h2> 之前的所有 <pre>。
  function attachPromptCopyButtons(root) {
    const h2s = root.querySelectorAll('h2');
    let promptH2 = null;
    h2s.forEach(function (h) {
      if (!promptH2 && h.textContent.trim() === '常用 prompt') promptH2 = h;
    });
    if (!promptH2) return;
    let node = promptH2.nextElementSibling;
    while (node && node.tagName !== 'H2') {
      if (node.tagName === 'PRE') addCopyButton(node);
      const inner = node.querySelectorAll ? node.querySelectorAll('pre') : null;
      if (inner) inner.forEach(addCopyButton);
      node = node.nextElementSibling;
    }
  }

  function addCopyButton(pre) {
    if (pre.querySelector('.copy-btn')) return;
    pre.classList.add('has-copy');
    const btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.type = 'button';
    btn.textContent = '复制';
    btn.addEventListener('click', function () {
      const code = pre.querySelector('code');
      const text = (code ? code.textContent : pre.textContent).replace(/\s+$/, '');
      copyText(text).then(function () {
        btn.textContent = '已复制 ✓';
        btn.classList.add('copied');
        setTimeout(function () {
          btn.textContent = '复制';
          btn.classList.remove('copied');
        }, 1500);
      }).catch(function () {
        btn.textContent = '失败';
        setTimeout(function () { btn.textContent = '复制'; }, 1500);
      });
    });
    pre.appendChild(btn);
  }

  // 兼容 file:// 本地预览（非 secure context 下 navigator.clipboard 不可用）
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      try {
        const ok = document.execCommand('copy');
        document.body.removeChild(ta);
        ok ? resolve() : reject(new Error('execCommand failed'));
      } catch (e) {
        document.body.removeChild(ta);
        reject(e);
      }
    });
  }
})();
