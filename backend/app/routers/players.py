"""Player endpoints: search, career summaries, season stats, honors,
similar players, and the career leaderboard."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select

from .. import schema as s
from ..db import get_conn
from ..util import as_columns, by_player, fetch_all, fetch_one, normalize_name, table_columns

router = APIRouter(tags=['players'])

CAREER_COLUMNS = table_columns(s.players, exclude=('name_search',))
ADV_FIELDS = ['per', 'ts_pct', 'usg_pct', 'ws', 'ws_48', 'obpm', 'dbpm', 'bpm', 'vorp']
P100_FIELDS = ['pts', 'trb', 'ast', 'stl', 'blk', 'tov', 'o_rtg', 'd_rtg']
LEADER_STATS = ['pts', 'trb', 'ast', 'stl', 'blk', 'x3p', 'g', 'ppg', 'rpg', 'apg', 'ws', 'vorp', 'all_star']


def player_or_404(conn, player_id):
    return fetch_one(conn, select(s.players).where(s.players.c.player_id == player_id),
                     not_found=f'No player with id {player_id!r}')


def public(p):
    p = dict(p)
    p.pop('name_search', None)
    return p


def merged_seasons(conn, player_id):
    """One row per season (the combined row for traded players), with advanced
    stats merged in and per-100 stats nested, plus the per-team stints."""
    rows = by_player(conn, s.player_seasons, player_id)
    adv = {r['season']: r for r in by_player(conn, s.player_advanced, player_id)}
    p100 = {r['season']: r for r in by_player(conn, s.player_per100, player_id)}
    by_season = {}
    for r in rows:
        if r['season'] not in by_season or r['combined']:
            by_season[r['season']] = r
    seasons = []
    for season in sorted(by_season):
        row = {k: v for k, v in by_season[season].items() if k not in ('id', 'player_id')}
        a = adv.get(season, {})
        row.update({f: a.get(f) for f in ADV_FIELDS})
        row['per100'] = {f: p100[season][f] for f in P100_FIELDS} if season in p100 else None
        row['teams'] = [x['team'] for x in rows if x['season'] == season and not x['combined']]
        seasons.append(row)
    return seasons


@router.get('/players', summary='Search players by name')
def search_players(q: str = Query('', description='Name or part of a name; accents optional'),
                   limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                   conn=Depends(get_conn)):
    stmt = select(s.players).order_by(s.players.c.pts.desc().nulls_last()).limit(limit).offset(offset)
    if q.strip():
        stmt = stmt.where(s.players.c.name_search.contains(normalize_name(q.strip()), autoescape=True))
    return [public(p) for p in fetch_all(conn, stmt)]


@router.get('/players/index', summary='Every player\'s career summary (compact)')
def player_index(response: Response, format: Literal['columns', 'objects'] = 'columns',
                 conn=Depends(get_conn)):
    """All ~5,100 players in one response. `columns` format (default) is what
    the dashboard loads at startup for search and leaderboards."""
    response.headers['Cache-Control'] = 'public, max-age=3600'
    rows = fetch_all(conn, select(s.players).order_by(s.players.c.player_id))
    return as_columns(rows, CAREER_COLUMNS) if format == 'columns' else [public(r) for r in rows]


@router.get('/leaders', summary='Career leaderboard')
def leaders(stat: str = Query('pts', description=', '.join(LEADER_STATS)),
            era: str = Query('all', description="'all' or a season range like 1990-2009"),
            q: str = '', limit: int = Query(100, ge=1, le=500), order: Literal['desc', 'asc'] = 'desc',
            conn=Depends(get_conn)):
    if stat not in LEADER_STATS:
        raise HTTPException(400, f'stat must be one of: {", ".join(LEADER_STATS)}')
    col = s.players.c[stat]
    stmt = select(s.players).where(s.players.c.g >= 1, col.is_not(None))
    if era != 'all':
        try:
            start, end = (int(x) for x in era.split('-'))
        except ValueError:
            raise HTTPException(400, "era must be 'all' or like 1990-2009")
        stmt = stmt.where(s.players.c.last_season >= start, s.players.c.first_season <= end)
    if q.strip():
        stmt = stmt.where(s.players.c.name_search.contains(normalize_name(q.strip()), autoescape=True))
    stmt = stmt.order_by(col.desc() if order == 'desc' else col.asc()).limit(limit)
    return [{'rank': i, **public(p)} for i, p in enumerate(fetch_all(conn, stmt), start=1)]


@router.get('/players/{player_id}', summary='Career summary, draft and All-Star seasons')
def get_player(player_id: str, conn=Depends(get_conn)):
    p = public(player_or_404(conn, player_id))
    drafts = by_player(conn, s.draft_picks, player_id)
    p['draft'] = {k: v for k, v in drafts[-1].items() if k not in ('id', 'player_id')} if drafts else None
    p['all_star_seasons'] = [r['season'] for r in by_player(conn, s.all_stars, player_id)]
    return p


@router.get('/players/{player_id}/seasons', summary='Season-by-season stats')
def player_seasons(player_id: str, conn=Depends(get_conn)):
    """Per-game box score with advanced metrics (PER, TS%, WS, BPM, VORP...)
    merged in and per-100-possession stats under `per100`."""
    player_or_404(conn, player_id)
    return merged_seasons(conn, player_id)


@router.get('/players/{player_id}/shooting', summary='Shot-zone profile by season (1997+)')
def player_shooting(player_id: str, conn=Depends(get_conn)):
    player_or_404(conn, player_id)
    return by_player(conn, s.player_shooting, player_id)


@router.get('/players/{player_id}/play-by-play', summary='Position mix, on/off and play-by-play stats (1997+)')
def player_pbp(player_id: str, conn=Depends(get_conn)):
    player_or_404(conn, player_id)
    return by_player(conn, s.player_pbp, player_id)


@router.get('/players/{player_id}/honors', summary='Awards, voting results, All-NBA teams and All-Star selections')
def player_honors(player_id: str, conn=Depends(get_conn)):
    player_or_404(conn, player_id)
    strip = lambda rows: [{k: v for k, v in r.items() if k not in ('id', 'player_id')} for r in rows]
    return {
        'awards': strip(by_player(conn, s.award_shares, player_id)),
        'all_league_teams': strip(by_player(conn, s.eos_teams, player_id)),
        'all_star_seasons': [r['season'] for r in by_player(conn, s.all_stars, player_id)],
        'title_seasons': [r['season'] for r in by_player(conn, s.player_titles, player_id)],
        'finals_mvp_seasons': [r.season for r in conn.execute(select(s.finals_mvp.c.season).where(s.finals_mvp.c.player_id == player_id).order_by(s.finals_mvp.c.season))],
    }


@router.get('/players/{player_id}/similar', summary='Most similar players across eras')
def player_similar(player_id: str, era: Literal['all', 'same'] = 'all',
                   limit: int = Query(8, ge=1, le=15), conn=Depends(get_conn)):
    """Matches on an era-relative style fingerprint. `era=same` keeps players
    whose career midpoint is within 10 seasons."""
    me = player_or_404(conn, player_id)
    style = conn.execute(select(s.player_style).where(s.player_style.c.player_id == player_id)).mappings().first()
    other = s.players.alias('other')
    stmt = (select(s.similar_players.c.score, other)
            .join(other, other.c.player_id == s.similar_players.c.similar_id)
            .where(s.similar_players.c.player_id == player_id)
            .order_by(s.similar_players.c.rank))
    matches = fetch_all(conn, stmt)
    if era == 'same':
        mid = (me['first_season'] + me['last_season']) / 2
        matches = [m for m in matches if abs((m['first_season'] + m['last_season']) / 2 - mid) <= 10]
    out = [{'score': m.pop('score'), **public(m)} for m in matches[:limit]]
    # each match's main playing styles (and the player's own), when the archetype model is loaded
    raw = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'archetype_model')).scalar()
    mine = []
    if raw:
        import json
        from .awards import career_mix
        by_id = {a['id']: a for a in json.loads(raw)['archetypes']}
        for m in out:
            m['styles'] = career_mix(conn, m['player_id'], by_id, limit=2)
        mine = career_mix(conn, player_id, by_id, limit=3)
    return {
        'fingerprint': {k: v for k, v in style.items() if k != 'player_id'} if style else None,
        'styles': mine,
        'matches': out,
    }


@router.get('/players/{player_id}/bundle', summary='Everything the dashboard needs for one player')
def player_bundle(player_id: str, conn=Depends(get_conn)):
    """Raw rows from every per-player table in one request: season stints
    (including combined rows), advanced, per-100, shooting, play-by-play,
    awards, All-NBA teams, All-Star selections, draft, and similarity."""
    p = public(player_or_404(conn, player_id))
    strip = lambda rows: [{k: v for k, v in r.items() if k != 'id'} for r in rows]
    style = conn.execute(select(s.player_style).where(s.player_style.c.player_id == player_id)).mappings().first()
    neighbors = fetch_all(conn, select(s.similar_players.c.similar_id, s.similar_players.c.score)
                          .where(s.similar_players.c.player_id == player_id).order_by(s.similar_players.c.rank))
    seasons = strip(by_player(conn, s.player_seasons, player_id))
    for r in seasons:
        r.pop('combined', None)
    return {
        'player': p,
        'seasons': seasons,
        'advanced': by_player(conn, s.player_advanced, player_id),
        'per100': by_player(conn, s.player_per100, player_id),
        'shooting': by_player(conn, s.player_shooting, player_id),
        'pbp': by_player(conn, s.player_pbp, player_id),
        'awards': strip(by_player(conn, s.award_shares, player_id)),
        'eos': strip(by_player(conn, s.eos_teams, player_id)),
        'all_stars': strip(by_player(conn, s.all_stars, player_id)),
        'draft': strip(by_player(conn, s.draft_picks, player_id)),
        'similar': {
            'features': [style[f] for f in s.STYLE_FEATURES] if style else None,
            'neighbors': [[n['similar_id'], n['score']] for n in neighbors],
        },
    }
