// ===================================================================
// COMPARE: TEAM COMPARISON
// ===================================================================
let cmpTeamA = null, cmpTeamB = null;
let cmpTeamScope = 'career'; // 'career' | 'season'
let cmpTeamSeasonA = null, cmpTeamSeasonB = null;

// franchise-career aggregate (sum/avg across every season the franchise has played)
function franchiseCareerAggregate(franchiseName) {
  const span = franchiseSpans.get(franchiseName);
  if (!span) return null;
  const rows = span.rows;
  const totalW = rows.reduce((s, r) => s + (r.w || 0), 0);
  const totalL = rows.reduce((s, r) => s + (r.l || 0), 0);
  const playoffSeasons = rows.filter(r => r.playoffs).length;
  const avg = (key) => {
    const vals = rows.map(r => r[key]).filter(v => v != null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  };
  return {
    franchise: franchiseName,
    displayName: rows[rows.length - 1].current_name || rows[rows.length - 1].team_name,
    minSeason: span.minSeason,
    maxSeason: span.maxSeason,
    totalSeasons: rows.length,
    totalW, totalL,
    winPct: (totalW + totalL) > 0 ? totalW / (totalW + totalL) : null,
    playoffSeasons,
    playoffPct: rows.length ? playoffSeasons / rows.length : null,
    avgSrs: avg('srs'), avgOrtg: avg('o_rtg'), avgDrtg: avg('d_rtg'),
    avgPace: avg('pace'), avgPts: avg('pts_per_game'),
    status: rows[rows.length - 1].status,
  };
}

function franchiseSeasonAggregate(franchiseName, season) {
  const span = franchiseSpans.get(franchiseName);
  if (!span) return null;
  const row = span.rows.find(r => r.season === season);
  if (!row) return null;
  return {
    franchise: franchiseName,
    displayName: row.team_name,
    season,
    totalW: row.w, totalL: row.l,
    winPct: (row.w != null && row.l != null && (row.w + row.l) > 0) ? row.w / (row.w + row.l) : null,
    playoffSeasons: row.playoffs ? 1 : 0,
    playoffPct: row.playoffs ? 1 : 0,
    avgSrs: row.srs, avgOrtg: row.o_rtg, avgDrtg: row.d_rtg,
    avgPace: row.pace, avgPts: row.pts_per_game,
    status: row.status,
  };
}

function populateTeamSelectors() {
  const franchises = Array.from(franchiseSpans.keys()).sort();
  const optionsHtml = franchises.map(fr => {
    const span = franchiseSpans.get(fr);
    const latest = span.rows[span.rows.length - 1];
    const displayName = latest.current_name || latest.team_name;
    return `<option value="${fr}">${displayName} (${span.minSeason}\u2013${span.maxSeason})</option>`;
  }).join('');
  $('#cmp-team-select-a').innerHTML = '<option value="">Select a team\u2026</option>' + optionsHtml;
  $('#cmp-team-select-b').innerHTML = '<option value="">Select a team\u2026</option>' + optionsHtml;
}

function populateTeamSeasonSelector(selectId, franchiseName) {
  const span = franchiseSpans.get(franchiseName);
  const sel = $('#' + selectId);
  if (!span) { sel.innerHTML = ''; return; }
  sel.innerHTML = span.rows.slice().reverse().map(r =>
    `<option value="${r.season}">${r.season} (${r.team_name})</option>`
  ).join('');
}

$('#cmp-team-select-a').addEventListener('change', (e) => {
  cmpTeamA = e.target.value || null;
  if (cmpTeamA) populateTeamSeasonSelector('cmp-team-season-a', cmpTeamA);
  renderTeamComparison();
});
$('#cmp-team-select-b').addEventListener('change', (e) => {
  cmpTeamB = e.target.value || null;
  if (cmpTeamB) populateTeamSeasonSelector('cmp-team-season-b', cmpTeamB);
  renderTeamComparison();
});
$('#cmp-team-season-a').addEventListener('change', (e) => {
  cmpTeamSeasonA = parseInt(e.target.value, 10);
  renderTeamComparison();
});
$('#cmp-team-season-b').addEventListener('change', (e) => {
  cmpTeamSeasonB = parseInt(e.target.value, 10);
  renderTeamComparison();
});

$$('#cmp-team-scope-toggle .pill-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    cmpTeamScope = btn.dataset.scope;
    $$('#cmp-team-scope-toggle .pill-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    $('#cmp-team-season-pickers').style.display = cmpTeamScope === 'season' ? 'flex' : 'none';
    if (cmpTeamScope === 'season') {
      if (cmpTeamA) { populateTeamSeasonSelector('cmp-team-season-a', cmpTeamA); cmpTeamSeasonA = parseInt($('#cmp-team-season-a').value, 10); }
      if (cmpTeamB) { populateTeamSeasonSelector('cmp-team-season-b', cmpTeamB); cmpTeamSeasonB = parseInt($('#cmp-team-season-b').value, 10); }
    }
    renderTeamComparison();
  });
});

populateTeamSelectors();

const CMP_TEAM_STAT_DEFS = [
  { key: 'totalW', label: 'Wins', isTotal: true },
  { key: 'totalL', label: 'Losses', isTotal: true },
  { key: 'winPct', label: 'Win %', isPct: true },
  { key: 'avgSrs', label: 'SRS (Strength)' },
  { key: 'avgOrtg', label: 'Off. Rating' },
  { key: 'avgDrtg', label: 'Def. Rating' },
  { key: 'avgPace', label: 'Pace' },
  { key: 'avgPts', label: 'Points/Game' },
];

function renderTeamComparison() {
  if (!cmpTeamA || !cmpTeamB) {
    $('#cmp-teams-result').style.display = 'none';
    return;
  }
  if (cmpTeamScope === 'season' && (cmpTeamSeasonA == null || cmpTeamSeasonB == null)) {
    $('#cmp-teams-result').style.display = 'none';
    return;
  }

  const dataA = cmpTeamScope === 'career' ? franchiseCareerAggregate(cmpTeamA) : franchiseSeasonAggregate(cmpTeamA, cmpTeamSeasonA);
  const dataB = cmpTeamScope === 'career' ? franchiseCareerAggregate(cmpTeamB) : franchiseSeasonAggregate(cmpTeamB, cmpTeamSeasonB);
  if (!dataA || !dataB) {
    $('#cmp-teams-result').style.display = 'none';
    return;
  }

  $('#cmp-teams-result').style.display = 'block';
  renderCmpTeamCard('cmp-team-card-a', dataA);
  renderCmpTeamCard('cmp-team-card-b', dataB);
  renderCmpTeamStatTable(dataA, dataB);
  const token = ++cmpTeamToken;
  ensureTeamHonors([cmpTeamA, cmpTeamB])
    .then(() => { if (token === cmpTeamToken) renderCmpTeamAccomplishments(dataA, dataB); })
    .catch(showDataError);
}
let cmpTeamToken = 0;

function renderCmpTeamCard(containerId, data) {
  const isCareer = data.season === undefined;
  const cells = isCareer ? [
    { l: 'Seasons', v: data.totalSeasons },
    { l: 'Record', v: `${fmtInt(data.totalW)}-${fmtInt(data.totalL)}` },
    { l: 'Win %', v: data.winPct != null ? (data.winPct * 100).toFixed(1) + '%' : '\u2014' },
    { l: 'Playoff Trips', v: `${data.playoffSeasons} / ${data.totalSeasons}` },
  ] : [
    { l: 'Season', v: data.season },
    { l: 'Record', v: `${fmtInt(data.totalW)}-${fmtInt(data.totalL)}` },
    { l: 'Win %', v: data.winPct != null ? (data.winPct * 100).toFixed(1) + '%' : '\u2014' },
    { l: 'Made Playoffs', v: data.playoffSeasons ? 'Yes' : 'No' },
  ];

  $('#' + containerId).innerHTML = `
    <div class="cmp-card-name">${data.displayName}</div>
    <div class="cmp-card-meta">${isCareer ? `${data.minSeason}\u2013${data.maxSeason}` : `Single season`}${data.status !== 'active' ? ' \u00b7 no longer in the NBA' : ''}</div>
    <div class="cmp-card-stat-grid">
      ${cells.map(c => `<div class="cs-cell"><div class="v">${c.v}</div><div class="l">${c.l}</div></div>`).join('')}
    </div>
  `;
}

function renderCmpTeamStatTable(dataA, dataB) {
  $('#cmp-team-stat-table').innerHTML = CMP_TEAM_STAT_DEFS.map(def => {
    const va = dataA[def.key];
    const vb = dataB[def.key];
    const fmt = (v) => {
      if (v == null) return '\u2014';
      if (def.isPct) return (v * 100).toFixed(1) + '%';
      if (def.isTotal) return fmtInt(v);
      return v.toFixed(1);
    };
    const maxV = Math.max(Math.abs(va || 0), Math.abs(vb || 0), 0.001);
    const pctA = va != null ? Math.max(4, (Math.abs(va) / maxV) * 100) : 0;
    const pctB = vb != null ? Math.max(4, (Math.abs(vb) / maxV) * 100) : 0;
    // Defensive rating is "lower is better" — flip the winner highlight for it
    const lowerIsBetter = def.key === 'avgDrtg' || def.key === 'totalL';
    const aWins = va != null && vb != null && (lowerIsBetter ? va < vb : va > vb);
    const bWins = va != null && vb != null && (lowerIsBetter ? vb < va : vb > va);
    return `
      <div class="cmp-stat-row ${aWins ? 'cmp-stat-winner-a' : ''} ${bWins ? 'cmp-stat-winner-b' : ''}">
        <div class="cmp-stat-bar-wrap right">
          <span class="cmp-stat-value a-val">${fmt(va)}</span>
          <div class="cmp-stat-bar-track"><div class="cmp-stat-bar-fill a" style="width:${pctA}%"></div></div>
        </div>
        <span class="cmp-stat-label">${def.label}</span>
        <div class="cmp-stat-bar-wrap">
          <div class="cmp-stat-bar-track"><div class="cmp-stat-bar-fill b" style="width:${pctB}%"></div></div>
          <span class="cmp-stat-value b-val">${fmt(vb)}</span>
        </div>
      </div>
    `;
  }).join('');
}

// Awards won by anyone on a given franchise's roster in a given season (or,
// for career scope, across every season of that franchise's history).
function teamAwardsInSeason(franchiseName, season) {
  if (DATA_MODE === 'api') {
    const h = teamHonorsCache.get(franchiseName) || { wins: [], eos: [], allStars: [] };
    const inSeason = x => x.season === season;
    return { wins: h.wins.filter(inSeason), eos: h.eos.filter(inSeason), allStars: h.allStars.filter(inSeason) };
  }
  const roster = rosterByFranchiseSeason.get(`${franchiseName}:${season}`) || [];
  const rosterIds = new Set(roster.map(p => p.player_id));
  const wins = AWARD_SHARES.filter(a => a.season === season && a.winner && rosterIds.has(a.player_id));
  const eos = EOS_TEAMS.filter(e => e.season === season && rosterIds.has(e.player_id));
  const allStars = [...rosterIds].filter(pid => isAllStar(pid, season)).map(pid => ({ player_id: pid, season }));
  return { wins, eos, allStars };
}

function teamAwardsAcrossCareer(franchiseName) {
  const span = franchiseSpans.get(franchiseName);
  if (!span) return { wins: [], eos: [], allStars: [] };
  const allWins = [], allEos = [], allStarsAll = [];
  span.rows.forEach(r => {
    const { wins, eos, allStars } = teamAwardsInSeason(franchiseName, r.season);
    allWins.push(...wins);
    allEos.push(...eos);
    allStarsAll.push(...allStars);
  });
  return { wins: allWins, eos: allEos, allStars: allStarsAll };
}

// Unique id counter for expand toggles so multiple calls don't collide.
let _cmpAccId = 0;

function renderCmpTeamAccomplishments(dataA, dataB) {
  const isCareer = dataA.season === undefined;

  function awardPillHtml(w, showSeason) {
    const player = careerById.get(w.player_id);
    const name = player ? player.player : w.player_id;
    return `<span class="award-pill won"><span class="award-trophy">\u{1F3C6}</span>${AWARD_LABELS[w.award] || w.award} \u2014 ${name}${showSeason ? ` (${w.season})` : ''}</span>`;
  }

  function eosPillHtml(e, showSeason) {
    const player = careerById.get(e.player_id);
    const name = player ? player.player : e.player_id;
    const label = e.team_type === 'All-NBA' ? `All-NBA ${e.team_number} Team`
      : e.team_type === 'All-Defense' ? `All-Defensive ${e.team_number} Team`
      : e.team_type === 'All-Rookie' ? `All-Rookie ${e.team_number} Team`
      : `${e.team_type} ${e.team_number}`;
    return `<span class="award-pill won">${label} \u2014 ${name}${showSeason ? ` (${e.season})` : ''}</span>`;
  }

  function allStarPillHtml(a, showSeason) {
    const player = careerById.get(a.player_id);
    return `<span class="award-pill won allstar-pill">\u2605 All-Star \u2014 ${player ? player.player : a.player_id}${showSeason ? ` (${a.season})` : ''}</span>`;
  }

  function summarize(franchiseName, data) {
    const { wins, eos, allStars } = isCareer
      ? teamAwardsAcrossCareer(franchiseName)
      : teamAwardsInSeason(franchiseName, data.season);

    const playoffLine = isCareer
      ? `${data.playoffSeasons} of ${data.totalSeasons} seasons reached the playoffs`
      : (data.playoffSeasons ? 'Reached the playoffs this season' : 'Missed the playoffs this season');

    const total = wins.length + eos.length + allStars.length;

    if (!isCareer) {
      const pills = [...wins.map(w => awardPillHtml(w, false)), ...eos.map(e => eosPillHtml(e, false)), ...allStars.map(a => allStarPillHtml(a, false))];
      return `
        <div class="cmp-accomplishments-col">
          <div class="cmp-accomplishments-name">${data.displayName}</div>
          <div class="cmp-accomplishments-line">${playoffLine}</div>
          <div class="cmp-accomplishments-pills">
            ${pills.length > 0 ? pills.join('') : '<span class="no-data-note" style="padding:6px 0;">No major individual awards, All-Stars or All-NBA/All-Defense selections this season.</span>'}
          </div>
        </div>`;
    }

    // Career mode: group by award/EOS type to get counts, then build summary badges
    const awardGroups = {};
    wins.forEach(w => {
      const label = AWARD_SHORT[w.award] || AWARD_LABELS[w.award] || w.award;
      awardGroups[label] = (awardGroups[label] || 0) + 1;
    });

    const eosGroups = {};
    eos.forEach(e => {
      const label = e.team_type === 'All-NBA' ? `All-NBA ${e.team_number} Team`
        : e.team_type === 'All-Defense' ? `All-Defensive ${e.team_number} Team`
        : e.team_type === 'All-Rookie' ? `All-Rookie ${e.team_number} Team`
        : `${e.team_type} ${e.team_number}`;
      eosGroups[label] = (eosGroups[label] || 0) + 1;
    });

    const summaryBadges = [
      ...Object.entries(awardGroups).map(([label, n]) =>
        `<span class="award-summary-badge"><span class="award-trophy">\u{1F3C6}</span> ${n}\u00d7 ${label}</span>`),
      ...(allStars.length ? [`<span class="award-summary-badge">\u2605 ${allStars.length}\u00d7 All-Star</span>`] : []),
      ...Object.entries(eosGroups).map(([label, n]) =>
        `<span class="award-summary-badge">${n}\u00d7 ${label}</span>`),
    ];

    if (total === 0) {
      return `
        <div class="cmp-accomplishments-col">
          <div class="cmp-accomplishments-name">${data.displayName}</div>
          <div class="cmp-accomplishments-line">${playoffLine}</div>
          <span class="no-data-note" style="padding:6px 0;">No major individual awards, All-Stars or All-NBA/All-Defense selections on record.</span>
        </div>`;
    }

    const uid = ++_cmpAccId;
    const detailId = `cmp-acc-detail-${uid}`;
    const btnId = `cmp-acc-btn-${uid}`;
    const allPills = [...wins.map(w => awardPillHtml(w, true)), ...eos.map(e => eosPillHtml(e, true)), ...allStars.map(a => allStarPillHtml(a, true))];
    const btnLabel = `Show all ${total} honors \u25be`;

    return `
      <div class="cmp-accomplishments-col">
        <div class="cmp-accomplishments-name">${data.displayName}</div>
        <div class="cmp-accomplishments-line">${playoffLine}</div>
        <div class="cmp-acc-summary">${summaryBadges.join('')}</div>
        <button class="cmp-acc-expand-btn" id="${btnId}" onclick="(function(){
          var detail = document.getElementById('${detailId}');
          var btn = document.getElementById('${btnId}');
          var open = detail.style.display !== 'none';
          detail.style.display = open ? 'none' : 'flex';
          btn.textContent = open ? '${btnLabel}' : 'Collapse \u25b4';
        })()">
          ${btnLabel}
        </button>
        <div id="${detailId}" class="cmp-accomplishments-pills" style="display:none;margin-top:10px;">
          ${allPills.join('')}
        </div>
      </div>`;
  }

  $('#cmp-team-accomplishments').innerHTML = `
    <div class="cmp-accomplishments-grid">
      ${summarize(cmpTeamA, dataA)}
      ${summarize(cmpTeamB, dataB)}
    </div>
  `;
}
