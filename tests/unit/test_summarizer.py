"""Unit tests for AI summarizer module."""

from unittest.mock import patch, MagicMock

from src.summarizer import (
    generate_summary,
    summarize_entries,
    _build_user_message,
    _get_client,
)


# --- Prompt construction ---

def test_build_user_message_includes_all_fields():
    """User message includes title, buyer, deadline, roles."""
    entry = {
        "title": "SAP Migration",
        "buyer": "Stadtwerke München",
        "deadline": "2025-06-01",
        "matched_roles": ["IT-Projektmanager", "IT-Architekt"],
    }
    msg = _build_user_message(entry)
    assert "SAP Migration" in msg
    assert "Stadtwerke München" in msg
    assert "2025-06-01" in msg
    assert "IT-Projektmanager" in msg


def test_build_user_message_handles_missing_fields():
    """Missing fields use fallback dash."""
    msg = _build_user_message({})
    assert "–" in msg


# --- Client creation ---

def test_get_client_returns_none_without_key(monkeypatch):
    """No API key -> None client."""
    monkeypatch.setattr("src.summarizer.ANTHROPIC_API_KEY", "")
    assert _get_client() is None


# --- Single summary generation ---

def test_generate_summary_returns_json():
    """Successful API call returns structured JSON summary."""
    import json
    mock_client = MagicMock()
    mock_json = '{"chance": "Gute Chance.", "empfehlung": "IT-PM.", "naechster_schritt": "Angebot.", "fit_score": 75}'
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=mock_json)]
    mock_client.messages.create.return_value = mock_response

    entry = {"id": "test-1", "title": "IT-Beratung", "buyer": "EnBW", "matched_roles": []}
    result = generate_summary(entry, mock_client)
    parsed = json.loads(result)
    assert parsed["chance"] == "Gute Chance."
    assert parsed["fit_score"] == 75


def test_generate_summary_returns_empty_on_api_error(monkeypatch):
    """API error returns empty string, no crash."""
    monkeypatch.setattr("src.summarizer.RETRY_DELAY", 0)
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("API Error")

    entry = {"id": "test-1", "title": "Test", "buyer": "Test", "matched_roles": []}
    result = generate_summary(entry, mock_client)
    assert result == ""


def test_generate_summary_returns_empty_when_client_none():
    """None client returns empty string immediately."""
    entry = {"id": "test-1", "title": "Test", "buyer": "Test", "matched_roles": []}
    result = generate_summary(entry, None)
    assert result == ""


def test_generate_summary_retries_on_failure(monkeypatch):
    """Retries on first failure, succeeds on second attempt."""
    import json
    monkeypatch.setattr("src.summarizer.RETRY_DELAY", 0)

    mock_client = MagicMock()
    mock_success = MagicMock()
    mock_json = '{"chance": "Erfolg.", "empfehlung": "", "naechster_schritt": "", "fit_score": 50}'
    mock_success.content = [MagicMock(text=mock_json)]
    mock_client.messages.create.side_effect = [
        Exception("Transient error"),
        mock_success,
    ]

    entry = {"id": "test-1", "title": "Test", "buyer": "Test", "matched_roles": []}
    result = generate_summary(entry, mock_client)
    parsed = json.loads(result)
    assert parsed["chance"] == "Erfolg."
    assert mock_client.messages.create.call_count == 2


# --- Batch summarization ---

@patch("src.summarizer._get_client")
def test_summarize_entries_skips_low_relevance(mock_get_client):
    """Entries below threshold are not sent to API."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    entries = [
        {"id": "low-1", "title": "Dachsanierung", "buyer": "Stadt X",
         "relevance_score": 10, "matched_roles": []},
    ]
    result = summarize_entries(entries, {})
    assert "low-1" not in result
    mock_client.messages.create.assert_not_called()


@patch("src.summarizer._get_client")
@patch("src.summarizer.generate_summary")
def test_summarize_entries_skips_already_stored(mock_gen, mock_get_client):
    """Entries with existing summaries are not re-generated."""
    mock_get_client.return_value = MagicMock()
    stored = {"existing-1": "Bereits vorhanden."}

    entries = [
        {"id": "existing-1", "title": "Test", "buyer": "Test",
         "relevance_score": 50, "matched_roles": ["IT-Projektmanager"]},
    ]
    result = summarize_entries(entries, stored)
    assert result["existing-1"] == "Bereits vorhanden."
    mock_gen.assert_not_called()


@patch("src.summarizer.BATCH_DELAY", 0)
@patch("src.summarizer._get_client")
@patch("src.summarizer.generate_summary")
def test_summarize_entries_generates_new(mock_gen, mock_get_client):
    """New high-relevance entries get summaries generated."""
    mock_get_client.return_value = MagicMock()
    mock_gen.return_value = "Neues Summary generiert."

    entries = [
        {"id": "new-1", "title": "IT-Beratung SAP", "buyer": "EnBW",
         "relevance_score": 50, "matched_roles": ["IT-Projektmanager"]},
    ]
    result = summarize_entries(entries, {})
    assert result["new-1"] == "Neues Summary generiert."


@patch("src.summarizer._get_client")
def test_summarize_entries_no_key_returns_stored(mock_get_client):
    """Without API key, returns stored summaries unchanged."""
    mock_get_client.return_value = None
    stored = {"old-1": "Alter Summary."}

    entries = [
        {"id": "new-1", "title": "IT-Beratung", "buyer": "Test",
         "relevance_score": 50, "matched_roles": []},
    ]
    result = summarize_entries(entries, stored)
    assert result == stored
    assert "new-1" not in result
