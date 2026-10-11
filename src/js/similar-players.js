// ===================================================================
// SIMILAR PLAYERS
// Neighbors are precomputed by scripts/prep_data.py from an era-relative
// career "style fingerprint" (see SIMILAR_PLAYERS.features).
// ===================================================================
const SIM_FEATURES = SIMILAR_PLAYERS.features;
const simFeature = (pid, name) => {
  const v = SIMILAR_PLAYERS.players[pid];
  return v ? v[SIM_FEATURES.indexOf(name)] : null;
};
let similarEraFilter = 'all';

const FINGERPRINT = [
  { key: 'pts_idx', label: 'Scoring', fmt: v => `${v.toFixed(2)}\u00d7 league` },
  { key: 'trb_idx', label: 'Rebounding', fmt: v => `${v.toFixed(2)}\u00d7 league` },
  { key: 'ast_idx', label: 'Playmaking', fmt: v => `${v.toFixed(2)}\u00d7 league` },
  { key: 'stl_idx', label: 'Steals', fmt: v => `${v.toFixed(2)}\u00d7 league` },
  { key: 'blk_idx', label: 'Blocks', fmt: v => `${v.toFixed(2)}\u00d7 league` },
  { key: 'ts_idx', label: 'Efficiency (TS+)', fmt: v => `${Math.round(v * 100)}` },
  { key: 'usg_percent', label: 'Usage', fmt: v => `${v.toFixed(1)}%` },
  { key: 'x3p_ar_diff', label: '3PT tendency', fmt: v => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(0)} pts vs lg` },
];

function careerMidpoint(pid) {
  const p = careerById.get(pid);
  return p ? (p.first_season + p.last_season) / 2 : null;
}

function renderSimilarPlayers(playerId) {
  const panel = $('#pc-similar-panel');
  panel.style.display = 'block';
  const neighbors = SIMILAR_PLAYERS.neighbors[playerId];

  if (!neighbors || !neighbors.length) {
    $('#pc-similar-fingerprint').innerHTML = '';
    $('#pc-similar-era').style.display = 'none';
    $('#pc-similar-list').innerHTML = `<div class="no-data-note">Not enough tracked minutes for a reliable match (needs 3,000+ career minutes; minutes were first recorded in 1951-52).</div>`;
    return;
  }
  $('#pc-similar-era').style.display = 'flex';

  // Fingerprint: how this player's career reads relative to the league.
  $('#pc-similar-fingerprint').innerHTML = FINGERPRINT.map(f => {
    const v = simFeature(playerId, f.key);
    return v == null ? '' : `<div class="fp-cell"><div class="v">${f.fmt(v)}</div><div class="l">${f.label}</div></div>`;
  }).join('');

  const mid = careerMidpoint(playerId);
  let list = neighbors.map(([pid, score]) => ({ p: careerById.get(pid), score })).filter(x => x.p);
  if (similarEraFilter === 'same') list = list.filter(x => Math.abs(careerMidpoint(x.p.player_id) - mid) <= 10);
  list = list.slice(0, 8);

  if (!list.length) {
    $('#pc-similar-list').innerHTML = `<div class="no-data-note">No close matches whose careers overlapped this era. Try "Any era".</div>`;
    return;
  }
  $('#pc-similar-list').innerHTML = list.map(({ p, score }) => `
    <div class="similar-row">
      <div class="similar-score"><div class="similar-score-fill" style="width:${score}%"></div><span>${score}</span></div>
      <div class="similar-name">
        <span class="name-link" data-pid="${p.player_id}">${p.player}</span>${p.hof ? '<span class="hof-badge">HOF</span>' : ''}
        <div class="similar-meta">${p.pos || '\u2014'} \u00b7 ${p.first_season}\u2013${p.last_season} \u00b7 ${fmtNum(p.ppg, 1)} / ${fmtNum(p.rpg, 1)} / ${fmtNum(p.apg, 1)}</div>
      </div>
      <button class="pill-btn similar-compare" data-pid="${p.player_id}">Compare \u2192</button>
    </div>`).join('');

  $$('#pc-similar-list .name-link').forEach(el => el.addEventListener('click', () => selectPlayer(el.dataset.pid)));
  $$('#pc-similar-list .similar-compare').forEach(el => el.addEventListener('click', () => openComparison(playerId, el.dataset.pid)));
}

$$('#pc-similar-era .pill-btn').forEach(btn => btn.addEventListener('click', () => {
  similarEraFilter = btn.dataset.era;
  $$('#pc-similar-era .pill-btn').forEach(b => b.classList.toggle('active', b === btn));
  if (currentPlayerId) renderSimilarPlayers(currentPlayerId);
}));
