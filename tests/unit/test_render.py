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


# Summary rendering tests

def test_summary_displayed_in_html(tmp_docs_dir):
    """Entries with summaries show the KI toggle button and summary text."""
    entries = [
        {
            "id": "sum-1",
            "title": "IT-Beratung SAP Migration",
            "buyer": "Stadtwerke Test",
            "published": "2025-04-01",
            "deadline": "2025-05-01",
            "url": "https://example.com/1",
            "source": "TED Europa",
        },
    ]
    import json
    summaries = {"sum-1": json.dumps({
        "chance": "Relevante IT-Beratung fuer Energieversorger.",
        "empfehlung": "IT-Projektmanager einsetzen.",
        "naechster_schritt": "Angebot vorbereiten.",
        "fit_score": 75,
    }, ensure_ascii=False)}
    render_page(entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR, summaries=summaries)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert '<button class="summary-toggle"' in html
    assert "Was wird gesucht?" in html
    assert "Empfehlung" in html
    assert "Management Summary" in html
    assert "Relevante IT-Beratung" in html
    assert "summary-card" in html
    # legacy v1 'chance' text must render via fallback
    assert "data-summary=" in html


def test_v2_summary_schema_rendered(tmp_docs_dir):
    """New structured summary schema renders and is embedded as data-summary."""
    import json
    entries = [{
        "id": "v2-1",
        "title": "IT-Beratung Beschaffungsoptimierung",
        "buyer": "Stadtwerke Test",
        "published": "2026-07-01",
        "deadline": "2026-08-01",
        "url": "https://example.com/1",
        "source": "TED Europa",
    }]
    summaries = {"v2-1": json.dumps({
        "was_gesucht": "Strategische Beschaffungsberatung fuer den Konzernverbund.",
        "handlungsfelder": ["IT-Dienstleistungen", "Prozessoptimierung"],
        "eckdaten": {"Verfahren": "Verhandlungsverfahren", "Laufzeit": "12 Monate"},
        "fristen": {"Teilnahmeantrag": "17.04.2026, 12:00 Uhr"},
        "zuschlagskriterien": [["Honorar", "30 %"], ["Umsetzungskonzept", "35 %"]],
        "eignung": ["Umsatz mind. 2,4 Mio. EUR"],
        "relevanz": "Sehr hohe thematische Relevanz.",
        "empfehlung": "IT-Einkauf und Prozessmanager anbieten.",
        "fit_score": 85,
    }, ensure_ascii=False)}
    render_page(entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR, summaries=summaries)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert "Strategische Beschaffungsberatung" in html
    assert "data-summary=" in html
    assert "Umsetzungskonzept" in html  # embedded JSON for the PDF
    assert "Sehr hohe thematische Relevanz." in html


def test_no_summary_no_toggle(sample_entries, tmp_docs_dir):
    """Entries without summaries don't show toggle button in table body."""
    render_page(sample_entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR, summaries={})

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert '<button class="summary-toggle"' not in html


def test_render_without_summaries_param(sample_entries, tmp_docs_dir):
    """render_page() works without summaries parameter (backward compat)."""
    render_page(sample_entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR)

    with open(os.path.join(tmp_docs_dir, "index.html"), encoding="utf-8") as f:
        html = f.read()

    assert "Ausschreibungs-Scout" in html
    assert '<button class="summary-toggle"' not in html


def test_ai_score_cannot_inflate_zero(tmp_docs_dir):
    """AI fit_score 75 with keyword_score 0 results in max 15."""
    import json
    entries = [{
        "id": "inflate-test",
        "title": "Holzbauarbeiten Turnhalle",
        "buyer": "Gemeinde X",
        "published": "2025-04-01",
        "deadline": "–",
        "url": "https://example.com/1",
        "source": "TED Europa",
    }]
    summaries = {"inflate-test": json.dumps({
        "chance": "Falsch positiv.",
        "empfehlung": "Keine.",
        "naechster_schritt": "Ignorieren.",
        "fit_score": 75,
    })}
    render_page(entries, set(), docs_dir=tmp_docs_dir, template_dir=TEMPLATE_DIR, summaries=summaries)
    assert entries[0]["relevance_score"] <= 15
