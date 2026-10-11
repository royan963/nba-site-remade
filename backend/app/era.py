"""Era adjustment, mirroring src/js/era-stats.js so the API and the
dashboard report the same numbers.

  raw    box score as recorded
  per100 per 100 team possessions (tracked from 1973-74)
  index  relative to that season's league average, 100 = average
"""
import math


def _num(v):
    return v if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)) else None


def per36(row, key):
    v, mp = _num(row.get(key)), _num(row.get('mp'))
    return v / mp * 36 if v is not None and mp else None


def league_index(value, league_value):
    return 100 * value / league_value if value is not None and league_value else None


def _p100(key):
    return lambda r, env: (r.get('per100') or {}).get(key)


STAT_BASES = {
    'raw': [
        ('pts', 'Points/Game', lambda r, e: r.get('pts')),
        ('trb', 'Rebounds/Game', lambda r, e: r.get('trb')),
        ('ast', 'Assists/Game', lambda r, e: r.get('ast')),
        ('stl', 'Steals/Game', lambda r, e: r.get('stl')),
        ('blk', 'Blocks/Game', lambda r, e: r.get('blk')),
        ('fg_pct', 'FG%', lambda r, e: r.get('fg_pct')),
        ('x3p_pct', '3P%', lambda r, e: r.get('x3p_pct')),
        ('ft_pct', 'FT%', lambda r, e: r.get('ft_pct')),
        ('ts_pct', 'True Shooting %', lambda r, e: r.get('ts_pct')),
        ('mp', 'Minutes/Game', lambda r, e: r.get('mp')),
        ('g', 'Games Played', lambda r, e: r.get('g')),
    ],
    'per100': [
        ('p_pts', 'Points / 100', _p100('pts')),
        ('p_trb', 'Rebounds / 100', _p100('trb')),
        ('p_ast', 'Assists / 100', _p100('ast')),
        ('p_stl', 'Steals / 100', _p100('stl')),
        ('p_blk', 'Blocks / 100', _p100('blk')),
        ('p_tov', 'Turnovers / 100', _p100('tov')),
        ('o_rtg', 'Offensive Rating', _p100('o_rtg')),
        ('d_rtg', 'Defensive Rating', _p100('d_rtg')),
        ('ts_pct', 'True Shooting %', lambda r, e: r.get('ts_pct')),
    ],
    'index': [
        ('i_pts', 'Scoring rate', lambda r, e: league_index(per36(r, 'pts'), e.get('pts36'))),
        ('i_trb', 'Rebounding rate', lambda r, e: league_index(per36(r, 'trb'), e.get('trb36'))),
        ('i_ast', 'Playmaking rate', lambda r, e: league_index(per36(r, 'ast'), e.get('ast36'))),
        ('i_stl', 'Steal rate', lambda r, e: league_index(per36(r, 'stl'), e.get('stl36'))),
        ('i_blk', 'Block rate', lambda r, e: league_index(per36(r, 'blk'), e.get('blk36'))),
        ('i_ts', 'TS+ (efficiency)', lambda r, e: league_index(r.get('ts_pct'), e.get('ts_pct'))),
        ('i_fg', 'FG+', lambda r, e: league_index(r.get('fg_pct'), e.get('fg_pct'))),
        ('i_3p', '3P+', lambda r, e: league_index(r.get('x3p_pct'), e.get('x3p_pct'))),
        ('i_ft', 'FT+', lambda r, e: league_index(r.get('ft_pct'), e.get('ft_pct'))),
    ],
}
ADVANCED = [
    ('per', 'PER', lambda r, e: r.get('per')),
    ('ws', 'Win Shares', lambda r, e: r.get('ws')),
    ('ws_48', 'WS / 48', lambda r, e: r.get('ws_48')),
    ('bpm', 'Box Plus/Minus', lambda r, e: r.get('bpm')),
    ('vorp', 'VORP', lambda r, e: r.get('vorp')),
    ('usg_pct', 'Usage %', lambda r, e: r.get('usg_pct')),
]
LOWER_IS_BETTER = {'p_tov', 'd_rtg'}


def stat_defs(basis):
    return STAT_BASES[basis] + ADVANCED


def compute(basis, season_row, env):
    out = {}
    for key, _, fn in stat_defs(basis):
        v = fn(season_row, env or {})
        out[key] = None if v is None else round(v, 4)
    return out
