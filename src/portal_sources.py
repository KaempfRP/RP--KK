"""Connectors for additional tender portals.

- oeffentlichevergabe.de (Datenservice Öffentlicher Einkauf):
  Official German central publication service. Daily eForms-XML bulk
  export, no auth required. Notices from many platforms (DTVP, subreport,
  Vergabe.NRW, ...) are published here since the eForms-DE mandate.
- ausschreibung.at: Austrian tender portal. The homepage lists the
  latest notices; detail pages are public and scraped for full data.

Entries are pre-filtered for IT/consulting context (CPV or title
keywords) so the page is not flooded with hundreds of irrelevant
notices per day.
"""

import io
import logging
import os
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from src.scoring import _has_context_cpv, _has_context_keywords

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 TenderScout/1.0"

# ---------------------------------------------------------------------------
# oeffentlichevergabe.de — eForms bulk export
# ---------------------------------------------------------------------------

OEVG_EXPORT_URL = (
    "https://oeffentlichevergabe.de/api/notice-exports"
    "?pubDay={day}&format=eforms.zip"
)
OEVG_DETAIL_URL = "https://oeffentlichevergabe.de/ui/de/notices/{notice_id}"

# eForms root elements that are open calls for competition
_OEVG_TENDER_ROOTS = {"ContractNotice"}


def _local(tag: str) -> str:
    """Strip XML namespace: '{ns}Name' -> 'Name'."""
    return tag.rsplit("}", 1)[-1]


def _findall_local(root: ET.Element, name: str) -> list[ET.Element]:
    """Find all descendants with the given local (namespace-free) name."""
    return [el for el in root.iter() if _local(el.tag) == name]


def _first_text(root: ET.Element, name: str) -> str:
    """Text of the first descendant with the given local name."""
    for el in root.iter():
        if _local(el.tag) == name and el.text:
            return el.text.strip()
    return ""


def _extract_buyer(root: ET.Element) -> str:
    """Resolve the buyer organization name from an eForms notice.

    EU notices: ContractingParty references an organization by ID and the
    organization list carries the names. National eForms-DE notices carry
    the name directly under ContractingParty/Party/PartyName instead.
    """
    buyer_org_id = ""
    cp_direct_name = ""
    for cp in _findall_local(root, "ContractingParty"):
        for el in cp.iter():
            tag = _local(el.tag)
            if tag == "ID" and el.text and not buyer_org_id:
                buyer_org_id = el.text.strip()
            elif tag == "Name" and el.text and not cp_direct_name:
                cp_direct_name = el.text.strip()
        break

    first_name = ""
    for org in _findall_local(root, "Organization"):
        org_id = ""
        name = ""
        for el in org.iter():
            tag = _local(el.tag)
            if tag == "ID" and el.text and not org_id:
                org_id = el.text.strip()
            elif tag == "Name" and el.text and not name:
                name = el.text.strip()
        if name and not first_name:
            first_name = name
        if buyer_org_id and org_id == buyer_org_id and name:
            return name
    return cp_direct_name or first_name or "–"


def _parse_eforms_notice(xml_bytes: bytes, notice_id: str, fallback_published: str = "") -> dict | None:
    """Parse one eForms XML file into the unified entry format.

    Returns None for non-tender notices (awards, planning) or
    unparseable XML.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    if _local(root.tag) not in _OEVG_TENDER_ROOTS:
        return None

    # Title: ProcurementProject/Name (first one is the main project)
    title = ""
    for pp in _findall_local(root, "ProcurementProject"):
        title = _first_text(pp, "Name")
        if title:
            break

    # CPV codes: all ItemClassificationCode values
    cpv = sorted({
        el.text.strip()
        for el in _findall_local(root, "ItemClassificationCode")
        if el.text
    })

    # Deadline: TenderSubmissionDeadlinePeriod/EndDate
    deadline = ""
    for period in _findall_local(root, "TenderSubmissionDeadlinePeriod"):
        deadline = _first_text(period, "EndDate")
        if deadline:
            break

    # National eForms-DE notices have no IssueDate — fall back to export day
    published = _first_text(root, "IssueDate") or fallback_published

    return {
        "id": f"oevg-{notice_id}",
        "title": re.sub(r"\s+", " ", title).strip() or "–",
        "buyer": _extract_buyer(root),
        "published": published.split("+")[0] if published else "–",
        "deadline": deadline.split("+")[0] if deadline else "–",
        "url": OEVG_DETAIL_URL.format(notice_id=notice_id),
        "source": "oeffentlichevergabe.de",
        "cpv": cpv,
        "details": _extract_eforms_details(root),
    }


_PROCEDURE_LABELS = {
    "open": "Offenes Verfahren",
    "restricted": "Nicht offenes Verfahren (Teilnahmewettbewerb)",
    "comp-dial": "Wettbewerblicher Dialog",
    "comp-tend": "Verhandlungsverfahren mit Teilnahmewettbewerb",
    "neg-w-call": "Verhandlungsverfahren mit Teilnahmewettbewerb",
    "neg-wo-call": "Verhandlungsverfahren ohne Teilnahmewettbewerb",
    "innovation": "Innovationspartnerschaft",
}

_DURATION_UNITS = {"MONTH": "Monate", "DAY": "Tage", "YEAR": "Jahre", "WEEK": "Wochen"}


def _extract_eforms_details(root: ET.Element) -> dict:
    """Extract fact fields from eForms XML.

    `beschreibung` speist das Scoring (siehe scoring.py). Die uebrigen Felder
    stammen aus der entfernten KI-Summary und werden derzeit nur mitgefuehrt.
    """
    details: dict[str, str] = {}

    # Project description: first Description inside the first ProcurementProject
    for pp in _findall_local(root, "ProcurementProject"):
        desc = _first_text(pp, "Description")
        if desc:
            details["beschreibung"] = re.sub(r"\s+", " ", desc).strip()[:2500]
        break

    procedure = _first_text(root, "ProcedureCode")
    if procedure:
        details["verfahren"] = _PROCEDURE_LABELS.get(procedure, procedure)

    value = _first_text(root, "EstimatedOverallContractAmount")
    if value:
        details["geschaetzter_wert"] = f"{value} EUR"

    for el in root.iter():
        if _local(el.tag) == "DurationMeasure" and el.text:
            unit = _DURATION_UNITS.get(el.get("unitCode", ""), el.get("unitCode", ""))
            details["laufzeit"] = f"{el.text.strip()} {unit}".strip()
            break

    sme = _first_text(root, "SMESuitableIndicator")
    if sme:
        details["kmu_geeignet"] = "Ja" if sme == "true" else "Nein"

    for el in root.iter():
        if _local(el.tag) == "EndpointID" and el.text and el.text.startswith("http"):
            details["vergabeportal"] = el.text.strip()
            break

    # Award criteria (best effort — name/description + numeric weight)
    criteria = []
    for crit in _findall_local(root, "SubordinateAwardingCriterion"):
        name = _first_text(crit, "Name") or _first_text(crit, "Description")
        weight = _first_text(crit, "ParameterNumeric")
        if name:
            criteria.append(f"{name[:80]}{f' ({weight} %)' if weight else ''}")
    if criteria:
        details["zuschlagskriterien"] = "; ".join(criteria[:8])

    return details


def fetch_oeffentlichevergabe(days: int | None = None) -> list[dict]:
    """Fetch IT/consulting tenders from the last `days` daily exports.

    4 days back so weekend exports are covered by the Monday run and a
    single failed workflow run does not lose notices permanently
    (dedup makes re-fetching harmless).

    Only entries passing the IT/consulting context check (CPV or title
    keywords) are returned — the service publishes ~1000 notices per
    day across all trades.
    """
    if days is None:
        # Overridable for backfills: OEVG_DAYS=14 python main.py
        # Default 6 covers a long weekend plus one missed run; persistence
        # keeps older-but-still-open tenders on the page anyway.
        # (env may be present but empty on scheduled runs → treat as unset)
        env_days = (os.environ.get("OEVG_DAYS") or "").strip()
        try:
            days = int(env_days) if env_days else 6
        except ValueError:
            days = 6

    entries: list[dict] = []
    seen_ids: set[str] = set()
    today = datetime.now(timezone.utc).date()

    for offset in range(days):
        day = (today - timedelta(days=offset)).isoformat()
        url = OEVG_EXPORT_URL.format(day=day)
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=90)
            resp.raise_for_status()
            archive = zipfile.ZipFile(io.BytesIO(resp.content))
        except Exception as e:
            logger.warning("oeffentlichevergabe.de export %s error: %s", day, e)
            continue

        for name in archive.namelist():
            notice_id = name.rsplit("-", 1)[0] if "-" in name else name
            notice_id = re.sub(r"\.xml$", "", notice_id)
            try:
                entry = _parse_eforms_notice(archive.read(name), notice_id, fallback_published=day)
            except Exception as e:
                logger.debug("eForms parse error %s: %s", name, e)
                continue
            if entry is None or entry["id"] in seen_ids:
                continue
            # Pre-filter: keep only IT/consulting context
            if not _has_context_cpv(entry["cpv"]) and not _has_context_keywords(entry["title"].lower()):
                continue
            seen_ids.add(entry["id"])
            entries.append(entry)

    logger.info("oeffentlichevergabe.de: %d IT-relevante Ergebnisse (%d Tage)", len(entries), days)
    return entries


# ---------------------------------------------------------------------------
# ausschreibung.at — homepage list + public detail pages
# ---------------------------------------------------------------------------

AUSSCHREIBUNG_AT_BASE = "https://www.ausschreibung.at"

# Document types that are open tenders (skip awards etc.)
_AT_SKIP_DOC_TYPES = ("vergebener auftrag", "berichtigung", "widerruf")


def _parse_ausschreibung_at_detail(html: str, url: str) -> dict | None:
    """Parse a public ausschreibung.at detail page."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["nav", "header", "footer", "script", "style"]):
        tag.decompose()

    text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    def value_after(label: str) -> str:
        for i, line in enumerate(lines):
            if line.lower() == label and i + 1 < len(lines):
                return lines[i + 1]
        return ""

    doc_type = value_after("art des dokuments")
    if doc_type and any(s in doc_type.lower() for s in _AT_SKIP_DOC_TYPES):
        return None

    # Title: the line right after the "ÜBERBLICK AUSSCHREIBUNG" heading
    title = ""
    for i, line in enumerate(lines):
        if "überblick ausschreibung" in line.lower() and i + 1 < len(lines):
            title = lines[i + 1]
            break

    published = value_after("veröffentlicht am")
    deadline = value_after("angebotsfrist") or value_after("frist") or "–"
    buyer = value_after("auftraggeber") or value_after("ausschreiber") or "–"

    if not title:
        return None

    return {
        "id": "at-" + re.sub(r"\D", "", url),
        "title": title,
        "buyer": buyer,
        "published": published or "–",
        "deadline": deadline,
        "url": url,
        "source": "ausschreibung.at",
    }


def fetch_ausschreibung_at() -> list[dict]:
    """Fetch the latest notices from ausschreibung.at.

    The homepage lists the most recent ~20 notices; each public detail
    page is fetched for the full title and metadata. Only entries with
    IT/consulting context in the title are kept.
    """
    try:
        resp = requests.get(
            AUSSCHREIBUNG_AT_BASE + "/",
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning("ausschreibung.at homepage error: %s", e)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    hrefs = []
    for a in soup.select('a[href^="/Ausschreibung/"]'):
        href = a.get("href", "")
        if re.match(r"^/Ausschreibung/\d+/?$", href) and href not in hrefs:
            hrefs.append(href)

    entries = []
    for i, href in enumerate(hrefs):
        url = AUSSCHREIBUNG_AT_BASE + href
        if i > 0:
            time.sleep(1.5)  # the portal 503s on rapid successive requests
        try:
            detail = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            if detail.status_code == 503:
                time.sleep(5)
                detail = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            detail.raise_for_status()
            entry = _parse_ausschreibung_at_detail(detail.text, url)
        except Exception as e:
            logger.warning("ausschreibung.at detail %s error: %s", url, e)
            continue
        if entry is None:
            continue
        # Pre-filter: IT/consulting context in title only (no CPV available)
        if not _has_context_keywords(entry["title"].lower()):
            continue
        entries.append(entry)

    logger.info("ausschreibung.at: %d IT-relevante Ergebnisse", len(entries))
    return entries
