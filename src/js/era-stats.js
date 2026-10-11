// ===================================================================
// ERA-ADJUSTED STATS
// Three ways to read a season, shared by the comparison table and the
// career overlay chart:
//   raw    — box score as recorded
//   per100 — per 100 team possessions (removes pace; tracked from 1973-74)
//   index  — relative to that season's league average, 100 = average
// Advanced metrics (PER, WS/48, BPM...) are already league-relative by
// construction, so they're shown in every mode.
// ===================================================================
function per36(row, key) {
  return row[key] != null && row.mp ? row[key] / row.mp * 36 : null;
}
function leagueIndex(value, leagueValue) {
  return value != null && leagueValue ? 100 * value / leagueValue : null;
}
const envOf = row => envBySeason.get(row.season) || {};
const p100 = key => row => row.per100 ? row.per100[key] : null;

const STAT_BASES = {
  raw: {
    label: 'Raw box score',
    note: 'Numbers as recorded. Faster eras (the 1960s averaged ~125 possessions a game vs. ~100 today) inflate counting stats.',
    defs: [
      { key: 'pts', label: 'Points/Game', get: r => r.pts, fmt: 'num' },
      { key: 'trb', label: 'Rebounds/Game', get: r => r.trb, fmt: 'num' },
      { key: 'ast', label: 'Assists/Game', get: r => r.ast, fmt: 'num' },
      { key: 'stl', label: 'Steals/Game', get: r => r.stl, fmt: 'num' },
      { key: 'blk', label: 'Blocks/Game', get: r => r.blk, fmt: 'num' },
      { key: 'fg_pct', label: 'FG%', get: r => r.fg_pct, fmt: 'pct' },
      { key: 'x3p_pct', label: '3P%', get: r => r.x3p_pct, fmt: 'pct' },
      { key: 'ft_pct', label: 'FT%', get: r => r.ft_pct, fmt: 'pct' },
      { key: 'ts_pct', label: 'True Shooting %', get: r => r.ts_pct, fmt: 'pct' },
      { key: 'mp', label: 'Minutes/Game', get: r => r.mp, fmt: 'num' },
      { key: 'g', label: 'Games Played', get: r => r.g, fmt: 'int' },
    ],
  },
  per100: {
    label: 'Per 100 possessions',
    note: 'Stats per 100 team possessions, which strips out pace. Basketball-Reference only tracks this from 1973-74, so earlier seasons show \u2014.',
    defs: [
      { key: 'p_pts', label: 'Points / 100', get: p100('pts'), fmt: 'num' },
      { key: 'p_trb', label: 'Rebounds / 100', get: p100('trb'), fmt: 'num' },
      { key: 'p_ast', label: 'Assists / 100', get: p100('ast'), fmt: 'num' },
      { key: 'p_stl', label: 'Steals / 100', get: p100('stl'), fmt: 'num' },
      { key: 'p_blk', label: 'Blocks / 100', get: p100('blk'), fmt: 'num' },
      { key: 'p_tov', label: 'Turnovers / 100', get: p100('tov'), fmt: 'num', lowerBetter: true },
      { key: 'o_rtg', label: 'Offensive Rating', get: p100('o_rtg'), fmt: 'int' },
      { key: 'd_rtg', label: 'Defensive Rating', get: p100('d_rtg'), fmt: 'int', lowerBetter: true },
      { key: 'ts_pct', label: 'True Shooting %', get: r => r.ts_pct, fmt: 'pct' },
    ],
  },
  index: {
    label: 'Era-adjusted (vs. league)',
    note: 'Each stat vs. that season\u2019s league average: 100 = average, 150 = 50% better. Counting stats use per-36-minute rates (minutes weren\u2019t recorded before 1951-52); shooting indexes compare percentages directly.',
    defs: [
      { key: 'i_pts', label: 'Scoring rate', get: r => leagueIndex(per36(r, 'pts'), envOf(r).pts36), fmt: 'idx' },
      { key: 'i_trb', label: 'Rebounding rate', get: r => leagueIndex(per36(r, 'trb'), envOf(r).trb36), fmt: 'idx' },
      { key: 'i_ast', label: 'Playmaking rate', get: r => leagueIndex(per36(r, 'ast'), envOf(r).ast36), fmt: 'idx' },
      { key: 'i_stl', label: 'Steal rate', get: r => leagueIndex(per36(r, 'stl'), envOf(r).stl36), fmt: 'idx' },
      { key: 'i_blk', label: 'Block rate', get: r => leagueIndex(per36(r, 'blk'), envOf(r).blk36), fmt: 'idx' },
      { key: 'i_ts', label: 'TS+ (efficiency)', get: r => leagueIndex(r.ts_pct, envOf(r).ts_pct), fmt: 'idx' },
      { key: 'i_fg', label: 'FG+', get: r => leagueIndex(r.fg_pct, envOf(r).fg_pct), fmt: 'idx' },
      { key: 'i_3p', label: '3P+', get: r => leagueIndex(r.x3p_pct, envOf(r).x3p_pct), fmt: 'idx' },
      { key: 'i_ft', label: 'FT+', get: r => leagueIndex(r.ft_pct, envOf(r).ft_pct), fmt: 'idx' },
    ],
  },
};

const ADVANCED_STAT_DEFS = [
  { key: 'per', label: 'PER', get: r => r.per, fmt: 'num' },
  { key: 'ws', label: 'Win Shares', get: r => r.ws, fmt: 'num' },
  { key: 'ws_48', label: 'WS / 48', get: r => r.ws_48, fmt: 'num3' },
  { key: 'bpm', label: 'Box Plus/Minus', get: r => r.bpm, fmt: 'signed' },
  { key: 'vorp', label: 'VORP', get: r => r.vorp, fmt: 'num' },
  { key: 'usg_pct', label: 'Usage %', get: r => r.usg_pct, fmt: 'num' },
];

function formatStat(fmt, v) {
  if (v == null || !isFinite(v)) return '\u2014';
  switch (fmt) {
    case 'pct': return (v * 100).toFixed(2) + '%';
    case 'int': return Math.round(v).toLocaleString('en-US');
    case 'idx': return Math.round(v).toString();
    case 'num3': return v.toFixed(3);
    case 'signed': return (v > 0 ? '+' : '') + v.toFixed(1);
    default: return v.toFixed(1);
  }
}
// Value to plot on a chart axis (percentages as 0-100 rather than 0-1).
function chartValue(fmt, v) {
  if (v == null || !isFinite(v)) return null;
  return fmt === 'pct' ? v * 100 : v;
}
