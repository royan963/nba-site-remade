// ===================================================================
// SHOT PROFILE: rendering, interaction, season selector
// ===================================================================
let currentShotSeason = null;
let shotBarChart = null;
let currentShotView = 'court';

function renderShotProfile(playerId) {
  const seasons = shootingByPlayer.get(playerId) || [];

  if (seasons.length === 0) {
    $('#pc-shooting-panel').style.display = 'block';
    $('#pc-shooting-sub').textContent = 'Shot-location tracking by NBA.com begins in the 1996/97 season — not available for this player\u2019s career.';
    $('#pc-shooting-season').innerHTML = '';
    $('#pc-court-container').innerHTML = '<div class="no-data-note">No tracked shooting-zone data for this player.</div>';
    $('#pc-shot-bars-view').innerHTML = '';
    return;
  }

  $('#pc-shooting-panel').style.display = 'block';
  $('#pc-shooting-sub').textContent = 'Shot-location tracking by NBA.com begins in the 1996/97 season. Hover or tap a zone for details.';

  $('#pc-shooting-season').innerHTML = seasons.slice().reverse().map(s =>
    `<option value="${s.season}">${s.season}</option>`
  ).join('');
  currentShotSeason = seasons[seasons.length - 1].season;
  $('#pc-shooting-season').value = currentShotSeason;

  $('#pc-shooting-season').onchange = (e) => {
    currentShotSeason = parseInt(e.target.value, 10);
    renderShotForSeason(playerId);
  };

  renderShotForSeason(playerId);
}

function renderShotForSeason(playerId) {
  const seasons = shootingByPlayer.get(playerId) || [];
  const zoneData = seasons.find(s => s.season === currentShotSeason);
  if (!zoneData) return;

  if (currentShotView === 'court') {
    renderCourtView(zoneData);
  } else {
    renderBarsView(zoneData);
  }
}

function renderCourtView(zoneData) {
  const container = $('#pc-court-container');
  container.innerHTML = buildCourtSVG(zoneData);

  let tooltip = $('.shot-tooltip', container.parentElement);
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.className = 'shot-tooltip';
    container.parentElement.style.position = 'relative';
    container.parentElement.appendChild(tooltip);
  }

  $$('.court-zone', container).forEach(zoneEl => {
    zoneEl.addEventListener('mouseenter', (e) => {
      const zone = zoneEl.dataset.zone;
      const sub = zoneEl.dataset.sub;
      const pctFga = zoneEl.dataset.pctFga;
      const fgPct = zoneEl.dataset.fgPct;
      tooltip.innerHTML = `
        <div class="st-zone">${zone}</div>
        <div class="st-row"><span>${sub}</span></div>
        <div class="st-row"><span>FG%</span><b>${fgPct ? fmtPct(parseFloat(fgPct), 2) : '—'}</b></div>
        <div class="st-row"><span>Share of shots</span><b>${pctFga ? fmtPct(parseFloat(pctFga), 2) : '—'}</b></div>
      `;
      tooltip.style.opacity = 1;
    });
    zoneEl.addEventListener('mousemove', (e) => {
      const rect = container.parentElement.getBoundingClientRect();
      tooltip.style.left = (e.clientX - rect.left + 14) + 'px';
      tooltip.style.top = (e.clientY - rect.top - 10) + 'px';
    });
    zoneEl.addEventListener('mouseleave', () => {
      tooltip.style.opacity = 0;
    });
  });
}

function renderBarsView(zoneData) {
  const labels = ZONE_DEFS.map(z => z.sub);
  const fgPcts = ZONE_DEFS.map(z => zoneData[z.pctKey]);
  const shares = ZONE_DEFS.map(z => zoneData[z.key]);

  const leagueRow = leagueAvgBySeason.get(currentShotSeason);
  const leagueFgKeyMap = {
    fg_pct_0_3: 'avg_fg_pct_0_3', fg_pct_3_10: 'avg_fg_pct_3_10',
    fg_pct_10_16: 'avg_fg_pct_10_16', fg_pct_16_3p: 'avg_fg_pct_16_3p',
    fg_pct_3p: 'avg_fg_pct_3p',
  };
  const leagueFgPcts = ZONE_DEFS.map(z => leagueRow ? leagueRow[leagueFgKeyMap[z.pctKey]] : null);
  const leagueShareKeyMap = {
    pct_fga_0_3: 'avg_pct_fga_0_3', pct_fga_3_10: 'avg_pct_fga_3_10',
    pct_fga_10_16: 'avg_pct_fga_10_16', pct_fga_16_3p: 'avg_pct_fga_16_3p',
    pct_fga_3p: 'avg_pct_fga_3p',
  };
  const leagueShares = ZONE_DEFS.map(z => leagueRow ? leagueRow[leagueShareKeyMap[z.key]] : null);

  const ctx = $('#pc-shot-bar-chart').getContext('2d');
  if (shotBarChart) shotBarChart.destroy();
  const datasets = [
    {
      label: 'Player FG%',
      data: fgPcts.map(v => v != null ? v * 100 : null),
      backgroundColor: fgPcts.map(v => fgPctColor(v)),
      yAxisID: 'y',
      borderRadius: 4,
      order: 1,
    },
  ];
  if (leagueRow) {
    datasets.push({
      label: 'League Avg FG%',
      data: leagueFgPcts.map(v => v != null ? v * 100 : null),
      backgroundColor: 'rgba(241,235,224,0.12)',
      borderColor: 'rgba(241,235,224,0.55)',
      borderWidth: 1.5,
      yAxisID: 'y',
      borderRadius: 4,
      order: 2,
    });
  }

  shotBarChart = new Chart(ctx, {
    type: 'bar',
    data: { labels, datasets },
    options: baseChartOptions({
      plugins: {
        legend: {
          display: !!leagueRow,
          labels: { color: PALETTE.chalkDim, font: { family: "'JetBrains Mono', monospace", size: 11 }, boxWidth: 12, boxHeight: 12 }
        },
        tooltip: {
          backgroundColor: '#1f1a16', borderColor: 'rgba(241,235,224,0.18)', borderWidth: 1,
          titleColor: PALETTE.amber, bodyColor: PALETTE.chalk,
          titleFont: { family: "'JetBrains Mono', monospace", size: 12 },
          bodyFont: { family: "'JetBrains Mono', monospace", size: 12 },
          callbacks: {
            label: (ctx) => {
              if (ctx.datasetIndex === 0) {
                return `Player FG%: ${ctx.parsed.y != null ? ctx.parsed.y.toFixed(2) + '%' : '—'}`;
              }
              return `League Avg FG%: ${ctx.parsed.y != null ? ctx.parsed.y.toFixed(2) + '%' : '—'}`;
            },
            afterLabel: (ctx) => {
              if (ctx.datasetIndex === 0) {
                return `Player share of shots: ${shares[ctx.dataIndex] != null ? (shares[ctx.dataIndex]*100).toFixed(2) + '%' : '—'}`;
              }
              return `League share of shots: ${leagueShares[ctx.dataIndex] != null ? (leagueShares[ctx.dataIndex]*100).toFixed(2) + '%' : '—'}`;
            }
          }
        }
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: PALETTE.chalkDim, font: { size: 10.5 } } },
        y: { grid: { color: PALETTE.grid }, ticks: { color: PALETTE.chalkDim, callback: v => v + '%' }, title: { display: true, text: 'FG%', color: PALETTE.chalkDim, font: { family: "'JetBrains Mono', monospace", size: 11 } } }
      }
    })
  });
}

$$('#pc-shot-view-toggle .pill-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    currentShotView = btn.dataset.shotview;
    $$('#pc-shot-view-toggle .pill-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    $('#pc-shot-court-view').style.display = currentShotView === 'court' ? 'block' : 'none';
    $('#pc-shot-bars-view').style.display = currentShotView === 'bars' ? 'block' : 'none';
    if (currentPlayerId) renderShotForSeason(currentPlayerId);
  });
});
