#!/usr/bin/env python3
"""NBA.com ids for the site's players and franchises, so pages can show official headshots.

The site uses Basketball-Reference ids (jamesle01); NBA.com uses numbers (LeBron is 2544). The eoinamoore box scores
(data/raw_eoin/, downloaded by update_season.py) carry NBA ids for every player-game since 1946, so:

  players: a player's spelling-proof name (prep_games_eoin.name_key) plus the seasons he played on both sides. The
           NBA person with that name whose seasons overlap the most is him; a tie is left unmatched rather than guessed.
           This season's provisional rookies already know their NBA id (data/new_players.json).
  teams:   each game is matched by date and final score to the site's game files, which gives the NBA team id of every
           franchise (ids follow the franchise through moves and renames: the Nets keep theirs from New Jersey).

Writes data/nba_ids.json. Usage:  python3 scripts/prep_nba_ids.py [data/raw_eoin]
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prep_games_eoin import name_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
TEAM_SEASONS_FROM = 2015          # the seasons with per-season headshots (2014-15 on); also plenty to learn every franchise's id


def season_of(dates: pd.Series) -> pd.Series:
    d = pd.to_datetime(dates.astype(str).str[:10], errors='coerce')
    return (d.dt.year + (d.dt.month >= 8)).astype('Int64')          # 2026-10 -> 2027 (the season named by its last year)


def frame(name):
    d = json.loads((DATA / f'{name}.json').read_text(encoding='utf-8'))
    return pd.DataFrame(d['rows'], columns=d['columns'])


def match_players(folder: Path) -> tuple[dict, dict]:
    ps = pd.read_csv(folder / 'PlayerStatistics.csv', usecols=['personId', 'firstName', 'lastName', 'gameDateTimeEst'], low_memory=False)
    ps['season'] = season_of(ps['gameDateTimeEst'])
    ps['key'] = (ps['firstName'].fillna('') + ' ' + ps['lastName'].fillna('')).map(name_key)
    nba = ps.dropna(subset=['key', 'season']).groupby(['key', 'personId'])['season'].agg(lambda s: set(int(x) for x in s)).reset_index()
    by_key, by_last = defaultdict(list), defaultdict(list)
    for r in nba.itertuples(index=False):
        by_key[r.key].append((int(r.personId), r.season))
        toks = r.key.split()
        if len(toks) >= 2:
            by_last[toks[-1]].append((toks[0], int(r.personId), r.season))

    ours = frame('player_seasons')[['player_id', 'player', 'season']]
    stubs = json.loads((DATA / 'new_players.json').read_text(encoding='utf-8')) if (DATA / 'new_players.json').exists() else {}
    ids = {pid: int(src['person_id']) for pid, src in (stubs.get('source') or {}).items() if src.get('person_id')}
    stats = Counter(from_rookie_list=len(ids))
    seasons = ours.groupby('player_id')['season'].agg(lambda s: set(int(x) for x in s))
    names = ours.sort_values('season').groupby('player_id')['player'].last()
    taken = Counter()
    exact = {}
    for pid, mine in seasons.items():
        if pid in ids:
            continue
        c = sorted(((len(mine & theirs), person) for person, theirs in by_key.get(name_key(names[pid]) or '', [])), reverse=True)
        c = [x for x in c if x[0] > 0]
        if c and (len(c) == 1 or c[0][0] > c[1][0]):
            exact[pid] = c[0][1]
    claimed = set(exact.values())          # provisional ids (already in ids) never block an official player
    for pid, mine in seasons.items():
        if pid in ids:
            continue
        key = name_key(names[pid]) or ''
        cands = [(len(mine & theirs), person) for person, theirs in by_key.get(key, [])]
        cands = sorted((c for c in cands if c[0] > 0), reverse=True)
        if not cands and len(key.split()) >= 2:
            # a short first name on one side (Basketball-Reference's "Ron Holland" is NBA.com's "Ronald Holland II"):
            # same surname, one first name the start of the other (3+ letters), seasons overlapping, and only one such person
            first, last = key.split()[0], key.split()[-1]
            short = [(len(mine & theirs), person) for f, person, theirs in by_last.get(last, [])
                     if min(len(f), len(first)) >= 3 and (f.startswith(first) or first.startswith(f)) and f != first
                     and person not in claimed]
            # most of his seasons must be shared: a partial overlap is usually a different player with a similar name
            short = sorted((c for c in short if c[0] >= max(1, 0.6 * len(mine))), reverse=True)
            if len(short) == 1 or (len(short) > 1 and short[0][0] > short[1][0] and len({p for _, p in short}) == len(short)):
                cands = short[:1]
                stats['matched_by_short_first_name'] += 1
        if not cands:
            stats['no_match'] += 1
            continue
        if len(cands) > 1 and cands[0][0] == cands[1][0]:
            stats['tie_left_unmatched'] += 1
            continue
        ids[pid] = cands[0][1]
        taken[cands[0][1]] += 1
        stats['matched_by_name_and_seasons'] += 1
    # one NBA person can't be two of our players: drop both sides of any clash rather than guess
    clashes = {person for person, n in taken.items() if n > 1}
    if clashes:
        ids = {k: v for k, v in ids.items() if v not in clashes}
        stats['dropped_clashes'] = len(clashes)
    # a provisional id for someone who already has an official one (a veteran back after time away): the official one wins
    stub_ids = set((stubs.get('source') or {}))
    official_people = {v for k, v in ids.items() if k not in stub_ids}
    dup = [k for k in stub_ids if k in ids and ids[k] in official_people]
    for k in dup:
        del ids[k]
    if dup:
        stats['provisional_duplicates'] = sorted(dup)
    recent = set(ours.loc[ours['season'] >= TEAM_SEASONS_FROM, 'player_id'])
    stats['recent_players'] = len(recent)
    stats['recent_matched'] = len(recent & set(ids))
    return ids, dict(stats)


def match_teams(folder: Path) -> dict:
    g = pd.read_csv(folder / 'Games.csv', usecols=['gameDateTimeEst', 'hometeamId', 'homeScore', 'awayScore'], low_memory=False)
    g['date'] = g['gameDateTimeEst'].astype(str).str[:10]
    geo = frame('team_geo')[['season', 'abbr', 'franchise']]
    votes = defaultdict(Counter)
    for f in sorted((DATA / 'games').glob('games_*.csv.gz')):
        season = int(f.name.split('_')[1].split('.')[0])
        if season < TEAM_SEASONS_FROM:
            continue
        ours = pd.read_csv(f, usecols=['date', 'home', 'home_pts', 'away_pts'])
        ours['date'] = ours['date'].astype(str).str[:10]
        m = ours.merge(g, left_on=['date', 'home_pts', 'away_pts'], right_on=['date', 'homeScore', 'awayScore'])
        franchise = dict(zip(geo.loc[geo['season'] == season, 'abbr'], geo.loc[geo['season'] == season, 'franchise']))
        for home, team_id in zip(m['home'], m['hometeamId']):
            if home in franchise:
                votes[franchise[home]][int(team_id)] += 1
    out = {}
    for fr, c in votes.items():
        (best, n), = c.most_common(1)
        if n >= 0.9 * sum(c.values()):                # a clear majority: score coincidences between games can't decide it
            out[fr] = best
    return out


def main():
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA / 'raw_eoin'
    if not (folder / 'PlayerStatistics.csv').exists():
        sys.exit(f'{folder} has no PlayerStatistics.csv (it comes from the eoinamoore dataset; see update_season.py)')
    players, stats = match_players(folder)
    teams = match_teams(folder)
    out = {'players': dict(sorted(players.items())), 'teams': dict(sorted(teams.items())), 'stats': stats}
    (DATA / 'nba_ids.json').write_text(json.dumps(out, indent=0, sort_keys=False) + '\n', encoding='utf-8')
    print(f"nba_ids.json: {len(players):,} players ({stats['recent_matched']:,} of {stats['recent_players']:,} who played since "
          f"{TEAM_SEASONS_FROM - 1}-{str(TEAM_SEASONS_FROM)[2:]}), {len(teams)} franchises; {stats}")
    if len(teams) < 30:
        sys.exit(f'only {len(teams)} franchises got an NBA id (expected 30)')


if __name__ == '__main__':
    main()
