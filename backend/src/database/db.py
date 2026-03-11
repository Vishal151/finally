"""SQLite connection management with lazy initialization."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_DB_DIR = Path(__file__).resolve().parent.parent.parent / "db"
_SCHEMA_PATH = _DB_DIR / "schema.sql"
_SEED_PATH = _DB_DIR / "seed.sql"

_connection: sqlite3.Connection | None = None


def _get_db_path() -> Path:
    env = os.environ.get("DATABASE_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent.parent / "db" / "finally.db"


def _is_initialized(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='users_profile'"
    ).fetchone()
    return row[0] > 0


def init_db(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    """Initialize database schema and seed data. Idempotent."""
    if conn is None:
        conn = get_db()
    if not _is_initialized(conn):
        schema_sql = _SCHEMA_PATH.read_text()
        conn.executescript(schema_sql)
        seed_sql = _SEED_PATH.read_text()
        conn.executescript(seed_sql)
    return conn


def get_db() -> sqlite3.Connection:
    """Return the singleton database connection, creating it if needed."""
    global _connection
    if _connection is not None:
        return _connection

    db_path = _get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    _connection = conn
    init_db(conn)
    return conn


def close_db() -> None:
    """Close the database connection."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def reset_db() -> None:
    """Drop all tables and reinitialize. For testing only."""
    conn = get_db()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    # Re-read schema and seed
    schema_sql = _SCHEMA_PATH.read_text()
    conn.executescript(schema_sql)
    seed_sql = _SEED_PATH.read_text()
    conn.executescript(seed_sql)
