"""MVP predictor endpoints (model trained offline by scripts/train_mvp.py)."""
import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import and_, select

from .. import schema as s
from ..db import get_conn

router = APIRouter(tags=['models'])


def model_info(conn) -> dict:
    raw = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'mvp_model')).scalar()
    if not raw:
        raise HTTPException(404, 'MVP model results aren\u2019t in the database. Check that data/mvp_model.json exists '
                                 '(or create it with scripts/train_mvp.py), then run python -m backend.etl.load_db '
                                 'or restart the server.')
    return json.loads(raw)


@router.get('/models/mvp', summary='MVP model: accuracy, what it weighs, and the seasons it covers')
def mvp_model(response: Response, conn=Depends(get_conn)):
    response.headers['Cache-Control'] = 'public, max-age=3600'
    info = model_info(conn)
    ids = {m[k] for m in info['misses'] for k in ('predicted', 'actual')}
    names = dict(conn.execute(select(s.players.c.player_id, s.players.c.player).where(s.players.c.player_id.in_(ids))).all())
    seasons = [r for (r,) in conn.execute(select(s.mvp_candidates.c.season).distinct().order_by(s.mvp_candidates.c.season.desc()))]
    return {
        **{k: info[k] for k in ('metrics', 'importances', 'latest_season', 'latest_has_votes', 'games_rule_season', 'games_rule')},
        'preseason': info.get('preseason'),
        'progress': info.get('progress'),
        'misses': [{**m, 'predicted_name': names.get(m['predicted']), 'actual_name': names.get(m['actual'])} for m in info['misses']],
        'seasons': seasons,
    }


@router.get('/models/mvp/{season}', summary="One season's MVP race: the model's ranking next to the real vote")
def mvp_season(season: int, response: Response, view: str | None = None, conn=Depends(get_conn)):
    """view='preseason' picks the preseason race of a season that also has a live one."""
    response.headers['Cache-Control'] = 'public, max-age=3600'
    info = model_info(conn)
    pre = info.get('preseason')
    live = season == info['latest_season'] and not info['latest_has_votes']
    preseason = bool(pre) and season == pre['season'] and (view == 'preseason' or not live)
    # a preseason race has no games yet: show the season it was predicted from
    stats_season = pre['base_season'] if preseason else season
    c, p = s.mvp_candidates, s.players
    ps, adv = s.player_seasons, s.player_advanced
    # the season's per-game line: the combined row for traded players, else the only row
    stmt = (select(c, p.c.player, p.c.hof, p.c.pos, ps.c.pts, ps.c.trb, ps.c.ast, adv.c.per, adv.c.ws, adv.c.bpm, adv.c.vorp, ps.c.team.label('row_team'))
            .join(p, p.c.player_id == c.c.player_id)
            .join(ps, and_(ps.c.player_id == c.c.player_id, ps.c.season == stats_season))
            .outerjoin(adv, and_(adv.c.player_id == c.c.player_id, adv.c.season == stats_season))
            .where(c.c.season == season, c.c.kind == ('preseason' if preseason else 'prediction' if live else 'backtest'))
            .order_by(c.c.rank, ps.c.combined.desc()))
    rows, seen = [], set()
    for r in conn.execute(stmt).mappings():
        if r['player_id'] in seen:            # traded players have several rows; the combined one sorts first
            continue
        seen.add(r['player_id'])
        rows.append({k: v for k, v in r.items() if k != 'row_team'})
    if not rows:
        raise HTTPException(404, f'No MVP data for {season}')
    kind = 'preseason' if preseason else 'prediction' if live else 'backtest'
    return {'season': season, 'kind': kind, 'stats_season': stats_season, 'candidates': rows}


# ---- champion predictor ----------------------------------------------------------------
def champion_info(conn) -> dict:
    raw = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'champion_model')).scalar()
    if not raw:
        raise HTTPException(404, 'Champion model results aren’t in the database. Check that data/champion_model.json exists '
                                 '(or create it with scripts/train_champion.py), then run python -m backend.etl.load_db '
                                 'or restart the server.')
    return json.loads(raw)


@router.get('/models/champion', summary='Champion model: accuracy, what it weighs, and the seasons it covers')
def champion_model(response: Response, conn=Depends(get_conn)):
    response.headers['Cache-Control'] = 'public, max-age=3600'
    info = champion_info(conn)
    cc = s.champion_candidates
    seasons = [r for (r,) in conn.execute(select(cc.c.season).distinct().order_by(cc.c.season.desc()))]
    return {**{k: info[k] for k in ('metrics', 'weights', 'misses', 'latest_season', 'latest_has_champion', 'preseason')},
            'progress': info.get('progress'),
            'seasons': seasons}


@router.get('/models/champion/{season}', summary="Every team's title chances one season, next to what happened")
def champion_season(season: int, response: Response, view: str | None = None, conn=Depends(get_conn)):
    """view='preseason' picks the preseason odds of a season that also has live ones."""
    response.headers['Cache-Control'] = 'public, max-age=3600'
    info = champion_info(conn)
    cc, p = s.champion_candidates, s.players
    kinds = {k for (k,) in conn.execute(select(cc.c.kind).where(cc.c.season == season).distinct())}
    kind = 'preseason' if 'preseason' in kinds and (view == 'preseason' or len(kinds) == 1) else next(iter(kinds - {'preseason'}), None)
    rows = [dict(r) for r in conn.execute(
        select(cc, p.c.player.label('star')).outerjoin(p, p.c.player_id == cc.c.star_id)
        .where(cc.c.season == season, cc.c.kind == kind).order_by(cc.c.rank)).mappings()]
    if not rows:
        raise HTTPException(404, f'No champion predictions for {season}')
    pre = info.get('preseason')
    return {'season': season, 'kind': kind, 'stats_season': pre['base_season'] if kind == 'preseason' else season, 'teams': rows}


# ---- player archetypes ---------------------------------------------------------------
def archetype_info(conn) -> dict:
    raw = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'archetype_model')).scalar()
    if not raw:
        raise HTTPException(404, 'Archetype results aren\u2019t in the database. Check that data/archetypes.json exists '
                                 '(or create it with scripts/train_archetypes.py), then run python -m backend.etl.load_db '
                                 'or restart the server.')
    return json.loads(raw)


@router.get('/models/archetypes', summary='Player archetypes: the roles, what defines them, and their share of minutes by season')
def archetypes(response: Response, conn=Depends(get_conn)):
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return archetype_info(conn)


@router.get('/models/archetypes/{key}', summary="One role's player-seasons, most minutes first (optionally one decade)")
def archetype_players(key: str, decade: int | None = None, limit: int = 25, conn=Depends(get_conn)):
    info = archetype_info(conn)
    role = next((a for a in info['archetypes'] if a['key'] == key), None)
    if role is None:
        raise HTTPException(404, f'No archetype {key!r}')
    pa, p, ps = s.player_archetypes, s.players, s.player_seasons
    stmt = (select(pa.c.player_id, pa.c.season, pa.c.fit, pa.c.secondary_id, p.c.player, p.c.hof,
                   ps.c.pts, ps.c.trb, ps.c.ast, ps.c.mp, ps.c.g, ps.c.team, ps.c.combined)
            .join(p, p.c.player_id == pa.c.player_id)
            .join(ps, and_(ps.c.player_id == pa.c.player_id, ps.c.season == pa.c.season))
            .where(pa.c.archetype_id == role['id']))
    if decade is not None:
        stmt = stmt.where(pa.c.season >= decade, pa.c.season < decade + 10)
    rows, seen = [], set()
    for r in conn.execute(stmt.order_by((ps.c.mp * ps.c.g).desc(), ps.c.combined.desc())).mappings():
        if (r['player_id'], r['season']) in seen:          # traded players: keep the combined row
            continue
        seen.add((r['player_id'], r['season']))
        rows.append({k: v for k, v in r.items() if k != 'combined'})
        if len(rows) >= min(limit, 100):
            break
    names = {a['id']: a['name'] for a in info['archetypes']}
    for r in rows:
        r['secondary'] = names.get(r.pop('secondary_id'))
    return {'archetype': role, 'decade': decade, 'players': rows}


@router.get('/players/{player_id}/archetypes', summary="A player's role each season, and his main role")
def player_archetypes(player_id: str, conn=Depends(get_conn)):
    info = archetype_info(conn)
    by_id = {a['id']: a for a in info['archetypes']}
    pa, ps = s.player_archetypes, s.player_seasons
    rows = conn.execute(select(pa, ps.c.mp, ps.c.g).join(ps, and_(ps.c.player_id == pa.c.player_id, ps.c.season == pa.c.season))
                        .where(pa.c.player_id == player_id).order_by(pa.c.season, ps.c.combined.desc())).mappings().all()
    seasons, minutes, seen = [], {}, set()
    for r in rows:
        if r['season'] in seen:
            continue
        seen.add(r['season'])
        a, b = by_id[r['archetype_id']], by_id[r['secondary_id']]
        seasons.append({'season': r['season'], 'key': a['key'], 'name': a['name'], 'secondary_key': b['key'],
                        'secondary': b['name'], 'fit': r['fit'], 'features_used': r['features_used']})
        minutes[a['key']] = minutes.get(a['key'], 0) + (r['mp'] or 0) * (r['g'] or 0)
    # season and career style mixes
    sm = s.player_archetype_mix
    per_season = {}
    for r in conn.execute(select(sm).where(sm.c.player_id == player_id).order_by(sm.c.season, sm.c.share.desc())).mappings():
        a = by_id[r['archetype_id']]
        per_season.setdefault(r['season'], []).append({'key': a['key'], 'name': a['name'], 'share': r['share']})
    for x in seasons:
        x['mix'] = per_season.get(x['season'], [])[:3]
    mix = career_mix(conn, player_id, by_id)
    main = mix[0]['key'] if mix else (max(minutes, key=minutes.get) if minutes else None)
    return {'player_id': player_id, 'main': next(({'key': a['key'], 'name': a['name'], 'description': a['description']}
                                                   for a in info['archetypes'] if a['key'] == main), None),
            'mix': mix, 'seasons': seasons, 'features_total': len(info['method']['features'])}


def career_mix(conn, player_id, by_id, limit=None):
    cm = s.player_style_mix
    rows = conn.execute(select(cm).where(cm.c.player_id == player_id).order_by(cm.c.share.desc())).mappings().all()
    out = [{'key': by_id[r['archetype_id']]['key'], 'name': by_id[r['archetype_id']]['name'], 'share': r['share']} for r in rows]
    return out[:limit] if limit else out


# ---- career projections ------------------------------------------------------------------
def projection_info(conn) -> dict:
    raw = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'projection_model')).scalar()
    if not raw:
        raise HTTPException(404, 'Projection results aren\u2019t in the database. Check that data/projections.json exists '
                                 '(or create it with scripts/train_projections.py), then run python -m backend.etl.load_db '
                                 'or restart the server.')
    return json.loads(raw)


def season_so_far(conn, season: int, player_ids=None) -> dict:
    """Each player's line in a season under way: {player_id: {g, mp, pts, trb, ast, ts_pct, team}} (combined row for traded players)."""
    ps, adv = s.player_seasons, s.player_advanced
    stmt = (select(ps.c.player_id, ps.c.team, ps.c.g, ps.c.mp, ps.c.pts, ps.c.trb, ps.c.ast, adv.c.ts_pct)
            .outerjoin(adv, and_(adv.c.player_id == ps.c.player_id, adv.c.season == ps.c.season))
            .where(ps.c.season == season).order_by(ps.c.combined.desc()))
    if player_ids is not None:
        stmt = stmt.where(ps.c.player_id.in_(player_ids))
    out = {}
    for r in conn.execute(stmt).mappings():
        out.setdefault(r['player_id'], {**dict(r), 'season': season})
    return out


def vs_projection(proj: dict, now: dict | None) -> dict | None:
    """How a season so far compares with its projection: the difference and whether it's inside the 60% range."""
    if not now or not now.get('g'):
        return None
    out = {}
    for k in ('pts', 'trb', 'ast', 'mp'):
        if proj.get(k) is None or now.get(k) is None:
            continue
        out[k] = {'diff': round(now[k] - proj[k], 1),
                  'in_range': None if proj.get(f'{k}_lo') is None else proj[f'{k}_lo'] <= now[k] <= proj[f'{k}_hi']}
    return out


@router.get('/players/{player_id}/projection', summary="A current player's next three seasons, with ranges and comparables")
def player_projection(player_id: str, conn=Depends(get_conn)):
    info = projection_info(conn)
    pp, pc, p = s.player_projections, s.projection_comps, s.players
    rows = [dict(r) for r in conn.execute(select(pp).where(pp.c.player_id == player_id).order_by(pp.c.h)).mappings()]
    live = info.get('in_progress')
    if not rows:
        return {'player_id': player_id, 'projected': False, 'base_season': info['latest_season'], 'horizons': [], 'comps': [],
                'in_progress': live, 'so_far': None}
    comps = [dict(r) for r in conn.execute(
        select(pc.c.rank, pc.c.comp_id, pc.c.comp_season, pc.c.similarity, p.c.player, p.c.hof)
        .join(p, p.c.player_id == pc.c.comp_id).where(pc.c.player_id == player_id).order_by(pc.c.rank)).mappings()]
    for r in rows:
        r.pop('player_id')
    so_far = None
    if live:
        now = season_so_far(conn, live['season'], [player_id]).get(player_id)
        proj = next((r for r in rows if r['season'] == live['season']), None)
        if now and proj:
            so_far = {**now, 'vs': vs_projection(proj, now)}
    return {'player_id': player_id, 'projected': True, 'base_season': info['latest_season'], 'horizons': rows, 'comps': comps,
            'in_progress': live, 'so_far': so_far}


@router.get('/models/projections', summary='Projection model accuracy, plus the biggest projected risers and decliners')
def projections_model(response: Response, conn=Depends(get_conn)):
    response.headers['Cache-Control'] = 'public, max-age=3600'
    info = projection_info(conn)
    pp, p, ps = s.player_projections, s.players, s.player_seasons
    base = info['latest_season']
    stmt = (select(pp.c.player_id, pp.c.pts, pp.c.pts_lo, pp.c.pts_hi, pp.c.p_active, pp.c.age, p.c.player, p.c.hof,
                   ps.c.pts.label('now_pts'), ps.c.team, ps.c.combined)
            .join(p, p.c.player_id == pp.c.player_id)
            .join(ps, and_(ps.c.player_id == pp.c.player_id, ps.c.season == base))
            .where(pp.c.h == 1, pp.c.pts.is_not(None)).order_by(ps.c.combined.desc()))
    seen, rows = set(), []
    for r in conn.execute(stmt).mappings():
        if r['player_id'] in seen:
            continue
        seen.add(r['player_id'])
        rows.append({**{k: v for k, v in r.items() if k != 'combined'}, 'change': round(r['pts'] - r['now_pts'], 1)})
    eligible = [r for r in rows if (r['now_pts'] or 0) >= 8]          # meaningful roles only for risers/decliners
    # the season under way: who is beating or trailing his projection so far (regulars only)
    live, ahead, behind, tracked = info.get('in_progress'), [], [], None
    if live:
        now = season_so_far(conn, live['season'])
        proj = {r['player_id']: dict(r) for r in conn.execute(
            select(pp, p.c.player, p.c.hof).join(p, p.c.player_id == pp.c.player_id).where(pp.c.season == live['season'])).mappings()}
        min_g = max(3, live['team_games'] / 2)
        cmp = []
        for pid, pr in proj.items():
            n = now.get(pid)
            if not n or (n['g'] or 0) < min_g or (n['mp'] or 0) < 15 or pr['pts'] is None or n['pts'] is None:
                continue
            cmp.append({'player_id': pid, 'player': pr['player'], 'hof': pr['hof'], 'team': n['team'], 'g': n['g'],
                        'pts': n['pts'], 'proj_pts': pr['pts'], 'pts_lo': pr['pts_lo'], 'pts_hi': pr['pts_hi'],
                        'diff': round(n['pts'] - pr['pts'], 1), 'in_range': pr['pts_lo'] <= n['pts'] <= pr['pts_hi']})
        ahead = sorted(cmp, key=lambda r: -r['diff'])[:10]
        behind = sorted(cmp, key=lambda r: r['diff'])[:10]
        tracked = {'players': len(cmp), 'in_range': round(sum(r['in_range'] for r in cmp) / len(cmp), 3) if cmp else None, 'min_games': min_g}
    return {
        **info,
        'ahead': ahead, 'behind': behind, 'tracked': tracked,
        'top_scorers': sorted(rows, key=lambda r: -r['pts'])[:12],
        'risers': sorted(eligible, key=lambda r: -r['change'])[:10],
        'decliners': sorted(eligible, key=lambda r: r['change'])[:10],
    }
