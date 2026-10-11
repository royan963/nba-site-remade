#!/usr/bin/env python3
"""Player archetypes: cluster every player-season into roles by playing style.

Reads data/*.json (from prep_data.py) and writes data/archetypes.json.

- Style features, all relative to that season's league so eras compare:
  per-36 scoring, rebounding, playmaking, steal and block rates; true
  shooting; usage; three-point tendency vs. the league AND vs. players of
  similar height that season (what makes a big a "stretch" big); height.
- k-means (weighted by minutes) learns the roles from 1979-80 on, when every
  feature exists. Older seasons (1951-52 on; minutes weren't recorded before)
  are placed in the nearest role using the stats they have.
- Stretch bigs are too rare (<1% of minutes) for clustering to separate, so
  they're defined by an explicit rule on top of the clusters.
- Cluster names come from matching each cluster to the closest role profile
  below, so they stay right when the data (and the clusters) change.

Usage:  pip install scikit-learn && python3 scripts/train_archetypes.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
MULTI = {'2TM', '3TM', '4TM', '5TM'}
MIN_MINUTES = 1000
TRAIN_FROM = 1980
K = 9
SEED = 7

FEATURES = ['pts_i', 'trb_i', 'ast_i', 'stl_i', 'blk_i', 'ts_i', 'usg_pct', 'x3_i', 'x3_pos', 'ht_in_in']
FEATURE_LABELS = {'pts_i': 'Scoring', 'trb_i': 'Rebounding', 'ast_i': 'Playmaking', 'stl_i': 'Steals', 'blk_i': 'Blocks',
                  'ts_i': 'Efficiency', 'usg_pct': 'Usage', 'x3_i': '3PT volume', 'x3_pos': '3PT vs. size', 'ht_in_in': 'Height'}

# Role profiles (in standard deviations from the 1980+ average). Each cluster
# gets the profile it most resembles; every profile is used at most once.
PROFILES = [
    ('star-creator', 'Star creator', 'Takes over possessions: elite scoring volume and usage, plus real playmaking.',
     {'pts_i': 2, 'ast_i': 1, 'usg_pct': 2}),
    ('scoring-wing', 'Scoring wing', 'A wing who looks for his own shot more than most, without running the offense.',
     {'pts_i': 1, 'usg_pct': 1, 'trb_i': -0.5}),
    ('floor-general', 'Pass-first point guard', 'Small, sets up teammates and pressures the ball; scoring is secondary.',
     {'ast_i': 2, 'stl_i': 1.3, 'ht_in_in': -1.3, 'trb_i': -1}),
    ('combo-guard', 'Combo guard', 'A smaller guard who splits scoring and playmaking; since the three-point line, a high-volume shooter.',
     {'ast_i': 1, 'x3_i': 1, 'ht_in_in': -1.3, 'trb_i': -1}),
    ('spot-up-shooter', 'Spot-up shooter', 'Spaces the floor: far more of his shots are threes than for others his size.',
     {'x3_i': 1.5, 'x3_pos': 1.6, 'usg_pct': -0.5}),
    ('role-player', 'Low-usage role player', 'Plays minutes without needing the ball: below-average volume and efficiency.',
     {'pts_i': -0.8, 'ts_i': -0.8, 'usg_pct': -0.7}),
    ('rebounding-forward', 'Rebounding forward', 'A big body who rebounds and stays inside, rarely creating or shooting threes.',
     {'trb_i': 1, 'ht_in_in': 0.7, 'ast_i': -0.7, 'x3_i': -0.7}),
    ('scoring-big', 'Scoring big', 'A frontcourt focal point: scores, rebounds and blocks shots with high usage.',
     {'pts_i': 1.2, 'trb_i': 1.3, 'blk_i': 1, 'usg_pct': 1.1, 'ht_in_in': 1.1}),
    ('rim-protector', 'Rim protector', 'Blocks shots and controls the glass; efficient, low-usage finisher, no threes.',
     {'trb_i': 1.4, 'blk_i': 1.9, 'usg_pct': -0.9, 'x3_i': -1.2, 'ht_in_in': 1.2}),
]
STRETCH = ('stretch-big', 'Stretch big', 'A power forward or center (6\u20199\u201d+) who shoots threes far more than players his size, '
           'pulling a defender away from the rim. Scored on a sliding scale by an explicit rule: too rare for clustering to separate.')
STRETCH_MIN_HEIGHT, STRETCH_MIN_POS_Z, STRETCH_MIN_3PAR = 81, 1.0, 0.25
MIX_TEMPERATURE = 0.25           # lower = more decisive style mixes
BIG_POSITIONS = {'PF', 'C'}


def frame(name):
    d = json.loads((DATA / f'{name}.json').read_text())
    return pd.DataFrame(d['rows'], columns=d['columns']) if isinstance(d, dict) else pd.DataFrame(d)


def build_features() -> pd.DataFrame:
    ps = frame('player_seasons')
    ps = ps.sort_values('team', key=lambda t: ~t.isin(MULTI)).drop_duplicates(['player_id', 'season'])
    adv = frame('player_advanced')[['player_id', 'season', 'ts_pct', 'usg_pct', 'x3p_ar']]
    career = frame('player_career')[['player_id', 'ht_in_in']]
    env = frame('league_env').set_index('season')
    df = ps.merge(adv, on=['player_id', 'season'], how='left').merge(career, on='player_id', how='left')
    df = df[df['mp'].notna() & (df['mp'] > 0) & df['ht_in_in'].notna()].copy()
    df['minutes'] = df['mp'] * df['g']
    df = df[df['minutes'] >= MIN_MINUTES].copy()
    for k in ('pts', 'trb', 'ast', 'stl', 'blk'):
        df[f'{k}_i'] = df[k] / df['mp'] * 36 / df['season'].map(env[f'{k}36'])
    df['ts_i'] = df['ts_pct'] / df['season'].map(env['ts_pct'])
    three = df['season'] >= 1980                                     # no three-point line before 1979-80
    df['x3_i'] = np.where(three, df['x3p_ar'] - df['season'].map(env['x3p_ar']), 0.0)
    df['band'] = pd.cut(df['ht_in_in'], [0, 76, 79, 82, 99], labels=False)
    peers = (df[three].groupby(['season', 'band'])
             .apply(lambda g: np.average(g['x3p_ar'].fillna(0), weights=g['minutes']), include_groups=False)
             .rename('band_x3'))
    df = df.join(peers, on=['season', 'band'])
    df['x3_pos'] = np.where(three, df['x3p_ar'].fillna(0) - df['band_x3'], 0.0)
    return df.reset_index(drop=True)


def name_clusters(centers: np.ndarray) -> list[int]:
    """Profile index for each cluster: greedy best match by cosine similarity."""
    sig = np.array([[p[3].get(f, 0.0) for f in FEATURES] for p in PROFILES])
    sim = (centers / np.linalg.norm(centers, axis=1, keepdims=True)) @ (sig / np.linalg.norm(sig, axis=1, keepdims=True)).T
    assigned, used = [None] * len(centers), set()
    for flat in np.argsort(-sim, axis=None):
        c, p = divmod(int(flat), sim.shape[1])
        if assigned[c] is None and p not in used:
            assigned[c] = p
            used.add(p)
    return assigned


def main():
    df = build_features()
    train = df[df['season'] >= TRAIN_FROM].dropna(subset=FEATURES)
    mu, sd = train[FEATURES].mean(), train[FEATURES].std()
    z = lambda frame_: ((frame_[FEATURES] - mu) / sd).clip(-3, 3)
    km = KMeans(K, n_init=20, random_state=SEED).fit(z(train).values, sample_weight=train['minutes'].values)
    centers = km.cluster_centers_
    profile_of = name_clusters(centers)

    # assign every qualified season (masking missing stats) to its nearest centroids
    Z = z(df).values
    mask = ~np.isnan(Z)
    Z0 = np.where(mask, Z, 0.0)
    d2 = np.stack([((Z0 - c) ** 2 * mask).sum(1) / mask.sum(1) for c in centers], axis=1)
    order = np.argsort(d2, axis=1)
    df['cluster'], df['second'] = order[:, 0], order[:, 1]
    best, runner = np.take_along_axis(d2, order[:, :2], 1).T
    df['fit'] = np.round(100 * (1 - best / np.maximum(runner, 1e-9)) ** 0.5, 0)      # 0 = torn between two roles
    df['features_used'] = mask.sum(1)

    roles = [(p[0], p[1], p[2]) for p in (PROFILES[i] for i in profile_of)] + [STRETCH]
    stretch_id = len(roles) - 1
    pos_z = (df['x3_pos'] - mu['x3_pos']) / sd['x3_pos']
    primary_pos = df['pos'].fillna('').str.split('-').str[0]
    is_stretch = (primary_pos.isin(BIG_POSITIONS) & (df['ht_in_in'] >= STRETCH_MIN_HEIGHT) & (pos_z >= STRETCH_MIN_POS_Z)
                  & (df['x3p_ar'].fillna(0) >= STRETCH_MIN_3PAR))
    # Style mix: every season gets a share of each role instead of one label.
    # Cluster shares come from how close the season is to each role's center
    # (a softmax over distances); "stretch big" is a sliding scale on top
    # (how much more he shoots threes than players his size, for PFs/Cs 6'9"+).
    logits = -d2 / MIX_TEMPERATURE
    cluster_mix = np.exp(logits - logits.max(1, keepdims=True))
    cluster_mix /= cluster_mix.sum(1, keepdims=True)
    sigmoid = lambda x: 1 / (1 + np.exp(-x))
    big = primary_pos.isin(BIG_POSITIONS) & (df['ht_in_in'] >= STRETCH_MIN_HEIGHT)
    stretch = (big.to_numpy() * sigmoid((pos_z.fillna(-9).to_numpy() - STRETCH_MIN_POS_Z) / 0.25)
               * sigmoid((df['x3p_ar'].fillna(0).to_numpy() - STRETCH_MIN_3PAR) / 0.05))
    mix = np.hstack([cluster_mix * (1 - stretch)[:, None], stretch[:, None]])
    ranked = np.argsort(-mix, axis=1)
    df['role'], df['role2'] = ranked[:, 0], ranked[:, 1]
    df['fit'] = np.round(100 * mix[np.arange(len(mix)), ranked[:, 0]])          # share of his main role
    mix_pct = np.round(mix * 100).astype(int)

    # minutes share of each role by season, counting each season's whole mix
    seasons = sorted(df['season'].unique())
    weighted = pd.DataFrame(mix * df['minutes'].to_numpy()[:, None]).assign(season=df['season'].to_numpy())
    by_season = weighted.groupby('season').sum()
    share = by_season.div(by_season.sum(axis=1), axis=0)
    trend = {str(r): [round(float(share.loc[s_, r]), 4) for s_ in seasons] for r in range(len(roles))}

    # career style mix: minutes-weighted blend of his seasons
    cm = pd.DataFrame(mix * df['minutes'].to_numpy()[:, None]).assign(player_id=df['player_id'].to_numpy()).groupby('player_id').sum()
    career_mix = {pid: [int(round(v)) for v in 100 * row / row.sum()] for pid, row in cm.iterrows()}

    names = frame('player_career').set_index('player_id')['player']
    zf = z(df)
    archetypes = []
    for rid, (key, name, desc) in enumerate(roles):
        members = df[df['role'] == rid]
        prof = (zf[df['role'] == rid].mul(members['minutes'], axis=0).sum() / members['minutes'].sum()).round(2)
        # examples: the most typical high-minute seasons, one per player, from the modern era and before
        dist = d2[df['role'] == rid, min(rid, K - 1)] if rid < K else -pos_z[df['role'] == rid]
        # typical = closest to the role's center among high-minute seasons, one per player. Main
        # examples come from 1979-80 on (every stat available); older ones are listed separately.
        def pick(rows, n):
            ranked = rows.sort_values('_d').head(250).sort_values('minutes', ascending=False)
            return ranked.drop_duplicates('player_id').head(n)
        members_d = members.assign(_d=dist)
        examples = pick(members_d[members_d['season'] >= TRAIN_FROM], 8)
        classic = pick(members_d[members_d['season'] < TRAIN_FROM], 4)
        decade = lambda s: (s // 10) * 10
        dec = df['season'].map(decade)
        by_decade = (pd.Series(mix[:, rid] * df['minutes'].to_numpy()).groupby(dec.to_numpy()).sum()
                     / df['minutes'].groupby(dec).sum()).sort_index()
        archetypes.append({
            'id': rid, 'key': key, 'name': name, 'description': desc,
            'profile': {f: float(prof[f]) for f in FEATURES if not np.isnan(prof[f])},
            'examples': [{'player_id': r.player_id, 'player': names.get(r.player_id), 'season': int(r.season)} for r in examples.itertuples()],
            'classic_examples': [{'player_id': r.player_id, 'player': names.get(r.player_id), 'season': int(r.season)} for r in classic.itertuples()],
            'share_by_decade': {str(int(k)): round(float(v), 4) for k, v in by_decade.items()},
            'rule_based': rid == stretch_id,
        })

    out = {
        'method': {'k': K, 'train_from': TRAIN_FROM, 'min_minutes': MIN_MINUTES, 'features': FEATURES,
                   'feature_labels': FEATURE_LABELS, 'first_season': int(df['season'].min())},
        'archetypes': archetypes,
        'trend': {'seasons': [int(s) for s in seasons], 'shares': trend},
        'columns': ['season', 'player_id', 'archetype_id', 'secondary_id', 'fit', 'features_used', 'mix'],
        'rows': [[int(r.season), r.player_id, int(r.role), int(r.role2), int(r.fit), int(r.features_used), mix_pct[i].tolist()]
                 for i, r in enumerate(df.itertuples())],
        'career_mix': career_mix,
    }
    (DATA / 'archetypes.json').write_text(json.dumps(out, allow_nan=False))
    print(f'{len(df):,} player-seasons ({out["method"]["first_season"]}-{seasons[-1]}) in {len(roles)} roles')
    for a in archetypes:
        sh = a['share_by_decade']
        print(f"  {a['name']:24s} 1980s {sh.get('1980', 0):5.1%}  2020s {sh.get('2020', 0):5.1%}   "
              + ', '.join(f"{e['player']} {e['season']}" for e in a['examples'][:4]))


if __name__ == '__main__':
    main()
