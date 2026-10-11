// ===================================================================
// BOOTSTRAP
// ===================================================================
renderHeroTicker();
renderOverviewChart();
renderScoreboard(LATEST_SEASON);
document.getElementById('topbar-player-count').textContent = CAREER.length.toLocaleString('en-US');
document.getElementById('player-explorer-count').textContent = CAREER.length.toLocaleString('en-US');
