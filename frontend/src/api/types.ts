// Shapes returned by the API (see backend/app/routers).

export interface PlayerSummary {
  player_id: string;
  player: string;
  pos: string | null;
  hof: boolean;
  ht_in_in: number | null;
  wt: number | null;
  seasons_played: number;
  first_season: number;
  last_season: number;
  g: number; pts: number; trb: number; ast: number; stl: number; blk: number;
  fg: number; fga: number; x3p: number; x3pa: number; ft: number; fta: number;
  ppg: number | null; rpg: number | null; apg: number | null;
  ws: number | null; vorp: number | null; all_star: number;
}

export interface PlayerDetail extends PlayerSummary {
  draft: { season: number; overall_pick: number | null; round: number | null; tm: string; college: string | null } | null;
  all_star_seasons: number[];
}

export interface Per100 {
  pts: number | null; trb: number | null; ast: number | null; stl: number | null; blk: number | null;
  tov: number | null; o_rtg: number | null; d_rtg: number | null;
}

export interface PlayerSeason {
  season: number;
  player: string;
  team: string;
  teams: string[];
  combined: boolean;
  pos: string | null;
  age: number | null;
  g: number | null; gs: number | null; mp: number | null;
  pts: number | null; trb: number | null; ast: number | null; stl: number | null; blk: number | null;
  fg_pct: number | null; x3p_pct: number | null; ft_pct: number | null;
  per: number | null; ts_pct: number | null; usg_pct: number | null; ws: number | null; ws_48: number | null;
  obpm: number | null; dbpm: number | null; bpm: number | null; vorp: number | null;
  per100: Per100 | null;
}

export interface ShootingSeason {
  season: number;
  avg_dist: number | null;
  pct_fga_0_3: number | null; fg_pct_0_3: number | null;
  pct_fga_3_10: number | null; fg_pct_3_10: number | null;
  pct_fga_10_16: number | null; fg_pct_10_16: number | null;
  pct_fga_16_3p: number | null; fg_pct_16_3p: number | null;
  pct_fga_3p: number | null; fg_pct_3p: number | null;
  pct_corner_3: number | null; corner_3_pct: number | null;
  pct_dunks: number | null; num_dunks: number | null;
  [key: string]: number | string | null;
}

export interface PbpSeason {
  season: number;
  pg_pct: number | null; sg_pct: number | null; sf_pct: number | null; pf_pct: number | null; c_pct: number | null;
  on_court_plus_minus: number | null; net_plus_minus: number | null;
  bad_pass_to: number | null; lost_ball_to: number | null;
  shooting_foul_committed: number | null; off_foul_committed: number | null;
  shooting_foul_drawn: number | null; off_foul_drawn: number | null;
  pts_generated_by_ast: number | null; and1: number | null; fga_blocked: number | null;
  [key: string]: number | null;
}

export interface AwardShare { season: number; award: string; share: number | null; winner: boolean; player_id?: string; player?: string }
export interface AllLeagueTeam { season: number; team_type: string; team_number: string; player_id?: string; player?: string }
export interface PlayerHonors { awards: AwardShare[]; all_league_teams: AllLeagueTeam[]; all_star_seasons: number[]; title_seasons?: number[]; finals_mvp_seasons?: number[] }

export interface SimilarResponse {
  fingerprint: Record<string, number | null> | null;
  styles?: { key: string; name: string; share: number }[];
  matches: (PlayerSummary & { score: number; styles?: { key: string; name: string; share: number }[] })[];
}

export interface LeaderRow extends PlayerSummary { rank: number }

export interface TeamSeason {
  season: number;
  franchise: string;
  team_name: string;
  abbr: string;
  city: string;
  lat: number; lng: number;
  current_name: string | null;
  status: string;
  w: number | null; l: number | null;
  srs: number | null; o_rtg: number | null; d_rtg: number | null; pace: number | null; pts_per_game: number | null;
  playoffs: boolean;
  primary_color: string; secondary_color: string; badge_code: string;
}

export interface TeamSummary {
  franchise: string;
  first_season: number; last_season: number; seasons: number; playoff_seasons: number;
  wins: number; losses: number;
  current_name: string | null; status: string; team_name: string; abbr: string;
  primary_color: string; secondary_color: string; badge_code: string; city: string;
}

export interface RosterRow {
  player_id: string; player: string; season: number; team: string; pos: string | null; age: number | null;
  g: number | null; gs: number | null; mp: number | null; pts: number | null; trb: number | null; ast: number | null;
  stl: number | null; blk: number | null; fg_pct: number | null; x3p_pct: number | null; ft_pct: number | null;
}

export interface TeamHonors {
  awards: AwardShare[];
  all_league_teams: AllLeagueTeam[];
  all_stars: { season: number; player_id: string; player: string; replaced: boolean }[];
}

export interface LeagueTrend {
  season: number; pace: number | null; o_rtg: number | null; d_rtg: number | null; x3p_ar: number | null;
  ts_percent: number | null; pts_per_game: number | null; x3pa_per_game: number | null; x3p_percent: number | null;
  fg_percent: number | null; ft_per_game: number | null; orb_per_game: number | null; ast_per_game: number | null;
  num_teams: number;
  [key: string]: number | null;
}

export interface LeagueShooting { season: number; [key: string]: number | null }

export interface Meta { first_season: number; latest_season: number; loaded_at: string; similarity_features: string[]; players: number; playoffs_through: number; series_through: number }

export type Align = 'experience' | 'age' | 'calendar';
export type Basis = 'raw' | 'per100' | 'index';

export interface CompareSide {
  season: number; age: number | null; teams: string[]; experience: number;
  raw: { g: number | null; mp: number | null; pts: number | null; trb: number | null; ast: number | null };
  league: { pace: number | null; ts_pct: number | null };
  honors: string[];
  stats: Record<string, number | null>;
}
export interface CompareResponse {
  a: PlayerSummary; b: PlayerSummary; align: Align; basis: Basis;
  stats: { key: string; label: string; lower_is_better: boolean }[];
  positions: { position: number; a: CompareSide | null; b: CompareSide | null;
               same_season?: { teammates: boolean; shared_teams: string[] } }[];
}

// ---- accounts & lineups -------------------------------------------------------
export interface Me { id: number; username: string; display_name: string; bio: string; created_at: number; email: string }
export interface PublicUser { id: number; username: string; display_name: string; bio: string; created_at: number }

export interface Favorites {
  players: { player_id: string; player: string; first_season: number; last_season: number; hof: boolean }[];
  teams: { slug: string; franchise: string }[];
}

export interface SavedComparison {
  id: number; kind: 'players' | 'teams'; a: string; b: string; params: string; title: string; note: string;
  is_public: boolean; created_at: number; path: string;
}

export interface LineupRatings {
  talent: number | null; scoring: number | null; playmaking: number | null; rebounding: number | null;
  steals: number | null; blocks: number | null; defense: number | null; efficiency: number | null; spacing: number | null;
}
export interface LineupPlayer {
  player_id: string; player: string; hof: boolean; season: number; age: number | null; teams: string[]; pos: string | null;
  pts: number | null; trb: number | null; ast: number | null; bpm: number | null; ws_48: number | null; usage: number | null;
  rating: number | null; ratings: LineupRatings; tags: string[];
}
export interface LineupScore {
  complete: boolean; overall: number | null; overall_exact: number | null; real_percentile: number | null; grade: string | null;
  categories: { key: string; label: string; score: number }[];
  players: LineupPlayer[]; fit_notes: string[]; notes: string[];
}
export interface LineupSummary { id: number; name: string; description: string; is_public: boolean; overall: number | null;
  created_at: number; updated_at: number; owner?: { username: string; display_name: string } }
export interface Lineup { id: number; name: string; description: string; is_public: boolean; created_at: number; updated_at: number;
  owner: { username: string; display_name: string }; score: LineupScore; mine?: boolean }
export interface PlayerLineupSeasons {
  player_id: string; best_season: number | null;
  seasons: { season: number; age: number | null; teams: string[]; g: number; pts: number | null; trb: number | null; ast: number | null; rating: number | null }[];
}
export interface Profile { user: PublicUser; lineups: LineupSummary[]; comparisons: SavedComparison[] }

// ---- models -------------------------------------------------------------------
export interface MvpModel {
  metrics: { seasons: number; top1: number; top3: number; baseline_top1: number; mean_winner_rank: number; trained_through: number };
  importances: { feature: string; label: string; importance: number }[];
  misses: { season: number; predicted: string; actual: string; predicted_name: string | null; actual_name: string | null }[];
  latest_season: number; latest_has_votes: boolean; games_rule_season: number; games_rule: { min: number; hard_min: number };
  preseason: { season: number; base_season: number; metrics: { seasons: number; top1: number; top3: number; baseline_top1: number; favorite_prob: number; features: string[] } } | null;
  seasons: number[];
}
export interface MvpCandidate {
  season: number; player_id: string; player: string; hof: boolean; pos: string | null; rank: number;
  predicted_share: number; win_prob: number; actual_share: number | null; actual_rank: number | null; winner: boolean;
  eligible: boolean; needs_exception: boolean; team: string | null; g: number | null; win_pct: number | null;
  pts: number | null; trb: number | null; ast: number | null; per: number | null; ws: number | null; bpm: number | null; vorp: number | null;
}
export interface ChampionMetrics { seasons: number; top1: number; top3: number; baseline_top1: number; power: number }
export interface ChampionModel {
  metrics: ChampionMetrics & { trained_through: number };
  weights: { feature: string; label: string; weight: number }[];
  misses: { season: number; predicted: string; actual: string }[];
  latest_season: number; latest_has_champion: boolean;
  preseason: { season: number; base_season: number; metrics: ChampionMetrics; weights: { feature: string; label: string; weight: number }[] } | null;
  seasons: number[];
}
export interface ChampionTeam {
  season: number; franchise: string; team: string; team_name: string | null; rank: number; win_prob: number;
  kind: 'backtest' | 'prediction' | 'preseason'; champion: boolean | null; result: string | null;
  w: number | null; l: number | null; srs: number | null; net: number | null; star_id: string | null; star: string | null; top_bpm: number | null;
}
export interface ChampionSeason { season: number; kind: 'backtest' | 'prediction' | 'preseason'; stats_season: number; teams: ChampionTeam[] }
export interface MvpSeason { season: number; kind: 'preseason' | 'prediction' | 'backtest'; stats_season: number; candidates: MvpCandidate[] }
export interface Archetype {
  id: number; key: string; name: string; description: string; rule_based: boolean;
  profile: Record<string, number>; share_by_decade: Record<string, number>;
  examples: { player_id: string; player: string | null; season: number }[];
  classic_examples: { player_id: string; player: string | null; season: number }[];
}
export interface ArchetypeModel {
  method: { k: number; train_from: number; min_minutes: number; features: string[]; feature_labels: Record<string, string>; first_season: number };
  archetypes: Archetype[];
  trend: { seasons: number[]; shares: Record<string, number[]> };
}
export interface ArchetypePlayers {
  archetype: Archetype; decade: number | null;
  players: { player_id: string; season: number; fit: number; secondary: string | null; player: string; hof: boolean;
             pts: number | null; trb: number | null; ast: number | null; mp: number | null; g: number | null; team: string }[];
}
export interface StyleShare { key: string; name: string; share: number }
export interface PlayerArchetypes {
  player_id: string; main: { key: string; name: string; description: string } | null; features_total: number;
  mix: StyleShare[];
  seasons: { season: number; key: string; name: string; secondary_key: string; secondary: string; fit: number; features_used: number;
             mix: StyleShare[] }[];
}
export interface ProjectionHorizon {
  h: number; season: number; age: number | null; p_active: number;
  pts: number | null; pts_lo: number | null; pts_hi: number | null; trb: number | null; trb_lo: number | null; trb_hi: number | null;
  ast: number | null; ast_lo: number | null; ast_hi: number | null; mp: number | null; mp_lo: number | null; mp_hi: number | null;
  ts_pct: number | null;
}
export interface PlayerProjection {
  player_id: string; projected: boolean; base_season: number; horizons: ProjectionHorizon[];
  comps: { rank: number; comp_id: string; comp_season: number; similarity: number; player: string; hof: boolean }[];
}
export interface ProjectionModel {
  latest_season: number;
  method: { k: number; pool_from: number; min_games: number; min_mp: number; band: number[] };
  metrics: { seasons: string; horizons: { h: number; n: number; active_brier: number; active_brier_base: number;
    pts: { model: number; last_season: number; aging_curve: number; band_coverage: number };
    trb: { model: number; last_season: number; aging_curve: number; band_coverage: number };
    ast: { model: number; last_season: number; aging_curve: number; band_coverage: number } }[] };
  top_scorers: ProjectionRow[]; risers: ProjectionRow[]; decliners: ProjectionRow[];
}
export interface ProjectionRow {
  player_id: string; player: string; hof: boolean; age: number /* age next season */; team: string; now_pts: number; pts: number;
  pts_lo: number; pts_hi: number; p_active: number; change: number;
}
export interface SearchResponse {
  query: string; scope: 'seasons' | 'careers'; stat: string; stat_label: string; stat_is_pct: boolean; order: 'asc' | 'desc';
  filters: { index: number | null; kind: string; label: string }[]; dropped: number[];
  ignored: string[]; notes: string[]; understood: boolean; season_note: string | null; examples: string[];
  name_matches: { player_id: string; player: string; hof: boolean; first_season: number; last_season: number }[];
  results: (Record<string, number | string | boolean | null> & { player_id: string; player: string; hof: boolean; value: number })[];
}

// ---- playoffs -----------------------------------------------------------------------
export interface PlayoffLine {
  g: number | null; mpg: number | null; ppg: number | null; rpg: number | null; apg: number | null; spg: number | null; bpg: number | null;
  fg_pct: number | null; x3p_pct: number | null; ft_pct: number | null; ts_pct: number | null;
  pts: number | null; trb: number | null; ast: number | null; stl: number | null; blk: number | null; x3p: number | null;
}
export interface PlayerPlayoffs {
  player_id: string;
  finals_mvp_seasons: number[];
  titles: { season: number; team: string; franchise: string; team_name: string | null }[];
  seasons: (PlayoffLine & { season: number; team: string; team_name: string | null; result: string | null })[];
  career: PlayoffLine | null;
}
export interface TeamPlayoffs {
  franchise: string; titles: number[]; finals_appearances: number; finals_losses: number[]; playoff_seasons: number;
  series_won: number; series_lost: number;
  seasons: { season: number; team: string; team_name: string | null; series_won: number; series_lost: number; games_won: number;
             games_lost: number; result: string; rff_deepest: number | null; champion: boolean }[];
  series: { season: number; round: string; round_label: string | null; rff: number | null; opponent: string; opponent_name: string | null;
            won: boolean; wins: number; losses: number; complete: boolean }[];
}
export interface ChampionRow {
  season: number; champion: string | null; champion_abbr: string; champion_franchise: string;
  runner_up: string | null; runner_up_abbr: string; runner_up_franchise: string; wins: number; losses: number;
  finals_mvp: { player_id: string; player: string } | null;
}
export interface ChampionsResponse { champions: ChampionRow[]; titles_by_franchise: Record<string, number> }
export interface PlayoffLeader {
  rank: number; player_id: string; player: string; hof: boolean; pos: string | null; first_season: number; last_season: number;
  g: number; pts: number; trb: number; ast: number; stl: number; blk: number; x3p: number; ppg: number | null; rpg: number | null;
  apg: number | null; titles: number;
}

// ---- game-by-game -------------------------------------------------------------------
export interface GameRow {
  date: string; game_ref: string; season: number; playoffs: boolean; team: string; opponent: string; opponent_name: string | null;
  home: boolean; result: 'W' | 'L' | null; score: string | null; ot: number;
  mp: number | null; pts: number | null; trb: number | null; ast: number | null; stl: number | null; blk: number | null; tov: number | null;
  pf: number | null; fg: number | null; fga: number | null; x3p: number | null; x3pa: number | null; ft: number | null; fta: number | null;
  orb: number | null; drb: number | null; pm: number | null; started?: boolean | null; src?: string;
}
export interface GameLog { player_id: string; seasons: { season: number; regular: number; playoffs: number }[]; season: number | null;
  type: 'regular' | 'playoffs'; games: GameRow[]; rebuilt_games: number }
export interface CareerHighs {
  player_id: string; type: 'regular' | 'playoffs'; highs: Record<string, GameRow & { value: number; times: number }>;
  milestones: { games: number; pts30: number; pts40: number; pts50: number; double_doubles: number; triple_doubles: number };
  first_game: string | null; last_game: string | null; top_scoring_games: GameRow[];
}
export interface GameCoverage { seasons: { season: number; playoffs: boolean; games: number; complete: number }[]; missing_playoffs: number[];
  first_season: number | null; last_season: number | null }
export interface TeamH2H {
  a: string; b: string; regular: H2HRecord; playoffs: H2HRecord; series_a_won: number; first_meeting: string | null;
  series: { season: number; round: string; winner: string; a_wins: number; b_wins: number }[];
  recent: { date: string; season: number; playoffs: boolean; game_ref: string; a_team: string | null; b_team: string | null; a_pts: number | null; b_pts: number | null; a_home: boolean }[];
}
export interface H2HRecord { games: number; a_wins: number; b_wins: number; a_ppg: number | null; b_ppg: number | null }
export interface PlayerH2HSide { games: number; a_wins: number; b_wins: number; a: Record<string, number | null>; b: Record<string, number | null> }
export interface PlayerH2H {
  a: { player_id: string; player: string }; b: { player_id: string; player: string }; regular: PlayerH2HSide; playoffs: PlayerH2HSide; teammate_games: number;
  meetings: { date: string; season: number; playoffs: boolean; game_ref: string; a_team: string | null; b_team: string | null; a_score: number | null; b_score: number | null;
              a: Record<string, number | null>; b: Record<string, number | null> }[];
}
