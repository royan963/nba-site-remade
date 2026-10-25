"""Players who are in the 2026-27 games but not yet in the Basketball-Reference player table (this year's rookies).

They are added as provisional players (data/new_players.json, built by scripts/prep_games_eoin.py) so their games and stats show up.
When the Basketball-Reference data catches up, the official rows win and the provisional ones are dropped.
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location('prep_games_eoin', ROOT / 'scripts' / 'prep_games_eoin.py')
ge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ge)


# ---- helpers ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('first, last, taken, expected', [
    ('Cameron', 'Boozer', set(), 'boozeca01'),
    ('Cameron', 'Boozer', {'boozeca01'}, 'boozeca02'),
    ('Cameron', 'Boozer', {'boozeca01', 'boozeca02'}, 'boozeca03'),
    ('Sergio', 'de Larrea', set(), 'delarse01'),
    ('Alperen', 'Şengün', set(), 'sengual01'),
    ('Egor', 'Demin', set(), 'demineg01'),
    ("Dyson", "Daniels", set(), 'daniedy01'),
    ('Jaylen', 'Wu', set(), 'wuja01'.replace('wuja01', 'wuja01')),
    ('Hansen', 'Yang', {'yangha01'}, 'yangha02'),
])
def test_ids_follow_basketball_references_pattern_and_skip_taken_ones(first, last, taken, expected):
    assert ge.bbref_id(first, last, taken) == expected


@pytest.mark.parametrize('flags, pos', [((1, 0, 0), 'G'), ((0, 1, 0), 'F'), ((0, 0, 1), 'C'), ((1, 1, 0), 'G-F'), ((0, 1, 1), 'F-C'),
                                        ((0, 0, 0), None), ((np.nan, np.nan, np.nan), None)])
def test_position_comes_from_the_guard_forward_center_flags(flags, pos):
    assert ge.position_from_flags(*flags) == pos


def test_age_is_as_of_february_first_of_the_season_year():
    assert ge.age_on('2006-05-11', 2027) == 20
    assert ge.age_on('2006-01-31', 2027) == 21
    assert ge.age_on('2006-02-01', 2027) == 21
    assert ge.age_on(None, 2027) is None and ge.age_on(float('nan'), 2027) is None


PERSON = {'firstName': 'Cameron', 'lastName': 'Boozer', 'birthDate': '2007-07-23', 'heightInches': 80.0, 'bodyWeightLbs': 250.0,
          'guard': 0.0, 'forward': 1.0, 'center': 0.0}
TOTALS = {'g': 5, 'gs': 5, 'mp': 150.0, 'pts': 100, 'trb': 40, 'ast': 10, 'stl': 5, 'blk': 3, 'fg': 35, 'fga': 70, 'x3p': 10, 'x3pa': 25, 'ft': 20, 'fta': 25}


def test_a_provisional_player_gets_a_career_row_and_a_season_row_in_the_site_formats():
    career, season = ge.provisional_player(PERSON, TOTALS, 'boozeca01', 'WAS', 2027)
    assert career['player_id'] == 'boozeca01' and career['player'] == 'Cameron Boozer' and career['pos'] == 'F' and career['hof'] is False
    assert (career['g'], career['pts'], career['trb'], career['ast'], career['seasons_played'], career['first_season'], career['last_season']) == (5, 100, 40, 10, 1, 2027, 2027)
    assert (career['ppg'], career['rpg'], career['apg']) == (20.0, 8.0, 2.0) and career['ht_in_in'] == 80 and career['wt'] == 250
    assert career['ws'] is None and career['vorp'] is None and career['all_star'] == 0
    assert season['player_id'] == 'boozeca01' and season['season'] == 2027 and season['team'] == 'WAS' and season['age'] == 19
    assert (season['g'], season['gs'], season['mp'], season['pts'], season['trb'], season['ast']) == (5, 5, 30.0, 20.0, 8.0, 2.0)
    assert (season['fg_pct'], season['x3p_pct'], season['ft_pct'], season['x3pa'], season['fta']) == (0.5, 0.4, 0.8, 5.0, 5.0)


def test_a_provisional_player_with_no_attempts_has_no_percentages():
    _, season = ge.provisional_player(PERSON, {**TOTALS, 'fga': 0, 'fg': 0, 'x3pa': 0, 'x3p': 0, 'fta': 0, 'ft': 0}, 'boozeca01', 'WAS', 2027)
    assert season['fg_pct'] is None and season['x3p_pct'] is None and season['ft_pct'] is None


OFFICIAL = [{'player_id': 'boozeca01', 'player': 'Cameron Boozer', 'first_season': 2027, 'last_season': 2027},
            {'player_id': 'jamesle01', 'player': 'LeBron James', 'first_season': 2004, 'last_season': 2027},
            {'player_id': 'morrima01', 'player': 'Marcus Morris', 'first_season': 2012, 'last_season': 2025}]


def stub(pid, name):
    return {'player_id': pid, 'player': name}


def test_a_provisional_player_is_dropped_once_the_official_table_has_that_id():
    keep, remap = ge.reconcile_stubs([stub('boozeca01', 'Cameron Boozer')], OFFICIAL)
    assert keep == [] and remap == {}


def test_a_provisional_player_is_remapped_if_the_official_table_has_the_same_name_under_another_id():
    keep, remap = ge.reconcile_stubs([stub('boozeca02', 'Cameron Boozer')], OFFICIAL)
    assert keep == [] and remap == {'boozeca02': 'boozeca01'}


def test_a_provisional_player_is_kept_while_the_official_table_has_nobody_by_that_name():
    keep, remap = ge.reconcile_stubs([stub('mara01', 'Aday Mara')], OFFICIAL)
    assert [k['player_id'] for k in keep] == ['mara01'] and remap == {}


def test_an_older_namesake_does_not_absorb_a_rookie():
    keep, remap = ge.reconcile_stubs([stub('morrima02', 'Marcus Morris')], OFFICIAL)
    assert [k['player_id'] for k in keep] == ['morrima02'] and remap == {}


# ---- the committed data and the loaded site ----------------------------------------------------------------------------------
def stubs_file():
    return json.loads((ROOT / 'data' / 'new_players.json').read_text(encoding='utf8'))


def test_provisional_players_are_in_the_data_with_ids_that_do_not_collide_with_official_ones():
    s = stubs_file()
    official = {r[0] for r in json.loads((ROOT / 'data' / 'player_career.json').read_text(encoding='utf8'))['rows']}
    ids = [p['player_id'] for p in s['players']]
    assert len(ids) >= 20 and len(set(ids)) == len(ids) and not (set(ids) & official)
    assert {x['player_id'] for x in s['seasons']} == set(ids)


def rookie_id(client):
    hits = [h for h in client.get('/api/v1/players?q=cameron boozer').json() if h['player'] == 'Cameron Boozer']
    assert len(hits) == 1
    return hits[0]['player_id']


def test_a_rookie_has_a_player_page_with_a_2026_27_season(client):
    pid = rookie_id(client)
    p = client.get(f'/api/v1/players/{pid}').json()
    assert p['player'] == 'Cameron Boozer' and p['first_season'] == 2027 and p['g'] >= 1
    seasons = client.get(f'/api/v1/players/{pid}/seasons').json()
    assert [x['season'] for x in seasons] == [2027] and seasons[0]['g'] == p['g']


def test_a_rookies_games_show_in_his_game_log_and_agree_with_his_season_line(client):
    pid = rookie_id(client)
    log = client.get(f'/api/v1/players/{pid}/gamelog?season=2027').json()['games']
    season = client.get(f'/api/v1/players/{pid}/seasons').json()[0]
    assert len(log) >= 1
    if len(log) == season['g']:                      # every game he played has stats
        assert round(sum(g['pts'] for g in log) / len(log), 1) == season['pts']


def test_nearly_all_2026_27_games_have_player_stats_now():
    g = pd.read_csv(ROOT / 'data' / 'games' / 'games_2027.csv.gz')
    assert g['complete'].mean() >= 0.9, g.loc[~g['complete'], 'game_ref'].tolist()
