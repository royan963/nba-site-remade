"""All-time lineup builder: score any five player-seasons; save and share lineups."""
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update

from .. import accounts_schema as a
from .. import lineup as model
from ..db import get_conn, get_tx
from ..security import current_user, require_user

router = APIRouter(tags=['lineups'])


class Pick(BaseModel):
    player_id: str = Field(max_length=16)
    season: int | None = Field(None, description="Omit to use the player's best season")


class ScoreRequest(BaseModel):
    players: list[Pick] = Field(min_length=1, max_length=5)


class LineupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field('', max_length=500)
    is_public: bool = False
    players: list[Pick] = Field(min_length=5, max_length=5)


def _score(conn, picks: list[Pick]) -> dict:
    try:
        return model.score_lineup(model.get_pool(conn), [(p.player_id, p.season) for p in picks])
    except ValueError as e:
        raise HTTPException(422, str(e))


def _lineup_out(conn, row, owner: dict | None = None) -> dict:
    picks = conn.execute(select(a.lineup_players).where(a.lineup_players.c.lineup_id == row['id'])
                         .order_by(a.lineup_players.c.slot)).mappings().all()
    if owner is None:
        owner = conn.execute(select(a.users.c.username, a.users.c.display_name)
                             .where(a.users.c.id == row['user_id'])).mappings().one()
    score = model.score_lineup(model.get_pool(conn), [(p['player_id'], p['season']) for p in picks])
    return {'id': row['id'], 'name': row['name'], 'description': row['description'], 'is_public': row['is_public'],
            'created_at': row['created_at'], 'updated_at': row['updated_at'],
            'owner': {'username': owner['username'], 'display_name': owner['display_name']}, 'score': score}


def _summary(row, owner=None) -> dict:
    out = {k: row[k] for k in ('id', 'name', 'description', 'is_public', 'overall', 'created_at', 'updated_at')}
    if owner:
        out['owner'] = owner
    return out


def _owned(conn, lineup_id: int, user: dict):
    row = conn.execute(select(a.lineups).where(a.lineups.c.id == lineup_id)).mappings().first()
    if not row or row['user_id'] != user['id']:
        raise HTTPException(404, 'Lineup not found')
    return row


@router.post('/lineups/score', summary='Score up to five player-seasons (no account needed)')
def score(body: ScoreRequest, conn=Depends(get_conn)):
    return _score(conn, body.players)


@router.get('/lineups/player-seasons/{player_id}', summary="A player's seasons with lineup ratings")
def player_seasons(player_id: str, conn=Depends(get_conn)):
    pool = model.get_pool(conn)
    if player_id not in pool.players:
        raise HTTPException(404, f'No player with id {player_id!r}')
    return {'player_id': player_id, 'best_season': model.best_season(pool, player_id),
            'seasons': model.player_seasons(pool, player_id)}


@router.get('/lineups/public', summary='Recently shared lineups')
def public_lineups(limit: int = Query(12, ge=1, le=50), conn=Depends(get_conn)):
    rows = conn.execute(select(a.lineups, a.users.c.username, a.users.c.display_name)
                        .join(a.users, a.users.c.id == a.lineups.c.user_id)
                        .where(a.lineups.c.is_public.is_(True))
                        .order_by(a.lineups.c.updated_at.desc()).limit(limit)).mappings().all()
    return [_summary(r, {'username': r['username'], 'display_name': r['display_name']}) for r in rows]


@router.post('/lineups', status_code=201, summary='Save a lineup')
def create_lineup(body: LineupIn, user=Depends(require_user), conn=Depends(get_tx)):
    result = _score(conn, body.players)
    now = int(time.time())
    lineup_id = conn.execute(a.lineups.insert().values(
        user_id=user['id'], name=body.name.strip(), description=body.description.strip(), is_public=body.is_public,
        overall=result['overall'], created_at=now, updated_at=now)).inserted_primary_key[0]
    conn.execute(a.lineup_players.insert(), [
        {'lineup_id': lineup_id, 'slot': i, 'player_id': p['player_id'], 'season': p['season']}
        for i, p in enumerate(result['players'], start=1)])
    return _lineup_out(conn, conn.execute(select(a.lineups).where(a.lineups.c.id == lineup_id)).mappings().one(), user)


@router.get('/lineups/{lineup_id}', summary='A saved lineup with its live score')
def get_lineup(lineup_id: int, user=Depends(current_user), conn=Depends(get_conn)):
    row = conn.execute(select(a.lineups).where(a.lineups.c.id == lineup_id)).mappings().first()
    if not row or (not row['is_public'] and (user is None or user['id'] != row['user_id'])):
        raise HTTPException(404, 'Lineup not found')        # private lineups look like they don't exist
    out = _lineup_out(conn, row)
    out['mine'] = user is not None and user['id'] == row['user_id']
    return out


@router.put('/lineups/{lineup_id}', summary='Update a saved lineup')
def update_lineup(lineup_id: int, body: LineupIn, user=Depends(require_user), conn=Depends(get_tx)):
    _owned(conn, lineup_id, user)
    result = _score(conn, body.players)
    conn.execute(update(a.lineups).where(a.lineups.c.id == lineup_id).values(
        name=body.name.strip(), description=body.description.strip(), is_public=body.is_public,
        overall=result['overall'], updated_at=int(time.time())))
    conn.execute(delete(a.lineup_players).where(a.lineup_players.c.lineup_id == lineup_id))
    conn.execute(a.lineup_players.insert(), [
        {'lineup_id': lineup_id, 'slot': i, 'player_id': p['player_id'], 'season': p['season']}
        for i, p in enumerate(result['players'], start=1)])
    return _lineup_out(conn, conn.execute(select(a.lineups).where(a.lineups.c.id == lineup_id)).mappings().one(), user)


@router.delete('/lineups/{lineup_id}', status_code=204, summary='Delete a saved lineup')
def delete_lineup(lineup_id: int, user=Depends(require_user), conn=Depends(get_tx)):
    _owned(conn, lineup_id, user)
    conn.execute(delete(a.lineups).where(a.lineups.c.id == lineup_id))


@router.get('/me/lineups', summary='Your saved lineups')
def my_lineups(user=Depends(require_user), conn=Depends(get_conn)):
    rows = conn.execute(select(a.lineups).where(a.lineups.c.user_id == user['id'])
                        .order_by(a.lineups.c.updated_at.desc())).mappings().all()
    return [_summary(r) for r in rows]
