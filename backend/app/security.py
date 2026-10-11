"""Passwords, sessions and request protections.

- Passwords: Argon2id (argon2-cffi defaults), with a length policy and a
  short blocklist of the most common passwords.
- Sessions: a random 256-bit token in an HttpOnly, SameSite=Lax cookie;
  only its SHA-256 is stored. 30-day lifetime; logout deletes the row.
- Cross-site requests: state-changing requests must be JSON and, when the
  browser sends an Origin header, come from this site (or TRUSTED_ORIGINS).
- Guessing: failed logins are rate limited per IP and per email (in memory,
  so per server process).
"""
import hashlib
import os
import re
import secrets
import time
from collections import defaultdict, deque

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select

from . import accounts_schema as a
from .db import get_conn

SESSION_COOKIE = 'nba_session'
SESSION_DAYS = 30
_hasher = PasswordHasher()
# Verified against when the email doesn't exist, so "no such user" and
# "wrong password" take the same time.
_DUMMY_HASH = _hasher.hash('not-a-real-password-' + secrets.token_hex(8))

COMMON_PASSWORDS = {
    'password', 'password1', 'password123', '12345678', '123456789', '1234567890', 'qwerty123', 'qwertyuiop',
    '11111111', '00000000', 'iloveyou', 'abc12345', 'letmein1', 'welcome1', 'basketball', 'football',
    'baseball', 'sunshine', 'princess', 'trustno1', 'superman', 'michaeljordan', 'lebronjames', 'admin123',
}
USERNAME_RE = re.compile(r'^[a-z0-9_]{3,20}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
RESERVED_USERNAMES = {'admin', 'api', 'me', 'login', 'signup', 'settings', 'account', 'lineups', 'docs', 'support'}


# ---- validation ----------------------------------------------------------------
def clean_email(email: str) -> str:
    email = (email or '').strip().lower()
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise HTTPException(422, 'Enter a valid email address.')
    return email


def clean_username(username: str) -> str:
    username = (username or '').strip().lower()
    if not USERNAME_RE.match(username):
        raise HTTPException(422, 'Usernames are 3-20 characters: lowercase letters, numbers and underscores.')
    if username in RESERVED_USERNAMES:
        raise HTTPException(422, 'That username is reserved.')
    return username


def check_password_strength(password: str, *, email: str = '', username: str = ''):
    if not isinstance(password, str) or len(password) < 10:
        raise HTTPException(422, 'Passwords need at least 10 characters.')
    if len(password) > 128:
        raise HTTPException(422, 'Passwords can be at most 128 characters.')
    low = password.lower()
    if low in COMMON_PASSWORDS or low in {email.lower(), username.lower(), email.split('@')[0].lower()}:
        raise HTTPException(422, 'That password is too easy to guess.')


# ---- passwords ------------------------------------------------------------------
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


# ---- sessions --------------------------------------------------------------------
def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _secure_cookie(request: Request) -> bool:
    if os.environ.get('COOKIE_SECURE') in ('0', '1'):
        return os.environ['COOKIE_SECURE'] == '1'
    return request.url.scheme == 'https'


def start_session(conn, response: Response, request: Request, user_id: int):
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    conn.execute(a.sessions.insert().values(
        token_hash=_token_hash(token), user_id=user_id, created_at=now,
        expires_at=now + SESSION_DAYS * 86400, user_agent=(request.headers.get('user-agent') or '')[:200]))
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_DAYS * 86400, httponly=True,
                        samesite='lax', secure=_secure_cookie(request), path='/')


def end_session(conn, response: Response, request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        conn.execute(delete(a.sessions).where(a.sessions.c.token_hash == _token_hash(token)))
    response.delete_cookie(SESSION_COOKIE, path='/', httponly=True, samesite='lax', secure=_secure_cookie(request))


def end_other_sessions(conn, request: Request, user_id: int):
    keep = _token_hash(request.cookies.get(SESSION_COOKIE, ''))
    conn.execute(delete(a.sessions).where(a.sessions.c.user_id == user_id, a.sessions.c.token_hash != keep))


def current_user(request: Request, conn=Depends(get_conn)) -> dict | None:
    """The signed-in user, or None."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    row = conn.execute(
        select(a.users).join(a.sessions, a.sessions.c.user_id == a.users.c.id)
        .where(a.sessions.c.token_hash == _token_hash(token), a.sessions.c.expires_at > int(time.time()))
    ).mappings().first()
    return dict(row) if row else None


def require_user(user=Depends(current_user)) -> dict:
    if user is None:
        raise HTTPException(401, 'Sign in to do that.')
    return user


# ---- cross-site request protection ------------------------------------------------------
UNSAFE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}


def trusted_origins() -> set[str]:
    return {o.strip().rstrip('/') for o in os.environ.get('TRUSTED_ORIGINS', '').split(',') if o.strip()}


def check_request_origin(request: Request) -> str | None:
    """Reason to reject a state-changing API request, or None if it's fine."""
    if request.method not in UNSAFE_METHODS or not request.url.path.startswith('/api/'):
        return None
    origin = request.headers.get('origin')
    if origin:
        own = f'{request.url.scheme}://{request.headers.get("host", "")}'
        if origin.rstrip('/') not in {own, *trusted_origins()}:
            return 'Cross-site request blocked.'
    # Requiring JSON means a plain HTML form on another site can't submit here.
    if request.method in {'POST', 'PUT', 'PATCH'} and int(request.headers.get('content-length') or 0) > 0:
        if not request.headers.get('content-type', '').startswith('application/json'):
            return 'Send JSON (Content-Type: application/json).'
    return None


# ---- rate limiting -------------------------------------------------------------------------
class RateLimiter:
    """Sliding-window counter: at most `limit` events per `window` seconds per key."""

    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self.events: dict[str, deque] = defaultdict(deque)

    def _trim(self, key: str, now: float):
        q = self.events[key]
        while q and q[0] <= now - self.window:
            q.popleft()
        return q

    def blocked(self, *keys: str) -> bool:
        now = time.monotonic()
        return any(len(self._trim(k, now)) >= self.limit for k in keys)

    def hit(self, *keys: str):
        now = time.monotonic()
        for k in keys:
            self._trim(k, now).append(now)

    def reset(self, *keys: str):
        for k in keys:
            self.events.pop(k, None)


login_failures = RateLimiter(limit=10, window=15 * 60)     # failed logins per IP / per email
signups = RateLimiter(limit=20, window=60 * 60)             # new accounts per IP


def client_ip(request: Request) -> str:
    # Behind a proxy (Render), uvicorn runs with --proxy-headers so this is the
    # real client address. X-Forwarded-For isn't read directly: it's spoofable.
    return request.client.host if request.client else 'unknown'
