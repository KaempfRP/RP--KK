"""Connectors for German energy sector tender portals.

Fetches tenders from tender24.de by searching for known energy sector
buyers (ÜNBs, VNBs, Stadtwerke, Energieversorger).
Each search is independent — a failure in one does not affect others.
"""

import hashlib
import logging
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

TENDER24_SEARCH_URL = (
    "https://www.tender24.de/NetServer/PublicationSearchControllerServlet"
    "?function=Search&Searchkey={query}"
)

# Energy sector buyers to search for on tender24.de
# Grouped by type for clarity
ENERGY_BUYERS = [
    # Große Energieversorger
    "EnBW",
    "RWE",
    "E.ON",
    "Vattenfall",
    "EWE",
    "LEAG",
    # ÜNBs (Übertragungsnetzbetreiber)
    "50Hertz",
    "Amprion",
    "TenneT",
    "TransnetBW",
    # VNBs / Netzgesellschaften
    "Westnetz",
    "Stromnetz Berlin",
    "Netze BW",
    "Bayernwerk",
    "E.DIS",
    "Avacon",
    "Schleswig-Holstein Netz",
    "Mitteldeutsche Netzgesellschaft",
    "Netz Leipzig",
    # Große Stadtwerke
    "Stadtwerke München",
    "Stadtwerke Köln",
    "Stadtwerke Düsseldorf",
    "Stadtwerke Hamburg",
    "Stadtwerke Frankfurt",
    "Stadtwerke Stuttgart",
    "Stadtwerke Hannover",
    "Stadtwerke Leipzig",
    "Stadtwerke Dresden",
    # Weitere relevante Unternehmen
    "N-ERGIE",
    "MVV Energie",
    "Lechwerke",
    "Mainova",
    "Entega",
    "STAWAG",
    "SWM",  # Stadtwerke München Kürzel
    "Rheinenergie",
    "ENSO",
    "WEMAG",
    "Pfalzwerke",
    "Thüga",
    # Erweitert: weitere große Versorger & Netzgesellschaften
    "Innogy",
    "Hansewerk",
    "E.ON Energie Deutschland",
    "EWE NETZ",
    "Netze Magdeburg",
    "SWK",              # Stadtwerke Krefeld
    "swb",              # Stadtwerke Bremen
    "HEAG",             # Darmstadt
    "EAM",              # EAM Netz Hessen
    "Stadtwerke Essen",
    "Stadtwerke Bochum",
    "Stadtwerke Dortmund",
    "DEW21",
    "Stadtwerke Bielefeld",
    "Stadtwerke Augsburg",
    "Stadtwerke Nürnberg",
    "Stadtwerke Karlsruhe",
    "Stadtwerke Bonn",
    "SWB Energie und Wasser",
    "Netze ODR",
    "Syna",
    "Süwag",
    "ovag Netz",
]


def _make_id(url: str) -> str:
    """Generate a stable ID from a URL using MD5 hash."""
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def _scrape_tender24_search(query: str) -> list[dict]:
    """Run a single search on tender24.de and return parsed results."""
    url = TENDER24_SEARCH_URL.format(query=requests.utils.quote(query))
    resp = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 TenderScout/1.0"},
        timeout=20,
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = soup.select("tr.clickable-row")
    entries = []

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 5:
            continue

        date_text = cells[0].get_text(strip=True)
        title = cells[1].get_text(strip=True)
        buyer = cells[2].get_text(strip=True)
        deadline_cell = cells[5] if len(cells) > 5 else None
        deadline = deadline_cell.get_text(strip=True) if deadline_cell else "–"

        # Link to search results with title — detail pages require login
        search_term = requests.utils.quote(title[:80]) if title else ""
        detail_url = (
            f"https://www.tender24.de/NetServer/PublicationSearchControllerServlet"
            f"?function=Search&Searchkey={search_term}"
        ) if search_term else ""

        entries.append({
            "id": _make_id(detail_url or title),
            "title": title or "–",
            "buyer": buyer or "–",
            "published": date_text or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "deadline": deadline or "–",
            "url": detail_url,
            "source": "tender24.de",
        })

    return entries


def fetch_tender24() -> list[dict]:
    """Fetch tenders from tender24.de for all known energy sector buyers."""
    all_entries = []
    seen_ids = set()

    for buyer in ENERGY_BUYERS:
        try:
            results = _scrape_tender24_search(buyer)
            for entry in results:
                if entry["id"] not in seen_ids:
                    seen_ids.add(entry["id"])
                    all_entries.append(entry)
        except Exception as e:
            logger.warning("tender24.de search '%s' error: %s", buyer, e)

    logger.info("tender24.de: %d Ergebnisse für %d Suchbegriffe", len(all_entries), len(ENERGY_BUYERS))
    return all_entries


def fetch_rss_sources() -> list[dict]:
    """Fetch and merge tenders from all non-TED sources."""
    from src.portal_sources import fetch_oeffentlichevergabe, fetch_ausschreibung_at

    results = fetch_tender24()
    results += fetch_oeffentlichevergabe()
    results += fetch_ausschreibung_at()
    return results
