#!/usr/bin/env python3
"""Rebuild the season in progress from the daily box scores.

The main stats dataset can lag the season by a week or more; the box scores
in data/games/ (from the eoinamoore dataset) are updated daily. When the box
scores are ahead, this replaces the newest season's rows in
data/player_seasons.json, data/player_advanced.json, data/team_geo.json and
data/league_env.json with ones built from the box scores
(scripts/season_from_games.py), and records what it did in
data/live_season.json. Once the main dataset has caught up, it leaves its
official numbers alone.

Win Shares, BPM and VORP can't be computed exactly from box scores. They come
from ridge regressions fit on 2012-2023 (single-team player-seasons, where
both the box scores and Basketball-Reference's values are known) and checked
on 2023-24, stored in scripts/live_stat_model.json. Refit with --calibrate.

Usage:  python3 scripts/prep_season_live.py               # rebuild the newest season if the box scores are ahead
        python3 scripts/prep_season_live.py --calibrate   # refit the estimates (takes a few minutes)
        python3 scripts/prep_season_live.py --force       # rebuild even if the main dataset has caught up
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import season_from_games as S  # noqa: E402

DATA = S.DATA
MODEL = Path(__file__).resolve().parent / 'live_stat_model.json'
MULTI = {'2TM', '3TM', '4TM', '5TM'}
LEAGUES = ['NBA', 'BAA']                         # as in prep_data.py: career totals leave out the ABA
TRAIN, TEST = range(2012, 2024), 2024            # box scores from Basketball-Reference, complete minutes and starters
FEATURES = ['pts_100', 'fga_100', 'fta_100', 'x3pa_100', 'x3p_100', 'ast_100', 'tov_100', 'orb_100', 'drb_100', 'stl_100',
            'blk_100', 'pf_100', 'ts_pct', 'usg_pct', 'orb_pct', 'drb_pct', 'ast_pct', 'stl_pct', 'blk_pct', 'tov_pct', 'mpg',
            'min_share', 'tm_net', 'tm_srs', 'tm_ortg_rel', 'tm_drtg_rel', 'per', 'usg_ts', 'ast_trb']
TARGETS = ['bpm', 'obpm', 'ws_48']
VORP_REPLACEMENT = -2.0


def features(r: pd.DataFrame) -> pd.DataFrame:
    r = r.copy()
    r['usg_ts'] = r['usg_pct'] * r['ts_pct']
    r['ast_trb'] = np.sqrt(r['ast_pct'].clip(lower=0) * (r['orb_pct'] + r['drb_pct']).clip(lower=0))
    return r


# ---- calibration ---------------------------------------------------------------------------------------
def calibrate():
    from sklearn.linear_model import Ridge
    ps, ad = S.frame('player_seasons'), S.frame('player_advanced')
    rows = []
    for season in [*TRAIN, TEST]:
        _, st, _ = S.season_tables(season)
        traded = set(ps.loc[(ps['season'] == season) & ps['team'].isin(MULTI), 'player_id'])
        x = st[~st['player_id'].isin(traded)].merge(ad[ad['season'] == season], on='player_id', suffixes=('', '_br'))
        rows.append(x.assign(season=season))
        print(f'{season}: {len(x)} player-seasons', flush=True)
    d = features(pd.concat(rows, ignore_index=True))
    d = d[d['mp'] >= 50].dropna(subset=FEATURES + TARGETS)
    tr, te = d[d['season'].isin(TRAIN)], d[d['season'] == TEST]
    out = {'trained_on': f'{min(TRAIN)}-{max(TRAIN)}', 'tested_on': TEST, 'features': FEATURES, 'models': {}}
    for tgt in TARGETS:
        m = Ridge(alpha=1.0).fit(tr[FEATURES], tr[tgt], sample_weight=tr['mp'])
        p = m.predict(te[FEATURES])
        big = (te['mp'] >= 500).to_numpy()
        out['models'][tgt] = {
            'intercept': float(m.intercept_), 'coef': [float(c) for c in m.coef_],
            'test_mae': round(float(np.abs(p - te[tgt]).mean()), 4),
            'test_mae_500_min': round(float(np.abs(p - te[tgt])[big].mean()), 4),
            'test_corr_500_min': round(float(np.corrcoef(p[big], te[tgt][big])[0, 1]), 4)}
        print(f"{tgt}: held-out {TEST} miss {out['models'][tgt]['test_mae_500_min']} for 500+ minutes "
              f"(correlation {out['models'][tgt]['test_corr_500_min']})")
    MODEL.write_text(json.dumps(out, indent=1) + '\n')
    print(f'wrote {MODEL.relative_to(DATA.parent)}')


def estimate(r: pd.DataFrame, model: dict) -> pd.DataFrame:
    X = features(r)[model['features']].fillna(0.0).to_numpy(float)
    out = pd.DataFrame(index=r.index)
    for tgt, m in model['models'].items():
        out[tgt] = X @ np.array(m['coef']) + m['intercept']
    out['dbpm'] = out['bpm'] - out['obpm']
    return out


# ---- the season in progress -----------------------------------------------------------------------------
def load(name):
    return json.loads((DATA / f'{name}.json').read_text(encoding='utf-8'))


def save(name, d):
    (DATA / f'{name}.json').write_text(json.dumps(d, allow_nan=False), encoding='utf-8')


def clean(v, digits):
    return None if v is None or pd.isna(v) or np.isinf(v) else round(float(v), digits)


def identities(season, ids, strict=True):
    """Name, age and position for each player id: this season's official row, a provisional rookie row, or last season's (one year older)."""
    ps = pd.DataFrame(load('player_seasons')['rows'], columns=load('player_seasons')['columns'])
    out = {}
    for _, r in ps[ps['season'] == season - 1].iterrows():
        out[r['player_id']] = {'player': r['player'], 'age': None if pd.isna(r['age']) else int(r['age']) + 1, 'pos': r['pos']}
    stubs = load('new_players') if (DATA / 'new_players.json').exists() else {'seasons': []}
    for r in stubs['seasons']:
        if r['season'] == season:
            out[r['player_id']] = {'player': r['player'], 'age': r['age'], 'pos': r['pos']}
    for _, r in ps[ps['season'] == season].iterrows():
        out[r['player_id']] = {'player': r['player'], 'age': None if pd.isna(r['age']) else int(r['age']), 'pos': r['pos']}
    career = load('player_career')
    for row in career['rows']:
        p = dict(zip(career['columns'], row))
        out.setdefault(p['player_id'], {'player': p['player'], 'age': None, 'pos': p.get('pos')})
    missing = sorted(set(ids) - set(out))
    if missing and strict:
        raise SystemExit(f'no name for player ids {missing[:10]}')
    for pid in missing:                                  # only when not strict (calibration snapshots): the id stands in
        out[pid] = {'player': pid, 'age': None, 'pos': None}
    return out


def combined_rows(st):
    """Traded players: one combined row ('2TM', '3TM', ...) from the summed stints, as Basketball-Reference lists them."""
    n = st.groupby('player_id')['team'].transform('count')
    multi = st[n > 1]
    if multi.empty:
        return st.iloc[0:0]
    sums = multi.groupby('player_id')[['g', 'gs'] + S.STATS].sum()
    w = multi['mp']
    wavg = lambda col: (multi[col] * w).groupby(multi['player_id']).sum() / w.groupby(multi['player_id']).sum()
    comb = sums.reset_index()
    comb['team'] = comb['player_id'].map(multi.groupby('player_id')['team'].count()).map(lambda k: f'{k}TM')
    for col in ('per', 'usg_pct', 'bpm', 'obpm', 'dbpm'):             # rate stats: minutes-weighted across stints
        comb[col] = comb['player_id'].map(wavg(col))
    for col in ('ws', 'vorp'):                                          # cumulative: summed
        comb[col] = comb['player_id'].map(multi.groupby('player_id')[col].sum())
    return comb


def build(season, model, through=None):
    teams, st, lg = S.season_tables(season, through)
    est = estimate(st, model)
    st = pd.concat([st, est], axis=1)
    st['ws'] = st['ws_48'] * st['mp'] / 48
    # VORP: points per 100 possessions over a replacement player, times the share of team minutes, scaled to 82 games
    st['vorp'] = (st['bpm'] - VORP_REPLACEMENT) * (st['mp'] / (st['tm_mp'] / 5)) * (st['tm_g'] / 82)
    comb = combined_rows(st)
    allrows = pd.concat([st, comb], ignore_index=True)
    return teams, st, comb, allrows, lg


def season_rows(allrows, ident, season):
    rows = []
    order = allrows.assign(_multi=allrows['team'].isin(MULTI)).sort_values(['player_id', '_multi'], ascending=[True, False])
    for _, r in order.iterrows():
        g = int(r['g'])
        pg = lambda c: clean(r[c] / g, 1)
        pct = lambda m, a: clean(r[m] / r[a], 3) if r[a] else None
        who = ident[r['player_id']]
        rows.append([season, r['player_id'], who['player'], who['age'], r['team'], who['pos'], g, int(r['gs']), pg('mp'),
                     pg('pts'), pg('trb'), pg('ast'), pg('stl'), pg('blk'), pct('fg', 'fga'), pct('x3p', 'x3pa'), pct('ft', 'fta'),
                     pg('x3pa'), pg('fta')])
    return rows


def advanced_rows(st, comb, season):
    """One row per player: his only stint, or his combined row if traded."""
    n = st.groupby('player_id')['team'].transform('count')
    one = st[n == 1]
    rows = []
    for src in (one, comb):
        for _, r in src.iterrows():
            tsa = r['fga'] + 0.44 * r['fta']
            rows.append([season, r['player_id'], clean(r['per'], 1), clean(r['pts'] / (2 * tsa), 3) if tsa else None, clean(r['usg_pct'], 1),
                         clean(r['fta'] / r['fga'], 3) if r['fga'] else None, clean(r['x3pa'] / r['fga'], 3) if r['fga'] else None,
                         clean(r['ws'], 1), clean(r['ws'] / r['mp'] * 48, 3) if r['mp'] else None,
                         clean(r['obpm'], 1), clean(r['dbpm'], 1), clean(r['bpm'], 1), clean(r['vorp'], 1)])
    return rows


CAREER_SUMS = ['g', 'pts', 'trb', 'ast', 'stl', 'blk', 'fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta']


def update_career(season, st):
    """Career totals: the main dataset's totals for every other season (data/raw, one row per player-season) plus this
    season from the box scores. Rebuilt from scratch each time, so running twice gives the same result."""
    raw = DATA / 'raw'
    if not (raw / 'Player Totals.csv').exists() or not (raw / 'Advanced.csv').exists():
        print('data/raw has no Player Totals.csv / Advanced.csv: career totals left as they are')
        return 0

    def one_row_per_season(df):
        has = df.groupby(['player_id', 'season'])['team'].transform(lambda x: x.isin(MULTI).any())
        return df[(~has) | df['team'].isin(MULTI)]
    pt = pd.read_csv(raw / 'Player Totals.csv')
    pt = one_row_per_season(pt[pt['lg'].isin(LEAGUES) & (pt['season'] != season)])
    adv = pd.read_csv(raw / 'Advanced.csv')
    adv = one_row_per_season(adv[adv['lg'].isin(LEAGUES)] if 'lg' in adv else adv)
    adv = adv[adv['season'] != season]
    box = st.groupby('player_id').agg({**{c: 'sum' for c in CAREER_SUMS if c != 'g'}, 'g': 'sum', 'ws': 'sum', 'vorp': 'sum'})
    box['g'] = st.groupby('player_id')['g'].sum()
    before = pt.groupby('player_id')[CAREER_SUMS].sum()
    seasons_before = pt.groupby('player_id')['season'].agg(['min', 'max', 'nunique'])
    ws_before = adv.groupby('player_id')[['ws', 'vorp']].sum(min_count=1)
    cr = load('player_career')
    c = cr['columns']
    changed = 0
    for r in cr['rows']:
        pid = r[c.index('player_id')]
        if pid not in box.index and pid not in before.index:
            continue
        tot = (before.loc[pid] if pid in before.index else pd.Series(0, index=CAREER_SUMS)).copy()
        played_now = pid in box.index
        if played_now:
            tot = tot.add(box.loc[pid, CAREER_SUMS], fill_value=0)
        for k in CAREER_SUMS:
            r[c.index(k)] = int(round(tot[k]))
        g = r[c.index('g')]
        for k, src in (('ppg', 'pts'), ('rpg', 'trb'), ('apg', 'ast')):
            r[c.index(k)] = round(r[c.index(src)] / g, 1) if g else None
        for k in ('ws', 'vorp'):
            prev = ws_before.loc[pid, k] if pid in ws_before.index else np.nan
            val = (0.0 if pd.isna(prev) else float(prev)) + (float(box.loc[pid, k]) if played_now else 0.0)
            r[c.index(k)] = None if pd.isna(prev) and not played_now else round(val, 1)
        sb = seasons_before.loc[pid] if pid in seasons_before.index else None
        first = int(sb['min']) if sb is not None else season
        r[c.index('first_season')] = min(first, season) if played_now else first
        r[c.index('last_season')] = season if played_now else int(sb['max'])
        r[c.index('seasons_played')] = (int(sb['nunique']) if sb is not None else 0) + (1 if played_now else 0)
        changed += 1
    save('player_career', cr)
    return changed


def fingerprint(tg, season):
    """Identifies the team rows this script wrote, so a second run knows they aren't the main dataset's."""
    rows = sorted(json.dumps(r) for r in tg['rows'] if r[0] == season)
    return hashlib.sha1('|'.join(rows).encode()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--calibrate', action='store_true', help='refit the Win Shares and BPM estimates')
    ap.add_argument('--force', action='store_true', help='rebuild even if the main dataset has caught up')
    args = ap.parse_args()
    if args.calibrate or not MODEL.exists():
        calibrate()
    model = json.loads(MODEL.read_text())

    season = max(int(f.name.split('_')[1].split('.')[0]) for f in S.GAMES.glob('games_*.csv.gz'))
    tg = load('team_geo')
    geo = pd.DataFrame(tg['rows'], columns=tg['columns'])
    official_games = float((geo.loc[geo['season'] == season, 'w'] + geo.loc[geo['season'] == season, 'l']).sum()) / 2
    prev = json.loads((DATA / 'live_season.json').read_text()) if (DATA / 'live_season.json').exists() else {}
    if prev.get('source') == 'box_scores' and prev.get('season') == season and prev.get('fingerprint') == fingerprint(tg, season):
        official_games = prev['official_games']          # the rows on disk are this script's own, from an earlier run
    teams, st, comb, allrows, lg = build(season, model)
    box_games = float(teams['g'].sum()) / 2
    if box_games <= official_games and not args.force:
        print(f'{season}: the main dataset is up to date ({official_games:.0f} games, box scores {box_games:.0f}); keeping its numbers')
        (DATA / 'live_season.json').write_text(json.dumps({'season': season, 'source': 'official', 'games': official_games}) + '\n')
        return
    games = pd.read_csv(S.GAMES / f'games_{season}.csv.gz')
    through = str(games.loc[games['game_ref'].isin(S.load_box(season)[0]['game_ref']), 'date'].max())
    print(f'{season}: box scores have {box_games:.0f} games through {through}; the main dataset {official_games:.0f}. Rebuilding the season from the box scores.')

    ident = identities(season, set(allrows['player_id']))
    ps = load('player_seasons')
    ps['rows'] = [r for r in ps['rows'] if r[0] != season] + season_rows(allrows, ident, season)
    save('player_seasons', ps)

    ad = load('player_advanced')
    assert ad['columns'] == ['season', 'player_id', 'per', 'ts_pct', 'usg_pct', 'f_tr', 'x3p_ar', 'ws', 'ws_48', 'obpm', 'dbpm', 'bpm', 'vorp']
    ad['rows'] = [r for r in ad['rows'] if r[0] != season] + advanced_rows(st, comb, season)
    save('player_advanced', ad)
    print(f'career totals rebuilt for {update_career(season, st)} players')

    # team records and ratings; franchise details from this season's row, else last season's
    t = teams.set_index('team')
    c = tg['columns']
    have = {r[c.index('abbr')] for r in tg['rows'] if r[0] == season}
    new_rows = [list(r) for r in tg['rows'] if r[0] == season - 1 and r[c.index('abbr')] in set(t.index) - have]
    for r in new_rows:
        r[0] = season
    tg['rows'] += new_rows
    for r in tg['rows']:
        if r[0] != season or r[c.index('abbr')] not in t.index:
            continue
        x = t.loc[r[c.index('abbr')]]
        r[c.index('w')], r[c.index('l')] = float(x['w']), float(x['l'])
        for col in ('srs', 'o_rtg', 'd_rtg', 'pace', 'pts_per_game'):
            r[c.index(col)] = clean(x[col], 1)
    save('team_geo', tg)

    # league environment (per-36 rates use 240 minutes per team-game, like prep_data.py)
    env = load('league_env')
    mins = 240.0 * lg['team_games']
    rate = lambda k: round(lg[k] / mins * 36, 3)
    row = [season, round(lg['pace'], 1), rate('pts'), rate('trb'), rate('ast'), rate('stl'), rate('blk'), rate('tov'),
           round(lg['pts'] / (2 * (lg['fga'] + 0.44 * lg['fta'])), 4), round(lg['fg'] / lg['fga'], 4), round(lg['x3p'] / lg['x3pa'], 4),
           round(lg['ft'] / lg['fta'], 4), round(lg['x3pa'] / lg['fga'], 4), round(lg['fta'] / lg['fga'], 4)]
    env['rows'] = [r for r in env['rows'] if r[0] != season] + [row]
    save('league_env', env)

    info = {'season': season, 'source': 'box_scores', 'through': through, 'games': box_games, 'official_games': official_games,
            'players': int(allrows['player_id'].nunique()), 'teams': int(len(teams)),
            'estimated': ['ws', 'ws_48', 'bpm', 'obpm', 'dbpm', 'vorp'],
            'estimate_accuracy': {k: {'mae_500_min': v['test_mae_500_min'], 'corr_500_min': v['test_corr_500_min']} for k, v in model['models'].items()},
            'estimate_tested_on': model['tested_on'], 'fingerprint': fingerprint(tg, season)}
    (DATA / 'live_season.json').write_text(json.dumps(info, indent=1) + '\n')
    print(f"wrote {info['players']} players and {info['teams']} teams for {season}, through {through}")


if __name__ == '__main__':
    main()
