"""Unit tests for HTML renderer."""

import os

from src.render import render_page, normalize_date_for_sort

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "templates")


def test_index_html_created(sample_entries, tmp_docs_dir):
    """index.html is created after render_page()."""
    render_page(sample_entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR)

    assert os.path.exists(os.path.join(tmp_docs_dir, "index.html"))


def test_contains_title(sample_entries, tmp_docs_dir):
    """The page contains the main title."""
    render_page(sample_entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert "Ausschreibungs-Scout" in html


def test_neu_badge_present(sample_entries, tmp_docs_dir):
    """NEU badge appears for new entries."""
    new_ids = {sample_entries[0]["id"]}
    render_page(sample_entries, new_ids, docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert "NEU" in html


def test_no_badge_for_old(sample_entries, tmp_docs_dir):
    """No NEU badge when no entries are new."""
    render_page(sample_entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert '<span class="badge-neu">' not in html


def test_relevance_column_present(sample_entries, tmp_docs_dir):
    """Generated HTML contains the Relevanz column header."""
    render_page(sample_entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert "Relevanz" in html


def test_data_score_attribute(sample_entries, tmp_docs_dir):
    """Each row has a data-score attribute."""
    render_page(sample_entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert "data-score=" in html


def test_data_published_attribute(sample_entries, tmp_docs_dir):
    """Each row has a data-published attribute in ISO format."""
    render_page(sample_entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert "data-published=" in html


def test_search_input_present(sample_entries, tmp_docs_dir):
    """Generated HTML contains the search input."""
    render_page(sample_entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert "search-input" in html


def test_sort_buttons_present(sample_entries, tmp_docs_dir):
    """Generated HTML contains sort buttons for date and relevance."""
    render_page(sample_entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert 'data-sort="date"' in html
    assert 'data-sort="relevance"' in html


# Date normalization tests

def test_normalize_iso_date():
    """ISO date stays as ISO."""
    assert normalize_date_for_sort("2026-04-04") == "2026-04-04 00:00"


def test_normalize_iso_with_timezone():
    """ISO date with timezone offset is normalized."""
    result = normalize_date_for_sort("2026-04-04+02:00")
    assert result.startswith("2026-04-04")


def test_normalize_rfc2822():
    """RFC 2822 date is converted to ISO."""
    result = normalize_date_for_sort("Tue, 7 Apr 2026 12:53:00 +0200")
    assert result.startswith("2026-04-07")


def test_normalize_german_date():
    """German DD.MM.YYYY format is converted."""
    assert normalize_date_for_sort("07.04.2025") == "2025-04-07 00:00"


def test_normalize_dash_fallback():
    """Dash returns epoch fallback for sorting last."""
    assert normalize_date_for_sort("–") == "1970-01-01 00:00"
