// ─── State ────────────────────────────────────────────────────────
const S = {
  uid: null, year: new Date().getFullYear(),
  month: new Date().getMonth() + 1,
  tab: 'overview', charts: {}, allTx: []
};

const MO = ['Yanvar','Fevral','Mart','Aprel','May','Iyun',
            'Iyul','Avgust','Sentabr','Oktabr','Noyabr','Dekabr'];

const CHART_COLORS = [
  '#00E5A0','#00D9FF','#A855F7','#FFB800',
  '#FF4D6A','#FB923C','#34D399','#818CF8','#64748B'
];

// ─── Init ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Telegram WebApp
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }
  const tgUser = tg?.initDataUnsafe?.user;
  if (tgUser?.id) { S.uid = tgUser.id; }
  if (!S.uid) { S.uid = new URLSearchParams(location.search).get('uid'); }
  if (!S.uid) { S.uid = prompt('Telegram user ID:'); }
  if (!S.uid) {
    document.body.innerHTML = '<p style="padding:40px;color:#FF4D6A;font-family:Inter,sans-serif">Telegram orqali oching yoki ?uid= qo\'shing.</p>';
    return;
  }
  document.getElementById('uid-display').textContent = `#${S.uid}`;
  updateMonthLabel();

  document.querySelectorAll('.nav-item').forEach(el =>
    el.addEventListener('click', e => { e.preventDefault(); switchTab(el.dataset.tab); })
  );
  document.getElementById('prev-month').addEventListener('click', () => changeMonth(-1));
  document.getElementById('next-month').addEventListener('click', () => changeMonth(1));
  document.getElementById('tx-search').addEventListener('input', renderTx);
  document.getElementById('tx-type').addEventListener('change', renderTx);

  // Chart.js global defaults — dark theme
  Chart.defaults.color = '#475569';
  Chart.defaults.borderColor = 'rgba(255,255,255,0.05)';
  Chart.defaults.font.family = 'Inter, Segoe UI, sans-serif';
  Chart.defaults.font.size = 12;

  loadAll();
});

function updateMonthLabel() {
  document.getElementById('month-label').textContent = `${MO[S.month-1]} ${S.year}`;
}
function changeMonth(d) {
  S.month += d;
  if (S.month > 12) { S.month = 1; S.year++; }
  if (S.month < 1)  { S.month = 12; S.year--; }
  updateMonthLabel();
  loadAll();
}
function switchTab(tab) {
  S.tab = tab;
  document.querySelectorAll('.nav-item').forEach(el => el.classList.toggle('active', el.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(el => el.classList.toggle('active', el.id === `tab-${tab}`));
  if (tab === 'calendar')     loadCalendar();
  if (tab === 'analytics')    loadAnalytics();
  if (tab === 'transactions') renderTx();
  if (tab === 'family')       loadFamily();
}

// ─── API ──────────────────────────────────────────────────────────
async function get(path, extra = '') {
  const r = await fetch(`${path}?uid=${S.uid}${extra}`);
  return r.json();
}

// ─── Load ─────────────────────────────────────────────────────────
async function loadAll() {
  await Promise.all([loadUser(), loadSummary(), loadTransactions()]);
  if (S.tab === 'calendar')  loadCalendar();
  if (S.tab === 'analytics') loadAnalytics();
}

async function loadUser() {
  const u = await get('/api/user');
  if (u.error) return;
  S.user = u;
  document.getElementById('user-name').textContent = u.name || 'Foydalanuvchi';
  document.getElementById('user-budget').textContent =
    u.monthly_income ? `Byudjet: ${fmt(u.monthly_income)} so'm` : 'Byudjet yo\'q';

  // Show family tab only if user is in a family
  const familyNav = document.getElementById('family-nav');
  if (u.is_family && u.family_members?.length > 1) {
    familyNav.style.display = 'flex';
  }
}

async function loadSummary() {
  const s = await get('/api/summary', `&year=${S.year}&month=${S.month}`);
  document.getElementById('c-income').textContent  = fmt(s.income)  + ' so\'m';
  document.getElementById('c-expense').textContent = fmt(s.expense) + ' so\'m';
  const bal = s.balance;
  const balEl = document.getElementById('c-balance');
  balEl.textContent = (bal >= 0 ? '+' : '') + fmt(bal) + ' so\'m';
  balEl.style.color = bal >= 0 ? 'var(--green)' : 'var(--red)';
  document.getElementById('c-budget-pct').textContent = s.budget_used_pct + '%';

  await loadCatPie();
  await loadTrendLine();
}

async function loadTransactions() {
  S.allTx = await get('/api/transactions', `&year=${S.year}&month=${S.month}&limit=200`);
  renderTx();
  renderRecent(S.allTx.slice(0, 7));
}

// ─── Pie Chart ────────────────────────────────────────────────────
async function loadCatPie() {
  const data = await get('/api/categories/stats', `&year=${S.year}&month=${S.month}`);
  if (!data.length) return;
  const ctx = document.getElementById('pie-chart').getContext('2d');
  if (S.charts.pie) S.charts.pie.destroy();
  S.charts.pie = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(d => `${d.icon} ${d.name}`),
      datasets: [{
        data: data.map(d => d.total),
        backgroundColor: CHART_COLORS,
        borderWidth: 0,
        hoverOffset: 6
      }]
    },
    options: {
      cutout: '68%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#64748B', boxWidth: 10, padding: 12, font: { size: 11 } }
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${fmt(ctx.parsed)} so'm`
          }
        }
      },
      animation: { animateRotate: true, duration: 800 }
    }
  });
}

// ─── Trend Line ───────────────────────────────────────────────────
async function loadTrendLine() {
  const data = await get('/api/trends', '&months=6');
  const months = [...new Set(data.map(d => d.month))].sort();
  const labels = months.map(m => MO[parseInt(m.split('-')[1]) - 1]);
  const income  = months.map(m => data.find(d => d.month===m && d.type==='income')?.total  || 0);
  const expense = months.map(m => data.find(d => d.month===m && d.type==='expense')?.total || 0);

  const ctx = document.getElementById('trend-chart').getContext('2d');
  const gradGreen = ctx.createLinearGradient(0, 0, 0, 220);
  gradGreen.addColorStop(0, 'rgba(0,229,160,0.25)');
  gradGreen.addColorStop(1, 'rgba(0,229,160,0)');
  const gradRed = ctx.createLinearGradient(0, 0, 0, 220);
  gradRed.addColorStop(0, 'rgba(255,77,106,0.2)');
  gradRed.addColorStop(1, 'rgba(255,77,106,0)');

  if (S.charts.trend) S.charts.trend.destroy();
  S.charts.trend = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Daromad', data: income,  borderColor: '#00E5A0', backgroundColor: gradGreen, tension: 0.4, fill: true, pointRadius: 4, pointBackgroundColor: '#00E5A0' },
        { label: 'Xarajat', data: expense, borderColor: '#FF4D6A', backgroundColor: gradRed,   tension: 0.4, fill: true, pointRadius: 4, pointBackgroundColor: '#FF4D6A' }
      ]
    },
    options: {
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#475569' } },
        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#475569', callback: v => fmt(v) } }
      },
      plugins: {
        legend: { labels: { color: '#64748B', boxWidth: 10 } },
        tooltip: { callbacks: { label: ctx => ` ${fmt(ctx.parsed.y)} so'm` } }
      },
      animation: { duration: 800 }
    }
  });
}

// ─── Recent ───────────────────────────────────────────────────────
function renderRecent(txs) {
  const el = document.getElementById('recent-list');
  if (!txs.length) { el.innerHTML = '<div class="empty-state">Hali tranzaksiya yo\'q</div>'; return; }
  el.innerHTML = txs.map(tx => `
    <div class="tx-row">
      <div class="tx-icon">${tx.cat_icon || (tx.type==='income' ? '💰' : '💸')}</div>
      <div class="tx-info">
        <div class="tx-cat">${tx.cat_name || 'Boshqa'}</div>
        <div class="tx-desc">${tx.description || '—'}</div>
      </div>
      <div class="tx-right">
        <div class="tx-amount ${tx.type}">${tx.type==='expense' ? '-' : '+'}${fmt(tx.amount)}</div>
        <div class="tx-date">${(tx.created_at||'').slice(0,10)}</div>
      </div>
    </div>`).join('');
}

// ─── Transactions Table ───────────────────────────────────────────
function renderTx() {
  const q = document.getElementById('tx-search').value.toLowerCase();
  const t = document.getElementById('tx-type').value;
  const rows = S.allTx.filter(tx =>
    (!t || tx.type === t) &&
    (!q || (tx.description||'').toLowerCase().includes(q) || (tx.cat_name||'').toLowerCase().includes(q))
  );
  const srcMap = { text: '✏️', voice: '🎤', receipt: '📷' };
  document.getElementById('tx-empty').style.display = rows.length ? 'none' : 'block';
  document.getElementById('tx-body').innerHTML = rows.map(tx => `
    <tr>
      <td>${(tx.created_at||'').slice(0,10)}</td>
      <td><span class="badge ${tx.type}">${tx.cat_icon||''} ${tx.cat_name||'Boshqa'}</span></td>
      <td>${tx.description || '—'}</td>
      <td class="tx-amount ${tx.type}" style="font-weight:700">${tx.type==='expense'?'-':'+'}${fmt(tx.amount)} so'm</td>
      <td><span class="src-icon" title="${tx.source}">${srcMap[tx.source]||'✏️'}</span></td>
    </tr>`).join('');
}

// ─── Calendar ─────────────────────────────────────────────────────
async function loadCalendar() {
  const data = await get('/api/calendar', `&year=${S.year}&month=${S.month}`);
  const map = {};
  data.forEach(d => {
    const k = parseInt(d.day);
    if (!map[k]) map[k] = { expense: 0, income: 0 };
    map[k][d.type] = d.total;
  });
  const grid = document.getElementById('calendar-grid');
  grid.innerHTML = ['Du','Se','Ch','Pa','Ju','Sh','Ya']
    .map(d => `<div class="cal-header">${d}</div>`).join('');

  const first = (new Date(S.year, S.month-1, 1).getDay() + 6) % 7;
  const days  = new Date(S.year, S.month, 0).getDate();
  const today = new Date();

  for (let i = 0; i < first; i++) grid.innerHTML += `<div class="cal-day empty"></div>`;
  for (let d = 1; d <= days; d++) {
    const isTd = today.getDate()===d && today.getMonth()+1===S.month && today.getFullYear()===S.year;
    const day = map[d] || {};
    grid.innerHTML += `
      <div class="cal-day${isTd?' today':''}">
        <div class="cal-day-num">${d}</div>
        ${day.expense ? `<div class="cal-exp">-${fmt(day.expense)}</div>` : ''}
        ${day.income  ? `<div class="cal-inc">+${fmt(day.income)}</div>`  : ''}
      </div>`;
  }
}

// ─── Analytics ────────────────────────────────────────────────────
async function loadAnalytics() {
  const cats  = await get('/api/categories/stats', `&year=${S.year}&month=${S.month}`);
  const trend = await get('/api/trends', '&months=6');

  // Doughnut
  const ctx1 = document.getElementById('doughnut-chart').getContext('2d');
  if (S.charts.doughnut) S.charts.doughnut.destroy();
  S.charts.doughnut = new Chart(ctx1, {
    type: 'doughnut',
    data: {
      labels: cats.map(c => `${c.icon} ${c.name}`),
      datasets: [{ data: cats.map(c => c.total), backgroundColor: CHART_COLORS, borderWidth: 0, hoverOffset: 6 }]
    },
    options: {
      cutout: '65%',
      plugins: {
        legend: { position: 'right', labels: { color: '#64748B', boxWidth: 10, font: { size: 11 } } },
        tooltip: { callbacks: { label: c => ` ${fmt(c.parsed)} so'm` } }
      }
    }
  });

  // Bar
  const months  = [...new Set(trend.map(d => d.month))].sort();
  const ctx2    = document.getElementById('bar-chart').getContext('2d');
  if (S.charts.bar) S.charts.bar.destroy();
  S.charts.bar = new Chart(ctx2, {
    type: 'bar',
    data: {
      labels: months.map(m => MO[parseInt(m.split('-')[1])-1]),
      datasets: [
        { label: 'Daromad', data: months.map(m => trend.find(d=>d.month===m&&d.type==='income')?.total||0),
          backgroundColor: 'rgba(0,229,160,0.7)', borderRadius: 6, borderSkipped: false },
        { label: 'Xarajat', data: months.map(m => trend.find(d=>d.month===m&&d.type==='expense')?.total||0),
          backgroundColor: 'rgba(255,77,106,0.7)', borderRadius: 6, borderSkipped: false }
      ]
    },
    options: {
      scales: {
        x: { grid: { display: false }, ticks: { color: '#475569' } },
        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#475569', callback: v => fmt(v) } }
      },
      plugins: { legend: { labels: { color: '#64748B', boxWidth: 10 } } }
    }
  });

  // Category bars
  const total = cats.reduce((s,c)=>s+c.total,0);
  const bd = document.getElementById('cat-breakdown');
  bd.innerHTML = '<h3>Kategoriyalar bo\'yicha taqsimot</h3>';
  cats.forEach((c, i) => {
    const pct = total > 0 ? Math.round(c.total/total*100) : 0;
    bd.innerHTML += `
      <div class="cat-item">
        <div class="cat-label">${c.icon} ${c.name}</div>
        <div class="cat-bar-wrap">
          <div class="cat-bar-bg">
            <div class="cat-bar" style="width:${pct}%;background:${CHART_COLORS[i]||'#64748B'}"></div>
          </div>
        </div>
        <div class="cat-pct">${pct}%</div>
        <div class="cat-val">-${fmt(c.total)}</div>
      </div>`;
  });
}

// ─── Family ───────────────────────────────────────────────────────
async function loadFamily() {
  const members = await get('/api/members', `&year=${S.year}&month=${S.month}`);
  if (!members.length) {
    document.getElementById('family-header').innerHTML =
      '<div class="empty-state">Oila a\'zolari yo\'q. Botda /invite yuboring.</div>';
    return;
  }

  const myName = S.user?.name || '';

  // Member cards
  document.getElementById('family-header').innerHTML = members.map((m, i) => {
    const letter = (m.first_name || '?')[0].toUpperCase();
    const isMe   = m.first_name === myName;
    return `
      <div class="member-card">
        <div class="member-avatar">${letter}</div>
        <div class="member-info">
          <div class="member-name">${m.first_name || '?'}</div>
          <div class="member-exp">💸 ${fmt(m.expense)} so'm</div>
          <div class="member-inc">💰 ${fmt(m.income)} so'm</div>
          ${isMe ? '<div class="member-you">● Siz</div>' : ''}
        </div>
      </div>`;
  }).join('');

  // Bar chart — per member expense
  const ctx1 = document.getElementById('member-bar-chart').getContext('2d');
  if (S.charts.memberBar) S.charts.memberBar.destroy();
  S.charts.memberBar = new Chart(ctx1, {
    type: 'bar',
    data: {
      labels: members.map(m => m.first_name || '?'),
      datasets: [
        { label: 'Xarajat', data: members.map(m => m.expense),
          backgroundColor: members.map((_, i) => CHART_COLORS[i] || '#64748B'),
          borderRadius: 8, borderSkipped: false },
        { label: 'Daromad', data: members.map(m => m.income),
          backgroundColor: 'rgba(0,229,160,0.25)',
          borderRadius: 8, borderSkipped: false }
      ]
    },
    options: {
      scales: {
        x: { grid: { display: false }, ticks: { color: '#475569' } },
        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#475569', callback: v => fmt(v) } }
      },
      plugins: { legend: { labels: { color: '#64748B', boxWidth: 10 } } }
    }
  });

  // Pie chart — share of expense
  const ctx2 = document.getElementById('member-pie-chart').getContext('2d');
  if (S.charts.memberPie) S.charts.memberPie.destroy();
  S.charts.memberPie = new Chart(ctx2, {
    type: 'doughnut',
    data: {
      labels: members.map(m => m.first_name || '?'),
      datasets: [{
        data: members.map(m => m.expense),
        backgroundColor: CHART_COLORS,
        borderWidth: 0, hoverOffset: 6
      }]
    },
    options: {
      cutout: '65%',
      plugins: {
        legend: { position: 'bottom', labels: { color: '#64748B', boxWidth: 10, font: { size: 11 } } },
        tooltip: { callbacks: { label: c => ` ${fmt(c.parsed)} so'm` } }
      }
    }
  });

  // Breakdown list
  const totalExp = members.reduce((s, m) => s + m.expense, 0);
  const bd = document.getElementById('member-breakdown');
  bd.innerHTML = '<h3>A\'zo bo\'yicha xarajat taqsimoti</h3>';
  members.forEach((m, i) => {
    const pct = totalExp > 0 ? Math.round(m.expense / totalExp * 100) : 0;
    bd.innerHTML += `
      <div class="cat-item">
        <div class="cat-label" style="width:160px">${CHART_COLORS[i] ? `<span style="color:${CHART_COLORS[i]}">●</span>` : ''} ${m.first_name || '?'}</div>
        <div class="cat-bar-wrap">
          <div class="cat-bar-bg">
            <div class="cat-bar" style="width:${pct}%;background:${CHART_COLORS[i]||'#64748B'}"></div>
          </div>
        </div>
        <div class="cat-pct">${pct}%</div>
        <div class="cat-val">-${fmt(m.expense)}</div>
      </div>`;
  });
}

// ─── Utils ────────────────────────────────────────────────────────
function fmt(n) {
  if (!n && n !== 0) return '0';
  return Math.round(n).toLocaleString('uz-UZ');
}
