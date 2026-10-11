// ===================================================================
// COMPARE: PLAYER COMPARISON
// ===================================================================
let cmpPlayerA = null, cmpPlayerB = null;
let cmpAlignMode = 'experience'; // 'experience' | 'age' | 'calendar'
let cmpBasis = 'raw';             // 'raw' | 'per100' | 'index'  (see era-stats.js)
let cmpView = 'snapshot';         // 'snapshot' | 'overlay'
let cmpOverlayStat = 'pts';
let cmpOverlayChart = null;

function cmpExperienceYear(playerId, season) {
  const p = careerById.get(playerId);
  if (!p) return null;
  return season - p.first_season + 1;
}

// For a given alignment mode and "slider position" (meaning depends on mode),
// return each player's matching season object (or null if they have no
// season at that position).
function cmpSeasonAtPosition(playerId, mode, pos) {
  const list = seasonsByPlayer.get(playerId) || [];
  if (mode === 'experience') {
    const p = careerById.get(playerId);
    if (!p) return null;
    const targetSeason = p.first_season + pos - 1;
    return list.find(s => s.season === targetSeason) || null;
  }
  if (mode === 'age') {
    return list.find(s => s.age === pos) || null;
  }
  // calendar
  return list.find(s => s.season === pos) || null;
}

function cmpPositionRange(mode) {
  if (!cmpPlayerA || !cmpPlayerB) return { min: 0, max: 0 };
  const listA = seasonsByPlayer.get(cmpPlayerA) || [];
  const listB = seasonsByPlayer.get(cmpPlayerB) || [];
  if (mode === 'experience') {
    const maxExpA = listA.length ? Math.max(...listA.map(s => cmpExperienceYear(cmpPlayerA, s.season))) : 0;
    const maxExpB = listB.length ? Math.max(...listB.map(s => cmpExperienceYear(cmpPlayerB, s.season))) : 0;
    return { min: 1, max: Math.max(maxExpA, maxExpB, 1) };
  }
  if (mode === 'age') {
    const ages = [...listA.map(s => s.age), ...listB.map(s => s.age)].filter(a => a != null);
    return ages.length ? { min: Math.min(...ages), max: Math.max(...ages) } : { min: 18, max: 45 };
  }
  // calendar — only the overlapping window matters, but show full union so
  // the slider can move across each player's whole career for context
  const seasonsAll = [...listA.map(s => s.season), ...listB.map(s => s.season)];
  return seasonsAll.length ? { min: Math.min(...seasonsAll), max: Math.max(...seasonsAll) } : { min: FIRST_SEASON, max: LATEST_SEASON };
}

// Stat rows for the current basis, followed by the advanced metrics.
function cmpStatDefs() {
  return [...STAT_BASES[cmpBasis].defs, ...ADVANCED_STAT_DEFS];
}


// ===================================================================
// COMPARE: PLAYER COMPARISON — search & selection
// ===================================================================
function setupCmpPlayerSearch(inputId, resultsId, onSelect) {
  const input = $('#' + inputId);
  const results = $('#' + resultsId);

  input.addEventListener('input', () => {
    const q = normalizeForSearch(input.value.trim());
    if (!q) { results.classList.remove('show'); return; }
    let matches;
    if (q.length < 2) {
      matches = notablePlayers.filter(p => playerSearchKey.get(p.player_id).startsWith(q)).slice(0, 12);
    } else {
      matches = CAREER.filter(p => playerSearchKey.get(p.player_id).includes(q)).slice(0, 30);
      matches.sort((a, b) => (b.pts || 0) - (a.pts || 0));
      matches = matches.slice(0, 12);
    }
    if (matches.length === 0) {
      results.innerHTML = `<div class="psr-item" style="cursor:default;color:var(--chalk-dim);">No players found</div>`;
      results.classList.add('show');
      return;
    }
    results.innerHTML = matches.map(p => `
      <div class="psr-item" data-pid="${p.player_id}">
        <span>${p.player}${p.hof ? '<span class="hof-badge">HOF</span>' : ''}</span>
        <span class="psr-meta">${p.first_season}–${p.last_season}</span>
      </div>
    `).join('');
    $$('.psr-item', results).forEach(item => {
      item.addEventListener('click', () => {
        if (!item.dataset.pid) return;
        const player = careerById.get(item.dataset.pid);
        onSelect(item.dataset.pid);
        input.value = player ? player.player : '';
        results.classList.remove('show');
      });
    });
    results.classList.add('show');
  });

  document.addEventListener('click', (e) => {
    if (!results.contains(e.target) && e.target !== input) {
      results.classList.remove('show');
    }
  });
}

setupCmpPlayerSearch('cmp-player-search-a', 'cmp-player-results-a', (pid) => {
  cmpPlayerA = pid;
  renderPlayerComparison();
});
setupCmpPlayerSearch('cmp-player-search-b', 'cmp-player-results-b', (pid) => {
  cmpPlayerB = pid;
  renderPlayerComparison();
});

function renderCmpPlayerSuggestions() {
  const pairs = [
    ['jamesle01', 'jordami01'], ['curryst01', 'thompkl01'], ['birdla01', 'johnsma02'],
    ['duncati01', 'garneke01'], ['jokicni01', 'embiijo01'],
  ];
  const found = pairs.map(([a, b]) => [careerById.get(a), careerById.get(b)]).filter(([a, b]) => a && b);
  $('#cmp-player-suggestions').innerHTML = found.map(([a, b]) =>
    `<button class="pill-btn" data-pa="${a.player_id}" data-pb="${b.player_id}">${a.player} vs ${b.player}</button>`
  ).join('');
  $$('#cmp-player-suggestions .pill-btn').forEach(btn => {
    btn.addEventListener('click', () => setComparisonPlayers(btn.dataset.pa, btn.dataset.pb));
  });
}
renderCmpPlayerSuggestions();

function setComparisonPlayers(a, b) {
  cmpPlayerA = a;
  cmpPlayerB = b;
  $('#cmp-player-search-a').value = careerById.get(a).player;
  $('#cmp-player-search-b').value = careerById.get(b).player;
  $('#cmp-align-slider').dataset.pair = '';
  renderPlayerComparison();
}

// Jump to the Compare tab with two players loaded (used by Similar Players).
function openComparison(a, b) {
  $$('#main-tabs > .tab-btn').forEach(x => x.classList.toggle('active', x.dataset.view === 'compare'));
  $$('.view').forEach(v => v.classList.remove('active'));
  $('#view-compare').classList.add('active');
  initCompareView();
  $$('#view-compare > .tabs > .tab-btn').forEach(x => x.classList.toggle('active', x.dataset.compareMode === 'players'));
  $$('.compare-mode-view').forEach(v => v.classList.toggle('active', v.id === 'compare-players'));
  setComparisonPlayers(a, b);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function bindPillGroup(selector, attr, onPick) {
  $$(selector + ' .pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$(selector + ' .pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      onPick(btn.dataset[attr]);
    });
  });
}
bindPillGroup('#cmp-basis-toggle', 'basis', v => {
  cmpBasis = v;
  cmpOverlayStat = STAT_BASES[v].defs[0].key;
  renderPlayerComparison();
});
bindPillGroup('#cmp-view-toggle', 'cmpview', v => { cmpView = v; renderPlayerComparison(); });

$$('#cmp-align-toggle .pill-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    cmpAlignMode = btn.dataset.align;
    $$('#cmp-align-toggle .pill-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderPlayerComparison();
  });
});

// ===================================================================
// COMPARE: PLAYER COMPARISON — rendering
// ===================================================================
let cmpRenderToken = 0;
async function renderPlayerComparison() {
  const token = ++cmpRenderToken;
  try {
    await ensurePlayers([cmpPlayerA, cmpPlayerB]);
  } catch (err) {
    showDataError(err);
    return;
  }
  if (token !== cmpRenderToken) return;
  renderPlayerComparisonNow();
}

function renderPlayerComparisonNow() {
  if (!cmpPlayerA || !cmpPlayerB) return;
  $('#cmp-players-empty').style.display = 'none';
  $('#cmp-players-result').style.display = 'block';

  const range = cmpPositionRange(cmpAlignMode);
  const slider = $('#cmp-align-slider');
  slider.min = range.min;
  slider.max = range.max;
  const pairKey = cmpPlayerA + '|' + cmpPlayerB + '|' + cmpAlignMode;
  if (slider.dataset.pair !== pairKey) {
    // New pair or mode: start at the latest point where BOTH players have a
    // season, so the first thing shown is an actual side-by-side comparison.
    let start = range.max;
    for (let p = range.max; p >= range.min; p--) {
      if (cmpSeasonAtPosition(cmpPlayerA, cmpAlignMode, p) && cmpSeasonAtPosition(cmpPlayerB, cmpAlignMode, p)) { start = p; break; }
    }
    slider.value = start;
    slider.dataset.pair = pairKey;
  }

  $('#cmp-align-slider-ticks').innerHTML = `<span>${range.min}</span><span>${range.max}</span>`;

  $('#cmp-basis-note').innerHTML = `<b>${STAT_BASES[cmpBasis].label}.</b> ${STAT_BASES[cmpBasis].note}`;
  const overlay = cmpView === 'overlay';
  $('#cmp-snapshot-view').style.display = overlay ? 'none' : 'block';
  $('#cmp-overlay-view').style.display = overlay ? 'block' : 'none';
  $('#cmp-align-slider-wrap').style.display = overlay ? 'none' : 'block';

  if (overlay) {
    $('#cmp-align-note').textContent = `Each player's career on one axis, aligned by ${cmpAlignMode === 'experience' ? 'years of experience' : cmpAlignMode === 'age' ? 'age' : 'calendar season'}. Switch to Season snapshot to step through one point at a time.`;
    renderCmpOverlay();
    return;
  }
  slider.oninput = () => renderCmpAtPosition(parseInt(slider.value, 10));
  renderCmpAtPosition(parseInt(slider.value, 10));
}

function cmpAlignNoteText(mode, pos, seasonA, seasonB) {
  if (mode === 'experience') {
    return `Comparing Year ${pos} of each player's career — ${seasonA ? seasonA.season : '\u2014'} for ${careerById.get(cmpPlayerA).player}, ${seasonB ? seasonB.season : '\u2014'} for ${careerById.get(cmpPlayerB).player}.`;
  }
  if (mode === 'age') {
    return `Comparing age ${pos} for both players — ${seasonA ? seasonA.season : 'no season at this age'} for ${careerById.get(cmpPlayerA).player}, ${seasonB ? seasonB.season : 'no season at this age'} for ${careerById.get(cmpPlayerB).player}.`;
  }
  return `Comparing the ${pos} season for both players directly.${(!seasonA || !seasonB) ? ' One or both players did not play that season.' : ''}`;
}

function renderCmpAtPosition(pos) {
  const seasonA = cmpSeasonAtPosition(cmpPlayerA, cmpAlignMode, pos);
  const seasonB = cmpSeasonAtPosition(cmpPlayerB, cmpAlignMode, pos);
  const playerA = careerById.get(cmpPlayerA);
  const playerB = careerById.get(cmpPlayerB);

  $('#cmp-align-note').textContent = cmpAlignNoteText(cmpAlignMode, pos, seasonA, seasonB);

  renderCmpPlayerCard('cmp-card-a', playerA, seasonA, cmpAlignMode, pos);
  renderCmpPlayerCard('cmp-card-b', playerB, seasonB, cmpAlignMode, pos);

  renderCmpStatTable(seasonA, seasonB);

  // Head-to-head only when both players have a season AND those seasons are
  // the same calendar year (a genuine overlap), regardless of alignment mode.
  if (seasonA && seasonB && seasonA.season === seasonB.season) {
    renderCmpHeadToHead(playerA, playerB, seasonA, seasonB);
    $('#cmp-h2h-panel').style.display = 'block';
  } else {
    $('#cmp-h2h-panel').style.display = 'none';
  }
}

function renderCmpPlayerCard(containerId, player, seasonRow, mode, pos) {
  const expYear = seasonRow ? cmpExperienceYear(player.player_id, seasonRow.season) : null;
  const env = seasonRow ? envBySeason.get(seasonRow.season) : null;
  const honors = seasonRow ? seasonHonors(player.player_id, seasonRow.season) : [];
  const teams = seasonRow ? teamsInSeason(player.player_id, seasonRow.season) : [];
  const cells = seasonRow ? [
    { l: 'Season', v: seasonRow.season },
    { l: 'Age', v: seasonRow.age ?? '\u2014' },
    { l: 'Exp. Yr', v: expYear ?? '\u2014' },
    { l: 'PPG', v: fmtNum(seasonRow.pts, 1) },
    { l: 'RPG', v: fmtNum(seasonRow.trb, 1) },
    { l: 'APG', v: fmtNum(seasonRow.ast, 1) },
  ] : [];

  $('#' + containerId).innerHTML = `
    <div class="cmp-card-name">${player.player}${player.hof ? '<span class="hof-badge">HOF</span>' : ''}</div>
    <div class="cmp-card-meta">${player.pos || '\u2014'} \u00b7 ${player.first_season}\u2013${player.last_season} (${player.seasons_played} seasons)</div>
    ${seasonRow ? `
      <div class="cmp-card-stat-grid">
 ${cells.map(c => `<div class="cs-cell"><div class="v">${c.v}</div><div class="l">${c.l}</div></div>`).join('')}
      </div>
      <div class="cmp-card-context">${teams.join(' / ') || seasonRow.team || ''}${env && env.pace ? ` \u00b7 league pace ${env.pace.toFixed(1)}` : ''}${env && env.ts_pct ? ` \u00b7 league TS ${(env.ts_pct * 100).toFixed(1)}%` : ''}</div>
      ${honors.length ? `<div class="cmp-card-honors">${honors.map(h => `<span class="award-pill won">${h}</span>`).join('')}</div>` : ''}
    ` : `<div class="no-data-note">No matching season for this player at this point in the comparison.</div>`}
  `;
}

function cmpStatRow(def, seasonA, seasonB) {
  const va = def.get(seasonA);
  const vb = def.get(seasonB);
  const ok = v => v != null && isFinite(v);
  const maxV = Math.max(Math.abs(ok(va) ? va : 0), Math.abs(ok(vb) ? vb : 0), 0.001);
  const pctA = ok(va) ? Math.max(4, (Math.abs(va) / maxV) * 100) : 0;
  const pctB = ok(vb) ? Math.max(4, (Math.abs(vb) / maxV) * 100) : 0;
  const both = ok(va) && ok(vb) && va !== vb;
  const aWins = both && (def.lowerBetter ? va < vb : va > vb);
  const bWins = both && !aWins;
  return `
    <div class="cmp-stat-row ${aWins ? 'cmp-stat-winner-a' : ''} ${bWins ? 'cmp-stat-winner-b' : ''}">
      <div class="cmp-stat-bar-wrap right">
        <span class="cmp-stat-value a-val">${formatStat(def.fmt, va)}</span>
        <div class="cmp-stat-bar-track"><div class="cmp-stat-bar-fill a" style="width:${pctA}%"></div></div>
      </div>
      <span class="cmp-stat-label">${def.label}</span>
      <div class="cmp-stat-bar-wrap">
        <div class="cmp-stat-bar-track"><div class="cmp-stat-bar-fill b" style="width:${pctB}%"></div></div>
        <span class="cmp-stat-value b-val">${formatStat(def.fmt, vb)}</span>
      </div>
    </div>`;
}

function renderCmpStatTable(seasonA, seasonB) {
  if (!seasonA || !seasonB) {
    $('#cmp-stat-table').innerHTML = `<div class="no-data-note">Both players need a season at this position in the comparison to show stat-by-stat detail.</div>`;
    return;
  }
  const basis = STAT_BASES[cmpBasis];
  $('#cmp-stat-table').innerHTML =
    basis.defs.map(d => cmpStatRow(d, seasonA, seasonB)).join('') +
    `<div class="cmp-stat-subhead">Advanced metrics <span>already league-relative, so they read the same in every mode</span></div>` +
    ADVANCED_STAT_DEFS.map(d => cmpStatRow(d, seasonA, seasonB)).join('');
}

function renderCmpHeadToHead(playerA, playerB, seasonA, seasonB) {
  const teamsA = teamsInSeason(playerA.player_id, seasonA.season);
  const teamsB = teamsInSeason(playerB.player_id, seasonB.season);
  const shared = teamsA.filter(t => teamsB.includes(t));
  if (shared.length) {
    $('#cmp-h2h-content').innerHTML = `<div class="no-data-note">${playerA.player} and ${playerB.player} were teammates on ${shared.join(' / ')} in ${seasonA.season} \u2014 no head-to-head, they were on the same side${teamsA.length > 1 || teamsB.length > 1 ? ' for at least part of the season' : ''}.</div>`;
    return;
  }
  $('#cmp-h2h-content').innerHTML = `
    <div class="no-data-note">
      ${playerA.player} (${teamsA.join(' / ') || '\u2014'}) and ${playerB.player} (${teamsB.join(' / ') || '\u2014'}) both played in ${seasonA.season}.
      This dataset doesn't include a game-by-game schedule, so individual head-to-head box scores aren't available \u2014
      but here's how each player's season compared above, and you can look up either team's full season in Team Explorer.
    </div>
  `;
}

// Awards, All-NBA/All-Defense teams and All-Star selection for one season.
function seasonHonors(playerId, season) {
  const out = [];
  (awardsByPlayer.get(playerId) || []).filter(a => a.season === season && a.winner)
    .forEach(a => out.push('\u{1F3C6} ' + (AWARD_SHORT[a.award] || a.award)));
  (eosByPlayer.get(playerId) || []).filter(e => e.season === season)
    .forEach(e => out.push(`${e.team_type} ${e.team_number}`));
  if (isAllStar(playerId, season)) out.push('All-Star');
  return out;
}

// ---- Career overlay chart (optional view) ----------------------------------
function renderCmpOverlay() {
  const defs = cmpStatDefs();
  if (!defs.find(d => d.key === cmpOverlayStat)) cmpOverlayStat = defs[0].key;
  $('#cmp-overlay-pills').innerHTML = defs.map(d =>
    `<button class="pill-btn ${d.key === cmpOverlayStat ? 'active' : ''}" data-stat="${d.key}">${d.label}</button>`).join('');
  $$('#cmp-overlay-pills .pill-btn').forEach(btn => btn.addEventListener('click', () => {
    cmpOverlayStat = btn.dataset.stat;
    renderCmpOverlay();
  }));

  const def = defs.find(d => d.key === cmpOverlayStat);
  const range = cmpPositionRange(cmpAlignMode);
  const positions = [];
  for (let p = range.min; p <= range.max; p++) positions.push(p);
  const series = pid => positions.map(p => {
    const row = cmpSeasonAtPosition(pid, cmpAlignMode, p);
    return row ? { v: chartValue(def.fmt, def.get(row)), row } : { v: null, row: null };
  });
  const a = series(cmpPlayerA), b = series(cmpPlayerB);
  const nameA = careerById.get(cmpPlayerA).player, nameB = careerById.get(cmpPlayerB).player;
  const hasData = [...a, ...b].some(x => x.v != null);
  $('#cmp-overlay-empty').style.display = hasData ? 'none' : 'block';

  const axisLabel = cmpAlignMode === 'experience' ? 'Year of career' : cmpAlignMode === 'age' ? 'Age' : 'Season';
  const tickFmt = v => def.fmt === 'pct' ? v.toFixed(1) + '%' : def.fmt === 'num3' ? v.toFixed(3) : v;
  const ds = (label, pts, color, fill) => ({
    label, data: pts.map(x => x.v), borderColor: color, backgroundColor: fill,
    pointBackgroundColor: color, pointRadius: 3, pointHoverRadius: 6, borderWidth: 2.5, tension: 0.25, spanGaps: false,
  });

  if (cmpOverlayChart) cmpOverlayChart.destroy();
  cmpOverlayChart = new Chart($('#cmp-overlay-chart').getContext('2d'), {
    type: 'line',
    data: { labels: positions, datasets: [ds(nameA, a, PALETTE.amber, PALETTE.amberDim), ds(nameB, b, PALETTE.blue, PALETTE.blueDim)] },
    options: baseChartOptions({
      plugins: {
        legend: { labels: { color: PALETTE.chalkDim, font: { family: "'JetBrains Mono', monospace", size: 11 }, boxWidth: 12, boxHeight: 12 } },
        tooltip: {
          backgroundColor: '#1f1a16', borderColor: 'rgba(241,235,224,0.18)', borderWidth: 1,
          titleColor: PALETTE.amber, bodyColor: PALETTE.chalk,
          titleFont: { family: "'JetBrains Mono', monospace", size: 12 },
          bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
          callbacks: {
            title: items => `${axisLabel} ${items[0].label}`,
            label: ctx => {
              const pt = (ctx.datasetIndex === 0 ? a : b)[ctx.dataIndex];
              const raw = pt.row ? def.get(pt.row) : null;
              return `${ctx.dataset.label}: ${formatStat(def.fmt, raw)}${pt.row ? ` (${pt.row.season}, age ${pt.row.age ?? '\u2014'})` : ''}`;
            },
          },
        },
      },
      scales: {
        x: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim }, title: { display: true, text: axisLabel, color: PALETTE.chalkDim, font: { family: "'JetBrains Mono', monospace", size: 11 } } },
        y: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, callback: tickFmt }, title: { display: true, text: def.label, color: PALETTE.chalkDim, font: { family: "'JetBrains Mono', monospace", size: 11 } } },
      },
    }),
  });
}
