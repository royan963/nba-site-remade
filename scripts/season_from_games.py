#!/usr/bin/env python3
"""Season totals built from the game-by-game box scores in data/games/.

The main stats dataset (Basketball-Reference CSVs on Kaggle) can lag the
season by a week or more, while the box scores are updated daily. This
module rebuilds one season's player lines, team records and ratings, and the
league environment straight from the box scores.

Exact (the same formulas Basketball-Reference publishes): games, starts,
per-game stats, shooting percentages, true shooting, usage, free-throw and
three-point rates, team W-L, points, possessions, pace, offensive and
defensive ratings, SRS (margin of victory adjusted for schedule), and PER.

Estimated: Win Shares, BPM (and its offensive/defensive split) and VORP need
inputs the box scores don't have (Basketball-Reference's BPM regression uses
position and role estimates). Those are fit on past seasons, where the box
scores and Basketball-Reference's values are both known (see
scripts/prep_season_live.py, which checks them on a held-out season).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
GAMES = DATA / 'games'
TEAM_TOV_PER_GAME = 0.7
STATS = ['mp', 'fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts']


def frame(name):
    d = json.loads((DATA / f'{name}.json').read_text(encoding='utf-8'))
    return pd.DataFrame(d['rows'], columns=d['columns']) if isinstance(d, dict) else pd.DataFrame(d)


def load_box(season: int, through: str | None = None):
    """Regular-season games (no play-in, Cup final or playoffs) and their player rows, complete games only;
    with `through` (a date), only the games played by then: the season as it stood that day."""
    games = pd.read_csv(GAMES / f'games_{season}.csv.gz')
    regular = games['kind'].eq('regular') if 'kind' in games else ~games['playoffs'].astype(bool)
    games = games[regular & games['complete'].astype(bool)].copy()
    if through is not None:
        games = games[games['date'].astype(str).str[:10] <= through]
    pg = pd.read_csv(GAMES / f'player_games_{season}.csv.gz')
    pg = pg[pg['game_ref'].isin(games['game_ref']) & (pg['mp'].fillna(0) > 0)].copy()
    pg['started'] = pg['started'].astype(str).str.lower().isin(['true', '1', '1.0'])
    # a few rows have rebounds without the offensive/defensive split: split them at the player's (else the league's) ratio
    for col in STATS:
        if col not in ('orb', 'drb'):
            pg[col] = pg[col].fillna(0.0)
    miss = pg['orb'].isna() | pg['drb'].isna()
    if miss.any():
        known = pg[~miss]
        lg_share = known['orb'].sum() / max(known['trb'].sum(), 1)
        share = (known.groupby('player_id')['orb'].sum() / known.groupby('player_id')['trb'].sum().replace(0, np.nan)).fillna(lg_share)
        s = pg.loc[miss, 'player_id'].map(share).fillna(lg_share)
        pg.loc[miss, 'orb'] = (pg.loc[miss, 'trb'] * s).round()
        pg.loc[miss, 'drb'] = pg.loc[miss, 'trb'] - pg.loc[miss, 'orb']
    return games, pg


def team_totals(games, pg):
    """One row per team: its box-score totals and its opponents', plus W-L, points and SRS."""
    side = pd.concat([
        games.assign(team=games['home'], opp=games['away'], pts_for=games['home_pts'], pts_against=games['away_pts']),
        games.assign(team=games['away'], opp=games['home'], pts_for=games['away_pts'], pts_against=games['home_pts'])])
    box = pg.groupby(['game_ref', 'team'])[STATS].sum().reset_index()
    side = side.merge(box, on=['game_ref', 'team'], how='left')
    opp_box = box.rename(columns={'team': 'opp', **{c: f'opp_{c}' for c in STATS}})
    side = side.merge(opp_box, on=['game_ref', 'opp'], how='left')
    side['win'] = side['pts_for'] > side['pts_against']
    agg = {c: 'sum' for c in STATS + [f'opp_{c}' for c in STATS] + ['pts_for', 'pts_against', 'win']}
    t = side.groupby('team').agg({**agg, 'game_ref': 'count'}).rename(columns={'game_ref': 'g', 'win': 'w'}).reset_index()
    t['l'] = t['g'] - t['w']
    # Team turnovers (shot-clock and 8-second violations and the like) are in a team's totals but no player's box
    # score. Against Basketball-Reference's team totals for 2013-2024 they come to about 0.6-0.7 a game.
    t['tov'] += TEAM_TOV_PER_GAME * t['g']
    t['opp_tov'] += TEAM_TOV_PER_GAME * t['g']

    def poss(fga, fta, orb, opp_drb, fg, tov):
        return fga + 0.4 * fta - 1.07 * (orb / (orb + opp_drb)) * (fga - fg) + tov
    t['poss'] = 0.5 * (poss(t['fga'], t['fta'], t['orb'], t['opp_drb'], t['fg'], t['tov'])
                       + poss(t['opp_fga'], t['opp_fta'], t['opp_orb'], t['drb'], t['opp_fg'], t['opp_tov']))
    t['pace'] = 48 * t['poss'] / (t['mp'] / 5)
    t['o_rtg'] = 100 * t['pts_for'] / t['poss']
    t['d_rtg'] = 100 * t['pts_against'] / t['poss']
    t['pts_per_game'] = t['pts_for'] / t['g']
    t['mov'] = (t['pts_for'] - t['pts_against']) / t['g']
    t['srs'] = srs(side, t.set_index('team')['mov'])
    t['sos'] = t['srs'] - t['mov']
    return t


def srs(side, mov: pd.Series) -> np.ndarray:
    """Simple Rating System: each team's margin plus the average rating of the opponents it played, solved iteratively."""
    opps = side.groupby('team')['opp'].apply(list)
    r = mov.copy()
    for _ in range(200):
        new = mov + opps.map(lambda os: float(np.mean([r[o] for o in os])))
        new -= new.mean()
        if np.abs(new - r).max() < 1e-9:
            break
        r = new
    return mov.index.map(r).values


def date_after_games(season: int, k: int) -> str:
    """The first date by which the median team had played k regular-season games."""
    games, _ = load_box(season)
    side = pd.concat([games[['date', 'home']].rename(columns={'home': 'team'}), games[['date', 'away']].rename(columns={'away': 'team'})])
    side = side.assign(date=side['date'].astype(str).str[:10]).sort_values('date')
    side['n'] = side.groupby('team').cumcount() + 1
    by_date = side.groupby('date').apply(lambda d: d.groupby('team')['n'].max()).unstack().ffill().fillna(0)
    return str(by_date.index[(by_date.median(axis=1) >= k).to_numpy()][0])


def league(teams):
    s = teams[STATS + ['pts_for', 'g', 'poss']].sum()
    lg = {k: float(s[k]) for k in STATS}
    lg['pts'] = float(s['pts_for'])
    lg['pace'] = float((teams['pace'] * teams['g']).sum() / teams['g'].sum())
    lg['team_games'] = float(teams['g'].sum())
    return lg


def player_lines(pg, teams, lg):
    """Per player and team (stint): totals and the box-score rates. Traded players also get a combined row."""
    t = teams.set_index('team')
    st = pg.groupby(['player_id', 'team']).agg(g=('game_ref', 'nunique'), gs=('started', 'sum'), **{c: (c, 'sum') for c in STATS}).reset_index()
    st['tm_mp'] = st['team'].map(t['mp'])
    for c in ('fga', 'fta', 'tov', 'fg', 'ast', 'orb', 'drb', 'trb', 'stl', 'blk', 'x3pa', 'pts'):
        st[f'tm_{c}'] = st['team'].map(t[c])
    for c in ('orb', 'drb', 'trb', 'fga', 'x3pa', 'pts', 'fg', 'tov', 'fta'):
        st[f'opp_{c}'] = st['team'].map(t[f'opp_{c}'])
    st['tm_poss'], st['tm_pace'], st['tm_g'] = st['team'].map(t['poss']), st['team'].map(t['pace']), st['team'].map(t['g'])
    st['tm_ortg'], st['tm_drtg'], st['tm_srs'] = st['team'].map(t['o_rtg']), st['team'].map(t['d_rtg']), st['team'].map(t['srs'])
    st['tm_w'] = st['team'].map(t['w'])
    st['per'] = per(st, lg)
    return st


def per(st, lg):
    """Hollinger's PER, as Basketball-Reference computes it (unadjusted, pace-adjusted, then scaled to a league average of 15)."""
    factor = (2 / 3) - (0.5 * (lg['ast'] / lg['fg'])) / (2 * (lg['fg'] / lg['ft']))
    vop = lg['pts'] / (lg['fga'] - lg['orb'] + lg['tov'] + 0.44 * lg['fta'])
    drbp = (lg['trb'] - lg['orb']) / lg['trb']
    tm_ast_fg = st['tm_ast'] / st['tm_fg']
    u = (st['x3p'] + (2 / 3) * st['ast'] + (2 - factor * tm_ast_fg) * st['fg']
         + st['ft'] * 0.5 * (1 + (1 - tm_ast_fg) + (2 / 3) * tm_ast_fg)
         - vop * st['tov'] - vop * drbp * (st['fga'] - st['fg']) - vop * 0.44 * (0.44 + 0.56 * drbp) * (st['fta'] - st['ft'])
         + vop * (1 - drbp) * (st['trb'] - st['orb']) + vop * drbp * st['orb'] + vop * st['stl'] + vop * drbp * st['blk']
         - st['pf'] * ((lg['ft'] / lg['pf']) - 0.44 * (lg['fta'] / lg['pf']) * vop)) / st['mp']
    a = u * lg['pace'] / st['tm_pace']
    lg_a = (a * st['mp']).sum() / st['mp'].sum()
    return a * 15 / lg_a


def rates(st):
    """Box-score rates per stint (or combined row): the inputs of the estimated stats and the exact advanced columns."""
    r = pd.DataFrame(index=st.index)
    tsa = st['fga'] + 0.44 * st['fta']
    r['ts_pct'] = st['pts'] / (2 * tsa.replace(0, np.nan))
    r['usg_pct'] = 100 * ((st['fga'] + 0.44 * st['fta'] + st['tov']) * (st['tm_mp'] / 5)) / (
        st['mp'] * (st['tm_fga'] + 0.44 * st['tm_fta'] + st['tm_tov']))
    r['f_tr'] = st['fta'] / st['fga'].replace(0, np.nan)
    r['x3p_ar'] = st['x3pa'] / st['fga'].replace(0, np.nan)
    share = st['mp'] / (st['tm_mp'] / 5)                       # share of the team's minutes at one position
    r['orb_pct'] = 100 * st['orb'] / (share * (st['tm_orb'] + st['opp_drb']))
    r['drb_pct'] = 100 * st['drb'] / (share * (st['tm_drb'] + st['opp_orb']))
    r['ast_pct'] = 100 * st['ast'] / ((share * st['tm_fg']) - st['fg']).replace(0, np.nan)
    r['stl_pct'] = 100 * st['stl'] / (share * st['tm_poss'])
    r['blk_pct'] = 100 * st['blk'] / (share * (st['opp_fga'] - st['opp_x3pa']))
    r['tov_pct'] = 100 * st['tov'] / tsa.add(st['tov']).replace(0, np.nan)
    poss = st['mp'] / 48 * st['tm_pace']                         # possessions while on the floor
    for c in ('pts', 'fga', 'fta', 'x3pa', 'x3p', 'ast', 'tov', 'orb', 'drb', 'stl', 'blk', 'pf'):
        r[f'{c}_100'] = 100 * st[c] / poss.replace(0, np.nan)
    r['mpg'] = st['mp'] / st['g']
    r['min_share'] = share / st['tm_g']                          # 1.0 = every minute of every team game
    r['tm_net'] = st['tm_ortg'] - st['tm_drtg']
    r['tm_ortg_rel'] = st['tm_ortg'] - st['tm_ortg'].mean()
    r['tm_drtg_rel'] = st['tm_drtg'] - st['tm_drtg'].mean()
    r['tm_win_pct'] = st['tm_w'] / st['tm_g']
    return r.replace([np.inf, -np.inf], np.nan)


def season_tables(season: int, through: str | None = None):
    """Everything for one season (or the part of it played by `through`): (teams, stints with rates, league environment dict)."""
    games, pg = load_box(season, through)
    teams = team_totals(games, pg)
    lg = league(teams)
    st = player_lines(pg, teams, lg)
    st = pd.concat([st, rates(st)], axis=1)
    return teams, st, lg
