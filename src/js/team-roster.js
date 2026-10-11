// ===================================================================
// ROSTER BY SEASON (Team Explorer)
// ===================================================================
// Build a season+abbreviation -> franchise bridge from TEAM_GEO (already
// has every historical abbreviation mapped to its franchise lineage), then
// index every individual-team player-season row (excluding 2TM/3TM/etc
// combined rows) by franchise+season for the roster table.
const seasonAbbrToFranchise = new Map();
GEO.forEach(g => {
  seasonAbbrToFranchise.set(`${g.season}:${g.abbr}`, g.franchise);
});

const rosterByFranchiseSeason = new Map(); // "franchise:season" -> [player rows]

SEASONS.forEach(s => {
  if (MULTITEAM_CODES.has(s.team)) return; // skip combined rows; use individual team stints
  const franchise = seasonAbbrToFranchise.get(`${s.season}:${s.team}`);
  if (!franchise) return; // shouldn't happen given full coverage, but fail safe
  const key = `${franchise}:${s.season}`;
  if (!rosterByFranchiseSeason.has(key)) rosterByFranchiseSeason.set(key, []);
  rosterByFranchiseSeason.get(key).push(s);
});

const ROSTER_COLS = [
  { key: 'player', label: 'Player', sortable: false },
  { key: 'pos', label: 'Pos', sortable: false },
  { key: 'age', label: 'Age', sortable: true },
  { key: 'g', label: 'GP', sortable: true },
  { key: 'gs', label: 'GS', sortable: true },
  { key: 'mp', label: 'MIN', sortable: true },
  { key: 'pts', label: 'PTS', sortable: true },
  { key: 'trb', label: 'REB', sortable: true },
  { key: 'ast', label: 'AST', sortable: true },
  { key: 'fg_pct', label: 'FG%', sortable: true, isPct: true },
  { key: 'x3p_pct', label: '3P%', sortable: true, isPct: true },
  { key: 'ft_pct', label: 'FT%', sortable: true, isPct: true },
];

let rosterSortKey = 'pts';
let rosterSortDir = 'desc';
let currentRosterFranchise = null;
let currentRosterSeason = null;
let rosterInitialized = false;

function initRosterForFranchise(franchiseName) {
  const span = franchiseSpans.get(franchiseName);
  if (!span) return;
  currentRosterFranchise = franchiseName;

  const slider = $('#roster-season-slider');
  slider.min = span.minSeason;
  slider.max = span.maxSeason;
  // default to the most recent season with an actual roster (guards against
  // any edge-case season gaps in the underlying team data)
  currentRosterSeason = span.maxSeason;
  slider.value = currentRosterSeason;

  $('#roster-slider-ticks').innerHTML = `<span>${span.minSeason}</span><span>${span.maxSeason}</span>`;

  renderRosterForSeason();

  if (!rosterInitialized) {
    rosterInitialized = true;
    slider.addEventListener('input', () => {
      currentRosterSeason = parseInt(slider.value, 10);
      renderRosterForSeason();
    });
    $('#roster-search').addEventListener('input', renderRosterTable);
  }
}

let rosterToken = 0;
async function renderRosterForSeason() {
  $('#roster-season-label').textContent = currentRosterSeason;
  const span = franchiseSpans.get(currentRosterFranchise);
  const teamRowThisSeason = span.rows.find(r => r.season === currentRosterSeason);
  $('#roster-team-name-label').textContent = teamRowThisSeason ? teamRowThisSeason.team_name : '';
  const token = ++rosterToken;
  try {
    await ensureRoster(currentRosterFranchise, currentRosterSeason);
  } catch (err) {
    showDataError(err);
    return;
  }
  if (token === rosterToken) renderRosterTable();   // skip stale slider positions
}

function renderRosterTable() {
  const key = `${currentRosterFranchise}:${currentRosterSeason}`;
  let roster = rosterByFranchiseSeason.get(key) || [];

  const search = $('#roster-search').value.trim().toLowerCase();
  if (search) roster = roster.filter(p => p.player.toLowerCase().includes(search));

  roster = roster.slice().sort((a, b) => {
    const av = a[rosterSortKey] ?? -Infinity;
    const bv = b[rosterSortKey] ?? -Infinity;
    return rosterSortDir === 'desc' ? bv - av : av - bv;
  });

  $('#roster-thead').innerHTML = ROSTER_COLS.map(c =>
    `<th data-key="${c.key}" class="${c.sortable && c.key === rosterSortKey ? 'sorted' : ''}" style="${c.sortable ? '' : 'cursor:default;'}">${c.label}${c.key === rosterSortKey ? (rosterSortDir === 'desc' ? ' \u2193' : ' \u2191') : ''}</th>`
  ).join('');

  $$('#roster-thead th').forEach(th => {
    const col = ROSTER_COLS.find(c => c.key === th.dataset.key);
    if (!col || !col.sortable) return;
    th.addEventListener('click', () => {
      if (rosterSortKey === col.key) {
        rosterSortDir = rosterSortDir === 'desc' ? 'asc' : 'desc';
      } else {
        rosterSortKey = col.key;
        rosterSortDir = 'desc';
      }
      renderRosterTable();
    });
  });

  if (roster.length === 0) {
    $('#roster-tbody').innerHTML = `<tr><td colspan="${ROSTER_COLS.length}"><div class="roster-empty-note">${search ? 'No players match that filter.' : 'No roster data for this season.'}</div></td></tr>`;
    return;
  }

  $('#roster-tbody').innerHTML = roster.map(p => `
    <tr>
      <td class="name-cell" data-pid="${p.player_id}">${p.player}</td>
      <td>${p.pos || '—'}</td>
      <td>${p.age != null ? p.age : '—'}</td>
      <td>${p.g != null ? p.g : '—'}</td>
      <td>${p.gs != null ? p.gs : '—'}</td>
      <td>${fmtNum(p.mp, 1)}</td>
      <td>${fmtNum(p.pts, 1)}</td>
      <td>${fmtNum(p.trb, 1)}</td>
      <td>${fmtNum(p.ast, 1)}</td>
      <td>${p.fg_pct != null ? (p.fg_pct * 100).toFixed(2) + '%' : '—'}</td>
      <td>${p.x3p_pct != null ? (p.x3p_pct * 100).toFixed(2) + '%' : '—'}</td>
      <td>${p.ft_pct != null ? (p.ft_pct * 100).toFixed(2) + '%' : '—'}</td>
    </tr>
  `).join('');

  $$('#roster-tbody .name-cell').forEach(td => {
    td.addEventListener('click', () => {
      goToPlayer(td.dataset.pid);
    });
  });
}
