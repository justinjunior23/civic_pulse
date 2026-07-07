// ── State ──────────────────────────────────────────────────────────────
let issues = [];
let selectedId = null;

// ── Helpers ────────────────────────────────────────────────────────────
function timeAgo(dateStr) {
  const s = Math.floor((Date.now() - new Date(dateStr)) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return Math.floor(s / 60) + 'm ago';
  return Math.floor(s / 3600) + 'h ago';
}

function sevClass(sev) {
  return { High: 'sev-high', Medium: 'sev-medium', Low: 'sev-low' }[sev] || 'sev-low';
}

function statusLabel(s) {
  return { open: 'Open', in_progress: 'In Progress', resolved: 'Resolved' }[s] || s;
}

function statusClass(s) {
  return { open: 'status-open', in_progress: 'status-progress', resolved: 'status-resolved' }[s] || '';
}

// ── Submit report ──────────────────────────────────────────────────────
async function submitReport() {
  const text = document.getElementById('reportInput').value.trim();
  if (!text) return;

  const btn = document.getElementById('submitBtn');
  const spinner = document.getElementById('spinner');
  const btnText = document.getElementById('btnText');

  btn.disabled = true;
  spinner.style.display = 'block';
  btnText.textContent = 'Analysing...';

  try {
    const res = await fetch('/api/reports/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Server error');
    }

    const issue = await res.json();
    document.getElementById('reportInput').value = '';
    issues.unshift(issue);
    renderFeed();
    await loadDashboard();
    selectIssue(issue.id);

    // Duplicate warning
    if (issue.duplicate_warning) {
      const dup = issue.duplicate_warning;
      showDuplicateWarning(dup);
    }

  } catch (e) {
    alert('Error: ' + e.message);
  } finally {
    btn.disabled = false;
    spinner.style.display = 'none';
    btnText.textContent = 'Analyse & Submit';
  }
}

// ── Duplicate warning banner ───────────────────────────────────────────
function showDuplicateWarning(dup) {
  let banner = document.getElementById('dupWarning');
  if (!banner) {
    banner = document.createElement('div');
    banner.id = 'dupWarning';
    banner.className = 'dup-warning';
    document.querySelector('.report-form').after(banner);
  }
  banner.innerHTML = `
    ⚠️ <strong>Possible duplicate</strong> — a similar ${statusLabel(dup.status)} issue already exists:
    <span class="dup-summary">"${dup.summary}"</span>
    <button onclick="selectIssue(${dup.id}); this.parentElement.remove()">View →</button>
    <button onclick="this.parentElement.remove()">✕</button>
  `;
}

// ── Update status ──────────────────────────────────────────────────────
async function updateStatus(id, newStatus) {
  try {
    const res = await fetch(`/api/reports/${id}/status/`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    });
    if (!res.ok) throw new Error('Failed to update status');
    const updated = await res.json();

    // Update local state
    const idx = issues.findIndex(i => i.id === id);
    if (idx !== -1) issues[idx] = updated;

    renderFeed();
    await loadDashboard();
    selectIssue(id);
  } catch (e) {
    alert('Error: ' + e.message);
  }
}

// ── Export PDF ─────────────────────────────────────────────────────────
function exportPDF(id) {
  window.open(`/api/reports/${id}/export/`, '_blank');
}

// ── Load dashboard from API ────────────────────────────────────────────
async function loadDashboard() {
  try {
    const res = await fetch('/api/dashboard/');
    const data = await res.json();

    document.getElementById('statTotal').textContent = data.total;
    document.getElementById('statHigh').textContent = data.high;
    document.getElementById('statMedium').textContent = data.medium;
    document.getElementById('statLow').textContent = data.low;

    // Status counters
    const statusRow = document.getElementById('statusRow');
    if (statusRow) {
      document.getElementById('statOpen').textContent = data.open;
      document.getElementById('statInProgress').textContent = data.in_progress;
      document.getElementById('statResolved').textContent = data.resolved;
    }

    renderPriorityList(data.priority_list);
  } catch (e) {
    console.error('Dashboard load failed:', e);
  }
}

// ── Load all reports ───────────────────────────────────────────────────
async function loadReports() {
  try {
    const res = await fetch('/api/reports/');
    issues = await res.json();
    renderFeed();
  } catch (e) {
    console.error('Reports load failed:', e);
  }
}

// ── Render feed ────────────────────────────────────────────────────────
function renderFeed() {
  const feed = document.getElementById('issueFeed');
  document.getElementById('emptyFeed').style.display = issues.length ? 'none' : 'block';
  feed.querySelectorAll('.issue-card').forEach(c => c.remove());

  issues.forEach(issue => {
    const card = document.createElement('div');
    card.className = 'issue-card' + (issue.id === selectedId ? ' active' : '');
    card.dataset.id = issue.id;
    card.onclick = () => selectIssue(issue.id);
    card.innerHTML = `
      <div class="issue-card-top">
        <div class="issue-text">${issue.text}</div>
        <span class="severity-badge ${sevClass(issue.severity)}">${issue.severity}</span>
      </div>
      <div class="issue-card-bottom">
        <span class="category-tag">${issue.category}</span>
        ${issue.location ? `<span class="location-tag">📍 ${issue.location}</span>` : ''}
        <span class="status-badge ${statusClass(issue.status)}">${statusLabel(issue.status)}</span>
        <span class="issue-time">${timeAgo(issue.created_at)}</span>
      </div>
    `;
    feed.appendChild(card);
  });

  renderAISummary(issues); // ← ADD THIS LINE
}
// ── Render priority list ───────────────────────────────────────────────
function renderPriorityList(list) {
  const section = document.getElementById('prioritySection');
  document.getElementById('emptyDash').style.display = list.length ? 'none' : 'block';
  section.querySelectorAll('.priority-item, .section-label').forEach(el => el.remove());

  if (list.length) {
    const label = document.createElement('div');
    label.className = 'section-label';
    label.textContent = 'Issues by Priority';
    section.prepend(label);
  }

 list.forEach((issue, idx) => {
  const item = document.createElement('div');
  item.className = 'priority-item';
  item.innerHTML = `
    <div class="priority-rank ${idx === 0 ? 'top' : ''}">${String(idx + 1).padStart(2, '0')}</div>
    <div class="priority-content">
      <div class="priority-summary">${issue.summary}</div>
      <div class="priority-meta">
        <span class="severity-badge ${sevClass(issue.severity)}">${issue.severity}</span>
        <span class="category-tag">${issue.category}</span>
        ${issue.location ? `<span class="location-tag">📍 ${issue.location}</span>` : ''}
        <span class="status-badge ${statusClass(issue.status)}">${statusLabel(issue.status)}</span>
        <span class="report-count">${timeAgo(issue.created_at)}</span>
      </div>
    </div>
    <div class="priority-action">
      ${renderPriorityBadge(issue)}
      <button class="action-btn" onclick="selectIssue(${issue.id})">View detail</button>
    </div>
  `;
  section.appendChild(item);
});
}

// ── Select issue + show detail ─────────────────────────────────────────
function selectIssue(id) {
  selectedId = id;
  const issue = issues.find(i => i.id === id);
  if (!issue) return;

  document.querySelectorAll('.issue-card').forEach(c => {
    c.classList.toggle('active', parseInt(c.dataset.id) === id);
  });

  const panel = document.getElementById('detailPanel');
  panel.classList.add('visible');

  document.getElementById('detailGrid').innerHTML = `
    <div class="detail-field">
      <div class="detail-field-label">Category</div>
      <div class="detail-field-value">${issue.category}</div>
    </div>
    <div class="detail-field">
      <div class="detail-field-label">Severity</div>
      <div class="detail-field-value"><span class="severity-badge ${sevClass(issue.severity)}">${issue.severity}</span></div>
    </div>
    <div class="detail-field">
      <div class="detail-field-label">Location</div>
      <div class="detail-field-value">${issue.location || '—'}</div>
    </div>
    <div class="detail-field">
      <div class="detail-field-label">Status</div>
      <div class="detail-field-value">
        <select class="status-select" onchange="updateStatus(${issue.id}, this.value)">
          <option value="open" ${issue.status === 'open' ? 'selected' : ''}>Open</option>
          <option value="in_progress" ${issue.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
          <option value="resolved" ${issue.status === 'resolved' ? 'selected' : ''}>Resolved</option>
        </select>
      </div>
    </div>
    <div class="detail-field" style="grid-column: 1 / -1">
      <div class="detail-field-label">AI Summary</div>
      <div class="detail-field-value">${issue.summary}</div>
    </div>
    <div class="detail-field" style="grid-column: 1 / -1">
      <div class="detail-field-label">Recommended Action</div>
      <div class="detail-field-value">${issue.recommended_action}</div>
    </div>
    <div class="detail-field" style="grid-column: 1 / -1">
      <button class="export-btn" onclick="exportPDF(${issue.id})">⬇ Export PDF Briefing</button>
    </div>
  `;

  // Map view
  renderMap(issue);
}

// ── Map view ───────────────────────────────────────────────────────────
function renderMap(issue) {
  const mapContainer = document.getElementById('mapContainer');
  if (!mapContainer) return;

  if (!issue.location) {
    mapContainer.innerHTML = '<div class="map-empty">No location data for this report.</div>';
    return;
  }

  // Use OpenStreetMap embed via iframe (no API key needed)
  const query = encodeURIComponent(issue.location + ', Rwanda');
  mapContainer.innerHTML = `
    <div class="map-label">📍 ${issue.location}</div>
    <iframe
      class="map-frame"
      src="https://www.openstreetmap.org/export/embed.html?bbox=29.5,-2.1,30.5,-1.5&layer=mapnik&marker=${encodeURIComponent(issue.location + ', Kigali, Rwanda')}"
      loading="lazy"
      allowfullscreen>
    </iframe>
    <a class="map-link" href="https://www.openstreetmap.org/search?query=${query}" target="_blank">
      Open in full map ↗
    </a>
  `;
}

// Renders the AI Situation Summary using counts you already have client-side
function renderAISummary(reports) {
  const card = document.getElementById('aiSummaryCard');
  const list = document.getElementById('aiSummaryList');
  if (!reports || reports.length === 0) {
    card.style.display = 'none';
    return;
  }

  const total = reports.length;
  const byCategory = {};
  reports.forEach(r => {
    byCategory[r.category] = (byCategory[r.category] || 0) + 1;
  });
  const topCategory = Object.entries(byCategory).sort((a, b) => b[1] - a[1])[0];
  const topCategoryPct = topCategory ? Math.round((topCategory[1] / total) * 100) : 0;

  const highPriority = reports.filter(r => (r.priority_score || 0) >= 85).length;

  const locationCounts = {};
  reports.forEach(r => {
    if (r.location) locationCounts[r.location] = (locationCounts[r.location] || 0) + 1;
  });
  const topLocation = Object.entries(locationCounts).sort((a, b) => b[1] - a[1])[0];

  const points = [];
  if (topCategory) points.push(`${topCategory[0]} accounts for ${topCategoryPct}% of active incidents.`);
  if (topLocation) points.push(`${topLocation[0]} is currently the highest-priority location.`);
  if (highPriority > 0) points.push(`${highPriority} incident${highPriority > 1 ? 's' : ''} require immediate attention.`);
  points.push(`${total} total report${total > 1 ? 's' : ''} tracked this session.`);

  list.innerHTML = points.map(p => `<li>${p}</li>`).join('');
  card.style.display = 'block';
}

// Builds the priority-score + confidence markup to insert into your existing card template
function renderPriorityBadge(report) {
  const score = report.priority_score ?? '—';
  const confidence = report.confidence ?? null;
  return `
    <div class="priority-score-badge">
      <div class="score-value">${score}</div>
      <div class="score-label">Priority</div>
    </div>
    ${confidence !== null ? `<span class="confidence-tag">Confidence ${confidence}%</span>` : ''}
  `;
}




// ── Enter key shortcut ─────────────────────────────────────────────────
document.getElementById('reportInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.ctrlKey) submitReport();
});

// ── Init ───────────────────────────────────────────────────────────────
loadReports();
loadDashboard();