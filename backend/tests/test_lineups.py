"""All-time lineup builder: scoring model and saved lineups."""
API = '/api/v1'
GREATS = ['curryst01', 'jordami01', 'jamesle01', 'duncati01', 'onealsh01']


def score(client, picks):
    r = client.post(f'{API}/lineups/score', json={'players': [{'player_id': p, 'season': s} for p, s in picks]})
    assert r.status_code == 200, r.text
    return r.json()


def test_greats_beat_bench_players(client):
    greats = score(client, [(p, None) for p in GREATS])
    bench = score(client, [('agbajoc01', 2026), ('hausesa01', 2024), ('kornelu01', 2023), ('walshjo01', 2025), ('mykhasv01', 2023)])
    assert greats['overall'] > bench['overall'] + 25
    assert greats['real_percentile'] > 99 and greats['grade'] == 'All-time great'
    assert bench['real_percentile'] < 30


def test_best_season_default(client):
    s = score(client, [('jordami01', None)])
    assert s['players'][0]['season'] == 1988 and s['complete'] is False and s['overall'] is None


def test_fit_penalizes_all_centers(client):
    centers = score(client, [(p, None) for p in ('onealsh01', 'olajuha01', 'robinda01', 'ewingpa01', 'mutomdi01')])
    fit = next(c['score'] for c in centers['categories'] if c['key'] == 'fit')
    assert fit < 70 and any('No guard' in n for n in centers['fit_notes'])


def test_old_eras_score_with_notes(client):
    s = score(client, [('russebi01', 1965), ('cousybo01', 1957), ('chambwi01', 1962), ('westje01', 1966), ('bayloel01', 1962)])
    assert s['overall'] > 70
    assert any('three-point line' in n for n in s['notes']) and any('usage' in n for n in s['notes'])


def test_score_validation(client):
    bad = lambda picks: client.post(f'{API}/lineups/score', json={'players': picks}).status_code
    assert bad([{'player_id': 'nobody00'}]) == 422
    assert bad([{'player_id': 'curryst01', 'season': 1990}]) == 422          # didn't play then
    assert bad([{'player_id': 'curryst01'}, {'player_id': 'curryst01'}]) == 422
    assert bad([{'player_id': p} for p in GREATS + ['birdla01']]) == 422      # max five
    assert bad([]) == 422


def test_player_seasons_endpoint(client):
    r = client.get(f'{API}/lineups/player-seasons/curryst01').json()
    assert r['best_season'] == 2016 and r['seasons'][0]['season'] >= 2026
    assert all(0 <= s['rating'] <= 100 for s in r['seasons'] if s['rating'] is not None)


def test_save_and_share_lineup(make_user, client):
    c = make_user()
    body = {'name': 'My all-time five', 'description': 'Peak seasons', 'is_public': False,
            'players': [{'player_id': p} for p in GREATS]}
    assert client.post(f'{API}/lineups', json=body).status_code in (401, 403)        # needs an account
    saved = c.post(f'{API}/lineups', json=body).json()
    assert saved['score']['overall'] > 80 and saved['owner']['username'] == c.user['username']
    lid = saved['id']
    client.cookies.clear()
    assert client.get(f'{API}/lineups/{lid}').status_code == 404                    # private: hidden
    assert c.get(f'{API}/lineups/{lid}').json()['mine'] is True
    c.put(f'{API}/lineups/{lid}', json={**body, 'is_public': True,
                                       'players': [{'player_id': p} for p in GREATS[:4] + ['birdla01']]})
    shared = client.get(f'{API}/lineups/{lid}').json()
    assert shared['mine'] is False and shared['score']['players'][4]['player'] == 'Larry Bird'
    assert lid in [x['id'] for x in client.get(f'{API}/lineups/public').json()]
    assert lid in [x['id'] for x in client.get(f'{API}/users/{c.user["username"]}').json()['lineups']]
    other = make_user()
    assert other.put(f'{API}/lineups/{lid}', json=body).status_code == 404
    assert other.delete(f'{API}/lineups/{lid}').status_code == 404
    assert c.delete(f'{API}/lineups/{lid}').status_code == 204
    assert c.get(f'{API}/me/lineups').json() == []


def test_saving_needs_exactly_five(make_user):
    c = make_user()
    r = c.post(f'{API}/lineups', json={'name': 'Short', 'players': [{'player_id': p} for p in GREATS[:3]]})
    assert r.status_code == 422
