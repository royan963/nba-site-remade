"""Natural-language search: the parser on its own (fast, no database), then the endpoint."""
import pytest

from backend.app.search import drop_filters, parse

TEAMS = {'celtics': ['Boston Celtics'], 'sixers': ['Philadelphia 76ers'], 'lakers': ['Los Angeles Lakers', 'Minneapolis Lakers']}
ARCH = {'stretch bigs': 'stretch-big', 'rim protectors': 'rim-protector', 'spot-up shooters': 'spot-up-shooter'}


def p(text):
    return parse(text, TEAMS, ARCH, 2026)


@pytest.mark.parametrize('text, stat, order', [
    ('best rebounding guards', 'trb', 'desc'), ('top scorers', 'pts', 'desc'), ('most assists', 'ast', 'desc'),
    ('best three point shooters', 'x3p_pct', 'desc'), ('most threes', 'x3pm', 'desc'), ('worst free throw shooters', 'ft_pct', 'asc'),
    ('highest true shooting', 'ts_pct', 'desc'), ('best shot blockers', 'blk', 'desc'), ('highest PER', 'per', 'desc'),
    ('most win shares', 'ws', 'desc'), ('best field goal percentage', 'fg_pct', 'desc'), ('best players', 'ws', 'desc'),
])
def test_ranking_stat(text, stat, order):
    q = p(text)
    assert (q.stat, q.order) == (stat, order)


@pytest.mark.parametrize('text, lo, hi', [
    ('of the 90s', 1990, 1999), ('in the 1980s', 1980, 1989), ("the '60s", 1960, 1969), ('in the nineties', 1990, 1999),
    ('2010s', 2010, 2019), ('since 2010', 2010, None), ('after 2010', 2011, None), ('before 1980', None, 1979),
    ('in 2016', 2016, 2016), ('2015-16', 2016, 2016), ('from 2000 to 2010', 2000, 2010), ('last 5 seasons', 2022, 2026),
    ('this season', 2026, 2026), ('the 60s and 70s', 1960, 1979),
])
def test_seasons(text, lo, hi):
    q = p('top scorers ' + text)
    assert (q.season_from, q.season_to) == (lo, hi)


def test_positions_and_styles():
    assert p('best rebounding guards').positions == {'PG', 'SG', 'G'}
    assert p('point guards').positions == {'PG'}
    assert p('bigs').positions == {'PF', 'C'}
    q = p('best stretch bigs')                      # a playing style, not just a position
    assert q.archetype == 'stretch-big' and q.positions is None


def test_statlines():
    q = p('players who averaged 25 and 10')
    assert ('pts', '>=', 25) in q.minimums and ('trb', '>=', 10) in q.minimums
    assert {m[0] for m in p('50/40/90 seasons').minimums} == {'fg_pct', 'x3p_pct', 'ft_pct'}
    assert len(p('triple-double seasons').minimums) == 3
    assert p('players averaging 30 points').minimums == [('pts', '>=', 30.0)]
    assert p('under 20 minutes').minimums == [('mp', '<', 20.0)]


def test_people_filters():
    assert p('scorers under 25').age_max == 24
    assert p('best seasons by players 35 or older').age_min == 35
    assert p('rookies with the most points').rookie
    assert p('Celtics leading scorers').teams == ['Boston Celtics']
    assert p('sixers').teams == ['Philadelphia 76ers']
    assert p('MVPs since 2000').honors == {'mvp'}
    assert p('hall of famers').honors == {'hof'}


def test_scope_and_limit():
    assert p('all-time leading scorers').scope == 'careers'
    assert p('most points in a single season ever').scope == 'seasons'    # "single season" wins
    assert p('top 10 scorers').limit == 10


def test_names_and_nonsense_are_not_stats_questions():
    assert not p('Michael Jordan').understood
    assert not p('zzqx').understood
    assert p('Michael Jordan').ignored == ['michael', 'jordan']


def test_drop_filters_keeps_positions_stable():
    q = p('best rebounding guards of the 90s')
    kinds = [f.kind for f in q.filters]
    q = drop_filters(q, [kinds.index('position')])
    assert q.positions is None and q.season_from == 1990
    assert all(f.index is not None for f in q.filters)


# ---- endpoint (real data) -------------------------------------------------------------
def search(client, **params):
    r = client.get('/api/v1/search', params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_search_rebounding_guards(client):
    r = search(client, q='best rebounding guards of the 90s')
    assert r['results'] and all(1990 <= x['season'] <= 1999 for x in r['results'])
    assert all(x['pos'].split('-')[0] in ('PG', 'SG', 'G') for x in r['results'])
    vals = [x['value'] for x in r['results']]
    assert vals == sorted(vals, reverse=True)


def test_search_statline_and_minimums(client):
    r = search(client, q='50/40/90 seasons')
    names = {x['player'] for x in r['results']}
    assert {'Stephen Curry', 'Kevin Durant', 'Dirk Nowitzki'} <= names
    r = search(client, q='best three point shooters in 2016')
    assert all(x['season'] == 2016 for x in r['results'])           # and nobody on 3-for-5: 2+ attempts a game required


def test_search_team_uses_team_stints(client):
    r = search(client, q='Celtics leading scorers in the 80s')
    assert r['results'][0]['player'] == 'Larry Bird' and all(x['team'] == 'BOS' for x in r['results'])


def test_search_careers(client):
    r = search(client, q='all-time leading scorers')
    assert r['scope'] == 'careers' and r['results'][0]['player'] == 'LeBron James' and r['stat_label'] == 'Career points'
    assert search(client, q='best scorers', scope='careers')['scope'] == 'careers'


def test_search_names_and_examples(client):
    r = search(client, q='michael jordan')
    assert r['results'] == [] and r['name_matches'][0]['player'] == 'Michael Jordan'
    r = search(client, q='zzqx')
    assert r['results'] == [] and r['name_matches'] == [] and r['examples']


def test_search_drop(client):
    r = search(client, q='best rebounding guards of the 90s')
    guards = next(f['index'] for f in r['filters'] if f['kind'] == 'position')
    r2 = search(client, q='best rebounding guards of the 90s', drop=[guards])
    assert r2['results'][0]['player'] == 'Dennis Rodman'
    assert all(f['kind'] != 'position' for f in r2['filters'])
