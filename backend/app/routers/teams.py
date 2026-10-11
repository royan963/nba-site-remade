"""Team / franchise endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func, select

from .. import schema as s
from ..db import get_conn
from ..util import as_columns, fetch_all, table_columns

router = APIRouter(tags=['teams'])
GEO_COLUMNS = table_columns(s.team_seasons, exclude=('id',))


def franchise_seasons(conn, franchise):
    rows = fetch_all(conn, select(s.team_seasons).where(s.team_seasons.c.franchise == franchise)
                     .order_by(s.team_seasons.c.season))
    if not rows:
        raise HTTPException(404, f'No franchise named {franchise!r} (see /api/v1/teams)')
    return rows


def roster_query(franchise, season=None):
    """Player stints whose team abbreviation matches the franchise that season."""
    ts, ps = s.team_seasons, s.player_seasons
    cond = [ts.c.franchise == franchise, ps.c.combined.is_(False)]
    if season is not None:
        cond.append(ps.c.season == season)
    return (select(ps).join(ts, and_(ts.c.abbr == ps.c.team, ts.c.season == ps.c.season))
            .where(*cond))


@router.get('/teams', summary='Every franchise lineage')
def list_teams(conn=Depends(get_conn)):
    ts = s.team_seasons
    rows = fetch_all(conn, select(
        ts.c.franchise, func.min(ts.c.season).label('first_season'), func.max(ts.c.season).label('last_season'),
        func.count().label('seasons'), func.sum(func.cast(ts.c.playoffs, s.Integer)).label('playoff_seasons'),
        func.sum(ts.c.w).label('wins'), func.sum(ts.c.l).label('losses'),
    ).group_by(ts.c.franchise).order_by(ts.c.franchise))
    latest = {r['franchise']: r for r in fetch_all(conn, select(ts).order_by(ts.c.season))}
    for r in rows:
        last = latest[r['franchise']]
        r.update({k: last[k] for k in ('current_name', 'status', 'team_name', 'abbr', 'primary_color',
                                        'secondary_color', 'badge_code', 'city')})
    return rows


@router.get('/teams/geo', summary='Every team-season with location and colors (compact)')
def team_geo(response: Response, conn=Depends(get_conn)):
    """What the dashboard's map loads at startup."""
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return as_columns(fetch_all(conn, select(s.team_seasons).order_by(s.team_seasons.c.season.desc())), GEO_COLUMNS)


@router.get('/teams/{franchise}/seasons', summary='Season-by-season record and ratings')
def team_seasons(franchise: str, conn=Depends(get_conn)):
    return [{k: v for k, v in r.items() if k != 'id'} for r in franchise_seasons(conn, franchise)]


@router.get('/teams/{franchise}/roster/{season}', summary='Roster and per-game stats for one season')
def roster(franchise: str, season: int, conn=Depends(get_conn)):
    franchise_seasons(conn, franchise)
    rows = fetch_all(conn, roster_query(franchise, season).order_by(s.player_seasons.c.pts.desc().nulls_last()))
    return [{k: v for k, v in r.items() if k not in ('id', 'combined')} for r in rows]


@router.get('/teams/{franchise}/honors', summary='Awards, All-NBA teams and All-Stars won by the roster')
def team_honors(franchise: str, season: int | None = Query(None, description='Omit for the whole franchise history'),
                conn=Depends(get_conn)):
    franchise_seasons(conn, franchise)
    rq = roster_query(franchise, season).subquery()
    on = lambda t: and_(t.c.player_id == rq.c.player_id, t.c.season == rq.c.season)
    strip = lambda rows: [{k: v for k, v in r.items() if k != 'id'} for r in rows]
    # ordered by season, then source order, so results match the static build
    wins = fetch_all(conn, select(s.award_shares).join(rq, on(s.award_shares))
                     .where(s.award_shares.c.winner.is_(True)).distinct().order_by(s.award_shares.c.season, s.award_shares.c.id))
    eos = fetch_all(conn, select(s.eos_teams).join(rq, on(s.eos_teams)).distinct().order_by(s.eos_teams.c.season, s.eos_teams.c.id))
    stars = fetch_all(conn, select(s.all_stars).join(rq, on(s.all_stars)).distinct().order_by(s.all_stars.c.season, s.all_stars.c.id))
    ids = {r['player_id'] for r in wins + eos + stars}
    names = dict(conn.execute(select(s.players.c.player_id, s.players.c.player)
                              .where(s.players.c.player_id.in_(ids))).all()) if ids else {}
    named = lambda rows: [{**r, 'player': names.get(r['player_id'])} for r in strip(rows)]
    return {'awards': named(wins), 'all_league_teams': named(eos), 'all_stars': named(stars)}
