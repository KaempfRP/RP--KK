"""End-to-end tests — full pipeline with mocked network."""

import os

import pytest

pytestmark = pytest.mark.e2e

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, "templates")


def _make_entries(source: str, count: int = 3, prefix: str = "") -> list[dict]:
    """Generate mock tender entries for a given source."""
    return [
        {
            "id": f"{prefix}{source.lower().replace('.', '')}-{i}",
            "title": f"Ausschreibung {source} Nr. {i}",
            "buyer": f"Auftraggeber {source}",
            "published": f"2024-11-{15 - i:02d}",
            "deadline": "–",
            "url": f"https://example.com/{source.lower()}/{i}",
            "source": source,
        }
        for i in range(1, count + 1)
    ]


def test_full_pipeline(tmp_path, monkeypatch):
    """Full pipeline with mocked sources produces valid HTML."""
    db_path = str(tmp_path / "e2e.db")
    docs_dir = str(tmp_path / "docs")
    os.makedirs(docs_dir, exist_ok=True)

    ted_entries = _make_entries("TED Europa")
    dtvp_entries = _make_entries("DTVP")
    nrw_entries = _make_entries("Vergabe.NRW")
    bund_entries = _make_entries("Bund.de")

    monkeypatch.setattr("src.ted_api.fetch_ted", lambda: ted_entries)
    monkeypatch.setattr(
        "src.rss_sources.fetch_rss_sources",
        lambda: dtvp_entries + nrw_entries + bund_entries,
    )
    monkeypatch.setattr("src.dedup.DB_PATH", db_path)
    monkeypatch.setattr("src.render.DOCS_DIR", docs_dir)

    from src.dedup import init_db
    init_db(db_path)

    from main import main
    main()

    html_path = os.path.join(docs_dir, "index.html")
    assert os.path.exists(html_path)

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    # At least one title visible
    assert "Ausschreibung" in html
    # NEU badge present
    assert "NEU" in html
    # Filter buttons present
    assert "filter-btn" in html
    assert "TED Europa" in html
    assert "DTVP" in html


def test_dedup_on_second_run(tmp_path, monkeypatch):
    """Second run reports 0 new entries."""
    db_path = str(tmp_path / "e2e_dedup.db")
    docs_dir = str(tmp_path / "docs")
    os.makedirs(docs_dir, exist_ok=True)

    entries = _make_entries("TED Europa", count=2)

    monkeypatch.setattr("src.ted_api.fetch_ted", lambda: entries)
    monkeypatch.setattr("src.rss_sources.fetch_rss_sources", lambda: [])
    monkeypatch.setattr("src.dedup.DB_PATH", db_path)
    monkeypatch.setattr("src.render.DOCS_DIR", docs_dir)

    from src.dedup import init_db, filter_new
    init_db(db_path)

    from main import main
    main()

    # Second run — same entries
    new_on_second = filter_new(entries, db_path=db_path)
    assert len(new_on_second) == 0


def test_resilience(tmp_path, monkeypatch):
    """One empty source doesn't prevent others from showing."""
    db_path = str(tmp_path / "e2e_resilience.db")
    docs_dir = str(tmp_path / "docs")
    os.makedirs(docs_dir, exist_ok=True)

    ted_entries = _make_entries("TED Europa", count=2)

    monkeypatch.setattr("src.ted_api.fetch_ted", lambda: [])  # TED "fails"
    monkeypatch.setattr("src.rss_sources.fetch_rss_sources", lambda: ted_entries)
    monkeypatch.setattr("src.dedup.DB_PATH", db_path)
    monkeypatch.setattr("src.render.DOCS_DIR", docs_dir)

    from src.dedup import init_db
    init_db(db_path)

    from main import main
    main()

    html_path = os.path.join(docs_dir, "index.html")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    assert "Ausschreibung" in html


def test_sorting(tmp_path):
    """Newest entries appear first in HTML."""
    docs_dir = str(tmp_path / "docs")
    os.makedirs(docs_dir, exist_ok=True)

    entries = [
        {
            "id": "old-1",
            "title": "Alte Ausschreibung",
            "buyer": "Test",
            "published": "2024-01-01",
            "deadline": "–",
            "url": "https://example.com/old",
            "source": "TED Europa",
        },
        {
            "id": "new-1",
            "title": "Neue Ausschreibung",
            "buyer": "Test",
            "published": "2024-12-01",
            "deadline": "–",
            "url": "https://example.com/new",
            "source": "TED Europa",
        },
    ]

    from src.render import render_page
    new_ids = {e["id"] for e in entries}
    render_page(entries, new_ids, docs_dir=docs_dir, template_dir=TEMPLATE_DIR)

    html_path = os.path.join(docs_dir, "index.html")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    # "Neue" should appear before "Alte" in the HTML
    pos_new = html.index("Neue Ausschreibung")
    pos_old = html.index("Alte Ausschreibung")
    assert pos_new < pos_old


def test_relevance_scoring_in_pipeline(tmp_path):
    """Full pipeline produces HTML with relevance scores."""
    docs_dir = str(tmp_path / "docs")
    os.makedirs(docs_dir, exist_ok=True)

    entries = [
        {
            "id": "high-score",
            "title": "SAP Migration Projektmanagement IT-Beratung",
            "buyer": "Stadtwerke Test",
            "published": "2024-12-01",
            "deadline": "–",
            "url": "https://example.com/1",
            "source": "TED Europa",
        },
        {
            "id": "low-score",
            "title": "Kabelverlegung Ortsnetz",
            "buyer": "Baufirma GmbH",
            "published": "2024-11-01",
            "deadline": "–",
            "url": "https://example.com/2",
            "source": "tender24.de",
        },
    ]

    from src.render import render_page
    render_page(entries, set(), docs_dir=docs_dir, template_dir=TEMPLATE_DIR)

    html_path = os.path.join(docs_dir, "index.html")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    # data-score attributes present
    assert 'data-score="' in html
    # Relevance column exists
    assert "Relevanz" in html
    # High-score entry should have a filled relevance bar
    assert "relevance-fill" in html


def test_search_and_sort_js_present(tmp_path):
    """Generated HTML contains all required JS functions."""
    docs_dir = str(tmp_path / "docs")
    os.makedirs(docs_dir, exist_ok=True)

    entries = [
        {
            "id": "js-test",
            "title": "Test Ausschreibung",
            "buyer": "Test AG",
            "published": "2024-12-01",
            "deadline": "–",
            "url": "https://example.com/1",
            "source": "TED Europa",
        },
    ]

    from src.render import render_page
    render_page(entries, set(), docs_dir=docs_dir, template_dir=TEMPLATE_DIR)

    html_path = os.path.join(docs_dir, "index.html")
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    assert "searchTable" in html
    assert "sortTable" in html
    assert "applyFilters" in html
    assert "search-input" in html
