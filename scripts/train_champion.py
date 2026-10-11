#!/usr/bin/env python3
"""Champion predictor: every team's title chances, from 1950 to the season ahead.

Reads data/*.json (from prep_data.py and prep_playoffs.py) and writes data/champion_model.json:
  - after the regular season: each season's title odds from that season's
    team and roster stats, predicted by a model that never saw that season
    (leave-one-season-out), next to what really happened
  - current: the latest season's odds, if it has no champion yet
  - preseason: once the latest season has a champion, next season's odds from
    a second model that learned how one season carries over to the next title
    (backtested the same way)

Two logistic regressions on a handful of inputs. Bigger models did no better:
there are only ~77 champions to learn from. Win chances are each team's model
score, normalized within the season and raised to a power fit on the backtest,
so a 30% favorite has won about 30% of the time.

Usage:  pip install scikit-learn && python3 scripts/train_champion.py
"""
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
MULTI = {'2TM', '3TM', '4TM', '5TM'}
FIRST_SEASON = 1950

SEASON_FEATURES = ['srs_z', 'win_pct_z', 'top3_vorp_z', 'top_bpm', 'prev_series_won']
PRE_FEATURES = ['srs_z', 'top_bpm']
LABELS = {
    'srs_z': 'Point differential (SRS) vs. league', 'win_pct_z': 'Win % vs. league',
    'top3_vorp_z': 'Top-3 players’ VORP vs. league', 'top_bpm': 'Best player’s BPM',
    'prev_series_won': 'Playoff series won last season',
}


def frame(name):
    d = json.loads((DATA / f'{name}.json').read_text(encoding='utf-8'))
    return pd.DataFrame(d['rows'], columns=d['columns'])


def zscore(df, col):
    return df.groupby('season')[col].transform(lambda s: (s - s.mean()) / (s.std() or 1))


def build_features() -> pd.DataFrame:
    t = frame('team_geo')[['season', 'franchise', 'team_name', 'abbr', 'w', 'l', 'srs', 'o_rtg', 'd_rtg']].copy()
    t['win_pct'] = t['w'] / (t['w'] + t['l'])
    t['net'] = t['o_rtg'] - t['d_rtg']
    t['srs_z'], t['win_pct_z'] = zscore(t, 'srs'), zscore(t, 'win_pct')

    pt = frame('playoff_teams')[['season', 'team', 'series_won', 'result', 'champion']].rename(columns={'team': 'abbr'})
    t = t.merge(pt, on=['season', 'abbr'], how='left')
    t['champion'] = t['champion'].eq(True)
    t['series_won'] = t['series_won'].fillna(0)

    # roster strength: each player counted on the team he played for (traded players: each stint)
    ps = frame('player_seasons')
    adv = frame('player_advanced')[['season', 'player_id', 'vorp', 'bpm', 'ws']]
    st = ps[~ps['team'].isin(MULTI)].merge(adv, on=['season', 'player_id'], how='left')
    st['minutes'] = st['mp'].fillna(0) * st['g'].fillna(0)
    st = st.sort_values('vorp', ascending=False)
    grp = st.groupby(['season', 'team'])
    r = pd.DataFrame({
        'top3_vorp': grp['vorp'].apply(lambda s: s.sort_values(ascending=False).iloc[:3].sum(min_count=1)),
        'top_bpm': st[st['minutes'] >= 1000].groupby(['season', 'team'])['bpm'].max(),
        'star_id': grp['player_id'].first(),          # most VORP
    }).reset_index().rename(columns={'team': 'abbr'})
    t = t.merge(r, on=['season', 'abbr'], how='left')
    t['top3_vorp_z'] = zscore(t, 'top3_vorp')

    t = t.sort_values(['franchise', 'season'])
    t['prev_series_won'] = t.groupby('franchise')['series_won'].shift(1)
    return t[t['season'] >= FIRST_SEASON].reset_index(drop=True)


def model():
    return make_pipeline(SimpleImputer(), StandardScaler(), LogisticRegression(C=0.3, max_iter=2000))


def pre_model():
    return make_pipeline(SimpleImputer(), StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))


def share_probabilities(score: pd.Series, power: float) -> pd.Series:
    z = np.power(np.maximum(score, 1e-9), power)
    return z / z.sum()


def backtest(df, features, target, by, make):
    """Leave-one-season-out scores, the calibrated power, and accuracy vs. a baseline column."""
    X, y = df[features], df[target].astype(int)
    oof = pd.Series(np.nan, index=df.index)
    for season in sorted(df[by].unique()):
        test = df[by] == season
        oof[test] = make().fit(X[~test], y[~test]).predict_proba(X[test])[:, 1]
    df = df.assign(score=oof)
    groups = [(g['score'], g.index[g[target]][0]) for _, g in df.groupby(by) if g[target].any()]
    def nll(k):
        return -sum(math.log(max(share_probabilities(s, k).get(w, 1e-12), 1e-12)) for s, w in groups)
    power = min(np.arange(0.3, 4.0, 0.05), key=nll)
    df['win_prob'] = df.groupby(by)['score'].transform(lambda s: share_probabilities(s, power))

    hits = top3 = base = 0
    misses = []
    for season, g in df.groupby(by):
        if not g[target].any():
            continue
        g = g.sort_values('win_prob', ascending=False)
        hits += bool(g[target].iloc[0])
        top3 += bool(g[target].iloc[:3].any())
        base += bool(g.loc[g['srs'].idxmax(), target])
        if not g[target].iloc[0]:
            misses.append({'season': int(season), 'predicted': g['franchise'].iloc[0], 'actual': g.loc[g[target], 'franchise'].iloc[0]})
    n = len(groups)
    metrics = {'seasons': n, 'top1': round(hits / n, 3), 'top3': round(top3 / n, 3), 'baseline_top1': round(base / n, 3),
               'power': round(float(power), 2)}
    final = make().fit(X, y)
    coefs = final[-1].coef_[0]
    weights = sorted(({'feature': f, 'label': LABELS[f], 'weight': round(float(c), 3)} for f, c in zip(features, coefs)),
                     key=lambda d: -abs(d['weight']))
    return df, metrics, misses, final, power, weights


def rows(g, season, kind):
    g = g.sort_values('win_prob', ascending=False)
    out = []
    for rank, (_, r) in enumerate(g.iterrows(), start=1):
        out.append({
            'season': int(season), 'franchise': r['franchise'], 'team': r['abbr'], 'team_name': r['team_name'], 'rank': rank,
            'win_prob': round(float(r['win_prob']), 4), 'kind': kind,
            'champion': bool(r['champion']) if kind == 'backtest' else None,
            'result': (r['result'] if isinstance(r['result'], str) else 'Missed playoffs') if kind == 'backtest' else None,
            'w': None if pd.isna(r['w']) else int(r['w']), 'l': None if pd.isna(r['l']) else int(r['l']),
            'srs': None if pd.isna(r['srs']) else round(float(r['srs']), 2),
            'net': None if pd.isna(r['net']) else round(float(r['net']), 1),
            'star_id': r['star_id'] if isinstance(r['star_id'], str) else None,
            'top_bpm': None if pd.isna(r['top_bpm']) else round(float(r['top_bpm']), 1),
        })
    return out


def main():
    started = time.time()
    df = build_features()
    latest = int(df['season'].max())
    has_champion = bool(df.loc[df['season'] == latest, 'champion'].any())
    done = df[df['season'] <= (latest if has_champion else latest - 1)]
    print(f'{len(df):,} team-seasons; latest season {latest}{"" if has_champion else " (no champion yet: will predict)"}')

    # ---- after the regular season ---------------------------------------------------------
    hist, metrics, misses, final, power, weights = backtest(done, SEASON_FEATURES, 'champion', 'season', model)
    metrics['trained_through'] = int(hist['season'].max())
    print(f"backtest: picks the champion in {metrics['top1']:.0%} of seasons (top 3: {metrics['top3']:.0%}); "
          f"best-SRS baseline: {metrics['baseline_top1']:.0%}")
    out_rows = []
    for season, g in hist.groupby('season'):
        out_rows += rows(g, season, 'backtest')
    if not has_champion:
        cur = df[df['season'] == latest].copy()
        cur['win_prob'] = share_probabilities(pd.Series(final.predict_proba(cur[SEASON_FEATURES])[:, 1], index=cur.index), power)
        out_rows += rows(cur, latest, 'prediction')

    # ---- preseason: next season from this one -------------------------------------------------
    pre = None
    if has_champion:
        nxt = df[['franchise', 'season', 'champion']].rename(columns={'champion': 'next_champion'}).assign(season=lambda x: x['season'] - 1)
        p = df.merge(nxt, on=['franchise', 'season'], how='left').assign(target_season=lambda x: x['season'] + 1)
        p['next_champion'] = p['next_champion'].eq(True)
        train = p[p['target_season'] <= latest]
        _, pre_metrics, _, pre_final, pre_power, pre_weights = backtest(
            train.drop(columns=['champion']).rename(columns={'next_champion': 'champion'}), PRE_FEATURES, 'champion', 'target_season', pre_model)
        cur = df[df['season'] == latest].copy()
        score = pd.Series(pre_final.predict_proba(cur[PRE_FEATURES])[:, 1], index=cur.index)
        cur['win_prob'] = share_probabilities(score, pre_power)
        out_rows += rows(cur, latest + 1, 'preseason')
        pre = {'season': latest + 1, 'base_season': latest, 'metrics': pre_metrics, 'weights': pre_weights}
        print(f"preseason backtest: picks the champion in {pre_metrics['top1']:.0%} (top 3: {pre_metrics['top3']:.0%}); "
              f"last season's best SRS: {pre_metrics['baseline_top1']:.0%}")
        print(f'{latest + 1} preseason:', ', '.join([f"{r['team']} {r['win_prob']:.0%}" for r in out_rows if r['season'] == latest + 1][:6]))

    out = {
        'latest_season': latest, 'latest_has_champion': has_champion, 'metrics': metrics, 'weights': weights,
        'misses': misses, 'preseason': pre,
        'columns': list(out_rows[0].keys()), 'rows': [list(r.values()) for r in out_rows],
    }
    (DATA / 'champion_model.json').write_text(json.dumps(out, allow_nan=False))
    print(f'wrote data/champion_model.json ({len(out_rows)} rows) in {time.time() - started:.0f}s')


if __name__ == '__main__':
    main()
