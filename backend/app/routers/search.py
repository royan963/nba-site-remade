"""Natural-language search over player-seasons and careers (see app/search.py)."""
import json
from typing import Literal

from fastapi import APIRouter, Depends, Query as Q
from sqlalchemy import and_, exists, func, or_, select

from .. import schema as s
from ..db import get_conn
from ..search import STAT_LABEL, drop_filters, parse
from ..util import normalize_name

router = APIRouter(tags=['search'])

PCT = {'fg_pct', 'x3p_pct', 'ft_pct', 'ts_pct'}
CAREER_LABEL = {'pts': 'Career points', 'trb': 'Career rebounds', 'ast': 'Career assists', 'stl': 'Career steals', 'blk': 'Career blocks',
                'x3pm': 'Career 3-pointers made', 'g': 'Career games', 'ws': 'Career Win Shares', 'vorp': 'Career VORP',
                'fg_pct': 'Career field goal %', 'x3p_pct': 'Career 3-point %', 'ft_pct': 'Career free throw %', 'ts_pct': 'Career true shooting %'}
EXAMPLES = ['best rebounding guards of the 90s', 'players who averaged 25 and 10 since 2010', 'top 10 three point shooters in 2016',
            'stretch bigs of the 2010s', 'rookies with the most points', 'efficient scorers under 25', '50/40/90 seasons',
            'Celtics leading scorers in the 80s', 'triple-double seasons', 'all-time leading scorers', 'MVPs since 2000',
            'most threes in the last 5 seasons', 'worst free throw shooters', 'best seasons by players over 35']


def vocab(conn):
    """Team aliases and archetype phrases, from the database."""
    names = [n for (n,) in conn.execute(select(s.team_seasons.c.team_name).distinct())]
    teams = {}
    for n in names:
        nick = n.split(' ')[-1].lower()
        if n.endswith('Trail Blazers'):
            nick = 'trail blazers'
        teams.setdefault(nick, []).append(n)
    for alias, target in {'sixers': '76ers', 'blazers': 'trail blazers', 'sonics': 'supersonics', 'cavs': 'cavaliers',
                          'mavs': 'mavericks', 'wolves': 'timberwolves', 't-wolves': 'timberwolves', 'nuggs': 'nuggets',
                          'dubs': 'warriors', 'knicks': 'knicks', 'pels': 'pelicans'}.items():
        if target in teams:
            teams[alias] = teams[target]
    raw = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'archetype_model')).scalar()
    archetypes = {}
    if raw:
        for a in json.loads(raw)['archetypes']:
            name = a['name'].lower()
            archetypes[name + 's'] = archetypes[name] = a['key']
        for alias, key in {'floor generals': 'floor-general', 'pass-first guards': 'floor-general', 'stretch fours': 'stretch-big',
                           'spot up shooters': 'spot-up-shooter', '3-and-d wings': 'spot-up-shooter', 'role players': 'role-player'}.items():
            archetypes[alias] = key
    latest = int(conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'latest_season')).scalar())
    return teams, archetypes, latest, (json.loads(raw)['archetypes'] if raw else [])


def _position_clause(col, codes):
    return or_(*[or_(col == c, col.like(f'{c}-%')) for c in codes])


def run_seasons(conn, q, archetypes_list):
    ps, p, adv, pa = s.player_seasons, s.players, s.player_advanced, s.player_archetypes
    expr = {k: ps.c[k] for k in ('pts', 'trb', 'ast', 'stl', 'blk', 'mp', 'g', 'fg_pct', 'x3p_pct', 'ft_pct', 'x3pa', 'fta')}
    expr['x3pm'] = ps.c.x3pa * ps.c.x3p_pct
    expr.update({k: adv.c[k] for k in ('ts_pct', 'per', 'ws', 'bpm', 'vorp')})
    rank = expr[q.stat]
    stmt = (select(ps.c.player_id, p.c.player, p.c.hof, ps.c.season, ps.c.age, ps.c.team, ps.c.pos, ps.c.g, ps.c.mp, ps.c.pts,
                   ps.c.trb, ps.c.ast, rank.label('value'), pa.c.archetype_id)
            .join(p, p.c.player_id == ps.c.player_id)
            .outerjoin(adv, and_(adv.c.player_id == ps.c.player_id, adv.c.season == ps.c.season))
            .outerjoin(pa, and_(pa.c.player_id == ps.c.player_id, pa.c.season == ps.c.season)))
    if q.teams:      # team-specific stints, not a traded player's combined line
        ts = s.team_seasons
        stmt = stmt.join(ts, and_(ts.c.abbr == ps.c.team, ts.c.season == ps.c.season)).where(ts.c.team_name.in_(q.teams), ps.c.combined.is_(False))
    else:            # one row per player-season: the combined row when he was traded
        ps2 = s.player_seasons.alias('ps2')
        stmt = stmt.where(or_(ps.c.combined.is_(True), ~exists().where(and_(ps2.c.player_id == ps.c.player_id, ps2.c.season == ps.c.season,
                                                                              ps2.c.combined.is_(True)))))
    cond = [rank.is_not(None)]
    # minimums so small samples don't win (and "worst" lists aren't all deep-bench players)
    if q.stat not in ('g',):
        cond.append(ps.c.g >= 40)
    if q.stat in ('fg_pct', 'ts_pct', 'per', 'bpm') or q.order == 'asc':
        cond.append(ps.c.mp >= 20)
    if q.stat == 'x3p_pct':
        cond.append(ps.c.x3pa >= 2.0)
    if q.stat == 'ft_pct':
        cond.append(ps.c.fta >= 3.0)
    if q.positions:
        cond.append(_position_clause(ps.c.pos, q.positions))
    if q.archetype:
        aid = next((a['id'] for a in archetypes_list if a['key'] == q.archetype), -1)
        cond.append(pa.c.archetype_id == aid)
    if q.season_from:
        cond.append(ps.c.season >= q.season_from)
    if q.season_to:
        cond.append(ps.c.season <= q.season_to)
    if q.age_min is not None:
        cond.append(ps.c.age >= q.age_min)
    if q.age_max is not None:
        cond.append(ps.c.age <= q.age_max)
    if q.rookie:
        cond.append(ps.c.season == p.c.first_season)
    if q.sophomore:
        cond.append(ps.c.season == p.c.first_season + 1)
    for stat, op, v in q.minimums:
        e = expr[stat]
        cond.append(e < v if op == '<' else e >= v)
        if stat == 'x3p_pct':
            cond.append(ps.c.x3pa >= 2.0)
        if stat == 'ft_pct':
            cond.append(ps.c.fta >= 2.0)
    aw, st, eos = s.award_shares, s.all_stars, s.eos_teams
    if 'mvp' in q.honors:
        cond.append(exists().where(and_(aw.c.player_id == ps.c.player_id, aw.c.season == ps.c.season, aw.c.award == 'nba mvp', aw.c.winner.is_(True))))
    if 'all_star' in q.honors:
        cond.append(exists().where(and_(st.c.player_id == ps.c.player_id, st.c.season == ps.c.season)))
    if 'all_nba' in q.honors:
        cond.append(exists().where(and_(eos.c.player_id == ps.c.player_id, eos.c.season == ps.c.season, eos.c.team_type == 'All-NBA')))
    if 'hof' in q.honors:
        cond.append(p.c.hof.is_(True))
    order = rank.asc() if q.order == 'asc' else rank.desc()
    rows = [dict(r) for r in conn.execute(stmt.where(*cond).order_by(order, ps.c.pts.desc()).limit(q.limit)).mappings()]
    names = {a['id']: (a['key'], a['name']) for a in archetypes_list}
    for r in rows:
        key, name = names.get(r.pop('archetype_id'), (None, None))
        r['archetype'], r['archetype_name'] = key, name
    return rows


def run_careers(conn, q, notes):
    p = s.players
    totals = {'pts': p.c.pts, 'trb': p.c.trb, 'ast': p.c.ast, 'stl': p.c.stl, 'blk': p.c.blk, 'x3pm': p.c.x3p, 'g': p.c.g,
              'ws': p.c.ws, 'vorp': p.c.vorp}
    pct = {'fg_pct': (p.c.fg / func.nullif(p.c.fga, 0), p.c.fga >= 2000), 'x3p_pct': (p.c.x3p / func.nullif(p.c.x3pa, 0), p.c.x3pa >= 500),
           'ft_pct': (p.c.ft / func.nullif(p.c.fta, 0), p.c.fta >= 500),
           'ts_pct': (p.c.pts / func.nullif(2 * (p.c.fga + 0.44 * p.c.fta), 0), p.c.fga >= 2000)}
    stat = q.stat
    if stat in ('per', 'bpm', 'mp'):
        notes.append(f'{STAT_LABEL[stat]} isn\u2019t available as a career total, so careers are ranked by Win Shares.')
        stat = 'ws'
    rank, cond = (pct[stat][0], [pct[stat][1]]) if stat in pct else (totals[stat], [])
    avg = {'pts': p.c.ppg, 'trb': p.c.rpg, 'ast': p.c.apg}
    for m_stat, op, v in q.minimums:
        if m_stat in avg:
            cond.append((avg[m_stat] < v) if op == '<' else (avg[m_stat] >= v))
            cond.append(p.c.g >= 100)
        elif m_stat in pct:
            cond += [pct[m_stat][0] >= v, pct[m_stat][1]]
    if q.positions:
        cond.append(_position_clause(p.c.pos, q.positions))
    if q.season_from:
        cond.append(p.c.last_season >= q.season_from)
    if q.season_to:
        cond.append(p.c.first_season <= q.season_to)
    aw, eos = s.award_shares, s.eos_teams
    if 'hof' in q.honors:
        cond.append(p.c.hof.is_(True))
    if 'all_star' in q.honors:
        cond.append(p.c.all_star >= 1)
    if 'mvp' in q.honors:
        cond.append(exists().where(and_(aw.c.player_id == p.c.player_id, aw.c.award == 'nba mvp', aw.c.winner.is_(True))))
    if 'all_nba' in q.honors:
        cond.append(exists().where(and_(eos.c.player_id == p.c.player_id, eos.c.team_type == 'All-NBA')))
    for what, active in (('age', q.age_min is not None or q.age_max is not None), ('rookie seasons', q.rookie or q.sophomore),
                         ('team', bool(q.teams)), ('playing style', bool(q.archetype))):
        if active:
            notes.append(f'The {what} filter applies to single seasons, so it was ignored for careers.')
    order = rank.asc() if q.order == 'asc' else rank.desc()
    stmt = (select(p.c.player_id, p.c.player, p.c.hof, p.c.pos, p.c.first_season, p.c.last_season, p.c.g, p.c.pts, p.c.trb, p.c.ast,
                   p.c.ppg, p.c.rpg, p.c.apg, rank.label('value'))
            .where(rank.is_not(None), p.c.g >= 1, *cond).order_by(order).limit(q.limit))
    return stat, [dict(r) for r in conn.execute(stmt).mappings()]


@router.get('/search', summary='Natural-language search: "best rebounding guards of the 90s"')
def search(q: str = Q(..., min_length=1, max_length=200), drop: list[int] = Q([], description='Indexes of filters to remove'),
           scope: Literal['seasons', 'careers'] | None = Q(None, description='Override seasons vs. careers'),
           conn=Depends(get_conn)):
    teams, archetypes, latest, archetypes_list = vocab(conn)
    query = parse(q, teams, archetypes, latest)
    if scope:
        query.scope = scope
        query.filters = [f for f in query.filters if f.kind != 'scope']
    drop_filters(query, drop)
    notes = []
    if query.scope == 'careers':
        stat, rows = run_careers(conn, query, notes)
    else:
        stat, rows = query.stat, run_seasons(conn, query, archetypes_list)

    label = CAREER_LABEL.get(stat, STAT_LABEL[stat]) if query.scope == 'careers' else STAT_LABEL[stat]
    for f in query.filters:
        if f.kind == 'stat':
            f.label = ('lowest ' if query.order == 'asc' else '') + label

    # a name, or nothing we recognized: also look for players by name
    names = []
    words = [w for w in normalize_name(q).split() if len(w) > 1]
    if not query.understood or (query.ignored and len(query.ignored) == len(words)):
        cond = [s.players.c.name_search.contains(w, autoescape=True) for w in words] or [s.players.c.player_id == '']
        names = [dict(r) for r in conn.execute(select(s.players.c.player_id, s.players.c.player, s.players.c.hof,
                                                      s.players.c.first_season, s.players.c.last_season)
                                               .where(*cond).order_by(s.players.c.pts.desc().nulls_last()).limit(8)).mappings()]
    if not query.understood:
        rows = []                      # a name, or nothing recognized: show players / examples, not a generic ranking
    return {
        'query': q, 'scope': query.scope, 'stat': stat, 'stat_label': label, 'stat_is_pct': stat in PCT, 'order': query.order,
        'filters': [{'index': f.index, 'kind': f.kind, 'label': f.label} for f in query.filters],
        'dropped': sorted(set(drop)),
        'ignored': query.ignored, 'notes': notes, 'understood': query.understood,
        'results': rows, 'name_matches': names, 'examples': EXAMPLES if not rows and not names else [],
        'season_note': 'Seasons are labeled by the year they ended: 2016 is the 2015-16 season.' if query.scope == 'seasons' else None,
    }
