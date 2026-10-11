"""Salaries (1996-97 on) and current contracts (scripts/prep_salaries.py)."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, func, select

from .. import schema as s
from ..db import get_conn
from .teams import franchise_seasons

router = APIRouter(tags=['salaries'])


def contracts_info(conn) -> dict:
    raw = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'contracts')).scalar()
    return json.loads(raw) if raw else {}


def team_names(conn):
    """(season, abbreviation) -> (franchise, team name)."""
    ts = s.team_seasons
    return {(r.season, r.abbr): (r.franchise, r.team_name) for r in conn.execute(select(ts.c.season, ts.c.abbr, ts.c.franchise, ts.c.team_name))}


def contract_rows(conn, where):
    cs, c = s.contract_salaries, s.contracts
    rows = conn.execute(select(cs, c.c.player, c.c.guaranteed, c.c.two_way, c.c.notes)
                        .join(c, and_(c.c.player_id == cs.c.player_id, c.c.team == cs.c.team))
                        .where(where).order_by(cs.c.season)).mappings().all()
    out = {}
    for r in rows:
        k = (r['player_id'], r['team'])
        if k not in out:
            out[k] = {'player_id': r['player_id'], 'player': r['player'], 'team': r['team'], 'guaranteed': r['guaranteed'],
                      'two_way': r['two_way'], 'notes': json.loads(r['notes'] or '[]'), 'seasons': []}
        out[k]['seasons'].append({'season': r['season'], 'salary': r['salary'], 'option': r['option']})
    return list(out.values())


@router.get('/players/{player_id}/salaries', summary="A player's salary by season (1996-97 on) and his current contract")
def player_salaries(player_id: str, conn=Depends(get_conn)):
    if conn.execute(select(s.players.c.player_id).where(s.players.c.player_id == player_id)).first() is None:
        raise HTTPException(404, f'No player with id {player_id!r}')
    ps = s.player_salaries
    rows = [dict(r) for r in conn.execute(select(ps).where(ps.c.player_id == player_id).order_by(ps.c.season, ps.c.salary.desc())).mappings()]
    names = team_names(conn)
    seasons = sorted({r['season'] for r in rows})
    # league rank: where his total that season sits among every player's total
    totals = select(ps.c.season, ps.c.player_id, func.sum(ps.c.salary).label('total')).where(ps.c.season.in_(seasons)) \
        .group_by(ps.c.season, ps.c.player_id).subquery()
    ranks = {}
    for season, pid, total in conn.execute(select(totals.c.season, totals.c.player_id, totals.c.total)):
        ranks.setdefault(season, []).append((total, pid))
    by_season = []
    for season in seasons:
        mine = [r for r in rows if r['season'] == season]
        total = sum(r['salary'] for r in mine)
        field = ranks.get(season, [])
        by_season.append({
            'season': season, 'total': total,
            'rank': 1 + sum(1 for t, _ in field if t > total), 'players': len(field),
            'teams': [{'team': r['team'], 'franchise': names.get((season, r['team']), (None, None))[0],
                       'team_name': names.get((season, r['team']), (None, None))[1], 'salary': r['salary']} for r in mine],
        })
    info = contracts_info(conn)
    return {
        'player_id': player_id, 'seasons': by_season, 'career_earnings': sum(x['total'] for x in by_season),
        'first_season': seasons[0] if seasons else None,
        'contract': {'as_of': info.get('as_of'), 'season': info.get('season'),
                     'teams': contract_rows(conn, s.contract_salaries.c.player_id == player_id)},
    }


@router.get('/teams/{franchise}/salaries', summary="A franchise's payroll by season and its current salary sheet")
def team_salaries(franchise: str, conn=Depends(get_conn)):
    seasons = franchise_seasons(conn, franchise)
    abbr_by_season = {r['season']: r['abbr'] for r in seasons}
    ps, cs = s.player_salaries, s.contract_salaries
    info = contracts_info(conn)
    current = info.get('season') or 10 ** 4
    # Past seasons: the salary history. The current season on: the team's contract sheet, which
    # (unlike the history) also counts signees who haven't played yet, so it matches the official payroll.
    payroll = []
    hist = conn.execute(select(ps.c.season, ps.c.team, func.sum(ps.c.salary), func.count())
                        .where(ps.c.season < current).group_by(ps.c.season, ps.c.team)).all()
    for season, team, total, n in hist:
        if abbr_by_season.get(season) == team:
            payroll.append({'season': season, 'total': int(total), 'players': n, 'kind': 'paid'})
    avg = {season: int(total / n) for season, total, n in conn.execute(
        select(ps.c.season, func.sum(ps.c.salary), func.count(func.distinct(ps.c.team))).where(ps.c.season < current).group_by(ps.c.season))}
    sheet = []
    if abbr_by_season.get(current):
        abbr = abbr_by_season[current]
        sheet = contract_rows(conn, cs.c.team == abbr)
        sheet.sort(key=lambda c: -next((x['salary'] for x in c['seasons'] if x['season'] == current), 0))
        sums = conn.execute(select(cs.c.season, func.sum(cs.c.salary), func.count()).where(cs.c.team == abbr)
                            .group_by(cs.c.season).order_by(cs.c.season)).all()
        payroll += [{'season': season, 'total': int(total), 'players': n, 'kind': 'paid' if season == current else 'committed'}
                    for season, total, n in sums]
        league = conn.execute(select(func.sum(cs.c.salary), func.count(func.distinct(cs.c.team))).where(cs.c.season == current)).one()
        if league[1]:
            avg[current] = int(league[0] / league[1])
    for p in payroll:
        p['league_avg'] = avg.get(p['season']) if p['kind'] == 'paid' else None
    payroll.sort(key=lambda p: p['season'])
    rules = (info.get('rules') or {}).get(str(current))
    return {'franchise': franchise, 'as_of': info.get('as_of'), 'season': info.get('season'), 'rules': rules,
            'payroll': payroll, 'sheet': sheet}
