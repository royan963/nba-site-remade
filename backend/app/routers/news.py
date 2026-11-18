"""Current NBA news (headlines from public RSS feeds), filterable by team or player. See backend/app/news.py."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select

from .. import news as N
from .. import schema as s
from ..db import get_conn

router = APIRouter(tags=['news'])
_tagger: dict = {}


def tagger(conn) -> N.Tagger:
    """Built once per data load from this season's teams and players."""
    loaded = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'loaded_at')).scalar()
    if _tagger.get('loaded') != loaded:
        ps, ts = s.player_seasons, s.team_seasons
        season = conn.execute(select(func.max(ps.c.season))).scalar()
        teams = [dict(r) for r in conn.execute(
            select(ts.c.abbr, ts.c.franchise, ts.c.team_name, ts.c.city).where(ts.c.season == season)).mappings()]
        rows = conn.execute(select(ps.c.player_id, ps.c.player, ps.c.team, ps.c.g, ps.c.mp)
                            .where(ps.c.season == season, ps.c.combined.is_(False), ps.c.g > 0)
                            .order_by(ps.c.player_id, ps.c.g.desc())).mappings()
        players = {}
        for r in rows:                                   # a traded player: the team he has played the most games for
            players.setdefault(r['player_id'], dict(r))
        _tagger.update(loaded=loaded, season=season, tagger=N.Tagger.build(teams, list(players.values())))
    return _tagger['tagger']


@router.get('/news', summary='Latest NBA headlines from ESPN, Yahoo Sports and CBS Sports, optionally for one team or player')
def news(response: Response, team: str | None = Query(None, description='Team abbreviation, e.g. SAS'),
         player: str | None = Query(None, description='Player id, e.g. wembavi01'), limit: int = Query(30, ge=1, le=100),
         conn=Depends(get_conn)):
    response.headers['Cache-Control'] = 'public, max-age=300'
    t = tagger(conn)
    if team and team.upper() not in t.teams:
        raise HTTPException(404, f'No current team {team!r}')
    if player and player not in t.players:
        raise HTTPException(404, f'No current player {player!r}')
    feed = N.latest()
    items = [t.tag(i) for i in feed['items']]
    if team:
        items = [i for i in items if any(x['abbr'] == team.upper() for x in i['teams'])]
    if player:
        items = [i for i in items if any(x['player_id'] == player for x in i['players'])]
    mentioned = {}
    for i in (t.tag(x) for x in feed['items']):
        for p in i['players']:
            mentioned.setdefault(p['player_id'], {**p, 'stories': 0})['stories'] += 1
    return {
        'updated_at': feed['at'], 'sources': feed['sources'],
        'teams': sorted(t.teams.values(), key=lambda x: x['team_name']),
        'players_in_news': sorted(mentioned.values(), key=lambda p: (-p['stories'], p['player']))[:40],
        'items': items[:limit],
    }
