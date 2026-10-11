"""Playoffs and championships: team history, player playoff stats, champions list, playoff leaders."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select

from .. import schema as s
from ..db import get_conn
from ..util import fetch_all, normalize_name

router = APIRouter(tags=['playoffs'])
PO = s.player_playoffs


def team_names(conn):
    """(season, team abbreviation) -> that season's team name."""
    return {(r.season, r.abbr): r.team_name for r in conn.execute(select(s.team_seasons.c.season, s.team_seasons.c.abbr, s.team_seasons.c.team_name))}


def ratio(num, den, digits=3):
    return round(num / den, digits) if num is not None and den else None


def lines(r, per=1):
    """Per-game and shooting lines from one row of totals (a season, or summed across a career)."""
    g = r['g']
    avg = lambda total, rec: round(total / rec, 1) if total is not None and rec else None
    fga, fta = r.get('fga'), r.get('fta')
    ts = ratio(r.get('pts'), 2 * (fga + 0.44 * fta)) if fga is not None and fta is not None and (fga or fta) else None
    return {
        'g': g, 'mpg': avg(r.get('mp'), r.get('g_mp')), 'ppg': avg(r.get('pts'), g), 'rpg': avg(r.get('trb'), r.get('g_trb')),
        'apg': avg(r.get('ast'), r.get('g_ast')), 'spg': avg(r.get('stl'), r.get('g_stl')), 'bpg': avg(r.get('blk'), r.get('g_blk')),
        'fg_pct': ratio(r.get('fg'), r.get('fga')), 'x3p_pct': ratio(r.get('x3p'), r.get('x3pa')),
        'ft_pct': ratio(r.get('ft'), r.get('fta')), 'ts_pct': ts,
        'pts': r.get('pts'), 'trb': r.get('trb'), 'ast': r.get('ast'), 'stl': r.get('stl'), 'blk': r.get('blk'), 'x3p': r.get('x3p'),
    }


@router.get('/players/{player_id}/playoffs', summary="A player's playoff seasons, career line and championships")
def player_playoffs(player_id: str, conn=Depends(get_conn)):
    if conn.execute(select(s.players.c.player_id).where(s.players.c.player_id == player_id)).first() is None:
        raise HTTPException(404, f'No player with id {player_id!r}')
    names = team_names(conn)
    rows = fetch_all(conn, select(PO).where(PO.c.player_id == player_id).order_by(PO.c.season, PO.c.team))
    results = {(r.season, r.team): r.result for r in conn.execute(
        select(s.playoff_teams.c.season, s.playoff_teams.c.team, s.playoff_teams.c.result).where(s.playoff_teams.c.season.in_({r['season'] for r in rows})))}
    seasons = [{'season': r['season'], 'team': r['team'], 'team_name': names.get((r['season'], r['team'])),
                'result': results.get((r['season'], r['team'])), **lines(r)} for r in rows]
    totals = {k: sum(r[k] for r in rows if r[k] is not None) if any(r[k] is not None for r in rows) else None
              for k in ('g', 'mp', 'fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'trb', 'ast', 'stl', 'blk', 'pts', 'g_mp', 'g_trb', 'g_ast', 'g_stl', 'g_blk')}
    titles = [dict(r) for r in conn.execute(select(s.player_titles.c.season, s.player_titles.c.team, s.player_titles.c.franchise)
                                            .where(s.player_titles.c.player_id == player_id).order_by(s.player_titles.c.season)).mappings()]
    for t in titles:
        t['team_name'] = names.get((t['season'], t['team']))
    fm = [r.season for r in conn.execute(select(s.finals_mvp.c.season).where(s.finals_mvp.c.player_id == player_id).order_by(s.finals_mvp.c.season))]
    return {'player_id': player_id, 'titles': titles, 'finals_mvp_seasons': fm, 'seasons': seasons, 'career': lines(totals) if rows else None}


@router.get('/teams/{franchise}/playoffs', summary="A franchise's playoff history: titles, finals, every season's result")
def team_playoffs(franchise: str, conn=Depends(get_conn)):
    if conn.execute(select(s.team_seasons.c.season).where(s.team_seasons.c.franchise == franchise).limit(1)).first() is None:
        raise HTTPException(404, f'No franchise named {franchise!r}')
    names = team_names(conn)
    pt = s.playoff_teams
    seasons = [dict(r) for r in conn.execute(select(pt).where(pt.c.franchise == franchise).order_by(pt.c.season)).mappings()]
    for r in seasons:
        r['team_name'] = names.get((r['season'], r['team']))
        r.pop('franchise')
    titles = [r['season'] for r in seasons if r['champion']]
    finals = [r for r in seasons if r['rff_deepest'] == 0]
    series = [dict(r) for r in conn.execute(select(s.playoff_series).where(
        (s.playoff_series.c.franchise_a == franchise) | (s.playoff_series.c.franchise_b == franchise)).order_by(s.playoff_series.c.season, s.playoff_series.c.start)).mappings()]
    mine = []
    for r in series:
        a = r['franchise_a'] == franchise
        won, lost = (r['wins_a'], r['wins_b']) if a else (r['wins_b'], r['wins_a'])
        mine.append({'season': r['season'], 'round': r['round_name'], 'round_label': r['round_label'], 'rff': r['rff'],
                     'opponent': r['team_b'] if a else r['team_a'], 'opponent_name': names.get((r['season'], r['team_b'] if a else r['team_a'])),
                     'won': r['winner_franchise'] == franchise, 'wins': won, 'losses': lost, 'complete': r['complete']})
    return {
        'franchise': franchise, 'titles': titles, 'finals_appearances': len(finals), 'finals_losses': [r['season'] for r in finals if not r['champion']],
        'playoff_seasons': len(seasons), 'series_won': sum(1 for m in mine if m['won']), 'series_lost': sum(1 for m in mine if not m['won']),
        'seasons': seasons, 'series': mine,
    }


@router.get('/playoffs/champions', summary='Every champion, with the runner-up and Finals result')
def champions(response: Response, conn=Depends(get_conn)):
    response.headers['Cache-Control'] = 'public, max-age=3600'
    names = team_names(conn)
    sr = s.playoff_series
    mvp = {r.season: (r.player_id, r.player) for r in conn.execute(
        select(s.finals_mvp.c.season, s.finals_mvp.c.player_id, s.players.c.player).join(s.players, s.players.c.player_id == s.finals_mvp.c.player_id))}
    out = []
    for r in conn.execute(select(sr).where(sr.c.rff == 0).order_by(sr.c.season.desc())).mappings():
        a_won = r['winner'] == r['team_a']
        champ, other = (r['team_a'], r['team_b']) if a_won else (r['team_b'], r['team_a'])
        cf, of = (r['franchise_a'], r['franchise_b']) if a_won else (r['franchise_b'], r['franchise_a'])
        out.append({'season': r['season'], 'champion': names.get((r['season'], champ)), 'champion_abbr': champ, 'champion_franchise': cf,
                    'runner_up': names.get((r['season'], other)), 'runner_up_abbr': other, 'runner_up_franchise': of,
                    'wins': max(r['wins_a'], r['wins_b']), 'losses': min(r['wins_a'], r['wins_b']),
                    'finals_mvp': {'player_id': mvp[r['season']][0], 'player': mvp[r['season']][1]} if r['season'] in mvp else None})
    counts = {}
    for r in out:
        counts[r['champion_franchise']] = counts.get(r['champion_franchise'], 0) + 1
    return {'champions': out, 'titles_by_franchise': dict(sorted(counts.items(), key=lambda kv: -kv[1]))}


PLAYOFF_LEADER_STATS = ['pts', 'trb', 'ast', 'stl', 'blk', 'x3p', 'g', 'ppg', 'rpg', 'apg', 'titles']


@router.get('/leaders/playoffs', summary='Career playoff leaderboard')
def playoff_leaders(stat: str = Query('pts', description=', '.join(PLAYOFF_LEADER_STATS)), era: str = 'all', q: str = '',
                    limit: int = Query(100, ge=1, le=500), order: Literal['desc', 'asc'] = 'desc', conn=Depends(get_conn)):
    if stat not in PLAYOFF_LEADER_STATS:
        raise HTTPException(400, f'stat must be one of: {", ".join(PLAYOFF_LEADER_STATS)}')
    p = s.players
    sums = {k: func.sum(PO.c[k]).label(k) for k in ('g', 'pts', 'trb', 'ast', 'stl', 'blk', 'x3p', 'g_trb', 'g_ast')}
    titles = select(func.count()).where(s.player_titles.c.player_id == PO.c.player_id).correlate(PO).scalar_subquery()
    stmt = (select(PO.c.player_id, p.c.player, p.c.hof, p.c.pos, func.min(PO.c.season).label('first_season'), func.max(PO.c.season).label('last_season'),
                   *sums.values(), titles.label('titles'))
            .join(p, p.c.player_id == PO.c.player_id).group_by(PO.c.player_id, p.c.player, p.c.hof, p.c.pos))
    if era != 'all':
        try:
            lo, hi = (int(x) for x in era.split('-'))
        except ValueError:
            raise HTTPException(400, "era must be 'all' or like 1990-2009")
        stmt = stmt.where(PO.c.season >= lo, PO.c.season <= hi)
    if q.strip():
        stmt = stmt.where(p.c.name_search.contains(normalize_name(q.strip()), autoescape=True))
    rows = []
    for r in conn.execute(stmt).mappings():
        r = dict(r)
        r['ppg'], r['rpg'], r['apg'] = (round(r['pts'] / r['g'], 1) if r['g'] else None, round(r['trb'] / r['g_trb'], 1) if r['g_trb'] else None,
                                        round(r['ast'] / r['g_ast'], 1) if r['g_ast'] else None)
        if stat in ('ppg', 'rpg', 'apg') and (r['g'] < 25 or r[stat] is None):      # averages need a real sample
            continue
        if r[stat] is None:
            continue
        r['value'] = r[stat]
        rows.append(r)
    rows.sort(key=lambda r: r['value'], reverse=(order == 'desc'))
    return [{'rank': i, **{k: v for k, v in r.items() if k not in ('g_trb', 'g_ast', 'value')}} for i, r in enumerate(rows[:limit], start=1)]
