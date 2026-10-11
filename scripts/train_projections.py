#!/usr/bin/env python3
"""Career projections: each current player's next three seasons, from how the
most similar players at the same age actually developed.

Reads data/*.json (from prep_data.py) and writes data/projections.json.

For a player's latest season, find historical player-seasons at the same age
with a similar profile (minutes and league-relative per-36 scoring, rebounding,
playmaking and efficiency, this season and last). Then look at what those
comparables did 1, 2 and 3 seasons later: the similarity-weighted average
change is the projection, the spread of their real outcomes is the range,
and the share still playing is the chance he's still in the league.

Backtest: past seasons projected using only comparables whose futures were
already known at the time, scored against "same as last season" and the
league-average aging curve.

Usage:  python3 scripts/train_projections.py
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
MULTI = {'2TM', '3TM', '4TM', '5TM'}
POOL_FROM = 1975                    # steals/blocks/usage era; minutes reliable
HORIZONS = (1, 2, 3)
K_NEIGHBORS = 60
MIN_G, MIN_MP = 20, 10.0            # a "current" season worth projecting from
PLAYED_G, PLAYED_MP = 10, 5.0       # counts as having played a later season
CUR = ['mp', 'pts_i', 'trb_i', 'ast_i', 'ts_r']
PREV_WEIGHT = 0.5
BACKTEST_SEASONS = range(2005, 2024)
OUT_STATS = ['pts', 'trb', 'ast', 'mp', 'ts_pct']


def frame(name):
    d = json.loads((DATA / f'{name}.json').read_text())
    return pd.DataFrame(d['rows'], columns=d['columns']) if isinstance(d, dict) else pd.DataFrame(d)


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    ps = frame('player_seasons')
    ps = ps.sort_values('team', key=lambda t: ~t.isin(MULTI)).drop_duplicates(['player_id', 'season'])
    adv = frame('player_advanced')[['player_id', 'season', 'ts_pct']]
    env = frame('league_env').set_index('season')
    df = ps.merge(adv, on=['player_id', 'season'], how='left')
    df = df[df['mp'].notna() & (df['mp'] > 0) & df['age'].notna()].copy()
    for k in ('pts', 'trb', 'ast'):
        df[f'{k}_i'] = df[k] / df['mp'] * 36 / df['season'].map(env[f'{k}36'])
    df['ts_r'] = df['ts_pct'] / df['season'].map(env['ts_pct'])
    # previous season (same player, the season right before)
    prev = df[['player_id', 'season'] + CUR].copy()
    prev['season'] += 1
    df = df.merge(prev.rename(columns={c: f'prev_{c}' for c in CUR}), on=['player_id', 'season'], how='left')
    # what happened h seasons later
    later = df[['player_id', 'season', 'g'] + CUR].copy()
    for h in HORIZONS:
        f = later.copy()
        f['season'] -= h
        f['played'] = (f['g'] >= PLAYED_G) & (f['mp'] >= PLAYED_MP)
        df = df.merge(f.rename(columns={c: f'f{h}_{c}' for c in CUR + ['g', 'played']}), on=['player_id', 'season'], how='left')
        df[f'f{h}_played'] = df[f'f{h}_played'].fillna(False).astype(bool)
    return df.reset_index(drop=True), env


def weighted_quantile(values, weights, qs):
    order = np.argsort(values)
    v, w = values[order], weights[order]
    c = np.cumsum(w) / w.sum()
    return [float(np.interp(q, c, v)) for q in qs]


def per_game(idx, mp, env_row, stat):
    return idx * env_row[f'{stat}36'] * mp / 36


def project(target, pool, env_row, sd):
    """Projection for one player-season from a pool of comparables (same age)."""
    has_prev = not np.isnan(target[[f'prev_{c}' for c in CUR]].astype(float)).any()
    cols = CUR + ([f'prev_{c}' for c in CUR] if has_prev else [])
    weights = np.array([1.0] * len(CUR) + [PREV_WEIGHT] * (len(cols) - len(CUR)))
    cand = pool[pool['player_id'] != target['player_id']].dropna(subset=cols)   # never compare a player with himself
    if len(cand) < 20:
        return None
    X = cand[cols].to_numpy(float)
    t = target[cols].to_numpy(float)
    scale = np.array([sd[c.replace('prev_', '')] for c in cols])
    d2 = ((((X - t) / scale) ** 2) * weights).sum(1) / weights.sum()
    near = np.argsort(d2)[:K_NEIGHBORS]
    comps, w = cand.iloc[near], np.exp(-d2[near])
    out = {'horizons': [], 'comps': [{'player_id': r.player_id, 'season': int(r.season), 'similarity': int(round(100 * np.exp(-d)))}
                                    for r, d in zip(comps.head(5).itertuples(), d2[near][:5])]}
    for h in HORIZONS:
        played = comps[f'f{h}_played'].to_numpy()
        p_active = float((w * played).sum() / w.sum())
        if played.sum() < 5:
            out['horizons'].append({'h': h, 'p_active': round(p_active, 3)})
            continue
        c, wp = comps[played], w[played]
        mp = np.clip(target['mp'] + (c[f'f{h}_mp'] - c['mp']).to_numpy(), 0, 48)
        rec = {'h': h, 'p_active': round(p_active, 3), 'n_comps': int(played.sum())}
        for stat in ('pts', 'trb', 'ast'):
            idx = np.clip(target[f'{stat}_i'] + (c[f'f{h}_{stat}_i'] - c[f'{stat}_i']).to_numpy(), 0, None)
            vals = per_game(idx, mp, env_row, stat)
            lo, hi = weighted_quantile(vals, wp, (0.2, 0.8))
            rec[stat] = round(float(np.average(vals, weights=wp)), 1)
            rec[f'{stat}_lo'], rec[f'{stat}_hi'] = round(lo, 1), round(hi, 1)
        lo, hi = weighted_quantile(mp, wp, (0.2, 0.8))
        rec['mp'], rec['mp_lo'], rec['mp_hi'] = round(float(np.average(mp, weights=wp)), 1), round(lo, 1), round(hi, 1)
        if not np.isnan(target['ts_r']):
            ok = c[f'f{h}_ts_r'].notna().to_numpy()
            if ok.sum() >= 5:
                ts = (target['ts_r'] + (c[f'f{h}_ts_r'] - c['ts_r']).to_numpy()[ok]) * env_row['ts_pct']
                rec['ts_pct'] = round(float(np.average(ts, weights=wp[ok])), 3)
        out['horizons'].append(rec)
    return out


def main():
    started = time.time()
    df, env = build()
    pool_all = df[(df['season'] >= POOL_FROM) & (df['g'] >= MIN_G) & (df['mp'] >= MIN_MP)]
    sd = pool_all[CUR].std()
    latest = int(df['season'].max())
    by_age = {a: g for a, g in pool_all.groupby('age')}

    def pool_for(age, max_season):
        frames = [by_age.get(a) for a in (age,)]
        pool = pd.concat([f for f in frames if f is not None]) if any(f is not None for f in frames) else pool_all.iloc[:0]
        pool = pool[pool['season'] <= max_season]
        if len(pool) < 150:                                   # rare ages (very young/old): widen to +/- 1 year
            pool = pd.concat([by_age[a] for a in (age - 1, age, age + 1) if a in by_age])
            pool = pool[pool['season'] <= max_season]
        return pool

    # ---- backtest -----------------------------------------------------------------
    rows = []
    targets = pool_all[pool_all['season'].isin(BACKTEST_SEASONS)]
    # league-average aging curve (per-game change by age), from seasons before the backtest
    curve_src = pool_all[pool_all['season'] < min(BACKTEST_SEASONS) - 3]
    curve = {}
    for h in HORIZONS:
        p = curve_src[curve_src[f'f{h}_played']]
        for stat in ('pts', 'trb', 'ast'):
            fut = per_game(p[f'f{h}_{stat}_i'], p[f'f{h}_mp'], env.loc[latest], stat) - per_game(p[f'{stat}_i'], p['mp'], env.loc[latest], stat)
            curve[(h, stat)] = fut.groupby(p['age']).mean()
    for r in targets.itertuples(index=False):
        t = pd.Series(r._asdict())
        res = project(t, pool_for(int(t['age']), int(t['season']) - 3), env.loc[int(t['season'])], sd)
        if not res:
            continue
        for hz in res['horizons']:
            h = hz['h']
            if not t[f'f{h}_played'] or 'pts' not in hz:
                rows.append({'h': h, 'p_active': hz['p_active'], 'played': bool(t[f'f{h}_played'])})
                continue
            fut_env = env.loc[int(t['season']) + h]
            rec = {'h': h, 'p_active': hz['p_active'], 'played': True}
            for stat in ('pts', 'trb', 'ast'):
                actual = per_game(t[f'f{h}_{stat}_i'], t[f'f{h}_mp'], fut_env, stat)
                now = t[stat]
                rec[f'{stat}_err'] = abs(hz[stat] - actual)
                rec[f'{stat}_persist_err'] = abs(now - actual)
                rec[f'{stat}_curve_err'] = abs(now + curve[(h, stat)].get(int(t['age']), 0) - actual)
                # plain float: numpy bools add like a logical OR, so their mean is wrong
                rec[f'{stat}_in_band'] = float(hz[f'{stat}_lo'] <= actual <= hz[f'{stat}_hi'])
            rows.append(rec)
    bt = pd.DataFrame(rows)
    metrics = {'seasons': f'{min(BACKTEST_SEASONS)}-{max(BACKTEST_SEASONS)}', 'horizons': []}
    for h in HORIZONS:
        b = bt[(bt['h'] == h) & bt['played'] & bt['pts_err'].notna()]
        a = bt[bt['h'] == h]
        m = {'h': h, 'n': int(len(b))}
        for stat in ('pts', 'trb', 'ast'):
            m[stat] = {'model': round(float(b[f'{stat}_err'].mean()), 2), 'last_season': round(float(b[f'{stat}_persist_err'].mean()), 2),
                       'aging_curve': round(float(b[f'{stat}_curve_err'].mean()), 2), 'band_coverage': round(float(b[f'{stat}_in_band'].mean()), 3)}
        # still-in-league calibration: Brier score vs. always predicting the base rate
        base = a['played'].mean()
        m['active_brier'] = round(float(((a['p_active'] - a['played']) ** 2).mean()), 4)
        m['active_brier_base'] = round(float(((base - a['played']) ** 2).mean()), 4)
        metrics['horizons'].append(m)
        print(f"h={h}: pts MAE {m['pts']['model']} (last season {m['pts']['last_season']}, aging curve {m['pts']['aging_curve']}), "
              f"60% band covers {m['pts']['band_coverage']:.0%}; still-playing Brier {m['active_brier']} vs {m['active_brier_base']}  (n={m['n']})")

    # ---- current players --------------------------------------------------------------
    cur = df[(df['season'] == latest) & (df['g'] >= MIN_G) & (df['mp'] >= MIN_MP)]
    projections = []
    for r in cur.itertuples(index=False):
        t = pd.Series(r._asdict())
        # only comparables whose next three seasons are known (same rule as the backtest)
        res = project(t, pool_for(int(t['age']), latest - max(HORIZONS)), env.loc[latest], sd)
        if not res:
            continue
        projections.append({'player_id': t['player_id'], 'season': latest, 'age': int(t['age']),
                            'current': {k: (None if pd.isna(t[k]) else round(float(t[k]), 3 if k == 'ts_pct' else 1)) for k in OUT_STATS},
                            'horizons': [{**hz, 'season': latest + hz['h'], 'age': int(t['age']) + hz['h']} for hz in res['horizons']],
                            'comps': res['comps']})
    out = {'latest_season': latest, 'method': {'k': K_NEIGHBORS, 'pool_from': POOL_FROM, 'min_games': MIN_G, 'min_mp': MIN_MP,
                                                'band': [0.2, 0.8]},
           'metrics': metrics, 'players': projections}
    (DATA / 'projections.json').write_text(json.dumps(out, allow_nan=False))
    print(f'{len(projections)} current players projected; wrote data/projections.json in {time.time() - started:.0f}s')


if __name__ == '__main__':
    main()
