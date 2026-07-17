"""Deduplication and persistence module using SQLite.

Tracks seen tenders in data/seen.db so each tender is only marked
"new" once and — since the page is no longer a rolling window —
persists the full entry data so a tender stays visible until its
deadline passes, regardless of when it was published or which fetch
window caught it.

Die Spalte `summary` stammt aus der entfernten KI-Zusammenfassung. Sie
bleibt bestehen, weil ein Entfernen die vorhandene seen.db migrieren
muesste; sie wird nur noch mitgeschleppt, nie gelesen.
"""

import json
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
                summary TEXT DEFAULT '',
                data TEXT DEFAULT ''
            )
        """)
        conn.commit()
    finally:
        conn.close()
    _migrate_db(db_path)


def _migrate_db(db_path: str | None = None) -> None:
    """Add missing columns to existing DBs (idempotent)."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute("PRAGMA table_info(seen)")
        columns = {row[1] for row in cursor.fetchall()}
        if "summary" not in columns:
            conn.execute("ALTER TABLE seen ADD COLUMN summary TEXT DEFAULT ''")
        if "data" not in columns:
            # Full entry JSON, so the page can show all open tenders
            conn.execute("ALTER TABLE seen ADD COLUMN data TEXT DEFAULT ''")
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


def store_entries(entries: list[dict], db_path: str | None = None) -> None:
    """Persist the full data of all fetched entries (insert new, refresh existing).

    Preserves first_seen and the summary column; only the JSON payload,
    source and title are refreshed so re-fetched tenders get up-to-date
    deadlines etc. This is what lets the page show every open tender,
    not just the current fetch window.
    """
    if not entries:
        return

    conn = _get_connection(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        for entry in entries:
            payload = json.dumps(entry, ensure_ascii=False)
            conn.execute(
                "INSERT OR IGNORE INTO seen (id, source, title, first_seen, data) "
                "VALUES (?, ?, ?, ?, ?)",
                (entry["id"], entry.get("source", ""), entry.get("title", ""), now, payload),
            )
            conn.execute(
                "UPDATE seen SET data = ?, source = ?, title = ? WHERE id = ?",
                (payload, entry.get("source", ""), entry.get("title", ""), entry["id"]),
            )
        conn.commit()
    finally:
        conn.close()


def get_all_entries(db_path: str | None = None) -> list[dict]:
    """Return all stored entries (with full data) as entry dicts.

    Rows from the old schema without a data payload are skipped — they
    carry no deadline/buyer and will be repopulated once re-fetched.
    """
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT id, data, first_seen FROM seen WHERE data IS NOT NULL AND data != ''"
        )
        entries = []
        for entry_id, data, first_seen in cursor.fetchall():
            try:
                entry = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue
            entry["id"] = entry_id
            entry["first_seen"] = first_seen
            entries.append(entry)
        return entries
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


