#!/usr/bin/env python3
"""Turn the raw Basketball-Reference CSVs into the compact JSON files in ../data.

Usage:  python3 scripts/prep_data.py [path/to/csv/folder]
Default CSV folder: data/raw  (unzip nba.zip there).
Requires: pandas, numpy.
"""
import sys, json, math
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from franchise_map import CITY_COORDS, resolve_meta
from team_colors import TEAM_COLORS

ROOT = Path(__file__).resolve().parent.parent
D = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'raw'
OUT = ROOT / 'data'
LEAGUES = ['NBA', 'BAA']          # BAA = 1947-49, the NBA's predecessor
MULTI = {'2TM', '3TM', '4TM', '5TM'}

def csv(name):
    return pd.read_csv(D / name, low_memory=False)

def dump(obj, name):
    # allow_nan=False: NaN isn't valid JSON, so any that slip through fail loudly here
    (OUT / f'{name}.json').write_text(json.dumps(obj, allow_nan=False))
    n = len(obj['rows']) if isinstance(obj, dict) and 'rows' in obj else len(obj)
    print(f'{name}.json: {n} rows')

def clean(obj):
    """NaN -> None, numpy scalars -> python, floats rounded to 3 dp."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if np.isnan(obj) else round(float(obj), 3)
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj

def isnan(v):
    return v is None or (isinstance(v, float) and math.isnan(v))

def rnd(v, d=1):
    return None if isnan(v) else round(float(v), d)

def to_int(v):
    if isnan(v):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None

def dedupe_tot(df):
    """Per-game/totals files: keep the combined 'TOT' row for traded players."""
    has = df.groupby(['player_id', 'season'])['team'].transform(lambda x: (x == 'TOT').any())
    return df[(~has) | (df['team'] == 'TOT')]

def dedupe_multi(df):
    """Shooting/play-by-play files: keep the combined 2TM/3TM/... row."""
    has = df.groupby(['player_id', 'season'])['team'].transform(lambda x: x.isin(MULTI).any())
    return df[(~has) | df['team'].isin(MULTI)]

# ---------------------------------------------------------------- teams
team_sum = csv('Team Summaries.csv')
team_sum = team_sum[team_sum['lg'].isin(LEAGUES) & (team_sum['team'] != 'League Average')]
team_pg = csv('Team Stats Per Game.csv')
team_pg = team_pg[team_pg['lg'].isin(LEAGUES) & (team_pg['team'] != 'League Average')]

# 1. league-wide trends, one row per season
era = []
for season in sorted(team_sum['season'].unique()):
    ts, tp = team_sum[team_sum['season'] == season], team_pg[team_pg['season'] == season]
    era.append({
        'season': int(season), 'pace': ts['pace'].mean(), 'o_rtg': ts['o_rtg'].mean(),
        'd_rtg': ts['d_rtg'].mean(), 'x3p_ar': ts['x3p_ar'].mean(), 'ts_percent': ts['ts_percent'].mean(),
        'pts_per_game': tp['pts_per_game'].mean(), 'x3pa_per_game': tp['x3pa_per_game'].mean(),
        'x3p_percent': tp['x3p_percent'].mean(), 'fg_percent': tp['fg_percent'].mean(),
        'ft_per_game': tp['ft_per_game'].mean(), 'orb_per_game': tp['orb_per_game'].mean(),
        'ast_per_game': tp['ast_per_game'].mean(), 'num_teams': ts['team'].nunique(),
    })
dump(clean(era), 'era_trends')

# 3. team geo timeline (franchise lineage, city, coordinates, colors)
merged = team_sum.merge(team_pg[['season', 'team', 'pts_per_game']], on=['season', 'team'], how='left')
geo_cols = ['season', 'franchise', 'team_name', 'city', 'lat', 'lng', 'current_name', 'status', 'w', 'l', 'srs',
            'o_rtg', 'd_rtg', 'pace', 'pts_per_game', 'playoffs', 'abbr',
            'primary_color', 'secondary_color', 'badge_code']
geo_rows = []
for rec in merged.itertuples(index=False):
    d = rec._asdict()
    meta = resolve_meta(d['team'], d['season'])
    lat, lng = CITY_COORDS[meta['city']]
    colors = TEAM_COLORS[meta['franchise']]
    geo_rows.append([
        int(d['season']), meta['franchise'], d['team'], meta['city'], lat, lng, meta['current'], meta['status'],
        to_int(d['w']), to_int(d['l']), rnd(d['srs']), rnd(d['o_rtg']), rnd(d['d_rtg']), rnd(d['pace']),
        rnd(d['pts_per_game']), False if isnan(d['playoffs']) else bool(d['playoffs']), d['abbreviation'],
        colors['primary'], colors['secondary'], colors['code'],
    ])
dump({'columns': geo_cols, 'rows': geo_rows}, 'team_geo')

# ---------------------------------------------------------------- players
pt = csv('Player Totals.csv')
pt = dedupe_multi(pt[pt['lg'].isin(LEAGUES)])   # one row per season: a traded player's combined 2TM/3TM row, not combined + stints
info = csv('Player Career Info.csv')
stat_cols = ['g', 'gs', 'mp', 'fg', 'fga', 'x3p', 'x3pa', 'x2p', 'x2pa', 'ft', 'fta',
             'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts']
# Group by id only: a few players appear under two spellings (e.g. "Vit Krejci" /
# "Vít Krejčí"), which would otherwise split one career into two rows.
career = pt.groupby('player_id').agg({c: 'sum' for c in stat_cols}).reset_index()
latest_name = pt.sort_values('season').groupby('player_id')['player'].last()
career.insert(1, 'player', latest_name.reindex(career['player_id']).values)
career['seasons_played'] = pt.groupby('player_id')['season'].nunique().reindex(career['player_id']).values
career['first_season'] = pt.groupby('player_id')['season'].min().reindex(career['player_id']).values
career['last_season'] = pt.groupby('player_id')['season'].max().reindex(career['player_id']).values
career['ppg'] = career['pts'] / career['g'].replace(0, np.nan)
career['rpg'] = career['trb'] / career['g'].replace(0, np.nan)
career['apg'] = career['ast'] / career['g'].replace(0, np.nan)
career = career.merge(info[['player_id', 'pos', 'hof', 'ht_in_in', 'wt']], on='player_id', how='left')

# Advanced stats (PER, TS%, WS, BPM, VORP ...). One row per player-season.
adv = dedupe_multi(csv('Advanced.csv'))
adv = adv[adv['lg'].isin(LEAGUES)]
all_star = csv('All-Star Selections.csv')
all_star = all_star[all_star['lg'] == 'NBA']
career = career.merge(adv.groupby('player_id')[['ws', 'vorp']].sum(min_count=1).reset_index(), on='player_id', how='left')
career = career.merge(all_star.groupby('player_id').size().rename('all_star').reset_index(), on='player_id', how='left')
career['all_star'] = career['all_star'].fillna(0)

career_cols = ['player_id', 'player', 'pos', 'hof', 'ht_in_in', 'wt', 'seasons_played', 'first_season',
               'last_season', 'g', 'pts', 'trb', 'ast', 'stl', 'blk', 'fg', 'fga', 'x3p', 'x3pa',
               'ft', 'fta', 'ppg', 'rpg', 'apg', 'ws', 'vorp', 'all_star']
career_rows = []
for row in career.itertuples(index=False):
    d = row._asdict()
    career_rows.append([
        d['player_id'], d['player'], None if isnan(d['pos']) else d['pos'], False if isnan(d['hof']) else bool(d['hof']),
        to_int(d['ht_in_in']), to_int(d['wt']), to_int(d['seasons_played']), to_int(d['first_season']),
        to_int(d['last_season']), to_int(d['g']), to_int(d['pts']), to_int(d['trb']), to_int(d['ast']),
        to_int(d['stl']), to_int(d['blk']), to_int(d['fg']), to_int(d['fga']), to_int(d['x3p']),
        to_int(d['x3pa']), to_int(d['ft']), to_int(d['fta']), rnd(d['ppg']), rnd(d['rpg']), rnd(d['apg']),
        rnd(d['ws']), rnd(d['vorp']), to_int(d['all_star']),
    ])
dump({'columns': career_cols, 'rows': career_rows}, 'player_career')

# player seasons (per-game). Kept rows include the 2TM/3TM combined row AND the
# per-team stints, because rosters need the individual team rows.
ppg = csv('Player Per Game.csv')
ppg = dedupe_tot(ppg[ppg['lg'].isin(LEAGUES)])
rows = []
for r in ppg.itertuples(index=False):
    rows.append([
        int(r.season), r.player_id, r.player, to_int(r.age), r.team, None if isnan(r.pos) else r.pos, to_int(r.g), to_int(r.gs),
        rnd(r.mp_per_game), rnd(r.pts_per_game), rnd(r.trb_per_game), rnd(r.ast_per_game),
        rnd(r.stl_per_game), rnd(r.blk_per_game),
        rnd(r.fg_percent, 4), rnd(r.x3p_percent, 4), rnd(r.ft_percent, 4),   # 4 dp so the UI can show 2 dp %
        rnd(r.x3pa_per_game), rnd(r.fta_per_game),   # attempts: minimums for shooting rankings
    ])
dump({'columns': ['season', 'player_id', 'player', 'age', 'team', 'pos', 'g', 'gs', 'mp', 'pts', 'trb', 'ast',
                  'stl', 'blk', 'fg_pct', 'x3p_pct', 'ft_pct', 'x3pa', 'fta'], 'rows': rows}, 'player_seasons')

# ---------------------------------------------------------------- shooting zones (1997+)
sh = dedupe_multi(csv('Player Shooting.csv'))
zone_map = [
    ('avg_dist', 'avg_dist_fga', 1),
    ('pct_fga_0_3', 'percent_fga_from_x0_3_range', 3), ('fg_pct_0_3', 'fg_percent_from_x0_3_range', 3),
    ('pct_fga_3_10', 'percent_fga_from_x3_10_range', 3), ('fg_pct_3_10', 'fg_percent_from_x3_10_range', 3),
    ('pct_fga_10_16', 'percent_fga_from_x10_16_range', 3), ('fg_pct_10_16', 'fg_percent_from_x10_16_range', 3),
    ('pct_fga_16_3p', 'percent_fga_from_x16_3p_range', 3), ('fg_pct_16_3p', 'fg_percent_from_x16_3p_range', 3),
    ('pct_fga_3p', 'percent_fga_from_x3p_range', 3), ('fg_pct_3p', 'fg_percent_from_x3p_range', 3),
    ('pct_assisted_2p', 'percent_assisted_x2p_fg', 3), ('pct_assisted_3p', 'percent_assisted_x3p_fg', 3),
    ('pct_dunks', 'percent_dunks_of_fga', 3), ('num_dunks', 'num_of_dunks', 'int'),
    ('pct_corner_3', 'percent_corner_3s_of_3pa', 3), ('corner_3_pct', 'corner_3_point_percent', 3),
]
def pack(df, spec):
    out = []
    for _, r in df.iterrows():
        row = [int(r['season']), r['player_id']]
        for _, src, dp in spec:
            row.append(to_int(r[src]) if dp == 'int' else rnd(r[src], dp))
        out.append(row)
    return out
dump({'columns': ['season', 'player_id'] + [c for c, _, _ in zone_map], 'rows': pack(sh, zone_map)}, 'player_shooting')

# league-average shooting by season (games-played x shot-share weighted, players with 20+ GP)
lg = sh[(sh['g'] >= 20)]
fga_fg = [('percent_fga_from_x0_3_range', 'fg_percent_from_x0_3_range'),
          ('percent_fga_from_x3_10_range', 'fg_percent_from_x3_10_range'),
          ('percent_fga_from_x10_16_range', 'fg_percent_from_x10_16_range'),
          ('percent_fga_from_x16_3p_range', 'fg_percent_from_x16_3p_range'),
          ('percent_fga_from_x3p_range', 'fg_percent_from_x3p_range')]
zones = ['0_3', '3_10', '10_16', '16_3p', '3p']
lg_cols = ['season', 'n_players'] + [f'avg_{k}_{z}' for z in zones for k in ('pct_fga', 'fg_pct')] + ['avg_pct_corner_3', 'avg_corner_3_pct']
lg_rows = []
for season, g in lg.groupby('season'):
    row = [int(season), int(len(g))]
    for fga, fgp in fga_fg:
        w = g['g'] * g[fga].fillna(0)
        ok = g[fgp].notna() & (w > 0)
        wavg = (g.loc[ok, fgp] * w[ok]).sum() / w[ok].sum() if ok.sum() else None
        row += [rnd(g[fga].mean(), 4), rnd(wavg, 4)]
    cw = g['g'] * g['percent_fga_from_x3p_range'].fillna(0) * g['percent_corner_3s_of_3pa'].fillna(0)
    ok = g['corner_3_point_percent'].notna() & (cw > 0)
    cavg = (g.loc[ok, 'corner_3_point_percent'] * cw[ok]).sum() / cw[ok].sum() if ok.sum() else None
    row += [rnd(g['percent_corner_3s_of_3pa'].mean(), 4), rnd(cavg, 4)]
    lg_rows.append(row)
dump({'columns': lg_cols, 'rows': lg_rows}, 'league_avg_shooting')

# ---------------------------------------------------------------- play by play (1997+)
pbp = dedupe_multi(csv('Player Play By Play.csv'))
pbp_map = [('pg_pct', 'pg_percent', 3), ('sg_pct', 'sg_percent', 3), ('sf_pct', 'sf_percent', 3),
           ('pf_pct', 'pf_percent', 3), ('c_pct', 'c_percent', 3),
           ('on_court_plus_minus', 'on_court_plus_minus_per_100_poss', 1),
           ('net_plus_minus', 'net_plus_minus_per_100_poss', 1),
           ('bad_pass_to', 'bad_pass_turnover', 'int'), ('lost_ball_to', 'lost_ball_turnover', 'int'),
           ('shooting_foul_committed', 'shooting_foul_committed', 'int'),
           ('off_foul_committed', 'offensive_foul_committed', 'int'),
           ('shooting_foul_drawn', 'shooting_foul_drawn', 'int'), ('off_foul_drawn', 'offensive_foul_drawn', 'int'),
           ('pts_generated_by_ast', 'points_generated_by_assists', 'int'), ('and1', 'and1', 'int'),
           ('fga_blocked', 'fga_blocked', 'int')]
dump({'columns': ['season', 'player_id'] + [c for c, _, _ in pbp_map], 'rows': pack(pbp, pbp_map)}, 'player_pbp')

# ---------------------------------------------------------------- awards
aw = csv('Player Award Shares.csv')
aw = aw[aw['player_id'].notna()]
dump({'columns': ['season', 'award', 'player_id', 'share', 'winner'],
      'rows': [[int(r.season), r.award, r.player_id, rnd(r.share, 3), bool(r.winner)] for r in aw.itertuples(index=False)]},
     'player_award_shares')
eos = csv('End of Season Teams.csv')
eos = eos[eos['lg'].isin(LEAGUES)]
dump({'columns': ['season', 'team_type', 'team_number', 'player_id'],
      'rows': [[int(r.season), r.type, r.number_tm, r.player_id] for r in eos.itertuples(index=False)]},
     'player_eos_teams')

# ---------------------------------------------------------------- advanced stats
adv_map = [('per', 'per', 1), ('ts_pct', 'ts_percent', 3), ('usg_pct', 'usg_percent', 1), ('f_tr', 'f_tr', 3), ('x3p_ar', 'x3p_ar', 3),
           ('ws', 'ws', 1), ('ws_48', 'ws_48', 3), ('obpm', 'obpm', 1), ('dbpm', 'dbpm', 1),
           ('bpm', 'bpm', 1), ('vorp', 'vorp', 1)]
dump({'columns': ['season', 'player_id'] + [c for c, _, _ in adv_map], 'rows': pack(adv, adv_map)}, 'player_advanced')

# ---------------------------------------------------------------- per 100 possessions (1974+)
p100 = dedupe_multi(csv('Per 100 Poss.csv'))
p100 = p100[p100['lg'].isin(LEAGUES) & p100['pts_per_100_poss'].notna()]
p100_map = [(k, f'{k}_per_100_poss', 1) for k in ('pts', 'trb', 'ast', 'stl', 'blk', 'tov')]
p100_map += [('o_rtg', 'o_rtg', 0), ('d_rtg', 'd_rtg', 0)]
dump({'columns': ['season', 'player_id'] + [c for c, _, _ in p100_map], 'rows': pack(p100, p100_map)}, 'player_per100')

# ---------------------------------------------------------------- All-Star selections + draft
dump({'columns': ['season', 'player_id', 'replaced'],
      'rows': [[int(r.season), r.player_id, bool(r.replaced)] for r in all_star.itertuples(index=False)]}, 'all_star')
dr = csv('Draft Pick History.csv')
dr = dr[dr['lg'].isin(LEAGUES) & dr['player_id'].isin(career['player_id'])]   # players who reached the NBA
dump({'columns': ['season', 'player_id', 'overall_pick', 'round', 'tm', 'college'],
      'rows': [[int(r.season), r.player_id, to_int(r.overall_pick), to_int(r.round), r.tm,
                None if isnan(r.college) else r.college] for r in dr.itertuples(index=False)]}, 'draft')

# ---------------------------------------------------------------- league environment (era adjustment)
# League-wide rates per season, used to express a player's stats relative to
# the league average (index, 100 = average). Minutes are estimated as
# 240 per team-game because team minutes weren't recorded in early seasons.
tt = csv('Team Totals.csv')
tt = tt[tt['lg'].isin(LEAGUES) & (tt['team'] != 'League Average')]
env_cols = ['season', 'pace', 'pts36', 'trb36', 'ast36', 'stl36', 'blk36', 'tov36',
            'ts_pct', 'fg_pct', 'x3p_pct', 'ft_pct', 'x3p_ar', 'ft_rate']
pace_by_season = {e['season']: e['pace'] for e in era}
env_rows = []
for season, g in tt.groupby('season'):
    s = g[['g', 'pts', 'trb', 'ast', 'stl', 'blk', 'tov', 'fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta']].sum()
    mins = 240.0 * s['g']
    rate = lambda k: None if s[k] <= 0 else s[k] / mins * 36
    ts = s['pts'] / (2 * (s['fga'] + 0.44 * s['fta'])) if s['fga'] > 0 else None
    env_rows.append([int(season), rnd(pace_by_season.get(int(season)), 1),
                     *[rnd(rate(k), 3) for k in ('pts', 'trb', 'ast', 'stl', 'blk', 'tov')],
                     rnd(ts, 4), rnd(s['fg'] / s['fga'], 4) if s['fga'] else None,
                     rnd(s['x3p'] / s['x3pa'], 4) if s['x3pa'] else None,
                     rnd(s['ft'] / s['fta'], 4) if s['fta'] else None,
                     rnd(s['x3pa'] / s['fga'], 4) if s['x3pa'] else None,
                     rnd(s['fta'] / s['fga'], 4) if s['fga'] else None])
dump({'columns': env_cols, 'rows': env_rows}, 'league_env')
env = pd.DataFrame(env_rows, columns=env_cols).set_index('season')

# Similar players are built by scripts/train_similarity.py (after train_archetypes.py),
# because they use each player's style mix.
