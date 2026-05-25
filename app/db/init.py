"""Schema bootstrap — runs schema.sql every startup (idempotent CREATE IF NOT EXISTS)."""

from __future__ import annotations

from pathlib import Path

from app.db.connection import connection

_SCHEMA = Path(__file__).parent / "schema.sql"


def init_schema() -> None:
    sql = _SCHEMA.read_text()
    with connection() as conn:
        conn.executescript(sql)
        conn.commit()
