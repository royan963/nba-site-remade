// ===================================================================
// PLAYER EXPLORER VIEW
// ===================================================================
const PLAYER_STAT_OPTIONS = [
  { key: 'pts', label: 'Points/Game' },
  { key: 'trb', label: 'Rebounds/Game' },
  { key: 'ast', label: 'Assists/Game' },
  { key: 'stl', label: 'Steals/Game' },
  { key: 'blk', label: 'Blocks/Game' },
  { key: 'fg_pct', label: 'FG%' },
  { key: 'x3p_pct', label: '3P%' },
  { key: 'mp', label: 'Minutes/Game' },
  { key: 'ts_pct', label: 'TS%' },
  { key: 'per', label: 'PER' },
  { key: 'usg_pct', label: 'Usage %' },
  { key: 'ws', label: 'Win Shares' },
  { key: 'bpm', label: 'BPM' },
  { key: 'vorp', label: 'VORP' },
];
let currentPlayerStat = 'pts';
let playerChart = null;
let currentPlayerId = null;

// notable default list: top 300 by career pts + all HOF
const notablePlayerIds = new Set();
CAREER.slice().sort((a, b) => (b.pts || 0) - (a.pts || 0)).slice(0, 300).forEach(p => notablePlayerIds.add(p.player_id));
CAREER.filter(p => p.hof).forEach(p => notablePlayerIds.add(p.player_id));
const notablePlayers = CAREER.filter(p => notablePlayerIds.has(p.player_id))
  .sort((a, b) => (b.pts || 0) - (a.pts || 0));

function renderPlayerSuggestions() {
  const picks = ['jamesle01', 'jordami01', 'abdulka01', 'birdla01', 'curryst01', 'duncati01'];
  const found = picks.map(id => careerById.get(id)).filter(Boolean);
  $('#player-suggestions').innerHTML = found.map(p =>
    `<button class="pill-btn" data-pid="${p.player_id}">${p.player}</button>`
  ).join('');
  $$('#player-suggestions .pill-btn').forEach(btn => {
    btn.addEventListener('click', () => selectPlayer(btn.dataset.pid));
  });
}

const searchInput = $('#player-search');
const searchResults = $('#player-search-results');

// Strip diacritics for comparison only (display names keep accents) so
// typing "jokic" or "doncic" finds "Jokić" / "Dončić" etc.
function normalizeForSearch(str) {
  return str.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}
const playerSearchKey = new Map(CAREER.map(p => [p.player_id, normalizeForSearch(p.player)]));

searchInput.addEventListener('input', () => {
  const q = normalizeForSearch(searchInput.value.trim());
  if (!q) {
    searchResults.classList.remove('show');
    return;
  }
  let matches;
  if (q.length < 2) {
    matches = notablePlayers.filter(p => playerSearchKey.get(p.player_id).startsWith(q)).slice(0, 12);
  } else {
    matches = CAREER.filter(p => playerSearchKey.get(p.player_id).includes(q)).slice(0, 30);
    matches.sort((a, b) => (b.pts || 0) - (a.pts || 0));
    matches = matches.slice(0, 12);
  }
  if (matches.length === 0) {
    searchResults.innerHTML = `<div class="psr-item" style="cursor:default;color:var(--chalk-dim);">No players found</div>`;
    searchResults.classList.add('show');
    return;
  }
  searchResults.innerHTML = matches.map(p => `
    <div class="psr-item" data-pid="${p.player_id}">
      <span>${p.player}${p.hof ? '<span class="hof-badge">HOF</span>' : ''}</span>
      <span class="psr-meta">${p.first_season}–${p.last_season}</span>
    </div>
  `).join('');
  $$('.psr-item', searchResults).forEach(item => {
    item.addEventListener('click', () => {
      if (!item.dataset.pid) return;
      const player = careerById.get(item.dataset.pid);
      selectPlayer(item.dataset.pid);
      searchInput.value = player ? player.player : '';
      searchResults.classList.remove('show');
    });
  });
  searchResults.classList.add('show');
});

document.addEventListener('click', (e) => {
  if (!searchResults.contains(e.target) && e.target !== searchInput) {
    searchResults.classList.remove('show');
  }
});

function renderPlayerStatPills() {
  $('#pc-stat-pills').innerHTML = PLAYER_STAT_OPTIONS.map(s =>
    `<button class="pill-btn ${s.key === currentPlayerStat ? 'active' : ''}" data-stat="${s.key}">${s.label}</button>`
  ).join('');
  $$('#pc-stat-pills .pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      currentPlayerStat = btn.dataset.stat;
      $$('#pc-stat-pills .pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderPlayerChart(currentPlayerId);
    });
  });
}

let selectPlayerToken = 0;
async function selectPlayer(playerId) {
  const player = careerById.get(playerId);
  if (!player) return;
  const token = ++selectPlayerToken;
  try {
    await ensurePlayers([playerId]);
  } catch (err) {
    showDataError(err);
    return;
  }
  if (token !== selectPlayerToken) return;   // a newer selection won the race
  currentPlayerId = playerId;

  $('#player-empty').style.display = 'none';
  $('#player-card').classList.add('show');

  $('#pc-name').innerHTML = player.player + (player.hof ? '<span class="hof-badge">Hall of Fame</span>' : '');
  const heightStr = player.ht_in_in ? `${Math.floor(player.ht_in_in / 12)}'${player.ht_in_in % 12}"` : '—';
  const draft = draftLine(playerId);
  $('#pc-meta').innerHTML = `${player.pos || '—'} · ${player.first_season}–${player.last_season} (${player.seasons_played} seasons) · ${heightStr}${player.wt ? `, ${player.wt} lb` : ''}${draft ? `<br>${draft}` : ''}`;

  const stats = [
    { l: 'Games', v: fmtInt(player.g) },
    { l: 'Points', v: fmtInt(player.pts) },
    { l: 'Rebounds', v: fmtInt(player.trb) },
    { l: 'Assists', v: fmtInt(player.ast) },
    { l: 'PPG', v: fmtNum(player.ppg, 1) },
    { l: 'RPG', v: fmtNum(player.rpg, 1) },
    { l: 'APG', v: fmtNum(player.apg, 1) },
    { l: 'All-Star', v: player.all_star ? player.all_star + '×' : '—' },
    { l: 'Win Shares', v: fmtNum(player.ws, 1) },
  ];
  $('#pc-stats').innerHTML = stats.map(s => `<div class="ps-cell"><div class="v">${s.v}</div><div class="l">${s.l}</div></div>`).join('');

  renderPlayerStatPills();
  renderPlayerChart(playerId);
  renderAdvancedPanel(playerId);
  renderSimilarPlayers(playerId);
  renderAwardsTimeline(playerId);
  renderShotProfile(playerId);
  renderPositionAndPbp(playerId);

  $('#view-players').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// Shooting percentages are stored as fractions (0.393) and plotted as 39.3.
const PERCENT_STAT_KEYS = new Set(['fg_pct', 'x3p_pct', 'ts_pct']);

function formatPlayerStatValue(statKey, chartValue) {
  if (chartValue == null) return '—';
  if (PERCENT_STAT_KEYS.has(statKey)) return chartValue.toFixed(2) + '%';
  if (statKey === 'bpm') return (chartValue > 0 ? '+' : '') + chartValue.toFixed(1);
  return chartValue.toFixed(1);
}

function renderPlayerChart(playerId) {
  const seasons = seasonsByPlayer.get(playerId) || [];
  const statDef = PLAYER_STAT_OPTIONS.find(s => s.key === currentPlayerStat);
  const isPercentStat = PERCENT_STAT_KEYS.has(currentPlayerStat);
  const labels = seasons.map(s => s.season);
  const data = seasons.map(s => s[currentPlayerStat] == null ? null : (isPercentStat ? s[currentPlayerStat] * 100 : s[currentPlayerStat]));

  const ctx = $('#player-chart').getContext('2d');
  if (playerChart) playerChart.destroy();
  playerChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: statDef.label,
        data,
        borderColor: PALETTE.amber,
        backgroundColor: PALETTE.amberDim,
        tension: 0.3,
        pointRadius: 3,
        pointBackgroundColor: PALETTE.amber,
        pointHoverRadius: 6,
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
            label: (ctx) => `${statDef.label}: ${formatPlayerStatValue(currentPlayerStat, ctx.parsed.y)}`,
            afterTitle: (items) => {
              const s = seasons[items[0].dataIndex];
              return `${s.team || ''}${s.age ? ' · age ' + s.age : ''}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim } },
        y: {
          grid: { color: PALETTE.grid },
          ticks: {
            color: PALETTE.chalkDim,
            callback: (v) => isPercentStat ? v.toFixed(2) + '%' : v
          }
        }
      }
    })
  });
}

renderPlayerSuggestions();
