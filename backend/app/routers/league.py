"""League-wide endpoints and dataset metadata."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select

from .. import schema as s
from ..db import get_conn
from ..util import fetch_all

router = APIRouter(tags=['league'])


def _cached(response):
    response.headers['Cache-Control'] = 'public, max-age=3600'


@router.get('/meta', summary='Season range, load time and row counts')
def meta(response: Response, conn=Depends(get_conn)):
    _cached(response)
    import json
    m = {r['key']: r['value'] for r in fetch_all(conn, select(s.meta))}
    return {
        'first_season': int(m['first_season']),
        'latest_season': int(m['latest_season']),
        'loaded_at': m['loaded_at'],
        'similarity_features': json.loads(m['similarity_features']),
        'players': conn.execute(select(func.count()).select_from(s.players)).scalar(),
        'playoffs_through': int(m.get('playoffs_through') or 0),
        'series_through': int(m.get('series_through') or 0),
    }


@router.get('/league/trends', summary='League-average pace, scoring and shooting by season')
def trends(response: Response, conn=Depends(get_conn)):
    _cached(response)
    return fetch_all(conn, select(s.league_trends).order_by(s.league_trends.c.season))


@router.get('/league/environment', summary='League per-36 rates and shooting by season (used for era adjustment)')
def environment(response: Response, conn=Depends(get_conn)):
    _cached(response)
    return fetch_all(conn, select(s.league_env).order_by(s.league_env.c.season))


@router.get('/league/shooting', summary='League-average shot-zone profile by season (1997+)')
def shooting(response: Response, conn=Depends(get_conn)):
    _cached(response)
    return fetch_all(conn, select(s.league_shooting).order_by(s.league_shooting.c.season))
