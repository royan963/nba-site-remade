#!/usr/bin/env python3
"""Game-by-game player stats and game results -> data/games/*.csv.gz (one pair of files per season).

Sources, used per game by how far each can be trusted (checked on 2023-24 against the box scores):
  1. Basketball-Reference box scores (gonzalo dataset): seasons through 2023-24. Frozen once built.
  2. Deo Cheng player game log: used for a game only if its player points add up to the game's final score.
  3. Deo Cheng play-by-play (the `br_crawler` source): rebuilds counting stats for games the game log gets wrong;
     assists and minutes aren't in play-by-play, so they're borrowed from the game log per player, only when that
     player's points and rebounds agree with the rebuild.
Anything unverified stays empty. Each player-game records its source in `src`.

Usage:
  python3 scripts/prep_games.py --validate GONZALO_DIR DC_SLICE1_DIR DC_SLICE2_DIR     # measure each route on 2023-24
  python3 scripts/prep_games.py --build [--base GONZALO_DIR] [--min-complete 0.9] DC_SLICE1_DIR DC_SLICE2_DIR  # write data/games/
     --base rebuilds the frozen seasons through 2023-24 (needs the box-score dataset); without it only Deo Cheng seasons are rebuilt.
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
STATS = ['fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts']
PG_COLS = ['game_ref', 'player_id', 'team', 'started', 'mp'] + STATS + ['pm', 'src']
ALIAS = {'PHX': 'PHO', 'BKN': 'BRK', 'CHA': 'CHO', 'PHL': 'PHI', 'NOR': 'NOP', 'GS': 'GSW', 'SA': 'SAS', 'NY': 'NYK', 'NO': 'NOP', 'UTH': 'UTA'}
BR_ID = re.compile(r'^\d{9}[A-Z]{3}$')
MULTI_SEASON_NOTE = 'seasons are labeled by the year they end (2024 = 2023-24)'


def ot_count(v):
    t = str(v)
    if 'OT' not in t:
        return 0
    m = re.match(r'(\d+)\s*OT', t)
    return int(m.group(1)) if m else 1


def abbr(a):
    return ALIAS.get(a, a) if isinstance(a, str) else a


def norm_ref(ref):
    """Game ids end in the home team's abbreviation; deocheng writes some as PHL, PHX, etc. Normalize to Basketball-Reference's."""
    return ref[:-3] + abbr(ref[-3:]) if isinstance(ref, str) and BR_ID.match(ref) else ref


def minutes(v):
    if isinstance(v, str) and ':' in v:
        m, s = v.split(':')[:2]
        return int(m) + int(s) / 60
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


# ------------------------------------------------------------------ gonzalo (box scores)
def load_gonzalo(base: Path, seasons=None):
    sched = pd.read_csv(base / 'schedule.csv', low_memory=False)
    sched = sched[sched['League'].isin(['NBA', 'BAA'])].copy()
    sched['season'] = sched['Season'].str[-4:].astype(int)
    if seasons is not None:
        sched = sched[sched['season'].isin(seasons)]
    games = pd.DataFrame({
        'game_ref': sched['Game Reference'], 'season': sched['season'], 'date': sched['Date'], 'home': sched['Home'], 'away': sched['Visitor'],
        'home_pts': sched['Home PTS'].astype(int), 'away_pts': sched['Visitor PTS'].astype(int),
        'ot': sched['OT'].map(ot_count) if 'OT' in sched else 0,
        'playoffs': sched['Playoffs'].astype(str).eq('True'), 'series': sched['Series'].where(sched['Playoffs'].astype(str).eq('True')),
        'src': 'bref'})
    frames = []
    for s in sorted(games['season'].unique()):
        f = base / 'boxscores_by_year' / f'{"BAA" if s <= 1949 else "NBA"}_{s - 1}-{s}_basic.csv'
        if not f.exists():
            continue
        b = pd.read_csv(f, low_memory=False)
        b = b[(b['Period'] == 'game') & b['Reason'].isna()].copy()
        b['pts'] = pd.to_numeric(b['PTS'], errors='coerce')
        b = b[b['pts'].notna()]
        out = pd.DataFrame({'game_ref': b['Game Reference'], 'player_id': b['Player Reference'], 'team': b['Team'],
                            'started': b['Starter'].astype(str).eq('True') if 'Starter' in b else False, 'mp': b['MP'].map(minutes)})
        for src, dst in (('FG', 'fg'), ('FGA', 'fga'), ('3P', 'x3p'), ('3PA', 'x3pa'), ('FT', 'ft'), ('FTA', 'fta'), ('ORB', 'orb'), ('DRB', 'drb'),
                         ('TRB', 'trb'), ('AST', 'ast'), ('STL', 'stl'), ('BLK', 'blk'), ('TOV', 'tov'), ('PF', 'pf')):
            out[dst] = pd.to_numeric(b[src], errors='coerce')
        out['pts'] = b['pts'].values
        out['pm'] = pd.to_numeric(b['+/-'], errors='coerce') if '+/-' in b else np.nan
        out['src'] = 'bref'
        frames.append(out)
    return games, pd.concat(frames, ignore_index=True)[PG_COLS]


# ------------------------------------------------------------------ deocheng
def load_dim_games(dc1: Path):
    d = pd.read_csv(dc1 / 'public.dim_games.csv', low_memory=False)
    d = d[d['season_type'].isin(['Regular Season', 'Playoffs', 'Play-In', 'NBA Cup'])].copy()
    d['game_id'] = d['game_id'].map(norm_ref)
    d['nba'] = pd.to_numeric(d['nba_api_id'], errors='coerce')
    d['truth'] = [tuple(sorted((int(a), int(b)))) for a, b in zip(d['home_pts'], d['away_pts'])]
    return d


def load_gamelog(dc1: Path, dim: pd.DataFrame):
    g = pd.read_csv(dc1 / 'public.player_gamelog.csv', low_memory=False)
    nba_to_br = dim.dropna(subset=['nba']).drop_duplicates('nba').set_index('nba')['game_id']
    br_style = g['game_id_full'].astype(str).str.match(BR_ID)
    g['game_ref'] = np.where(br_style, g['game_id_full'], pd.to_numeric(g['gameid'], errors='coerce').map(nba_to_br))
    pick = lambda a, b: g[a].combine_first(g[b]) if b in g else g[a]
    num = lambda c: pd.to_numeric(g[c], errors='coerce') if c in g else pd.Series(np.nan, index=g.index)
    out = pd.DataFrame({
        'game_ref': g['game_ref'], 'player_id': g['br_player_id'], 'team': g['team'].map(abbr),
        'started': g['start_position'].notna() & g['start_position'].astype(str).str.strip().ne(''),
        'mp': g['minutes'].map(minutes),
        'fg': num('fg').combine_first(num('fgm')), 'fga': num('fga'), 'x3p': num('fg3').combine_first(num('tpm')),
        'x3pa': num('fga3').combine_first(num('tpa')), 'ft': num('ft').combine_first(num('ftm')), 'fta': num('fta'),
        'orb': num('orb').combine_first(num('oreb')), 'drb': num('drb').combine_first(num('dreb')), 'trb': num('trb').combine_first(num('reb')),
        'ast': num('ast'), 'stl': num('stl'), 'blk': num('blk'), 'tov': num('tov'), 'pf': num('pf'), 'pts': num('pts'),
        'pm': num('plus_minus'), 'src': 'dc_log', 'season': num('season'), 'player_name': g['player_name'] if 'player_name' in g else None})
    out['game_ref'] = out['game_ref'].map(norm_ref)
    out = out[out['pts'].notna() & out['player_id'].notna() & out['game_ref'].notna()]
    counting = out[['fg', 'fga', 'ft', 'fta', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts']].fillna(0).sum(axis=1)
    out = out[~((counting == 0) & (out['mp'].fillna(0) == 0))]               # did not play
    out.loc[(out['mp'] == 0) & (out['fga'] > 0), 'mp'] = np.nan                  # minutes missing, not zero
    return out.drop_duplicates(['game_ref', 'player_id'], keep='last')


def game_log_passes(log: pd.DataFrame, dim: pd.DataFrame) -> pd.Series:
    """game_ref -> True when the two teams' player points equal the final scores (label-free)."""
    sums = log.groupby(['game_ref', 'team'])['pts'].sum().groupby(level=0).apply(lambda s: tuple(sorted(int(v) for v in s)))
    truth = dim.drop_duplicates('game_id').set_index('game_id')['truth']
    return (sums == truth.reindex(sums.index)).rename('passes')


def load_pbp(dc2: Path, dim: pd.DataFrame, seasons):
    p = pd.read_csv(dc2 / 'public.play_by_play.csv', low_memory=False)
    p = p[(p['source'] == 'br_crawler') & p['season'].isin(seasons)].copy()
    nba_to_br = dim.dropna(subset=['nba']).drop_duplicates('nba').set_index('nba')['game_id']
    br_style = p['gameid'].astype(str).str.match(BR_ID)
    p['game_ref'] = np.where(br_style, p['gameid'], pd.to_numeric(p['gameid'], errors='coerce').map(nba_to_br))
    p['game_ref'] = p['game_ref'].map(norm_ref)
    return p[p['game_ref'].notna()]


def pbp_scores(p: pd.DataFrame) -> pd.DataFrame:
    """Final home/away score from the running score (home = first of the two sides, matching the game id's home team)."""
    s = p.groupby('game_ref').agg(home_pts=('h_pts', 'max'), away_pts=('a_pts', 'max'))
    return s.dropna()


SUFFIXES = {'jr', 'sr', 'ii', 'iii', 'iv', 'v'}


def name_key(n):
    """Spelling-proof key for an abbreviated name: 'A. Sengun' and 'A. Şengün' both give 'a sengun'; suffixes (Jr., III) and
    punctuation are dropped, and a Cyrillic look-alike е counts as e."""
    if not isinstance(n, str):
        return None
    n = unicodedata.normalize('NFKD', n.replace('\u0435', 'e').replace('\u0451', 'e'))
    n = ''.join(c for c in n if not unicodedata.combining(c)).lower()
    n = re.sub(r"[.,'’]", '', n).replace('-', ' ')
    toks = [t for t in n.split() if t not in SUFFIXES]
    return ' '.join(toks) if toks else None


def abbreviated(full):
    """'Shai Gilgeous-Alexander' -> 'S. Gilgeous-Alexander' (play-by-play style)."""
    if not isinstance(full, str) or ' ' not in full.strip():
        return None
    first, rest = full.strip().split(' ', 1)
    return f'{first[0]}. {rest}'


def log_name_map(log_raw: pd.DataFrame) -> pd.Series:
    """(game_ref, abbreviated name) -> player_id from the game log's full names; ambiguous names dropped."""
    m = log_raw[['game_ref', 'player_name', 'player_id']].dropna().copy()
    m['abbr'] = m['player_name'].map(abbreviated).map(name_key)
    m = m.dropna(subset=['abbr']).drop_duplicates(['game_ref', 'abbr', 'player_id'])
    m = m[~m.duplicated(['game_ref', 'abbr'], keep=False)]
    return m.set_index(['game_ref', 'abbr'])['player_id']


def season_roster(p: pd.DataFrame) -> pd.Series:
    """(abbreviated name, team) -> player_id from every play-by-play row that has both, across the whole season. Ambiguous pairs dropped."""
    t = p['team'].combine_first(p['current_team']).map(abbr)
    k = pd.DataFrame({'player': p['player'].map(name_key), 'team': t, 'pid': p['br_player_id']}).dropna().drop_duplicates()
    k = k[~k.duplicated(['player', 'team'], keep=False)]
    return k.set_index(['player', 'team'])['pid']


def log_season_roster(log_raw: pd.DataFrame) -> pd.Series:
    """(abbreviated name, team) -> player_id from the whole season's game log, for players play-by-play never gives an id."""
    m = log_raw[['player_name', 'team', 'player_id']].dropna().copy()
    m['abbr'] = m['player_name'].map(abbreviated).map(name_key)
    m = m.dropna(subset=['abbr']).drop_duplicates(['abbr', 'team', 'player_id'])
    m = m[~m.duplicated(['abbr', 'team'], keep=False)]
    m.index = pd.MultiIndex.from_arrays([m['abbr'].astype('string'), m['team']])
    return m['player_id']


def our_roster(seasons) -> pd.Series:
    """(abbreviated name, team) -> player_id from this project's own Basketball-Reference season data (full names, per-team stints)."""
    f = DATA / 'player_seasons.json'
    if not f.exists():
        return pd.Series(dtype='object')
    d = json.loads(f.read_text())
    ps = pd.DataFrame(d['rows'], columns=d['columns'])
    ps = ps[ps['season'].isin(seasons) & ~ps['team'].isin(['2TM', '3TM', '4TM', '5TM'])].copy()
    ps['abbr'] = ps['player'].map(abbreviated).map(name_key)
    ps = ps.dropna(subset=['abbr']).drop_duplicates(['abbr', 'team', 'player_id'])
    ps = ps[~ps.duplicated(['abbr', 'team'], keep=False)]
    ps.index = pd.MultiIndex.from_arrays([ps['abbr'].astype('string'), ps['team']])
    return ps['player_id']


def pbp_rebuild(p: pd.DataFrame, extra_names: pd.Series = None, roster: pd.Series = None) -> pd.DataFrame:
    """Counting stats per (game, player) from play-by-play events. Steal/block rows carry only names, so names are
    resolved to ids within the game (ambiguous names are dropped)."""
    p = p.copy()
    p['player'] = p['player'].map(name_key)                 # spelling-proof from here on
    known = p[p['br_player_id'].notna() & p['player'].notna()][['game_ref', 'player', 'br_player_id']].drop_duplicates()
    amb = known.groupby(['game_ref', 'player'])['br_player_id'].nunique()
    ok = known.set_index(['game_ref', 'player'])['br_player_id']
    ok = ok[~ok.index.duplicated(keep='first')]
    ambiguous = set(amb[amb > 1].index)
    keys = list(zip(p['game_ref'], p['player']))
    from_name = pd.Series([ok.get(k) if k not in ambiguous else None for k in keys], index=p.index)
    p['pid'] = p['br_player_id'].where(p['br_player_id'].notna(), from_name)
    if extra_names is not None:
        need = p['pid'].isna() & p['player'].notna()
        lookup = pd.Series([extra_names.get(k) for k in zip(p.loc[need, 'game_ref'], p.loc[need, 'player'])], index=p.index[need])
        p.loc[need, 'pid'] = lookup
    if roster is not None:                          # still unresolved: the player's name on this team, from anywhere in the season
        need = p['pid'].isna() & p['player'].notna()
        tm = p['team'].combine_first(p['current_team']).map(abbr)
        p.loc[need, 'pid'] = pd.Series([roster.get(k) for k in zip(p.loc[need, 'player'], tm[need])], index=p.index[need])
    et = p['event_type'].astype('string').str.lower().fillna('')
    av = p['action_verb'].astype('string').str.lower().fillna('')
    desc = p['description'].astype('string').str.lower().fillna('')
    sub = p['subtype'].astype('string').str.lower().fillna('')
    # two event formats occur in this source: 'Made Shot' / 'Free Throw' with 'makes ... 3-pt' text, and NBA-style
    # '2pt' / '3pt' / 'freethrow' with makes/misses in action_verb and missed free throws starting with 'MISS'
    shot_alt = et.isin(['2pt', '3pt'])
    three = desc.str.contains('3-pt') | (et == '3pt')
    made = (et == 'made shot') | (shot_alt & (av == 'makes'))
    missed = (et == 'missed shot') | (shot_alt & (av == 'misses'))
    is_ft = et.isin(['free throw', 'freethrow'])
    ftm = is_ft & (desc.str.contains('makes') | ((et == 'freethrow') & ~desc.str.startswith('miss')))
    ev = pd.DataFrame({
        'game_ref': p['game_ref'], 'pid': p['pid'], 'team': p['team'].combine_first(p['current_team']).map(abbr),
        'fg': made.astype(int), 'fga': (made | missed).astype(int), 'x3p': (made & three).astype(int), 'x3pa': ((made | missed) & three).astype(int),
        'ft': ftm.astype(int), 'fta': is_ft.astype(int),
        'orb': ((et == 'rebound') & desc.str.contains('offensive')).astype(int), 'drb': ((et == 'rebound') & desc.str.contains('defensive')).astype(int),
        'trb': (et == 'rebound').astype(int), 'tov': (et == 'turnover').astype(int),
        'pf': ((et == 'foul') & ~sub.str.contains('technical')).astype(int), 'stl': (av == 'steal').astype(int), 'blk': (av == 'block').astype(int)})
    ev['pts'] = ev['fg'] * 2 + ev['x3p'] + ev['ft']
    ev = ev[ev['pid'].notna()]
    team = ev.dropna(subset=['team']).groupby(['game_ref', 'pid'])['team'].agg(lambda s: s.mode().iat[0])
    out = ev.groupby(['game_ref', 'pid'])[['fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'orb', 'drb', 'trb', 'tov', 'pf', 'stl', 'blk', 'pts']].sum()
    out['team'] = team
    return out.reset_index().rename(columns={'pid': 'player_id'})


def compare(label, mine: pd.DataFrame, truth: pd.DataFrame, fields):
    m = truth.merge(mine, on=['game_ref', 'player_id'], suffixes=('_t', '_m'))
    rows = []
    for f in fields:
        a, b = m[f + '_t'], m[f + '_m']
        both = a.notna() & b.notna() & ((a > 0) | (b > 0))
        rows.append((f, int(both.sum()), (a[both] == b[both]).mean() if both.any() else np.nan))
    print(f'\n{label}: {len(m):,} player-games in both ({len(m) / len(truth):.1%} of the box-score rows)')
    print('  ' + ' | '.join(f'{f} {r:.1%}' for f, n, r in rows))
    return dict((f, r) for f, n, r in rows)


def validate(gz: Path, dc1: Path, dc2: Path):
    games, truth = load_gonzalo(gz, seasons=[2024])
    truth = truth[truth['game_ref'].isin(games['game_ref'])]
    dim = load_dim_games(dc1)
    log = load_gamelog(dc1, dim)
    log24 = log[log['season'] == 2024]
    passes = game_log_passes(log24, dim)
    print(f'2023-24 game log: {len(passes):,} games, {passes.mean():.1%} pass the points-sum check')
    good = log24[log24['game_ref'].isin(passes[passes].index)]
    compare('ROUTE A, game log (games that pass the check) vs. box scores', good, truth, STATS + ['mp', 'pm'])
    bad = log24[log24['game_ref'].isin(passes[~passes].index)]
    compare('   game log, games that FAIL the check', bad, truth, STATS)
    p = load_pbp(dc2, dim, [2024])
    reb = pbp_rebuild(p)
    sc = pbp_scores(p)
    t = dim.drop_duplicates('game_id').set_index('game_id')['truth']
    full = sc[[tuple(sorted((int(h), int(a)))) == t.get(g) for g, h, a in zip(sc.index, sc['home_pts'], sc['away_pts'])]]
    print(f'\n2023-24 play-by-play: {len(sc):,} games, {len(full):,} with the true final score')
    compare('ROUTE B, play-by-play rebuild (complete games) vs. box scores', reb[reb['game_ref'].isin(full.index)], truth, [s for s in STATS if s != 'ast'])
    # route C: players in both the rebuild and the game log whose points and rebounds agree take the whole log row
    j = reb.merge(log24, on=['game_ref', 'player_id'], suffixes=('_pbp', ''))
    agree = j[(j['pts_pbp'] == j['pts']) & (j['trb_pbp'] == j['trb'])]
    print(f'\nROUTE C, take the game-log row when points and rebounds agree with the rebuild: {len(agree):,} of {len(j):,} joined players')
    compare('   those log rows (all stats incl. ast, mp, pm, orb, drb, pf) vs. box scores', agree[['game_ref', 'player_id'] + STATS + ['mp', 'pm']], truth, STATS + ['mp', 'pm'])
    dis = j[~((j['pts_pbp'] == j['pts']) & (j['trb_pbp'] == j['trb']))]
    print(f'   disagreeing players ({len(dis):,}): rebuild vs. box score pts equal ' f"{(truth.merge(dis[['game_ref', 'player_id', 'pts_pbp']], on=['game_ref', 'player_id']).pipe(lambda m: (m['pts'] == m['pts_pbp']).mean())):.1%}, "
          f"log vs. box score pts equal {(truth.merge(dis[['game_ref', 'player_id', 'pts']], on=['game_ref', 'player_id'], suffixes=('_t', '_l')).pipe(lambda m: (m['pts_t'] == m['pts_l']).mean())):.1%}")
    # team label: does the rebuild's team match?
    mt = truth.merge(reb[['game_ref', 'player_id', 'team']], on=['game_ref', 'player_id'], suffixes=('_t', '_m'))
    mt = mt[mt['team_m'].notna()]
    print(f"\nteam label from play-by-play agrees with the box score for {(mt['team_t'] == mt['team_m']).mean():.1%} of {len(mt):,} player-games")


# ------------------------------------------------------------------ build
FIRST_DEOCHENG_SEASON = 2025          # the box-score dataset ends with 2023-24; seasons from here on come from Deo Cheng
ACCEPT_FROM_PBP = ['fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'trb', 'stl', 'blk', 'tov', 'pts']      # validated >= 99% (orb/drb/pf are not)


def complete_flags(games: pd.DataFrame, pg: pd.DataFrame) -> pd.Series:
    """game_ref -> player points add up to each team's final score."""
    sums = pg.groupby(['game_ref', 'team'])['pts'].sum()
    key = pd.concat([games.set_index('game_ref')['home_pts'].rename('h'), games.set_index('game_ref')['away_pts'].rename('a')], axis=1).dropna()
    expected = pd.Series([tuple(sorted((int(h), int(a)))) for h, a in zip(key['h'], key['a'])], index=key.index)
    got = sums.groupby(level=0).apply(lambda t: tuple(sorted(int(v) for v in t)))
    return (got.reindex(key.index) == expected).fillna(False)


def team_sums_ok(df: pd.DataFrame, truth: pd.Series) -> pd.Series:
    got = df.groupby(['game_ref', 'team'])['pts'].sum().groupby(level=0).apply(lambda t: tuple(sorted(int(v) for v in t)))
    return got.reindex(truth.index).eq(truth).fillna(False)


def assemble(log: pd.DataFrame, p: pd.DataFrame, truth: pd.Series):
    """Per game: the game log if its points add up; else the play-by-play rebuild (when its score is complete), upgraded with the
    game-log row for each player whose points and rebounds agree. Returns player rows, the games each route covered, and the scores."""
    sc = pbp_scores(p)
    pbp_ok = pd.Index([g for g, h, a in zip(sc.index, sc['home_pts'], sc['away_pts']) if tuple(sorted((int(h), int(a)))) == truth.get(g)])
    log_ok = team_sums_ok(log, truth)
    log_games = log_ok[log_ok].index
    take_log = log[log['game_ref'].isin(log_games)][PG_COLS]
    todo = pbp_ok.difference(log_games)
    roster = pd.concat([season_roster(p), log_season_roster(log), our_roster(sorted(set(pd.to_numeric(p['season'], errors='coerce').dropna().astype(int))))])
    roster = roster[~roster.index.duplicated(keep='first')]
    reb = pbp_rebuild(p[p['game_ref'].isin(todo)], log_name_map(log), roster)
    reb = reb[reb['team'].notna()]
    j = reb.merge(log.drop(columns=['team', 'src', 'player_name']), on=['game_ref', 'player_id'], how='left', suffixes=('', '_log'), indicator=True)
    both = j['_merge'] == 'both'
    agree = both & (j['pts'] == j['pts_log']) & (j['trb'] == j['trb_log'])
    conflict = both & ~agree

    def as_log(rows):                               # the game-log values for these joined rows
        out = rows[['game_ref', 'player_id', 'team']].copy()
        for c in ['started', 'mp'] + STATS + ['pm']:
            out[c] = rows[c + '_log'] if c + '_log' in rows else rows[c]        # columns only the log has carry no suffix
        out['src'] = 'dc_log'
        return out[PG_COLS]
    rebuilt = j[['game_ref', 'player_id', 'team'] + ACCEPT_FROM_PBP].copy()
    for c in ['started', 'mp', 'orb', 'drb', 'pf', 'ast', 'pm']:
        rebuilt[c] = np.nan
    rebuilt['src'] = 'dc_pbp'
    rebuilt = rebuilt[PG_COLS]
    stage1 = pd.concat([rebuilt[~agree.values & ~conflict.values], as_log(j[agree])], ignore_index=True)
    # for players whose log row and rebuild disagree, keep whichever version makes both teams' points add up
    with_conf = pd.concat([stage1, rebuilt[conflict.values]], ignore_index=True)
    swapped = pd.concat([stage1, as_log(j[conflict])], ignore_index=True)
    ok_keep, ok_swap = team_sums_ok(with_conf, truth), team_sums_ok(swapped, truth)
    conf_games = set(j.loc[conflict, 'game_ref'])
    use_swap = {g for g in conf_games if ok_swap.get(g, False) and not ok_keep.get(g, False)}
    swap_rows = as_log(j[conflict & j['game_ref'].isin(use_swap)])
    keep_rows = rebuilt[conflict.values & ~j['game_ref'].isin(use_swap).values]
    pg = pd.concat([take_log, stage1, swap_rows, keep_rows], ignore_index=True)
    complete = team_sums_ok(pg, truth)
    pg = pg[pg['game_ref'].isin(complete[complete].index)]           # a game whose points don't add up shows no player stats
    return pg, complete, log_ok, sc, pbp_ok


def build_deocheng(dc1: Path, dc2: Path, seasons):
    dim = load_dim_games(dc1)
    real = dim[dim['season'].isin(seasons) & dim['season_type'].isin(['Regular Season', 'Playoffs'])].drop_duplicates('game_id').copy()
    truth = real.set_index('game_id')['truth']
    log = load_gamelog(dc1, dim)
    log = log[log['season'].isin(seasons) & log['game_ref'].isin(real['game_id'])].drop(columns='season')
    p = load_pbp(dc2, dim, seasons)
    p = p[p['game_ref'].isin(real['game_id'])]
    pg, complete, log_ok, sc, pbp_ok = assemble(log, p, truth)
    teams = pg.groupby('game_ref')['team'].agg(lambda t: sorted(set(t)))
    max_period = p.groupby('game_ref')['period'].max()
    team_pts = pg.groupby(['game_ref', 'team'])['pts'].sum()
    rows = []
    for g in real.itertuples():
        ref = g.game_id
        home = abbr(ref[-3:])
        ts = teams.get(ref, [])
        away = next((t for t in ts if t != home), None) if home in ts else None
        hp = ap = None
        if ref in pbp_ok:
            hp, ap = int(sc.at[ref, 'home_pts']), int(sc.at[ref, 'away_pts'])
        elif complete.get(ref, False) and away is not None:           # player points already equal the final scores
            hp, ap = int(team_pts.get((ref, home), 0)), int(team_pts.get((ref, away), 0))
        rows.append({'game_ref': ref, 'season': int(g.season), 'date': f'{ref[:4]}-{ref[4:6]}-{ref[6:8]}', 'home': home, 'away': away,
                     'home_pts': hp, 'away_pts': ap, 'ot': int(max(max_period.get(ref, 4) - 4, 0)) if ref in max_period.index else None,
                     'playoffs': g.season_type == 'Playoffs', 'series': None, 'src': 'deocheng', 'complete': bool(complete.get(ref, False))})
    games = pd.DataFrame(rows)
    games = games[games['away'].notna() & games['home_pts'].notna()]          # games we can't place (no team or score) are left out
    return games, pg[pg['game_ref'].isin(games['game_ref'])], real, log_ok, complete


def write_season(season, games, pg):
    OUT.mkdir(parents=True, exist_ok=True)
    games = games.sort_values(['date', 'game_ref'])
    pg = pg.sort_values(['game_ref', 'team', 'player_id'])
    for name, df in (('games', games), ('player_games', pg)):
        csv_bytes = df.to_csv(index=False, float_format='%.1f' if name == 'player_games' else None).encode()
        with gzip.GzipFile(OUT / f'{name}_{season}.csv.gz', 'wb', compresslevel=9, mtime=0) as f:      # mtime=0: unchanged seasons stay byte-identical
            f.write(csv_bytes)


def build(base, dc1, dc2):
    total = {}
    if base:
        games, pg = load_gonzalo(base)
        games['complete'] = games['game_ref'].map(complete_flags(games, pg)).fillna(False)
        for s in sorted(games['season'].unique()):
            g = games[games['season'] == s]
            write_season(int(s), g, pg[pg['game_ref'].isin(g['game_ref'])])
        print(f'base seasons written: {games["season"].min()}-{games["season"].max()}; {len(games):,} games, {len(pg):,} player-games; '
              f'player points add up in {games["complete"].mean():.1%} of games')
    seasons = sorted(int(x) for x in load_dim_games(dc1)['season'].unique() if x >= FIRST_DEOCHENG_SEASON)
    games, pg, real, log_ok, complete = build_deocheng(dc1, dc2, seasons)
    for s in seasons:
        g = games[games['season'] == s]
        write_season(s, g, pg[pg['game_ref'].isin(g['game_ref'])])
    r = real.assign(has_game=real['game_id'].isin(games['game_ref']), complete=real['game_id'].map(complete).fillna(False), log_ok=real['game_id'].map(log_ok).fillna(False))
    print('\nDeo Cheng seasons (games the site can show / with complete player stats / game log alone was complete):')
    for (s, t), x in r.groupby(['season', 'season_type']):
        print(f'  {s} {t:<15s} {len(x):>5d} games | in dataset {int(x.has_game.sum()):>5d} | complete {int(x.complete.sum()):>5d} | log alone {int(x.log_ok.sum()):>5d}')
    srcs = pg.groupby('src').size().to_dict()
    print('player-game rows by source:', srcs)
    unknown = set(pg['team'].dropna()) | set(games['home']) | set(games['away'])
    geo = json.loads((DATA / 'team_geo.json').read_text()); gc = geo['columns']
    known = {r[gc.index('abbr')] for r in geo['rows']}
    print('team labels not in team_geo:', sorted(unknown - known))
    sizes = sum(f.stat().st_size for f in OUT.glob('*.csv.gz'))
    print(f'data/games: {len(list(OUT.glob("*.csv.gz")))} files, {sizes / 1e6:.1f} MB')
    return r


def coverage_gate(r, minimum):
    """Fail (exit 2) if a season far enough along has too few regular-season games with complete player stats, so an
    update can't silently replace good data with a worse source."""
    bad = []
    for s_, x in r[r['season_type'] == 'Regular Season'].groupby('season'):
        if len(x) >= 200 and x['complete'].mean() < minimum:
            bad.append(f'{s_}: {x["complete"].mean():.1%} of {len(x)} games complete (minimum {minimum:.0%})')
    if bad:
        print('COVERAGE CHECK FAILED:', '; '.join(bad))
        sys.exit(2)
    print(f'coverage check passed (each season: at least {minimum:.0%} of regular-season games complete)')


def validate_build(gz: Path, dc1: Path, dc2: Path):
    """Run the exact production assembly on 2023-24 and compare with the box scores (regular season only: the playoffs aren't in deocheng)."""
    games, truth = load_gonzalo(gz, seasons=[2024])
    reg = games[~games['playoffs']]
    truth = truth[truth['game_ref'].isin(reg['game_ref'])]
    g, pg, real, log_ok, complete = build_deocheng(dc1, dc2, [2024])
    real = real[real['season_type'] == 'Regular Season']
    print(f'2023-24 regular season: {len(real):,} games | placed in dataset {g["game_ref"].isin(real["game_id"]).sum():,} | complete {complete.reindex(real["game_id"]).fillna(False).sum():,} | game log alone complete {log_ok.reindex(real["game_id"]).fillna(False).sum():,}')
    print('player-game rows by source:', pg.groupby('src').size().to_dict())
    compare('PRODUCTION ASSEMBLY vs. box scores', pg, truth, STATS + ['mp', 'pm'])
    have = truth.merge(pg[['game_ref', 'player_id']], on=['game_ref', 'player_id'], how='left', indicator=True)
    print(f'coverage: {(have._merge == "both").mean():.1%} of the box-score player-games are present; extra rows not in the box score: ' f"{len(pg.merge(truth[['game_ref', 'player_id']], on=['game_ref', 'player_id'], how='left', indicator=True).query('_merge == \"left_only\"')):,}")
    real_teams = games.set_index('game_ref')
    ok_away = (g.set_index('game_ref')['away'] == real_teams['away'].reindex(g['game_ref']).values).mean()
    ok_score = ((g.set_index('game_ref')['home_pts'] == real_teams['home_pts'].reindex(g['game_ref']).values) & (g.set_index('game_ref')['away_pts'] == real_teams['away_pts'].reindex(g['game_ref']).values)).mean()
    print(f'games table: visitor correct {ok_away:.1%}, home/away scores correct {ok_score:.1%} (of {len(g):,} games)')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--validate' in sys.argv:
        validate(Path(args[0]), Path(args[1]), Path(args[2]))
    elif '--validate-build' in sys.argv:
        validate_build(Path(args[0]), Path(args[1]), Path(args[2]))
    elif '--build' in sys.argv:
        base = Path(sys.argv[sys.argv.index('--base') + 1]) if '--base' in sys.argv else None
        args = [a for a in sys.argv[1:] if not a.startswith('--') and (base is None or a != str(base))]
        minimum = float(sys.argv[sys.argv.index('--min-complete') + 1]) if '--min-complete' in sys.argv else None
        args = [a for a in args if minimum is None or a != str(sys.argv[sys.argv.index('--min-complete') + 1])]
        r = build(base, Path(args[0]), Path(args[1]))
        if minimum is not None:
            coverage_gate(r, minimum)
    else:
        sys.exit(__doc__)
