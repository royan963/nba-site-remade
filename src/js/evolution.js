// ===================================================================
// ERA EVOLUTION VIEW
// ===================================================================
const EVO_STATS = [
  { key: 'pace', label: 'Pace', fmt: v => fmtNum(v, 1) },
  { key: 'pts_per_game', label: 'Points/Game', fmt: v => fmtNum(v, 1) },
  { key: 'o_rtg', label: 'Off. Rating', fmt: v => fmtNum(v, 1) },
  { key: 'x3p_ar', label: '3PA Rate', fmt: v => fmtPct(v) },
  { key: 'x3p_percent', label: '3P%', fmt: v => fmtPct(v) },
  { key: 'fg_percent', label: 'FG%', fmt: v => fmtPct(v) },
  { key: 'ast_per_game', label: 'Assists/Game', fmt: v => fmtNum(v, 1) },
  { key: 'orb_per_game', label: 'Off. Rebounds/Game', fmt: v => fmtNum(v, 1) },
  { key: 'ts_percent', label: 'True Shooting %', fmt: v => fmtPct(v) },
];

let currentEvoStat = 'pace';
let evolutionChart = null;
let evoInitialized = false;

function renderEvoPills() {
  $('#evo-stat-pills').innerHTML = EVO_STATS.map(s =>
    `<button class="pill-btn ${s.key === currentEvoStat ? 'active' : ''}" data-stat="${s.key}">${s.label}</button>`
  ).join('');
  $$('#evo-stat-pills .pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      currentEvoStat = btn.dataset.stat;
      $$('#evo-stat-pills .pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderEvolutionChart();
    });
  });
}

function renderEvolutionChart() {
  const stat = EVO_STATS.find(s => s.key === currentEvoStat);
  const labels = ERA.map(e => e.season);
  const data = ERA.map(e => e[currentEvoStat]);
  const ctx = $('#evolution-chart').getContext('2d');
  if (evolutionChart) evolutionChart.destroy();
  evolutionChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: stat.label,
        data,
        borderColor: PALETTE.amber,
        backgroundColor: PALETTE.amberDim,
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: 5,
        borderWidth: 2.5,
        fill: true,
      }]
    },
    options: baseChartOptions({
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1f1a16', borderColor: 'rgba(241,235,224,0.18)', borderWidth: 1,
          titleColor: PALETTE.amber, bodyColor: PALETTE.chalk,
          titleFont: { family: "'JetBrains Mono', monospace", size: 12 },
          bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
          callbacks: {
            label: (ctx) => stat.fmt(ctx.parsed.y)
          }
        }
      },
      scales: {
        x: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, maxTicksLimit: 14 } },
        y: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, callback: (v) => stat.fmt(v) } }
      }
    })
  });
}

let threePtChart = null, ortgChart = null;
function renderSmallCharts() {
  const labels = ERA.map(e => e.season);

  const ctx1 = $('#three-pt-chart').getContext('2d');
  if (threePtChart) threePtChart.destroy();
  threePtChart = new Chart(ctx1, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: '3PA Rate',
        data: ERA.map(e => e.x3p_ar),
        borderColor: PALETTE.wood,
        backgroundColor: 'rgba(217,154,92,0.12)',
        tension: 0.25, pointRadius: 0, borderWidth: 2, fill: true,
      }]
    },
    options: baseChartOptions({
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtPct(ctx.parsed.y) } } },
      scales: {
        x: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, maxTicksLimit: 8 } },
        y: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, callback: v => fmtPct(v, 0) } }
      }
    })
  });

  const ctx2 = $('#ortg-chart').getContext('2d');
  if (ortgChart) ortgChart.destroy();
  ortgChart = new Chart(ctx2, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Off. Rating', data: ERA.map(e => e.o_rtg), borderColor: PALETTE.amber, tension: 0.25, pointRadius: 0, borderWidth: 2 },
        { label: 'Def. Rating', data: ERA.map(e => e.d_rtg), borderColor: PALETTE.blue, tension: 0.25, pointRadius: 0, borderWidth: 2 },
      ]
    },
    options: baseChartOptions({
      scales: {
        x: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, maxTicksLimit: 8 } },
        y: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim } }
      }
    })
  });
}

function initEvolutionView() {
  if (evoInitialized) return;
  evoInitialized = true;
  renderEvoPills();
  renderEvolutionChart();
  renderSmallCharts();
}
