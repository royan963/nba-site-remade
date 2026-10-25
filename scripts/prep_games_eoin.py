#!/usr/bin/env python3
"""Fill gaps in data/games and add the current season from the eoinamoore dataset.

Source: https://www.kaggle.com/datasets/eoinamoore/historical-nba-data-and-player-box-scores (updated daily; Games.csv and
PlayerStatistics.csv). Put both files in data/raw_eoin/ (gitignored) or pass the folder.

What it does (per season file in data/games/, labeled by the year the season ends):
  - adds games the existing files lack: seasons 2025 and 2026 (any game not already there) and every game of 2027 so far;
  - never changes a row that is already there, and never adds preseason or All-Star games;
  - a game is skipped if the same teams and score already exist within two days (a date-shifted copy);
  - player rows are written only for games whose player points add up to both final scores. Players are matched to
    Basketball-Reference ids by name (accents and Jr./III ignored) and by that season's team; a name that fits two players is
    left out, so a game missing a rookie or an ambiguous name is saved as incomplete with no player rows.
Added rows carry src = 'eoin'. Play-in games count as regular season, like the existing files.

Usage:  python3 scripts/prep_games_eoin.py [path/to/folder]      (default data/raw_eoin)
"""
import gzip
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
OUT = DATA / 'games'
FILL_SEASONS = (2025, 2026)          # seasons filled in; later seasons are added whole
FIRST_NEW_SEASON = 2027
KEEP_TYPES = {'Regular Season', 'Playoffs', 'Play-in Tournament', 'NBA Emirates Cup', 'Emirates NBA Cup', 'NBA Cup', 'in-season-knockout'}
STATS = ['fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts']
PG_COLS = ['game_ref', 'player_id', 'team', 'started', 'mp'] + STATS + ['pm', 'src']
GAME_COLS = ['game_ref', 'season', 'date', 'home', 'away', 'home_pts', 'away_pts', 'ot', 'playoffs', 'series', 'src', 'complete', 'kind']
FIRST_KIND_SEASON = 2020        # play-in games began with 2019-20; every season file from here has a `kind` column
SRC_COLS = {'fieldGoalsMade': 'fg', 'fieldGoalsAttempted': 'fga', 'threePointersMade': 'x3p', 'threePointersAttempted': 'x3pa',
            'freeThrowsMade': 'ft', 'freeThrowsAttempted': 'fta', 'reboundsOffensive': 'orb', 'reboundsDefensive': 'drb',
            'reboundsTotal': 'trb', 'assists': 'ast', 'steals': 'stl', 'blocks': 'blk', 'turnovers': 'tov', 'foulsPersonal': 'pf',
            'points': 'pts', 'plusMinusPoints': 'pm'}
SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}
SRC = 'eoin'


# ------------------------------------------------------------------ small helpers
def game_season(game_id):
    """NBA game ids are type + season start year + number: 22600005 is 2026-27, which this project labels 2027."""
    yy = int(str(int(game_id)).zfill(8)[1:3])
    return (yy + 2000 if yy < 40 else yy + 1900) + 1


def minutes_to_float(v):
    if isinstance(v, str) and ':' in v:
        m, s = v.split(':')[:2]
        return int(m) + int(s) / 60
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def ot_from_minutes(team_minutes):
    """A regulation game is 240 team minutes; each overtime adds 25."""
    if team_minutes is None or (isinstance(team_minutes, float) and np.isnan(team_minutes)):
        return None
    return max(int(round((float(team_minutes) - 240) / 25)), 0)


def game_ref(date, home):
    return f'{str(date).replace("-", "")}0{home}'


def keep_game_type(t):
    return t in KEEP_TYPES


def game_kind(game_id):
    """regular | playoffs | play_in | cup_final, from the first digit of the NBA game id (2, 4, 5, 6). Preseason (1) and All-Star (3) give None.
    The NBA counts neither play-in games nor the Cup championship game in regular-season stats or records."""
    return {'2': 'regular', '4': 'playoffs', '5': 'play_in', '6': 'cup_final'}.get(str(int(game_id)).zfill(8)[0])


def tag_kinds(games, special):
    """Set `kind` on every game: playoffs / regular by the existing flag, then play_in and cup_final where `special`
    (columns date, home, away, kind) has the same date and the same two teams."""
    games = games.copy()
    games['kind'] = np.where(games['playoffs'].astype(bool), 'playoffs', 'regular')
    sp = {(r.date, frozenset((r.home, r.away))): r.kind for r in special.itertuples()}
    tagged = [sp.get((d, frozenset((h, a)))) for d, h, a in zip(games['date'], games['home'], games['away'])]
    games['kind'] = [t or k for t, k in zip(tagged, games['kind'])]
    return games


def is_playoffs(t):
    return t == 'Playoffs'


def name_key(n):
    """Spelling-proof player name: accents, punctuation and Jr./III are dropped."""
    if not isinstance(n, str):
        return None
    n = unicodedata.normalize('NFKD', n.replace('е', 'e'))
    n = ''.join(c for c in n if not unicodedata.combining(c)).lower()
    n = re.sub(r"[.,'’]", '', n).replace('-', ' ')
    toks = [t for t in n.split() if t not in SUFFIXES]
    return ' '.join(toks) if toks else None


PLAY_STATS = ['points', 'fieldGoalsAttempted', 'freeThrowsAttempted', 'reboundsTotal', 'assists', 'steals', 'blocks', 'turnovers', 'foulsPersonal']


def played_mask(df):
    """Rows of players who played: minutes above zero, or minutes left blank but some real stat recorded (the source leaves
    minutes blank for every player in a few games, and the points still add up)."""
    stats = df[PLAY_STATS].apply(pd.to_numeric, errors='coerce').fillna(0)
    return (df['mp'].fillna(0) > 0) | (df['mp'].isna() & (stats.abs().sum(axis=1) > 0))


def team_from_home_flag(home, home_abbr, away_abbr):
    """Team of each player row from the source's home flag (1 = home team). The team-id column is empty for some rows."""
    return pd.Series(np.where(pd.Series(home).astype(float) == 1, home_abbr, away_abbr), index=pd.Series(home).index)


def drop_pending(games, pg):
    """Remove games this source added earlier that were incomplete (and their rows), so the next run can redo them."""
    pending = set(games.loc[(games['src'] == SRC) & ~games['complete'].astype(bool), 'game_ref'])
    return games[~games['game_ref'].isin(pending)], pg[~pg['game_ref'].isin(pending)]


STUBS_FILE = 'new_players.json'
CAREER_COLS = ['player_id', 'player', 'pos', 'hof', 'ht_in_in', 'wt', 'seasons_played', 'first_season', 'last_season', 'g', 'pts', 'trb', 'ast', 'stl', 'blk',
               'fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'ppg', 'rpg', 'apg', 'ws', 'vorp', 'all_star']


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


def bbref_id(first, last, taken):
    """Basketball-Reference's id pattern: first five letters of the last name, first two of the first name, then 01, 02, ...
    (the first number not already taken)."""
    def letters(s, n):
        s = unicodedata.normalize('NFKD', str(s or '').replace('ø', 'o').replace('ł', 'l').replace('đ', 'd'))
        return re.sub('[^a-z]', '', ''.join(c for c in s if not unicodedata.combining(c)).lower())[:n]
    base = letters(last, 5) + letters(first, 2)
    n = 1
    while f'{base}{n:02d}' in taken:
        n += 1
    return f'{base}{n:02d}'


def position_from_flags(guard, forward, center):
    """G, F, C or a pair (G-F, F-C, G-C) from the source's position flags; None if it gives none."""
    g, f, c = (bool(_num(x) == 1) for x in (guard, forward, center))
    name = '-'.join(p for p, on in (('G', g), ('F', f), ('C', c)) if on)
    return name or None


def age_on(birth, season):
    """Age on February 1 of the season's ending year, which is how Basketball-Reference lists a season's age."""
    b = pd.to_datetime(birth, errors='coerce') if birth is not None else pd.NaT
    if pd.isna(b):
        return None
    return season - b.year - ((2, 1) < (b.month, b.day))


def provisional_player(person, totals, player_id, team, season):
    """A career row and a season row, in the site's formats, for a player the official table doesn't have yet."""
    first, last = str(person.get('firstName') or '').strip(), str(person.get('lastName') or '').strip()
    pos = position_from_flags(person.get('guard'), person.get('forward'), person.get('center'))
    g = int(totals['g'])
    per = lambda v: round(v / g, 1) if g else None
    pct = lambda made, att: round(made / att, 4) if att else None
    ht, wt = _num(person.get('heightInches')), _num(person.get('bodyWeightLbs'))
    t = {k: (int(totals[k]) if k not in ('mp',) else float(totals[k])) for k in totals}
    career = {'player_id': player_id, 'player': f'{first} {last}'.strip(), 'pos': pos, 'hof': False,
              'ht_in_in': None if ht is None else int(ht), 'wt': None if wt is None else int(wt),
              'seasons_played': 1, 'first_season': season, 'last_season': season, 'g': g, 'pts': t['pts'], 'trb': t['trb'], 'ast': t['ast'],
              'stl': t['stl'], 'blk': t['blk'], 'fg': t['fg'], 'fga': t['fga'], 'x3p': t['x3p'], 'x3pa': t['x3pa'], 'ft': t['ft'], 'fta': t['fta'],
              'ppg': per(t['pts']), 'rpg': per(t['trb']), 'apg': per(t['ast']), 'ws': None, 'vorp': None, 'all_star': 0}
    season_row = {'season': season, 'player_id': player_id, 'player': career['player'], 'age': age_on(person.get('birthDate'), season), 'team': team,
                  'pos': pos, 'g': g, 'gs': t['gs'], 'mp': per(t['mp']), 'pts': per(t['pts']), 'trb': per(t['trb']), 'ast': per(t['ast']),
                  'stl': per(t['stl']), 'blk': per(t['blk']), 'fg_pct': pct(t['fg'], t['fga']), 'x3p_pct': pct(t['x3p'], t['x3pa']),
                  'ft_pct': pct(t['ft'], t['fta']), 'x3pa': per(t['x3pa']), 'fta': per(t['fta'])}
    return career, season_row


def reconcile_stubs(stubs, official):
    """Provisional players once the official table has caught up. Returns (stubs to keep, {provisional id: official id}).
    A provisional player is dropped if the official table has that id, and remapped if a player who has played in the
    newest season carries the same name under another id. An older namesake never counts."""
    ids = {o['player_id'] for o in official}
    recent = {}
    for o in official:
        if (o.get('last_season') or 0) >= FIRST_NEW_SEASON:
            recent.setdefault(name_key(o['player']), []).append(o['player_id'])
    keep, remap = [], {}
    for s in stubs:
        if s['player_id'] in ids:
            continue
        hits = recent.get(name_key(s['player']), [])
        if len(hits) == 1:
            remap[s['player_id']] = hits[0]
        else:
            keep.append(s)
    return keep, remap


def apply_remap(remap):
    """Rewrite player ids in the newest seasons' player-game files after a provisional player became an official one."""
    if not remap:
        return
    for f in sorted(OUT.glob('player_games_*.csv.gz')):
        if int(f.name.split('_')[2].split('.')[0]) < FIRST_NEW_SEASON:
            continue
        pg = pd.read_csv(f)
        if pg['player_id'].isin(list(remap)).any():
            write_season(int(f.name.split('_')[2].split('.')[0]), None, pg.assign(player_id=pg['player_id'].replace(remap)))


def read_stubs():
    f = DATA / STUBS_FILE
    return json.loads(f.read_text(encoding='utf8')) if f.exists() else {'players': [], 'seasons': [], 'source': {}}


def stub_totals(rows):
    """Season totals for one player from his regular-season game rows (the columns of PlayerStatistics, already renamed)."""
    return {'g': len(rows), 'gs': int(rows['started'].sum()), 'mp': float(rows['mp'].sum()),
            **{k: int(rows[k].fillna(0).sum()) for k in ('pts', 'trb', 'ast', 'stl', 'blk', 'fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta')}}


def is_duplicate(game, existing):
    """True if `existing` (columns date, home, away, home_pts, away_pts) has the same teams and score within two days."""
    if existing is None or len(existing) == 0:
        return False
    d = pd.to_datetime(game['date'])
    near = existing[(existing['home'] == game['home']) & (existing['away'] == game['away'])
                    & (existing['home_pts'] == game['home_pts']) & (existing['away_pts'] == game['away_pts'])]
    return bool(((pd.to_datetime(near['date']) - d).abs() <= pd.Timedelta(days=2)).any())


def complete_flags(games, pg):
    """game_ref -> both teams' player points equal the final score."""
    sums = pg.groupby(['game_ref', 'team'])['pts'].sum()
    out = {}
    for r in games.itertuples():
        out[r.game_ref] = bool(sums.get((r.game_ref, r.home)) == r.home_pts and sums.get((r.game_ref, r.away)) == r.away_pts)
    return pd.Series(out)


# ------------------------------------------------------------------ team and player matching
def learn_team_abbrs(new, existing):
    """NBA team id -> Basketball-Reference abbreviation, from games both sources have (same date and final score)."""
    existing = existing.dropna(subset=['home_pts', 'away_pts'])
    a = existing.assign(key=existing['date'] + '|' + existing['home_pts'].astype(int).astype(str) + '|' + existing['away_pts'].astype(int).astype(str))
    n = new.assign(key=new['date'] + '|' + new['homeScore'].astype(int).astype(str) + '|' + new['awayScore'].astype(int).astype(str))
    a = a[~a['key'].duplicated(keep=False)]
    n = n[~n['key'].duplicated(keep=False)]
    m = a.merge(n, on='key', suffixes=('_o', '_n'))
    votes = pd.concat([m[['hometeamId', 'home']].set_axis(['tid', 'abbr'], axis=1), m[['awayteamId', 'away']].set_axis(['tid', 'abbr'], axis=1)])
    return votes.groupby('tid')['abbr'].agg(lambda s: s.mode()[0]).to_dict()


def player_index(season_rows):
    """Lookups from this project's own season data: (name key, team, season) -> id, and name key -> ids of recent players."""
    ps = pd.DataFrame(season_rows['rows'], columns=season_rows['columns'])
    ps = ps[~ps['team'].isin(['2TM', '3TM', '4TM', '5TM'])].copy()
    ps['key'] = ps['player'].map(name_key)
    by_team = {}
    for (k, t, s), g in ps.groupby(['key', 'team', 'season']):
        ids = set(g['player_id'])
        if len(ids) == 1:
            by_team[(k, t, int(s))] = next(iter(ids))
    recent = ps[ps['season'] >= max(FILL_SEASONS) - 1]
    by_name = {k: set(g['player_id']) for k, g in recent.groupby('key')}
    ps['last'] = ps['key'].map(lambda k: k.split()[-1] if isinstance(k, str) and k else None)
    by_last = {}                                          # (last name, team, season) -> id, only when one player has it
    for (last, t, s), g in ps.groupby(['last', 'team', 'season']):
        ids = set(g['player_id'])
        if len(ids) == 1:
            by_last[(last, t, int(s))] = next(iter(ids))
    return by_team, by_name, by_last


def resolve_player(key, team, season, by_team, by_name, by_last=None):
    """The id for a name on a team in a season. Tried in order, each only when it gives exactly one player:
    the name on that team that season; the same name written the other way round (Basketball-Reference has 'Yang Hansen', the
    new dataset 'Hansen Yang'); a nickname or short first name (Ronald/Ron Holland) by last name on that team that season;
    and, for a season we have no player data for, the one recent player with that name (either order)."""
    flipped = ' '.join(reversed(key.split())) if key and len(key.split()) == 2 else None
    hit = by_team.get((key, team, season)) or (by_team.get((flipped, team, season)) if flipped else None)
    if hit:
        return hit
    if by_last and key:
        hit = by_last.get((key.split()[-1], team, season))
        if hit:
            return hit
    for k in (key, flipped):
        ids = by_name.get(k, set()) if k else set()
        if len(ids) == 1:
            return next(iter(ids))
    return None


# ------------------------------------------------------------------ build
def load_new(folder):
    games = pd.read_csv(folder / 'Games.csv', low_memory=False)
    games['date'] = games['gameDate'].astype(str).str[:10]
    games['season'] = games['gameId'].map(game_season)
    games = games[games['gameType'].map(keep_game_type)].copy()
    games = games[games['homeScore'].notna() & games['awayScore'].notna()]
    use = sorted({'gameId', 'personId', 'firstName', 'lastName', 'home', 'numMinutes', 'startingPosition'} | set(SRC_COLS) | set(PLAY_STATS))
    ps = pd.read_csv(folder / 'PlayerStatistics.csv', usecols=use, low_memory=False)
    ps = ps[ps['gameId'].isin(games['gameId'])].copy()
    ps['mp'] = ps['numMinutes'].map(minutes_to_float)
    return games, ps


def read_season(season):
    g, p = OUT / f'games_{season}.csv.gz', OUT / f'player_games_{season}.csv.gz'
    games = pd.read_csv(g) if g.exists() else pd.DataFrame(columns=GAME_COLS)
    pg = pd.read_csv(p) if p.exists() else pd.DataFrame(columns=PG_COLS)
    return games, pg


def write_season(season, games, pg=None):
    """Write the games file, and the player-games file unless `pg` is None (unchanged files are left byte-identical)."""
    OUT.mkdir(parents=True, exist_ok=True)
    parts = [('games', games.sort_values(['date', 'game_ref']))] if games is not None else []
    if pg is not None:
        parts.append(('player_games', pg.sort_values(['game_ref', 'team', 'player_id'])))
    for name, df in parts:
        data = df.to_csv(index=False, float_format='%.1f' if name == 'player_games' else None).encode()
        with gzip.GzipFile(OUT / f'{name}_{season}.csv.gz', 'wb', compresslevel=9, mtime=0) as f:
            f.write(data)


def build(folder):
    new, ps = load_new(folder)
    existing = pd.concat([read_season(s)[0] for s in range(2023, 2027)], ignore_index=True)
    abbr = learn_team_abbrs(new[new['season'].between(2024, 2026)], existing[existing['season'] >= 2024])
    ids = set(new['hometeamId']) | set(new['awayteamId'])
    missing = sorted(ids - set(abbr))
    teams_now = set(new.loc[new['season'] >= FIRST_NEW_SEASON, 'hometeamId']) | set(new.loc[new['season'] >= FIRST_NEW_SEASON, 'awayteamId'])
    if teams_now - set(abbr):
        raise SystemExit(f'no abbreviation for NBA team ids {sorted(teams_now - set(abbr))}')
    sd = json.loads((DATA / 'player_seasons.json').read_text(encoding='utf8'))
    by_team, by_name, by_last = player_index(sd)
    career = json.loads((DATA / 'player_career.json').read_text(encoding='utf8'))
    official = [dict(zip(career['columns'], r)) for r in career['rows']]
    known = {o['player_id'] for o in official}
    old = read_stubs()
    kept, remap = reconcile_stubs(old['players'], official)
    apply_remap(remap)
    if remap or len(kept) != len(old['players']):
        print(f'provisional players: {len(old["players"]) - len(kept) - len(remap)} replaced by official rows, {len(remap)} remapped to official ids')
    stub_source = {p['player_id']: old['source'][p['player_id']] for p in kept if p['player_id'] in old['source']}
    stub_names = {p['player_id']: p['player'] for p in kept}
    taken = set(known) | set(stub_names)
    players_csv = pd.read_csv(folder / 'Players.csv', low_memory=False) if (folder / 'Players.csv').exists() else pd.DataFrame(columns=['personId'])
    people = players_csv.drop_duplicates('personId').set_index('personId')
    for pid, src in stub_source.items():
        k = name_key(stub_names[pid])
        by_team[(k, src['team'], FIRST_NEW_SEASON)] = pid
        by_name.setdefault(k, set()).add(pid)
    known |= set(stub_names)
    # player rows that played: minutes > 0
    ps = ps[played_mask(ps)].copy()
    ps['key'] = (ps['firstName'].fillna('') + ' ' + ps['lastName'].fillna('')).map(name_key)
    summary = {}
    new['kind'] = new['gameId'].map(game_kind)
    special = new[new['kind'].isin(['play_in', 'cup_final'])].assign(home=lambda d: d['hometeamId'].map(abbr), away=lambda d: d['awayteamId'].map(abbr))
    for season in sorted(set(new['season'])):
        if season < FIRST_KIND_SEASON:
            continue
        add = season in FILL_SEASONS or season >= FIRST_NEW_SEASON
        orig_games, orig_pg = read_season(season)
        old_games, old_pg = drop_pending(orig_games, orig_pg)
        rows, keep, unmatched = pd.DataFrame(columns=GAME_COLS), pd.DataFrame(columns=PG_COLS), pd.DataFrame(columns=['key'])
        gs = new[new['season'] == season].copy() if add else new.iloc[0:0].copy()
        gs['home'], gs['away'] = gs['hometeamId'].map(abbr), gs['awayteamId'].map(abbr)
        gs['game_ref'] = [game_ref(d, h) for d, h in zip(gs['date'], gs['home'])]
        gs = gs[~gs['game_ref'].isin(old_games['game_ref'])]
        gs = gs[[not is_duplicate({'date': r.date, 'home': r.home, 'away': r.away, 'home_pts': int(r.homeScore), 'away_pts': int(r.awayScore)}, old_games)
                 for r in gs.itertuples()]]
        gs = gs.drop_duplicates('game_ref')
        if not gs.empty:
            p = ps[ps['gameId'].isin(gs['gameId'])].copy()
            p = p.merge(gs[['gameId', 'game_ref', 'home', 'away']].rename(columns={'home': 'home_abbr', 'away': 'away_abbr'}), on='gameId')
            p['team'] = team_from_home_flag(p['home'], p['home_abbr'], p['away_abbr']).values
            p['player_id'] = [resolve_player(k, t, season, by_team, by_name, by_last) for k, t in zip(p['key'], p['team'])]
            if season >= FIRST_NEW_SEASON:
                for person_id, grp in p[p['player_id'].isna()].groupby('personId'):
                    first = grp.iloc[0]
                    info = people.loc[person_id].to_dict() if person_id in people.index else {'firstName': first['firstName'], 'lastName': first['lastName']}
                    info.setdefault('firstName', first['firstName'])
                    info.setdefault('lastName', first['lastName'])
                    pid = bbref_id(info.get('firstName'), info.get('lastName'), taken)
                    taken.add(pid)
                    stub_names[pid] = f"{str(info.get('firstName') or '').strip()} {str(info.get('lastName') or '').strip()}".strip()
                    stub_source[pid] = {'person_id': int(person_id), 'team': grp['team'].mode().iloc[0]}
                    k = name_key(stub_names[pid])
                    by_team[(k, stub_source[pid]['team'], season)] = pid
                    by_name.setdefault(k, set()).add(pid)
                    known.add(pid)
                p['player_id'] = [resolve_player(k, t, season, by_team, by_name, by_last) for k, t in zip(p['key'], p['team'])]
            unmatched = p[p['player_id'].isna() | ~p['player_id'].isin(known)]
            p = p[p['player_id'].notna() & p['player_id'].isin(known)].copy()
            p['started'] = p['startingPosition'].fillna('').astype(str).str.strip().ne('')
            p = p.rename(columns=SRC_COLS)
            p['src'] = SRC
            p = p.drop_duplicates(['game_ref', 'player_id', 'team'])
            tm = ps[ps['gameId'].isin(gs['gameId'])].merge(gs[['gameId', 'home', 'away']].rename(columns={'home': 'home_abbr', 'away': 'away_abbr'}), on='gameId')
            tm['team'] = team_from_home_flag(tm['home'], tm['home_abbr'], tm['away_abbr']).values
            team_min = tm.groupby(['gameId', 'team'])['mp'].sum()
            rows = pd.DataFrame({
                'game_ref': gs['game_ref'].values, 'season': season, 'date': gs['date'].values, 'home': gs['home'].values, 'away': gs['away'].values,
                'home_pts': gs['homeScore'].astype(int).values, 'away_pts': gs['awayScore'].astype(int).values,
                'ot': [ot_from_minutes(team_min.get((g, h))) for g, h in zip(gs['gameId'], gs['home'])],
                'playoffs': gs['gameType'].map(is_playoffs).values, 'series': None, 'src': SRC})
            rows['complete'] = rows['game_ref'].map(complete_flags(rows, p)).fillna(False)
            keep = p[p['game_ref'].isin(rows.loc[rows['complete'], 'game_ref'])][PG_COLS]
        all_games = tag_kinds(pd.concat([old_games.drop(columns='kind', errors='ignore'), rows.drop(columns='kind', errors='ignore')], ignore_index=True),
                              special[special['season'] == season])
        pg_changed = len(keep) > 0 or len(old_pg) != len(orig_pg)
        write_season(season, all_games[GAME_COLS], (pd.concat([old_pg, keep], ignore_index=True) if len(keep) else old_pg) if pg_changed else None)
        if add:
            summary[season] = {'games_added': len(rows), 'complete': int(rows['complete'].sum()) if len(rows) else 0, 'player_rows': len(keep),
                               'unmatched_player_rows': len(unmatched), 'unmatched_names': sorted(set(unmatched['key'].dropna()))[:8]}
        summary.setdefault(season, {})['play_in'] = int((all_games['kind'] == 'play_in').sum())
        summary[season]['cup_final'] = int((all_games['kind'] == 'cup_final').sum())
    if missing:
        print('team ids with no abbreviation (not in 2024-2026 games):', missing)
    summary['provisional_players'] = write_stubs(new, ps, abbr, people, stub_source, stub_names)
    return summary


def write_stubs(new, ps, abbr, people, stub_source, stub_names):
    """data/new_players.json: each provisional player's career row and newest-season row, from all his regular-season games so far."""
    meta = new[(new['season'] >= FIRST_NEW_SEASON) & (new['kind'] == 'regular')]
    meta = meta.assign(home_abbr=meta['hometeamId'].map(abbr), away_abbr=meta['awayteamId'].map(abbr))[['gameId', 'season', 'home_abbr', 'away_abbr']]
    rows = ps[ps['gameId'].isin(meta['gameId'])].merge(meta, on='gameId')
    rows['team'] = team_from_home_flag(rows['home'], rows['home_abbr'], rows['away_abbr']).values
    rows['started'] = rows['startingPosition'].fillna('').astype(str).str.strip().ne('')
    rows = rows.rename(columns=SRC_COLS)
    players, seasons, source = [], [], {}
    for pid, src in sorted(stub_source.items(), key=lambda kv: stub_names[kv[0]]):
        mine = rows[rows['personId'] == src['person_id']]
        if mine.empty:
            continue
        info = people.loc[src['person_id']].to_dict() if src['person_id'] in people.index else {}
        first, _, last = stub_names[pid].partition(' ')
        info.setdefault('firstName', first)
        info.setdefault('lastName', last)
        season = int(mine['season'].max())
        mine = mine[mine['season'] == season]
        career, season_row = provisional_player(info, stub_totals(mine), pid, mine['team'].mode().iloc[0], season)
        players.append(career)
        seasons.append(season_row)
        source[pid] = {'person_id': src['person_id'], 'team': mine['team'].mode().iloc[0]}
    (DATA / STUBS_FILE).write_text(json.dumps({'as_of': str(new['date'].max()), 'players': players, 'seasons': seasons, 'source': source},
                                              indent=1, ensure_ascii=False) + '\n', encoding='utf8')
    return len(players)


if __name__ == '__main__':
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else DATA / 'raw_eoin'
    for season, s in build(folder).items():
        print(season, s)
