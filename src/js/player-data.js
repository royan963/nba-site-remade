// ===================================================================
// PLAYER DEEP-DIVE: shooting zones, play-by-play, awards (app_part8)
// ===================================================================
const SHOOTING = toObjects(PLAYER_SHOOTING);
const PBP = toObjects(PLAYER_PBP);
const AWARD_SHARES = toObjects(PLAYER_AWARD_SHARES);
const EOS_TEAMS = toObjects(PLAYER_EOS_TEAMS);

const shootingByPlayer = new Map();
SHOOTING.forEach(s => {
  if (!shootingByPlayer.has(s.player_id)) shootingByPlayer.set(s.player_id, []);
  shootingByPlayer.get(s.player_id).push(s);
});
shootingByPlayer.forEach(list => list.sort((a, b) => a.season - b.season));

const pbpByPlayer = new Map();
PBP.forEach(p => {
  if (!pbpByPlayer.has(p.player_id)) pbpByPlayer.set(p.player_id, []);
  pbpByPlayer.get(p.player_id).push(p);
});
pbpByPlayer.forEach(list => list.sort((a, b) => a.season - b.season));

const awardsByPlayer = new Map();
AWARD_SHARES.forEach(a => {
  if (!awardsByPlayer.has(a.player_id)) awardsByPlayer.set(a.player_id, []);
  awardsByPlayer.get(a.player_id).push(a);
});

const eosByPlayer = new Map();
EOS_TEAMS.forEach(e => {
  if (!eosByPlayer.has(e.player_id)) eosByPlayer.set(e.player_id, []);
  eosByPlayer.get(e.player_id).push(e);
});

const LEAGUE_AVG = toObjects(LEAGUE_AVG_SHOOTING);
const leagueAvgBySeason = new Map(LEAGUE_AVG.map(r => [r.season, r]));

const AWARD_LABELS = {
  'nba mvp': 'MVP',
  'nba dpoy': 'Defensive Player of the Year',
  'nba mip': 'Most Improved Player',
  'nba roy': 'Rookie of the Year',
  'nba smoy': 'Sixth Man of the Year',
  'nba clutch_poy': 'Clutch Player of the Year',
  'aba mvp': 'ABA MVP',
  'aba roy': 'ABA Rookie of the Year',
  'baa roy': 'BAA Rookie of the Year',
};

const AWARD_SHORT = {
  'nba mvp': 'MVP',
  'nba dpoy': 'DPOY',
  'nba mip': 'MIP',
  'nba roy': 'ROY',
  'nba smoy': '6MOY',
  'nba clutch_poy': 'Clutch POY',
  'aba mvp': 'ABA MVP',
  'aba roy': 'ABA ROY',
  'baa roy': 'BAA ROY',
};
