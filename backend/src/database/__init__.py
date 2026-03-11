"""Database subsystem -- SQLite with lazy initialization.

Public API:
    get_db()            -- get a connection (initializes DB on first call)
    init_db()           -- explicitly initialize (idempotent)
    queries module      -- all query functions
"""

from .db import get_db, init_db

__all__ = ["get_db", "init_db"]
