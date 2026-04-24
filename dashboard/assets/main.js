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
})();
