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
    } else {
      manualBody.innerHTML = '<p style="color:var(--muted)">⚠ 未找到运作手册数据，请确认 <code>项目初始化草稿.md</code> 存在并运行 <code>npm run build</code>。</p>';
    }
  }

  // Task board panel
  renderTaskboard(document.getElementById('taskboard-body'), data);

  // Stewardship panel
  renderStewardship(document.getElementById('stewardship-body'), data);

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
  tabs.forEach(function (t) {
    t.addEventListener('click', function (e) {
      e.preventDefault();
      const target = t.dataset.tab;
      tabs.forEach(function (x) { x.classList.toggle('active', x === t); });
      panels.forEach(function (p) { p.classList.toggle('active', p.id === target); });
      history.replaceState(null, '', '#' + target);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  });

  // Honor hash on load
  const hash = (location.hash || '').replace('#', '');
  if (hash) {
    const t = document.querySelector('.tab[data-tab="' + hash + '"]');
    if (t) t.click();
  }

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
})();
