#!/usr/bin/env python3
"""Player salaries (1996-97 on) and current contracts (through 2030-31) from the Deo Cheng tables.

Writes:
  data/player_salaries.json   season, player_id, team, salary: what each team paid each player.
                              Through 2024-25 from player_salaries_historical (names only, so
                              matched to Basketball-Reference ids by spelling-proof name, season
                              and team); the current season from the contracts below.
  data/contracts.json         every team's salary sheet as scraped from Basketball-Reference
                              (player ids included): salaries by season with player/team options,
                              guaranteed money, two-way flags and notes, plus that season's cap,
                              tax and apron lines. Rows include money still owed to waived players,
                              so each team's sum equals its official payroll (checked).

Seasons use the site's convention: 2026 = 2025-26.

Usage:  python3 scripts/prep_salaries.py data/raw_deocheng/slice/slice [--review matches.tsv]
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
MULTI = {'2TM', '3TM', '4TM', '5TM', 'TOT'}
SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}
# the salary table's abbreviations -> Basketball-Reference's for that era
ALIASES = {'CHO': ['CHA'], 'CHA': ['CHO'], 'BRK': ['NJN'], 'NJN': ['BRK'], 'NOP': ['NOH'], 'NOH': ['NOP', 'NOK'], 'NOJ': ['NOP'],
           'OKC': ['SEA'], 'SEA': ['OKC']}
REVIEW = None             # --review FILE: write every player matched under a different name, to check by hand
MIN_MATCH = 0.97          # share of salary rows that must match a player, or the script stops
LETTERS = str.maketrans({'ı': 'i', 'İ': 'I', 'ø': 'o', 'Ø': 'O', 'ł': 'l', 'Ł': 'L', 'đ': 'd', 'Đ': 'D', 'ß': 'ss', 'æ': 'ae'})


def name_key(n):
    """'Nikola Jokić', 'Nikola Jokic' and 'Nikola Jokic Jr.' all give 'nikola jokic'."""
    if not isinstance(n, str):
        return None
    n = unicodedata.normalize('NFKD', n.translate(LETTERS))
    n = ''.join(c for c in n if not unicodedata.combining(c)).lower()
    n = re.sub(r"[.,'’]", '', n).replace('-', ' ')
    n = re.sub(r'(?<=[a-z])oe(?=[a-z])', 'o', n)       # German transliteration: Schroeder = Schröder
    toks = [t for t in n.split() if t not in SUFFIXES]
    return ' '.join(toks) if toks else None


# Players known by a different name than the salary table uses (keys as name_key gives them).
NAME_CHANGES = {
    'enes kanter': 'enes freedom', 'nene hilario': 'nene', 'didier ilunga mbenga': 'dj mbenga', 'pooh jeter': 'eugene jeter',
    'anthony barber': 'cat barber', 'jeenathan williams': 'nate williams', 'moe harkless': 'maurice harkless',
    'bj boston': 'brandon boston', 'slava medvedenko': 'stanislav medvedenko', 'slava kravtsov': 'viacheslav kravtsov',
    'guillermo hernangomez': 'willy hernangomez', 'luigi datome': 'gigi datome', 'michael sweetney': 'mike sweetney',
}


def same_first_name(a, b):
    """Patrick/Patty, Herb/Herbert, Darrel/Darrell, Victor/Viktor: yes. Brandon/Ben, Pat/Matt: no."""
    from difflib import SequenceMatcher
    return (min(len(a), len(b)) >= 3 and a[:3] == b[:3]) or SequenceMatcher(None, a, b).ratio() >= 0.8


def fix_text(n):
    """Undo UTF-8 read as Latin-1 ('JokiÄ\u0087' -> 'Jokić'), which some scraped names have."""
    if isinstance(n, str) and any(ch in n for ch in 'ÃÄÅÆ'):
        try:
            return n.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return n


def season_of(label):
    """'2025-26' -> 2026"""
    return int(label[:4]) + 1


def frame(name):
    d = json.loads((DATA / f'{name}.json').read_text(encoding='utf-8'))
    return pd.DataFrame(d['rows'], columns=d['columns'])


def dump(obj, name):
    (DATA / f'{name}.json').write_text(json.dumps(obj, allow_nan=False))


def contracts(src: Path):
    c = pd.read_csv(src / 'public.player_contracts.csv')
    site_names = frame('player_career').set_index('player_id')['player']
    c['player_name'] = [site_names.get(pid, fix_text(n)) for pid, n in zip(c['player_id'], c['player_name'])]
    base = season_of(c['season'].iloc[0])
    years = [col for col in c.columns if re.fullmatch(r'salary_\d{4}_\d{2}', col)]

    payroll_file = src / 'public.team_payroll.csv'
    if payroll_file.exists():                      # every team's sheet must add up to its official payroll
        tp = pd.read_csv(payroll_file).set_index('team_abbr')
        sums = c.groupby('team_abbr')[years[0]].sum()
        off = (sums.reindex(tp.index).fillna(0) - tp[f'total_{years[0][7:]}']).abs()
        if (off > 1).any():
            sys.exit(f'contract sheets don’t add up to team payrolls: {off[off > 1].to_dict()}')

    rows, details = [], []
    for r in c.itertuples(index=False):
        for col in years:
            v = getattr(r, col)
            if pd.notna(v):
                opt = getattr(r, 'opt_' + col[7:], None)
                rows.append([r.player_id, r.team_abbr, season_of(col[7:11] + '-' + col[12:]), int(v),
                             opt if isinstance(opt, str) else None])
        notes = json.loads(r.notes) if isinstance(r.notes, str) and r.notes.startswith('[') else []
        details.append([r.player_id, r.team_abbr, r.player_name, None if pd.isna(r.guaranteed) else int(r.guaranteed),
                        str(r.is_two_way).lower() in ('t', 'true'), notes])

    rules = {}
    rules_file = src / 'public.league_salary_rules.csv'
    if rules_file.exists():
        lr = pd.read_csv(rules_file)
        lr = lr[lr['league'] == 'NBA']
        for r in lr.itertuples(index=False):
            rules[season_of(r.season)] = {k: int(getattr(r, k)) for k in ('salary_cap', 'luxury_tax', 'first_apron', 'second_apron', 'minimum_team_salary')
                                          if pd.notna(getattr(r, k))}
    as_of = str(c['scraped_at'].max())[:10]
    print(f'contracts: {c["player_id"].nunique()} players on {c["team_abbr"].nunique()} teams, {base}-{base + len(years) - 1}, as of {as_of}')
    return base, as_of, rules, rows, details


def history(src: Path, until: int):
    s = pd.read_csv(src / 'public.player_salaries_historical.csv')
    s['player_name'] = s['player_name'].map(fix_text)
    s = s[s['season'] < until].copy()
    ps = frame('player_seasons')
    ps['key'] = ps['player'].map(name_key)
    stints = ps[~ps['team'].isin(MULTI)]
    by_season = stints.groupby(['season', 'key'])['player_id'].unique()
    teams_of = stints.groupby(['season', 'player_id'])['team'].apply(set)
    career = frame('player_career')
    career['key'] = career['player'].map(name_key)
    valid = set(zip(frame('team_geo')['season'], frame('team_geo')['abbr']))

    roster = stints.assign(toks=stints['key'].str.split())
    roster = {k: g for k, g in roster.groupby(['season', 'team'])}
    modern = career[career['last_season'] >= s['season'].min() - 1]
    unique_name = modern.groupby('key')['player_id'].unique()

    def match(season, key, team):
        """Each step only accepts exactly one candidate."""
        teams = {team, *ALIASES.get(team, [])}
        ids = by_season.get((season, key))
        if ids is not None:
            if len(ids) == 1:
                return ids[0]
            hit = [i for i in ids if teams_of.get((season, i), set()) & teams]
            return hit[0] if len(hit) == 1 else None
        # paid in a season he didn't play (injured, waived, still owed money)
        c = career[(career['key'] == key) & (career['first_season'] <= season + 1) & (career['last_season'] >= season - 1)]
        if c['player_id'].nunique() == 1:
            return c['player_id'].iloc[0]
        ids = unique_name.get(key)
        if ids is not None and len(ids) == 1:
            return ids[0]
        if key in NAME_CHANGES:
            return match(season, NAME_CHANGES[key], team)
        # a nickname or spelling (Patrick/Patty Mills, Darrel/Darrell Armstrong, Roko-Leni/Roko Ukic): someone
        # on that team that season with the same last name and a first name that looks like the same name.
        # Teammates who merely share a last name (Kennedy and Jodie Meeks) don't count.
        toks = key.split() if key else []
        if len(toks) < 2:
            return None
        hits = set()
        for t in teams:
            g = roster.get((season, t))
            if g is not None:
                for pid, ptoks in zip(g['player_id'], g['toks']):
                    if len(ptoks) >= 2 and set(toks[1:]) & set(ptoks[1:]) and same_first_name(toks[0], ptoks[0]):
                        hits.add(pid)
        return hits.pop() if len(hits) == 1 else None

    def team_for(season, pid, team):
        for t in (team, *ALIASES.get(team, [])):
            if (season, t) in valid:
                return t
        own = sorted(teams_of.get((season, pid), set()))
        return own[0] if len(own) == 1 else None

    s['key'] = s['player_name'].map(name_key)
    s['player_id'] = [match(a, b, c) for a, b, c in zip(s['season'], s['key'], s['team_abbr'])]
    rate = s['player_id'].notna().mean()
    print(f'salary history: matched {s["player_id"].notna().sum():,} of {len(s):,} rows ({rate:.1%}) to players')
    missed = s[s['player_id'].isna()]
    if len(missed):
        print('  unmatched, e.g.:', ', '.join(f'{r.player_name} {r.season}' for r in missed.head(8).itertuples()))
    if rate < MIN_MATCH:
        sys.exit(f'only {rate:.1%} of salary rows matched a player (need {MIN_MATCH:.0%}); nothing was written')
    names = career.set_index('player_id')['player']
    renamed = s[s['player_id'].notna()].assign(site=lambda x: x['player_id'].map(names))
    renamed = renamed[renamed['site'].map(name_key) != renamed['key']].drop_duplicates(['player_name', 'player_id'])
    print(f'  {len(renamed)} players matched under a different name, e.g.:',
          ', '.join(f'{r.player_name} = {r.site}' for r in renamed.head(6).itertuples()))
    if REVIEW:
        Path(REVIEW).write_text('\n'.join(f'{r.season}\t{r.team_abbr}\t{r.player_name}\t{r.site}\t{r.player_id}' for r in renamed.itertuples()),
                                encoding='utf-8')
    s = s.dropna(subset=['player_id'])
    s['team'] = [team_for(a, b, c) for a, b, c in zip(s['season'], s['player_id'], s['team_abbr'])]
    no_team = s['team'].isna()
    if no_team.any():                     # e.g. a G League or defunct abbreviation for a player with no NBA stint that season
        print(f'  {no_team.sum()} rows dropped: no NBA team that season, e.g.', ', '.join(f'{r.player_name} {r.team_abbr} {r.season}' for r in s[no_team].head(4).itertuples()))
        s = s[~no_team]
    dupes = s.duplicated(['season', 'player_id', 'team'], keep=False)
    if dupes.any():                        # two salary rows matched the same player-team: keep the larger, it's the same contract
        s = s.sort_values('salary', ascending=False).drop_duplicates(['season', 'player_id', 'team'])
    return [[int(r.season), r.player_id, r.team, int(r.salary)] for r in s.sort_values(['season', 'player_id']).itertuples()]


def main():
    global REVIEW
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    REVIEW = sys.argv[sys.argv.index('--review') + 1] if '--review' in sys.argv else None
    base, as_of, rules, rows, details = contracts(src)
    paid = history(src, base)
    known = set(frame('player_career')['player_id'])
    current = [[season, pid, team, salary] for pid, team, season, salary, _ in rows if season == base and pid in known]
    dump({'columns': ['season', 'player_id', 'team', 'salary'], 'rows': paid + current}, 'player_salaries')
    print(f'player_salaries.json: {len(paid) + len(current):,} rows, {min(r[0] for r in paid)}-{base}')
    dump({'season': base, 'as_of': as_of, 'rules': rules,
          'columns': ['player_id', 'team', 'season', 'salary', 'option'], 'rows': rows,
          'detail_columns': ['player_id', 'team', 'player', 'guaranteed', 'two_way', 'notes'], 'details': details}, 'contracts')
    print(f'contracts.json: {len(rows):,} salary rows, {len(details)} contracts')


if __name__ == '__main__':
    main()

