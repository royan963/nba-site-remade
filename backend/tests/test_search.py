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
    assert r['results'] == [] and r['player']['player'] == 'Michael Jordan' and len(r['player']['titles']) == 6
    r = search(client, q='zzqx')
    assert r['results'] == [] and r['name_matches'] == [] and r['examples']


def test_search_drop(client):
    r = search(client, q='best rebounding guards of the 90s')
    guards = next(f['index'] for f in r['filters'] if f['kind'] == 'position')
    r2 = search(client, q='best rebounding guards of the 90s', drop=[guards])
    assert r2['results'][0]['player'] == 'Dennis Rodman'
    assert all(f['kind'] != 'position' for f in r2['filters'])


# ---- questions about players, playoffs, single games and more ---------------------------------------
def test_named_player_questions(client):
    assert search(client, q='how many rings does lebron have')['answer'] == 'LeBron James: 4 championships.'
    assert search(client, q='how tall is wembanyama')['answer'] == 'Victor Wembanyama: 7\'4".'
    r = search(client, q='lebron mvps')
    assert sorted(x['season'] for x in r['results']) == [2009, 2010, 2012, 2013] and '2009, 2010, 2012, 2013' in r['answer']
    r = search(client, q='shai gilgeous-alexander stats')          # just a name: a player card, nothing left unread
    assert r['player']['player'] == 'Shai Gilgeous-Alexander' and r['ignored'] == [] and r['results'] == []
    r = search(client, q='curry vs harden')
    assert r['compare']['url'] == '/compare/players/curryst01/hardeja01'
    assert search(client, q='compare lebron and jordan')['compare']['url'] == '/compare/players/jamesle01/jordami01'
    # a common word that's also a surname isn't a player
    assert search(client, q='best young players')['player'] is None


def test_new_question_types(client):
    r = search(client, q='who has the most championships')
    assert r['results'][0]['player'] == 'Bill Russell' and r['answer'].endswith('11 championships.')
    r = search(client, q='players who scored 60 points in a game')
    assert r['scope'] == 'games' and r['results'][0]['player'] == 'Wilt Chamberlain' and r['results'][0]['value'] == 100
    r = search(client, q='top 10 scorers in playoff history')
    assert r['playoffs'] and r['scope'] == 'careers' and r['results'][0]['player'] == 'LeBron James' and len(r['results']) == 10
    r = search(client, q='youngest mvp')
    assert r['results'][0]['player'] == 'Derrick Rose' and r['results'][0]['value'] == 22
    assert search(client, q='finals mvps since 2020')['results'][0]['player_id'] in {'jokicni01', 'antetgi01', 'curryst01', 'brownja02', 'gilgesh01', 'brunsja01'}
    assert search(client, q='who won rookie of the year in 2026')['results'][0]['player'] == 'Cooper Flagg'
    assert search(client, q='highest scoring season ever')['scope'] == 'seasons'          # 'season' beats 'ever'
    assert search(client, q='best point guards ever')['results']                           # careers by their seasons' positions
    r = search(client, q='who will win mvp')
    assert r['results'] == [] and r['links'][0]['url'] == '/models/mvp'
    r = search(client, q='steph curry 3 point percentage')
    assert r['stat'] == 'x3p_pct' and all(x['player_id'] == 'curryst01' for x in r['results']) and r['ignored'] == []


# ---- Ask-bar fixes: team championships and per-game career averages --------------------------------------------------
# Reported 2026-10-13: "how many rings do the lakers have" answered Bill Russell, and "how many rebounds did james
# harden average for his career" answered his career total. Expected values come from other endpoints, not from the
# search code under test.


@pytest.mark.parametrize('text', ['how many rings do the lakers have', 'how many championships do the lakers have', 'lakers titles',
                                  'how many titles have the celtics won'])
def test_team_titles_question_is_a_team_question(text):
    q = p(text)
    assert q.stat == 'titles' and q.teams and q.team_titles


@pytest.mark.parametrize('text', ['who has the most championships with the lakers', 'which players won the most titles with the celtics',
                                  'who has the most championships'])
def test_titles_ranking_questions_are_not_team_questions(text):
    assert not p(text).team_titles


@pytest.mark.parametrize('text, per_game', [
    ('how many rebounds did james harden average for his career', True), ('james harden career rebounds per game', True),
    ('lebron career ppg', True), ('highest career scoring average', True),
    ('how many rebounds did james harden have for his career', False), ('most career rebounds', False), ('top scorers', False)])
def test_per_game_flag(text, per_game):
    assert p(text).per_game is per_game


def ask(client, q):
    r = client.get('/api/v1/search', params={'q': q})
    assert r.status_code == 200
    return r.json()


def champion_counts(client):
    return client.get('/api/v1/playoffs/champions').json()['titles_by_franchise']


@pytest.mark.parametrize('q, franchise', [('how many rings do the lakers have', 'Los Angeles Lakers'),
                                          ('how many championships do the celtics have', 'Boston Celtics'),
                                          ('lakers titles', 'Los Angeles Lakers')])
def test_team_titles_answer_matches_the_champions_list(client, q, franchise):
    d = ask(client, q)
    expected = champion_counts(client)[franchise]
    assert d['understood'] is True
    assert d['answer'] and franchise in d['answer'] and f'{expected} championship' in d['answer']
    assert 'Bill Russell' not in d['answer']
    assert [r['franchise'] for r in d['team_results']] == [franchise]
    assert d['team_results'][0]['titles'] == expected == len(d['team_results'][0]['seasons'])
    assert d['results'] == []                                   # a team answer, not a ranking of players
    assert not any('ignored for careers' in n for n in d['notes'])


def test_most_titles_with_a_team_ranks_players_by_titles_with_that_team(client):
    d = ask(client, 'who has the most championships with the lakers')
    assert d['results'] and d['team_results'] == []
    assert d['results'][0]['value'] <= champion_counts(client)['Los Angeles Lakers']
    assert d['results'][0]['player'] != 'Bill Russell'          # all of Russell's titles were with Boston
    assert not any('ignored for careers' in n for n in d['notes'])


@pytest.mark.parametrize('q, pid, per_game_key, total_key', [
    ('how many rebounds did james harden average for his career', 'hardeja01', 'rpg', 'trb'),
    ('lebron career points per game', 'jamesle01', 'ppg', 'pts')])
def test_career_average_answers_with_the_per_game_number(client, q, pid, per_game_key, total_key):
    d = ask(client, q)
    career = client.get(f'/api/v1/players/{pid}').json()
    expected = career[total_key] / career['g']
    assert d['stat_is_avg'] is True
    assert f'{expected:.1f}' in d['answer'] and 'per game' in d['answer']
    assert f"{career[total_key]:,}" not in d['answer']          # not the career total
    assert d['results'][0]['value'] == pytest.approx(expected, abs=0.06)


def test_career_total_without_average_wording_is_still_a_total(client):
    d = ask(client, 'how many rebounds does james harden have in his career')
    career = client.get('/api/v1/players/hardeja01').json()
    assert d['stat_is_avg'] is False and f"{career['trb']:,}" in d['answer']


def test_highest_career_scoring_average_ranks_by_per_game_with_a_games_minimum(client):
    d = ask(client, 'highest career scoring average')
    values = [r['value'] for r in d['results']]
    assert d['scope'] == 'careers' and d['stat_is_avg'] is True
    assert values == sorted(values, reverse=True) and 25 < values[0] < 40     # points per game, not 40,000+ career totals
    assert all(r['g'] >= 400 for r in d['results'])


def test_playoff_career_average(client):
    d = ask(client, 'how many points did lebron average in the playoffs for his career')
    assert d['playoffs'] is True and d['stat_is_avg'] is True
    assert 20 < d['results'][0]['value'] < 40 and 'per game' in d['answer']


def test_single_season_average_is_unchanged(client):
    d = ask(client, 'how many points did curry average in 2016')
    assert d['stat_is_avg'] is False and '30.1' in d['answer'] and 'per game' in d['answer']


@pytest.mark.parametrize('q, playoffs', [('how many points does lebron average', False),
                                         ('how many points did lebron average in the playoffs', True)])
def test_named_player_average_with_no_season_means_career(client, q, playoffs):
    d = ask(client, q)
    assert d['scope'] == 'careers' and d['stat_is_avg'] is True and d['playoffs'] is playoffs
    assert 'per game' in d['answer'] and 'seasons match' not in d['answer']
    assert len(d['results']) == 1 and 20 < d['results'][0]['value'] < 40


@pytest.mark.parametrize('q', ['how many points did curry average in 2016', 'how many points did lebron average each season',
                               'what season did lebron average the most points'])
def test_average_questions_that_name_a_season_stay_per_season(client, q):
    assert ask(client, q)['scope'] == 'seasons'


# ---- the "I can't answer that yet" fallback ---------------------------------------------------------------------------
# Before: questions about team records, payroll, opponents, playoff rounds or things we have no data for were answered
# with an unrelated player ranking ("how many wins did the lakers have in 2020" returned a Win Shares leader), and
# filters the engine had to drop were only mentioned in a small grey note. Now they are explained, not answered wrongly.

BLOCKED = [
    ('lakers attendance', 'no_data', None),
    ('who is the best coach', 'no_data', None),
    ('most points against the lakers', 'opponent', None),
    ('lebron points against the celtics', 'opponent', None),
    ('lebron points in the finals', 'playoff_round', None),
    ('lebron shoe size', 'unknown_stat', None),
]


@pytest.mark.parametrize('q, kind, link', BLOCKED)
def test_unsupported_question_is_explained_not_answered_wrongly(client, q, kind, link):
    d = ask(client, q)
    found = [u for u in d['unsupported'] if u['kind'] == kind]
    assert found, d['unsupported']
    assert found[0]['blocking'] is True and found[0]['message']
    assert d['answer'] is None and d['results'] == [] and d['team_results'] == []
    if link:
        assert found[0]['link']['url'] == link


def test_blocked_question_about_a_player_still_shows_his_card(client):
    d = ask(client, 'lebron points against the celtics')
    assert d['player'] and d['player']['player_id'] == 'jamesle01'


@pytest.mark.parametrize('q', ['most career win shares with the celtics', 'rookies with the most career points',
                               'best career scorers under 25'])
def test_dropped_filter_is_called_out_and_not_stated_as_the_answer(client, q):
    d = ask(client, q)
    dropped = [u for u in d['unsupported'] if u['kind'] == 'ignored_filter']
    assert dropped and all(u['blocking'] is False for u in dropped)
    assert d['answer'] is None and d['results']                  # the ranking is still shown, but not asserted as the answer


STARTERS = ['how many rings does lebron have', 'curry vs harden', 'best rebounding guards of the 90s', 'most points in a playoff game',
            'players who averaged 25 and 10 since 2010', 'who has the most championships', 'youngest MVPs', 'tallest players',
            'highest paid players this season', '50/40/90 seasons', 'Celtics leading scorers in the 80s', 'all-time leading scorers']
SUPPORTED_SINCE = ['how many rings do the lakers have', 'lakers titles', 'how many rebounds did james harden average for his career',
                   'highest career scoring average', 'who has the most championships with the lakers',
                   'how many points did lebron average in the playoffs', 'michael jordan', 'how tall is lebron', 'how old is curry',
                   'who is taller lebron or curry', 'weather in boston', 'who won mvp in 2016', 'lakers payroll', 'lakers record in 2020',
                   'celtics best season', 'best teams of the 90s', 'lakers vs celtics', 'most career points with the celtics']


@pytest.mark.parametrize('q', sorted(set(STARTERS + SUPPORTED_SINCE)))
def test_supported_questions_raise_no_warning(client, q):
    assert ask(client, q)['unsupported'] == []


def test_every_example_question_raises_no_warning(client):
    from backend.app.routers.search import EXAMPLES
    for q in EXAMPLES:
        assert ask(client, q)['unsupported'] == [], q


def test_fallback_hook_can_rescue_an_unsupported_question(client, monkeypatch):
    """The seam for a future LLM parser: asked first for blocked questions, never for supported ones."""
    from backend.app.routers import search as router
    from backend.app.search import parse
    calls = []

    def fake(text, teams, archetypes, latest):
        calls.append(text)
        return parse('top scorers', teams, archetypes, latest)

    monkeypatch.setattr(router, 'fallback_query', fake)
    d = ask(client, 'lakers attendance')
    assert calls == ['lakers attendance'] and d['unsupported'] == [] and d['results']
    calls.clear()
    ask(client, 'top scorers')
    ask(client, 'how many rings do the lakers have')
    assert calls == []


# ---- real answers for team questions -----------------------------------------------------------------------------------
# These were explained as "can't answer yet" (or, worse, answered with a player ranking). The data exists, so they are
# answered. Expected values come from other endpoints (/teams/.../seasons, /teams/geo, /head-to-head, /teams/.../salaries,
# /teams/.../roster), not from the search code under test.


def label(season):
    return f'{season - 1}-{str(season)[2:]}'


def season_rows(client, franchise):
    return client.get(f'/api/v1/teams/{franchise}/seasons').json()


def geo_rows(client):
    g = client.get('/api/v1/teams/geo').json()
    return [dict(zip(g['columns'], r)) for r in g['rows']]


def win_pct(r):
    return r['w'] / (r['w'] + r['l'])


@pytest.mark.parametrize('text, intent', [
    ('lakers record in 2020', 'record'), ('lakers record', 'record'), ('how many wins did the lakers have in 2020', 'record'),
    ('how many games did the celtics win in 1986', 'record'), ('lakers payroll', 'payroll'),
    ('celtics best season', 'best'), ('best teams of the 90s', 'best'), ('worst team of the 2010s', 'best'), ('best record in 1996', 'best'),
    ('top scorers', None), ('lebron best scoring season', None), ('how many rings do the lakers have', None),
    ('celtics leading scorers in the 80s', None), ('best players of all time', None), ('best seasons ever', None)])
def test_team_intent(text, intent):
    assert p(text).team_intent == intent


@pytest.mark.parametrize('q, franchise, season', [('lakers record in 2020', 'Los Angeles Lakers', 2020),
                                                  ('how many wins did the lakers have in 2020', 'Los Angeles Lakers', 2020),
                                                  ('how many games did the bulls win in 1996', 'Chicago Bulls', 1996)])
def test_team_record_in_a_season_matches_the_team_seasons_endpoint(client, q, franchise, season):
    d = ask(client, q)
    row = next(r for r in season_rows(client, franchise) if r['season'] == season)
    assert f"{row['w']}-{row['l']}" in d['answer'] and franchise in d['answer'] and label(season) in d['answer']
    assert d['unsupported'] == [] and d['results'] == [] and d['understood'] is True
    assert [r['record'] for r in d['team_table']['rows']] == [f"{row['w']}-{row['l']}"]
    assert [f['label'] for f in d['filters'] if f['kind'] == 'stat'] == ['team record']      # not "ranked by Win Shares"


def test_team_record_all_time(client):
    d = ask(client, 'lakers record')
    rows = season_rows(client, 'Los Angeles Lakers')
    w, l = sum(r['w'] for r in rows), sum(r['l'] for r in rows)
    assert f'{w:,}-{l:,}' in d['answer'] and f'{len(rows)} seasons' in d['answer']


def test_team_record_over_a_range_of_seasons(client):
    d = ask(client, 'celtics record in the 80s')
    rows = [r for r in season_rows(client, 'Boston Celtics') if 1980 <= r['season'] <= 1989]
    w, l = sum(r['w'] for r in rows), sum(r['l'] for r in rows)
    assert f'{w}-{l}' in d['answer'] and len(d['team_table']['rows']) == len(rows) == 10


def test_best_season_for_a_team(client):
    d = ask(client, 'celtics best season')
    best = max(season_rows(client, 'Boston Celtics'), key=lambda r: (win_pct(r), r['srs'] if r['srs'] is not None else -99))
    assert f"{best['w']}-{best['l']}" in d['answer'] and label(best['season']) in d['answer'] and 'Boston Celtics' in d['answer']
    assert d['team_table']['rows'][0]['season'] == label(best['season'])
    assert d['results'] == [] and d['unsupported'] == []


def test_best_teams_of_a_decade_ranks_every_franchise(client):
    d = ask(client, 'best teams of the 90s')
    best = max((r for r in geo_rows(client) if 1990 <= r['season'] <= 1999), key=lambda r: (win_pct(r), r['srs'] if r['srs'] is not None else -99))
    rows = d['team_table']['rows']
    assert rows[0]['team'] == best['team_name'] and rows[0]['season'] == label(best['season']) and len(rows) == 10
    pcts = [float(r['win_pct']) for r in rows]
    assert pcts == sorted(pcts, reverse=True)


def test_worst_team_ranks_from_the_bottom(client):
    d = ask(client, 'worst team of the 2010s')
    worst = min((r for r in geo_rows(client) if 2010 <= r['season'] <= 2019), key=lambda r: (win_pct(r), r['srs'] if r['srs'] is not None else 99))
    assert d['team_table']['rows'][0]['team'] == worst['team_name'] and d['team_table']['rows'][0]['season'] == label(worst['season'])


def test_team_career_leader_is_exact_for_players_who_only_played_for_that_team(client):
    d = ask(client, 'most career points with the celtics')
    top = d['results'][0]
    career = client.get('/api/v1/players/havlijo01').json()
    assert top['player_id'] == 'havlijo01' and top['value'] == career['pts'] and top['approx'] is False
    assert d['unsupported'] == [] and not any('ignored' in n for n in d['notes'])


def test_who_scored_the_most_for_a_team_answers_with_that_player(client):
    d = ask(client, 'who scored the most career points for the lakers')
    career = client.get('/api/v1/players/bryanko01').json()
    assert d['results'][0]['player_id'] == 'bryanko01' and d['results'][0]['value'] == career['pts']
    assert 'Kobe Bryant' in d['answer'] and f"{career['pts']:,}" in d['answer']


def test_team_career_total_for_a_traded_player_is_rebuilt_from_his_seasons_with_that_team(client):
    d = ask(client, 'most career points with the rockets')
    row = next(r for r in d['results'] if r['player_id'] == 'olajuha01')
    expected = sum(r['pts'] * r['g'] for season in range(1985, 2003)
                   for r in client.get(f'/api/v1/teams/Houston Rockets/roster/{season}').json() if r['player_id'] == 'olajuha01')
    assert row['approx'] is True and row['value'] == round(expected)
    assert any('per-game' in n for n in d['notes'])                  # the page says these totals are approximate


def test_team_career_average_ranks_by_points_per_game_with_that_team(client):
    d = ask(client, 'highest career scoring average with the celtics')
    assert d['stat_is_avg'] is True and d['results'][0]['player_id'] == 'birdla01' and 22 < d['results'][0]['value'] < 27
    assert all(r['g'] >= 250 for r in d['results'])


def test_team_vs_team_gives_the_head_to_head_record(client):
    h = client.get('/api/v1/head-to-head/teams', params={'a': 'Los Angeles Lakers', 'b': 'Boston Celtics'}).json()
    d = ask(client, 'lakers vs celtics')
    assert d['answer'].startswith('Los Angeles Lakers vs Boston Celtics') and f"{h['regular']['a_wins']}-{h['regular']['b_wins']}" in d['answer']
    assert d['unsupported'] == [] and d['results'] == [] and d['team_table']['rows']
    assert {'label': 'Compare the two teams', 'url': '/compare/teams/los-angeles-lakers/boston-celtics'} in d['links']
    d2 = ask(client, 'celtics vs lakers')                              # the team named first comes first
    assert d2['answer'].startswith('Boston Celtics vs Los Angeles Lakers') and f"{h['regular']['b_wins']}-{h['regular']['a_wins']}" in d2['answer']


def test_team_payroll_for_a_past_season(client):
    d = ask(client, 'lakers payroll in 2020')
    row = next(x for x in client.get('/api/v1/teams/Los Angeles Lakers/salaries').json()['payroll'] if x['season'] == 2020)
    assert f"${row['total'] / 1e6:.1f}M" in d['answer'] and label(2020) in d['answer'] and d['unsupported'] == []


def test_team_payroll_without_a_season_is_the_current_one(client):
    d = ask(client, 'lakers payroll')
    sal = client.get('/api/v1/teams/Los Angeles Lakers/salaries').json()
    cur = next(x for x in sal['payroll'] if x['season'] == sal['season'])
    assert f"${cur['total'] / 1e6:.1f}M" in d['answer'] and label(sal['season']) in d['answer']
    assert len(d['team_table']['rows']) >= 5


def test_team_payroll_before_the_data_starts_is_explained(client):
    d = ask(client, 'lakers payroll in 1990')
    assert d['answer'] is None and d['unsupported'][0]['blocking'] is True and '1996-97' in d['unsupported'][0]['message']
