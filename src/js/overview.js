// ===================================================================
// HERO TICKER — headline all-time facts
// ===================================================================
function renderHeroTicker() {
  const first = ERA[0], last = ERA[ERA.length - 1];
  const peakPace = ERA.reduce((a, b) => (b.pace || 0) > (a.pace || 0) ? b : a);
  const lowPace = ERA.filter(e => e.pace).reduce((a, b) => (b.pace) < (a.pace) ? b : a);
  const top3pa = ERA.reduce((a, b) => (b.x3p_ar || 0) > (a.x3p_ar || 0) ? b : a);
  const topScorer = CAREER.reduce((a, b) => (b.pts || 0) > (a.pts || 0) ? b : a);

  const cells = [
    { label: 'Fastest season', value: `${fmtNum(peakPace.pace, 1)}`, sub: `pace · ${peakPace.season}` },
    { label: 'Slowest season', value: `${fmtNum(lowPace.pace, 1)}`, sub: `pace · ${lowPace.season}` },
    { label: 'Peak 3PT rate', value: fmtPct(top3pa.x3p_ar), sub: `of all shots · ${top3pa.season}` },
    { label: 'All-time scorer', value: topScorer.player, sub: `${fmtInt(topScorer.pts)} pts` },
    { label: 'Seasons tracked', value: ERA.length, sub: `${first.season}–${last.season}` },
  ];

  $('#hero-ticker').innerHTML = cells.map(c => `
    <div class="ticker-cell">
      <span class="t-label">${c.label}</span>
      <div class="t-value">${c.value}</div>
      <div class="t-sub">${c.sub}</div>
    </div>
  `).join('');
}


// ===================================================================
// SCOREBOARD / SEASON SLIDER (signature element)
// ===================================================================
function eraLabel(season) {
  if (season < 1950) return 'BAA Founding Era';
  if (season < 1954) return 'Pre-Shot-Clock Era';
  if (season < 1968) return 'Russell Dynasty Era';
  if (season < 1980) return 'Run-and-Gun Era';
  if (season < 1992) return 'Early 3PT / Showtime Era';
  if (season < 2005) return 'Hand-Check Era';
  if (season < 2015) return 'Pace-and-Space Dawn';
  return 'Three-Point Era';
}

let prevSeasonStats = null;

function renderScoreboard(season) {
  // find nearest available season with data (handles any gaps)
  let e = eraBySeason.get(season);
  if (!e) {
    const seasonsAvail = ERA.map(x => x.season);
    const nearest = seasonsAvail.reduce((a, b) => Math.abs(b - season) < Math.abs(a - season) ? b : a);
    e = eraBySeason.get(nearest);
  }

  $('#sb-season').textContent = e.season;
  $('#sb-era-label').textContent = eraLabel(e.season);

  const slider = $('#season-slider');
  const pct = ((e.season - FIRST_SEASON) / (LATEST_SEASON - FIRST_SEASON)) * 100;
  slider.style.setProperty('--fill', pct + '%');
  if (slider.value != e.season) slider.value = e.season;

  const stats = [
    { label: 'Pace', value: fmtNum(e.pace, 1), unit: 'poss/48', key: 'pace' },
    { label: 'Pts / Game', value: fmtNum(e.pts_per_game, 1), unit: 'pts', key: 'pts_per_game' },
    { label: '3PA Rate', value: fmtPct(e.x3p_ar), unit: '', key: 'x3p_ar' },
    { label: '3P%', value: fmtPct(e.x3p_percent), unit: '', key: 'x3p_percent' },
    { label: 'Off. Rating', value: fmtNum(e.o_rtg, 1), unit: '', key: 'o_rtg' },
    { label: 'True Shooting', value: fmtPct(e.ts_percent), unit: '', key: 'ts_percent' },
  ];

  $('#sb-stats').innerHTML = stats.map(s => {
    let deltaHtml = '';
    if (prevSeasonStats) {
      const prevVal = prevSeasonStats[s.key];
      const curVal = e[s.key];
      if (prevVal != null && curVal != null && prevVal !== 0) {
        const diff = curVal - prevVal;
        const dir = Math.abs(diff) < (Math.abs(prevVal) * 0.001) ? 'flat' : (diff > 0 ? 'up' : 'down');
        const arrow = dir === 'up' ? '▲' : dir === 'down' ? '▼' : '·';
        deltaHtml = `<span class="delta ${dir}">${arrow} ${diff > 0 ? '+' : ''}${fmtNum(diff, 2)}</span>`;
      }
    }
    return `<div class="sb-stat">
      <span class="label">${s.label}</span>
      <div class="value">${s.value}<span class="unit">${s.unit}</span></div>
      ${deltaHtml}
    </div>`;
  }).join('');

  prevSeasonStats = e;
}

const slider = $('#season-slider');
slider.addEventListener('input', () => {
  prevSeasonStats = null; // no delta needed on manual scrub for clarity... actually keep continuity
  renderScoreboard(parseInt(slider.value, 10));
});

// Playback
let playInterval = null;
let playing = false;
$('#play-btn').addEventListener('click', () => {
  playing = !playing;
  $('#play-btn').innerHTML = playing ? '&#10074;&#10074;' : '&#9654;';
  $('#playback-label').textContent = playing ? 'Playing through history…' : 'Drag the slider — or hit play to watch the league evolve';
  if (playing) {
    if (parseInt(slider.value, 10) >= LATEST_SEASON) slider.value = FIRST_SEASON;
    playInterval = setInterval(() => {
      let v = parseInt(slider.value, 10) + 1;
      if (v > LATEST_SEASON) {
        clearInterval(playInterval);
        playing = false;
        $('#play-btn').innerHTML = '&#9654;';
        $('#playback-label').textContent = 'Drag the slider — or hit play to watch the league evolve';
        return;
      }
      slider.value = v;
      renderScoreboard(v);
    }, 110);
  } else {
    clearInterval(playInterval);
  }
});

// ===================================================================
// OVERVIEW CHART — pace + scoring dual axis
// ===================================================================
let overviewChart = null;
function renderOverviewChart() {
  const labels = ERA.map(e => e.season);
  const ctx = $('#overview-chart').getContext('2d');
  if (overviewChart) overviewChart.destroy();
  overviewChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Pace (poss/48)',
          data: ERA.map(e => e.pace),
          borderColor: PALETTE.blue,
          backgroundColor: PALETTE.blueDim,
          yAxisID: 'y',
          tension: 0.25,
          pointRadius: 0,
          borderWidth: 2,
          fill: true,
        },
        {
          label: 'Points / Game',
          data: ERA.map(e => e.pts_per_game),
          borderColor: PALETTE.amber,
          backgroundColor: PALETTE.amberDim,
          yAxisID: 'y1',
          tension: 0.25,
          pointRadius: 0,
          borderWidth: 2,
          fill: true,
        }
      ]
    },
    options: baseChartOptions({
      scales: {
        x: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, maxTicksLimit: 12 } },
        y: { position: 'left', grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim }, title: { display: true, text: 'Pace', color: PALETTE.blue, font: { family: "'JetBrains Mono', monospace", size: 11 } } },
        y1: { position: 'right', grid: { display: false }, ticks: { color: PALETTE.chalkDim }, title: { display: true, text: 'Pts/Game', color: PALETTE.amber, font: { family: "'JetBrains Mono', monospace", size: 11 } } },
      }
    })
  });
}
