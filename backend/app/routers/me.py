"""Signed-in user's favorites and saved comparisons, and public profiles."""
import re
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update

from .. import accounts_schema as a
from .. import schema as s
from ..db import get_conn, get_tx
from ..security import require_user
from .auth import public_user

router = APIRouter(tags=['accounts'])
Kind = Literal['player', 'team']


def _slug(name: str) -> str:
    return re.sub(r'^-|-$', '', re.sub(r'[^a-z0-9]+', '-', name.lower()))


def _franchise_slugs(conn) -> dict[str, str]:
    return {_slug(f): f for (f,) in conn.execute(select(s.team_seasons.c.franchise).distinct())}


def _check_ref(conn, kind: str, ref: str):
    if kind == 'player':
        if not conn.execute(select(s.players.c.player_id).where(s.players.c.player_id == ref)).first():
            raise HTTPException(404, f'No player with id {ref!r}')
    elif ref not in _franchise_slugs(conn):
        raise HTTPException(404, f'No franchise {ref!r}')


# ---- favorites -------------------------------------------------------------------------
@router.get('/me/favorites', summary='Your favorite players and teams')
def list_favorites(user=Depends(require_user), conn=Depends(get_conn)):
    rows = conn.execute(select(a.favorites).where(a.favorites.c.user_id == user['id'])
                        .order_by(a.favorites.c.created_at.desc())).mappings().all()
    players = {p['player_id']: p for p in conn.execute(
        select(s.players.c.player_id, s.players.c.player, s.players.c.first_season, s.players.c.last_season, s.players.c.hof)
        .where(s.players.c.player_id.in_([r['ref'] for r in rows if r['kind'] == 'player']))).mappings()}
    teams = _franchise_slugs(conn)
    out = {'players': [], 'teams': []}
    for r in rows:
        if r['kind'] == 'player' and r['ref'] in players:
            out['players'].append(dict(players[r['ref']]))
        elif r['kind'] == 'team' and r['ref'] in teams:
            out['teams'].append({'slug': r['ref'], 'franchise': teams[r['ref']]})
    return out


@router.put('/me/favorites/{kind}/{ref}', summary='Add a favorite')
def add_favorite(kind: Kind, ref: str, user=Depends(require_user), conn=Depends(get_tx)):
    _check_ref(conn, kind, ref)
    exists = conn.execute(select(a.favorites.c.id).where(
        a.favorites.c.user_id == user['id'], a.favorites.c.kind == kind, a.favorites.c.ref == ref)).first()
    if not exists:
        conn.execute(a.favorites.insert().values(user_id=user['id'], kind=kind, ref=ref, created_at=int(time.time())))
    return {'favorite': True}


@router.delete('/me/favorites/{kind}/{ref}', summary='Remove a favorite')
def remove_favorite(kind: Kind, ref: str, user=Depends(require_user), conn=Depends(get_tx)):
    conn.execute(delete(a.favorites).where(
        a.favorites.c.user_id == user['id'], a.favorites.c.kind == kind, a.favorites.c.ref == ref))
    return {'favorite': False}


# ---- saved comparisons -------------------------------------------------------------------
class ComparisonIn(BaseModel):
    kind: Literal['players', 'teams']
    a: str = Field(min_length=1, max_length=64)
    b: str = Field(min_length=1, max_length=64)
    params: str = Field('', max_length=300, description='View settings as a URL query string, e.g. basis=index&pos=5')
    title: str = Field(min_length=1, max_length=100)
    note: str = Field('', max_length=1000)
    is_public: bool = False


class ComparisonPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=100)
    note: str | None = Field(None, max_length=1000)
    is_public: bool | None = None


def _comparison_out(r) -> dict:
    out = {k: r[k] for k in ('id', 'kind', 'a', 'b', 'params', 'title', 'note', 'is_public', 'created_at')}
    out['path'] = f"/compare/{r['kind']}/{r['a']}/{r['b']}" + (f"?{r['params']}" if r['params'] else '')
    return out


@router.get('/me/comparisons', summary='Your saved comparisons')
def list_comparisons(user=Depends(require_user), conn=Depends(get_conn)):
    rows = conn.execute(select(a.saved_comparisons).where(a.saved_comparisons.c.user_id == user['id'])
                        .order_by(a.saved_comparisons.c.created_at.desc())).mappings().all()
    return [_comparison_out(r) for r in rows]


@router.post('/me/comparisons', status_code=201, summary='Save a comparison')
def save_comparison(body: ComparisonIn, user=Depends(require_user), conn=Depends(get_tx)):
    for ref in (body.a, body.b):
        _check_ref(conn, 'player' if body.kind == 'players' else 'team', ref)
    if not re.fullmatch(r'[A-Za-z0-9_=&.%-]*', body.params):
        raise HTTPException(422, 'params must be a plain query string')
    new_id = conn.execute(a.saved_comparisons.insert().values(
        user_id=user['id'], kind=body.kind, a=body.a, b=body.b, params=body.params, title=body.title.strip(),
        note=body.note.strip(), is_public=body.is_public, created_at=int(time.time()))).inserted_primary_key[0]
    return _comparison_out(conn.execute(select(a.saved_comparisons).where(a.saved_comparisons.c.id == new_id)).mappings().one())


@router.patch('/me/comparisons/{comparison_id}', summary='Edit a saved comparison')
def edit_comparison(comparison_id: int, body: ComparisonPatch, user=Depends(require_user), conn=Depends(get_tx)):
    t = a.saved_comparisons
    if not conn.execute(select(t.c.id).where(t.c.id == comparison_id, t.c.user_id == user['id'])).first():
        raise HTTPException(404, 'Comparison not found')
    values = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.model_dump(exclude_none=True).items()}
    if values:
        conn.execute(update(t).where(t.c.id == comparison_id).values(**values))
    return _comparison_out(conn.execute(select(t).where(t.c.id == comparison_id)).mappings().one())


@router.delete('/me/comparisons/{comparison_id}', status_code=204, summary='Delete a saved comparison')
def delete_comparison(comparison_id: int, user=Depends(require_user), conn=Depends(get_tx)):
    t = a.saved_comparisons
    if not conn.execute(select(t.c.id).where(t.c.id == comparison_id, t.c.user_id == user['id'])).first():
        raise HTTPException(404, 'Comparison not found')
    conn.execute(delete(t).where(t.c.id == comparison_id))


# ---- public profiles ---------------------------------------------------------------------
@router.get('/users/{username}', summary="A user's public profile: shared lineups and comparisons")
def profile(username: str, conn=Depends(get_conn)):
    user = conn.execute(select(a.users).where(a.users.c.username == username.lower())).mappings().first()
    if not user:
        raise HTTPException(404, 'No such user')
    lineups = conn.execute(select(a.lineups).where(a.lineups.c.user_id == user['id'], a.lineups.c.is_public.is_(True))
                           .order_by(a.lineups.c.updated_at.desc())).mappings().all()
    comps = conn.execute(select(a.saved_comparisons).where(
        a.saved_comparisons.c.user_id == user['id'], a.saved_comparisons.c.is_public.is_(True))
        .order_by(a.saved_comparisons.c.created_at.desc())).mappings().all()
    return {
        'user': public_user(user),
        'lineups': [{k: r[k] for k in ('id', 'name', 'description', 'overall', 'updated_at')} for r in lineups],
        'comparisons': [_comparison_out(r) for r in comps],
    }
