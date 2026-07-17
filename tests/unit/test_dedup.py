"""Unit tests for deduplication and persistence module."""

from src.dedup import (
    init_db, filter_new, save_seen, get_all_seen_ids, _migrate_db,
    store_entries, get_all_entries,
)


def test_filter_new_returns_all_on_empty_db(in_memory_db, sample_entries):
    """On empty DB, all entries are new."""
    result = filter_new(sample_entries, db_path=in_memory_db)
    assert len(result) == len(sample_entries)


def test_filter_new_removes_known_ids(in_memory_db, sample_entries):
    """Known IDs are filtered out."""
    save_seen(sample_entries[:1], db_path=in_memory_db)

    result = filter_new(sample_entries, db_path=in_memory_db)
    assert len(result) == len(sample_entries) - 1
    assert sample_entries[0] not in result


def test_save_seen_persists_entries(in_memory_db, sample_entries):
    """Saved entries appear in get_all_seen_ids."""
    save_seen(sample_entries, db_path=in_memory_db)

    seen_ids = get_all_seen_ids(db_path=in_memory_db)
    for entry in sample_entries:
        assert entry["id"] in seen_ids


def test_no_duplicates_after_double_save(in_memory_db, sample_entries):
    """Saving the same entries twice doesn't create duplicates."""
    save_seen(sample_entries, db_path=in_memory_db)
    save_seen(sample_entries, db_path=in_memory_db)

    seen_ids = get_all_seen_ids(db_path=in_memory_db)
    assert len(seen_ids) == len(sample_entries)


def test_migrate_adds_summary_column(tmp_path):
    """Migration adds summary column to existing DB without it."""
    import sqlite3
    db_path = str(tmp_path / "migrate_test.db")
    # Create table WITHOUT summary column (old schema)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE seen (id TEXT PRIMARY KEY, source TEXT, title TEXT, first_seen TEXT)")
    conn.execute("INSERT INTO seen VALUES ('t1', 'TED', 'Test', '2025-01-01')")
    conn.commit()
    conn.close()

    _migrate_db(db_path)

    # Verify column exists by updating it
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE seen SET summary = 'Test summary' WHERE id = 't1'")
    conn.commit()
    row = conn.execute("SELECT summary FROM seen WHERE id = 't1'").fetchone()
    conn.close()
    assert row[0] == "Test summary"


# --- Full-entry persistence (page shows all open tenders) ---

def _entry(eid, **kw):
    base = {
        "id": eid, "title": "IT-Beratung", "buyer": "Stadtwerke Test",
        "published": "2026-07-11", "deadline": "2026-08-10",
        "url": "https://example.com/" + eid, "source": "oeffentlichevergabe.de",
        "cpv": ["72000000"],
    }
    base.update(kw)
    return base


def test_store_and_get_all_entries_roundtrip(in_memory_db):
    """Stored entries come back with full data."""
    store_entries([_entry("e1"), _entry("e2", buyer="EnBW")], db_path=in_memory_db)
    entries = {e["id"]: e for e in get_all_entries(db_path=in_memory_db)}
    assert set(entries) == {"e1", "e2"}
    assert entries["e2"]["buyer"] == "EnBW"
    assert entries["e1"]["deadline"] == "2026-08-10"
    assert "first_seen" in entries["e1"]


def test_get_all_entries_persists_across_runs(in_memory_db):
    """A tender stored earlier is still returned when a later fetch does not include it."""
    store_entries([_entry("old-open")], db_path=in_memory_db)   # run 1
    store_entries([_entry("fresh")], db_path=in_memory_db)      # run 2, different fetch
    ids = {e["id"] for e in get_all_entries(db_path=in_memory_db)}
    assert ids == {"old-open", "fresh"}


def test_store_entries_refreshes_data_keeps_first_seen(in_memory_db):
    """Re-storing updates the payload but preserves first_seen."""
    store_entries([_entry("e1", deadline="2026-08-10")], db_path=in_memory_db)
    first = get_all_entries(db_path=in_memory_db)[0]["first_seen"]
    store_entries([_entry("e1", deadline="2026-09-01")], db_path=in_memory_db)
    after = get_all_entries(db_path=in_memory_db)[0]
    assert after["deadline"] == "2026-09-01"       # refreshed
    assert after["first_seen"] == first             # preserved


def test_store_entries_preserves_summary(in_memory_db):
    """Re-storing an entry does not wipe the legacy summary column."""
    import sqlite3
    store_entries([_entry("e1")], db_path=in_memory_db)

    conn = sqlite3.connect(in_memory_db)
    conn.execute("UPDATE seen SET summary = 'Ein Summary.' WHERE id = 'e1'")
    conn.commit()
    conn.close()

    store_entries([_entry("e1", deadline="2026-09-01")], db_path=in_memory_db)

    conn = sqlite3.connect(in_memory_db)
    row = conn.execute("SELECT summary FROM seen WHERE id = 'e1'").fetchone()
    conn.close()
    assert row[0] == "Ein Summary."


def test_migrate_adds_data_column(tmp_path):
    """Migration adds the data column to an old-schema DB."""
    import sqlite3
    db_path = str(tmp_path / "migrate_data.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE seen (id TEXT PRIMARY KEY, source TEXT, title TEXT, first_seen TEXT, summary TEXT DEFAULT '')")
    conn.execute("INSERT INTO seen (id) VALUES ('t1')")
    conn.commit()
    conn.close()

    _migrate_db(db_path)
    store_entries([_entry("t2")], db_path=db_path)
    ids = {e["id"] for e in get_all_entries(db_path=db_path)}
    assert "t2" in ids            # new row with data works
    assert "t1" not in ids        # old row without data is skipped, not crashing
