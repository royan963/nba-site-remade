"""Official headshots: NBA.com ids for players and franchises (scripts/prep_nba_ids.py, data/nba_ids.json) and
/api/v1/players/{id}/headshots. Expected ids are NBA.com's own public ids, written here by hand."""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))


def ids():
    f = ROOT / 'data' / 'nba_ids.json'
    if not f.exists():
        pytest.skip('data/nba_ids.json not built yet (scripts/prep_nba_ids.py)')
    return json.loads(f.read_text(encoding='utf-8'))


def test_known_players_and_franchises_get_their_nba_ids():
    d = ids()
    p, t = d['players'], d['teams']
    assert p['jamesle01'] == 2544 and p['wembavi01'] == 1641705 and p['leonaka01'] == 202695 and p['jordami01'] == 893
    assert p['paytoga01'] == 56 and p['paytoga02'] == 1627780            # father and son kept apart
    assert p['hollaro01'] == 1641842                                     # "Ron" here, "Ronald ... II" at NBA.com
    assert p['robincl02'] == 361 and p.get('robincl01') != 361          # a short first name never takes an exact match's person
    assert len(t) == 30 and len(set(t.values())) == 30
    assert t['San Antonio Spurs'] == 1610612759 and t['Brooklyn Nets'] == 1610612751   # the Nets keep New Jersey's id
    assert len(set(p.values())) == len(p)                                # one NBA person is never two of our players
    s = d['stats']
    assert s['recent_matched'] >= 0.97 * s['recent_players']


def test_seasons_are_named_by_their_last_year():
    from prep_nba_ids import season_of
    got = season_of(pd.Series(['2026-10-22 21:30:00', '2027-04-12 19:00:00', '2026-06-10 20:00:00'])).tolist()
    assert got == [2027, 2027, 2026]


def test_headshots_endpoint(client):
    if not ids()['players'].get('jamesle01'):
        pytest.skip('no ids')
    r = client.get('/api/v1/players/jamesle01/headshots').json()
    assert r['nba_id'] == 2544 and r['latest'] == 'https://cdn.nba.com/headshots/nba/latest/260x190/2544.png'
    by = {(x['season'], x['team']): x['url'] for x in r['seasons']}
    # NBA.com names folders by the season's first year: 2015-16 (season 2016 here) is folder 2015
    assert by[(2016, 'CLE')] == 'https://cdn.nba.com/headshots/nba/1610612739/2015/260x190/2544.png'
    assert by[(2020, 'LAL')] == 'https://cdn.nba.com/headshots/nba/1610612747/2019/260x190/2544.png'
    assert min(x['season'] for x in r['seasons']) >= 2015                 # no season photos before 2014-15
    jordan = client.get('/api/v1/players/jordami01/headshots').json()
    assert jordan['seasons'] == [] and jordan['latest'].endswith('/latest/260x190/893.png')
    assert client.get('/api/v1/players/nobody00/headshots').status_code == 404
