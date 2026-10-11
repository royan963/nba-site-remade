"""API tests: `pytest backend/tests` from the repo root.
Expected values are real stats, so they double as data-pipeline checks."""
import pytest


def get(client, path, status=200):
    r = client.get(path)
    assert r.status_code == status, r.text
    return r.json()


# ---- meta -------------------------------------------------------------------
def test_health(client):
    body = get(client, '/api/health')
    assert body['status'] == 'ok' and body['latest_season'] >= 2026


def test_meta(client):
    m = get(client, '/api/v1/meta')
    assert m['first_season'] == 1947
    assert m['similarity_features'][0] == 'pts_idx'


# ---- players ----------------------------------------------------------------
def test_search_ignores_accents(client):
    hits = get(client, '/api/v1/players?q=jokic')
    assert hits[0]['player'] == 'Nikola Jokić'
    assert 'name_search' not in hits[0]


def test_player_with_two_spellings_has_one_full_career(client):
    hits = get(client, '/api/v1/players?q=krejci')
    assert len(hits) == 1
    assert hits[0]['pts'] == 1870    # 770 + 1100 from both spellings


def test_player_index_is_compact(client):
    idx = get(client, '/api/v1/players/index')
    assert 'columns' in idx and len(idx['rows']) > 5000
    assert len(idx['rows']) == len({r[0] for r in idx['rows']})   # no duplicate ids


def test_player_detail_and_draft(client):
    p = get(client, '/api/v1/players/curryst01')
    assert p['player'] == 'Stephen Curry'
    assert p['draft']['season'] == 2009 and p['draft']['overall_pick'] == 7 and p['draft']['tm'] == 'GSW'
    assert 2016 in p['all_star_seasons']


def test_unknown_player_404(client):
    assert get(client, '/api/v1/players/nobody00', status=404)['detail'].startswith('No player')


def test_traded_player_gets_one_row_per_season(client):
    seasons = get(client, '/api/v1/players/agbajoc01/seasons')
    years = [s['season'] for s in seasons]
    assert len(years) == len(set(years))
    s2026 = next(s for s in seasons if s['season'] == 2026)
    assert s2026['team'] == '2TM' and sorted(s2026['teams']) == ['BRK', 'TOR']


def test_seasons_include_advanced_and_per100(client):
    s2016 = next(s for s in get(client, '/api/v1/players/curryst01/seasons') if s['season'] == 2016)
    assert s2016['per'] == pytest.approx(31.5, abs=0.2)
    assert s2016['per100']['pts'] > 40
    assert 0.4 < s2016['x3p_pct'] < 0.5          # stored as a fraction, 4 dp


def test_shooting_starts_in_1997(client):
    seasons = [r['season'] for r in get(client, '/api/v1/players/jordami01/shooting')]
    assert seasons and min(seasons) >= 1997


def test_honors(client):
    h = get(client, '/api/v1/players/curryst01/honors')
    mvps = sorted(a['season'] for a in h['awards'] if a['award'] == 'nba mvp' and a['winner'])
    assert mvps == [2015, 2016]


def test_similar_players(client):
    sim = get(client, '/api/v1/players/curryst01/similar')
    top = [m['player'] for m in sim['matches'][:5]]
    assert top[0] != 'James Harden'                                      # same box score, opposite way of scoring
    assert {'Kyrie Irving', 'Damian Lillard'} & set(top)
    assert sim['fingerprint']['pts_idx'] > 1.5
    assert sim['fingerprint']['x3p_accuracy'] > 0.3 and sim['fingerprint']['ft_rate_diff'] < 0   # makes threes, rarely at the line
    harden = get(client, '/api/v1/players/hardeja01/similar')['fingerprint']
    assert harden['ft_rate_diff'] > 0.15
    same = get(client, '/api/v1/players/curryst01/similar?era=same')
    assert all(abs((m['first_season'] + m['last_season']) / 2 - 2018) <= 10 for m in same['matches'])


def test_similar_needs_enough_minutes(client):
    sim = get(client, '/api/v1/players/wiltjky01/similar')   # 14 career games
    assert sim['fingerprint'] is None and sim['matches'] == []


def test_bundle_matches_seasons_endpoint(client):
    b = get(client, '/api/v1/players/agbajoc01/bundle')
    assert {r['team'] for r in b['seasons'] if r['season'] == 2026} == {'2TM', 'TOR', 'BRK'}
    assert b['similar']['neighbors'] and b['draft']


# ---- leaders ----------------------------------------------------------------
def test_leaders(client):
    top = get(client, '/api/v1/leaders?stat=ws&limit=3')
    assert top[0]['player'] == 'LeBron James' and top[0]['rank'] == 1
    early = get(client, '/api/v1/leaders?stat=trb&era=1947-1969&limit=1')
    assert early[0]['player'] == 'Wilt Chamberlain'


def test_leaders_rejects_bad_stat(client):
    get(client, '/api/v1/leaders?stat=dunks', status=400)
    get(client, '/api/v1/leaders?era=nineties', status=400)


# ---- teams ------------------------------------------------------------------
def test_team_list(client):
    teams = get(client, '/api/v1/teams')
    assert len(teams) == 44
    lakers = next(t for t in teams if t['franchise'] == 'Los Angeles Lakers')
    assert lakers['first_season'] == 1949      # Minneapolis years included


def test_roster(client):
    roster = get(client, '/api/v1/teams/Boston%20Celtics/roster/1986')
    assert roster[0]['player'] == 'Larry Bird'
    assert all(r['team'] == 'BOS' for r in roster)


def test_team_honors(client):
    h = get(client, '/api/v1/teams/Los%20Angeles%20Lakers/honors?season=2000')
    assert any(a['award'] == 'nba mvp' and a['player_id'] == 'onealsh01' for a in h['awards'])
    assert {a['player_id'] for a in h['all_stars']} >= {'onealsh01', 'bryanko01'}


def test_unknown_team_404(client):
    get(client, '/api/v1/teams/Seattle%20Pilots/seasons', status=404)


def test_geo_is_compact(client):
    geo = get(client, '/api/v1/teams/geo')
    assert 'franchise' in geo['columns'] and len(geo['rows']) > 1700


# ---- compare ----------------------------------------------------------------
def test_compare_experience_alignment(client):
    c = get(client, '/api/v1/compare/players?a=jamesle01&b=jordami01&position=5')
    pos = c['positions'][0]
    assert pos['a']['season'] == 2008 and pos['b']['season'] == 1989
    assert pos['a']['stats']['pts'] == pytest.approx(30.0, abs=0.1)


def test_compare_era_index(client):
    # Wilt's 1962 season (Year 3): ~210 scoring index vs the league
    c = get(client, '/api/v1/compare/players?a=chambwi01&b=onealsh01&basis=index&position=3')
    wilt = c['positions'][0]['a']
    assert wilt['season'] == 1962
    assert 200 < wilt['stats']['i_pts'] < 220
    assert [s['key'] for s in c['stats']][:2] == ['i_pts', 'i_trb']


def test_compare_detects_teammates(client):
    c = get(client, '/api/v1/compare/players?a=curryst01&b=thompkl01&align=calendar&position=2017')
    assert c['positions'][0]['same_season'] == {'teammates': True, 'shared_teams': ['GSW']}


def test_compare_validation(client):
    get(client, '/api/v1/compare/players?a=curryst01&b=curryst01', status=400)
    get(client, '/api/v1/compare/players?a=curryst01&b=nobody00', status=404)
    get(client, '/api/v1/compare/players?a=curryst01&b=jamesle01&basis=adjusted', status=422)


# ---- transport ----------------------------------------------------------------
def test_large_responses_are_gzipped(client):
    r = client.get('/api/v1/players/index', headers={'Accept-Encoding': 'gzip'})
    assert r.headers.get('content-encoding') == 'gzip'
    assert 'max-age' in r.headers.get('cache-control', '')


# ---- additions used by the React frontend ------------------------------------
def test_meta_counts_players(client):
    assert get(client, '/api/v1/meta')['players'] > 5000


def test_team_honors_include_player_names(client):
    h = get(client, '/api/v1/teams/Boston%20Celtics/honors?season=1986')
    mvp = next(a for a in h['awards'] if a['award'] == 'nba mvp')
    assert mvp['player'] == 'Larry Bird'
    assert all(s['player'] for s in h['all_stars'])


def test_compare_includes_season_context(client):
    side = get(client, '/api/v1/compare/players?a=jamesle01&b=jordami01&position=5')['positions'][0]['b']
    assert side['season'] == 1989 and side['experience'] == 5
    assert side['raw']['pts'] == pytest.approx(32.5, abs=0.1)
    assert side['league']['pace'] > 90
    assert {'All-NBA 1st', 'All-Star'} <= set(side['honors'])


def test_frontend_deep_links_fall_back_to_the_app(client):
    from backend.app.main import WEB_DIR
    if not (WEB_DIR / 'index.html').exists():
        pytest.skip('frontend not built')
    r = client.get('/players/curryst01')
    assert r.status_code == 200 and '<div id="root">' in r.text
    assert client.get('/api/v1/not-a-route').status_code == 404       # API 404s stay JSON


# ---- MVP model ---------------------------------------------------------------------
def test_mvp_model_card(client):
    m = get(client, '/api/v1/models/mvp')
    assert m['metrics']['seasons'] >= 70 and m['metrics']['top1'] > m['metrics']['baseline_top1']
    newest = m['preseason']['season'] if m['preseason'] else m['latest_season']
    assert m['importances'][0]['label'] and m['seasons'][0] == newest
    assert all(x['predicted_name'] and x['actual_name'] for x in m['misses'])


def test_mvp_backtest_season(client):
    r = get(client, '/api/v1/models/mvp/1962')
    assert r['kind'] == 'backtest'
    top = r['candidates'][0]
    assert top['player'] == 'Bill Russell' and top['winner'] and top['actual_rank'] == 1
    probs = [c['win_prob'] for c in r['candidates']]          # top 10 listed; the rest of the field holds the remainder
    assert sum(probs) <= 1.0001 and probs[0] == max(probs)


def test_mvp_current_race(client):
    m = get(client, '/api/v1/models/mvp')
    r = get(client, f"/api/v1/models/mvp/{m['latest_season']}")
    assert r['kind'] == ('backtest' if m['latest_has_votes'] else 'prediction')
    assert r['candidates'][0]['pts'] is not None
    assert len({c['player_id'] for c in r['candidates']}) == len(r['candidates'])   # traded players listed once


def test_mvp_preseason_race(client):
    # once the latest season's vote is in, the next season gets a preseason race
    m = get(client, '/api/v1/models/mvp')
    assert m['latest_has_votes'] and m['preseason']['season'] == m['latest_season'] + 1
    assert m['preseason']['metrics']['top1'] > m['preseason']['metrics']['baseline_top1']
    r = get(client, f"/api/v1/models/mvp/{m['preseason']['season']}")
    assert r['kind'] == 'preseason' and r['stats_season'] == m['latest_season']
    assert r['candidates'][0]['pts'] is not None and r['candidates'][0]['actual_share'] is None
    probs = [c['win_prob'] for c in r['candidates']]
    assert sum(probs) <= 1.0001 and probs[0] == max(probs) and probs[0] < 0.75   # a year out, no lock


def test_2026_awards(client):
    # 2025-26 voting comes from the Deo Cheng tables (the main dataset stops at 2024-25)
    h = get(client, '/api/v1/players/gilgesh01/honors')
    assert sorted(a['season'] for a in h['awards'] if a['award'] == 'nba mvp' and a['winner']) == [2025, 2026]
    assert any(t['season'] == 2026 and t['team_type'] == 'All-NBA' and t['team_number'] == '1st' for t in h['all_league_teams'])
    assert any(a['season'] == 2026 and a['award'] == 'nba roy' and a['winner'] for a in get(client, '/api/v1/players/flaggco01/honors')['awards'])


# ---- champion model -------------------------------------------------------------------
def test_champion_model_card(client):
    m = get(client, '/api/v1/models/champion')
    assert m['metrics']['seasons'] >= 70 and m['metrics']['top1'] > m['metrics']['baseline_top1']
    assert m['weights'][0]['label'] and m['misses'] and all(x['predicted'] and x['actual'] for x in m['misses'])


def test_champion_backtest_season(client):
    r = get(client, '/api/v1/models/champion/1996')
    assert r['kind'] == 'backtest'
    champ = next(t for t in r['teams'] if t['champion'])
    assert champ['team'] == 'CHI' and champ['w'] == 72 and champ['rank'] == 1 and champ['star'] == 'Michael Jordan'
    probs = [t['win_prob'] for t in r['teams']]
    assert abs(sum(probs) - 1) < 0.01 and probs == sorted(probs, reverse=True)       # every team listed, odds sum to 1
    assert sum(1 for t in r['teams'] if t['champion']) == 1 and all(t['result'] for t in r['teams'])


def test_champion_preseason(client):
    m = get(client, '/api/v1/models/champion')
    assert m['latest_has_champion'] and m['preseason']['season'] == m['latest_season'] + 1 and m['seasons'][0] == m['preseason']['season']
    r = get(client, f"/api/v1/models/champion/{m['preseason']['season']}")
    assert r['kind'] == 'preseason' and r['stats_season'] == m['latest_season']
    assert all(t['champion'] is None and t['result'] is None for t in r['teams'])
    assert abs(sum(t['win_prob'] for t in r['teams']) - 1) < 0.01 and r['teams'][0]['win_prob'] < 0.6
    get(client, '/api/v1/models/champion/1900', status=404)


def test_mvp_unknown_season(client):
    get(client, '/api/v1/models/mvp/1900', status=404)


# ---- player archetypes ---------------------------------------------------------------
def test_archetype_model(client):
    m = get(client, '/api/v1/models/archetypes')
    keys = {a['key'] for a in m['archetypes']}
    assert len(keys) == len(m['archetypes']) == m['method']['k'] + 1          # k clusters + the stretch-big rule
    assert {'star-creator', 'rim-protector', 'spot-up-shooter', 'stretch-big'} <= keys
    seasons, shares = m['trend']['seasons'], m['trend']['shares']
    i = seasons.index(2020)
    assert abs(sum(v[i] for v in shares.values()) - 1) < 0.01               # shares of minutes sum to 100%
    shooters = next(a for a in m['archetypes'] if a['key'] == 'spot-up-shooter')
    assert shooters['share_by_decade']['2020'] > 4 * shooters['share_by_decade']['1980']   # the three-point revolution


def test_archetype_players(client):
    r = get(client, '/api/v1/models/archetypes/stretch-big?decade=2000&limit=10')
    assert r['players'] and all(2000 <= p['season'] < 2010 for p in r['players'])
    assert len({(p['player_id'], p['season']) for p in r['players']}) == len(r['players'])
    get(client, '/api/v1/models/archetypes/point-center', status=404)


def test_player_archetypes(client):
    r = get(client, '/api/v1/players/onealsh01/archetypes')
    assert r['main']['key'] == 'scoring-big'
    lopez = {s['season']: s['key'] for s in get(client, '/api/v1/players/lopezbr01/archetypes')['seasons']}
    assert lopez[2010] != 'stretch-big' and lopez[2024] == 'stretch-big'     # the post scorer who became a shooter
    assert get(client, '/api/v1/players/wiltjky01/archetypes')['main'] is None   # too few minutes to classify


# ---- career projections ---------------------------------------------------------------
def test_projection_model_beats_baselines(client):
    m = get(client, '/api/v1/models/projections')
    for h in m['metrics']['horizons']:
        assert h['pts']['model'] < h['pts']['last_season'] and h['pts']['model'] < h['pts']['aging_curve']
        assert 0.5 < h['pts']['band_coverage'] < 0.75                    # the "60% range" is calibrated
        assert h['active_brier'] < h['active_brier_base']
    assert m['risers'][0]['change'] > 0 > m['decliners'][0]['change']


def test_player_projection(client):
    r = get(client, '/api/v1/players/wembavi01/projection')
    m = get(client, '/api/v1/models/projections')
    assert r['projected'] and [h['season'] for h in r['horizons']] == [m['latest_season'] + i for i in (1, 2, 3)]
    h1 = r['horizons'][0]
    assert h1['pts_lo'] <= h1['pts'] <= h1['pts_hi'] and 0 <= h1['p_active'] <= 1
    assert r['comps'] and all(c['comp_id'] != 'wembavi01' for c in r['comps'])        # never compared with himself
    assert all(c['comp_season'] <= m['latest_season'] - 3 for c in r['comps'])          # comparables' futures are known


def test_retired_player_has_no_projection(client):
    assert get(client, '/api/v1/players/jordami01/projection')['projected'] is False


# ---- style mixes and similar players v2 ---------------------------------------------
def test_style_mix(client):
    r = get(client, '/api/v1/players/lopezbr01/archetypes')
    keys = [m['key'] for m in r['mix']]
    assert keys[:2] == ['stretch-big', 'scoring-big']                    # a player can blend roles
    assert 95 <= sum(m['share'] for m in r['mix']) <= 101
    by_season = {x['season']: x for x in r['seasons']}
    assert by_season[2010]['key'] == 'scoring-big' and by_season[2024]['key'] == 'stretch-big'
    assert all(len(x['mix']) >= 1 for x in r['seasons'])


def test_similar_players_respect_style_changes(client):
    r = get(client, '/api/v1/players/lopezbr01/similar')
    top = [m['player_id'] for m in r['matches'][:5]]
    assert {'turnemy01', 'holmgch01', 'porzikr01'} & set(top)             # other bigs who became shooters
    assert all(m['styles'] for m in r['matches'])
    assert r['styles'][0]['key'] == 'stretch-big'


def test_old_era_matches_are_not_inflated(client):
    # Bill Russell's stats lack blocks/steals/usage; missing stats now count as a partial mismatch
    assert get(client, '/api/v1/players/russebi01/similar')['matches'][0]['score'] < 90
