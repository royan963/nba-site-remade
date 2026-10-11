// ===================================================================
// TEAM EXPLORER VIEW (franchise-lineage aware: groups relocated teams together)
// ===================================================================
const TEAM_STAT_OPTIONS = [
  { key: 'w', label: 'Wins' },
  { key: 'srs', label: 'SRS (Strength)' },
  { key: 'o_rtg', label: 'Off. Rating' },
  { key: 'd_rtg', label: 'Def. Rating' },
  { key: 'pace', label: 'Pace' },
  { key: 'pts_per_game', label: 'Points/Game' },
];
let currentTeamStat = 'w';
let teamChart = null;
let currentFranchise = null;
let teamsInitialized = false;

// franchiseSpans / geoByFranchise are defined in app_part7.js (map module) and
// reused here so the grid, map, and detail panel all agree on what a "team" is.

function renderTeamGrid() {
  const franchises = Array.from(franchiseSpans.keys()).sort();
  $('#team-grid').innerHTML = franchises.map(fr => {
    const span = franchiseSpans.get(fr);
    const latestRow = span.rows[span.rows.length - 1];
    const displayName = latestRow.current_name || latestRow.team_name;
    return `<button class="team-chip" data-franchise="${fr}">
      <div class="tc-name">${displayName}</div>
      <div class="tc-meta">${span.minSeason}–${span.maxSeason}${latestRow.status !== 'active' ? ' · defunct' : ''}</div>
    </button>`;
  }).join('');

  $$('#team-grid .team-chip').forEach(chip => {
    chip.addEventListener('click', () => selectTeam(chip.dataset.franchise));
  });
}

function renderTeamStatPills() {
  $('#tc-stat-pills').innerHTML = TEAM_STAT_OPTIONS.map(s =>
    `<button class="pill-btn ${s.key === currentTeamStat ? 'active' : ''}" data-stat="${s.key}">${s.label}</button>`
  ).join('');
  $$('#tc-stat-pills .pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      currentTeamStat = btn.dataset.stat;
      $$('#tc-stat-pills .pill-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderTeamChart(currentFranchise);
    });
  });
}

function selectTeam(franchiseName) {
  currentFranchise = franchiseName;
  $$('#team-grid .team-chip').forEach(c => c.classList.toggle('active', c.dataset.franchise === franchiseName));

  const span = franchiseSpans.get(franchiseName);
  if (!span) return;
  const list = span.rows;
  const latest = list[list.length - 1];
  const totalSeasons = list.length;
  const playoffSeasons = list.filter(t => t.playoffs).length;
  const displayName = latest.current_name || latest.team_name;

  // build a human-readable lineage string if the franchise changed cities/names
  const cityPath = franchiseCityPath(franchiseName);
  const nameChain = [];
  let lastName = null;
  list.forEach(r => { if (r.team_name !== lastName) { nameChain.push(r.team_name); lastName = r.team_name; } });
  const lineageNote = nameChain.length > 1 ? nameChain.join(' → ') : '';

  $('#team-panel').style.display = 'block';
  $('#tc-name').textContent = displayName;
  $('#tc-meta').innerHTML = `${span.minSeason}–${span.maxSeason} · ${totalSeasons} seasons · ${playoffSeasons} playoff appearances` +
    (latest.status !== 'active' ? ' · <span style="color:var(--chalk-dim)">no longer in the NBA</span>' : ` · currently "${latest.abbr || ''}"`) +
    (lineageNote ? `<br><span style="opacity:0.75;">${lineageNote}</span>` : '');

  renderTeamStatPills();
  renderTeamChart(franchiseName);
  initRosterForFranchise(franchiseName);

  $('#team-panel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderTeamChart(franchiseName) {
  const span = franchiseSpans.get(franchiseName);
  const list = span.rows;
  const statDef = TEAM_STAT_OPTIONS.find(s => s.key === currentTeamStat);
  const labels = list.map(t => t.season);
  const data = list.map(t => t[currentTeamStat]);

  const ctx = $('#team-chart').getContext('2d');
  if (teamChart) teamChart.destroy();
  teamChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: statDef.label,
        data,
        borderColor: PALETTE.blue,
        backgroundColor: PALETTE.blueDim,
        tension: 0.25,
        pointRadius: 2,
        pointHoverRadius: 6,
        borderWidth: 2.5,
        fill: true,
        segment: {
          borderColor: ctx => {
            const t = list[ctx.p1DataIndex];
            return t && t.playoffs ? PALETTE.amber : PALETTE.blue;
          }
        }
      }]
    },
    options: baseChartOptions({
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1f1a16', borderColor: 'rgba(241,235,224,0.18)', borderWidth: 1,
          titleColor: PALETTE.amber, bodyColor: PALETTE.chalk,
          titleFont: { family: "'JetBrains Mono', monospace", size: 12 },
          bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
          callbacks: {
            afterTitle: (items) => {
              const t = list[items[0].dataIndex];
              return `${t.team_name} (${t.city}) · ${t.w ?? '\u2014'}-${t.l ?? '\u2014'} · ${t.playoffs ? 'Made playoffs' : 'Missed playoffs'}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, maxTicksLimit: 14 } },
        y: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim } }
      }
    })
  });
}

function initTeamsView() {
  if (teamsInitialized) return;
  teamsInitialized = true;
  renderTeamGrid();
}
