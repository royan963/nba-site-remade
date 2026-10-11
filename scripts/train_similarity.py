#!/usr/bin/env python3
"""Similar players: each player's closest stylistic matches across eras.

Reads data/*.json, including data/archetypes.json (run train_archetypes.py
first), and writes data/similar_players.json.

Two parts, both relative to each season's league so eras compare:
  - a career fingerprint: minutes-weighted per-36 scoring, rebounding,
    playmaking, steal and block rates, efficiency, usage, three-point volume
    (vs. the league and vs. players his size) and height
  - how he scores: free throws per shot and three-point accuracy (both vs.
    the league), plus, from 1996-97 on, how many of his shots were assisted
    and where they came from (at the rim, mid-range)
  - a career style mix: how his minutes split across the playing-style roles
    (e.g. Brook Lopez: stretch big 51%, scoring big 37%), so players who
    changed styles match others who made the same change, not an average

Stats that weren't recorded for one of the two players (blocks, steals and
usage before the mid-1970s) count as a moderate mismatch instead of being
skipped, so old-era players can't look near-identical on fewer stats.

Usage:  python3 scripts/train_similarity.py [--compare]
  --compare  also scores the previous data/similar_players.json on the same checks
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_archetypes import FEATURES as SEASON_FEATURES, build_features   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
MIN_CAREER_MINUTES = 3000
N_NEIGHBORS = 15
# season feature -> name in the API/database (kept from the first version where possible)
# How he scores (added because overall efficiency hid opposite styles: Harden
# gets to the line, Curry makes threes off movement).
SCORING_FEATURES = ['ftr_rel', 'x3_acc', 'assisted_rel', 'rim_rel', 'mid_rel']
TRACKED = {'assisted_rel', 'rim_rel', 'mid_rel'}         # only tracked from 1996-97
FEATURES = SEASON_FEATURES + SCORING_FEATURES
NAMES = {'pts_i': 'pts_idx', 'trb_i': 'trb_idx', 'ast_i': 'ast_idx', 'stl_i': 'stl_idx', 'blk_i': 'blk_idx', 'ts_i': 'ts_idx',
         'usg_pct': 'usg_percent', 'x3_i': 'x3p_ar_diff', 'x3_pos': 'x3p_pos_diff', 'ht_in_in': 'ht_in_in',
         'ftr_rel': 'ft_rate_diff', 'x3_acc': 'x3p_accuracy', 'assisted_rel': 'assisted_diff', 'rim_rel': 'rim_diff', 'mid_rel': 'mid_diff'}
WEIGHTS = {'pts_i': 1.2, 'trb_i': 1.0, 'ast_i': 1.0, 'stl_i': 0.7, 'blk_i': 0.7, 'ts_i': 0.8, 'usg_pct': 0.8, 'x3_i': 0.7,
           'x3_pos': 0.7, 'ht_in_in': 1.0, 'ftr_rel': 0.8, 'x3_acc': 0.8, 'assisted_rel': 0.6, 'rim_rel': 0.5, 'mid_rel': 0.5}
MISSING_PENALTY = 1.0          # squared-z mismatch charged per stat one of the two players lacks
TRACKED_PENALTY = 0.5          # smaller for 1996-97+ tracking stats, so cross-era matches stay possible
STYLE_WEIGHT = 1.5             # how much the style mix counts next to the fingerprint


def frame(name):
    d = json.loads((DATA / f'{name}.json').read_text())
    return pd.DataFrame(d['rows'], columns=d['columns']) if isinstance(d, dict) and 'columns' in d else d


def scoring_features(seasons):
    """Per-season 'how he scores' stats, each relative to that season's league."""
    env = frame('league_env').set_index('season')
    adv = frame('player_advanced')[['player_id', 'season', 'f_tr']]
    df = seasons.merge(adv, on=['player_id', 'season'], how='left')
    df['ftr_rel'] = df['f_tr'] - df['season'].map(env['ft_rate'])
    # extra threes made per 36 minutes vs. a league-average shooter on the same attempts
    # (0 for non-shooters and before the three-point line)
    per36 = df['x3pa'].fillna(0) / df['mp'] * 36
    df['x3_acc'] = np.where(df['season'] >= 1980, per36 * (df['x3p_pct'].fillna(0) - df['season'].map(env['x3p_pct'])), 0.0)
    df.loc[(df['season'] >= 1980) & (df['x3pa'].fillna(0) < 0.5), 'x3_acc'] = 0.0
    sh = frame('player_shooting')
    sh['assisted'] = sh['pct_assisted_2p'].fillna(0) * (1 - sh['pct_fga_3p'].fillna(0)) + sh['pct_assisted_3p'].fillna(0) * sh['pct_fga_3p'].fillna(0)
    sh['mid'] = sh['pct_fga_10_16'].fillna(0) + sh['pct_fga_16_3p'].fillna(0)
    df = df.merge(sh[['player_id', 'season', 'assisted', 'pct_fga_0_3', 'mid']], on=['player_id', 'season'], how='left')
    for col, out in (('assisted', 'assisted_rel'), ('pct_fga_0_3', 'rim_rel'), ('mid', 'mid_rel')):
        ok = df[col].notna()
        league = df[ok].groupby('season').apply(lambda g: np.average(g[col], weights=g['minutes']), include_groups=False)
        df[out] = df[col] - df['season'].map(league)
    return df


def career_table():
    seasons = scoring_features(build_features())
    def wavg(g, col):
        ok = g[col].notna()
        return np.average(g.loc[ok, col], weights=g.loc[ok, 'minutes']) if ok.any() else np.nan
    car = seasons.groupby('player_id').apply(
        lambda g: pd.Series({**{c: wavg(g, c) for c in FEATURES}, 'minutes': g['minutes'].sum()}), include_groups=False)
    car = car[car['minutes'] >= MIN_CAREER_MINUTES]
    mixes = json.loads((DATA / 'archetypes.json').read_text())['career_mix']
    car = car[car.index.isin(mixes.keys())]
    M = np.array([mixes[p] for p in car.index], dtype=float)
    return car, M / M.sum(1, keepdims=True)


def neighbors(car, M):
    X = car[FEATURES].to_numpy(float)
    # cap at 3 standard deviations so one extreme stat (Curry's three-point accuracy)
    # can't swamp every comparison, as in the archetype model
    Z = np.clip((X - np.nanmean(X, 0)) / np.nanstd(X, 0), -3, 3)
    known = ~np.isnan(Z)
    Z0 = np.where(known, Z, 0.0)
    w = np.array([WEIGHTS[f] for f in FEATURES])
    penalty = np.array([TRACKED_PENALTY if f in TRACKED else MISSING_PENALTY for f in FEATURES])
    ids = car.index.to_list()
    out = {}
    for i, pid in enumerate(ids):
        both = known & known[i]
        diff = ((Z0 - Z0[i]) ** 2 * both * w).sum(1) + ((~both) * w * penalty).sum(1)
        fp = diff / w.sum()
        style = 1 - np.minimum(M, M[i]).sum(1)              # 0 = same mix, 1 = no overlap
        d = fp + STYLE_WEIGHT * style
        d[i] = np.inf
        order = np.argsort(d)[:N_NEIGHBORS]
        out[pid] = [[ids[j], int(round(100 * np.exp(-d[j])))] for j in order]
    return out, Z


def evaluate(neigh, label, career, M_by_id):
    """Checks on things the model doesn't directly optimize."""
    pos = career['pos'].fillna('').str.split('-').str[0].map({'PG': 'G', 'SG': 'G', 'G': 'G', 'SF': 'F', 'PF': 'F', 'F': 'F', 'C': 'C'})
    par = (career['x3pa'] / career['fga'].replace(0, np.nan))
    first = career['first_season']
    pos_hits, three_gap, old_top, new_top, mix_overlap = [], [], [], [], []
    for pid, lst in neigh.items():
        top = [o for o, _ in lst[:5] if o in pos.index]
        if not top or pid not in pos.index:
            continue
        pos_hits.append(np.mean([pos[o] == pos[pid] for o in top]))
        if first[pid] >= 1985 and not np.isnan(par[pid]):
            three_gap.append(np.nanmean([abs(par[o] - par[pid]) for o in top]))
        (old_top if first[pid] < 1970 else new_top).append(lst[0][1])
        if pid in M_by_id:
            mix_overlap.append(np.mean([np.minimum(M_by_id[pid], M_by_id[o]).sum() for o in top if o in M_by_id]))
    mid = (career['first_season'] + career['last_season']) / 2
    cross = [np.mean([abs(mid[o] - mid[pid]) > 15 for o, _ in lst[:5] if o in mid.index]) for pid, lst in neigh.items() if pid in mid.index]
    print(f'{label:>9}: same position {np.mean(pos_hits):.0%} | 3PT-rate gap (modern players) {np.mean(three_gap):.3f} | '
          f'top match score: pre-1970 players {np.median(old_top):.0f}, later {np.median(new_top):.0f} | '
          f'matches 15+ years apart {np.mean(cross):.0%} | style-mix overlap {np.mean(mix_overlap):.0%}')


def main():
    compare = '--compare' in sys.argv
    old = json.loads((DATA / 'similar_players.json').read_text()) if compare and (DATA / 'similar_players.json').exists() else None
    car, M = career_table()
    neigh, Z = neighbors(car, M)
    out = {'features': [NAMES[f] for f in FEATURES],
           'players': {pid: [None if np.isnan(v) else round(float(v), 3) for v in row]
                       for pid, row in zip(car.index, car[FEATURES].to_numpy(float))},
           'neighbors': neigh,
           'method': {'min_career_minutes': MIN_CAREER_MINUTES, 'style_weight': STYLE_WEIGHT, 'missing_penalty': MISSING_PENALTY}}
    if compare:
        career = frame('player_career').set_index('player_id')
        M_by_id = dict(zip(car.index, M))
        if old:
            evaluate(old['neighbors'], 'before', career, M_by_id)
        evaluate(neigh, 'after', career, M_by_id)
    (DATA / 'similar_players.json').write_text(json.dumps(out, allow_nan=False))
    print(f'{len(neigh):,} players; wrote data/similar_players.json')


if __name__ == '__main__':
    main()
