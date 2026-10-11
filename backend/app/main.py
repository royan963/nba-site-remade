"""NBA History API.

Run locally (from the repo root):
    python -m backend.etl.load_db              # build the database once
    (cd frontend && npm install && npm run build)
    uvicorn backend.app.main:app --reload
Then open http://localhost:8000 for the site and /docs for the API.
"""
import os
from pathlib import Path

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from . import accounts_schema
from .db import engine, is_sqlite
from .routers import auth, awards, compare, games, league, lineups, me, players, playoffs, search, teams
from .security import check_request_origin

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = Path(os.environ.get('WEB_DIR', ROOT / 'frontend' / 'dist')).resolve()

app = FastAPI(
    title='NBA History API',
    version='1.0.0',
    description='Eighty seasons of NBA stats (1947-present): players, teams, honors, '
                'shot profiles, similar players and era-adjusted comparisons.',
)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get('CORS_ORIGINS', '*').split(',')],
    allow_methods=['GET'],     # cross-origin access is read-only; accounts are same-site only
    allow_headers=['*'],
)

@app.middleware('http')
async def block_cross_site_writes(request: Request, call_next):
    reason = check_request_origin(request)
    if reason:
        return JSONResponse({'detail': reason}, status_code=403)
    return await call_next(request)


for r in (players.router, teams.router, league.router, compare.router, awards.router, search.router, playoffs.router, games.router, auth.router, me.router, lineups.router):
    app.include_router(r, prefix='/api/v1')


@app.on_event('startup')
def prepare_database():
    # Load the stats automatically if the database is empty or older than
    # data/ (first run, or a deploy with new data). Turn off with AUTO_LOAD_DATA=0
    # if you'd rather run `python -m backend.etl.load_db` yourself.
    if os.environ.get('AUTO_LOAD_DATA', '1') != '0':
        from backend.etl.load_db import ensure_loaded
        ensure_loaded(engine, log=logging.getLogger('uvicorn.error').info)
    elif not inspect(engine).has_table('meta'):
        logging.getLogger('uvicorn.error').error(
            'The stats database is empty. Run `python -m backend.etl.load_db` (with the same Python as the server).')
    create_account_tables()


def create_account_tables():
    # Account tables are created if missing and never dropped (stats reloads
    # only touch the stats tables). Add Alembic migrations before changing them.
    accounts_schema.account_metadata.create_all(engine)
    if is_sqlite() and os.environ.get('RENDER'):
        logging.getLogger('uvicorn.error').warning(
            'Accounts are stored in SQLite inside the container and will be lost on the next deploy. '
            'Set DATABASE_URL to a PostgreSQL database to keep them.')


@app.get('/api/health', tags=['meta'], summary='Liveness and database check')
def health():
    with engine.connect() as conn:
        latest = conn.execute(text("SELECT value FROM meta WHERE key = 'latest_season'")).scalar()
    return {'status': 'ok', 'database': engine.dialect.name, 'latest_season': int(latest)}


# Serve the React app (frontend/dist, built with `npm run build`). Registered
# last so API routes win. Any other path returns index.html, so deep links
# like /players/curryst01 load the app, which then routes client-side.
if (WEB_DIR / 'index.html').exists():
    if (WEB_DIR / 'assets').is_dir():
        app.mount('/assets', StaticFiles(directory=WEB_DIR / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path.startswith('api/'):
            raise HTTPException(404, 'Not found')
        file = (WEB_DIR / path).resolve()
        if path and file.is_file() and WEB_DIR in file.parents:
            return FileResponse(file)
        return FileResponse(WEB_DIR / 'index.html', headers={'Cache-Control': 'no-cache'})
