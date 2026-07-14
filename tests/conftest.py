"""Shared test fixtures for Tender Scout."""

import os
import tempfile

import pytest

from src.dedup import init_db


@pytest.fixture
def sample_ted_entry():
    """A valid TED entry dict."""
    return {
        "id": "TED-2024-123456",
        "title": "IT-Dienstleistungen für Energieversorger",
        "buyer": "Stadtwerke München GmbH",
        "published": "2024-11-15",
        "deadline": "2024-12-15",
        "url": "https://ted.europa.eu/notice/123456",
        "source": "TED Europa",
    }


@pytest.fixture
def sample_rss_entry():
    """A valid RSS entry dict."""
    return {
        "id": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "title": "Beratungsleistungen Energiewirtschaft",
        "buyer": "DTVP",
        "published": "2024-11-14",
        "deadline": "–",
        "url": "https://www.dtvp.de/notice/12345",
        "source": "DTVP",
    }


@pytest.fixture
def sample_entries(sample_ted_entry, sample_rss_entry):
    """A list of 3 mixed entries."""
    return [
        sample_ted_entry,
        sample_rss_entry,
        {
            "id": "bund-entry-001",
            "title": "Softwareentwicklung Netzsteuerung",
            "buyer": "Bund.de",
            "published": "2024-11-13",
            "deadline": "–",
            "url": "https://www.bund.de/notice/001",
            "source": "Bund.de",
        },
    ]


@pytest.fixture
def in_memory_db(tmp_path):
    """SQLite database in a temp directory for tests."""
    db_path = str(tmp_path / "test_seen.db")
    init_db(db_path)
    return db_path


@pytest.fixture
def tmp_docs_dir(tmp_path):
    """Temporary docs/ directory."""
    docs = tmp_path / "docs"
    docs.mkdir()
    return str(docs)
