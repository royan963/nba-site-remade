"""Loads a fresh database for the test run.

SQLite in a temp folder by default; set TEST_DATABASE_URL to run the same
tests against PostgreSQL. (Must run before backend.app.db is imported.)
"""
import os
import tempfile

import pytest

TEST_URL = os.environ.get('TEST_DATABASE_URL') or f'sqlite:///{tempfile.mkdtemp()}/test.db'
os.environ['DATABASE_URL'] = TEST_URL

from backend.app.accounts_schema import account_metadata  # noqa: E402
from backend.app.db import make_engine  # noqa: E402
from backend.etl.load_db import load  # noqa: E402

load(TEST_URL, quiet=True)
account_metadata.drop_all(make_engine(TEST_URL))     # fresh account tables for every test run


@pytest.fixture(scope='session')
def client():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def reset_rate_limits():
    from backend.app import security
    security.login_failures.events.clear()
    security.signups.events.clear()
    yield


_counter = iter(range(1, 10_000))


@pytest.fixture
def make_user(client):
    """Create an account and return a signed-in TestClient-like helper."""
    from fastapi.testclient import TestClient
    from backend.app.main import app

    def _make(password='correct horse battery', **extra):
        n = next(_counter)
        c = TestClient(app)
        body = {'email': f'fan{n}@example.com', 'username': f'fan{n}', 'password': password, **extra}
        r = c.post('/api/v1/auth/register', json=body)
        assert r.status_code == 201, r.text
        c.user = r.json()
        c.password = password
        return c
    return _make
