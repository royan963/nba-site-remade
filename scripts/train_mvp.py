#!/usr/bin/env python3
"""MVP predictor: learn MVP vote share from 70 seasons of voting (1956-present).

Reads data/*.json (from prep_data.py) and writes data/mvp_model.json:
  - backtest: every past season predicted by a model that never saw it
    (leave-one-season-out), with the real result alongside
  - current: the latest season's race, from a model trained on every season
  - metrics vs. a simple baseline (pick the Win Shares leader)
  - feature importances (permutation importance on the backtest)

Usage:  pip install scikit-learn && python3 scripts/train_mvp.py
"""
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
MULTI = {'2TM', '3TM', '4TM', '5TM'}
FIRST_MVP_SEASON = 1956
GAMES_RULE_SEASON = 2024          # 65-game minimum for MVP eligibility, from 2023-24
# The rule has exceptions (games of 15-20 minutes can partly count; season-ending
# injuries lower the bar to 62), which this data can't see. So only players under
# 62 games are excluded; 62-64 are kept and flagged.
HARD_MIN_GAMES, RULE_GAMES = 62, 65
SEED = 7


def frame(name):
    d = json.loads((DATA / f'{name}.json').read_text())
    return pd.DataFrame(d['rows'], columns=d['columns']) if isinstance(d, dict) else pd.DataFrame(d)


def build_features() -> pd.DataFrame:
    ps = frame('player_seasons')
    stints = ps[~ps['team'].isin(MULTI)]
    # one row per player-season: the combined row for traded players
    seasons = ps.sort_values('team', key=lambda t: ~t.isin(MULTI)).drop_duplicates(['player_id', 'season'])
    # the team he played the most games for (for team record)
    main_team = stints.sort_values('g', ascending=False).drop_duplicates(['player_id', 'season'])[['player_id', 'season', 'team']]
    df = seasons.drop(columns='team').merge(main_team, on=['player_id', 'season'], how='left')

    adv = frame('player_advanced')
    df = df.merge(adv, on=['player_id', 'season'], how='left')

    teams = frame('team_geo')[['season', 'abbr', 'w', 'l']].rename(columns={'abbr': 'team'})
    teams['win_pct'] = teams['w'] / (teams['w'] + teams['l'])
    teams['team_rank'] = teams.groupby('season')['win_pct'].rank(ascending=False, method='min')
    df = df.merge(teams[['season', 'team', 'win_pct', 'team_rank']], on=['season', 'team'], how='left')

    env = frame('league_env').set_index('season')
    df['pts_idx'] = df['pts'] / df['mp'] * 36 / df['season'].map(env['pts36'])
    df['ts_rel'] = df['ts_pct'] / df['season'].map(env['ts_pct'])

    # MVP is decided against that season's field, so rank and scale within season
    for col in ('pts', 'ws', 'per', 'bpm', 'vorp', 'ws_48'):
        df[f'{col}_rank'] = df.groupby('season')[col].rank(ascending=False, method='min')
        z = df.groupby('season')[col].transform(lambda s: (s - s.mean()) / (s.std() or 1))
        df[f'{col}_z'] = z

    aw = frame('player_award_shares')
    mvp = aw[aw['award'] == 'nba mvp'][['season', 'player_id', 'share', 'winner']]
    df = df.merge(mvp, on=['season', 'player_id'], how='left')
    df['share'] = df['share'].fillna(0.0)
    df['winner'] = df['winner'].fillna(False).astype(bool)

    # voter fatigue: MVPs won in earlier seasons
    wins = mvp[mvp['winner']].groupby('player_id')['season'].apply(sorted).to_dict()
    df['prior_mvps'] = [sum(s < season for s in wins.get(pid, [])) for pid, season in zip(df['player_id'], df['season'])]
    df['won_last_year'] = [int(season - 1 in wins.get(pid, [])) for pid, season in zip(df['player_id'], df['season'])]

    df = df[(df['season'] >= FIRST_MVP_SEASON) & (df['g'].fillna(0) >= 20)].copy()
    rule = df['season'] >= GAMES_RULE_SEASON
    df['eligible'] = ~(rule & (df['g'] < HARD_MIN_GAMES))
    df['needs_exception'] = rule & (df['g'] >= HARD_MIN_GAMES) & (df['g'] < RULE_GAMES)
    return df.reset_index(drop=True)


FEATURES = ['g', 'mp', 'pts', 'trb', 'ast', 'stl', 'blk', 'per', 'ts_pct', 'usg_pct', 'ws', 'ws_48', 'bpm', 'vorp',
            'win_pct', 'team_rank', 'pts_idx', 'ts_rel', 'pts_rank', 'ws_rank', 'per_rank', 'bpm_rank', 'vorp_rank',
            'ws_48_rank', 'pts_z', 'ws_z', 'per_z', 'bpm_z', 'vorp_z', 'ws_48_z', 'prior_mvps', 'won_last_year']
LABELS = {
    'g': 'Games played', 'mp': 'Minutes per game', 'pts': 'Points per game', 'trb': 'Rebounds per game',
    'ast': 'Assists per game', 'stl': 'Steals per game', 'blk': 'Blocks per game', 'per': 'PER', 'ts_pct': 'True shooting',
    'usg_pct': 'Usage', 'ws': 'Win Shares', 'ws_48': 'WS/48', 'bpm': 'Box Plus/Minus', 'vorp': 'VORP',
    'win_pct': 'Team win %', 'team_rank': "Team's league rank", 'pts_idx': 'Scoring vs. league', 'ts_rel': 'Efficiency vs. league',
    'pts_rank': 'Scoring rank in season', 'ws_rank': 'Win Shares rank in season', 'per_rank': 'PER rank in season',
    'bpm_rank': 'BPM rank in season', 'vorp_rank': 'VORP rank in season', 'ws_48_rank': 'WS/48 rank in season',
    'pts_z': 'Scoring vs. field', 'ws_z': 'Win Shares vs. field', 'per_z': 'PER vs. field', 'bpm_z': 'BPM vs. field',
    'vorp_z': 'VORP vs. field', 'ws_48_z': 'WS/48 vs. field', 'prior_mvps': 'Previous MVPs', 'won_last_year': 'Won MVP last year',
}


def model():
    return HistGradientBoostingRegressor(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=20,
                                         l2_regularization=1.0, random_state=SEED)


def season_probabilities(pred: pd.Series, temperature: float) -> pd.Series:
    """Turn predicted shares into a chance of winning (softmax within the season)."""
    z = np.exp((pred - pred.max()) / temperature)
    return z / z.sum()


def main():
    started = time.time()
    df = build_features()
    hist = df[df['season'] <= df.loc[df['share'] > 0, 'season'].max()]           # seasons with voting
    latest = int(df['season'].max())
    has_votes = latest in set(hist['season'])
    print(f'{len(df):,} player-seasons, {hist["season"].nunique()} seasons with voting; latest season {latest}'
          f'{"" if has_votes else " (no voting yet: will predict)"}')

    # ---- leave-one-season-out backtest ------------------------------------------------
    X, y = hist[FEATURES], hist['share']
    oof = pd.Series(np.nan, index=hist.index)
    for season in sorted(hist['season'].unique()):
        test = hist['season'] == season
        m = model().fit(X[~test], y[~test])
        oof[test] = m.predict(X[test])
    hist = hist.assign(pred=oof.clip(lower=0))

    # calibrate win probabilities: temperature that best explains who actually won
    def nll(t):
        total = 0.0
        for _, g in hist.groupby('season'):
            p = season_probabilities(g['pred'][g['eligible']], t)
            winner = g.index[g['winner']]
            total -= math.log(max(p.get(winner[0], 1e-9), 1e-9)) if len(winner) else 0
        return total
    temperature = min(np.arange(0.02, 0.5, 0.01), key=nll)

    results, misses = [], []
    for season, g in hist.groupby('season'):
        g = g[g['eligible']].sort_values('pred', ascending=False)
        actual = g[g['winner']]
        pick = g.iloc[0]
        ws_pick = g.sort_values('ws', ascending=False).iloc[0]
        winner_rank = int((g['pred'] > actual['pred'].iloc[0]).sum() + 1) if len(actual) else None
        results.append({'season': int(season), 'model_hit': bool(pick['winner']), 'ws_hit': bool(ws_pick['winner']),
                        'winner_rank': winner_rank,
                        'top3': bool(actual.index[0] in g.index[:3]) if len(actual) else False})
        if not pick['winner'] and len(actual):
            misses.append({'season': int(season), 'predicted': pick['player_id'], 'actual': actual['player_id'].iloc[0]})
    res = pd.DataFrame(results)
    metrics = {
        'seasons': int(len(res)),
        'top1': round(float(res['model_hit'].mean()), 3),
        'top3': round(float(res['top3'].mean()), 3),
        'baseline_top1': round(float(res['ws_hit'].mean()), 3),
        'mean_winner_rank': round(float(res['winner_rank'].mean()), 2),
        'temperature': round(float(temperature), 3),
        'trained_through': int(hist['season'].max()),
    }
    print(f"backtest: model picks the MVP in {metrics['top1']:.0%} of seasons (top 3: {metrics['top3']:.0%}); "
          f"Win Shares leader baseline: {metrics['baseline_top1']:.0%}")

    # ---- final model on every season with voting, for the current race ------------------------
    final = model().fit(X, y)
    imp = permutation_importance(final, X, y, n_repeats=5, random_state=SEED, scoring='r2')
    importances = sorted(({'feature': f, 'label': LABELS[f], 'importance': round(float(v), 4)}
                          for f, v in zip(FEATURES, imp.importances_mean)), key=lambda d: -d['importance'])

    cur = df[df['season'] == latest].copy()
    cur['pred'] = final.predict(cur[FEATURES]).clip(min=0) if not has_votes else hist.loc[hist['season'] == latest, 'pred']

    def rows(g, n):
        g = g.copy()
        g['win_prob'] = 0.0
        el = g['eligible']
        g.loc[el, 'win_prob'] = season_probabilities(g.loc[el, 'pred'], temperature)
        g = g.sort_values(['eligible', 'pred'], ascending=[False, False]).head(n)
        out = []
        for rank, (_, r) in enumerate(g.iterrows(), start=1):
            out.append({
                'season': int(r['season']), 'player_id': r['player_id'], 'rank': rank,
                'predicted_share': round(float(r['pred']), 4), 'win_prob': round(float(r['win_prob']), 4),
                'actual_share': round(float(r['share']), 4) if r['season'] <= metrics['trained_through'] else None,
                'winner': bool(r['winner']), 'eligible': bool(r['eligible']),
                'needs_exception': bool(r['needs_exception']), 'team': r['team'],
                'g': int(r['g']), 'win_pct': None if pd.isna(r['win_pct']) else round(float(r['win_pct']), 3),
            })
        # actual vote rank among those who got votes
        return out

    candidates = []
    for season, g in hist.groupby('season'):
        top = rows(g, 10)
        voted = g[g['share'] > 0].sort_values('share', ascending=False)
        actual_rank = {pid: i for i, pid in enumerate(voted['player_id'], start=1)}
        for c in top:
            c['actual_rank'] = actual_rank.get(c['player_id'])
        # make sure the real winner is always listed, even if the model ranked him low
        if not any(c['winner'] for c in top) and len(voted):
            extra = rows(g, len(g))
            w = next(c for c in extra if c['winner'])
            w['actual_rank'] = 1
            top.append(w)
        candidates += top
    if not has_votes:
        for c in rows(cur, 15):
            c['actual_rank'] = None
            candidates.append(c)

    out = {
        'latest_season': latest, 'latest_has_votes': has_votes, 'games_rule_season': GAMES_RULE_SEASON,
        'games_rule': {'min': RULE_GAMES, 'hard_min': HARD_MIN_GAMES},
        'metrics': metrics, 'importances': importances, 'misses': misses,
        'columns': list(candidates[0].keys()), 'rows': [list(c.values()) for c in candidates],
    }
    (DATA / 'mvp_model.json').write_text(json.dumps(out, allow_nan=False))
    print(f'wrote data/mvp_model.json ({len(candidates)} candidate rows) in {time.time() - started:.0f}s')
    print('top features:', ', '.join(f"{d['label']} ({d['importance']:.3f})" for d in importances[:6]))
    if not has_votes:
        print(f'{latest} race:', ', '.join(f"{c['player_id']} {c['win_prob']:.0%}" for c in out['rows'] and
                                           [dict(zip(out['columns'], r)) for r in out['rows'] if r[0] == latest][:5]))


if __name__ == '__main__':
    main()
