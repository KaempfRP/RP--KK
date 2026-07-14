"""Deduplication module using SQLite.

Tracks seen tender IDs in data/seen.db to ensure each tender
is only marked as "new" once. Also stores AI-generated summaries.
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "seen.db")


def _get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get a SQLite connection."""
    return sqlite3.connect(db_path or DB_PATH)


def init_db(db_path: str | None = None) -> None:
    """Create the seen table if it doesn't exist."""
    conn = _get_connection(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen (
                id TEXT PRIMARY KEY,
                source TEXT,
                title TEXT,
                first_seen TEXT,
                summary TEXT DEFAULT ''
            )
        """)
        conn.commit()
    finally:
        conn.close()
    _migrate_db(db_path)


def _migrate_db(db_path: str | None = None) -> None:
    """Add summary column if it doesn't exist (idempotent)."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute("PRAGMA table_info(seen)")
        columns = {row[1] for row in cursor.fetchall()}
        if "summary" not in columns:
            conn.execute("ALTER TABLE seen ADD COLUMN summary TEXT DEFAULT ''")
            conn.commit()
    finally:
        conn.close()


def filter_new(entries: list[dict], db_path: str | None = None) -> list[dict]:
    """Return only entries whose ID is not yet in the database."""
    if not entries:
        return []

    conn = _get_connection(db_path)
    try:
        cursor = conn.execute("SELECT id FROM seen")
        seen_ids = {row[0] for row in cursor.fetchall()}
        return [e for e in entries if e["id"] not in seen_ids]
    finally:
        conn.close()


def save_seen(entries: list[dict], db_path: str | None = None) -> None:
    """Persist new entry IDs with timestamp."""
    if not entries:
        return

    conn = _get_connection(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        for entry in entries:
            conn.execute(
                "INSERT OR IGNORE INTO seen (id, source, title, first_seen) VALUES (?, ?, ?, ?)",
                (entry["id"], entry.get("source", ""), entry.get("title", ""), now),
            )
        conn.commit()
    finally:
        conn.close()


def get_all_seen_ids(db_path: str | None = None) -> set[str]:
    """Return set of all known IDs."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute("SELECT id FROM seen")
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()


def get_stored_summaries(db_path: str | None = None) -> dict[str, str]:
    """Return dict of {id: summary} for all entries with a non-empty summary."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT id, summary FROM seen WHERE summary != '' AND summary IS NOT NULL"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        conn.close()


def save_summaries(summaries: dict[str, str], db_path: str | None = None) -> None:
    """Update summary column for given entry IDs."""
    if not summaries:
        return

    conn = _get_connection(db_path)
    try:
        for entry_id, summary in summaries.items():
            conn.execute(
                "UPDATE seen SET summary = ? WHERE id = ?",
                (summary, entry_id),
            )
        conn.commit()
    finally:
        conn.close()
