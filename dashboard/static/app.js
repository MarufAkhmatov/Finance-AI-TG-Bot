// ─── State ───────────────────────────────────────────────────────
const state = {
  uid: null,
  year: new Date().getFullYear(),
  month: new Date().getMonth() + 1,
  tab: 'overview',
  charts: {},
  allTx: []
};

const MONTHS_UZ = ['Yanvar','Fevral','Mart','Aprel','May','Iyun','Iyul','Avgust','Sentabr','Oktabr','Noyabr','Dekabr'];

// ─── Init ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  const params = new URLSearchParams(location.search);
  state.uid = params.get('uid') || prompt('Telegram user ID kiriting:');
  if (!state.uid) { document.body.innerHTML = '<p style="padding:40px;color:#f87171">UID kerak. ?uid=... qo\'shing</p>'; return; }
  document.getElementById('uid-display').textContent = `UID: ${state.uid}`;

  // Nav tabs
  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      switchTab(el.dataset.tab);
    });
  });

  // Month nav
  document.getElementById('prev-month').addEventListener('click', () => changeMonth(-1));
  document.getElementById('next-month').addEventListener('click', () => changeMonth(1));

  // Search/filter
  document.getElementById('tx-search').addEventListener('input', filterTx);
  document.getElementById('tx-type').addEventListener('change', filterTx);

  loadAll();
});

function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(el => el.classList.toggle('active', el.id === `tab-${tab}`));
  if (tab === 'analytics') loadAnalytics();
  if (tab === 'calendar') loadCalendar();
  if (tab === 'transactions') renderTx();
}

function changeMonth(delta) {
  state.month += delta;
  if (state.month > 12) { state.month = 1; state.year++; }
  if (state.month < 1)  { state.month = 12; state.year--; }
  document.getElementById('month-label').textContent = `${MONTHS_UZ[state.month-1]} ${state.year}`;
  loadAll();
}

async function loadAll() {
  await Promise.all([loadUser(), loadSummary(), loadTransactions()]);
  if (state.tab === 'calendar') loadCalendar();
  if (state.tab === 'analytics') loadAnalytics();
}

// ─── API helpers ─────────────────────────────────────────────────
async function api(path) {
  const sep = path.includes('?') ? '&' : '?';
  const r = await fetch(path + sep + `uid=${state.uid}`);
  return r.json();
}

// ─── Load functions ───────────────────────────────────────────────
async function loadUser() {
  const u = await api('/api/user');
  if (u.error) return;
  document.getElementById('user-info').innerHTML = `👤 ${u.name}<br>💰 Byudjet: ${fmt(u.monthly_income)} so'm`;
}

async function loadSummary() {
  const s = await api(`/api/summary?year=${state.year}&month=${state.month}`);
  document.getElementById('c-income').textContent  = fmt(s.income) + ' so\'m';
  document.getElementById('c-expense').textContent = fmt(s.expense) + ' so\'m';
  const bal = s.balance;
  const balEl = document.getElementById('c-balance');
  balEl.textContent = (bal >= 0 ? '+' : '') + fmt(bal) + ' so\'m';
  balEl.style.color = bal >= 0 ? '#4ade80' : '#f87171';
  document.getElementById('c-budget').textContent = s.budget_used_pct + '%';
  await loadCatChart();
  await loadTrendChart();
}

async function loadTransactions() {
  const data = await api(`/api/transactions?year=${state.year}&month=${state.month}&limit=100`);
  state.allTx = data;
  renderTx();
  renderRecent(data.slice(0, 5));
}

async function loadCatChart() {
  const data = await api(`/api/categories/stats?year=${state.year}&month=${state.month}`);
  const labels = data.map(d => `${d.icon} ${d.name}`);
  const values = data.map(d => d.total);
  const colors = ['#f87171','#fb923c','#fbbf24','#a3e635','#34d399','#7dd3fc','#818cf8','#e879f9','#94a3b8'];

  const ctx = document.getElementById('pie-chart').getContext('2d');
  if (state.charts.pie) state.charts.pie.destroy();
  state.charts.pie = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }] },
    options: {
      plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', boxWidth: 12, font: { size: 12 } } } },
      cutout: '65%'
    }
  });
}

async function loadTrendChart() {
  const data = await api('/api/trends?months=6');
  const months = [...new Set(data.map(d => d.month))].sort();
  const income  = months.map(m => { const r = data.find(d => d.month === m && d.type === 'income');  return r ? r.total : 0; });
  const expense = months.map(m => { const r = data.find(d => d.month === m && d.type === 'expense'); return r ? r.total : 0; });
  const labels  = months.map(m => { const [y,mo] = m.split('-'); return MONTHS_UZ[parseInt(mo)-1]; });

  const ctx = document.getElementById('trend-chart').getContext('2d');
  if (state.charts.trend) state.charts.trend.destroy();
  state.charts.trend = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Daromad', data: income,  borderColor: '#4ade80', backgroundColor: 'rgba(74,222,128,.1)', tension: .4, fill: true },
        { label: 'Xarajat', data: expense, borderColor: '#f87171', backgroundColor: 'rgba(248,113,113,.1)', tension: .4, fill: true }
      ]
    },
    options: {
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: '#1e2535' } },
        y: { ticks: { color: '#64748b', callback: v => fmt(v) }, grid: { color: '#1e2535' } }
      },
      plugins: { legend: { labels: { color: '#94a3b8' } } }
    }
  });
}

// ─── Render transactions ──────────────────────────────────────────
function renderTx() {
  const q = (document.getElementById('tx-search').value || '').toLowerCase();
  const t = document.getElementById('tx-type').value;
  let rows = state.allTx.filter(tx => {
    if (t && tx.type !== t) return false;
    if (q && !(tx.description || '').toLowerCase().includes(q) && !(tx.cat_name || '').toLowerCase().includes(q)) return false;
    return true;
  });
  const tbody = document.getElementById('tx-body');
  tbody.innerHTML = '';
  document.getElementById('tx-empty').style.display = rows.length ? 'none' : 'block';
  rows.forEach(tx => {
    const tr = document.createElement('tr');
    const date = tx.created_at ? tx.created_at.slice(0,10) : '';
    const srcMap = { text: '✏️ Matn', voice: '🎤 Ovoz', receipt: '📷 Chek' };
    tr.innerHTML = `
      <td>${date}</td>
      <td><span class="badge ${tx.type}">${tx.cat_icon || ''} ${tx.cat_name || 'Boshqa'}</span></td>
      <td>${tx.description || '—'}</td>
      <td class="tx-amount ${tx.type}">${tx.type === 'expense' ? '-' : '+'}${fmt(tx.amount)} so'm</td>
      <td><span class="source-badge">${srcMap[tx.source] || tx.source}</span></td>
    `;
    tbody.appendChild(tr);
  });
}
function filterTx() { renderTx(); }

function renderRecent(txs) {
  const el = document.getElementById('recent-list');
  el.innerHTML = txs.length ? '' : '<div class="empty-state">Hali tranzaksiyalar yo\'q</div>';
  txs.forEach(tx => {
    const date = tx.created_at ? tx.created_at.slice(0,10) : '';
    el.innerHTML += `
      <div class="tx-row">
        <div class="tx-icon">${tx.cat_icon || (tx.type === 'income' ? '💰' : '💸')}</div>
        <div class="tx-info">
          <div class="tx-cat">${tx.cat_name || 'Boshqa'}</div>
          <div class="tx-desc">${tx.description || ''}</div>
        </div>
        <div class="tx-date">${date}</div>
        <div class="tx-amount ${tx.type}">${tx.type === 'expense' ? '-' : '+'}${fmt(tx.amount)}</div>
      </div>`;
  });
}

// ─── Calendar ────────────────────────────────────────────────────
async function loadCalendar() {
  const data = await api(`/api/calendar?year=${state.year}&month=${state.month}`);
  const dayMap = {};
  data.forEach(d => {
    const key = parseInt(d.day);
    if (!dayMap[key]) dayMap[key] = { expense: 0, income: 0 };
    dayMap[key][d.type] = d.total;
  });

  const grid = document.getElementById('calendar-grid');
  grid.innerHTML = '';
  ['Du','Se','Ch','Pa','Ju','Sh','Ya'].forEach(d => {
    grid.innerHTML += `<div class="cal-header">${d}</div>`;
  });

  const firstDay = new Date(state.year, state.month - 1, 1).getDay();
  const offset = (firstDay + 6) % 7; // Monday first
  const daysInMonth = new Date(state.year, state.month, 0).getDate();
  const today = new Date();

  for (let i = 0; i < offset; i++) grid.innerHTML += `<div class="cal-day empty"></div>`;
  for (let d = 1; d <= daysInMonth; d++) {
    const isToday = today.getDate() === d && today.getMonth() + 1 === state.month && today.getFullYear() === state.year;
    const day = dayMap[d] || {};
    const expStr = day.expense ? `<div class="cal-exp">-${fmt(day.expense)}</div>` : '';
    const incStr = day.income  ? `<div class="cal-inc">+${fmt(day.income)}</div>`  : '';
    grid.innerHTML += `
      <div class="cal-day${isToday ? ' today' : ''}">
        <div class="cal-day-num">${d}</div>
        ${expStr}${incStr}
      </div>`;
  }
}

// ─── Analytics ───────────────────────────────────────────────────
async function loadAnalytics() {
  const cats = await api(`/api/categories/stats?year=${state.year}&month=${state.month}`);
  const total = cats.reduce((s, c) => s + c.total, 0);

  // Doughnut
  const colors = ['#f87171','#fb923c','#fbbf24','#a3e635','#34d399','#7dd3fc','#818cf8','#e879f9','#94a3b8'];
  const ctx2 = document.getElementById('doughnut-chart').getContext('2d');
  if (state.charts.doughnut) state.charts.doughnut.destroy();
  state.charts.doughnut = new Chart(ctx2, {
    type: 'pie',
    data: {
      labels: cats.map(c => `${c.icon} ${c.name}`),
      datasets: [{ data: cats.map(c => c.total), backgroundColor: colors, borderWidth: 0 }]
    },
    options: { plugins: { legend: { position: 'bottom', labels: { color: '#94a3b8', boxWidth: 12 } } } }
  });

  // Bar chart
  const trend = await api('/api/trends?months=6');
  const months = [...new Set(trend.map(d => d.month))].sort();
  const ctx3 = document.getElementById('bar-chart').getContext('2d');
  if (state.charts.bar) state.charts.bar.destroy();
  state.charts.bar = new Chart(ctx3, {
    type: 'bar',
    data: {
      labels: months.map(m => MONTHS_UZ[parseInt(m.split('-')[1])-1]),
      datasets: [
        { label: 'Daromad', data: months.map(m => { const r = trend.find(d => d.month===m && d.type==='income');  return r?r.total:0; }), backgroundColor: 'rgba(74,222,128,.7)', borderRadius: 6 },
        { label: 'Xarajat', data: months.map(m => { const r = trend.find(d => d.month===m && d.type==='expense'); return r?r.total:0; }), backgroundColor: 'rgba(248,113,113,.7)', borderRadius: 6 }
      ]
    },
    options: {
      scales: {
        x: { ticks: { color: '#64748b' }, grid: { color: '#1e2535' } },
        y: { ticks: { color: '#64748b', callback: v => fmt(v) }, grid: { color: '#1e2535' } }
      },
      plugins: { legend: { labels: { color: '#94a3b8' } } }
    }
  });

  // Category breakdown bars
  const bd = document.getElementById('cat-breakdown');
  bd.innerHTML = '<h3 style="font-size:14px;color:#94a3b8;margin-bottom:14px">Kategoriyalar bo\'yicha xarajat taqsimoti</h3>';
  cats.forEach((c, i) => {
    const pct = total > 0 ? Math.round(c.total / total * 100) : 0;
    bd.innerHTML += `
      <div class="cat-item">
        <div class="cat-label">${c.icon} ${c.name}</div>
        <div class="cat-bar-wrap">
          <div class="cat-bar-bg"><div class="cat-bar" style="width:${pct}%;background:${colors[i] || '#7dd3fc'}"></div></div>
        </div>
        <div class="cat-pct">${pct}%</div>
        <div class="cat-val">${fmt(c.total)} so'm</div>
      </div>`;
  });
}

// ─── Utils ────────────────────────────────────────────────────────
function fmt(n) {
  if (!n && n !== 0) return '0';
  return Math.round(n).toLocaleString('uz-UZ');
}
