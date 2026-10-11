// ===================================================================
// AWARDS TIMELINE
// ===================================================================
function renderAwardsTimeline(playerId) {
  const shares = awardsByPlayer.get(playerId) || [];
  const eosSelections = eosByPlayer.get(playerId) || [];

  const allStarSeasons = Array.from(allStarByPlayer.get(playerId) || []);
  if (shares.length === 0 && eosSelections.length === 0 && allStarSeasons.length === 0) {
    $('#pc-awards-panel').style.display = 'none';
    return;
  }
  $('#pc-awards-panel').style.display = 'block';

  // merge into one timeline keyed by season
  const bySeasonMap = new Map();
  const touchSeason = (season) => {
    if (!bySeasonMap.has(season)) bySeasonMap.set(season, { wins: [], votes: [], teams: [], allStar: false });
    return bySeasonMap.get(season);
  };

  shares.forEach(a => {
    const bucket = touchSeason(a.season);
    if (a.winner) {
      bucket.wins.push(a);
    } else if (a.share > 0.05) {
      // only show meaningful voting finishes, not every single vote-getter
      bucket.votes.push(a);
    }
  });

  eosSelections.forEach(e => {
    touchSeason(e.season).teams.push(e);
  });

  allStarSeasons.forEach(s => { touchSeason(s).allStar = true; });

  const seasons = Array.from(bySeasonMap.keys()).sort((a, b) => b - a); // most recent first

  if (seasons.length === 0) {
    $('#pc-awards-timeline').innerHTML = `<div class="awards-empty">No major awards, All-Star or All-NBA/All-Defense selections on record.</div>`;
    return;
  }

  $('#pc-awards-timeline').innerHTML = seasons.map(season => {
    const bucket = bySeasonMap.get(season);
    const pills = [];

    bucket.wins.forEach(a => {
      pills.push(`<span class="award-pill won"><span class="award-trophy">🏆</span>${AWARD_LABELS[a.award] || a.award}</span>`);
    });
    if (bucket.allStar) pills.push(`<span class="award-pill won allstar-pill">★ All-Star</span>`);
    bucket.teams.forEach(e => {
      const label = e.team_type === 'All-NBA' ? `All-NBA ${e.team_number} Team`
        : e.team_type === 'All-Defense' ? `All-Defensive ${e.team_number} Team`
        : e.team_type === 'All-Rookie' ? `All-Rookie ${e.team_number} Team`
        : `${e.team_type} ${e.team_number}`;
      pills.push(`<span class="award-pill won">${label}</span>`);
    });
    bucket.votes.forEach(a => {
      const pct = Math.round(a.share * 100);
      pills.push(`<span class="award-pill">${AWARD_SHORT[a.award] || a.award} voting (${pct}% share)</span>`);
    });

    return `<div class="awards-timeline-row">
      <span class="awards-season-tag">${season}</span>
      <div>${pills.join('')}</div>
    </div>`;
  }).join('');
}
