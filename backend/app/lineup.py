"""All-time lineup scoring.

A playful model, not a prediction: it rates five player-seasons from any era
on the same scale by comparing every stat to its own season's league.

1. Each player-season gets percentiles against a pool of qualified seasons
   (40+ games and 1,200+ minutes; minutes weren't recorded before 1951-52):
   - talent: average z-score of the impact metrics the season has (BPM from
     1973-74, WS/48 and PER from 1951-52, Win Shares per game always), shrunk
     toward average for small samples
   - per-36 scoring, playmaking, rebounding, steal and block rates vs league
   - efficiency (TS% vs league), spacing (3PA rate vs league + 3P% vs league,
     from 1979-80), defense (steals, blocks, defensive BPM)
2. The lineup gets category scores (top-heavy where only one player needs the
   skill, e.g. playmaking), a fit score (ball-dominance overlap via usage,
   having a big and a ball handler), and an overall 0-100.
Missing data counts as league average and is listed in `notes`.
"""
import bisect
import math
from statistics import fmean, pstdev

from sqlalchemy import select

from . import schema as s

MULTITEAM = {'2TM', '3TM', '4TM', '5TM'}
TALENT_METRICS = ('bpm', 'ws_48', 'per', 'ws_pg')
CATEGORY_WEIGHTS = {'talent': 0.45, 'scoring': 0.12, 'playmaking': 0.10, 'rebounding': 0.08,
                    'defense': 0.10, 'spacing': 0.08, 'efficiency': 0.07}
# Grades come from where a score ranks among real NBA starting fives (each
# team-season's five highest-minute players, 1951-52 onward).
GRADES = [(99, 'All-time great'), (90, 'Title favorite'), (70, 'Contender'), (40, 'Playoff team'), (0, 'Lottery team')]
LABELS = {'talent': 'Talent', 'scoring': 'Scoring', 'playmaking': 'Playmaking', 'rebounding': 'Rebounding',
          'defense': 'Defense', 'spacing': 'Shooting & spacing', 'efficiency': 'Efficiency', 'fit': 'Fit'}


def _num(v):
    return v if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)) else None


def _ratio(v, base):
    v, base = _num(v), _num(base)
    return v / base if v is not None and base else None


class Pool:
    """Season features plus sorted distributions for percentiles."""

    def __init__(self, seasons: dict, players: dict):
        self.seasons, self.players = seasons, players
        self.real_scores: list[float] = []
        qualified = [f for f in seasons.values() if f['qualified']]
        self.z = {}
        for m in TALENT_METRICS:
            vals = [f[m] for f in qualified if f[m] is not None]
            self.z[m] = (fmean(vals), pstdev(vals) or 1.0)
        for f in seasons.values():
            f['talent_raw'] = self._talent_raw(f)
        self.sorted = {}
        for key in ('talent_raw', 'pts_idx', 'ast_idx', 'trb_idx', 'stl_idx', 'blk_idx', 'ts_idx', 'dbpm'):
            self.sorted[key] = sorted(f[key] for f in qualified if f[key] is not None)
        for f in seasons.values():
            f['spacing_raw'] = self._spacing_raw(f)
        self.sorted['spacing_raw'] = sorted(f['spacing_raw'] for f in qualified if f['spacing_raw'] is not None)

    def _talent_raw(self, f):
        zs = [(f[m] - mu) / sd for m, (mu, sd) in self.z.items() if f[m] is not None]
        if not zs:
            return None
        weight = min(1.0, f['minutes'] / 1500) if f['minutes'] else min(1.0, (f['g'] or 0) / 60)
        return fmean(zs) * weight          # small samples drift toward average

    def _spacing_raw(self, f):
        if f['season'] < 1980 or f['x3p_ar_diff'] is None:
            return None
        shooting = (f['x3p_pct_idx'] - 1) * 3 if (f['x3p_pct_idx'] and (f['x3p_ar'] or 0) >= 0.1) else -0.3
        return f['x3p_ar_diff'] * 5 + shooting

    def pct(self, key, value):
        arr = self.sorted[key]
        if value is None or not arr:
            return None
        return round(100 * bisect.bisect_left(arr, value) / len(arr), 1)


_cache: dict = {}


def get_pool(conn) -> Pool:
    """Built once per data load (keyed on the load time in the meta table)."""
    loaded_at = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'loaded_at')).scalar()
    if _cache.get('key') != loaded_at:
        pool = build_pool(conn)
        calibrate(pool)
        _cache.update(key=loaded_at, pool=pool)
    return _cache['pool']


def build_pool(conn) -> Pool:
    env = {r['season']: dict(r) for r in conn.execute(select(s.league_env)).mappings()}
    adv = {(r['player_id'], r['season']): dict(r) for r in conn.execute(select(s.player_advanced)).mappings()}
    players = {r['player_id']: dict(r) for r in conn.execute(
        select(s.players.c.player_id, s.players.c.player, s.players.c.pos, s.players.c.ht_in_in, s.players.c.hof)).mappings()}
    rows = {}
    stints = {}
    for r in conn.execute(select(s.player_seasons)).mappings():
        key = (r['player_id'], r['season'])
        if not r['combined']:
            stints.setdefault(key, []).append(r['team'])
        if key not in rows or r['combined']:
            rows[key] = dict(r)
    seasons = {}
    for key, r in rows.items():
        e, a = env.get(r['season'], {}), adv.get(key, {})
        mp, g = _num(r['mp']), _num(r['g']) or 0
        per36 = lambda k: (r[k] / mp * 36) if mp and _num(r[k]) is not None else None
        minutes = mp * g if mp else None
        usage = _num(a.get('usg_pct'))
        pts_idx = _ratio(per36('pts'), e.get('pts36'))
        seasons[key] = {
            'player_id': r['player_id'], 'season': r['season'], 'age': r['age'], 'g': g, 'mp': mp, 'minutes': minutes,
            'teams': stints.get(key) or [r['team']], 'pos': r['pos'] or players.get(r['player_id'], {}).get('pos'),
            'pts': r['pts'], 'trb': r['trb'], 'ast': r['ast'],
            'qualified': g >= 40 and (minutes is None or minutes >= 1200),
            'bpm': _num(a.get('bpm')), 'ws_48': _num(a.get('ws_48')), 'per': _num(a.get('per')),
            'ws_pg': (_num(a.get('ws')) / g) if g and _num(a.get('ws')) is not None else None,
            'dbpm': _num(a.get('dbpm')),
            'pts_idx': pts_idx, 'ast_idx': _ratio(per36('ast'), e.get('ast36')), 'trb_idx': _ratio(per36('trb'), e.get('trb36')),
            'stl_idx': _ratio(per36('stl'), e.get('stl36')), 'blk_idx': _ratio(per36('blk'), e.get('blk36')),
            'ts_idx': _ratio(a.get('ts_pct'), e.get('ts_pct')),
            'x3p_ar': _num(a.get('x3p_ar')),
            'x3p_ar_diff': (a['x3p_ar'] - e['x3p_ar']) if _num(a.get('x3p_ar')) is not None and _num(e.get('x3p_ar')) is not None else None,
            'x3p_pct_idx': _ratio(r['x3p_pct'], e.get('x3p_pct')),
            'usage': usage if usage is not None else (min(40.0, max(8.0, 20 * pts_idx)) if pts_idx else None),
            'usage_estimated': usage is None and pts_idx is not None,
        }
    return Pool(seasons, players)


# ---- per-player ratings ---------------------------------------------------------------------
def rate_season(pool: Pool, f: dict) -> dict:
    p = pool.pct
    defense_parts = [v for v in (p('stl_idx', f['stl_idx']), p('blk_idx', f['blk_idx']), p('dbpm', f['dbpm'])) if v is not None]
    return {
        'talent': p('talent_raw', f['talent_raw']),
        'scoring': p('pts_idx', f['pts_idx']), 'playmaking': p('ast_idx', f['ast_idx']),
        'rebounding': p('trb_idx', f['trb_idx']), 'steals': p('stl_idx', f['stl_idx']), 'blocks': p('blk_idx', f['blk_idx']),
        'defense': round(fmean(defense_parts), 1) if defense_parts else None,
        'efficiency': p('ts_idx', f['ts_idx']), 'spacing': p('spacing_raw', f['spacing_raw']),
    }


def role_tags(r: dict) -> list[str]:
    tags = [(r['scoring'], 'Go-to scorer'), (r['playmaking'], 'Floor general'), (r['rebounding'], 'Glass cleaner'),
            (r['blocks'], 'Rim protector'), (r['steals'], 'Ball hawk'), (r['spacing'], 'Floor spacer'),
            (r['efficiency'], 'Efficient')]
    return [t for v, t in sorted(tags, key=lambda x: -(x[0] or 0)) if (v or 0) >= 88][:3]


def best_season(pool: Pool, player_id: str):
    options = [f for (pid, _), f in pool.seasons.items() if pid == player_id and f['talent_raw'] is not None]
    return max(options, key=lambda f: f['talent_raw'])['season'] if options else None


def player_seasons(pool: Pool, player_id: str) -> list[dict]:
    out = []
    for (pid, season), f in sorted(pool.seasons.items(), key=lambda kv: -kv[0][1]):
        if pid == player_id:
            out.append({'season': season, 'age': f['age'], 'teams': f['teams'], 'g': f['g'],
                        'pts': f['pts'], 'trb': f['trb'], 'ast': f['ast'], 'rating': rate_season(pool, f)['talent']})
    return out


# ---- lineup -----------------------------------------------------------------------------------
def _weighted(values: list[float], weights: list[float]) -> float:
    vals = sorted(values, reverse=True)
    w = weights[:len(vals)]
    return sum(v * x for v, x in zip(vals, w)) / sum(w)


# Listed position decides; height is only a fallback when there's no position.
def _is_big(player: dict, f: dict) -> bool:
    pos = (f['pos'] or player.get('pos') or '').upper()
    if pos:
        return pos.split('-')[0] in ('C', 'PF') or pos in ('F-C', 'C-F')
    return (player.get('ht_in_in') or 0) >= 82


def _is_guard(player: dict, f: dict) -> bool:
    pos = (f['pos'] or player.get('pos') or '').upper()
    if pos:
        return pos.split('-')[0] in ('PG', 'SG', 'G')
    return (player.get('ht_in_in') or 99) <= 76


def real_percentile(pool: Pool, overall: float) -> float:
    """Share of real NBA starting fives this score beats."""
    return round(100 * bisect.bisect_left(pool.real_scores, overall) / len(pool.real_scores), 1)


def real_starting_fives(pool: Pool) -> dict:
    """(team, season) -> the five players with the most minutes, 1951-52 on."""
    by_team: dict = {}
    for (pid, season), f in pool.seasons.items():
        if f['minutes'] is None:
            continue
        for team in f['teams']:
            by_team.setdefault((team, season), []).append((f['minutes'] / max(1, len(f['teams'])), pid))
    return {k: [pid for _, pid in sorted(v, reverse=True)[:5]] for k, v in by_team.items() if len(v) >= 5}


def calibrate(pool: Pool):
    pool.real_scores = []
    scores = []
    for (team, season), pids in real_starting_fives(pool).items():
        scores.append(score_lineup(pool, [(pid, season) for pid in pids])['overall_exact'])
    pool.real_scores = sorted(scores)


def score_lineup(pool: Pool, picks: list[tuple[str, int | None]]) -> dict:
    """picks: [(player_id, season or None for their best season)], 1-5 players."""
    members, notes = [], []
    for pid, season in picks:
        player = pool.players.get(pid)
        if player is None:
            raise ValueError(f'Unknown player {pid!r}')
        season = season or best_season(pool, pid)
        f = pool.seasons.get((pid, season))
        if f is None:
            raise ValueError(f'{player["player"]} has no {season} season')
        r = rate_season(pool, f)
        name = f'{player["player"]} ({season})'
        if r['talent'] is None:
            notes.append(f'{name}: no impact metrics for this season, so talent counts as league average.')
        if f['mp'] is None:
            notes.append(f'{name}: minutes weren\u2019t recorded before 1951-52, so per-minute rates count as average.')
        if season < 1980:
            notes.append(f'{name}: no three-point line before 1979-80, so spacing counts as average.')
        elif f['spacing_raw'] is None:
            notes.append(f'{name}: no three-point data, so spacing counts as average.')
        if season < 1974 and f['mp'] is not None:
            notes.append(f'{name}: steals and blocks weren\u2019t tracked before 1973-74, so defense counts as average.')
        if f['usage_estimated']:
            notes.append(f'{name}: usage wasn\u2019t tracked before 1977-78; estimated from scoring rate.')
        if f['minutes'] is not None and f['minutes'] < 1200:
            notes.append(f'{name}: small sample ({int(f["minutes"])} minutes), so ratings are pulled toward average.')
        members.append({'player': player, 'f': f, 'r': r})

    if len({m['player']['player_id'] for m in members}) != len(members):
        raise ValueError('Each player can only appear once in a lineup')

    val = lambda m, k: m['r'][k] if m['r'][k] is not None else 50.0
    cats = {
        'talent': fmean(val(m, 'talent') for m in members),
        'scoring': _weighted([val(m, 'scoring') for m in members], [0.35, 0.25, 0.2, 0.12, 0.08]),
        'playmaking': (0.6 * max(val(m, 'playmaking') for m in members)
                       + 0.4 * (fmean(sorted(val(m, 'playmaking') for m in members)[:-1]) if len(members) > 1 else 0)),
        'rebounding': _weighted([val(m, 'rebounding') for m in members], [0.35, 0.3, 0.15, 0.1, 0.1]),
        'defense': _weighted([val(m, 'defense') for m in members], [0.3, 0.25, 0.2, 0.15, 0.1]),
        'spacing': fmean(val(m, 'spacing') for m in members),
        'efficiency': (sum(val(m, 'efficiency') * (m['f']['usage'] or 20) for m in members)
                       / sum(m['f']['usage'] or 20 for m in members)),
    }

    fit, fit_notes = 100.0, []
    complete = len(members) == 5
    if complete:
        usage = sum(m['f']['usage'] or 20 for m in members)
        # Stars' usage rates naturally add up past 100%; only heavy overlap costs much.
        if usage > 115:
            fit -= min(20.0, (usage - 115) * 0.4)
            fit_notes.append(f'Combined usage is {usage:.0f}% (one team\'s possessions add up to about 100%), so some stars would have to give up touches.')
        bigs = sum(_is_big(m['player'], m['f']) for m in members)
        guards = sum(_is_guard(m['player'], m['f']) for m in members)
        if bigs == 0:
            fit -= 25
            fit_notes.append('No big man to protect the rim or rebound.')
        elif bigs > 2:
            fit -= 8 * (bigs - 2)
            fit_notes.append(f'{bigs} bigs share the floor, which crowds the paint.')
        if guards == 0:
            fit -= 10
            fit_notes.append('No guard to bring the ball up and run the offense.')
        if cats['spacing'] < 30:
            fit -= 6
            fit_notes.append('Little outside shooting, so defenses can pack the paint.')
    fit = max(0.0, min(100.0, fit))
    cats['fit'] = fit

    base = sum(cats[k] * w for k, w in CATEGORY_WEIGHTS.items())
    overall = round(base * (0.75 + 0.25 * fit / 100), 1) if complete else None
    real = real_percentile(pool, overall) if complete and pool.real_scores else None
    return {
        'complete': complete,
        'overall': round(overall) if overall is not None else None,
        'overall_exact': overall,
        'real_percentile': real,
        'grade': next(label for floor, label in GRADES if real >= floor) if real is not None else None,
        'categories': [{'key': k, 'label': LABELS[k], 'score': round(v)} for k, v in cats.items()],
        'players': [{
            'player_id': m['player']['player_id'], 'player': m['player']['player'], 'hof': m['player']['hof'],
            'season': m['f']['season'], 'age': m['f']['age'], 'teams': m['f']['teams'], 'pos': m['f']['pos'],
            'pts': m['f']['pts'], 'trb': m['f']['trb'], 'ast': m['f']['ast'],
            'bpm': m['f']['bpm'], 'ws_48': m['f']['ws_48'], 'usage': m['f']['usage'],
            'rating': m['r']['talent'], 'ratings': m['r'], 'tags': role_tags(m['r']),
        } for m in members],
        'fit_notes': fit_notes,
        'notes': notes,
    }
