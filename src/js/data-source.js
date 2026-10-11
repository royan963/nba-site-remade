// ===================================================================
// DATA SOURCE
// In this static build every dataset is embedded, so the ensure*() functions
// below resolve immediately. They also support loading per-player data from
// the API on demand (DATA_MODE = 'api'); the full-stack site is now the React
// app in frontend/, which talks to the API directly.
// ===================================================================
const DATA_MODE = window.NBA_DATA_MODE || 'static';
const API_BASE = (window.NBA_API_BASE || '').replace(/\/$/, '');

async function apiGet(path) {
  const res = await fetch(`${API_BASE}/api/v1${path}`);
  if (!res.ok) throw new Error(`API ${res.status} for ${path}`);
  return res.json();
}

function showDataError(err) {
  console.error(err);
  let bar = document.getElementById('data-error');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'data-error';
    bar.className = 'data-error';
    document.body.prepend(bar);
  }
  bar.textContent = `Couldn't load data from the API (${err.message}). Check that the server is running and refresh.`;
}

// ---- players ---------------------------------------------------------------
const loadedPlayers = new Set();
const playerRequests = new Map();

async function ensurePlayers(ids) {
  if (DATA_MODE !== 'api') return;
  const needed = [...new Set(ids)].filter(id => id && !loadedPlayers.has(id));
  await Promise.all(needed.map(id => {
    if (!playerRequests.has(id)) {
      playerRequests.set(id, apiGet(`/players/${encodeURIComponent(id)}/bundle`)
        .then(registerPlayerBundle)
        .catch(err => { playerRequests.delete(id); throw err; }));
    }
    return playerRequests.get(id);
  }));
}

// Mirrors the startup indexing in core.js, extended-data.js and
// player-data.js for a single player.
function registerPlayerBundle(b) {
  const pid = b.player.player_id;
  const seasons = b.seasons.slice().sort((x, y) => x.season - y.season);

  stintsByPlayer.set(pid, seasons.filter(s => !MULTITEAM_CODES.has(s.team)));
  const bySeason = new Map();
  seasons.forEach(s => {
    if (!bySeason.has(s.season) || MULTITEAM_CODES.has(s.team)) bySeason.set(s.season, s);
  });
  const adv = new Map(b.advanced.map(a => [a.season, a]));
  const p100 = new Map(b.per100.map(r => [r.season, r]));
  const combined = [...bySeason.values()].sort((x, y) => x.season - y.season);
  combined.forEach(s => {
    const a = adv.get(s.season);
    ADV_FIELDS.forEach(f => { s[f] = a ? a[f] : null; });
    s.per100 = p100.get(s.season) || null;
  });
  seasonsByPlayer.set(pid, combined);

  shootingByPlayer.set(pid, b.shooting);
  pbpByPlayer.set(pid, b.pbp);
  awardsByPlayer.set(pid, b.awards);
  eosByPlayer.set(pid, b.eos);
  allStarByPlayer.set(pid, new Set(b.all_stars.map(a => a.season)));
  if (b.draft.length) draftByPlayer.set(pid, b.draft.sort((x, y) => x.season - y.season)[b.draft.length - 1]);
  if (b.similar.features) SIMILAR_PLAYERS.players[pid] = b.similar.features;
  SIMILAR_PLAYERS.neighbors[pid] = b.similar.neighbors;
  loadedPlayers.add(pid);
}

// ---- rosters ---------------------------------------------------------------
const loadedRosters = new Set();

async function ensureRoster(franchise, season) {
  if (DATA_MODE !== 'api') return;
  const key = `${franchise}:${season}`;
  if (loadedRosters.has(key)) return;
  const rows = await apiGet(`/teams/${encodeURIComponent(franchise)}/roster/${season}`);
  rosterByFranchiseSeason.set(key, rows);
  loadedRosters.add(key);
}

// ---- team honors (awards / All-NBA / All-Star won by a franchise's roster) --
const teamHonorsCache = new Map();

async function ensureTeamHonors(franchises) {
  if (DATA_MODE !== 'api') return;
  await Promise.all(franchises.filter(f => f && !teamHonorsCache.has(f)).map(async f => {
    const h = await apiGet(`/teams/${encodeURIComponent(f)}/honors`);
    teamHonorsCache.set(f, { wins: h.awards, eos: h.all_league_teams, allStars: h.all_stars });
  }));
}
