"""Games from the eoinamoore dataset fill the gaps in data/games and add the current season.

Unit tests cover the conversion helpers on small fixtures. The data tests check the committed files: no duplicate games,
Basketball-Reference-style game ids, no preseason, player points that add up for the rows this source added, and the
gaps it was added to fill (2024-25 playoffs and play-in, the last games of 2025-26, the 2026-27 season so far).
"""
import gzip
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
GAMES = ROOT / 'data' / 'games'

spec = importlib.util.spec_from_file_location('prep_games_eoin', ROOT / 'scripts' / 'prep_games_eoin.py')
ge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ge)


# ---- helpers ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('game_id, season', [(22600005, 2027), ('0022600005', 2027), (42400407, 2025), (22500001, 2026), (21900001, 2020), (29600001, 1997)])
def test_game_season_is_the_year_the_season_ends(game_id, season):
    assert ge.game_season(game_id) == season


@pytest.mark.parametrize('v, expected', [('18:18', 18.3), ('5:53', 5.9), (32.5, 32.5), ('34', 34.0)])
def test_minutes_are_read_in_both_formats(v, expected):
    assert ge.minutes_to_float(v) == pytest.approx(expected, abs=0.05)


def test_missing_minutes_are_nan():
    assert np.isnan(ge.minutes_to_float(None)) and np.isnan(ge.minutes_to_float(float('nan'))) and np.isnan(ge.minutes_to_float('DNP'))


@pytest.mark.parametrize('team_minutes, ot', [(240, 0), (265, 1), (290, 2), (240.4, 0), (None, None)])
def test_overtimes_come_from_team_minutes(team_minutes, ot):
    assert ge.ot_from_minutes(team_minutes) == ot


def test_game_ref_is_date_then_zero_then_home_team():
    assert ge.game_ref('2026-10-21', 'LAL') == '202610210LAL'


@pytest.mark.parametrize('t, keep', [('Regular Season', True), ('Playoffs', True), ('Play-in Tournament', True), ('Emirates NBA Cup', True),
                                     ('NBA Cup', True), ('in-season-knockout', True), ('Preseason', False), ('Pre Season', False),
                                     ('All-Star Game', False), (None, False)])
def test_preseason_and_all_star_games_are_never_kept(t, keep):
    assert ge.keep_game_type(t) is keep


def test_only_playoffs_are_flagged_as_playoffs():
    """Play-in games follow the existing files: counted with the regular season."""
    assert ge.is_playoffs('Playoffs') is True
    assert ge.is_playoffs('Play-in Tournament') is False and ge.is_playoffs('Regular Season') is False


def test_player_names_match_across_accents_and_suffixes():
    assert ge.name_key('Alperen Şengün') == ge.name_key('Alperen Sengun')
    assert ge.name_key('Jaren Jackson Jr.') == ge.name_key('Jaren Jackson')


def test_a_nickname_or_short_first_name_resolves_by_team_season_and_last_name():
    """The source says 'Ronald Holland' and 'Ga Bitadze'; our season data has Ron Holland and Goga Bitadze."""
    rows = {'columns': ['season', 'player_id', 'player', 'team', 'age'],
            'rows': [[2026, 'hollaro01', 'Ron Holland', 'DET', 20], [2026, 'bitadgo01', 'Goga Bitadze', 'ORL', 26],
                     [2026, 'wilsoja01', 'Jaylen Wilson', 'DET', 25], [2026, 'wilsoja02', 'Jalen Wilson', 'DET', 25]]}
    by_team, by_name, by_last = ge.player_index(rows)
    assert ge.resolve_player('ronald holland', 'DET', 2026, by_team, by_name, by_last) == 'hollaro01'
    assert ge.resolve_player('ga bitadze', 'ORL', 2026, by_team, by_name, by_last) == 'bitadgo01'
    assert ge.resolve_player('someone wilson', 'DET', 2026, by_team, by_name, by_last) is None        # two Wilsons on that team: no guess
    assert ge.resolve_player('ronald holland', 'ORL', 2026, by_team, by_name, by_last) is None        # wrong team: no guess


def test_a_players_team_comes_from_the_home_flag_not_the_team_id():
    """About 270 player rows since 2024-25 have no team id (28 games, among them the 2024-25 NBA Cup final)."""
    p = pd.DataFrame({'home': [1.0, 0.0, 1.0], 'playerteamId': [np.nan, np.nan, 5]})
    assert ge.team_from_home_flag(p['home'], 'OKC', 'MIL').tolist() == ['OKC', 'MIL', 'OKC']


def test_games_added_earlier_but_incomplete_are_rebuilt_on_the_next_run():
    """A rookie missing from the player table today appears after the next season-data update; the game is then redone."""
    games = pd.DataFrame({'game_ref': ['a', 'b', 'c'], 'src': ['bref', 'eoin', 'eoin'], 'complete': [True, True, False]})
    pg = pd.DataFrame({'game_ref': ['a', 'b', 'c'], 'player_id': ['p1', 'p2', 'p3']})
    g, p = ge.drop_pending(games, pg)
    assert g['game_ref'].tolist() == ['a', 'b'] and p['game_ref'].tolist() == ['a', 'b']


def test_a_name_in_the_other_order_resolves_to_the_same_player():
    """Basketball-Reference has 'Yang Hansen' (surname first); the new dataset has 'Hansen Yang'."""
    rows = {'columns': ['season', 'player_id', 'player', 'team', 'age'],
            'rows': [[2026, 'yangha01', 'Yang Hansen', 'POR', 20], [2026, 'hollaro01', 'Ron Holland', 'DET', 20]]}
    by_team, by_name, by_last = ge.player_index(rows)
    assert ge.resolve_player('hansen yang', 'POR', 2026, by_team, by_name, by_last) == 'yangha01'
    assert ge.resolve_player('hansen yang', 'DET', 2026, by_team, by_name, by_last) == 'yangha01'   # traded or mislabeled team: still the one recent player with that name
    assert ge.resolve_player('hansen yang', 'DET', 2026, by_team, by_name, by_last) != 'hollaro01'
    assert ge.resolve_player('hansen yang', 'POR', 2027, by_team, by_name, by_last) == 'yangha01'   # a newer season: the one recent player with that name


def test_games_added_for_portland_in_2025_26_have_player_stats():
    g = games(2026)
    assert g.loc[g['src'] == 'eoin'].set_index('game_ref').loc['202602200POR', 'complete']


def test_a_game_is_a_duplicate_if_the_same_teams_and_score_exist_within_two_days():
    existing = pd.DataFrame({'date': ['2025-02-12'], 'home': ['BRK'], 'away': ['PHI'], 'home_pts': [100], 'away_pts': [96]})
    assert ge.is_duplicate({'date': '2025-02-13', 'home': 'BRK', 'away': 'PHI', 'home_pts': 100, 'away_pts': 96}, existing)
    assert not ge.is_duplicate({'date': '2025-02-20', 'home': 'BRK', 'away': 'PHI', 'home_pts': 100, 'away_pts': 96}, existing)
    assert not ge.is_duplicate({'date': '2025-02-12', 'home': 'BRK', 'away': 'PHI', 'home_pts': 101, 'away_pts': 96}, existing)


def test_a_team_sum_check_marks_complete_only_when_both_scores_add_up():
    pg = pd.DataFrame({'game_ref': ['g1'] * 3 + ['g2'] * 2, 'team': ['AAA', 'AAA', 'BBB', 'AAA', 'BBB'], 'pts': [60, 40, 90, 50, 80]})
    games = pd.DataFrame({'game_ref': ['g1', 'g2'], 'home': ['AAA', 'AAA'], 'away': ['BBB', 'BBB'], 'home_pts': [100, 100], 'away_pts': [90, 80]})
    assert ge.complete_flags(games, pg).to_dict() == {'g1': True, 'g2': False}


# ---- the committed data -------------------------------------------------------------------------------------------------
def read(name):
    with gzip.open(GAMES / name, 'rt', encoding='utf-8') as f:
        return pd.read_csv(f)


def games(season):
    return read(f'games_{season}.csv.gz')


def test_no_season_has_a_duplicate_game_id():
    for season in (2025, 2026, 2027):
        g = games(season)
        assert not g['game_ref'].duplicated().any(), season


def test_added_games_have_basketball_reference_style_ids_and_dates():
    for season in (2025, 2026, 2027):
        g = games(season)
        g = g[g['src'] == 'eoin']
        assert len(g) > 0
        assert (g['game_ref'] == g['date'].str.replace('-', '') + '0' + g['home']).all()


def test_no_preseason_games_were_added():
    """Preseason ran from early October; the 2026-27 regular season opened on 2026-10-20."""
    g = games(2027)
    assert g['date'].min() >= '2026-10-20'


def test_2024_25_playoffs_and_play_in_were_filled_in():
    g = games(2025)
    assert g['playoffs'].sum() == 84
    assert len(g[g['date'].between('2025-04-15', '2025-04-18') & ~g['playoffs']]) >= 6          # the play-in games
    final = g[g['playoffs']].sort_values('date').iloc[-1]
    assert (final['date'], final['home'], final['away']) == ('2025-06-22', 'OKC', 'IND') and (final['home_pts'], final['away_pts']) == (103, 91)


def test_2025_26_has_every_regular_season_game():
    g = games(2026)
    assert (~g['playoffs']).sum() >= 1230 + 6 + 1          # 1,230 regular season + 6 play-in + the NBA Cup final


def test_2026_27_season_starts_on_opening_night():
    g = games(2027).sort_values('date')
    assert g.iloc[0]['date'] == '2026-10-20' and len(g) >= 16 and (g['src'] == 'eoin').all()
    assert not g['playoffs'].any()


def test_every_team_label_in_added_games_is_a_known_team():
    known = set(pd.DataFrame(__import__('json').loads((ROOT / 'data' / 'team_geo.json').read_text())['rows'],
                             columns=__import__('json').loads((ROOT / 'data' / 'team_geo.json').read_text())['columns'])['abbr'])
    for season in (2025, 2026, 2027):
        g = games(season)
        g = g[g['src'] == 'eoin']
        assert set(g['home']) | set(g['away']) <= known


def test_added_player_rows_add_up_to_the_final_score_when_the_game_is_marked_complete():
    for season in (2025, 2026, 2027):
        g = games(season)
        g = g[(g['src'] == 'eoin') & g['complete']]
        pg = read(f'player_games_{season}.csv.gz')
        sums = pg.groupby(['game_ref', 'team'])['pts'].sum()
        bad = []
        for r in g.itertuples():
            if sums.get((r.game_ref, r.home)) != r.home_pts or sums.get((r.game_ref, r.away)) != r.away_pts:
                bad.append(r.game_ref)
        assert not bad, (season, bad[:5])


def test_incomplete_games_have_no_player_rows():
    for season in (2025, 2026, 2027):
        g = games(season)
        pg = read(f'player_games_{season}.csv.gz')
        incomplete = set(g.loc[(g['src'] == 'eoin') & ~g['complete'], 'game_ref'])
        assert not (set(pg['game_ref']) & incomplete)


def test_added_player_rows_use_known_player_ids_and_no_player_is_in_a_game_twice():
    import json
    d = json.loads((ROOT / 'data' / 'player_career.json').read_text(encoding='utf8'))
    known = {r[0] for r in d['rows']}
    for season in (2025, 2026, 2027):
        pg = read(f'player_games_{season}.csv.gz')
        pg = pg[pg['src'] == 'eoin']
        assert set(pg['player_id']) <= known
        assert not pg.duplicated(['game_ref', 'player_id', 'team']).any()


def test_play_in_and_cup_final_games_are_tagged_in_every_season_file():
    expected_play_in = {2020: 1, 2021: 6, 2022: 6, 2023: 6, 2024: 6, 2025: 6, 2026: 6}
    for season, n in expected_play_in.items():
        g = games(season)
        assert (g['kind'] == 'play_in').sum() == n, season
        assert g.loc[g['playoffs'], 'kind'].eq('playoffs').all() and g.loc[~g['playoffs'] & ~g['kind'].isin(['play_in', 'cup_final']), 'kind'].eq('regular').all()
    finals = {2024: '202312090LAL', 2025: '202412170OKC', 2026: '202512160NYK'}
    for season, ref in finals.items():
        g = games(season)
        assert g.loc[g['kind'] == 'cup_final', 'game_ref'].tolist() == [ref], season
    assert (games(2027)['kind'] == 'regular').all()


def test_kind_of_a_game_comes_from_the_nba_game_id():
    assert ge.game_kind(22600005) == 'regular' and ge.game_kind(42400407) == 'playoffs'
    assert ge.game_kind(52500211) == 'play_in' and ge.game_kind(62400001) == 'cup_final'
    assert ge.game_kind(12600001) is None and ge.game_kind(32600001) is None          # preseason (1) and All-Star (3) are not kept
