"""Small helpers shared by the routers."""
import unicodedata

from fastapi import HTTPException
from sqlalchemy import select


def normalize_name(name: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', name) if not unicodedata.combining(c)).lower()


def fetch_all(conn, stmt):
    return [dict(r) for r in conn.execute(stmt).mappings()]


def fetch_one(conn, stmt, not_found='Not found'):
    row = conn.execute(stmt).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail=not_found)
    return dict(row)


def as_columns(rows, columns):
    """Compact {columns, rows} form — about half the size of a list of objects."""
    return {'columns': columns, 'rows': [[r.get(c) for c in columns] for r in rows]}


def table_columns(table, exclude=()):
    return [c.name for c in table.columns if c.name not in exclude]


def by_player(conn, table, player_id, order='season'):
    """Rows for one player, by season; ties keep the source-file order."""
    cols = [table.c[order]] + ([table.c.id] if 'id' in table.c else [])
    return fetch_all(conn, select(table).where(table.c.player_id == player_id).order_by(*cols))
