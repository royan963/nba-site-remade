#!/usr/bin/env python3
"""Finals MVP by season -> data/finals_mvp.json.

The winners 1969-2025 are a short public record, entered by hand below (player names) and then CHECKED:
  - each must have been on that season's champion (West 1969 is the one MVP from the losing team),
  - each player's total must equal the official "Nx Finals MVP" count in the Deo Cheng honors table,
  - and where the Deo Cheng playoff-series table marks the award, it must agree.
The newest season(s) come straight from that series table. Needs data/player_titles.json (run prep_playoffs.py first).

Usage: python3 scripts/build_finals_mvp.py <folder with the Deo Cheng slice CSVs>
"""
import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
DC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'data' / 'raw_deocheng'

HAND = {1969: 'Jerry West', 1970: 'Willis Reed', 1971: 'Kareem Abdul-Jabbar', 1972: 'Wilt Chamberlain', 1973: 'Willis Reed', 1974: 'John Havlicek',
        1975: 'Rick Barry', 1976: 'Jo Jo White', 1977: 'Bill Walton', 1978: 'Wes Unseld', 1979: 'Dennis Johnson', 1980: 'Magic Johnson',
        1981: 'Cedric Maxwell', 1982: 'Magic Johnson', 1983: 'Moses Malone', 1984: 'Larry Bird', 1985: 'Kareem Abdul-Jabbar', 1986: 'Larry Bird',
        1987: 'Magic Johnson', 1988: 'James Worthy', 1989: 'Joe Dumars', 1990: 'Isiah Thomas', 1991: 'Michael Jordan', 1992: 'Michael Jordan',
        1993: 'Michael Jordan', 1994: 'Hakeem Olajuwon', 1995: 'Hakeem Olajuwon', 1996: 'Michael Jordan', 1997: 'Michael Jordan', 1998: 'Michael Jordan',
        1999: 'Tim Duncan', 2000: "Shaquille O'Neal", 2001: "Shaquille O'Neal", 2002: "Shaquille O'Neal", 2003: 'Tim Duncan', 2004: 'Chauncey Billups',
        2005: 'Tim Duncan', 2006: 'Dwyane Wade', 2007: 'Tony Parker', 2008: 'Paul Pierce', 2009: 'Kobe Bryant', 2010: 'Kobe Bryant', 2011: 'Dirk Nowitzki',
        2012: 'LeBron James', 2013: 'LeBron James', 2014: 'Kawhi Leonard', 2015: 'Andre Iguodala', 2016: 'LeBron James', 2017: 'Kevin Durant',
        2018: 'Kevin Durant', 2019: 'Kawhi Leonard', 2020: 'LeBron James', 2021: 'Giannis Antetokounmpo', 2022: 'Stephen Curry', 2023: 'Nikola Jokić',
        2024: 'Jaylen Brown', 2025: 'Shai Gilgeous-Alexander'}
LOST_FINAL = {1969}          # Jerry West: MVP of the losing team


def norm(n):
    return ''.join(c for c in unicodedata.normalize('NFD', n) if not unicodedata.combining(c)).lower().replace('.', '').replace("'", '').strip()


def main():
    car = json.loads((DATA / 'player_career.json').read_text())
    c = car['columns']
    players = [dict(zip(c, r)) for r in car['rows']]
    titles = json.loads((DATA / 'player_titles.json').read_text())
    on_champ = {(r[0], r[1]) for r in titles['rows']}
    team_of = {(r[0], r[1]): r[2] for r in titles['rows']}
    series = pd.read_csv(DC / 'public.player_playoffs_series.csv', low_memory=False)
    series = series[series['lg'] == 'NBA']
    marked = series[series['awards'].fillna('').str.contains('Finals MVP')]
    # the series table stores 1947-1999 as 2047-2099, so its recent rows are the only ones with a true year
    marked_recent = {int(r.season_end): r.player_id for r in marked.itertuples() if 2000 <= r.season_end <= 2030}

    out, problems = {}, []
    for season, name in HAND.items():
        cands = [p for p in players if norm(p['player']) == norm(name) and p['first_season'] <= season <= p['last_season']]
        ok = [p for p in cands if (p['player_id'], season) in on_champ] if season not in LOST_FINAL else cands
        if len(ok) != 1:
            problems.append(f'{season} {name}: {len(ok)} candidates matching the champion roster (of {len(cands)} by name)')
            continue
        out[season] = ok[0]['player_id']
        if season in marked_recent and marked_recent[season] != out[season]:
            problems.append(f'{season} {name}: series table says {marked_recent[season]}, not {out[season]}')
    for season, pid in marked_recent.items():
        if season not in out:
            out[season] = pid
    # official counts from the honors table
    h = pd.read_csv(DC / 'public.player_career_honors.csv', low_memory=False)
    h = h[h['honor_raw'].fillna('').str.contains('Finals MVP')]
    official = h.assign(n=h['honor_count'].fillna(1)).groupby('player_id')['n'].sum().astype(int)
    mine = pd.Series(out).value_counts()
    cmp = official.to_frame('official').join(mine.rename('mine')).fillna(0).astype(int)
    bad = cmp[cmp.official != cmp.mine]
    print(f'Finals MVPs: {len(out)} seasons ({min(out)}-{max(out)}); players: {mine.size}; official-count check: '
          f'{len(cmp) - len(bad)} of {len(cmp)} players match exactly')
    if len(bad):
        print('   mismatches (official vs. mine):', bad.to_dict('index'))
    if problems:
        print('PROBLEMS:'); [print('  ', p) for p in problems]
        raise SystemExit(1)
    rows = [[season, pid, team_of.get((pid, season))] for season, pid in sorted(out.items())]
    (DATA / 'finals_mvp.json').write_text(json.dumps({'columns': ['season', 'player_id', 'team'], 'rows': rows}))
    print('wrote data/finals_mvp.json;', [r for r in rows if r[0] >= 2024])


if __name__ == '__main__':
    main()
