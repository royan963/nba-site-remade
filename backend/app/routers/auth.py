"""Account endpoints: sign up, sign in/out, profile settings, password, deletion."""
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update

from .. import accounts_schema as a
from .. import security as sec
from ..db import get_tx

router = APIRouter(prefix='/auth', tags=['accounts'])


class SignUp(BaseModel):
    email: str = Field(max_length=254)
    username: str = Field(max_length=40)
    password: str = Field(max_length=200)
    display_name: str | None = Field(None, max_length=60)


class SignIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=60)
    bio: str | None = Field(None, max_length=280)
    username: str | None = Field(None, max_length=40)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)


class Confirm(BaseModel):
    password: str = Field(max_length=200)


def public_user(u: dict) -> dict:
    return {'id': u['id'], 'username': u['username'], 'display_name': u['display_name'], 'bio': u['bio'],
            'created_at': u['created_at']}


def me_payload(u: dict) -> dict:
    return {**public_user(u), 'email': u['email']}


def password_identity(conn, user_id: int):
    return conn.execute(select(a.auth_identities).where(
        a.auth_identities.c.user_id == user_id, a.auth_identities.c.provider == 'password')).mappings().first()


@router.post('/register', status_code=201, summary='Create an account (and sign in)')
def register(body: SignUp, request: Request, response: Response, conn=Depends(get_tx)):
    ip = sec.client_ip(request)
    if sec.signups.blocked(f'ip:{ip}'):
        raise HTTPException(429, 'Too many new accounts from this network. Try again later.')
    email, username = sec.clean_email(body.email), sec.clean_username(body.username)
    sec.check_password_strength(body.password, email=email, username=username)
    if conn.execute(select(a.users.c.id).where(a.users.c.email == email)).first():
        raise HTTPException(409, 'An account with that email already exists. Sign in instead.')
    if conn.execute(select(a.users.c.id).where(a.users.c.username == username)).first():
        raise HTTPException(409, 'That username is taken.')
    now = int(time.time())
    display = (body.display_name or '').strip() or username
    user_id = conn.execute(a.users.insert().values(
        username=username, email=email, display_name=display, bio='', created_at=now)).inserted_primary_key[0]
    conn.execute(a.auth_identities.insert().values(
        user_id=user_id, provider='password', provider_user_id=email,
        secret_hash=sec.hash_password(body.password), created_at=now, last_used_at=now))
    sec.signups.hit(f'ip:{ip}')
    sec.start_session(conn, response, request, user_id)
    return me_payload(conn.execute(select(a.users).where(a.users.c.id == user_id)).mappings().one())


@router.post('/login', summary='Sign in with email and password')
def login(body: SignIn, request: Request, response: Response, conn=Depends(get_tx)):
    email = (body.email or '').strip().lower()
    keys = (f'ip:{sec.client_ip(request)}', f'email:{email}')
    if sec.login_failures.blocked(*keys):
        raise HTTPException(429, 'Too many attempts. Wait a few minutes and try again.')
    ident = conn.execute(select(a.auth_identities).where(
        a.auth_identities.c.provider == 'password', a.auth_identities.c.provider_user_id == email)).mappings().first()
    if not sec.verify_password(ident['secret_hash'] if ident else None, body.password):
        sec.login_failures.hit(*keys)
        raise HTTPException(401, 'Incorrect email or password.')
    sec.login_failures.reset(f'email:{email}')
    values = {'last_used_at': int(time.time())}
    if sec.needs_rehash(ident['secret_hash']):
        values['secret_hash'] = sec.hash_password(body.password)
    conn.execute(update(a.auth_identities).where(a.auth_identities.c.id == ident['id']).values(**values))
    sec.start_session(conn, response, request, ident['user_id'])
    return me_payload(conn.execute(select(a.users).where(a.users.c.id == ident['user_id'])).mappings().one())


@router.post('/logout', status_code=204, summary='Sign out (this device)')
def logout(request: Request, response: Response, conn=Depends(get_tx)):
    sec.end_session(conn, response, request)
    response.status_code = 204


@router.get('/me', summary='The signed-in user, or null')
def me(user=Depends(sec.current_user)):
    return me_payload(user) if user else None


@router.patch('/me', summary='Update display name, bio or username')
def update_me(body: ProfileUpdate, user=Depends(sec.require_user), conn=Depends(get_tx)):
    values = {}
    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(422, 'Display name can\'t be empty.')
        values['display_name'] = name
    if body.bio is not None:
        values['bio'] = body.bio.strip()
    if body.username is not None and body.username.strip().lower() != user['username']:
        username = sec.clean_username(body.username)
        if conn.execute(select(a.users.c.id).where(a.users.c.username == username)).first():
            raise HTTPException(409, 'That username is taken.')
        values['username'] = username
    if values:
        conn.execute(update(a.users).where(a.users.c.id == user['id']).values(**values))
    return me_payload(conn.execute(select(a.users).where(a.users.c.id == user['id'])).mappings().one())


@router.post('/password', summary='Change password (signs out other devices)')
def change_password(body: PasswordChange, request: Request, user=Depends(sec.require_user), conn=Depends(get_tx)):
    ident = password_identity(conn, user['id'])
    if not ident or not sec.verify_password(ident['secret_hash'], body.current_password):
        raise HTTPException(403, 'Your current password is incorrect.')
    sec.check_password_strength(body.new_password, email=user['email'], username=user['username'])
    conn.execute(update(a.auth_identities).where(a.auth_identities.c.id == ident['id'])
                 .values(secret_hash=sec.hash_password(body.new_password)))
    sec.end_other_sessions(conn, request, user['id'])
    return {'ok': True}


@router.delete('/me', status_code=204, summary='Delete your account and everything you saved')
def delete_me(body: Confirm, request: Request, response: Response, user=Depends(sec.require_user), conn=Depends(get_tx)):
    ident = password_identity(conn, user['id'])
    if not ident or not sec.verify_password(ident['secret_hash'], body.password):
        raise HTTPException(403, 'Password is incorrect.')
    conn.execute(delete(a.users).where(a.users.c.id == user['id']))     # cascades to everything they own
    response.delete_cookie(sec.SESSION_COOKIE, path='/')
    response.status_code = 204


@router.get('/username-available', summary='Check whether a username is free')
def username_available(username: str, conn=Depends(get_tx)):
    try:
        name = sec.clean_username(username)
    except HTTPException as e:
        return {'available': False, 'reason': e.detail}
    taken = conn.execute(select(func.count()).select_from(a.users).where(a.users.c.username == name)).scalar()
    return {'available': not taken, 'reason': 'That username is taken.' if taken else None}
