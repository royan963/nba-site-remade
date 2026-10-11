// ===================================================================
// LEADERBOARDS VIEW
// ===================================================================
const LB_STATS = [
  { key: 'pts', label: 'Points' },
  { key: 'trb', label: 'Rebounds' },
  { key: 'ast', label: 'Assists' },
  { key: 'stl', label: 'Steals' },
  { key: 'blk', label: 'Blocks' },
  { key: 'x3p', label: '3-Pointers Made' },
  { key: 'g', label: 'Games Played' },
  { key: 'ppg', label: 'Points / Game (avg)' },
  { key: 'rpg', label: 'Rebounds / Game (avg)' },
  { key: 'apg', label: 'Assists / Game (avg)' },
  { key: 'ws', label: 'Win Shares', short: 'WS', dec: 1 },
  { key: 'vorp', label: 'VORP (1974+)', short: 'VORP', dec: 1 },
  { key: 'all_star', label: 'All-Star Selections', short: 'ASG' },
];
const LB_EXTRA_COLS = { stl: 'STL', blk: 'BLK', x3p: '3PM', rpg: 'RPG', apg: 'APG', ws: 'WS', vorp: 'VORP', all_star: 'ASG' };

let lbSortKey = 'pts';
let lbSortDir = 'desc';
let lbInitialized = false;

function eraFilterPredicate(eraVal) {
  if (eraVal === 'all') return () => true;
  const [start, end] = eraVal.split('-').map(Number);
  return (p) => p.last_season >= start && p.first_season <= end;
}

function renderLbControls() {
  $('#lb-stat-select').innerHTML = LB_STATS.map(s => `<option value="${s.key}">${s.label}</option>`).join('');
  $('#lb-stat-select').value = lbSortKey;
  $('#lb-stat-select').addEventListener('change', (e) => {
    lbSortKey = e.target.value;
    renderLbTable();
  });
  $('#lb-search').addEventListener('input', renderLbTable);
  $('#lb-era-select').addEventListener('change', renderLbTable);
}

function renderLbTable() {
  const search = $('#lb-search').value.trim().toLowerCase();
  const eraVal = $('#lb-era-select').value;
  const eraPred = eraFilterPredicate(eraVal);

  let rows = CAREER.filter(p => p.g >= 1);
  if (search) rows = rows.filter(p => p.player.toLowerCase().includes(search));
  rows = rows.filter(eraPred);

  rows = rows.slice().sort((a, b) => {
    const av = a[lbSortKey] ?? -Infinity;
    const bv = b[lbSortKey] ?? -Infinity;
    return lbSortDir === 'desc' ? bv - av : av - bv;
  });

  const top = rows.slice(0, 100);

  const cols = [
    { key: 'rank', label: '#' },
    { key: 'player', label: 'Player' },
    { key: 'pos', label: 'Pos' },
    { key: 'first_season', label: 'Span' },
    { key: 'g', label: 'GP' },
    { key: 'pts', label: 'PTS' },
    { key: 'trb', label: 'REB' },
    { key: 'ast', label: 'AST' },
    { key: 'ppg', label: 'PPG' },
  ];
  // Show the stat being ranked when it isn't one of the default columns.
  const extra = LB_EXTRA_COLS[lbSortKey];
  if (extra) cols.push({ key: lbSortKey, label: extra });
  const extraCell = p => {
    if (!extra) return '';
    const v = p[lbSortKey];
    return `<td>${['rpg', 'apg', 'ws', 'vorp'].includes(lbSortKey) ? fmtNum(v, 1) : fmtInt(v)}</td>`;
  };

  $('#lb-thead').innerHTML = cols.map(c =>
    `<th data-key="${c.key}" class="${c.key === lbSortKey ? 'sorted' : ''}">${c.label}${c.key === lbSortKey ? (lbSortDir === 'desc' ? ' ↓' : ' ↑') : ''}</th>`
  ).join('');

  $$('#lb-thead th').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.key;
      if (key === 'rank' || key === 'player' || key === 'pos') return;
      if (lbSortKey === key) {
        lbSortDir = lbSortDir === 'desc' ? 'asc' : 'desc';
      } else {
        lbSortKey = key;
        lbSortDir = 'desc';
      }
      $('#lb-stat-select').value = LB_STATS.find(s => s.key === lbSortKey) ? lbSortKey : $('#lb-stat-select').value;
      renderLbTable();
    });
  });

  $('#lb-tbody').innerHTML = top.map((p, i) => `
    <tr>
      <td class="rank-cell">${i + 1}</td>
      <td class="name-cell" data-pid="${p.player_id}">${p.player}${p.hof ? '<span class="hof-badge">HOF</span>' : ''}</td>
      <td>${p.pos || '—'}</td>
      <td>${p.first_season}–${p.last_season}</td>
      <td>${fmtInt(p.g)}</td>
      <td>${fmtInt(p.pts)}</td>
      <td>${fmtInt(p.trb)}</td>
      <td>${fmtInt(p.ast)}</td>
      <td>${fmtNum(p.ppg, 1)}</td>
      ${extraCell(p)}
    </tr>
  `).join('');

  $$('#lb-tbody .name-cell').forEach(td => {
    td.addEventListener('click', () => {
      goToPlayer(td.dataset.pid);
    });
  });
}

function initLeadersView() {
  if (lbInitialized) return;
  lbInitialized = true;
  renderLbControls();
  renderLbTable();
}

function goToPlayer(playerId) {
  $$('.tab-btn').forEach(b => b.classList.remove('active'));
  $$('.view').forEach(v => v.classList.remove('active'));
  $('.tab-btn[data-view="players"]').classList.add('active');
  $('#view-players').classList.add('active');
  selectPlayer(playerId);
}
