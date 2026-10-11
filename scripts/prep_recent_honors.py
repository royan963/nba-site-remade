#!/usr/bin/env python3
"""Add award voting and All-NBA/Defense/Rookie teams for seasons the main dataset doesn't have yet.

The Basketball-Reference dataset behind prep_data.py can lag a season behind on
awards (it had 2025-26 stats but not 2025-26 MVP voting). The Deo Cheng
database carries the same Basketball-Reference tables, so seasons missing from
data/player_award_shares.json and data/player_eos_teams.json are filled from
it. Seasons already there are never changed.

Before adding anything, the seasons both sources cover are compared row by
row; any disagreement stops the script, so a changed source can't slip in.

Usage:  python3 scripts/prep_recent_honors.py data/raw_deocheng/slice/slice
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
LEAGUES = ['NBA', 'BAA']
TEAM_NUMBERS = ['1st', '2nd', '3rd']        # leaves out 'ORV' (others receiving votes) and ties
CHECK_SEASONS = 3                           # overlapping seasons compared before trusting the source


def load(name):
    d = json.loads((DATA / f'{name}.json').read_text())
    return d, pd.DataFrame(d['rows'], columns=d['columns'])


def save(d, name, added):
    (DATA / f'{name}.json').write_text(json.dumps(d, allow_nan=False))
    print(f'{name}.json: {len(d["rows"])} rows ({added} added)')


def check(label, ours: set, theirs: set):
    if ours != theirs:
        sys.exit(f'{label}: the two sources disagree on {len(ours ^ theirs)} rows, e.g. {sorted(ours ^ theirs, key=str)[:3]}. '
                 'Nothing was changed.')


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])

    # ---- award voting
    aw_json, aw = load('player_award_shares')
    dc = pd.read_csv(src / 'public.player_award_shares.csv', low_memory=False)
    dc = dc[dc['player_id'].notna()].assign(winner=lambda x: x['winner'].astype(str).str.lower().isin(['t', 'true', '1']))
    have = set(aw['season'])
    key = lambda df: {(int(r.season), r.award, r.player_id, round(float(r.share), 3), bool(r.winner)) for r in df.itertuples()}
    for s in sorted(have & set(dc['season']))[-CHECK_SEASONS:]:
        check(f'{s} award voting', key(aw[aw['season'] == s]), key(dc[dc['season'] == s]))
    new = dc[~dc['season'].isin(have)].sort_values(['season', 'award', 'share'], ascending=[True, True, False])
    aw_json['rows'] += [[int(r.season), r.award, r.player_id, round(float(r.share), 3), bool(r.winner)] for r in new.itertuples()]
    save(aw_json, 'player_award_shares', len(new))
    for r in new[new['winner']].itertuples():
        print(f'  {r.season} {r.award}: {r.player_id}')

    # ---- All-NBA / All-Defense / All-Rookie teams
    eos_json, eos = load('player_eos_teams')
    dc = pd.read_csv(src / 'public.end_of_season_teams.csv', low_memory=False)
    dc = dc[dc['lg'].isin(LEAGUES) & dc['number_tm'].isin(TEAM_NUMBERS) & dc['type'].isin(set(eos['team_type'])) & dc['player_id'].notna()]
    have = set(eos['season'])
    key = lambda df, t, n: {(int(r[0]), r[1], r[2], r[3]) for r in df[['season', t, n, 'player_id']].itertuples(index=False)}
    for s in sorted(have & set(dc['season']))[-CHECK_SEASONS:]:
        check(f'{s} season teams', key(eos[eos['season'] == s], 'team_type', 'team_number'), key(dc[dc['season'] == s], 'type', 'number_tm'))
    new = dc[~dc['season'].isin(have)].sort_values(['season', 'type', 'number_tm'])
    eos_json['rows'] += [[int(r.season), r.type, r.number_tm, r.player_id] for r in new.itertuples()]
    save(eos_json, 'player_eos_teams', len(new))


if __name__ == '__main__':
    main()
