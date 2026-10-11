// ===================================================================
// UTILITIES
// ===================================================================
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function fmtNum(v, decimals = 1) {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return Number(v).toFixed(decimals);
}
function fmtInt(v) {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return Number(v).toLocaleString('en-US');
}
function fmtPct(v, decimals = 1) {
  if (v === null || v === undefined || isNaN(v)) return '—';
  return (Number(v) * 100).toFixed(decimals) + '%';
}

// rows-of-arrays -> array of objects, using a columns map
function toObjects(payload) {
  const { columns, rows } = payload;
  return rows.map(r => {
    const o = {};
    columns.forEach((c, i) => { o[c] = r[i]; });
    return o;
  });
}

const CAREER = toObjects(PLAYER_CAREER);
const SEASONS = toObjects(PLAYER_SEASONS);
const ERA = ERA_TRENDS; // already array of objects

// index helpers
const careerById = new Map(CAREER.map(p => [p.player_id, p]));
// A traded player has a combined row (team "2TM", "3TM", ...) plus one row
// per team stint. seasonsByPlayer keeps ONE row per season (the combined row
// when it exists) for charts and comparisons; stintsByPlayer keeps the
// per-team rows for rosters and teammate checks.
const MULTITEAM_CODES = new Set(['2TM', '3TM', '4TM', '5TM']);
const seasonsByPlayer = new Map();
const stintsByPlayer = new Map();
SEASONS.forEach(s => {
  if (MULTITEAM_CODES.has(s.team)) return;
  if (!stintsByPlayer.has(s.player_id)) stintsByPlayer.set(s.player_id, []);
  stintsByPlayer.get(s.player_id).push(s);
});
{
  const bySeason = new Map();
  SEASONS.forEach(s => {
    const key = s.player_id + ':' + s.season;
    const prev = bySeason.get(key);
    if (!prev || MULTITEAM_CODES.has(s.team)) bySeason.set(key, s);
  });
  bySeason.forEach(s => {
    if (!seasonsByPlayer.has(s.player_id)) seasonsByPlayer.set(s.player_id, []);
    seasonsByPlayer.get(s.player_id).push(s);
  });
}
seasonsByPlayer.forEach(list => list.sort((a, b) => a.season - b.season));
stintsByPlayer.forEach(list => list.sort((a, b) => a.season - b.season));

// Team abbreviations a player suited up for in a given season.
function teamsInSeason(playerId, season) {
  return (stintsByPlayer.get(playerId) || []).filter(s => s.season === season).map(s => s.team);
}


const eraBySeason = new Map(ERA.map(e => [e.season, e]));
// Season range comes from the data, so a data update needs no code changes.
const FIRST_SEASON = ERA[0].season;
const LATEST_SEASON = ERA[ERA.length - 1].season;

// ===================================================================
// CHART.JS GLOBAL DEFAULTS — match design system
// ===================================================================
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.color = '#b7afa0';
Chart.defaults.borderColor = 'rgba(241,235,224,0.08)';

const PALETTE = {
  amber: '#ff9d2e',
  amberDim: 'rgba(255,157,46,0.15)',
  blue: '#4a8fb8',
  blueDim: 'rgba(74,143,184,0.15)',
  wood: '#d99a5c',
  chalk: '#f1ebe0',
  chalkDim: '#b7afa0',
  grid: 'rgba(241,235,224,0.07)',
};

function baseChartOptions(extra = {}) {
  return Object.assign({
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        labels: { color: PALETTE.chalkDim, font: { family: "'JetBrains Mono', monospace", size: 11 }, boxWidth: 12, boxHeight: 12 }
      },
      tooltip: {
        backgroundColor: '#1f1a16',
        borderColor: 'rgba(241,235,224,0.18)',
        borderWidth: 1,
        titleFont: { family: "'JetBrains Mono', monospace", size: 12 },
        bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
        padding: 10,
        titleColor: PALETTE.amber,
        bodyColor: PALETTE.chalk,
      }
    },
    scales: {
      x: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, font: { size: 11 } } },
      y: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, font: { size: 11 } } }
    }
  }, extra);
}
