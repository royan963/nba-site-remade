"""Accounts: sign-up, sign-in, sessions, security protections, favorites,
saved comparisons, profiles and account deletion."""
import pytest

API = '/api/v1'


def test_register_signs_you_in(make_user):
    c = make_user(display_name='Royan')
    me = c.get(f'{API}/auth/me').json()
    assert me['username'] == c.user['username'] and me['display_name'] == 'Royan'
    assert 'password' not in str(me).lower()


def test_session_cookie_is_httponly(client):
    r = client.post(f'{API}/auth/register', json={'email': 'cookie@example.com', 'username': 'cookie_fan',
                                                   'password': 'a strong passphrase'})
    cookie = r.headers['set-cookie'].lower()
    assert 'nba_session=' in cookie and 'httponly' in cookie and 'samesite=lax' in cookie
    client.cookies.clear()


@pytest.mark.parametrize('body, message', [
    ({'email': 'not-an-email', 'username': 'okname', 'password': 'a strong passphrase'}, 'valid email'),
    ({'email': 'a@b.co', 'username': 'Bad Name!', 'password': 'a strong passphrase'}, 'Usernames'),
    ({'email': 'a@b.co', 'username': 'admin', 'password': 'a strong passphrase'}, 'reserved'),
    ({'email': 'a@b.co', 'username': 'okname', 'password': 'short'}, 'at least 10'),
    ({'email': 'a@b.co', 'username': 'okname', 'password': 'basketball'}, 'too easy'),
    ({'email': 'a@b.co', 'username': 'okname', 'password': 'okname'}, 'at least 10'),
])
def test_register_validation(client, body, message):
    r = client.post(f'{API}/auth/register', json=body)
    assert r.status_code == 422 and message in r.json()['detail']


def test_duplicate_email_and_username(make_user, client):
    c = make_user()
    dup_email = client.post(f'{API}/auth/register', json={'email': c.user['email'].upper(), 'username': 'other_name',
                                                          'password': 'a strong passphrase'})
    assert dup_email.status_code == 409
    dup_user = client.post(f'{API}/auth/register', json={'email': 'new@example.com', 'username': c.user['username'],
                                                         'password': 'a strong passphrase'})
    assert dup_user.status_code == 409
    assert client.get(f'{API}/auth/username-available?username={c.user["username"]}').json()['available'] is False


def test_login_logout(make_user, client):
    c = make_user()
    client.cookies.clear()
    bad = client.post(f'{API}/auth/login', json={'email': c.user['email'], 'password': 'wrong password!'})
    assert bad.status_code == 401 and bad.json()['detail'] == 'Incorrect email or password.'
    unknown = client.post(f'{API}/auth/login', json={'email': 'nobody@example.com', 'password': 'whatever123'})
    assert unknown.json()['detail'] == bad.json()['detail']          # no hint whether the email exists
    ok = client.post(f'{API}/auth/login', json={'email': c.user['email'].upper(), 'password': c.password})
    assert ok.status_code == 200 and client.get(f'{API}/auth/me').json()['id'] == c.user['id']
    client.post(f'{API}/auth/logout')
    assert client.get(f'{API}/auth/me').json() is None


def test_logout_kills_the_session_server_side(make_user):
    c = make_user()
    token = c.cookies.get('nba_session')
    c.post(f'{API}/auth/logout')
    from fastapi.testclient import TestClient
    from backend.app.main import app
    stolen = TestClient(app, cookies={'nba_session': token})      # reusing the old cookie doesn't work
    assert stolen.get(f'{API}/auth/me').json() is None


def test_login_is_rate_limited(make_user, client):
    c = make_user()
    client.cookies.clear()
    for _ in range(10):
        client.post(f'{API}/auth/login', json={'email': c.user['email'], 'password': 'wrong password!'})
    blocked = client.post(f'{API}/auth/login', json={'email': c.user['email'], 'password': c.password})
    assert blocked.status_code == 429


def test_cross_site_writes_are_blocked(make_user):
    c = make_user()
    evil = c.put(f'{API}/me/favorites/player/curryst01', headers={'Origin': 'https://evil.example'})
    assert evil.status_code == 403
    form = c.post(f'{API}/me/comparisons', content='kind=players', headers={'Content-Type': 'application/x-www-form-urlencoded'})
    assert form.status_code == 403
    same_site = c.put(f'{API}/me/favorites/player/curryst01', headers={'Origin': 'http://testserver'})
    assert same_site.status_code == 200


def test_signed_out_users_cant_write(client):
    client.cookies.clear()
    assert client.put(f'{API}/me/favorites/player/curryst01').status_code == 401
    assert client.get(f'{API}/me/lineups').status_code == 401


def test_profile_update_and_password_change(make_user):
    c = make_user()
    r = c.patch(f'{API}/auth/me', json={'display_name': 'Hoops Fan', 'bio': 'Bird > Magic', 'username': 'hoops_fan'})
    assert r.json()['username'] == 'hoops_fan' and r.json()['bio'] == 'Bird > Magic'
    assert c.post(f'{API}/auth/password', json={'current_password': 'nope nope nope', 'new_password': 'another strong one'}).status_code == 403
    assert c.post(f'{API}/auth/password', json={'current_password': c.password, 'new_password': 'another strong one'}).status_code == 200
    c.post(f'{API}/auth/logout')
    assert c.post(f'{API}/auth/login', json={'email': c.user['email'], 'password': c.password}).status_code == 401
    assert c.post(f'{API}/auth/login', json={'email': c.user['email'], 'password': 'another strong one'}).status_code == 200


def test_favorites(make_user):
    c = make_user()
    assert c.put(f'{API}/me/favorites/player/curryst01').json() == {'favorite': True}
    assert c.put(f'{API}/me/favorites/player/curryst01').status_code == 200          # idempotent
    assert c.put(f'{API}/me/favorites/team/boston-celtics').status_code == 200
    assert c.put(f'{API}/me/favorites/player/nobody00').status_code == 404
    assert c.put(f'{API}/me/favorites/team/seattle-pilots').status_code == 404
    favs = c.get(f'{API}/me/favorites').json()
    assert [p['player'] for p in favs['players']] == ['Stephen Curry']
    assert favs['teams'] == [{'slug': 'boston-celtics', 'franchise': 'Boston Celtics'}]
    c.delete(f'{API}/me/favorites/player/curryst01')
    assert c.get(f'{API}/me/favorites').json()['players'] == []


def test_saved_comparisons_and_profile(make_user, client):
    c = make_user()
    body = {'kind': 'players', 'a': 'jamesle01', 'b': 'jordami01', 'params': 'basis=index&pos=5',
            'title': 'GOAT debate', 'note': 'Year 5 era-adjusted', 'is_public': True}
    saved = c.post(f'{API}/me/comparisons', json=body).json()
    assert saved['path'] == '/compare/players/jamesle01/jordami01?basis=index&pos=5'
    private = c.post(f'{API}/me/comparisons', json={**body, 'title': 'secret', 'is_public': False}).json()
    assert c.post(f'{API}/me/comparisons', json={**body, 'params': '"><script>'}).status_code == 422
    assert c.post(f'{API}/me/comparisons', json={**body, 'a': 'nobody00'}).status_code == 404
    other = make_user()
    assert other.patch(f'{API}/me/comparisons/{saved["id"]}', json={'title': 'hacked'}).status_code == 404
    assert other.delete(f'{API}/me/comparisons/{saved["id"]}').status_code == 404
    profile = client.get(f'{API}/users/{c.user["username"]}').json()
    assert [x['title'] for x in profile['comparisons']] == ['GOAT debate']           # private one hidden
    assert 'email' not in profile['user']
    c.delete(f'{API}/me/comparisons/{private["id"]}')
    assert len(c.get(f'{API}/me/comparisons').json()) == 1


def test_delete_account_removes_everything(make_user, client):
    c = make_user()
    c.put(f'{API}/me/favorites/player/curryst01')
    lineup = c.post(f'{API}/lineups', json={'name': 'Mine', 'is_public': True, 'players': [
        {'player_id': p} for p in ('curryst01', 'jordami01', 'jamesle01', 'duncati01', 'onealsh01')]}).json()
    assert c.request('DELETE', f'{API}/auth/me', json={'password': 'wrong one'}).status_code == 403
    assert c.request('DELETE', f'{API}/auth/me', json={'password': c.password}).status_code == 204
    assert client.get(f'{API}/users/{c.user["username"]}').status_code == 404
    assert client.get(f'{API}/lineups/{lineup["id"]}').status_code == 404
    assert client.post(f'{API}/auth/login', json={'email': c.user['email'], 'password': c.password}).status_code == 401


def test_stats_reload_keeps_accounts(make_user):
    """The data loader drops and rebuilds the stats tables; accounts must survive."""
    import os
    from backend.etl.load_db import load
    c = make_user()
    c.put(f'{API}/me/favorites/player/curryst01')
    load(os.environ['DATABASE_URL'], quiet=True)
    assert c.get(f'{API}/auth/me').json()['id'] == c.user['id']
    assert c.get(f'{API}/me/favorites').json()['players'][0]['player_id'] == 'curryst01'


def test_server_loads_stats_into_an_empty_or_stale_database(tmp_path, monkeypatch):
    monkeypatch.setenv('LOAD_GAMES', '0')               # this tests reload logic; skip the big game tables
    """First run with no database, or a deploy with newer data/: the server
    loads the stats itself, and never touches accounts."""
    from sqlalchemy import insert, select, update
    from backend.app import accounts_schema as acc
    from backend.app import schema
    from backend.app.db import make_engine
    from backend.etl.load_db import ensure_loaded

    engine = make_engine(f'sqlite:///{tmp_path}/fresh.db')
    logs = []
    assert ensure_loaded(engine, log=logs.append) is True                 # empty -> loads
    assert 'empty' in logs[0]
    assert ensure_loaded(engine, log=logs.append) is False                # up to date -> no-op

    acc.account_metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(acc.users).values(username='keepme', email='keep@example.com', display_name='K', bio='', created_at=1))
        conn.execute(update(schema.meta).where(schema.meta.c.key == 'data_fingerprint').values(value='older-data'))
    assert ensure_loaded(engine, log=logs.append) is True                 # stale -> reloads
    assert 'changed' in logs[-2]
    with engine.connect() as conn:
        assert conn.execute(select(acc.users.c.username)).scalar() == 'keepme'
        assert conn.execute(select(schema.players.c.player).where(schema.players.c.player_id == 'curryst01')).scalar() == 'Stephen Curry'


def test_loader_code_change_triggers_reload(tmp_path, monkeypatch):
    monkeypatch.setenv('LOAD_GAMES', '0')
    """A database loaded by different loader code (e.g. an older version that
    didn't know about the model tables) is reloaded even if data/ is unchanged."""
    from sqlalchemy import update
    from backend.app import schema
    from backend.app.db import make_engine
    from backend.etl import load_db as ld

    engine = make_engine(f'sqlite:///{tmp_path}/old.db')
    ld.ensure_loaded(engine, log=lambda *_: None)
    real = ld.data_fingerprint()
    monkeypatch.setattr(ld, 'data_fingerprint', lambda: real + '-new-loader')   # same data, different code
    assert ld.ensure_loaded(engine, log=lambda *_: None) is True
