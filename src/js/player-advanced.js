// ===================================================================
// ADVANCED METRICS PANEL (Player Explorer)
// ===================================================================
function bestSeason(seasons, key) {
  return seasons.filter(s => s[key] != null && (s.g || 0) >= 20)
    .reduce((best, s) => (!best || s[key] > best[key] ? s : best), null);
}

function renderAdvancedPanel(playerId) {
  const player = careerById.get(playerId);
  const seasons = seasonsByPlayer.get(playerId) || [];
  const hasAny = seasons.some(s => s.per != null || s.ws != null);
  $('#pc-advanced-panel').style.display = hasAny ? 'block' : 'none';
  if (!hasAny) return;

  const peak = (key, fmt, label) => {
    const s = bestSeason(seasons, key);
    return { l: label, v: s ? formatStat(fmt, s[key]) : '\u2014', sub: s ? String(s.season) : '' };
  };
  const cells = [
    { l: 'Career WS', v: fmtNum(player.ws, 1), sub: '' },
    { l: 'Career VORP', v: fmtNum(player.vorp, 1), sub: '' },
    peak('per', 'num', 'Best PER'),
    peak('ws_48', 'num3', 'Best WS/48'),
    peak('bpm', 'signed', 'Best BPM'),
    peak('ts_pct', 'pct', 'Best TS%'),
  ];
  $('#pc-advanced-stats').innerHTML = cells.map(c =>
    `<div class="ps-cell"><div class="v">${c.v}</div><div class="l">${c.l}${c.sub ? ` \u00b7 ${c.sub}` : ''}</div></div>`).join('');
}
