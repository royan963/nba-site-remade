"""The season in progress is rebuilt from the daily box scores (scripts/season_from_games.py, scripts/prep_season_live.py).

The exact stats are checked against Basketball-Reference's own numbers for 2023-24, a season whose box scores in
data/games/ come from Basketball-Reference too. The expected values come from data/player_seasons.json,
data/player_advanced.json and data/team_geo.json (the main dataset), never from the code under test.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import season_from_games as S  # noqa: E402

SEASON = 2024


@pytest.fixture(scope='module')
def built():
    teams, st, lg = S.season_tables(SEASON)
    return teams.set_index('team'), st, lg


def official(name):
    d = json.loads((ROOT / 'data' / f'{name}.json').read_text(encoding='utf-8'))
    df = pd.DataFrame(d['rows'], columns=d['columns'])
    return df[df['season'] == SEASON]


def test_team_ratings_match_the_official_numbers(built):
    teams, _, _ = built
    geo = official('team_geo').set_index('abbr').reindex(teams.index)
    assert (teams['srs'] - geo['srs']).abs().max() < 0.3
    for col in ('pace', 'o_rtg', 'd_rtg'):
        assert (teams[col] - geo[col]).abs().mean() < 0.15, col        # team turnovers aren't in player box scores; corrected
    assert (teams['pts_per_game'] - geo['pts_per_game']).abs().max() < 0.3


def test_player_lines_and_exact_rates_match(built):
    _, st, _ = built
    ps = official('player_seasons')
    traded = set(ps.loc[ps['team'].str.endswith('TM'), 'player_id'])
    one = ps[~ps['team'].str.endswith('TM')]
    m = st.merge(one, on=['player_id', 'team'], suffixes=('', '_br'))
    assert len(m) >= 0.99 * len(one)
    assert (m['pts'] / m['g'] - m['pts_br']).abs().mean() < 0.05
    adv = st[~st['player_id'].isin(traded) & (st['mp'] >= 500)].merge(official('player_advanced'), on='player_id', suffixes=('', '_br'))
    assert len(adv) > 250
    assert (adv['ts_pct'] - adv['ts_pct_br']).abs().mean() < 0.002
    assert (adv['usg_pct'] - adv['usg_pct_br']).abs().mean() < 0.1
    assert (adv['per'] - adv['per_br']).abs().mean() < 0.1                 # Hollinger's PER, as Basketball-Reference computes it


def test_the_estimates_were_checked_on_a_season_they_never_saw():
    m = json.loads((ROOT / 'scripts' / 'live_stat_model.json').read_text())
    assert m['tested_on'] not in range(*map(int, m['trained_on'].split('-')))
    assert m['models']['bpm']['test_mae_500_min'] < 0.6 and m['models']['bpm']['test_corr_500_min'] > 0.97
    assert m['models']['ws_48']['test_mae_500_min'] < 0.01


def test_the_newest_season_comes_from_the_box_scores_when_they_are_ahead():
    f = ROOT / 'data' / 'live_season.json'
    if not f.exists():
        pytest.skip('scripts/prep_season_live.py has not run yet')
    live = json.loads(f.read_text())
    if live['source'] != 'box_scores':
        pytest.skip('the main dataset has caught up')
    season = live['season']
    games = pd.read_csv(ROOT / 'data' / 'games' / f'games_{season}.csv.gz')
    regular = games[games['kind'].eq('regular') & games['complete'].astype(bool)]
    assert live['games'] == len(regular) and live['through'] == str(regular['date'].max())
    d = json.loads((ROOT / 'data' / 'team_geo.json').read_text())
    geo = pd.DataFrame(d['rows'], columns=d['columns'])
    geo = geo[geo['season'] == season]
    wins = pd.concat([regular.loc[regular['home_pts'] > regular['away_pts'], 'home'], regular.loc[regular['away_pts'] > regular['home_pts'], 'away']]).value_counts()
    assert len(geo) == 30 and all(geo.set_index('abbr')['w'].astype(int) == wins.reindex(geo['abbr']).fillna(0).astype(int).values)
    ps = json.loads((ROOT / 'data' / 'player_seasons.json').read_text())
    rows = [dict(zip(ps['columns'], r)) for r in ps['rows'] if r[0] == season]
    assert len({(r['player_id'], r['team']) for r in rows}) == len(rows)
    team_games = dict(zip(geo['abbr'], geo['w'] + geo['l']))
    assert all(r['g'] <= team_games.get(r['team'], 82) for r in rows)


def test_league_trends_for_the_season_in_progress_come_from_the_box_scores():
    f = ROOT / 'data' / 'live_season.json'
    if not f.exists() or json.loads(f.read_text())['source'] != 'box_scores':
        pytest.skip('the season in progress is not rebuilt from box scores')
    if 'in_progress' not in json.loads(f.read_text()):
        pytest.skip('data built before prep_season_live.py rebuilt the league trends')
    season = json.loads(f.read_text())['season']
    era = {r['season']: r for r in json.loads((ROOT / 'data' / 'era_trends.json').read_text())}
    teams, _, _ = S.season_tables(season)
    expected = float((teams['x3pa'] / teams['fga']).mean())          # league 3PT rate, the mean of the teams' rates
    assert abs(era[season]['x3p_ar'] - expected) < 0.001 and era[season]['num_teams'] == 30


def test_rookies_are_listed_once_after_the_rebuild(client):
    # provisional rookies (data/new_players.json) are also in the rebuilt season; the loader must not add them twice
    stubs = json.loads((ROOT / 'data' / 'new_players.json').read_text(encoding='utf8'))
    if not stubs['seasons']:
        pytest.skip('no provisional players')
    r = stubs['seasons'][0]
    seasons = client.get(f"/api/v1/players/{r['player_id']}/seasons").json()
    mine = [s for s in seasons if s['season'] == r['season']]
    assert len(mine) == len({s['team'] for s in mine})


def test_meta_says_how_the_newest_season_was_built(client):
    live = client.get('/api/v1/meta').json()['live_season']
    if not (ROOT / 'data' / 'live_season.json').exists():
        assert live is None
        return
    assert live and live['season'] >= 2027 and live['source'] in ('box_scores', 'official')
