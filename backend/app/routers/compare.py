"""Player comparison with career alignment and era adjustment."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from .. import era
from .. import schema as s
from ..db import get_conn
from ..util import by_player, fetch_all
from .players import merged_seasons, player_or_404, public

router = APIRouter(tags=['compare'])


AWARD_SHORT = {'nba mvp': 'MVP', 'nba dpoy': 'DPOY', 'nba mip': 'MIP', 'nba roy': 'ROY', 'nba smoy': '6MOY',
               'nba clutch_poy': 'Clutch POY', 'aba mvp': 'ABA MVP', 'aba roy': 'ABA ROY', 'baa roy': 'BAA ROY'}


def season_honors(conn, player_id):
    """season -> short labels for awards won, All-NBA/Defense teams and All-Star picks."""
    out = {}
    add = lambda season, label: out.setdefault(season, []).append(label)
    for r in by_player(conn, s.award_shares, player_id):
        if r['winner']:
            add(r['season'], AWARD_SHORT.get(r['award'], r['award']))
    for r in by_player(conn, s.eos_teams, player_id):
        add(r['season'], f"{r['team_type']} {r['team_number']}")
    for r in by_player(conn, s.all_stars, player_id):
        add(r['season'], 'All-Star')
    for r in by_player(conn, s.player_titles, player_id):
        add(r['season'], 'NBA Champion')
    for r in by_player(conn, s.finals_mvp, player_id):
        add(r['season'], 'Finals MVP')
    return out


def position_of(season_row, first_season, align):
    if align == 'experience':
        return season_row['season'] - first_season + 1
    if align == 'age':
        return season_row.get('age')
    return season_row['season']


@router.get('/compare/players', summary='Compare two players season by season')
def compare_players(
    a: str = Query(..., description='First player id, e.g. jamesle01'),
    b: str = Query(..., description='Second player id, e.g. jordami01'),
    align: Literal['experience', 'age', 'calendar'] = Query(
        'experience', description='Line careers up by year of career, by age, or by calendar season'),
    basis: Literal['raw', 'per100', 'index'] = Query(
        'raw', description='raw box score, per 100 possessions, or index vs league average (100 = average)'),
    position: int | None = Query(None, description='Return only this year / age / season'),
    conn=Depends(get_conn),
):
    if a == b:
        raise HTTPException(400, 'Pick two different players')
    env = {r['season']: r for r in fetch_all(conn, select(s.league_env))}
    sides = {}
    for key, pid in (('a', a), ('b', b)):
        p = public(player_or_404(conn, pid))
        rows = merged_seasons(conn, pid)
        sides[key] = {'player': p, 'by_pos': {}, 'honors': season_honors(conn, pid)}
        for r in rows:
            pos = position_of(r, p['first_season'], align)
            if pos is not None and pos not in sides[key]['by_pos']:
                sides[key]['by_pos'][pos] = r
    positions = sorted(set(sides['a']['by_pos']) | set(sides['b']['by_pos']))
    if position is not None:
        positions = [position] if position in positions else []

    def side(key, pos):
        r = sides[key]['by_pos'].get(pos)
        if r is None:
            return None
        e = env.get(r['season']) or {}
        return {'season': r['season'], 'age': r['age'], 'teams': r['teams'] or [r['team']],
                'experience': r['season'] - sides[key]['player']['first_season'] + 1,
                'raw': {k: r.get(k) for k in ('g', 'mp', 'pts', 'trb', 'ast')},
                'league': {'pace': e.get('pace'), 'ts_pct': e.get('ts_pct')},
                'honors': sides[key]['honors'].get(r['season'], []),
                'stats': era.compute(basis, r, e)}

    out = []
    for pos in positions:
        sa, sb = side('a', pos), side('b', pos)
        entry = {'position': pos, 'a': sa, 'b': sb}
        if sa and sb and sa['season'] == sb['season']:
            shared = sorted(set(sa['teams']) & set(sb['teams']))
            entry['same_season'] = {'teammates': bool(shared), 'shared_teams': shared}
        out.append(entry)
    return {
        'a': sides['a']['player'], 'b': sides['b']['player'],
        'align': align, 'basis': basis,
        'stats': [{'key': k, 'label': lbl, 'lower_is_better': k in era.LOWER_IS_BETTER}
                  for k, lbl, _ in era.stat_defs(basis)],
        'positions': out,
    }
