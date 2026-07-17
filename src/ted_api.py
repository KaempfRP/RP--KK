"""TED Search API V3 Connector.

Queries the TED Europa Search API for relevant energy & IT tenders
matching ReqPOOL's filter criteria (CPV, country, legal basis).
"""

import logging
import requests

logger = logging.getLogger(__name__)

TED_SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"

# notice-type values that are actual open tenders (not awards/results)
OPEN_NOTICE_TYPES = {"cn-standard", "cn-social", "cn-desg", "comp-negotiated", "qu-sy"}

SEARCH_BODY = {
    "query": (
        "classification-cpv IN ("
        "72000000, 72200000, 72220000, 72224000, 72240000, "
        "72260000, 72300000, 72600000, "
        "79410000, 79411000, 79421000"
        ") "
        "AND buyer-country = DEU "
        "SORT BY publication-date DESC"
    ),
    "fields": [
        "publication-number",
        "notice-title",
        "buyer-name",
        "publication-date",
        "deadline-receipt-tender-date-lot",
        "classification-cpv",
        "notice-type",
        "buyer-country",
        # description-lot speist das Scoring (siehe scoring.py: die Beschreibung
        # ist ein Signal, das der Titel allein verpasst). Die uebrigen Felder
        # stammen aus der entfernten KI-Summary und werden derzeit nur mitgefuehrt.
        "description-lot",
        "procedure-type",
        "duration-period-value-lot",
        "award-criterion-type-lot",
    ],
    "page": 1,
    "limit": 100,
}

PROCEDURE_LABELS = {
    "open": "Offenes Verfahren",
    "restricted": "Nicht offenes Verfahren (Teilnahmewettbewerb)",
    "comp-dial": "Wettbewerblicher Dialog",
    "comp-tend": "Verhandlungsverfahren mit Teilnahmewettbewerb",
    "innovation": "Innovationspartnerschaft",
    "neg-w-call": "Verhandlungsverfahren mit Teilnahmewettbewerb",
    "neg-wo-call": "Verhandlungsverfahren ohne Teilnahmewettbewerb",
}


def _first_of(value) -> str:
    """Reduce list/dict multilingual API values to one plain string."""
    if isinstance(value, dict):
        value = value.get("deu") or value.get("eng") or next(iter(value.values()), "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value) if value else ""


def _extract_entry(raw: dict) -> dict:
    """Convert a raw TED API result into our unified entry format."""
    title = raw.get("notice-title", "")
    if isinstance(title, dict):
        title = title.get("deu") or title.get("eng") or next(iter(title.values()), "–")
    if isinstance(title, list):
        title = title[0] if title else "–"

    buyer = raw.get("buyer-name", "–")
    if isinstance(buyer, dict):
        first_val = buyer.get("deu") or buyer.get("eng") or next(iter(buyer.values()), "–")
        buyer = first_val
    if isinstance(buyer, list):
        buyer = buyer[0] if buyer else "–"

    deadline_raw = raw.get("deadline-receipt-tender-date-lot")
    if isinstance(deadline_raw, list):
        deadline = str(deadline_raw[0]) if deadline_raw else "–"
    elif deadline_raw:
        deadline = str(deadline_raw)
    else:
        deadline = "–"

    # URL from links object (auto-included by API)
    links = raw.get("links", {})
    html_links = links.get("html", {})
    url = html_links.get("DEU") or html_links.get("ENG") or ""
    if not url:
        # Fallback: construct from publication number
        pub_nr = raw.get("publication-number", "")
        if pub_nr:
            url = f"https://ted.europa.eu/en/notice/-/detail/{pub_nr}"

    # CPV codes (P2: used by the scoring context gate)
    cpv_raw = raw.get("classification-cpv")
    if isinstance(cpv_raw, list):
        cpv = [str(c) for c in cpv_raw]
    elif cpv_raw:
        cpv = [str(cpv_raw)]
    else:
        cpv = []

    # Detail facts for the AI management summary
    details = {}
    description = _first_of(raw.get("description-lot"))
    if description:
        details["beschreibung"] = description[:2500]
    procedure = _first_of(raw.get("procedure-type"))
    if procedure:
        details["verfahren"] = PROCEDURE_LABELS.get(procedure, procedure)
    duration = _first_of(raw.get("duration-period-value-lot"))
    if duration:
        details["laufzeit_monate"] = duration
    criteria = raw.get("award-criterion-type-lot")
    if criteria:
        if not isinstance(criteria, list):
            criteria = [criteria]
        details["zuschlagskriterien_typen"] = ", ".join(str(c) for c in criteria)

    return {
        "id": str(raw.get("publication-number", "")),
        "title": str(title),
        "buyer": str(buyer),
        "published": str(raw.get("publication-date", "–")).split("+")[0],
        "deadline": deadline.split("+")[0],
        "url": url,
        "source": "TED Europa",
        "cpv": cpv,
        "details": details,
    }


def fetch_ted() -> list[dict]:
    """Fetch tenders from TED Search API V3.

    Returns a list of entry dicts. On any error, logs a warning
    and returns an empty list (never crashes).
    """
    try:
        resp = requests.post(
            TED_SEARCH_URL,
            json=SEARCH_BODY,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        notices = data.get("notices") or data.get("results") or []
        if isinstance(data, list):
            notices = data

        # Filter out contract awards and other non-tender notices
        entries = []
        for n in notices:
            notice_type = n.get("notice-type", "")
            if notice_type and notice_type not in OPEN_NOTICE_TYPES:
                logger.debug("Überspringe %s (Typ: %s)", n.get("publication-number", "?"), notice_type)
                continue
            entries.append(_extract_entry(n))
        return entries

    except requests.exceptions.Timeout:
        logger.warning("TED API Timeout – returning empty list")
        return []
    except requests.exceptions.HTTPError as e:
        logger.warning("TED API HTTP Error %s – returning empty list", e)
        return []
    except Exception as e:
        logger.warning("TED API unexpected error: %s – returning empty list", e)
        return []
