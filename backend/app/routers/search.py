"""Natural-language search over player-seasons, careers, playoffs and single games (see app/search.py).

Besides the filters the parser reads, the question is scanned for player names ("lebron", "SGA",
"Shai Gilgeous-Alexander"): one named player narrows the results to him (or, with nothing else
to go on, returns a player card); two become a comparison.
"""
import json
import re
import threading
from typing import Literal

from fastapi import APIRouter, Depends, Query as Q
from sqlalchemy import Float, and_, case, cast, exists, false, func, or_, select, true

from .. import schema as s
from ..db import get_conn
from ..search import STAT_LABEL, drop_filters, parse, Filter
from ..util import normalize_name
from .games import h2h_teams
from .salaries import team_salaries

router = APIRouter(tags=['search'])

PCT = {'fg_pct', 'x3p_pct', 'ft_pct', 'ts_pct'}
CAREER_LABEL = {'pts': 'Career points', 'trb': 'Career rebounds', 'ast': 'Career assists', 'stl': 'Career steals', 'blk': 'Career blocks',
                'x3pm': 'Career 3-pointers made', 'g': 'Career games', 'ws': 'Career Win Shares', 'vorp': 'Career VORP',
                'fg_pct': 'Career field goal %', 'x3p_pct': 'Career 3-point %', 'ft_pct': 'Career free throw %', 'ts_pct': 'Career true shooting %',
                'height': 'Height', 'titles': 'Championships', 'salary': 'Career earnings'}
GAME_LABEL = {'pts': 'Points', 'trb': 'Rebounds', 'ast': 'Assists', 'stl': 'Steals', 'blk': 'Blocks', 'x3pm': '3-pointers made'}
PLAYOFF_SEASON_LABEL = {'pts': 'Playoff points per game', 'trb': 'Playoff rebounds per game', 'ast': 'Playoff assists per game',
                        'stl': 'Playoff steals per game', 'blk': 'Playoff blocks per game', 'x3pm': 'Playoff 3-pointers per game',
                        'mp': 'Playoff minutes per game', 'g': 'Playoff games', 'fg_pct': 'Playoff field goal %', 'x3p_pct': 'Playoff 3-point %',
                        'ft_pct': 'Playoff free throw %', 'ts_pct': 'Playoff true shooting %'}
PLAYOFF_CAREER_LABEL = {'pts': 'Career playoff points', 'trb': 'Career playoff rebounds', 'ast': 'Career playoff assists',
                        'stl': 'Career playoff steals', 'blk': 'Career playoff blocks', 'x3pm': 'Career playoff 3-pointers', 'g': 'Career playoff games',
                        'mp': 'Career playoff minutes', 'fg_pct': 'Career playoff field goal %', 'x3p_pct': 'Career playoff 3-point %',
                        'ft_pct': 'Career playoff free throw %', 'ts_pct': 'Career playoff true shooting %', 'titles': 'Championships'}
CAREER_AVG_LABEL = {'pts': 'Career points per game', 'trb': 'Career rebounds per game', 'ast': 'Career assists per game',
                    'stl': 'Career steals per game', 'blk': 'Career blocks per game', 'x3pm': 'Career 3-pointers made per game'}
CAREER_AVG_MIN_GAMES = 400          # a career average needs a real sample before it can top a leaderboard
AWARD_CODE = {'dpoy': 'nba dpoy', 'roy': 'nba roy', 'smoy': 'nba smoy', 'mip': 'nba mip', 'clutch': 'nba clutch_poy', 'mvp': 'nba mvp'}
LINKS = [(r'\bchampions?\b(?! *(?:of|in) )|\bchampionship (?:list|history|teams?)\b|\bwho won the (?:title|championship|finals)', 'Every champion', '/teams?view=champions'),
         (r'\bmvp (?:race|odds|predict\w*|favou?rites?)\b|\bwho will win mvp\b', 'MVP predictor', '/models/mvp'),
         (r'\b(?:title|championship) odds\b|\bwho will win the (?:title|championship)\b|\bchampion predict\w*', 'Champion predictor', '/models/champion'),
         (r'\bprojections?\b|\bnext season\b', 'Career projections', '/models/projections'),
         (r'\blineups?\b|\bstarting five\b', 'Lineup builder', '/lineups/new'),
         (r'\barchetypes?\b|\bplaying styles?\b', 'Player archetypes', '/models/archetypes')]
EXAMPLES = ['best rebounding guards of the 90s', 'players who averaged 25 and 10 since 2010', 'top 10 three point shooters in 2016',
            'stretch bigs of the 2010s', 'rookies with the most points', 'efficient scorers under 25', '50/40/90 seasons',
            'Celtics leading scorers in the 80s', 'triple-double seasons', 'all-time leading scorers', 'MVPs since 2000',
            'most points in a playoff game', 'who has the most championships', 'tallest players', 'highest paid players this season',
            'youngest MVPs', 'best defensive players of the 2010s', 'curry vs harden', 'how many rings does lebron have']

# ---- player names in a question ----------------------------------------------------------------------
NICKNAMES = {'lebron': 'jamesle01', 'king james': 'jamesle01', 'mj': 'jordami01', 'kobe': 'bryanko01', 'shaq': 'onealsh01',
             'steph': 'curryst01', 'kd': 'duranke01', 'giannis': 'antetgi01', 'greek freak': 'antetgi01', 'jokic': 'jokicni01',
             'joker': 'jokicni01', 'sga': 'gilgesh01', 'shai': 'gilgesh01', 'wemby': 'wembavi01', 'magic': 'johnsma02',
             'magic johnson': 'johnsma02', 'kareem': 'abdulka01', 'wilt': 'chambwi01', 'dirk': 'nowitdi01', 'luka': 'doncilu01',
             'ad': 'davisan02', 'cp3': 'paulch01', 'the beard': 'hardeja01', 'dame': 'lillada01', 'ant': 'edwaran01',
             'ant man': 'edwaran01', 'jimmy buckets': 'butleji01', 'kawhi': 'leonaka01', 'russ': 'westbru01', 'zion': 'williza01',
             'hakeem': 'olajuha01', 'the dream': 'olajuha01', 'dr j': 'ervinju01', 'pistol pete': 'maravpe01', 'ai': 'iversal01',
             'iverson': 'iversal01', 'bird': 'birdla01', 'larry legend': 'birdla01', 'timmy': 'duncati01', 'tim duncan': 'duncati01',
             'curry': 'curryst01', 'steph curry': 'curryst01', 'jordan': 'jordami01', 'michael jordan': 'jordami01', 'cade': 'cunnica01', 'tatum': 'tatumja01', 'embiid': 'embiijo01', 'kyrie': 'irvinky01'}
# single words that are also players' names but usually mean something else in a question
COMMON = set('''young love rose will west green hill price king grant white black brown little long early battle best mann
    miller allen smith johnson jones davis williams thomas jackson harris robinson walker scott moore martin thompson
    lee wright hunter wood house holiday free bridges booker paul james george anthony carter morris gay'''.split())

_index_lock = threading.Lock()
_index: dict = {}


def name_index(conn):
    """Full names, last names and nicknames -> player ids (most career points first), cached per data load."""
    key = conn.execute(select(s.meta.c.value).where(s.meta.c.key == 'loaded_at')).scalar()
    if _index.get('key') != key:
        with _index_lock:
            if _index.get('key') != key:
                full, last = {}, {}
                for pid, name, pts in conn.execute(select(s.players.c.player_id, s.players.c.name_search, s.players.c.pts)):
                    n = re.sub(r"[.'’]", '', (name or '').replace('-', ' ')).split()
                    n = [w for w in n if w not in ('jr', 'sr', 'ii', 'iii', 'iv')]
                    if not n:
                        continue
                    full.setdefault(' '.join(n), []).append((pts or 0, pid))
                    last.setdefault(n[-1], []).append((pts or 0, pid))
                for d in (full, last):
                    for k in d:
                        d[k].sort(reverse=True)
                _index.update(key=key, full=full, last=last)
    return _index


def find_players(conn, text: str, ignored: list):
    """Players named in the question: (player ids in order of mention, words used up).
    Full names and nicknames anywhere; a bare last name only if the parser didn't use the word,
    it isn't a common English word or surname, and one player clearly owns it."""
    idx = name_index(conn)
    words = re.sub(r"[^a-z0-9 ]", ' ', normalize_name(text).replace('-', ' ').replace("'", '')).split()
    used, found = set(), []
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            if any(j in used for j in range(i, i + n)):
                continue
            gram = ' '.join(words[i:i + n])
            pid = None
            if gram in NICKNAMES:
                pid = NICKNAMES[gram]
            elif n >= 2 and gram in idx['full']:
                pid = idx['full'][gram][0][1]
            elif n == 1 and gram in ignored and gram not in COMMON and len(gram) > 3 and gram in idx['last']:
                cands = idx['last'][gram]
                # a surname only one player has, or one a star clearly owns (Jordan the guard, not DeAndre)
                if len(cands) == 1 or (cands[0][0] >= 8000 and cands[0][0] >= 2.5 * cands[1][0]):
                    pid = cands[0][1]
            if pid:                        # the same player named twice ('steph ... curry') uses up both
                if pid not in [f for _, f in found]:
                    found.append((i, pid))
                used.update(range(i, i + n))
    found.sort()
    return [pid for _, pid in found], {words[j] for j in used}


def player_card(conn, pid):
    p = s.players
    r = conn.execute(select(p).where(p.c.player_id == pid)).mappings().first()
    if not r:
        return None
    titles = [t for (t,) in conn.execute(select(s.player_titles.c.season).where(s.player_titles.c.player_id == pid).order_by(s.player_titles.c.season))]
    aw = s.award_shares
    mvps = [t for (t,) in conn.execute(select(aw.c.season).where(aw.c.player_id == pid, aw.c.award == 'nba mvp', aw.c.winner.is_(True)).order_by(aw.c.season))]
    fmvp = [t for (t,) in conn.execute(select(s.finals_mvp.c.season).where(s.finals_mvp.c.player_id == pid).order_by(s.finals_mvp.c.season))]
    sal = conn.execute(select(s.player_salaries.c.season, func.sum(s.player_salaries.c.salary)).where(s.player_salaries.c.player_id == pid)
                       .group_by(s.player_salaries.c.season).order_by(s.player_salaries.c.season.desc()).limit(1)).first()
    age = conn.execute(select(s.player_seasons.c.age, s.player_seasons.c.season).where(s.player_seasons.c.player_id == pid)
                       .order_by(s.player_seasons.c.season.desc()).limit(1)).first()
    return {'player_id': pid, 'player': r['player'], 'hof': r['hof'], 'age': age[0] if age else None, 'age_season': age[1] if age else None, 'pos': r['pos'], 'height': r['ht_in_in'], 'weight': r['wt'],
            'first_season': r['first_season'], 'last_season': r['last_season'], 'g': r['g'], 'pts': r['pts'], 'ppg': r['ppg'],
            'rpg': r['rpg'], 'apg': r['apg'], 'ws': r['ws'], 'all_star': r['all_star'], 'titles': titles, 'mvps': mvps,
            'finals_mvps': fmvp, 'salary': {'season': sal[0], 'amount': int(sal[1])} if sal else None}


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


def _career_position(pid_col, codes):
    """Careers only store G/F/C, so a career counts as a position when most of the player's seasons list it."""
    ps = s.player_seasons
    at = select(func.count()).where(ps.c.player_id == pid_col, ps.c.combined.is_(False), _position_clause(ps.c.pos, codes)).scalar_subquery()
    total = select(func.count()).where(ps.c.player_id == pid_col, ps.c.combined.is_(False)).scalar_subquery()
    return at * 2 >= total


def _season_honor(key, pid_col, season_col):
    aw = s.award_shares
    if key in AWARD_CODE:
        return exists().where(and_(aw.c.player_id == pid_col, aw.c.season == season_col, aw.c.award == AWARD_CODE[key], aw.c.winner.is_(True)))
    if key == 'finals_mvp':
        return exists().where(and_(s.finals_mvp.c.player_id == pid_col, s.finals_mvp.c.season == season_col))
    if key == 'all_star':
        return exists().where(and_(s.all_stars.c.player_id == pid_col, s.all_stars.c.season == season_col))
    if key == 'all_nba':
        eos = s.eos_teams
        return exists().where(and_(eos.c.player_id == pid_col, eos.c.season == season_col, eos.c.team_type == 'All-NBA'))
    return None


def _career_honor(key, pid_col):
    aw = s.award_shares
    if key in AWARD_CODE:
        return exists().where(and_(aw.c.player_id == pid_col, aw.c.award == AWARD_CODE[key], aw.c.winner.is_(True)))
    if key == 'finals_mvp':
        return exists().where(s.finals_mvp.c.player_id == pid_col)
    if key == 'all_nba':
        return exists().where(and_(s.eos_teams.c.player_id == pid_col, s.eos_teams.c.team_type == 'All-NBA'))
    return None


def run_seasons(conn, q, archetypes_list, notes):
    ps, p, adv, pa = s.player_seasons, s.players, s.player_advanced, s.player_archetypes
    expr = {k: ps.c[k] for k in ('pts', 'trb', 'ast', 'stl', 'blk', 'mp', 'g', 'fg_pct', 'x3p_pct', 'ft_pct', 'x3pa', 'fta', 'age')}
    expr['x3pm'] = ps.c.x3pa * ps.c.x3p_pct
    expr.update({k: adv.c[k] for k in ('ts_pct', 'per', 'ws', 'bpm', 'vorp', 'dbpm')})
    sal = select(s.player_salaries.c.player_id, s.player_salaries.c.season, func.sum(s.player_salaries.c.salary).label('salary')) \
        .group_by(s.player_salaries.c.player_id, s.player_salaries.c.season).subquery()
    expr['salary'] = sal.c.salary
    if q.stat not in expr:                 # career-only stats can't rank seasons
        notes.drop(f'{STAT_LABEL.get(q.stat, q.stat)} isn’t a season stat, so seasons are ranked by Win Shares.')
        q.stat = 'ws'
    rank = expr[q.stat]
    stmt = (select(ps.c.player_id, p.c.player, p.c.hof, ps.c.season, ps.c.age, ps.c.team, ps.c.pos, ps.c.g, ps.c.mp, ps.c.pts,
                   ps.c.trb, ps.c.ast, rank.label('value'), pa.c.archetype_id)
            .join(p, p.c.player_id == ps.c.player_id)
            .outerjoin(adv, and_(adv.c.player_id == ps.c.player_id, adv.c.season == ps.c.season))
            .outerjoin(pa, and_(pa.c.player_id == ps.c.player_id, pa.c.season == ps.c.season)))
    if q.stat == 'salary':
        stmt = stmt.outerjoin(sal, and_(sal.c.player_id == ps.c.player_id, sal.c.season == ps.c.season))
    if q.teams:      # team-specific stints, not a traded player's combined line
        ts = s.team_seasons
        stmt = stmt.join(ts, and_(ts.c.abbr == ps.c.team, ts.c.season == ps.c.season)).where(ts.c.team_name.in_(q.teams), ps.c.combined.is_(False))
    else:            # one row per player-season: the combined row when he was traded
        ps2 = s.player_seasons.alias('ps2')
        stmt = stmt.where(or_(ps.c.combined.is_(True), ~exists().where(and_(ps2.c.player_id == ps.c.player_id, ps2.c.season == ps.c.season,
                                                                              ps2.c.combined.is_(True)))))
    cond = [rank.is_not(None)]
    # minimums so small samples don't win (and "worst" lists aren't all deep-bench players); not when asking about named players
    if not q.player_ids:
        if q.stat not in ('g', 'salary', 'age'):
            cond.append(ps.c.g >= 40)
        if q.stat in ('fg_pct', 'ts_pct', 'per', 'bpm', 'dbpm') or q.order == 'asc' and q.stat != 'age':
            cond.append(ps.c.mp >= 20)
        if q.stat == 'x3p_pct':
            cond.append(ps.c.x3pa >= 2.0)
        if q.stat == 'ft_pct':
            cond.append(ps.c.fta >= 3.0)
    else:
        cond.append(ps.c.player_id.in_(q.player_ids))
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
    for key in q.honors:
        c = _season_honor(key, ps.c.player_id, ps.c.season)
        if c is not None:
            cond.append(c)
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
    if q.teams and not q.minimums and q.stat in TEAM_TOTAL_STATS:
        return run_team_careers(conn, q, notes)
    p = s.players
    team_franchises = franchises_of(conn, q.teams) if q.teams and q.stat == 'titles' else []
    title_where = [s.player_titles.c.player_id == p.c.player_id]
    if team_franchises:                      # only titles won with that franchise
        title_where.append(s.player_titles.c.franchise.in_(team_franchises))
    titles = select(func.count()).where(*title_where).scalar_subquery()
    earned = select(func.sum(s.player_salaries.c.salary)).where(s.player_salaries.c.player_id == p.c.player_id).scalar_subquery()
    totals = {'pts': p.c.pts, 'trb': p.c.trb, 'ast': p.c.ast, 'stl': p.c.stl, 'blk': p.c.blk, 'x3pm': p.c.x3p, 'g': p.c.g,
              'ws': p.c.ws, 'vorp': p.c.vorp, 'height': p.c.ht_in_in, 'titles': titles, 'salary': earned}
    pct = {'fg_pct': (p.c.fg / func.nullif(p.c.fga, 0), p.c.fga >= 2000), 'x3p_pct': (p.c.x3p / func.nullif(p.c.x3pa, 0), p.c.x3pa >= 500),
           'ft_pct': (p.c.ft / func.nullif(p.c.fta, 0), p.c.fta >= 500),
           'ts_pct': (p.c.pts / func.nullif(2 * (p.c.fga + 0.44 * p.c.fta), 0), p.c.fga >= 2000)}
    stat = q.stat
    if stat not in totals and stat not in pct:
        notes.drop(f'{STAT_LABEL[stat]} isn’t available as a career total, so careers are ranked by Win Shares.')
        stat = 'ws'
    rank, cond = (pct[stat][0], [pct[stat][1]]) if stat in pct else (totals[stat], [])
    if q.player_ids:
        cond = [p.c.player_id.in_(q.player_ids)]
    if stat == 'titles' and q.order == 'desc':
        cond.append(titles > 0)
    per_game = {'pts': p.c.ppg, 'trb': p.c.rpg, 'ast': p.c.apg,
                'stl': p.c.stl * 1.0 / func.nullif(p.c.g, 0), 'blk': p.c.blk * 1.0 / func.nullif(p.c.g, 0),
                'x3pm': p.c.x3p * 1.0 / func.nullif(p.c.g, 0)}
    if q.per_game and stat in per_game:      # the per-game number, not the career total
        rank = per_game[stat]
        q.per_game_used = True
        if not q.player_ids:
            cond.append(p.c.g >= CAREER_AVG_MIN_GAMES)
            notes.append(f'Career averages only count players with at least {CAREER_AVG_MIN_GAMES} games.')
    avg = {'pts': p.c.ppg, 'trb': p.c.rpg, 'ast': p.c.apg}
    for m_stat, op, v in q.minimums:
        if m_stat in avg:
            cond.append((avg[m_stat] < v) if op == '<' else (avg[m_stat] >= v))
            cond.append(p.c.g >= 100)
        elif m_stat in pct:
            cond += [pct[m_stat][0] >= v, pct[m_stat][1]]
    if q.positions:
        cond.append(_career_position(p.c.player_id, q.positions))
    if q.season_from:
        cond.append(p.c.last_season >= q.season_from)
    if q.season_to:
        cond.append(p.c.first_season <= q.season_to)
    if 'hof' in q.honors:
        cond.append(p.c.hof.is_(True))
    if 'all_star' in q.honors:
        cond.append(p.c.all_star >= 1)
    for key in q.honors:
        c = _career_honor(key, p.c.player_id)
        if c is not None:
            cond.append(c)
    for what, active in (('age', q.age_min is not None or q.age_max is not None), ('rookie seasons', q.rookie or q.sophomore),
                         ('team', bool(q.teams) and not team_franchises), ('playing style', bool(q.archetype))):
        if active:
            notes.drop(f'The {what} filter applies to single seasons, so it was ignored for careers.')
    order = rank.asc() if q.order == 'asc' else rank.desc()
    stmt = (select(p.c.player_id, p.c.player, p.c.hof, p.c.pos, p.c.first_season, p.c.last_season, p.c.g, p.c.pts, p.c.trb, p.c.ast,
                   p.c.ppg, p.c.rpg, p.c.apg, rank.label('value'))
            .where(rank.is_not(None), p.c.g >= 1, *cond).order_by(order, p.c.pts.desc()).limit(q.limit))
    return stat, [dict(r) for r in conn.execute(stmt).mappings()]


def run_playoffs(conn, q, notes):
    """Playoff seasons (one row per player and playoff run) or playoff careers, from the player_playoffs table."""
    po, p = s.player_playoffs, s.players
    keys = [po.c.player_id] + ([po.c.season] if q.scope == 'seasons' else [])
    sums = {c: func.sum(po.c[c]) for c in ('g', 'mp', 'fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'trb', 'ast', 'stl', 'blk', 'pts',
                                           'g_mp', 'g_trb', 'g_ast', 'g_stl', 'g_blk')}
    agg = select(*keys, *[v.label(k) for k, v in sums.items()], func.max(po.c.team).label('team'))
    if q.teams:
        ts = s.team_seasons
        agg = agg.join(ts, and_(ts.c.abbr == po.c.team, ts.c.season == po.c.season)).where(ts.c.team_name.in_(q.teams))
    if q.season_from:
        agg = agg.where(po.c.season >= q.season_from)
    if q.season_to:
        agg = agg.where(po.c.season <= q.season_to)
    t = agg.group_by(*keys).subquery()
    per = lambda num, den: num * 1.0 / func.nullif(den, 0)
    seasons = q.scope == 'seasons'
    expr = ({'pts': per(t.c.pts, t.c.g), 'trb': per(t.c.trb, t.c.g_trb), 'ast': per(t.c.ast, t.c.g_ast), 'stl': per(t.c.stl, t.c.g_stl),
             'blk': per(t.c.blk, t.c.g_blk), 'x3pm': per(t.c.x3p, t.c.g), 'mp': per(t.c.mp, t.c.g_mp), 'g': t.c.g} if (seasons or q.per_game) else
            {'pts': t.c.pts, 'trb': t.c.trb, 'ast': t.c.ast, 'stl': t.c.stl, 'blk': t.c.blk, 'x3pm': t.c.x3p, 'mp': t.c.mp, 'g': t.c.g})
    pct = {'fg_pct': (per(t.c.fg, t.c.fga), t.c.fga >= (60 if seasons else 300)), 'x3p_pct': (per(t.c.x3p, t.c.x3pa), t.c.x3pa >= (25 if seasons else 100)),
           'ft_pct': (per(t.c.ft, t.c.fta), t.c.fta >= (30 if seasons else 100)),
           'ts_pct': (t.c.pts / func.nullif(2 * (t.c.fga + 0.44 * t.c.fta), 0), t.c.fga >= (60 if seasons else 300))}
    stat = q.stat
    if q.scope == 'careers' and stat == 'titles':
        notes.append('Championships are listed under careers; showing career playoff games won’t help here.')
    if stat not in expr and stat not in pct:
        notes.drop(f'{STAT_LABEL.get(stat, stat)} isn’t available for the playoffs, so they’re ranked by points.')
        stat = 'pts'
    q.per_game_used = bool(q.per_game and not seasons and stat in ('pts', 'trb', 'ast', 'stl', 'blk', 'x3pm', 'mp'))
    rank, cond = (pct[stat][0], [pct[stat][1]]) if stat in pct else (expr[stat], [])
    if q.player_ids:
        cond = [t.c.player_id.in_(q.player_ids)]
    elif stat not in ('g',):
        cond.append(t.c.g >= (6 if seasons else 20))
    per_game = {'pts': per(t.c.pts, t.c.g), 'trb': per(t.c.trb, t.c.g_trb), 'ast': per(t.c.ast, t.c.g_ast)}
    for m_stat, op, v in q.minimums:
        e = per_game.get(m_stat) if m_stat in per_game else pct.get(m_stat, (None,))[0]
        if e is not None:
            cond.append(e < v if op == '<' else e >= v)
    if q.positions:
        cond.append(_career_position(p.c.player_id, q.positions))
    if 'hof' in q.honors:
        cond.append(p.c.hof.is_(True))
    for what, active in (('age', q.age_min is not None or q.age_max is not None), ('rookie seasons', q.rookie or q.sophomore),
                         ('playing style', bool(q.archetype)), ('award', bool(q.honors - {'hof'}))):
        if active:
            notes.drop(f'The {what} filter isn’t available for playoff stats, so it was ignored.')
    cols = [t.c.player_id, p.c.player, p.c.hof, p.c.pos, t.c.g, per(t.c.pts, t.c.g).label('ppg'), per(t.c.trb, t.c.g_trb).label('rpg'),
            per(t.c.ast, t.c.g_ast).label('apg'), t.c.pts, rank.label('value'), t.c.team]
    if seasons:
        cols.append(t.c.season)
    else:
        cols += [p.c.first_season, p.c.last_season]
    order = rank.asc() if q.order == 'asc' else rank.desc()
    stmt = select(*cols).join(p, p.c.player_id == t.c.player_id).where(rank.is_not(None), *cond).order_by(order, t.c.pts.desc()).limit(q.limit)
    rows = [dict(r) for r in conn.execute(stmt).mappings()]
    for r in rows:
        for k in ('ppg', 'rpg', 'apg'):
            r[k] = round(r[k], 1) if r[k] is not None else None
    return stat, rows


def run_games(conn, q, notes):
    """Single-game performances from the game logs."""
    pg, g, p = s.player_games, s.games, s.players
    expr = {'pts': pg.c.pts, 'trb': pg.c.trb, 'ast': pg.c.ast, 'stl': pg.c.stl, 'blk': pg.c.blk, 'x3pm': pg.c.x3p}
    stat = q.stat
    if stat not in expr:
        notes.drop(f'{STAT_LABEL.get(stat, stat)} isn’t a single-game stat, so games are ranked by points.')
        stat = 'pts'
    rank = expr[stat]
    cond = [rank.is_not(None)]
    if q.player_ids:
        cond.append(pg.c.player_id.in_(q.player_ids))
    if q.playoffs:
        cond.append(pg.c.playoffs.is_(True))
    if q.season_from:
        cond.append(pg.c.season >= q.season_from)
    if q.season_to:
        cond.append(pg.c.season <= q.season_to)
    for m_stat, op, v in q.minimums:
        if m_stat in expr:
            cond.append(expr[m_stat] < v if op == '<' else expr[m_stat] >= v)
    stmt = (select(pg.c.player_id, p.c.player, p.c.hof, pg.c.season, pg.c.team, pg.c.playoffs, g.c.date, g.c.home, g.c.away,
                   g.c.home_pts, g.c.away_pts, pg.c.pts, pg.c.trb, pg.c.ast, pg.c.mp, rank.label('value'))
            .join(p, p.c.player_id == pg.c.player_id).join(g, g.c.game_ref == pg.c.game_ref))
    if q.teams:
        ts = s.team_seasons
        stmt = stmt.join(ts, and_(ts.c.abbr == pg.c.team, ts.c.season == pg.c.season)).where(ts.c.team_name.in_(q.teams))
    if q.positions:
        cond.append(_position_clause(p.c.pos, {c[0] if c in ('PG', 'SG') else c for c in q.positions} | q.positions))
    for what, active in (('age', q.age_min is not None or q.age_max is not None), ('rookie seasons', q.rookie or q.sophomore),
                         ('playing style', bool(q.archetype)), ('award', bool(q.honors))):
        if active:
            notes.drop(f'The {what} filter isn’t available for single games, so it was ignored.')
    order = rank.asc() if q.order == 'asc' else rank.desc()
    rows = []
    for r in conn.execute(stmt.where(*cond).order_by(order, g.c.date).limit(q.limit)).mappings():
        r = dict(r)
        h, a = r.pop('home'), r.pop('away')
        hp, ap = r.pop('home_pts'), r.pop('away_pts')
        home = r['team'] == h
        r['opponent'] = a if home else h
        mine, theirs = (hp, ap) if home else (ap, hp)
        r['result'] = None if mine is None or theirs is None else ('W' if mine > theirs else 'L')
        r['score'] = None if mine is None else f'{mine}-{theirs}'
        r['home'] = home
        rows.append(r)
    return stat, rows


def franchises_of(conn, team_names):
    """Franchise lineages behind team names ("Minneapolis Lakers" and "Los Angeles Lakers" are one franchise)."""
    ts = s.team_seasons
    return [f for (f,) in conn.execute(select(ts.c.franchise).where(ts.c.team_name.in_(team_names)).distinct().order_by(ts.c.franchise))]


def run_team_titles(conn, q):
    """Championships won by the franchise(s) behind the team named in the question ("how many rings do the Lakers have")."""
    pt = s.playoff_teams
    out = []
    for fr in franchises_of(conn, q.teams):
        seasons = [x for (x,) in conn.execute(select(pt.c.season).where(pt.c.franchise == fr, pt.c.champion.is_(True)).order_by(pt.c.season))]
        finals = conn.execute(select(func.count()).select_from(pt).where(pt.c.franchise == fr, pt.c.rff_deepest == 0)).scalar() or 0
        out.append({'franchise': fr, 'titles': len(seasons), 'seasons': seasons, 'finals_appearances': finals})
    return sorted(out, key=lambda r: (-r['titles'], r['franchise']))


def team_answer_text(rows):
    label = lambda yr: f'{yr - 1}-{str(yr)[2:]}'
    parts = [f"{r['franchise']}: {r['titles']} championship{'s' if r['titles'] != 1 else ''}"
             + (f", most recent {label(r['seasons'][-1])}" if r['seasons'] else '') for r in rows]
    return '; '.join(parts) + '.'


# ---- questions about a team itself: record, best seasons, payroll, head to head -------------------------------------------------
INTENT_LABEL = {'record': 'team record', 'best': 'best team seasons', 'payroll': 'team payroll', 'head_to_head': 'head-to-head record'}
TEAM_TOTAL_STATS = ('pts', 'trb', 'ast', 'stl', 'blk', 'g')
TEAM_AVG_MIN_GAMES = 250            # a career average with one team needs a real sample too
PAYROLL_FIRST_SEASON = 1997         # 1996-97, the first season in the salary data


def season_label(season):
    return f'{season - 1}-{str(season)[2:]}'


def span_text(lo, hi):
    if lo and hi and lo == hi:
        return season_label(lo)
    if lo and hi:
        return f'{season_label(lo)} to {season_label(hi)}'
    if lo:
        return f'{season_label(lo)} on'
    return f'through {season_label(hi)}' if hi else ''


def win_pct_text(w, l):
    return f'{w / (w + l):.3f}'.lstrip('0') if w + l else '\u2014'


def result_phrase(result, champion, made_playoffs):
    if champion:
        return 'won the championship'
    if result and result.startswith('Lost in '):
        return 'lost in the ' + result[8:].lower()
    if result:
        return result.lower()
    return 'made the playoffs' if made_playoffs else 'missed the playoffs'


def team_table(title, columns, rows, note=None):
    return {'title': title, 'columns': [{'key': k, 'label': l} for k, l in columns], 'rows': rows, 'note': note}


def team_url(franchise):
    return f'/teams/{slugify(franchise)}'


def _blocked(kind, message):
    return [{'kind': kind, 'message': message, 'link': None, 'blocking': True}]


def two_team_names(conn, query, text, teams):
    """("Los Angeles Lakers", "Boston Celtics") for a question naming two teams, in the order they were mentioned."""
    others = [w for w in query.ignored if w in teams]
    if not (query.teams and others):
        return None
    t = text.lower()
    first = next((f.label.lower() for f in query.filters if f.kind == 'team'), '')
    pair = sorted([(t.find(first), query.teams), (t.find(others[0]), teams[others[0]])], key=lambda x: x[0])
    a, b = franchises_of(conn, pair[0][1]), franchises_of(conn, pair[1][1])
    return (a[0], b[0]) if a and b and a[0] != b[0] else None


def _team_seasons(conn, franchise, lo=None, hi=None):
    ts, pt = s.team_seasons, s.playoff_teams
    stmt = (select(ts.c.season, ts.c.team_name, ts.c.w, ts.c.l, ts.c.srs, ts.c.playoffs, pt.c.result, pt.c.champion)
            .select_from(ts.outerjoin(pt, and_(pt.c.season == ts.c.season, pt.c.team == ts.c.abbr)))
            .where(ts.c.franchise == franchise).order_by(ts.c.season))
    if lo:
        stmt = stmt.where(ts.c.season >= lo)
    if hi:
        stmt = stmt.where(ts.c.season <= hi)
    return [dict(r) for r in conn.execute(stmt).mappings()]


def _season_row(fr, r):
    return {'team': r['team_name'], 'team_url': team_url(fr), 'season': season_label(r['season']), 'record': f"{r['w']}-{r['l']}",
            'win_pct': win_pct_text(r['w'], r['l']), 'srs': r['srs'], 'result': result_phrase(r['result'], r['champion'], r['playoffs']).capitalize()}


def run_team_record(conn, q):
    """"lakers record in 2020", "how many wins did the bulls have in 1996", "celtics record in the 80s", "lakers record"."""
    lo, hi = q.season_from, q.season_to
    rows, parts = [], []
    all_time = not (lo or hi)
    for fr in franchises_of(conn, q.teams):
        seasons = _team_seasons(conn, fr, lo, hi)
        if not seasons:
            continue
        w, l = sum(r['w'] for r in seasons), sum(r['l'] for r in seasons)
        titles = sum(1 for r in seasons if r['champion'])
        champs = f"{titles} championship{'s' if titles != 1 else ''}"
        if len(seasons) == 1:
            r = seasons[0]
            rows.append(_season_row(fr, r))
            parts.append(f"{r['team_name']}, {season_label(r['season'])}: {r['w']}-{r['l']} ({win_pct_text(r['w'], r['l'])}), "
                         f"{result_phrase(r['result'], r['champion'], r['playoffs'])}")
        elif all_time:
            rows.append({'team': fr, 'team_url': team_url(fr), 'seasons': len(seasons), 'record': f'{w:,}-{l:,}', 'win_pct': win_pct_text(w, l),
                         'titles': titles, 'playoffs': sum(1 for r in seasons if r['playoffs'])})
            parts.append(f'{fr}: {w:,}-{l:,} all-time ({win_pct_text(w, l)}) over {len(seasons)} seasons, {champs}')
        else:
            rows += [_season_row(fr, r) for r in seasons]
            parts.append(f'{fr}, {span_text(lo, hi)}: {w:,}-{l:,} ({win_pct_text(w, l)}) over {len(seasons)} seasons, {champs}')
    if not rows:
        return None, None, [], _blocked('no_data', f"No season of that team matches {span_text(lo, hi) or 'that question'}.")
    cols = ([('team', 'Team'), ('seasons', 'Seasons'), ('record', 'Record'), ('win_pct', 'Win %'), ('titles', 'Titles'), ('playoffs', 'Playoff trips')]
            if all_time else [('team', 'Team'), ('season', 'Season'), ('record', 'Record'), ('win_pct', 'Win %'), ('srs', 'SRS'), ('result', 'Result')])
    table = team_table('Team record', cols, rows, 'Regular-season record. SRS is the team\u2019s average point margin, adjusted for schedule strength.')
    return table, '; '.join(parts) + '.', [], []


def run_team_best(conn, q, text):
    """"celtics best season", "best teams of the 90s", "worst team of the 2010s", "most wins in a season"."""
    ts, pt = s.team_seasons, s.playoff_teams
    asc = re.search(r'\b(?:worst|fewest|lowest)\b', text.lower()) is not None
    pct = cast(ts.c.w, Float) / func.nullif(ts.c.w + ts.c.l, 0)
    stmt = (select(ts.c.season, ts.c.franchise, ts.c.team_name, ts.c.w, ts.c.l, ts.c.srs, ts.c.playoffs, pt.c.result, pt.c.champion)
            .select_from(ts.outerjoin(pt, and_(pt.c.season == ts.c.season, pt.c.team == ts.c.abbr))).where(ts.c.w + ts.c.l > 0))
    frs = franchises_of(conn, q.teams) if q.teams else []
    if frs:
        stmt = stmt.where(ts.c.franchise.in_(frs))
    if q.season_from:
        stmt = stmt.where(ts.c.season >= q.season_from)
    if q.season_to:
        stmt = stmt.where(ts.c.season <= q.season_to)
    d = (lambda c: c.asc()) if asc else (lambda c: c.desc())
    order = [d(ts.c.w), d(pct)] if q.team_by_wins else [d(pct)]
    found = [dict(r) for r in conn.execute(stmt.order_by(*order, d(ts.c.srs).nulls_last(), d(ts.c.w)).limit(10)).mappings()]
    if not found:
        return None, None, [], _blocked('no_data', 'No team season matches that question.')
    rows = [dict(_season_row(r['franchise'], r), rank=i) for i, r in enumerate(found, start=1)]
    top = found[0]
    span = span_text(q.season_from, q.season_to)
    detail = (f"{season_label(top['season'])}, {top['w']}-{top['l']} ({win_pct_text(top['w'], top['l'])}), "
              f"{result_phrase(top['result'], top['champion'], top['playoffs'])}")
    if len(frs) == 1:
        lead = (f"{'Fewest' if asc else 'Most'} wins for the {frs[0]}" if q.team_by_wins else f"{'Worst' if asc else 'Best'} season for the {frs[0]}")
    else:
        lead = (f"{'Fewest' if asc else 'Most'} wins" if q.team_by_wins else f"{'Worst' if asc else 'Best'} team")
    if span:
        lead += f' in {span}'
    note = ('Ranked by regular-season wins; ties go to the higher win percentage.' if q.team_by_wins
            else 'Ranked by regular-season win percentage; ties go to the higher SRS (average point margin, adjusted for schedule).')
    cols = [('rank', '#'), ('team', 'Team'), ('season', 'Season'), ('record', 'Record'), ('win_pct', 'Win %'), ('srs', 'SRS'), ('result', 'Result')]
    return team_table('Worst team seasons' if asc else 'Best team seasons', cols, rows, note), f'{lead}: {detail}.', [], []


def run_team_payroll(conn, q):
    """"lakers payroll", "lakers payroll in 2020": from the team's salary history and current contract sheet."""
    frs = franchises_of(conn, q.teams)
    if not frs:
        return None, None, [], _blocked('no_data', 'I could not find that team.')
    fr = frs[0]
    data = team_salaries(fr, conn)
    cur, payroll = data['season'], data['payroll']
    lo, hi = q.season_from, q.season_to
    if lo or hi:
        rows = [x for x in payroll if (not lo or x['season'] >= lo) and (not hi or x['season'] <= hi)]
    else:
        rows = [x for x in payroll if cur - 7 <= x['season'] <= cur + 3]
    if not rows:
        return None, None, [], _blocked('no_data', f'I only have team payrolls from {season_label(PAYROLL_FIRST_SEASON)} on, '
                                                     f"so I can't answer for {span_text(lo, hi)}.")
    focus = rows[-1] if (lo or hi) else next((x for x in payroll if x['season'] == cur), rows[-1])
    money = lambda v: f'${v / 1e6:.1f}M'
    out = []
    for x in rows:
        avg = x.get('league_avg')
        out.append({'season': season_label(x['season']), 'payroll': money(x['total']), 'players': x['players'],
                    'league_avg': money(avg) if avg else '\u2014', 'vs_avg': f"{(x['total'] / avg - 1) * 100:+.0f}%" if avg else '\u2014',
                    'kind': 'Contracts committed' if x['kind'] == 'committed' else 'Paid'})
    answer = f"{fr} payroll, {season_label(focus['season'])}: {money(focus['total'])}"
    if focus.get('league_avg'):
        answer += f" ({(focus['total'] / focus['league_avg'] - 1) * 100:+.0f}% vs the league average of {money(focus['league_avg'])})"
    elif focus['kind'] == 'committed':
        answer += ' in contracts committed so far'
    cols = [('season', 'Season'), ('payroll', 'Payroll'), ('players', 'Players'), ('league_avg', 'League average'), ('vs_avg', 'vs league'), ('kind', '')]
    note = 'Payroll counts money owed to waived players. Salary data starts in 1996-97; future seasons are contracts already signed.'
    return team_table(f'{fr} payroll', cols, out, note), answer + '.', [{'label': f'{fr} team page', 'url': team_url(fr)}], []


def run_head_to_head(conn, a, b):
    h = h2h_teams(a, b, conn)
    reg, po, n_series = h['regular'], h['playoffs'], len(h['series'])
    link = [{'label': 'Compare the two teams', 'url': f'/compare/teams/{slugify(a)}/{slugify(b)}'}]
    if not reg['games'] and not po['games']:
        return None, f'{a} vs {b}: no games between them are recorded.', link, []
    answer = f"{a} vs {b}, regular season: {a} {reg['a_wins']}-{reg['b_wins']} over {reg['games']} games"
    if n_series:
        answer += f"; playoff series: {a} won {h['series_a_won']} of {n_series}"
    rows = [{'metric': 'Regular-season wins', 'a': reg['a_wins'], 'b': reg['b_wins']},
            {'metric': 'Regular-season points per game', 'a': reg['a_ppg'], 'b': reg['b_ppg']},
            {'metric': 'Playoff game wins', 'a': po['a_wins'], 'b': po['b_wins']},
            {'metric': 'Playoff series won', 'a': h['series_a_won'], 'b': n_series - h['series_a_won']}]
    note = f"Since {h['first_meeting']}, from the game logs. Franchise lineages are combined (Minneapolis and Los Angeles Lakers count as one team)."
    return team_table(f'{a} vs {b}', [('metric', 'Head to head'), ('a', a), ('b', b)], rows, note), answer + '.', link, []


def run_team_intent(conn, intent, query, text, pair):
    """(table, answer, links, blocking) for a question about a team itself rather than its players."""
    if intent == 'head_to_head':
        return run_head_to_head(conn, *pair)
    if intent == 'record':
        return run_team_record(conn, query)
    if intent == 'best':
        return run_team_best(conn, query, text)
    return run_team_payroll(conn, query)


def run_team_careers(conn, q, notes):
    """Career totals (or averages) for one franchise: "most career points with the Celtics", "who scored the most for the Lakers".
    Built from each player's team stints, because a player's stored career total counts a season he was traded twice. A player
    whose whole career was with this franchise keeps his exact stored total; a traded player's total is rebuilt from per-game
    averages times games, so it can be off by a few points (marked approx)."""
    p, ps, ts = s.players, s.player_seasons, s.team_seasons
    stat = q.stat
    per_game = bool(q.per_game and stat != 'g')
    where = [ps.c.combined.is_(False), ts.c.franchise.in_(franchises_of(conn, q.teams))]
    if q.season_from:
        where.append(ps.c.season >= q.season_from)
    if q.season_to:
        where.append(ps.c.season <= q.season_to)
    tm = (select(ps.c.player_id, func.sum(ps.c.g).label('g'), func.count().label('n_team'), func.min(ps.c.season).label('first_season'),
                 func.max(ps.c.season).label('last_season'), *[func.sum(ps.c[k] * ps.c.g).label(k) for k in ('pts', 'trb', 'ast', 'stl', 'blk')])
          .select_from(ps.join(ts, and_(ts.c.abbr == ps.c.team, ts.c.season == ps.c.season)))
          .where(*where).group_by(ps.c.player_id).subquery())
    n_all = select(ps.c.player_id, func.count().label('n_all')).where(ps.c.combined.is_(False)).group_by(ps.c.player_id).subquery()
    whole = false() if (q.season_from or q.season_to) else (tm.c.n_team == n_all.c.n_all)

    def total(col):
        return case((whole, p.c[col]), else_=func.round(tm.c[col] + 1e-6))
    if stat == 'g':
        value, approx = tm.c.g, false()
    elif per_game:
        value, approx = tm.c[stat] * 1.0 / func.nullif(tm.c.g, 0), false()
    else:
        value, approx = total(stat), case((whole, false()), else_=true())
    cond = [p.c.player_id.in_(q.player_ids)] if q.player_ids else ([tm.c.g >= TEAM_AVG_MIN_GAMES] if per_game else [])
    if q.positions:
        cond.append(_career_position(p.c.player_id, q.positions))
    if 'hof' in q.honors:
        cond.append(p.c.hof.is_(True))
    if 'all_star' in q.honors:
        cond.append(p.c.all_star >= 1)
    for what, active in (('age', q.age_min is not None or q.age_max is not None), ('rookie seasons', q.rookie or q.sophomore),
                         ('playing style', bool(q.archetype)), ('award', bool(q.honors - {'hof', 'all_star'}))):
        if active:
            notes.drop(f'The {what} filter applies to single seasons, so it was ignored for careers.')
    if per_game and not q.player_ids:
        notes.append(f'Career averages with a team only count players with at least {TEAM_AVG_MIN_GAMES} games for it.')
    per = lambda col: tm.c[col] * 1.0 / func.nullif(tm.c.g, 0)
    stmt = (select(p.c.player_id, p.c.player, p.c.hof, p.c.pos, tm.c.first_season, tm.c.last_season, tm.c.g,
                   total('pts').label('pts'), total('trb').label('trb'), total('ast').label('ast'),
                   per('pts').label('ppg'), per('trb').label('rpg'), per('ast').label('apg'), value.label('value'), approx.label('approx'))
            .select_from(tm.join(p, p.c.player_id == tm.c.player_id).join(n_all, n_all.c.player_id == tm.c.player_id))
            .where(value.is_not(None), tm.c.g >= 1, *cond)
            .order_by(value.asc() if q.order == 'asc' else value.desc(), tm.c.pts.desc()).limit(q.limit))
    rows = [dict(r) for r in conn.execute(stmt).mappings()]
    for r in rows:
        for k in ('pts', 'trb', 'ast'):
            r[k] = int(r[k]) if r[k] is not None else None
        for k in ('ppg', 'rpg', 'apg'):
            r[k] = round(r[k], 1) if r[k] is not None else None
        r['value'] = round(r['value'], 2) if per_game else int(r['value'])
        r['approx'] = bool(r['approx'])
    q.per_game_used = per_game
    if any(r['approx'] for r in rows):
        notes.append('Team totals for players who also played for other teams are rebuilt from per-game averages, so they can be off by a few points.')
    return stat, rows


class Notes(list):
    """The notes shown with a result. drop() also records that part of the question could not be applied, so the page
    can say so instead of stating the answer as if nothing had been left out."""

    def __init__(self):
        super().__init__()
        self.dropped: list[str] = []

    def drop(self, message):
        self.append(message)
        self.dropped.append(message)


# Things the question can name that this search cannot answer (yet).
NO_DATA_WORDS = {'attendance', 'coach', 'coaches', 'arena', 'owner', 'owners', 'mascot', 'ticket', 'tickets', 'jersey', 'jerseys'}
TEAM_RECORD_WORDS = {'record', 'records', 'wins', 'win', 'won', 'losses', 'loss', 'lost', 'standings', 'games'}
TEAM_MONEY_WORDS = {'payroll', 'cap'}
ROUND_WORDS = {'finals', 'semifinals', 'quarterfinals', 'round'}
OPPONENT_RE = re.compile(r'\b(?:against|versus|vs)\b')
# leftover words that are just chatter, not a stat the user is asking about
FILLER = {'who', 'whos', 'what', 'whats', 'which', 'please', 'tell', 'about', 'ever', 'now', 'today', 'currently', 'right', 'still',
          'just', 'really', 'also', 'is', 'are', 'the', 'me', 'show', 'give', 'list', 'goat', 'nba', 'basketball', 'player', 'players'}


def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def fallback_query(text, teams, archetypes, latest):
    """Seam for a smarter parser. Asked first when a question is blocked; return a parsed Query to answer it, or None to
    explain why it cannot be answered. Nothing is plugged in yet: an LLM turning the text into the same Query object
    (so the filter chips and the SQL path stay the same) would go here, behind a flag, and be checked against the
    golden question set before it is switched on."""
    return None


def explain_unsupported(conn, query, text, teams, has_card, understood, has_link):
    """Blocking reasons a question cannot be answered as asked. Checked before any ranking runs, so an unrelated
    ranking is never presented as the answer."""
    t = text.lower()
    words = set(re.findall(r"[a-z0-9'-]+", t))
    ign = [w for w in (x[:-2] if x.endswith("'s") else x for x in query.ignored) if w not in FILLER]

    def team_link(names):
        found = franchises_of(conn, names)
        return {'label': f'{found[0]} team page', 'url': f'/teams/{slugify(found[0])}'} if found else None

    def blocked(kind, message, link=None):
        return [{'kind': kind, 'message': message, 'link': link, 'blocking': True}]

    others = [w for w in query.ignored if w in teams]
    if query.teams and others:                                  # "lakers vs celtics": only one team can be used
        first = next((f.label.lower() for f in query.filters if f.kind == 'team'), '')
        pair = sorted([(t.find(first), query.teams), (t.find(others[0]), teams[others[0]])], key=lambda x: x[0])
        a, b = franchises_of(conn, pair[0][1]), franchises_of(conn, pair[1][1])
        link = {'label': 'Compare the two teams', 'url': f'/compare/teams/{slugify(a[0])}/{slugify(b[0])}'} if a and b else None
        return blocked('two_teams', 'I can only use one team per question. To compare two teams, use the team comparison page.', link)
    if query.teams and OPPONENT_RE.search(t):
        return blocked('opponent', 'I can\u2019t filter by opponent yet. Team pages show head-to-head records.', team_link(query.teams))
    if ROUND_WORDS & set(ign):
        return blocked('playoff_round', 'I can\u2019t filter playoff stats by round (for example the Finals) yet.')
    if query.teams and not has_card and not query.stat_given and words & TEAM_RECORD_WORDS:
        return blocked('team_record', 'I can\u2019t answer team win-loss records here yet. They are on each team\u2019s page, under Seasons.',
                       team_link(query.teams))
    if query.teams and TEAM_MONEY_WORDS & set(ign):
        return blocked('team_money', 'I can\u2019t answer team payroll here yet. It is on each team\u2019s page, under Salaries.',
                       team_link(query.teams))
    nodata = sorted(NO_DATA_WORDS & set(ign))
    if nodata:
        return blocked('no_data', f'I don\u2019t have {nodata[0]} data, so I can\u2019t answer that.')
    if ign and not query.stat_given and (understood or has_card) and not has_link:
        return blocked('unknown_stat', 'I can\u2019t answer that yet: I don\u2019t recognize \u201c' + ' '.join(ign) + '\u201d as a stat or filter I have.')
    return []


def _understood(query):
    return query.understood and (query.stat_given or query.superlative or any(
        f.kind not in ('limit', 'scope', 'stat', 'player') for f in query.filters))


def answer_text(query, stat, label, rows, scope, playoffs, card, per_game=False):
    """A one-line answer for "who/which/how many" questions and questions about one named player."""
    if not rows:
        return None
    def fmt(v):
        if v is None:
            return '—'
        if stat in PCT:
            return f'{v * 100:.1f}%'
        if stat == 'height':
            return f"{int(v) // 12}'{int(v) % 12}\""
        if stat == 'salary':
            return f'${v / 1e6:.1f}M'
        if stat == 'titles':
            return f"{int(v)} championship{'s' if int(v) != 1 else ''}"
        if stat == 'age':
            return f'age {int(v)}'
        if per_game:
            return f'{v:.1f} {label.lower().replace("career ", "")}'
        if scope in ('careers', 'games') and stat not in ('ws', 'vorp'):
            return f'{approx}{int(round(v)):,} {label.lower().replace("career ", "").replace("playoff ", "")}'.strip()
        return f'{v:.1f} {label.lower()}'
    top = rows[0]
    approx = '≈ ' if top.get('approx') else ''
    if query.player_ids and len(query.player_ids) == 1:
        if scope == 'games':
            return f"{top['player']}: {len(rows)}{'+' if len(rows) == query.limit else ''} game{'s' if len(rows) != 1 else ''}. Best: {top['date']}, {fmt(top['value'])}."
        if scope == 'careers':
            return f"{top['player']}: {fmt(top['value'])}."
        if scope == 'seasons':
            seasons = [str(x) for x in sorted(r['season'] for r in rows)]
            if len(rows) == 1:
                return f"{top['player']}, {top['season']}: {fmt(top['value'])}."
            return f"{top['player']}: {len(rows)} seasons match{' (' + ', '.join(seasons) + ')' if len(rows) <= 12 else ''}. Best: {top['season']}, {fmt(top['value'])}."
    asks = re.match(r'\s*(who|which|what|whose|how many|name)\b', query.text.lower()) or query.limit == 1
    if not asks:
        return None
    where = (f", {top['season']}" if scope == 'seasons' else f", {top['date']}" if scope == 'games' else
             f" ({top.get('first_season')}–{top.get('last_season')})" if top.get('first_season') else '')
    return f"{top['player']}{where}: {fmt(top['value'])}{' in the playoffs' if playoffs and scope != 'games' else ''}."


@router.get('/search', summary='Natural-language search: "best rebounding guards of the 90s"')
def search(q: str = Q(..., min_length=1, max_length=200), drop: list[int] = Q([], description='Indexes of filters to remove'),
           scope: Literal['seasons', 'careers', 'games'] | None = Q(None, description='Override seasons vs. careers vs. single games'),
           conn=Depends(get_conn)):
    teams, archetypes, latest, archetypes_list = vocab(conn)
    query = parse(q, teams, archetypes, latest)

    # named players
    pids, name_words = find_players(conn, q, query.ignored)
    query.ignored = [w for w in query.ignored if not set(re.split(r"[-']", w)) <= name_words]
    compare = None
    card = None
    names = {}
    if pids:
        names = dict(conn.execute(select(s.players.c.player_id, s.players.c.player).where(s.players.c.player_id.in_(pids))).all())
        query.ignored = [w for w in query.ignored if w not in ('vs', 'versus', 'compare', 'compared', 'or', 'better', 'than', 'and', 'tall', 'old')]
    if len(pids) >= 2:
        a, b = pids[:2]
        compare = {'a': {'player_id': a, 'player': names.get(a)}, 'b': {'player_id': b, 'player': names.get(b)},
                   'url': f'/compare/players/{a}/{b}', 'cards': [player_card(conn, a), player_card(conn, b)]}
    elif len(pids) == 1:
        query.player_ids = pids
        if query.scope == 'games' and query.limit == 25:
            query.limit = 100                   # all of one player's qualifying games
        if (query.per_game and query.scope == 'seasons' and not query.season_from and not query.season_to and not query.superlative
                and not re.search(r'\bseasons?\b|\bwhen\b|\bwhich year\b', q.lower())):
            query.scope = 'careers'             # "how many points does lebron average": his career average, not a list of seasons
            query.filters.append(Filter('scope', 'careers'))
        query.filters.append(Filter('player', names.get(pids[0]), pids[0]))
        card = player_card(conn, pids[0])

    if scope:
        query.scope = scope
        query.filters = [f for f in query.filters if f.kind != 'scope']
    drop_filters(query, drop)
    if not query.player_ids:
        card = None
    notes = Notes()
    understood = _understood(query)
    has_link = any(re.search(pattern, q.lower()) for pattern, _, _ in LINKS)
    pair = None if (compare or card) else two_team_names(conn, query, q, teams)
    intent = None if (compare or card) else ('head_to_head' if pair else query.team_intent)
    if intent:
        understood, query.ignored = True, []          # a question about a team itself: read, and answered below
    blocking = [] if (compare or intent) else explain_unsupported(conn, query, q, teams, card is not None, understood, has_link)
    if blocking:
        alt = fallback_query(q, teams, archetypes, latest)          # nothing plugged in yet: returns None
        if alt is not None:
            alt.player_ids = alt.player_ids or query.player_ids
            query, blocking = alt, []
            understood = _understood(query)
    rows, stat, team_rows = [], query.stat, []
    table, table_answer, extra_links = None, None, []
    team_question = query.team_titles and query.stat == 'titles' and bool(query.teams) and not query.player_ids
    if compare or (card and not understood):
        pass                                    # a comparison, or a question that's only a name: the cards answer it
    elif intent:
        table, table_answer, extra_links, blocking = run_team_intent(conn, intent, query, q, pair)
    elif blocking:
        pass                                    # explained below, not answered with an unrelated ranking
    elif team_question:
        team_rows = run_team_titles(conn, query)    # a question about the team, not a ranking of players
    elif query.scope == 'games':
        stat, rows = run_games(conn, query, notes)
    elif query.playoffs:
        stat, rows = run_playoffs(conn, query, notes)
    elif query.scope == 'careers':
        stat, rows = run_careers(conn, query, notes)
    else:
        rows = run_seasons(conn, query, archetypes_list, notes)
        stat = query.stat

    if query.scope == 'games':
        label = GAME_LABEL.get(stat, STAT_LABEL.get(stat, stat))
    elif query.playoffs:
        label = (PLAYOFF_CAREER_LABEL if query.scope == 'careers' and not query.per_game_used else PLAYOFF_SEASON_LABEL).get(stat, STAT_LABEL.get(stat, stat))
    elif query.scope == 'careers':
        label = (CAREER_AVG_LABEL if query.per_game_used else CAREER_LABEL).get(stat, STAT_LABEL[stat])
    else:
        label = STAT_LABEL[stat]
    for f in query.filters:
        if f.kind == 'stat':
            f.label = ('lowest ' if query.order == 'asc' and stat not in ('age', 'height') else '') + label
            if stat == 'age':
                f.label = 'youngest first' if query.order == 'asc' else 'oldest first'
            if stat == 'height':
                f.label = 'shortest first' if query.order == 'asc' else 'tallest first'
    if intent:
        for f in query.filters:
            if f.kind == 'stat':
                f.label = INTENT_LABEL[intent]

    # nothing recognized, not even a name: look for players by name
    name_matches = []
    words = [w for w in normalize_name(q).split() if len(w) > 1]
    if not pids and (not understood or (query.ignored and len(query.ignored) == len(words))):
        cond = [s.players.c.name_search.contains(w, autoescape=True) for w in words] or [s.players.c.player_id == '']
        name_matches = [dict(r) for r in conn.execute(select(s.players.c.player_id, s.players.c.player, s.players.c.hof,
                                                             s.players.c.first_season, s.players.c.last_season)
                                                      .where(*cond).order_by(s.players.c.pts.desc().nulls_last()).limit(8)).mappings()]
    if not understood and not pids:
        rows = []
    links = [{'label': label_, 'url': url} for pattern, label_, url in LINKS if re.search(pattern, q.lower())]
    if links and re.search(r'\b(will|odds|predict\w*|favou?rites?|projected|going to|next)\b', q.lower()):
        rows, understood = [], False             # a question about the future: the model pages answer it
    if links and not understood:
        query.ignored = []
    links = links + extra_links
    answer = None if compare else answer_text(query, stat, label, rows, query.scope, query.playoffs, card, query.per_game_used)
    if team_rows:
        answer = team_answer_text(team_rows)
    if table_answer:
        answer = table_answer
    if card and not rows and card.get('age') and re.search(r'\bhow old\b|\bage\b', q.lower()):
        answer = f"{card['player']} was {card['age']} in the {card['age_season'] - 1}-{str(card['age_season'])[2:]} season."
    caution = [{'kind': 'ignored_filter', 'message': m, 'link': None, 'blocking': False} for m in notes.dropped]
    unsupported = blocking + caution
    if unsupported:
        answer = None                           # never state a direct answer to a question we could not fully read
    shown = understood and not compare and not (card and not understood)
    return {
        'query': q, 'scope': query.scope, 'playoffs': query.playoffs, 'stat': stat, 'stat_label': label, 'stat_is_pct': stat in PCT,
        'order': query.order,
        'filters': [{'index': f.index, 'kind': f.kind, 'label': f.label} for f in query.filters],
        'dropped': sorted(set(drop)),
        'ignored': query.ignored, 'notes': notes, 'understood': shown, 'answer': answer,
        'player': card if not compare else None, 'compare': compare, 'links': links,
        'results': rows, 'name_matches': name_matches,
        'examples': EXAMPLES if not rows and not name_matches and not card and not compare and not links and not team_rows and not table else [],
        'stat_is_avg': query.per_game_used, 'team_results': team_rows, 'unsupported': unsupported, 'team_table': table,
        'season_note': 'Seasons are labeled by the year they ended: 2016 is the 2015-16 season.' if query.scope == 'seasons' else None,
    }
