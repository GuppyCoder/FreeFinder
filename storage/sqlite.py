"""SQLite storage helpers for FreeFinder."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from models import Item

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL,
    description TEXT,
    location TEXT,
    posted_at TEXT,
    price REAL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

MAX_ITEM_AGE = timedelta(days=7)


def init_db(db_path: str = "freefinder.db") -> sqlite3.Connection:
    path = Path(db_path)
    connection = sqlite3.connect(path)
    # These pragma statements enable performance-friendly defaults for small apps.
    connection.execute("PRAGMA journal_mode=WAL;")
    connection.execute("PRAGMA synchronous=NORMAL;")
    connection.execute(SCHEMA)
    connection.commit()
    return connection


def purge_stale_items(connection: sqlite3.Connection, *, max_age: timedelta = MAX_ITEM_AGE) -> int:
    """
    Remove records older than the configured age threshold.

    Returns the number of rows deleted.
    """
    threshold_iso = (datetime.now(timezone.utc) - max_age).isoformat()
    with connection:
        # Listings without a timestamp are treated as stale because we cannot trust them.
        cursor = connection.execute(
            "DELETE FROM items WHERE posted_at IS NULL OR posted_at < ?",
            (threshold_iso,),
        )
    return cursor.rowcount


def upsert_items(connection: sqlite3.Connection, items: Iterable[Item]) -> int:
    sql = """
    INSERT INTO items (id, title, url, source, description, location, posted_at, price)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        title=excluded.title,
        url=excluded.url,
        source=excluded.source,
        description=excluded.description,
        location=excluded.location,
        posted_at=excluded.posted_at,
        price=excluded.price;
    """
    rows = [item.as_row() for item in items]
    if not rows:
        return 0
    with connection:
        # executemany will insert or update every row in a single transaction.
        connection.executemany(sql, rows)
    return len(rows)
