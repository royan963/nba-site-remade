"""Game-by-game data. Expected values are well-known single-game records and results."""
import pytest


def get(client, path, status=200):
    r = client.get(path)
    assert r.status_code == status, r.text
    return r.json()


def test_famous_games(client):
    wilt = get(client, '/api/v1/players/chambwi01/highs')
    assert (wilt['highs']['pts']['value'], wilt['highs']['pts']['date'], wilt['highs']['pts']['opponent']) == (100, '1962-03-02', 'NYK')
    assert wilt['milestones']['pts50'] == 118
    kobe = get(client, '/api/v1/players/bryanko01/highs')['highs']['pts']
    assert (kobe['value'], kobe['date'], kobe['opponent']) == (81, '2006-01-22', 'TOR')
    mj = get(client, '/api/v1/players/jordami01/highs')
    assert mj['milestones']['pts50'] == 31 and mj['highs']['pts']['value'] == 69
    mjp = get(client, '/api/v1/players/jordami01/highs?type=playoffs')['highs']['pts']
    assert (mjp['value'], mjp['date'], mjp['opponent']) == (63, '1986-04-20', 'BOS')


def test_gamelog_shapes_and_results(client):
    g = get(client, '/api/v1/players/jordami01/gamelog?season=1998&type=playoffs')
    assert len(g['games']) == 21 and all(x['result'] in ('W', 'L') for x in g['games'])
    last = g['games'][-1]
    assert last['date'] == '1998-06-14' and last['opponent'] == 'UTA' and last['result'] == 'W' and last['pts'] == 45   # Game 6, "the last shot"
    seasons = {s['season'] for s in g['seasons']}
    assert {1985, 1998, 2003} <= seasons


def test_newest_seasons_have_playoffs_and_the_current_season(client):
    cov = get(client, '/api/v1/games/coverage')
    assert cov['missing_playoffs'] == [] and cov['last_season'] >= 2027      # the 2024-25 playoffs were filled in from the eoinamoore data
    reg = get(client, '/api/v1/players/gilgesh01/gamelog?season=2026')
    assert len(reg['games']) >= 60
    assert get(client, '/api/v1/players/gilgesh01/gamelog?season=2026&type=playoffs')['games']
    po25 = get(client, '/api/v1/players/gilgesh01/gamelog?season=2025&type=playoffs')['games']
    assert len(po25) == 23 and po25[-1]['date'] == '2025-06-22' and po25[-1]['result'] == 'W'
    by_cov = {(s['season'], s['playoffs']): s for s in cov['seasons']}
    assert by_cov[(2026, True)]['games'] == 85 and by_cov[(2025, False)]['complete'] >= 1220 and by_cov[(2025, True)]['games'] == 84


def test_rebuilt_rows_leave_unverified_stats_blank(client):
    # games rebuilt from play-by-play have no assists or minutes; they must be empty, never zero
    for pid in ('gilgesh01', 'jokicni01', 'wembavi01', 'sengual01'):
        for season in (2025, 2026):
            rows = [x for x in get(client, f'/api/v1/players/{pid}/gamelog?season={season}')['games'] if x['src'] == 'dc_pbp']
            if rows:
                assert all(x['ast'] is None and x['mp'] is None and x['pts'] is not None for x in rows)
                return
    pytest.skip('no rebuilt rows among the sampled players')


def test_protested_1978_game_keeps_both_teams(client):
    rows = [x for x in get(client, '/api/v1/players/catchha01/gamelog?season=1979')['games'] if x['date'] == '1978-11-08']
    assert {r['team'] for r in rows} == {'NJN', 'PHI'}          # traded between the original game and its replayed finish


def test_team_head_to_head(client):
    x = get(client, '/api/v1/head-to-head/teams?a=Boston%20Celtics&b=Los%20Angeles%20Lakers')
    assert len(x['series']) == 12 and x['series_a_won'] == 9                                      # 12 Finals meetings, Boston 9-3
    assert x['regular']['games'] > 250 and x['playoffs']['games'] > 60
    assert x['recent'] and x['first_meeting'] < '1960'
    get(client, '/api/v1/head-to-head/teams?a=Boston%20Celtics&b=Boston%20Celtics', status=400)
    get(client, '/api/v1/head-to-head/teams?a=Boston%20Celtics&b=Seattle%20Pilots', status=404)


def test_player_head_to_head(client):
    x = get(client, '/api/v1/head-to-head/players?a=jamesle01&b=curryst01')
    assert (x['playoffs']['games'], x['playoffs']['a_wins'], x['playoffs']['b_wins']) == (28, 11, 17)   # four Finals + 2023 West semis
    assert x['teammate_games'] == 0
    t = get(client, '/api/v1/head-to-head/players?a=curryst01&b=thompkl01')
    assert t['teammate_games'] > 500 and t['regular']['games'] > 0                                       # Klay later played against him
    get(client, '/api/v1/head-to-head/players?a=jamesle01&b=jamesle01', status=400)


def test_current_season_games_know_their_franchises_and_team_names(client):
    """2026-27 has no team-season rows yet, so franchises and names carry over from the team's latest season."""
    h = get(client, '/api/v1/head-to-head/teams?a=Detroit Pistons&b=Boston Celtics')
    first = h['recent'][0]
    assert (first['season'], first['date']) == (2027, '2026-10-20') and (first['a_pts'], first['b_pts']) == (121, 113)
    assert first['a_team'] == 'Detroit Pistons' and first['b_team'] == 'Boston Celtics' and first['a_home'] is True


# ---- play-in and NBA Cup final games are not regular-season games --------------------------------------------------------
# The NBA does not count play-in games or the Cup championship game in regular-season totals, records or player stats.

def test_play_in_and_cup_final_games_are_not_in_a_players_regular_season_log(client):
    lebron = get(client, '/api/v1/players/jamesle01/gamelog?season=2024')['games']
    assert len(lebron) == 71                                        # his 2023-24 regular season (he also played the Cup final and a play-in game)
    assert '2023-12-09' not in {g['date'] for g in lebron} and '2024-04-16' not in {g['date'] for g in lebron}
    sga = get(client, '/api/v1/players/gilgesh01/gamelog?season=2025')['games']
    assert len(sga) == 76 and '2024-12-17' not in {g['date'] for g in sga}


def test_play_in_games_are_not_playoff_games_either(client):
    playoffs = get(client, '/api/v1/players/jamesle01/gamelog?season=2024&type=playoffs')['games']
    assert playoffs and all(g['date'] >= '2024-04-20' for g in playoffs)


def test_career_highs_and_milestones_skip_play_in_and_cup_final_games(client):
    highs = get(client, '/api/v1/players/jamesle01/highs')
    games = highs['milestones']['games']
    all_games = sum(len(get(client, f'/api/v1/players/jamesle01/gamelog?season={s}')['games']) for s in range(2004, 2028))
    assert games == all_games == 1623          # 1,622 through 2025-26 (the career total) + his first 2026-27 game


def test_team_head_to_head_records_skip_the_cup_final(client):
    h = get(client, '/api/v1/head-to-head/teams?a=Los Angeles Lakers&b=Indiana Pacers')
    assert '2023-12-09' not in {g['date'] for g in h['recent'] if g.get('kind') == 'regular'}
    assert all(g['kind'] in ('regular', 'playoffs', 'play_in', 'cup_final') for g in h['recent'])
    cup = [g for g in h['recent'] if g['date'] == '2023-12-09']
    assert cup and cup[0]['kind'] == 'cup_final'
