"""Playoffs and championships. Expected values are real, well-known records."""
import pytest


def get(client, path, status=200):
    r = client.get(path)
    assert r.status_code == status, r.text
    return r.json()


def test_title_counts_match_the_record_books(client):
    known = {'russebi01': 11, 'jonessa01': 10, 'heinsto01': 8, 'joneskc01': 8, 'horryro01': 7, 'jordami01': 6, 'abdulka01': 6,
             'johnsma02': 5, 'bryanko01': 5, 'duncati01': 5, 'curryst01': 4, 'jamesle01': 4, 'onealsh01': 4}
    for pid, want in known.items():
        assert len(get(client, f'/api/v1/players/{pid}/playoffs')['titles']) == want, pid


def test_player_playoff_line_matches_basketball_reference(client):
    r = get(client, '/api/v1/players/jordami01/playoffs')
    c = r['career']
    assert (c['g'], c['pts']) == (179, 5987)
    assert c['ppg'] == pytest.approx(33.4, abs=0.05) and c['ft_pct'] == pytest.approx(0.828, abs=0.001)
    s1993 = next(s for s in r['seasons'] if s['season'] == 1993)
    assert s1993['ppg'] == pytest.approx(35.1, abs=0.05) and s1993['result'] == 'Champion' and s1993['team'] == 'CHI'


def test_missing_stats_stay_blank_not_zero(client):
    r = get(client, '/api/v1/players/russebi01/playoffs')
    assert r['career']['trb'] == 4104                              # Russell's real playoff rebounds
    early = get(client, '/api/v1/players/macaued01/playoffs')      # Ed Macauley: 1950s, no steals or blocks recorded
    assert early['career']['spg'] is None and early['career']['bpg'] is None


def test_champions_list(client):
    r = get(client, '/api/v1/playoffs/champions')
    by_season = {c['season']: c for c in r['champions']}
    assert len(r['champions']) == 80 and by_season[1947]['champion'] == 'Philadelphia Warriors'
    assert by_season[2016]['champion'] == 'Cleveland Cavaliers' and (by_season[2016]['wins'], by_season[2016]['losses']) == (4, 3)
    assert by_season[1998]['runner_up'] == 'Utah Jazz'
    assert by_season[2025]['champion'] == 'Oklahoma City Thunder' and (by_season[2025]['wins'], by_season[2025]['losses']) == (4, 3)
    assert by_season[2026]['champion'] and by_season[2026]['runner_up']                 # through the latest season
    assert by_season[1969]['finals_mvp']['player'] == 'Jerry West' and by_season[1998]['finals_mvp']['player'] == 'Michael Jordan'
    assert by_season[2024]['finals_mvp']['player'] == 'Jaylen Brown' and by_season[2025]['finals_mvp']['player'] == 'Shai Gilgeous-Alexander'
    assert all(by_season[s]['finals_mvp'] for s in range(1969, 2027)) and by_season[1968]['finals_mvp'] is None
    titles = r['titles_by_franchise']
    assert titles['Boston Celtics'] == 18 and titles['Los Angeles Lakers'] == 17           # Lakers: 5 as Minneapolis, 12 in LA
    assert titles['Golden State Warriors'] == 7 and titles['Chicago Bulls'] == 6
    assert titles['Oklahoma City Thunder'] == 2                                         # Seattle 1979 and Oklahoma City 2025


def test_team_playoff_history(client):
    r = get(client, '/api/v1/teams/Los%20Angeles%20Lakers/playoffs')
    assert len(r['titles']) == 17 and r['titles'][0] == 1949 and r['finals_appearances'] == 32
    seasons = {s['season']: s for s in r['seasons']}
    assert seasons[1952]['team_name'] == 'Minneapolis Lakers' and seasons[1952]['champion']
    assert r['series_won'] + r['series_lost'] == len(r['series'])
    assert get(client, '/api/v1/teams/Seattle%20Pilots/playoffs', status=404)


def test_playoff_results_follow_the_bracket(client):
    gsw = {s['season']: s for s in get(client, '/api/v1/teams/Golden%20State%20Warriors/playoffs')['seasons']}
    assert gsw[2016]['result'] == 'Lost in Finals' and (gsw[2016]['series_won'], gsw[2016]['series_lost']) == (3, 1)
    assert gsw[2015]['champion'] and gsw[2015]['series_won'] == 4


def test_game_7_missing_from_one_source_is_included(client):
    # gonzalo's box scores stop at 3-3 for Cavaliers-Magic 2024 (no Game 7); the series table has the full 4-3
    cle = get(client, '/api/v1/teams/Cleveland%20Cavaliers/playoffs')
    first = next(m for m in cle['series'] if m['season'] == 2024 and m['opponent'] == 'ORL')
    assert first['won'] and (first['wins'], first['losses']) == (4, 3) and first['complete']


def test_rings_cover_the_latest_seasons_and_match_official_counts(client):
    assert [t['season'] for t in get(client, '/api/v1/players/gilgesh01/playoffs')['titles']] == [2025]
    assert len(get(client, '/api/v1/players/jordami01/playoffs')['titles']) == 6
    assert len(get(client, '/api/v1/players/tsiorlo01/playoffs')['titles']) == 2        # Celtics reserve: rostered, never in a box score


def test_finals_mvp_counts(client):
    counts = {pid: len(get(client, f'/api/v1/players/{pid}/playoffs')['finals_mvp_seasons']) for pid in ('jordami01', 'jamesle01', 'duncati01', 'johnsma02')}
    assert counts == {'jordami01': 6, 'jamesle01': 4, 'duncati01': 3, 'johnsma02': 3}
    assert 1998 in get(client, '/api/v1/players/jordami01/honors')['finals_mvp_seasons']


def test_playoff_leaders(client):
    pts = get(client, '/api/v1/leaders/playoffs?stat=pts&limit=3')
    assert [p['player'] for p in pts] == ['LeBron James', 'Michael Jordan', 'Kareem Abdul-Jabbar']
    assert pts[1]['pts'] == 5987 and pts[1]['titles'] == 6
    ppg = get(client, '/api/v1/leaders/playoffs?stat=ppg&limit=2')
    assert ppg[0]['player'] == 'Michael Jordan' and all(p['g'] >= 25 for p in ppg)         # averages need a real sample
    assert get(client, '/api/v1/leaders/playoffs?stat=titles&limit=1')[0]['player'] == 'Bill Russell'
    assert get(client, '/api/v1/leaders/playoffs?stat=ws', status=400)


def test_titles_appear_in_honors_and_comparisons(client):
    assert 1998 in get(client, '/api/v1/players/jordami01/honors')['title_seasons']
    c = get(client, '/api/v1/compare/players?a=curryst01&b=jamesle01&align=calendar&position=2015')     # Curry won it, LeBron lost the Finals
    assert 'NBA Champion' in c['positions'][0]['a']['honors'] and 'NBA Champion' not in c['positions'][0]['b']['honors']


def test_playoff_coverage_is_reported(client):
    m = get(client, '/api/v1/meta')
    assert m['playoffs_through'] == m['series_through'] == m['latest_season']
    assert m['playoffs_partial'] == [2025]          # no box scores for the 2024-25 playoffs: series totals, some players missing
