"""Database connection.

Set DATABASE_URL to use PostgreSQL, e.g.
    postgresql://user:password@host:5432/nba
Without it, a local SQLite file (backend/nba.db) is used, so the API runs
with no database server installed.
"""
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[1] / 'nba.db'


def database_url() -> str:
    url = os.environ.get('DATABASE_URL') or f'sqlite:///{DEFAULT_SQLITE_PATH}'
    # Hosting providers often hand out postgres:// URLs; SQLAlchemy needs a
    # driver name, and we use psycopg 3.
    if url.startswith('postgres://'):
        url = 'postgresql://' + url[len('postgres://'):]
    if url.startswith('postgresql://'):
        url = 'postgresql+psycopg://' + url[len('postgresql://'):]
    return url


def make_engine(url: str | None = None) -> Engine:
    url = url or database_url()
    kwargs = {'pool_pre_ping': True}
    if url.startswith('sqlite'):
        kwargs['connect_args'] = {'check_same_thread': False}
    engine = create_engine(url, **kwargs)
    if url.startswith('sqlite'):
        # SQLite ignores foreign keys (and ON DELETE CASCADE) unless asked.
        event.listen(engine, 'connect', lambda dbapi_conn, _: dbapi_conn.execute('PRAGMA foreign_keys=ON'))
    return engine


engine = make_engine()


def get_conn():
    """FastAPI dependency: one read connection per request."""
    with engine.connect() as conn:
        yield conn


def get_tx():
    """FastAPI dependency for writes: a transaction committed when the request
    succeeds and rolled back if it raises."""
    with engine.begin() as conn:
        yield conn


def is_sqlite() -> bool:
    return engine.dialect.name == 'sqlite'
