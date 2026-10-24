"""Load data/*.json (produced by scripts/prep_data.py) into the database.

Usage (from the repo root):
    python -m backend.etl.load_db                          # local SQLite: backend/nba.db
    DATABASE_URL=postgresql://... python -m backend.etl.load_db

Every run is a full refresh: tables are dropped and recreated in one
transaction, so the API never sees a half-loaded database on PostgreSQL.
"""
import argparse
import os
import csv
import gzip
import io
import hashlib
import json
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from backend.app import schema
from backend.app.db import database_url, make_engine

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / 'data'
MULTITEAM = {'2TM', '3TM', '4TM', '5TM'}
BATCH = 5000


def normalize_name(name: str) -> str:
    """Same rule as the frontend search: strip accents, lowercase."""
    return ''.join(c for c in unicodedata.normalize('NFD', name) if not unicodedata.combining(c)).lower()


def read(name):
    return json.loads((DATA / f'{name}.json').read_text())


def as_dicts(payload):
    """{'columns': [...], 'rows': [[...]]} or a list of dicts -> list of dicts."""
    if isinstance(payload, list):
        return payload
    cols = payload['columns']
    return [dict(zip(cols, row)) for row in payload['rows']]


def keep_columns(table, rows):
    """Only the table's columns, and the same keys in every row (bulk inserts need
    that): a column some rows lack is filled with NULL. Columns no row has at all,
    like auto-numbered ids, are left out so the database fills them."""
    names = {c.name for c in table.columns}
    present = sorted({k for r in rows for k in r if k in names})
    return [{k: r.get(k) for k in present} for r in rows]


def insert(conn, table, rows):
    for i in range(0, len(rows), BATCH):
        conn.execute(table.insert(), rows[i:i + BATCH])
    return len(rows)


def build_rows():
    """Read every data file and shape it for its table."""
    players = as_dicts(read('player_career'))
    seasons = as_dicts(read('player_seasons'))
    # Players in the newest games who aren't in the Basketball-Reference tables yet (this year's rookies), built by
    # scripts/prep_games_eoin.py. An official row for the same id always wins.
    if (DATA / 'new_players.json').exists():
        extra = read('new_players')
        official = {p['player_id'] for p in players}
        players += [p for p in extra['players'] if p['player_id'] not in official]
        seasons += [r for r in extra['seasons'] if r['player_id'] not in official]
    for p in players:
        p['name_search'] = normalize_name(p['player'])
    known = {p['player_id'] for p in players}

    for s in seasons:
        s['combined'] = s['team'] in MULTITEAM

    similar = read('similar_players')
    style = [{'player_id': pid, **dict(zip(similar['features'], vals))}
             for pid, vals in similar['players'].items()]
    neighbors = [{'player_id': pid, 'rank': rank, 'similar_id': other, 'score': score}
                 for pid, lst in similar['neighbors'].items()
                 for rank, (other, score) in enumerate(lst, start=1)]

    mvp = read('mvp_model') if (DATA / 'mvp_model.json').exists() else None
    champ = read('champion_model') if (DATA / 'champion_model.json').exists() else None
    pay = as_dicts(read('player_salaries')) if (DATA / 'player_salaries.json').exists() else []
    con = read('contracts') if (DATA / 'contracts.json').exists() else None
    con_details = [dict(zip(con['detail_columns'], d)) for d in con['details']] if con else []
    for d in con_details:
        d['notes'] = json.dumps(d['notes'])
    roles = read('archetypes') if (DATA / 'archetypes.json').exists() else None
    MIN_SHARE = 3                                     # percent; smaller shares are noise
    season_mix = [{'player_id': r['player_id'], 'season': r['season'], 'archetype_id': a, 'share': v}
                  for r in (as_dicts(roles) if roles else []) for a, v in enumerate(r.get('mix') or []) if v >= MIN_SHARE]
    career_mix = [{'player_id': pid, 'archetype_id': a, 'share': v}
                  for pid, m in ((roles or {}).get('career_mix') or {}).items() for a, v in enumerate(m) if v >= MIN_SHARE]
    proj = read('projections') if (DATA / 'projections.json').exists() else None
    proj_rows = [{'player_id': p['player_id'], **{k: v for k, v in hz.items() if k != 'n_comps'}}
                 for p in (proj or {}).get('players', []) for hz in p['horizons']]
    proj_comps = [{'player_id': p['player_id'], 'rank': i, 'comp_id': c['player_id'], 'comp_season': c['season'],
                   'similarity': c['similarity']}
                  for p in (proj or {}).get('players', []) for i, c in enumerate(p['comps'], start=1)]

    # playoffs: map each season's team abbreviation to its franchise via team_geo
    geo = as_dicts(read('team_geo'))
    franchise_of = {(g['season'], g['abbr']): g['franchise'] for g in geo}
    def fr(season, abbr):
        return franchise_of.get((season, abbr))
    have_playoffs = (DATA / 'playoff_series.json').exists()
    p_series, p_teams, p_players, p_titles = [], [], [], []
    if have_playoffs:
        p_series = [dict(r, franchise_a=fr(r['season'], r['team_a']), franchise_b=fr(r['season'], r['team_b']),
                         winner_franchise=fr(r['season'], r['winner'])) for r in as_dicts(read('playoff_series'))]
        p_teams = [dict(r, franchise=fr(r['season'], r['team'])) for r in as_dicts(read('playoff_teams'))]
        p_players = [dict(r, franchise=fr(r['season'], r['team'])) for r in as_dicts(read('player_playoffs'))]
        p_titles = [dict(r, franchise=fr(r['season'], r['team'])) for r in as_dicts(read('player_titles'))]
        unmapped = {(r['season'], t) for r in p_series for t in (r['team_a'], r['team_b']) if fr(r['season'], t) is None}
        if unmapped:
            raise SystemExit(f'playoff teams with no franchise in team_geo: {sorted(unmapped)[:10]}')

    per_player = {
        schema.player_playoffs: p_players,
        schema.player_titles: p_titles,
        schema.player_seasons: seasons,
        schema.player_advanced: as_dicts(read('player_advanced')),
        schema.player_per100: as_dicts(read('player_per100')),
        schema.player_shooting: as_dicts(read('player_shooting')),
        schema.player_pbp: as_dicts(read('player_pbp')),
        schema.player_style: style,
        schema.similar_players: neighbors,
        schema.mvp_candidates: as_dicts(mvp) if mvp else [],
        schema.player_archetypes: as_dicts(roles) if roles else [],
        schema.player_archetype_mix: season_mix,
        schema.player_style_mix: career_mix,
        schema.player_projections: proj_rows,
        schema.player_salaries: pay,
        schema.projection_comps: [dict(c, similar_id=c['comp_id']) for c in proj_comps],
    }
    dropped = {}
    for table, rows in per_player.items():
        ok = [r for r in rows if r['player_id'] in known and r.get('similar_id', r['player_id']) in known]
        if len(ok) != len(rows):
            dropped[table.name] = len(rows) - len(ok)
        per_player[table] = ok

    return {
        schema.players: players,
        **per_player,
        schema.award_shares: as_dicts(read('player_award_shares')),
        schema.eos_teams: as_dicts(read('player_eos_teams')),
        schema.all_stars: as_dicts(read('all_star')),
        schema.draft_picks: as_dicts(read('draft')),
        schema.team_seasons: geo,
        schema.champion_candidates: as_dicts(champ) if champ else [],
        schema.contract_salaries: as_dicts(con) if con else [],
        schema.contracts: con_details,
        schema.playoff_series: p_series,
        schema.playoff_teams: p_teams,
        schema.finals_mvp: [r for r in (as_dicts(read('finals_mvp')) if (DATA / 'finals_mvp.json').exists() else []) if r['player_id'] in known],
        schema.league_trends: read('era_trends'),
        schema.league_env: as_dicts(read('league_env')),
        schema.league_shooting: as_dicts(read('league_avg_shooting')),
    }, dropped, {'mvp': mvp, 'roles': roles, 'proj': proj, 'champ': champ, 'contracts': con}


def data_fingerprint() -> str:
    """Hash of every data/*.json file plus the code that loads them (this file
    and the table definitions), stored with each load. The server reloads when
    it changes, so new data, new tables or a loader fix all take effect on the
    next start, even if only some files were updated."""
    h = hashlib.sha256()
    code = [Path(__file__), Path(schema.__file__)]
    for path in sorted(DATA.glob('*.json')) + sorted((DATA / 'games').glob('*.csv.gz')) + code:
        h.update(path.name.encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def loaded_fingerprint(engine):
    """Fingerprint of the data currently in the database, or None if it was never loaded."""
    from sqlalchemy import inspect, select
    if not inspect(engine).has_table('meta'):
        return None
    with engine.connect() as conn:
        found = conn.execute(select(schema.meta.c.value).where(schema.meta.c.key == 'data_fingerprint')).scalar()
    return found or ''          # '' = loaded by an older version, before fingerprints


def ensure_loaded(engine, log=print) -> bool:
    """Load the stats if the database is empty or holds older data than data/.
    Never touches account tables. Returns True if it loaded."""
    current = data_fingerprint()
    found = loaded_fingerprint(engine)
    if found == current:
        return False
    log('Stats database is empty; loading data/*.json (one time)...' if found is None
        else 'Data or loader code changed since the last load; reloading the stats tables...')
    load(engine.url.render_as_string(hide_password=False), quiet=True)
    log('Stats loaded.')
    return True


def _int(v):
    return None if v in ('', None) else int(float(v))


def _num(v):
    return None if v in ('', None) else float(v)


def _bool(v):
    return None if v in ('', None, '<NA>') else v in ('True', 'true', '1')


GAME_STATS = ['fg', 'fga', 'x3p', 'x3pa', 'ft', 'fta', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf', 'pts', 'pm']


class _Writer:
    """Inserts rows in batches; on PostgreSQL uses COPY, which is many times faster for 1.5M rows."""
    def __init__(self, conn, table, batch):
        self.conn, self.table, self.batch, self.buf, self.n = conn, table, batch, [], 0
        self.cols = [c.name for c in table.columns]
        self.pg = conn.dialect.name == 'postgresql'

    def add(self, row):
        self.buf.append(row)
        if len(self.buf) >= self.batch:
            self.flush()

    def flush(self):
        if not self.buf:
            return
        if self.pg:
            cur = self.conn.connection.dbapi_connection.cursor()       # same transaction as the rest of the load
            with cur.copy(f'COPY {self.table.name} ({", ".join(self.cols)}) FROM STDIN') as cp:
                for r in self.buf:
                    cp.write_row(tuple(r.get(c) for c in self.cols))
        else:
            self.conn.execute(self.table.insert(), self.buf)
        self.n += len(self.buf)
        self.buf = []


def load_games(conn, known, franchise_of, batch=20000):
    """Stream data/games/*.csv.gz into games / player_games in batches (1.5M rows don't fit comfortably in memory as dicts)."""
    gdir = DATA / 'games'
    counts = {'games': 0, 'player_games': 0, 'player_games_skipped': 0}
    last_season = max((s for s, _ in franchise_of), default=0)
    newest = {a: f for (s, a), f in sorted(franchise_of.items())}          # abbreviation -> franchise in its latest season

    def franchise(season, abbr):
        """A season newer than the team data (the current season's games) uses each team's latest known franchise."""
        return franchise_of.get((season, abbr)) or (newest.get(abbr) if season > last_season else None)
    for f in sorted(gdir.glob('games_*.csv.gz')) if gdir.exists() else []:
        season = int(f.name.split('_')[1].split('.')[0])
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            rows = [{'game_ref': r['game_ref'], 'season': int(r['season']), 'date': r['date'], 'home': r['home'], 'away': r['away'],
                     'home_franchise': franchise(season, r['home']), 'away_franchise': franchise(season, r['away']),
                     'home_pts': _int(r['home_pts']), 'away_pts': _int(r['away_pts']), 'ot': _int(r.get('ot')),
                     'playoffs': _bool(r['playoffs']) or False, 'series': r.get('series') or None, 'src': r.get('src') or None,
                     'kind': r.get('kind') or ('playoffs' if _bool(r['playoffs']) else 'regular'),
                     'complete': _bool(r.get('complete')) or False} for r in csv.DictReader(fh)]
        gw = _Writer(conn, schema.games, batch)
        for r in rows:
            gw.add(r)
        gw.flush()
        counts['games'] += len(rows)
        info = {r['game_ref']: (r['playoffs'], r['kind']) for r in rows}
        pf = gdir / f'player_games_{season}.csv.gz'
        if not pf.exists():
            continue
        w = _Writer(conn, schema.player_games, batch)
        seen = set()
        with gzip.open(pf, 'rt', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                key = (r['player_id'], r['game_ref'], r['team'])
                if key in seen:
                    raise SystemExit(f'{pf.name}: duplicate player-game {key}')
                seen.add(key)
                if r['player_id'] not in known or r['game_ref'] not in info:
                    counts['player_games_skipped'] += 1
                    continue
                row = {'player_id': r['player_id'], 'game_ref': r['game_ref'], 'season': season, 'playoffs': info[r['game_ref']][0], 'kind': info[r['game_ref']][1],
                       'team': r['team'] or None, 'started': _bool(r.get('started')), 'mp': _num(r.get('mp')), 'src': r.get('src') or None}
                for k in GAME_STATS:
                    row[k] = _int(r.get(k))
                w.add(row)
        w.flush()
        counts['player_games'] += w.n
    return counts


def load(url=None, quiet=False):
    started = time.time()
    tables, dropped, models = build_rows()
    mvp, roles, proj, champ, con = models['mvp'], models['roles'], models['proj'], models['champ'], models['contracts']
    engine = make_engine(url)
    latest = max(r['season'] for r in tables[schema.league_trends])
    with engine.begin() as conn:
        schema.metadata.drop_all(conn)
        schema.metadata.create_all(conn)
        counts = {}
        for table, rows in tables.items():          # dict order = FK-safe order
            counts[table.name] = insert(conn, table, keep_columns(table, rows))
        known = {r['player_id'] for r in tables[schema.players]}
        franchise_of = {(r['season'], r['abbr']): r['franchise'] for r in tables[schema.team_seasons]}
        if os.environ.get('LOAD_GAMES', '1') != '0':        # LOAD_GAMES=0 skips the 1.5M game rows (tests of reload mechanics)
            g = load_games(conn, known, franchise_of)
            counts['games'], counts['player_games'] = g['games'], g['player_games']
        insert(conn, schema.meta, [
            {'key': 'latest_season', 'value': str(latest)},
            {'key': 'first_season', 'value': str(min(r['season'] for r in tables[schema.league_trends]))},
            {'key': 'loaded_at', 'value': datetime.now(timezone.utc).isoformat(timespec='seconds')},
            {'key': 'similarity_features', 'value': json.dumps(schema.STYLE_FEATURES)},
            {'key': 'data_fingerprint', 'value': data_fingerprint()},
            {'key': 'playoffs_through', 'value': str(max((r['season'] for r in tables[schema.player_playoffs]), default=0))},      # player playoff stats
            # seasons whose player playoff stats come only from series totals, which leave out some players
            {'key': 'playoffs_partial', 'value': json.dumps(sorted({r['season'] for r in tables[schema.player_playoffs]} - {r['season'] for r in tables[schema.player_playoffs] if r.get('source') != 'series'}))},
            {'key': 'series_through', 'value': str(max((r['season'] for r in tables[schema.playoff_series]), default=0))},         # series, champions, rings
            {'key': 'mvp_model', 'value': json.dumps({k: v for k, v in mvp.items() if k not in ('columns', 'rows')})
             if mvp else ''},
            {'key': 'archetype_model', 'value': json.dumps({k: v for k, v in roles.items() if k not in ('columns', 'rows', 'career_mix')})
             if roles else ''},
            {'key': 'champion_model', 'value': json.dumps({k: v for k, v in champ.items() if k not in ('columns', 'rows')})
             if champ else ''},
            {'key': 'contracts', 'value': json.dumps({k: con[k] for k in ('season', 'as_of', 'rules')}) if con else ''},
            {'key': 'projection_model', 'value': json.dumps({k: v for k, v in proj.items() if k != 'players'}) if proj else ''},
        ])
    if not quiet:
        target = engine.url.render_as_string(hide_password=True)
        print(f'Loaded {sum(counts.values()):,} rows into {target} in {time.time() - started:.1f}s')
        for name, n in counts.items():
            print(f'  {name:18s} {n:>7,}')
        for name, n in dropped.items():
            print(f'  (skipped {n} {name} rows for players without a career record)')
    return counts


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--database-url', help=f'defaults to $DATABASE_URL or {database_url()}')
    load(ap.parse_args().database_url)
