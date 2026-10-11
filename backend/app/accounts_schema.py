"""Tables for user accounts and user content.

These live in their own MetaData, separate from the stats tables in
schema.py, because the stats loader (etl/load_db.py) drops and recreates
the stats tables on every data refresh. Nothing here is ever dropped by it,
and nothing here has a database foreign key into the stats tables (player
and franchise ids are validated by the API instead) so stats reloads can't
be blocked by user data or cascade into it.

Times are stored as Unix epoch seconds so they compare the same way on
PostgreSQL and SQLite.
"""
from sqlalchemy import (Boolean, Column, ForeignKey, Index, Integer, MetaData, String, Table, Text,
                        UniqueConstraint)

account_metadata = MetaData()


def _user_fk():
    return Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)


users = Table(
    'users', account_metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('username', String(20), nullable=False, unique=True),       # lowercase, used in /u/<username>
    Column('email', String(254), nullable=False, unique=True),         # lowercase
    Column('display_name', String(60), nullable=False),
    Column('bio', String(280), nullable=False, default=''),
    Column('created_at', Integer, nullable=False),
)

# How a user signs in. Email/password is one row with provider='password';
# "Sign in with GitHub/Google" later adds rows with provider='github' etc.
# and the provider's user id, without changing the users table.
auth_identities = Table(
    'auth_identities', account_metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    _user_fk(),
    Column('provider', String(20), nullable=False),
    Column('provider_user_id', String(255), nullable=False),
    Column('secret_hash', Text),                                        # Argon2 hash for 'password'; NULL for OAuth
    Column('created_at', Integer, nullable=False),
    Column('last_used_at', Integer),
    UniqueConstraint('provider', 'provider_user_id', name='uq_identity_provider_user'),
)

# Server-side sessions. The cookie holds a random token; only its SHA-256
# is stored, so a leaked database can't be used to hijack sessions.
sessions = Table(
    'sessions', account_metadata,
    Column('token_hash', String(64), primary_key=True),
    _user_fk(),
    Column('created_at', Integer, nullable=False),
    Column('expires_at', Integer, nullable=False),
    Column('user_agent', String(200)),
)

favorites = Table(
    'favorites', account_metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    _user_fk(),
    Column('kind', String(8), nullable=False),                          # 'player' | 'team'
    Column('ref', String(64), nullable=False),                          # player_id or franchise slug
    Column('created_at', Integer, nullable=False),
    UniqueConstraint('user_id', 'kind', 'ref', name='uq_favorite'),
)

saved_comparisons = Table(
    'saved_comparisons', account_metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    _user_fk(),
    Column('kind', String(8), nullable=False),                          # 'players' | 'teams'
    Column('a', String(64), nullable=False),
    Column('b', String(64), nullable=False),
    Column('params', String(300), nullable=False, default=''),          # view settings as a query string
    Column('title', String(100), nullable=False),
    Column('note', String(1000), nullable=False, default=''),
    Column('is_public', Boolean, nullable=False, default=False),
    Column('created_at', Integer, nullable=False),
)

lineups = Table(
    'lineups', account_metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    _user_fk(),
    Column('name', String(80), nullable=False),
    Column('description', String(500), nullable=False, default=''),
    Column('is_public', Boolean, nullable=False, default=False),
    Column('overall', Integer),                                         # cached score for listings
    Column('created_at', Integer, nullable=False),
    Column('updated_at', Integer, nullable=False),
)

lineup_players = Table(
    'lineup_players', account_metadata,
    Column('lineup_id', Integer, ForeignKey('lineups.id', ondelete='CASCADE'), primary_key=True),
    Column('slot', Integer, primary_key=True),                          # 1-5
    Column('player_id', String(16), nullable=False),
    Column('season', Integer, nullable=False),
)
Index('ix_lineups_public', lineups.c.is_public, lineups.c.updated_at)
