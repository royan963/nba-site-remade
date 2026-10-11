#!/usr/bin/env python3
"""Playoff series, championships and playoff player stats, from game-level data.

Reads the Basketball-Reference game data (the "NBA All Time Stats" dataset by
gonzalogigena: schedule.csv + boxscores_by_year/*_basic.csv) and writes
data/playoff_series.json, data/playoff_teams.json, data/player_playoffs.json
and data/player_titles.json.

Usage:  python3 scripts/prep_playoffs.py [folder with schedule.csv] [--deocheng folder with the slice's CSVs]
        (default folder: data/raw_games). With --deocheng, results, playoff totals and rings are extended
        through the latest season and rings are audited against official counts (see the extension section).

What it works out
  - Series: games grouped by round and team pair; winner = most game wins.
  - Round depth: counted back from the Finals ("rounds from the final"), so
    differently named rounds across eras (Division, Conference, Quarterfinals)
    line up.
  - Team playoff results: how far each team got, and its series/game record.
  - Titles: a player gets a ring for a season if he appears in any playoff box
    score row for the champion that year, including did-not-play rows (rostered
    but unused), but not rows marked suspended or not with the team.
  - Player playoff seasons: totals from box scores. Stats the era didn't record
    stay empty rather than becoming zero, and per-game averages use only the
    games where the stat exists (`g_rec`).
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else ROOT / 'data' / 'raw_games'
DC = Path(sys.argv[sys.argv.index('--deocheng') + 1]) if '--deocheng' in sys.argv else None
LEAGUES = ['NBA', 'BAA']
NOT_ON_ROSTER = {'Not With Team', 'Player Suspended'}
ROUND_LABELS = {0: 'Finals', 1: 'Conference Finals', 2: 'Conference Semifinals', 3: 'First Round', 4: 'Opening Round'}
COUNT_STATS = ['fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts']
REC_STATS = ['mp', 'trb', 'ast', 'stl', 'blk']          # stats with gaps in older seasons


def season_end(label: str) -> int:
    return int(label.split('-')[1])


def minutes(v):
    if isinstance(v, str) and ':' in v:
        m, s = v.split(':')
        return int(m) + int(s) / 60
    return np.nan


def build_series(games: pd.DataFrame, nameless: bool = False) -> pd.DataFrame:
    """nameless=True: the source has no round names, so the Finals is the season's last-ending series."""
    g = games.copy()
    g['winner'] = np.where(g['Home PTS'] > g['Visitor PTS'], g['Home'], g['Visitor'])
    g['a'] = g[['Home', 'Visitor']].min(axis=1)
    g['b'] = g[['Home', 'Visitor']].max(axis=1)
    rows = []
    for (season, name, a, b), s in g.groupby(['season', 'Series', 'a', 'b']):
        wa, wb = int((s['winner'] == a).sum()), int((s['winner'] == b).sum())
        rows.append({'season': season, 'round_name': name, 'team_a': a, 'team_b': b, 'wins_a': wa, 'wins_b': wb,
                     'winner': a if wa > wb else b if wb > wa else None, 'games': len(s),
                     'start': s['Date'].min(), 'end': s['Date'].max()})
    ser = pd.DataFrame(rows)
    ser['complete'] = True
    ser['is_final'] = ser['round_name'].eq('Finals')
    if nameless:
        ser['is_final'] = ser.groupby('season')['end'].transform('max').eq(ser['end'])
    # Cross-check every non-Finals winner against who actually played in a later round. A missing game
    # in the source data can leave a series tied or put the wrong team ahead; the team that advanced wins.
    fixes = []
    for i, r in ser.iterrows():
        if r.is_final:
            continue
        later = ser[(ser.season == r.season) & (ser.start > r.end)]
        advanced = [t for t in (r.team_a, r.team_b) if ((later.team_a == t) | (later.team_b == t)).any()]
        if len(advanced) == 1 and advanced[0] != r.winner:
            fixes.append((int(r.season), r.round_name, r.team_a, r.team_b, f'{r.wins_a}-{r.wins_b}', r.winner, advanced[0]))
            ser.at[i, 'winner'], ser.at[i, 'complete'] = advanced[0], False
    if fixes:
        print('series fixed because a game is missing from the source (derived winner -> team that advanced):')
        for f in fixes:
            print('   ', f)
    ser['rff'] = np.nan
    for season, s in ser.groupby('season'):
        idx = s.sort_values('end', ascending=False).index.to_list()
        finals = [i for i in idx if ser.at[i, 'is_final']]
        assert len(finals) == 1, f'{season}: expected one Finals series, found {len(finals)}'
        ser.at[finals[0], 'rff'] = 0
        for i in idx:                                    # latest first, so later rounds are already known
            if i == finals[0]:
                continue
            w = ser.at[i, 'winner']
            nxt = s[(s['start'] > ser.at[i, 'end']) & ((s['team_a'] == w) | (s['team_b'] == w))].sort_values('start')
            if len(nxt) and not np.isnan(ser.at[nxt.index[0], 'rff']):
                ser.at[i, 'rff'] = ser.at[nxt.index[0], 'rff'] + 1
    ser['round_label'] = ser['rff'].map(lambda r: None if np.isnan(r) else ROUND_LABELS.get(int(r), f'Round of {2 ** (int(r) + 1)}'))
    if nameless:
        ser['round_name'] = ser['round_label']
    return ser


def team_results(ser: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in ser.iterrows():
        for team, opp, won, lost in ((r.team_a, r.team_b, r.wins_a, r.wins_b), (r.team_b, r.team_a, r.wins_b, r.wins_a)):
            rows.append({'season': r.season, 'team': team, 'end': r.end, 'rff': r.rff, 'round_label': r.round_label,
                         'series_won': int(r.winner == team), 'gw': won, 'gl': lost})
    t = pd.DataFrame(rows).sort_values(['end', 'rff'], ascending=[True, False], na_position='last')
    out = []
    for (season, team), g in t.groupby(['season', 'team']):
        last = g.iloc[-1]
        champion = last['rff'] == 0 and last['series_won'] == 1
        deepest = g.sort_values('rff').iloc[0]
        result = 'Champion' if champion else f"Lost in {deepest['round_label'] or 'playoffs'}" if not np.isnan(deepest['rff']) else 'Playoffs'
        out.append({'season': season, 'team': team, 'series_won': int(g['series_won'].sum()), 'series_lost': int(len(g) - g['series_won'].sum()),
                    'games_won': int(g['gw'].sum()), 'games_lost': int(g['gl'].sum()), 'result': result,
                    'rff_deepest': None if np.isnan(deepest['rff']) else int(deepest['rff']), 'champion': bool(champion)})
    return pd.DataFrame(out)


PLAYER_COLS = ['player_id', 'season', 'team', 'g', 'mp'] + COUNT_STATS + [f'g_{s}' for s in REC_STATS] + ['source']
SERIES_COLS = ['season', 'round_name', 'round_label', 'rff', 'team_a', 'team_b', 'wins_a', 'wins_b', 'winner', 'games', 'start', 'end', 'complete']
TEAM_COLS = ['season', 'team', 'series_won', 'series_lost', 'games_won', 'games_lost', 'result', 'rff_deepest', 'champion']


def _rows(df, columns):
    return [[None if (isinstance(v, float) and np.isnan(v)) else (int(v) if isinstance(v, (np.integer,)) else
             float(v) if isinstance(v, np.floating) else v) for v in r] for r in df[columns].itertuples(index=False)]


def write_outputs(ser, teams, out, titles):
    ser_out = ser.copy()
    ser_out['rff'] = ser_out['rff'].map(lambda r: None if r is None or (isinstance(r, float) and np.isnan(r)) else int(r))
    ser_out = ser_out.sort_values(['season', 'rff', 'team_a'], ascending=[True, False, True], na_position='first', kind='stable')
    for name, df, columns in (('playoff_series', ser_out, SERIES_COLS), ('playoff_teams', teams.sort_values(['season', 'team']), TEAM_COLS),
                              ('player_playoffs', out.sort_values(['season', 'player_id', 'team']), PLAYER_COLS),
                              ('player_titles', titles.sort_values(['season', 'player_id']), ['player_id', 'season', 'team'])):
        (DATA / f'{name}.json').write_text(json.dumps({'columns': columns, 'rows': _rows(df, columns)}, allow_nan=False))
        print(f'  {name}.json: {len(df):,} rows')


def load_json_frame(name):
    d = json.loads((DATA / f'{name}.json').read_text())
    return pd.DataFrame(d['rows'], columns=d['columns'])


def main_frozen():
    """The game-data folder (gonzalo) isn't here, e.g. on the weekly GitHub job. That source ends with 2023-24 and never
    updates, so keep everything built from it (committed in data/) and rebuild only the Deo Cheng part: series and team
    results from SLICE_FROM on, and rings for the seasons after the box scores end, audited against official counts."""
    if not DC:
        raise SystemExit(f'{SRC} has no schedule.csv; pass --deocheng <slice folder> to update from Deo Cheng only')
    ser_old = load_json_frame('playoff_series')
    ser = pd.concat([ser_old[ser_old['season'] < SLICE_FROM], deocheng_series(DC)], ignore_index=True)
    teams = team_results(ser)
    champs = ser[ser['rff'] == 0].set_index('season')['winner']
    out = load_json_frame('player_playoffs')
    if 'source' not in out:
        out['source'] = 'box'
    out = out[out['source'] == 'box']                           # rebuilt below from the newer sources
    last_box = int(out['season'].max())
    titles = load_json_frame('player_titles')
    titles = titles[titles['season'] <= last_box]
    _, srows = deocheng_player_playoffs(DC)
    new = [{'player_id': pid, 'season': season, 'team': champ} for season, champ in champs.items() if season > last_box
           for pid in srows[(srows.season_end == season) & (srows.team_abbr == champ)]['player_id'].unique()]
    titles = pd.concat([titles, pd.DataFrame(new)], ignore_index=True)
    titles, rec = reconcile_titles(titles, dict(champs), DC)
    out = extend_player_playoffs(out, DC)
    print(f'frozen base through {last_box}; series {ser.season.min()}-{ser.season.max()}; champions '
          + ', '.join(f"{y} {champs[y]}" for y in sorted(champs.index)[-3:]))
    print(f'rings: {rec["equal"]} of {rec["compared"]} players match official counts; unresolved {len(rec["unresolved"])}; over-credited {rec["over"]}')
    write_outputs(ser, teams, out, titles)


def main():
    if not (SRC / 'schedule.csv').exists():
        return main_frozen()
    sched = pd.read_csv(SRC / 'schedule.csv', low_memory=False)
    sched = sched[sched['League'].isin(LEAGUES)].copy()
    sched['season'] = sched['Season'].map(season_end)
    po = sched[sched['Playoffs'].astype(str) == 'True'].copy()
    ser = build_series(po)
    teams = team_results(ser)
    if DC:
        ser2 = deocheng_series(DC)
        key = lambda df: {(r.team_a, r.team_b): (r.winner, max(r.wins_a, r.wins_b), min(r.wins_a, r.wins_b)) for r in df.itertuples()}
        k1, k2 = key(ser[ser.season == SLICE_FROM]), key(ser2[ser2.season == SLICE_FROM])
        same_w = sum(1 for k in k1 if k in k2 and k1[k][0] == k2[k][0])
        same_rec = sum(1 for k in k1 if k in k2 and k1[k] == k2[k])
        print(f'{SLICE_FROM} cross-check, series from gonzalo vs. Deo Cheng series table: {len(k1)} vs {len(k2)} series, '
              f'same winner {same_w}, same exact record {same_rec}; differing: {[(k, k1[k], k2.get(k)) for k in k1 if k2.get(k) != k1[k]]}')
        ser = pd.concat([ser[ser.season < SLICE_FROM], ser2], ignore_index=True)
        teams = team_results(ser)
        print(f'seasons now: {ser.season.min()}-{ser.season.max()}; champions: ' + ', '.join(f"{int(y)} {ser[(ser.season == y) & (ser.rff == 0)].winner.iloc[0]}" for y in (2024, 2025, 2026) if y in set(ser.season)))
    undecided = ser[ser['winner'].isna()]
    assert undecided.empty, f'series with no winner: {undecided[["season", "round_name", "team_a", "team_b"]].values.tolist()}'
    print(f'{len(po):,} playoff games -> {len(ser):,} series in {ser.season.nunique()} seasons; '
          f'rounds-from-final unresolved: {int(ser.rff.isna().sum())}')

    champs = ser[ser.rff == 0].set_index('season')['winner']
    po_refs = set(po['Game Reference'])
    po_season = po.set_index('Game Reference')['season']
    frames = []
    for f in sorted(glob.glob(str(SRC / 'boxscores_by_year' / '*_basic.csv'))):
        if Path(f).name.startswith('ABA_'):
            continue
        b = pd.read_csv(f, low_memory=False)
        b = b[(b['Period'] == 'game') & b['Game Reference'].isin(po_refs)]
        if len(b):
            frames.append(b)
    box = pd.concat(frames, ignore_index=True)
    box['season'] = box['Game Reference'].map(po_season)
    print(f'{len(box):,} playoff player-game rows; reasons: {box["Reason"].value_counts().to_dict()}')

    # ---- titles --------------------------------------------------------------------------
    roster = box[~box['Reason'].isin(NOT_ON_ROSTER)]
    champ_rows = roster[roster['Team'] == roster['season'].map(champs)]
    titles = champ_rows.groupby(['Player Reference', 'season', 'Team']).size().reset_index(name='games')[['Player Reference', 'season', 'Team']]
    titles.columns = ['player_id', 'season', 'team']

    # ---- player playoff seasons ----------------------------------------------------------
    played = box[box['Reason'].isna()].copy()
    played['mp'] = played['MP'].map(minutes)
    for src, dst in (('FG', 'fg'), ('FGA', 'fga'), ('3P', 'x3p'), ('3PA', 'x3pa'), ('FT', 'ft'), ('FTA', 'fta'), ('ORB', 'orb'), ('DRB', 'drb'),
                     ('TRB', 'trb'), ('AST', 'ast'), ('STL', 'stl'), ('BLK', 'blk'), ('TOV', 'tov'), ('PF', 'pf'), ('PTS', 'pts')):
        played[dst] = pd.to_numeric(played[src], errors='coerce')
    played = played[played['pts'].notna()]                      # a game he's credited with playing
    keys = ['Player Reference', 'season', 'Team']
    grp = played.groupby(keys)
    out = grp[['mp'] + COUNT_STATS].sum(min_count=1)
    out['g'] = grp.size()
    for s in REC_STATS:
        out[f'g_{s}'] = grp[s].count()
    out = out.reset_index().rename(columns={'Player Reference': 'player_id', 'Team': 'team'})
    out['mp'] = out['mp'].round(1)
    out['source'] = 'box'

    if DC:
        ext_pp, srows = deocheng_player_playoffs(DC)
        # cross-check the series totals against gonzalo's box scores for the season they share
        mine = out[out.season == SLICE_FROM].set_index(['player_id', 'team'])
        theirs = ext_pp[ext_pp.season == SLICE_FROM].set_index(['player_id', 'team'])
        both = mine.index.intersection(theirs.index)
        print(f'{SLICE_FROM} playoff totals, gonzalo box scores vs. Deo Cheng series table: {len(both)} players in both '
              f'(gonzalo {len(mine)}, deocheng {len(theirs)}); games equal {(mine.loc[both, "g"] == theirs.loc[both, "g"]).mean():.1%}, '
              f'points equal {(mine.loc[both, "pts"] == theirs.loc[both, "pts"]).mean():.1%}, rebounds equal '
              f'{((mine.loc[both, "trb"] == theirs.loc[both, "trb"]) | mine.loc[both, "trb"].isna()).mean():.1%}')
        out = extend_player_playoffs(out, DC)
        # champions' rosters for the new seasons: everyone with a series row for the champion
        new_titles = []
        for season, champ in champs.items():
            if season > SLICE_FROM:
                ids = srows[(srows.season_end == season) & (srows.team_abbr == champ)]['player_id'].unique()
                new_titles += [{'player_id': pid, 'season': season, 'team': champ} for pid in ids]
        titles = pd.concat([titles, pd.DataFrame(new_titles)], ignore_index=True)
        titles, rec = reconcile_titles(titles, dict(champs), DC)
        print(f'rings audited against official "Nx NBA Champ" counts: {rec["equal"]} of {rec["compared"]} players match exactly after '
              f'crediting {rec["added"]} rostered players the box scores miss; unresolved {len(rec["unresolved"])} players; over-credited {rec["over"]}')
        if rec['unresolved']:
            print('   unresolved (player, rings short):', rec['unresolved'][:12])

    write_outputs(ser, teams, out, titles)

    # ---- sanity checks against facts that can be looked up --------------------------------------
    n = titles.groupby('player_id').size()
    known = {'russebi01': 11, 'heinsto01': 8, 'joneskc01': 8, 'sandeto01': 8, 'ramsefr01': 7, 'jonessa01': 10, 'horryro01': 7, 'jordami01': 6, 'abdulka01': 6, 'johnsma02': 5,
             'bryanko01': 5, 'duncati01': 5, 'curryst01': 4, 'jamesle01': 4, 'onealsh01': 4, 'cousybo01': 6, 'havlijo01': 8}
    bad = {p: (int(n.get(p, 0)), want) for p, want in known.items() if int(n.get(p, 0)) != want}
    print('titles:', {p: int(n.get(p, 0)) for p in known})
    print('title-count mismatches vs. known:', bad or 'none')
    po_tot = played.groupby('Player Reference')[['pts', 'trb', 'ast']].sum()
    print('playoff career points: Jordan', int(po_tot.loc['jordami01', 'pts']), '(5,987), Kareem', int(po_tot.loc['abdulka01', 'pts']), '(5,762), '
          'LeBron', int(po_tot.loc['jamesle01', 'pts']))


# ======================================================================================
# Extension with the Deo Cheng slice (see scripts/extract_deocheng_slice.py)
#   - game results (dim_games): final scores matched gonzalo's schedule 100% on 2023-24, and include
#     the Game 7 gonzalo lacks, so series and champions are built from them for 2024 onward
#   - player_playoffs_series: series results (team, opponent, round, record), which matched gonzalo's 2024 series
#     15 of 15 (and include the Game 7 gonzalo lacks). Its per-player totals are incomplete, so they are only
#     used for the champion roster check below, never for stats.
#   - honors (player_career_honors): official "Nx NBA Champ" counts, used to audit rings and to credit
#     rostered players who never appear in a box score
# Its own player game log is NOT used: it's missing games and almost all playoff box scores.
# ======================================================================================
SLICE_FROM = 2024


def season_team_lookup():
    geo = json.loads((DATA / 'team_geo.json').read_text())
    c = geo['columns']
    rows = [dict(zip(c, r)) for r in geo['rows']]
    return ({(r['season'], r['team_name']): r['abbr'] for r in rows}, {(r['season'], r['abbr']) for r in rows})


ROUND_CODES = {  # code in player_playoffs_series -> (rounds from the final, round name); 4-round format since 1984
    'FIN': (0, 'Finals'), 'ECF': (1, 'Eastern Conference Finals'), 'WCF': (1, 'Western Conference Finals'),
    'ECS': (2, 'Eastern Conference Semifinals'), 'WCS': (2, 'Western Conference Semifinals'),
    'EC1': (3, 'Eastern Conference First Round'), 'WC1': (3, 'Western Conference First Round'),
}


def deocheng_series(dc: Path) -> pd.DataFrame:
    """Series from the player playoff-series table, which names both teams, the round and the result.
    (The games table's team names are unreliable for playoff games, so it isn't used for this.)"""
    import re
    names, abbrs = season_team_lookup()
    t = pd.read_csv(dc / 'public.player_playoffs_series.csv', low_memory=False)
    t = t[(t['lg'] == 'NBA') & (t['season_end'] >= SLICE_FROM) & (t['season_end'] <= 2030) & t['ps_round'].isin(ROUND_CODES)]
    u = t[['season_end', 'ps_round', 'team_abbr', 'opp_abbr', 'series_result']].drop_duplicates()
    rows, views = [], {}
    for r in u.itertuples():
        m = re.match(r'^([WL]) \((\d+)-(\d+)\)$', str(r.series_result).strip())
        if not m:
            raise SystemExit(f'unreadable series result {r.series_result!r} ({r.season_end} {r.team_abbr} vs {r.opp_abbr})')
        for abbr in (r.team_abbr, r.opp_abbr):
            if (r.season_end, abbr) not in abbrs:
                raise SystemExit(f'playoff team {abbr} in {r.season_end} is not in team_geo')
        won, lost = int(m.group(2)), int(m.group(3))
        assert (m.group(1) == 'W') == (won > lost), f'result letter disagrees with score: {r}'
        a, b = sorted((r.team_abbr, r.opp_abbr))
        wa, wb = (won, lost) if r.team_abbr == a else (lost, won)
        key = (r.season_end, r.ps_round, a, b)
        if key in views and views[key] != (wa, wb):
            raise SystemExit(f'the two teams disagree about the series {key}: {views[key]} vs {(wa, wb)}')
        if key in views:
            continue
        views[key] = (wa, wb)
        rff, name = ROUND_CODES[r.ps_round]
        rows.append({'season': int(r.season_end), 'round_name': name, 'round_label': ROUND_LABELS[rff], 'rff': rff, 'team_a': a, 'team_b': b,
                     'wins_a': wa, 'wins_b': wb, 'winner': a if wa > wb else b, 'games': wa + wb, 'start': None, 'end': None,
                     'complete': True, 'is_final': rff == 0})
    ser = pd.DataFrame(rows)
    for season, g in ser.groupby('season'):
        assert (g['rff'] == 0).sum() == 1, f'{season}: expected one Finals series'
    return ser


def deocheng_player_playoffs(dc: Path):
    s = pd.read_csv(dc / 'public.player_playoffs_series.csv', low_memory=False)
    s = s[(s['lg'] == 'NBA') & (s['season_end'] >= SLICE_FROM) & (s['season_end'] <= 2030)].copy()     # (1947-1999 rows carry a 2-digit-year bug)
    s['mp_total'] = s['mp_per_g'] * s['games']
    agg = s.groupby(['player_id', 'season_end', 'team_abbr']).agg(
        g=('games', 'sum'), mp=('mp_total', 'sum'), fg=('fg', 'sum'), fga=('fga', 'sum'), x3p=('fg3', 'sum'), x3pa=('fg3a', 'sum'),
        ft=('ft', 'sum'), fta=('fta', 'sum'), orb=('orb', 'sum'), drb=('drb', 'sum'), trb=('trb', 'sum'), ast=('ast', 'sum'),
        stl=('stl', 'sum'), blk=('blk', 'sum'), tov=('tov', 'sum'), pf=('pf', 'sum'), pts=('pts', 'sum')).reset_index()
    agg.columns = ['player_id', 'season', 'team'] + list(agg.columns[3:])
    agg['mp'] = agg['mp'].round(1)
    for stat in REC_STATS:
        agg[f'g_{stat}'] = agg['g']
    return agg, s


def extend_player_playoffs(out: pd.DataFrame, dc: Path) -> pd.DataFrame:
    """Player playoff seasons after the box scores end (2023-24):
      - from this project's game logs (data/games, built by prep_games.py) for seasons whose every playoff game is
        complete, i.e. its players' points add up to the final score (source 'game_log'). They have no minutes, and
        games rebuilt from play-by-play have no assists or offensive/defensive rebound split; per-game averages use
        only the games where a stat exists (g_ast etc.), like older eras.
      - the Deo Cheng series table (source 'series') is accurate for the players it lists (2024: 92% match the box scores
        exactly, the rest are a Game 7 the box scores lack; 2026: points match the game logs for every player) and has minutes,
        so its lines are preferred. It leaves out some rotation players: with game logs, those come from the logs; without
        (2024-25), that season is partial.
    """
    last = int(out['season'].max())
    series_pp, _ = deocheng_player_playoffs(dc)
    added = []
    seasons = sorted(set(series_pp['season']) | {int(f.name[6:10]) for f in (DATA / 'games').glob('games_*.csv.gz')})
    for season in [s for s in seasons if s > last]:
        gf, pf = DATA / 'games' / f'games_{season}.csv.gz', DATA / 'games' / f'player_games_{season}.csv.gz'
        po = pd.DataFrame()
        if gf.exists() and pf.exists():
            g = pd.read_csv(gf)
            po = g[g['playoffs'].astype(str) == 'True']
        if len(po) and po['complete'].astype(str).eq('True').all():
            pg = pd.read_csv(pf, low_memory=False)
            x = pg[pg['game_ref'].isin(po['game_ref']) & pg['pts'].notna()]
            grp = x.groupby(['player_id', 'team'])
            t = grp[['mp'] + COUNT_STATS].sum(min_count=1)
            t['g'] = grp.size()
            for s in REC_STATS:
                t[f'g_{s}'] = grp[s].count()
            t = t.reset_index().assign(season=season, source='game_log')
            mine = t.set_index(['player_id', 'team'])
            theirs = series_pp[series_pp['season'] == season].set_index(['player_id', 'team'])
            both = mine.index.intersection(theirs.index)
            pts_equal = (mine.loc[both, 'pts'] == theirs.loc[both, 'pts']).mean()
            print(f'{season} playoffs from game logs: {len(po)} complete games, {len(t)} players; vs. the series table '
                  f'({len(theirs)} players): games equal {(mine.loc[both, "g"] == theirs.loc[both, "g"]).mean():.1%}, '
                  f'points equal {pts_equal:.1%}')
            if pts_equal < 0.98:
                raise SystemExit(f'{season}: game-log playoff points disagree with the series table for {1 - pts_equal:.1%} of players')
            # The series table's lines are right for the players it lists and have minutes and every game played (the game
            # logs skip bench appearances with no stats), so they're used where they exist; the game logs fill in the
            # players it leaves out.
            from_series = series_pp[series_pp['season'] == season].assign(source='series')
            rest = t[~t.set_index(['player_id', 'team']).index.isin(from_series.set_index(['player_id', 'team']).index)]
            print(f'   using {len(from_series)} series-table lines and {len(rest)} game-log lines')
            added += [from_series, rest]
        elif season in set(series_pp['season']):
            t = series_pp[series_pp['season'] == season].assign(source='series')
            print(f'{season} playoffs: no complete game logs ({len(po)} games); {len(t)} players from the series table (partial)')
            added.append(t)
    if not added:
        return out
    new = pd.concat(added, ignore_index=True)
    if 'mp' in new:
        new['mp'] = new['mp'].round(1)
    return pd.concat([out, new[PLAYER_COLS]], ignore_index=True)

def reconcile_titles(titles: pd.DataFrame, champs: dict, dc: Path):
    """Credit rostered players the box scores miss, up to the official count, using regular-season team membership."""
    h = pd.read_csv(dc / 'public.player_career_honors.csv', low_memory=False)
    h = h[h['honor_type'] == 'nba_champ']
    official = h.assign(n=h['honor_count'].fillna(1)).groupby('player_id')['n'].sum().astype(int)
    ps = json.loads((DATA / 'player_seasons.json').read_text())
    c = ps['columns']
    stints = {(r[c.index('player_id')], r[c.index('season')]): r[c.index('team')] for r in ps['rows'] if r[c.index('team')] not in ('2TM', '3TM', '4TM', '5TM')}
    have = {(p, s) for p, s in zip(titles.player_id, titles.season)}
    count = titles.groupby('player_id').size()
    added, unresolved = [], []
    for pid, want in official.items():
        short = want - int(count.get(pid, 0))
        if short <= 0:
            continue
        cands = sorted(s for s, champ in champs.items() if (pid, s) not in have and stints.get((pid, s)) == champ)
        for s in cands[:short]:
            added.append({'player_id': pid, 'season': s, 'team': champs[s]})
        if len(cands) < short:
            unresolved.append((pid, short - len(cands)))
    out = pd.concat([titles, pd.DataFrame(added)], ignore_index=True) if added else titles
    final = out.groupby('player_id').size()
    cmp = official.to_frame('official').join(final.rename('mine')).fillna(0).astype(int)
    return out, {'added': len(added), 'unresolved': unresolved, 'compared': len(cmp), 'equal': int((cmp.official == cmp.mine).sum()),
                 'over': int((cmp.mine > cmp.official).sum()), 'cmp': cmp}


if __name__ == '__main__':
    main()
