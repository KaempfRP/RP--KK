"""AI-powered Management Summaries via Claude Haiku.

Generates concise German management summaries for high-relevance
tender entries. Summaries describe what is being tendered, the buyer,
and which ReqPOOL consulting role would fit best.
"""

import json
import logging
import os
import time

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-haiku-4-5-20251001"
RELEVANCE_THRESHOLD = 15
MAX_RETRIES = 2
RETRY_DELAY = 1.0
BATCH_DELAY = 0.1

SYSTEM_PROMPT = (
    "Du bist ein Senior-Berater bei ReqPOOL (Management-Beratung für Software-Projekte).\n"
    "ReqPOOL hilft Kunden bei: Anforderungsspezifikation (Lastenheft/Pflichtenheft), "
    "EU-weiten Software-Ausschreibungen, Software-Implementierungsmanagement "
    "(PM, Testing, QA), strategischer IT-Beratung & Digitalisierung.\n"
    "ReqPOOL schreibt KEINEN Code, liefert KEINE Software-Produkte, "
    "installiert KEINE Hardware, betreibt KEINE Systeme.\n\n"
    "Du erstellst eine faktenbasierte Management Summary einer Ausschreibung.\n"
    "STRIKTE REGEL: Verwende AUSSCHLIESSLICH die im User-Prompt gelieferten Daten. "
    "ERFINDE NICHTS. Wenn eine Information nicht geliefert wurde, lasse das Feld "
    "weg (bei Listen/Objekten) oder leer. Lieber eine kurze, korrekte Summary "
    "als eine vollständige mit erfundenen Details.\n\n"
    "Antworte NUR mit einem JSON-Objekt. Kein Text davor oder danach. Schema:\n"
    "{\n"
    ' "was_gesucht": "2-4 Sätze: Was wird konkret gesucht? Ziel und Kontext.",\n'
    ' "handlungsfelder": ["konkrete Themen/Leistungsbausteine aus der Beschreibung"],\n'
    ' "eckdaten": {"Verfahren": "...", "Laufzeit": "...", "Geschätzter Wert": "...", "KMU-geeignet": "..."},\n'
    ' "fristen": {"Angebots-/Teilnahmefrist": "..."},\n'
    ' "zuschlagskriterien": [["Kriterium", "Gewichtung"]],\n'
    ' "eignung": ["Eignungs-/Referenzanforderungen, falls genannt"],\n'
    ' "relevanz": "2-4 Sätze: Wie relevant für ReqPOOL? Kritische Hürden? Go/No-Go-Hinweis.",\n'
    ' "empfehlung": "1 Satz: Welche ReqPOOL-Rolle(n) anbieten (IT-Projektmanager / Requirements Engineer / '
    "Business-Analyst / IT-Architekt / Prozessmanager / Scrum Master / Testmanager / "
    'IT-Stratege / PMO / IT-Einkauf / Proxy-PO / IT-Cost Controller)?",\n'
    ' "fit_score": 0-100\n'
    "}\n\n"
    "Nur belegte Schlüssel in eckdaten/fristen aufnehmen. Leere Listen weglassen.\n"
    "fit_score Skala:\n"
    "- 0 = Nicht relevant (Bau, Hardware, Infrastruktur ohne IT-Bezug)\n"
    "- 10-25 = Randthema, evtl. IT-Anteil\n"
    "- 30-50 = IT-Bezug, aber kein klarer Management-Beratungs-Fit\n"
    "- 55-75 = Guter Fit fuer mindestens eine ReqPOOL-Rolle\n"
    "- 80-100 = Kerngeschaeft von ReqPOOL, hohe Gewinnchance\n"
    "WENN die Ausschreibung KEINE Management-Beratung oder IT-Consulting sucht "
    "(z.B. Softwareentwicklung, Hardware, Bau), MUSS fit_score unter 20 sein."
)


def _get_client():
    """Create Anthropic client. Returns None if API key is missing or package unavailable."""
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        logger.warning("anthropic package nicht installiert – überspringe Summaries")
        return None
    except Exception as e:
        logger.warning("Anthropic Client-Fehler: %s", e)
        return None


_DETAIL_LABELS = {
    "beschreibung": "Beschreibung",
    "verfahren": "Verfahren",
    "laufzeit": "Laufzeit",
    "laufzeit_monate": "Laufzeit (Monate)",
    "geschaetzter_wert": "Geschätzter Wert",
    "kmu_geeignet": "KMU-geeignet",
    "vergabeportal": "Vergabeportal",
    "zuschlagskriterien": "Zuschlagskriterien",
    "zuschlagskriterien_typen": "Zuschlagskriterien (Typen)",
}


def _build_user_message(entry: dict) -> str:
    """Build the user prompt from an entry's fields and detail facts."""
    title = entry.get("title", "–")
    buyer = entry.get("buyer", "–")
    deadline = entry.get("deadline", "–")
    roles = ", ".join(entry.get("matched_roles", []))
    lines = [
        f"Ausschreibung: {title}",
        f"Auftraggeber: {buyer}",
        f"Quelle: {entry.get('source', '–')}",
        f"Veröffentlicht: {entry.get('published', '–')}",
        f"Angebots-/Teilnahmefrist: {deadline}",
        f"CPV-Codes: {', '.join(entry.get('cpv', [])) or '–'}",
        f"Erkannte Rollen: {roles or '–'}",
    ]
    for key, value in (entry.get("details") or {}).items():
        lines.append(f"{_DETAIL_LABELS.get(key, key)}: {value}")
    return "\n".join(lines)


def _parse_summary_json(text: str) -> dict:
    """Parse the JSON response from Claude into a structured summary dict.

    Passes through all schema keys (v2 management summary) while
    guaranteeing a numeric fit_score. Legacy v1 keys (chance/empfehlung/
    naechster_schritt) survive unchanged for backward compatibility.
    """
    try:
        # Strip markdown code fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
            cleaned = cleaned.rsplit("```", 1)[0]
        data = json.loads(cleaned)
        if not isinstance(data, dict):
            raise ValueError("not a JSON object")
        try:
            data["fit_score"] = int(data.get("fit_score", 0))
        except (ValueError, TypeError):
            data["fit_score"] = 0
        return data
    except (json.JSONDecodeError, ValueError, TypeError):
        # Fallback: treat entire text as unstructured summary
        return {
            "was_gesucht": text.strip(),
            "relevanz": "",
            "empfehlung": "",
            "fit_score": 0,
        }


def generate_summary(entry: dict, client) -> str:
    """Generate a management summary for a single entry.

    Returns JSON string with structured summary, or "" on any error.
    """
    if client is None:
        return ""

    for attempt in range(MAX_RETRIES + 1):
        try:
            message = client.messages.create(
                model=MODEL,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _build_user_message(entry)}],
            )
            raw = message.content[0].text.strip()
            parsed = _parse_summary_json(raw)
            return json.dumps(parsed, ensure_ascii=False)
        except Exception as e:
            logger.warning(
                "Summary fehlgeschlagen (Versuch %d/%d) für '%s': %s",
                attempt + 1, MAX_RETRIES + 1, entry.get("id", "?"), e,
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    return ""


def summarize_entries(
    entries: list[dict], stored_summaries: dict[str, str]
) -> dict[str, str]:
    """Generate summaries for entries with relevance_score >= threshold.

    Skips entries that already have a summary in stored_summaries.

    Returns dict mapping entry ID -> summary (includes both stored and new).
    """
    result = dict(stored_summaries)

    to_summarize = [
        e for e in entries
        if e.get("relevance_score", 0) >= RELEVANCE_THRESHOLD
        and e["id"] not in result
    ]

    if not to_summarize:
        logger.info("Keine neuen Einträge zum Zusammenfassen")
        return result

    client = _get_client()
    if client is None:
        logger.warning("ANTHROPIC_API_KEY nicht gesetzt – überspringe Summaries")
        return result

    logger.info("Generiere %d Management Summaries...", len(to_summarize))

    for i, entry in enumerate(to_summarize):
        summary = generate_summary(entry, client)
        if summary:
            result[entry["id"]] = summary
            logger.info("Summary %d/%d generiert: %s", i + 1, len(to_summarize), entry["id"])
        else:
            logger.warning("Summary %d/%d fehlgeschlagen: %s", i + 1, len(to_summarize), entry["id"])

        if i < len(to_summarize) - 1:
            time.sleep(BATCH_DELAY)

    return result
