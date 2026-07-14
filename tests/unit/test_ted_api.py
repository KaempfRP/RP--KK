"""Unit tests for TED API connector."""

from unittest.mock import patch, MagicMock

import requests

from src.ted_api import fetch_ted


MOCK_TED_RESPONSE = {
    "notices": [
        {
            "publication-number": "TED-2024-999",
            "notice-title": {"deu": "IT-Beratung Energie"},
            "buyer-name": {"deu": ["Stadtwerke Test GmbH"]},
            "publication-date": "2024-11-15+01:00",
            "deadline-receipt-tender-date-lot": ["2024-12-15+01:00"],
            "classification-cpv": ["72000000"],
            "notice-type": "cn-standard",
            "buyer-country": "DEU",
            "links": {
                "html": {
                    "DEU": "https://ted.europa.eu/de/notice/-/detail/TED-2024-999",
                    "ENG": "https://ted.europa.eu/en/notice/-/detail/TED-2024-999",
                }
            },
        }
    ]
}


@patch("src.ted_api.requests.post")
def test_fetch_returns_list(mock_post):
    """fetch_ted() returns a list of dicts on success."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_TED_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    result = fetch_ted()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["id"] == "TED-2024-999"
    assert result[0]["source"] == "TED Europa"


@patch("src.ted_api.requests.post")
def test_fetch_handles_http_error(mock_post):
    """HTTP 500 returns empty list, no crash."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
    mock_post.return_value = mock_resp

    result = fetch_ted()

    assert result == []


@patch("src.ted_api.requests.post")
def test_fetch_handles_timeout(mock_post):
    """Timeout returns empty list, no crash."""
    mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

    result = fetch_ted()

    assert result == []


@patch("src.ted_api.requests.post")
def test_output_format(mock_post):
    """All required fields are present in output."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = MOCK_TED_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_post.return_value = mock_resp

    result = fetch_ted()

    assert len(result) > 0
    entry = result[0]
    required_fields = {"id", "title", "buyer", "published", "deadline", "url", "source"}
    assert required_fields.issubset(entry.keys())
