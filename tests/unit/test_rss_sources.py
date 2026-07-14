"""Unit tests for tender24.de energy sector scraper."""

from unittest.mock import patch, MagicMock

from src.rss_sources import (
    fetch_tender24,
    fetch_rss_sources,
    _make_id,
)


MOCK_TENDER24_HTML = """
<html><body>
<table>
<thead><tr><th>Datum</th></tr></thead>
<tr class="tableRow clickable-row publicationDetail" data-oid="abc-123" data-category="InvitationToTender">
  <td>07.04.2025</td>
  <td class="tender">UW Spitziger Berg (EnBW-2026-0022)</td>
  <td class="tenderAuthority">EnBW Energie Baden-Württemberg AG</td>
  <td class="tenderType">Offenes Verfahren</td>
  <td class="tenderType">VgV</td>
  <td class="tenderDeadline">30.04.2025</td>
</tr>
<tr class="tableRow clickable-row publicationDetail" data-oid="def-456" data-category="InvitationToTender">
  <td>06.04.2025</td>
  <td class="tender">IT-Plattform Netzsteuerung</td>
  <td class="tenderAuthority">EnBW Energie Baden-Württemberg AG</td>
  <td class="tenderType">Offenes Verfahren</td>
  <td class="tenderType">VgV</td>
  <td class="tenderDeadline">28.04.2025</td>
</tr>
</table>
</body></html>
"""

MOCK_EMPTY_HTML = "<html><body><table></table></body></html>"


@patch("src.rss_sources._scrape_tender24_search")
def test_fetch_tender24_returns_list(mock_scrape):
    """fetch_tender24() returns a list of dicts."""
    mock_scrape.return_value = [
        {
            "id": "abc123",
            "title": "UW Spitziger Berg",
            "buyer": "EnBW Energie Baden-Württemberg AG",
            "published": "07.04.2025",
            "deadline": "30.04.2025",
            "url": "https://www.tender24.de/NetServer/Detail?Publication=abc-123",
            "source": "tender24.de",
        }
    ]

    result = fetch_tender24()
    assert isinstance(result, list)
    assert len(result) >= 1
    assert result[0]["source"] == "tender24.de"


@patch("src.rss_sources._scrape_tender24_search")
def test_fetch_deduplicates_across_searches(mock_scrape):
    """Same entry from different searches is only included once."""
    entry = {
        "id": "same-id",
        "title": "Test",
        "buyer": "EnBW",
        "published": "07.04.2025",
        "deadline": "–",
        "url": "https://example.com",
        "source": "tender24.de",
    }
    mock_scrape.return_value = [entry]

    result = fetch_tender24()
    ids = [e["id"] for e in result]
    assert ids.count("same-id") == 1


@patch("src.rss_sources._scrape_tender24_search")
def test_failed_search_doesnt_crash(mock_scrape):
    """A failed search returns empty list without crashing others."""
    mock_scrape.side_effect = Exception("Network error")

    result = fetch_tender24()
    assert result == []


@patch("src.rss_sources.requests.get")
def test_scrape_parses_html_correctly(mock_get):
    """HTML table rows are parsed into correct entry format."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = MOCK_TENDER24_HTML
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    from src.rss_sources import _scrape_tender24_search
    result = _scrape_tender24_search("EnBW")

    assert len(result) == 2
    assert result[0]["buyer"] == "EnBW Energie Baden-Württemberg AG"
    assert result[0]["source"] == "tender24.de"

    required_fields = {"id", "title", "buyer", "published", "deadline", "url", "source"}
    assert required_fields.issubset(result[0].keys())


@patch("src.rss_sources.requests.get")
def test_scrape_empty_page(mock_get):
    """Empty search results return empty list."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = MOCK_EMPTY_HTML
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    from src.rss_sources import _scrape_tender24_search
    result = _scrape_tender24_search("NonexistentCompany")
    assert result == []


@patch("src.rss_sources._scrape_tender24_search")
def test_fetch_rss_sources_calls_tender24(mock_scrape):
    """fetch_rss_sources delegates to fetch_tender24."""
    mock_scrape.return_value = []

    result = fetch_rss_sources()
    assert isinstance(result, list)
    assert mock_scrape.called


def test_id_is_consistent():
    """Same URL produces the same ID."""
    url = "https://example.com/tender/42"
    id1 = _make_id(url)
    id2 = _make_id(url)
    assert id1 == id2
    assert isinstance(id1, str)
    assert len(id1) == 32  # MD5 hex digest
