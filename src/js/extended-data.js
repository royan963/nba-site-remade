// ===================================================================
// EXTENDED DATA: advanced stats, per-100, All-Star, draft, league
// environment. Loaded right after core.js so every view can use it.
// ===================================================================
const ADVANCED = toObjects(PLAYER_ADVANCED);
const PER100 = toObjects(PLAYER_PER100);
const ALL_STARS = toObjects(ALL_STAR_SELECTIONS);
const DRAFTS = toObjects(DRAFT_PICKS);
const envBySeason = new Map(toObjects(LEAGUE_ENV).map(e => [e.season, e]));

// Merge advanced metrics onto the one-row-per-season records so charts and
// comparisons can read e.g. row.per or row.bpm directly.
const ADV_FIELDS = ['per', 'ts_pct', 'usg_pct', 'ws', 'ws_48', 'obpm', 'dbpm', 'bpm', 'vorp'];
{
  const advByKey = new Map(ADVANCED.map(a => [a.player_id + ':' + a.season, a]));
  const p100ByKey = new Map(PER100.map(r => [r.player_id + ':' + r.season, r]));
  seasonsByPlayer.forEach(list => list.forEach(s => {
    const a = advByKey.get(s.player_id + ':' + s.season);
    ADV_FIELDS.forEach(f => { s[f] = a ? a[f] : null; });
    s.per100 = p100ByKey.get(s.player_id + ':' + s.season) || null;
  }));
}

const allStarByPlayer = new Map();
ALL_STARS.forEach(a => {
  if (!allStarByPlayer.has(a.player_id)) allStarByPlayer.set(a.player_id, new Set());
  allStarByPlayer.get(a.player_id).add(a.season);
});
function isAllStar(playerId, season) {
  const s = allStarByPlayer.get(playerId);
  return !!(s && s.has(season));
}

// Some early players were drafted more than once; the last pick is the one
// that stuck, so that's what gets shown.
const draftByPlayer = new Map();
DRAFTS.slice().sort((a, b) => a.season - b.season).forEach(d => draftByPlayer.set(d.player_id, d));

function draftLine(playerId) {
  const d = draftByPlayer.get(playerId);
  if (!d) {
    const p = careerById.get(playerId);
    return p && p.first_season >= 1950 ? 'Undrafted' : null;
  }
  const pick = d.overall_pick ? `Round ${d.round}, Pick ${d.overall_pick}` : `Round ${d.round}`;
  return `Drafted ${d.season} · ${pick} · ${d.tm}${d.college ? ` · ${d.college}` : ''}`;
}
