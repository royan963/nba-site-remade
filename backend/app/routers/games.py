"""Game-by-game: player game logs, career highs, and head-to-head for teams and players."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, case, func, or_, select

from .. import schema as s
from ..db import get_conn

router = APIRouter(tags=['games'])
G, PG = s.games, s.player_games
LINE = ['mp', 'pts', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'orb', 'drb', 'pm']
HIGH_STATS = ['pts', 'trb', 'ast', 'stl', 'blk', 'x3p', 'ft', 'fg']


class _Names(dict):
    """(season, abbreviation) -> team name; a season newer than the team data uses the team's latest name."""

    def __init__(self, rows):
        super().__init__(rows)
        self.last = max((k[0] for k in self), default=0)
        self.newest = {a: n for (_, a), n in sorted(self.items())}

    def get(self, key, default=None):
        if key in self:
            return self[key]
        return self.newest.get(key[1], default) if key[0] > self.last else default


def team_names(conn):
    return _Names({(r.season, r.abbr): r.team_name for r in conn.execute(select(s.team_seasons.c.season, s.team_seasons.c.abbr, s.team_seasons.c.team_name))})


def player_or_404(conn, pid):
    r = conn.execute(select(s.players.c.player_id, s.players.c.player).where(s.players.c.player_id == pid)).first()
    if r is None:
        raise HTTPException(404, f'No player with id {pid!r}')
    return r


def game_view(row, team, names):
    """Opponent, home/away and result from the player's side."""
    home = row['home'] == team
    opp = row['away'] if home else row['home']
    us, them = (row['home_pts'], row['away_pts']) if home else (row['away_pts'], row['home_pts'])
    return {'date': row['date'], 'game_ref': row['game_ref'], 'season': row['season'], 'playoffs': row['playoffs'], 'team': team,
            'opponent': opp, 'opponent_name': names.get((row['season'], opp)), 'home': home,
            'result': None if us is None or them is None else ('W' if us > them else 'L'), 'score': None if us is None else f'{us}-{them}',
            'ot': row['ot'] or 0}


_coverage_cache = {}


@router.get('/games/coverage', summary='Which seasons have game-by-game data, and where it is missing')
def coverage(response: Response, conn=Depends(get_conn)):
    response.headers['Cache-Control'] = 'public, max-age=3600'
    key = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'loaded_at')).scalar()   # changes only when the data reloads
    if key not in _coverage_cache:
        _coverage_cache.clear()
        _coverage_cache[key] = _coverage(conn)
    return _coverage_cache[key]


def _coverage(conn):
    rows = conn.execute(select(G.c.season, G.c.playoffs, func.count().label('games'), func.sum(case((G.c.complete, 1), else_=0)).label('complete'))
                        .group_by(G.c.season, G.c.playoffs)).mappings().all()
    have = {(r['season'], r['playoffs']): r for r in rows}
    series_seasons = [r for (r,) in conn.execute(select(s.playoff_series.c.season).distinct())]
    missing_playoffs = sorted(sn for sn in series_seasons if (sn, True) not in have)
    return {'seasons': [{'season': k[0], 'playoffs': k[1], 'games': v['games'], 'complete': int(v['complete'] or 0)} for k, v in sorted(have.items())],
            'missing_playoffs': missing_playoffs,
            'first_season': min(k[0] for k in have) if have else None, 'last_season': max(k[0] for k in have) if have else None}


@router.get('/players/{player_id}/gamelog', summary="A player's games in one season (regular season or playoffs)")
def gamelog(player_id: str, season: int | None = None, type: Literal['regular', 'playoffs'] = 'regular', conn=Depends(get_conn)):
    player_or_404(conn, player_id)
    seasons = [dict(r) for r in conn.execute(
        select(PG.c.season, func.sum(case((PG.c.kind == 'regular', 1), else_=0)).label('regular'), func.sum(case((PG.c.kind == 'playoffs', 1), else_=0)).label('playoffs'))
        .where(PG.c.player_id == player_id).group_by(PG.c.season).order_by(PG.c.season)).mappings()]
    if not seasons:
        return {'player_id': player_id, 'seasons': [], 'season': None, 'type': type, 'games': [], 'rebuilt_games': 0}
    if season is None:
        season = max(r['season'] for r in seasons if (r['playoffs'] if type == 'playoffs' else r['regular']))  if any(
            (r['playoffs'] if type == 'playoffs' else r['regular']) for r in seasons) else seasons[-1]['season']
    names = team_names(conn)
    q = (select(PG, G.c.date, G.c.home, G.c.away, G.c.home_pts, G.c.away_pts, G.c.ot)
         .join(G, G.c.game_ref == PG.c.game_ref)
         .where(PG.c.player_id == player_id, PG.c.season == season, PG.c.kind == ('playoffs' if type == 'playoffs' else 'regular')).order_by(G.c.date))
    games = []
    for r in conn.execute(q).mappings():
        games.append({**game_view(r, r['team'], names), **{k: r[k] for k in LINE}, 'started': r['started'], 'src': r['src']})
    return {'player_id': player_id, 'seasons': seasons, 'season': season, 'type': type, 'games': games,
            'rebuilt_games': sum(1 for g in games if g['src'] == 'dc_pbp')}


@router.get('/players/{player_id}/highs', summary='Career highs and milestone games')
def highs(player_id: str, type: Literal['regular', 'playoffs'] = 'regular', conn=Depends(get_conn)):
    """One query for all the player's games, then everything is computed from those rows (a career is at most ~1,600 games)."""
    player_or_404(conn, player_id)
    names = team_names(conn)
    rows = [dict(r) for r in conn.execute(
        select(PG, G.c.date, G.c.home, G.c.away, G.c.home_pts, G.c.away_pts, G.c.ot).join(G, G.c.game_ref == PG.c.game_ref)
        .where(PG.c.player_id == player_id, PG.c.kind == ('playoffs' if type == 'playoffs' else 'regular')).order_by(G.c.date)).mappings()]
    out = {}
    for stat in HIGH_STATS:
        vals = [r for r in rows if r[stat] is not None]
        if not vals:
            continue
        best = max(r[stat] for r in vals)
        if not best:
            continue
        first = next(r for r in vals if r[stat] == best)                 # rows are in date order: the earliest such game
        out[stat] = {'value': best, 'times': sum(1 for r in vals if r[stat] == best), **game_view(first, first['team'], names)}

    def tens(r):
        return sum(1 for k in ('pts', 'trb', 'ast', 'stl', 'blk') if (r[k] or 0) >= 10)
    with_ast = [r for r in rows if r['ast'] is not None]                 # doubles need assists recorded
    pts = lambda n: sum(1 for r in rows if (r['pts'] or 0) >= n)
    milestones = {'games': len(rows), 'pts30': pts(30), 'pts40': pts(40), 'pts50': pts(50),
                  'double_doubles': sum(1 for r in with_ast if tens(r) >= 2), 'triple_doubles': sum(1 for r in with_ast if tens(r) >= 3)}
    top = sorted((r for r in rows if r['pts'] is not None), key=lambda r: (-r['pts'], r['date']))[:10]
    return {'player_id': player_id, 'type': type, 'highs': out, 'milestones': milestones,
            'first_game': rows[0]['date'] if rows else None, 'last_game': rows[-1]['date'] if rows else None,
            'top_scoring_games': [{**game_view(r, r['team'], names), **{k: r[k] for k in LINE}} for r in top]}


@router.get('/head-to-head/teams', summary='Two franchises against each other: records, playoff series, recent games')
def h2h_teams(a: str, b: str, conn=Depends(get_conn)):
    if a == b:
        raise HTTPException(400, 'Pick two different franchises')
    for f in (a, b):
        if conn.execute(select(s.team_seasons.c.season).where(s.team_seasons.c.franchise == f).limit(1)).first() is None:
            raise HTTPException(404, f'No franchise named {f!r}')
    names = team_names(conn)
    rows = conn.execute(select(G).where(or_(and_(G.c.home_franchise == a, G.c.away_franchise == b),
                                            and_(G.c.home_franchise == b, G.c.away_franchise == a))).order_by(G.c.date)).mappings().all()
    def rec(sub):
        wa = sum(1 for r in sub if r['home_pts'] is not None and ((r['home_franchise'] == a) == (r['home_pts'] > r['away_pts'])))
        n = sum(1 for r in sub if r['home_pts'] is not None)
        pa = sum((r['home_pts'] if r['home_franchise'] == a else r['away_pts']) or 0 for r in sub)
        pb = sum((r['away_pts'] if r['home_franchise'] == a else r['home_pts']) or 0 for r in sub)
        return {'games': n, 'a_wins': wa, 'b_wins': n - wa, 'a_ppg': round(pa / n, 1) if n else None, 'b_ppg': round(pb / n, 1) if n else None}
    recent = []
    for r in rows[-12:][::-1]:
        a_home = r['home_franchise'] == a
        recent.append({'date': r['date'], 'season': r['season'], 'playoffs': r['playoffs'], 'kind': r['kind'], 'game_ref': r['game_ref'],
                       'a_team': names.get((r['season'], r['home'] if a_home else r['away'])), 'b_team': names.get((r['season'], r['away'] if a_home else r['home'])),
                       'a_pts': r['home_pts'] if a_home else r['away_pts'], 'b_pts': r['away_pts'] if a_home else r['home_pts'], 'a_home': a_home})
    sr = s.playoff_series
    series = [dict(r) for r in conn.execute(select(sr.c.season, sr.c.round_name, sr.c.franchise_a, sr.c.franchise_b, sr.c.wins_a, sr.c.wins_b, sr.c.winner_franchise)
                                             .where(or_(and_(sr.c.franchise_a == a, sr.c.franchise_b == b), and_(sr.c.franchise_a == b, sr.c.franchise_b == a)))
                                             .order_by(sr.c.season)).mappings()]
    series = [{'season': x['season'], 'round': x['round_name'], 'winner': x['winner_franchise'],
               'a_wins': x['wins_a'] if x['franchise_a'] == a else x['wins_b'], 'b_wins': x['wins_b'] if x['franchise_a'] == a else x['wins_a']} for x in series]
    return {'a': a, 'b': b, 'regular': rec([r for r in rows if r['kind'] == 'regular']), 'playoffs': rec([r for r in rows if r['kind'] == 'playoffs']),
            'series': series, 'series_a_won': sum(1 for x in series if x['winner'] == a), 'recent': recent,
            'first_meeting': rows[0]['date'] if rows else None}


@router.get('/head-to-head/players', summary='Two players in the games they faced each other')
def h2h_players(a: str, b: str, conn=Depends(get_conn)):
    if a == b:
        raise HTTPException(400, 'Pick two different players')
    pa_, pb_ = player_or_404(conn, a), player_or_404(conn, b)
    A, B = PG.alias('a'), PG.alias('b')
    q = (select(A.c.game_ref, A.c.team.label('a_team'), B.c.team.label('b_team'), A.c.playoffs, A.c.kind, G.c.date, G.c.season, G.c.home, G.c.away,
                G.c.home_pts, G.c.away_pts, *[A.c[k].label('a_' + k) for k in LINE], *[B.c[k].label('b_' + k) for k in LINE])
         .join(B, and_(B.c.game_ref == A.c.game_ref, B.c.player_id == b))
         .join(G, G.c.game_ref == A.c.game_ref).where(A.c.player_id == a).order_by(G.c.date))
    rows = conn.execute(q).mappings().all()
    vs = [r for r in rows if r['a_team'] != r['b_team'] and r['kind'] in ('regular', 'playoffs')]      # play-in and Cup final games don't count
    together = [r for r in rows if r['a_team'] == r['b_team'] and r['kind'] in ('regular', 'playoffs')]
    names = team_names(conn)

    def summary(sub):
        n = len(sub)
        def won(r):
            us = r['home_pts'] if r['home'] == r['a_team'] else r['away_pts']
            them = r['away_pts'] if r['home'] == r['a_team'] else r['home_pts']
            return us is not None and them is not None and us > them
        aw = sum(1 for r in sub if won(r))
        def avg(side, k):
            vals = [r[f'{side}_{k}'] for r in sub if r[f'{side}_{k}'] is not None]
            return round(sum(vals) / len(vals), 1) if vals else None
        return {'games': n, 'a_wins': aw, 'b_wins': n - aw,
                'a': {k: avg('a', k) for k in ('pts', 'trb', 'ast', 'stl', 'blk', 'x3p')}, 'b': {k: avg('b', k) for k in ('pts', 'trb', 'ast', 'stl', 'blk', 'x3p')}}
    meetings = []
    for r in vs[::-1][:15]:
        a_home = r['home'] == r['a_team']
        meetings.append({'date': r['date'], 'season': r['season'], 'playoffs': r['playoffs'], 'game_ref': r['game_ref'],
                         'a_team': names.get((r['season'], r['a_team'])), 'b_team': names.get((r['season'], r['b_team'])),
                         'a_score': r['home_pts'] if a_home else r['away_pts'], 'b_score': r['away_pts'] if a_home else r['home_pts'],
                         'a': {k: r['a_' + k] for k in ('pts', 'trb', 'ast')}, 'b': {k: r['b_' + k] for k in ('pts', 'trb', 'ast')}})
    return {'a': {'player_id': a, 'player': pa_.player}, 'b': {'player_id': b, 'player': pb_.player},
            'regular': summary([r for r in vs if not r['playoffs']]), 'playoffs': summary([r for r in vs if r['playoffs']]),
            'teammate_games': len(together), 'meetings': meetings}
