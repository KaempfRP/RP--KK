"""Unit tests for deduplication module."""

from src.dedup import (
    init_db, filter_new, save_seen, get_all_seen_ids,
    get_stored_summaries, save_summaries, _migrate_db,
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


def test_get_stored_summaries_empty(in_memory_db):
    """Empty DB returns empty dict."""
    result = get_stored_summaries(in_memory_db)
    assert result == {}


def test_get_stored_summaries_returns_nonempty(in_memory_db, sample_entries):
    """Returns only entries with non-empty summaries."""
    save_seen(sample_entries, in_memory_db)
    save_summaries({"TED-2024-123456": "Ein Summary."}, in_memory_db)

    result = get_stored_summaries(in_memory_db)
    assert result == {"TED-2024-123456": "Ein Summary."}


def test_save_summaries_updates_existing(in_memory_db, sample_entries):
    """Summary is written to an existing seen entry."""
    save_seen(sample_entries, in_memory_db)
    save_summaries({"TED-2024-123456": "Summary text."}, in_memory_db)

    result = get_stored_summaries(in_memory_db)
    assert result["TED-2024-123456"] == "Summary text."


def test_save_summaries_empty_dict(in_memory_db):
    """Empty dict is a no-op, no crash."""
    save_summaries({}, in_memory_db)
