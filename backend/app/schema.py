"""Table definitions (SQLAlchemy Core). Works on PostgreSQL and SQLite.

Column names match the JSON the dashboard already uses, so API rows can be
dropped straight into the frontend.
"""
from sqlalchemy import (REAL, Boolean, Column, Float, ForeignKey, Index, Integer, MetaData, SmallInteger, String,
                        Table, Text)

metadata = MetaData()


def _f(*names):
    return [Column(n, Float) for n in names]


def _i(*names):
    return [Column(n, Integer) for n in names]


def _player_fk():
    return Column('player_id', String(16), ForeignKey('players.player_id'), nullable=False)


meta = Table('meta', metadata,
             Column('key', String(64), primary_key=True),
             Column('value', Text))

players = Table(
    'players', metadata,
    Column('player_id', String(16), primary_key=True),
    Column('player', String(80), nullable=False),
    Column('name_search', String(80), nullable=False, index=True),  # lowercase, accents stripped
    Column('pos', String(16)),
    Column('hof', Boolean),
    *_i('ht_in_in', 'wt', 'seasons_played', 'first_season', 'last_season',
        'g', 'pts', 'trb', 'ast', 'stl', 'blk', 'fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'all_star'),
    *_f('ppg', 'rpg', 'apg', 'ws', 'vorp'),
)

# One row per player per team stint, plus a combined row ('2TM', '3TM', ...)
# for traded players, flagged with combined = true.
player_seasons = Table(
    'player_seasons', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    _player_fk(),
    Column('season', Integer, nullable=False),
    Column('player', String(80)),
    Column('team', String(4), nullable=False),
    Column('combined', Boolean, nullable=False, default=False),
    Column('pos', String(16)),
    *_i('age', 'g', 'gs'),
    *_f('mp', 'pts', 'trb', 'ast', 'stl', 'blk', 'fg_pct', 'x3p_pct', 'ft_pct', 'x3pa', 'fta'),
    Index('ix_player_seasons_player', 'player_id', 'season'),
    Index('ix_player_seasons_team', 'team', 'season'),
)


def _per_player_season(name, *cols):
    return Table(name, metadata,
                 Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
                 Column('season', Integer, primary_key=True),
                 *cols)


player_advanced = _per_player_season(
    'player_advanced', *_f('per', 'ts_pct', 'usg_pct', 'x3p_ar', 'ws', 'ws_48', 'obpm', 'dbpm', 'bpm', 'vorp'))
player_per100 = _per_player_season(
    'player_per100', *_f('pts', 'trb', 'ast', 'stl', 'blk', 'tov', 'o_rtg', 'd_rtg'))
player_shooting = _per_player_season(
    'player_shooting',
    *_f('avg_dist', 'pct_fga_0_3', 'fg_pct_0_3', 'pct_fga_3_10', 'fg_pct_3_10', 'pct_fga_10_16',
        'fg_pct_10_16', 'pct_fga_16_3p', 'fg_pct_16_3p', 'pct_fga_3p', 'fg_pct_3p', 'pct_assisted_2p',
        'pct_assisted_3p', 'pct_dunks', 'pct_corner_3', 'corner_3_pct'),
    Column('num_dunks', Integer))
player_pbp = _per_player_season(
    'player_pbp',
    *_f('pg_pct', 'sg_pct', 'sf_pct', 'pf_pct', 'c_pct', 'on_court_plus_minus', 'net_plus_minus'),
    *_i('bad_pass_to', 'lost_ball_to', 'shooting_foul_committed', 'off_foul_committed',
        'shooting_foul_drawn', 'off_foul_drawn', 'pts_generated_by_ast', 'and1', 'fga_blocked'))

award_shares = Table(
    'award_shares', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('season', Integer, nullable=False),
    Column('award', String(32), nullable=False),
    Column('player_id', String(16), nullable=False, index=True),  # a few voting rows predate a player record
    Column('share', Float),
    Column('winner', Boolean, nullable=False),
)
eos_teams = Table(
    'eos_teams', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('season', Integer, nullable=False),
    Column('team_type', String(16), nullable=False),
    Column('team_number', String(8)),
    Column('player_id', String(16), nullable=False, index=True),
)
all_stars = Table(
    'all_stars', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('season', Integer, nullable=False),
    Column('player_id', String(16), nullable=False, index=True),
    Column('replaced', Boolean),
)
draft_picks = Table(
    'draft_picks', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('season', Integer, nullable=False),
    Column('player_id', String(16), nullable=False, index=True),
    *_i('overall_pick', 'round'),
    Column('tm', String(8)),
    Column('college', String(80)),
)

# Team-season rows with franchise lineage, location and colors (team_geo.json).
team_seasons = Table(
    'team_seasons', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('season', Integer, nullable=False),
    Column('franchise', String(64), nullable=False, index=True),
    Column('team_name', String(64), nullable=False),
    Column('abbr', String(4), nullable=False),
    Column('city', String(48)),
    *_f('lat', 'lng'),
    Column('current_name', String(64)),
    Column('status', String(16)),
    *_i('w', 'l'),
    *_f('srs', 'o_rtg', 'd_rtg', 'pace', 'pts_per_game'),
    Column('playoffs', Boolean),
    Column('primary_color', String(8)),
    Column('secondary_color', String(8)),
    Column('badge_code', String(4)),
    Index('ix_team_seasons_abbr', 'abbr', 'season'),
)


def _per_season(name, *cols):
    return Table(name, metadata, Column('season', Integer, primary_key=True), *cols)


league_trends = _per_season(
    'league_trends',
    *_f('pace', 'o_rtg', 'd_rtg', 'x3p_ar', 'ts_percent', 'pts_per_game', 'x3pa_per_game',
        'x3p_percent', 'fg_percent', 'ft_per_game', 'orb_per_game', 'ast_per_game'),
    Column('num_teams', Integer))
league_env = _per_season(
    'league_env',
    *_f('pace', 'pts36', 'trb36', 'ast36', 'stl36', 'blk36', 'tov36', 'ts_pct', 'fg_pct', 'x3p_pct',
        'ft_pct', 'x3p_ar'))
league_shooting = _per_season(
    'league_shooting',
    Column('n_players', Integer),
    *_f('avg_pct_fga_0_3', 'avg_fg_pct_0_3', 'avg_pct_fga_3_10', 'avg_fg_pct_3_10',
        'avg_pct_fga_10_16', 'avg_fg_pct_10_16', 'avg_pct_fga_16_3p', 'avg_fg_pct_16_3p',
        'avg_pct_fga_3p', 'avg_fg_pct_3p', 'avg_pct_corner_3', 'avg_corner_3_pct'))

# Similar players: each player's era-relative style fingerprint and top matches.
STYLE_FEATURES = ['pts_idx', 'trb_idx', 'ast_idx', 'stl_idx', 'blk_idx', 'ts_idx', 'usg_percent',
                  'x3p_ar_diff', 'x3p_pos_diff', 'ht_in_in',
                  # how he scores
                  'ft_rate_diff', 'x3p_accuracy', 'assisted_diff', 'rim_diff', 'mid_diff']
player_style = Table(
    'player_style', metadata,
    Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
    *_f(*STYLE_FEATURES))
similar_players = Table(
    'similar_players', metadata,
    Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
    Column('rank', Integer, primary_key=True),
    Column('similar_id', String(16), ForeignKey('players.player_id'), nullable=False),
    Column('score', Integer, nullable=False),
)

# MVP predictor output (scripts/train_mvp.py -> data/mvp_model.json). Past
# seasons are leave-one-season-out predictions; the latest season without
# voting is a true prediction. Model metrics live in meta['mvp_model'].
mvp_candidates = Table(
    'mvp_candidates', metadata,
    Column('season', Integer, primary_key=True),
    Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
    Column('rank', Integer, nullable=False),               # model's rank that season
    Column('predicted_share', Float, nullable=False),
    Column('win_prob', Float, nullable=False),
    Column('actual_share', Float),                         # NULL when voting isn't in the data yet
    Column('actual_rank', Integer),
    Column('winner', Boolean, nullable=False),
    Column('eligible', Boolean, nullable=False),
    Column('needs_exception', Boolean, nullable=False),
    Column('team', String(4)),
    Column('g', Integer),
    Column('win_pct', Float),
)

# Player archetypes (scripts/train_archetypes.py -> data/archetypes.json): each
# qualified player-season's role. Role definitions and the trend over time live
# in meta['archetype_model'].
player_archetypes = Table(
    'player_archetypes', metadata,
    Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
    Column('season', Integer, primary_key=True),
    Column('archetype_id', Integer, nullable=False),
    Column('secondary_id', Integer, nullable=False),
    Column('fit', Integer, nullable=False),               # 0 = torn between two roles, 100 = textbook
    Column('features_used', Integer, nullable=False),     # fewer in older seasons (no blocks/steals/usage/threes)
    Index('ix_player_archetypes_role', 'archetype_id', 'season'),
)

# Career projections (scripts/train_projections.py -> data/projections.json):
# each current player's next seasons (h = 1..3 seasons ahead), with a 60% range
# and the chance he plays that season, plus his most similar comparables.
# Backtest metrics live in meta['projection_model'].
player_projections = Table(
    'player_projections', metadata,
    Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
    Column('h', Integer, primary_key=True),
    Column('season', Integer, nullable=False),
    Column('age', Integer),
    Column('p_active', Float, nullable=False),
    *_f('pts', 'pts_lo', 'pts_hi', 'trb', 'trb_lo', 'trb_hi', 'ast', 'ast_lo', 'ast_hi', 'mp', 'mp_lo', 'mp_hi', 'ts_pct'),
)
projection_comps = Table(
    'projection_comps', metadata,
    Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
    Column('rank', Integer, primary_key=True),
    Column('comp_id', String(16), ForeignKey('players.player_id'), nullable=False),
    Column('comp_season', Integer, nullable=False),
    Column('similarity', Integer, nullable=False),
)

# Style mixes: how much a season (or a whole career, minutes-weighted)
# resembles each archetype. Shares are whole percents; tiny shares are dropped.
player_archetype_mix = Table(
    'player_archetype_mix', metadata,
    Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
    Column('season', Integer, primary_key=True),
    Column('archetype_id', Integer, primary_key=True),
    Column('share', Integer, nullable=False),
)
player_style_mix = Table(
    'player_style_mix', metadata,
    Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
    Column('archetype_id', Integer, primary_key=True),
    Column('share', Integer, nullable=False),
)

# Playoffs and championships (scripts/prep_playoffs.py -> data/playoff_*.json, data/player_*.json).
# Teams are stored by that season's abbreviation AND by franchise, so a franchise's whole
# history (Minneapolis Lakers -> Los Angeles Lakers) can be queried together.
playoff_series = Table(
    'playoff_series', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('season', Integer, nullable=False),
    Column('round_name', String(48), nullable=False),          # as named that year ("Eastern Division Semifinals")
    Column('round_label', String(32)),                          # normalized: Finals / Conference Finals / ...
    Column('rff', Integer),                                     # rounds from the final: 0 = Finals
    Column('team_a', String(4), nullable=False), Column('team_b', String(4), nullable=False),
    Column('franchise_a', String(64)), Column('franchise_b', String(64)),
    Column('wins_a', Integer, nullable=False), Column('wins_b', Integer, nullable=False),
    Column('winner', String(4), nullable=False), Column('winner_franchise', String(64)),
    Column('games', Integer), Column('start', String(10)), Column('end', String(10)),
    Column('complete', Boolean, nullable=False),               # False: a game is missing from the source
    Index('ix_playoff_series_season', 'season', 'rff'),
)
playoff_teams = Table(
    'playoff_teams', metadata,
    Column('season', Integer, primary_key=True), Column('team', String(4), primary_key=True),
    Column('franchise', String(64), index=True),
    *_i('series_won', 'series_lost', 'games_won', 'games_lost'),
    Column('result', String(48), nullable=False), Column('rff_deepest', Integer), Column('champion', Boolean, nullable=False),
)
player_playoffs = Table(
    'player_playoffs', metadata,
    Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
    Column('season', Integer, primary_key=True), Column('team', String(4), primary_key=True),
    Column('franchise', String(64), index=True),
    Column('g', Integer, nullable=False), Column('mp', Float),
    *_i('fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts'),
    # games in which the stat was recorded (older eras lack some), so per-game averages stay honest
    *_i('g_mp', 'g_trb', 'g_ast', 'g_stl', 'g_blk'),
)
player_titles = Table(
    'player_titles', metadata,
    Column('player_id', String(16), ForeignKey('players.player_id'), primary_key=True),
    Column('season', Integer, primary_key=True),
    Column('team', String(4), nullable=False), Column('franchise', String(64), index=True),
)

finals_mvp = Table(
    'finals_mvp', metadata,
    Column('season', Integer, primary_key=True),
    Column('player_id', String(16), ForeignKey('players.player_id'), nullable=False, index=True),
    Column('team', String(4)),
)

# Game-by-game data (scripts/prep_games.py -> data/games/*.csv.gz, one pair of files per season).
# No foreign keys on purpose: 1.5M rows load much faster without them; the loader drops unknown players.
games = Table(
    'games', metadata,
    Column('game_ref', String(12), primary_key=True),             # Basketball-Reference id: date + home team
    Column('season', Integer, nullable=False, index=True),
    Column('date', String(10), nullable=False),
    Column('home', String(4), nullable=False), Column('away', String(4), nullable=False),
    Column('home_franchise', String(64)), Column('away_franchise', String(64)),
    Column('home_pts', Integer), Column('away_pts', Integer), Column('ot', Integer),
    Column('playoffs', Boolean, nullable=False), Column('series', String(48)),
    Column('src', String(10)),                                      # bref | deocheng
    Column('complete', Boolean, nullable=False),                    # player points add up to the final score
    Index('ix_games_franchises', 'home_franchise', 'away_franchise'),
)
player_games = Table(
    # Sized for free hosted databases (~0.5 GB): 2-byte stats, 4-byte minutes, and two plain indexes instead of a
    # three-column primary key. (player, game, team) is unique; the loader checks it per season file.
    # team is part of that key: in the protested Nets-76ers game of Nov 8 1978, whose finish was replayed after a trade,
    # three players appear for both teams.
    'player_games', metadata,
    Column('player_id', String(16), nullable=False), Column('game_ref', String(12), nullable=False),
    Column('team', String(4), nullable=False),
    Column('season', SmallInteger, nullable=False), Column('playoffs', Boolean, nullable=False),
    Column('started', Boolean), Column('mp', REAL),
    *[Column(c, SmallInteger) for c in ('fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts', 'pm')],
    Column('src', String(8)),                                       # bref | dc_log | dc_pbp (rebuilt: no ast, minutes, fouls, ORB/DRB)
    Index('ix_player_games_player', 'player_id', 'season'),
    Index('ix_player_games_game', 'game_ref'),
)
