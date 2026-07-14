"""Relevance scoring for ReqPOOL tender matching.

Weighted scoring system (v2):
1. Context Gate — Is this an IT/consulting tender at all?
   Passes via CPV code (72xxx IT / 794xx consulting) OR title keywords.
   This is the only hard gate — everything else is weighted.
2. Role Matching (max 50) — Which ReqPOOL roles fit?
3. ReqPOOL Fit Bonus (max 20) — Direct match to ReqPOOL's core services?
4. Sector Bonus (max 20) — Buyer from a target sector (Energie,
   Immobilien, Telko, Rohstoffe)? Weighted, no longer a hard gate:
   real energy-IT tenders with unusual buyer names still score.
5. Context Bonus (max 10) — CPV/keyword strength of the IT context.

Additionally classifies every entry:
- sector: Energie | Public | Industrie | Sonstige
- buyer_type: e.g. Netzbetreiber, Stadtwerke, Landkreis, Ministerium
"""

import re

# ---------------------------------------------------------------------------
# Tier 1: Context Gate
# At least one must match (CPV or title keyword), otherwise score = 0.
# This eliminates all non-IT/consulting tenders (construction, furniture, etc.)
# ---------------------------------------------------------------------------

# CPV prefixes that indicate IT / consulting context (P2: CPV in the gate)
_CPV_IT_PREFIXES = (
    "72",     # IT services: consulting, software development, internet
    "480",    # Software packages
    "7222",   # Systems and technical consultancy
)
_CPV_CONSULTING_PREFIXES = (
    "7941",   # Business and management consultancy
    "79421",  # Project-management services other than construction
    "73220",  # Development consultancy
)

_CONTEXT_KEYWORDS_SIMPLE = [
    # IT domain
    "software", "ikt", "edv", "sap", "erp", "crm",
    "digitalisierung", "cloud", "saas", "paas", "iaas",
    "cyber", "informationssicherheit",
    # Consulting domain (specific to IT/management, NOT generic "beratung")
    "it-beratung", "consulting", "managementberatung",
    "unternehmensberatung", "strategieberatung",
    "digitalisierungsberatung",
    # Software project lifecycle
    "softwareprojekt", "softwareeinführung", "softwarebeschaffung",
    "softwareauswahl", "systemeinführung", "systemauswahl",
    "anforderungsmanagement", "anforderungsanalyse",
    "lastenheft", "pflichtenheft",
    "testmanagement", "qualitätssicherung",
    "projektmanagement", "projektsteuerung", "programmmanagement",
    # IT procurement
    "vergabebegleitung", "ausschreibungsberatung", "vergabeberatung",
    "ausschreibungsmanagement",
    # Energy IT specifics
    "marktkommunikation", "redispatch", "netzleitsystem",
    "billing", "abrechnungssystem", "energiedatenmanagement",
    "smart meter", "intelligentes messsystem",
    "mako", "gpke",
]

# Short terms that need word-boundary matching to avoid false positives
_CONTEXT_KEYWORDS_BOUNDARY = ["it", "bi", "ki", "dms", "ecm"]


def _has_context_keywords(title: str) -> bool:
    """Check if TITLE contains at least one IT/consulting context keyword.

    Only checks title, not buyer — 'Projektmanagement' in a company name
    like 'Drees & Sommer - Projektmanagement' is not IT context.
    """
    for kw in _CONTEXT_KEYWORDS_SIMPLE:
        if kw in title:
            return True
    for kw in _CONTEXT_KEYWORDS_BOUNDARY:
        if re.search(r'\b' + re.escape(kw) + r'\b', title):
            return True
    return False


def _has_context_cpv(cpv_codes: list[str]) -> bool:
    """Check if any CPV code indicates IT/consulting context."""
    for code in cpv_codes:
        code = str(code).strip()
        if code.startswith(_CPV_IT_PREFIXES) or code.startswith(_CPV_CONSULTING_PREFIXES):
            return True
    return False


# ---------------------------------------------------------------------------
# Tier 2: Role Matching — refined keywords, generics removed
# ---------------------------------------------------------------------------

ROLE_KEYWORDS: dict[str, list[str]] = {
    "IT-Stratege": [
        "it-strategie", "digitalisierungsstrategie",
        "digitale transformation", "it-beratung", "strategieberatung",
        "e-government", "smart city", "it-governance", "it-steuerung",
        "digitalisierungsberatung", "it-masterplan", "it-roadmap",
        "technologieberatung",
    ],
    "PMO & IT-Koordinator": [
        "pmo", "projektsteuerung", "programmmanagement",
        "multiprojektmanagement", "it-koordination", "projektkoordination",
        "projektbüro", "projektportfolio", "projektoffice",
    ],
    "Business-Analyst": [
        "business-analyse", "business analyse", "geschäftsprozessanalyse",
        "wirtschaftlichkeitsanalyse", "kosten-nutzen-analyse",
        "machbarkeitsstudie", "ist-analyse", "soll-konzept",
        "potenzialanalyse", "bedarfsanalyse",
    ],
    "Requirements Engineer": [
        "anforderungsmanagement", "requirements engineering",
        "lastenheft", "pflichtenheft",
        "anforderungsanalyse", "anforderungsspezifikation",
        "fachkonzept", "lastenhefterstellung",
        "anforderungskatalog", "leistungsbeschreibung",
        "pflichtenhefterstellung",
    ],
    "IT-Architekt": [
        "it-architektur", "enterprise-architektur", "systemarchitektur",
        "lösungsarchitektur", "cloud-architektur",
        "microservices", "systemdesign", "datenarchitektur",
        "schnittstellenmanagement",
    ],
    "Prozessmanager": [
        "prozessmanagement", "prozessoptimierung", "prozessdokumentation",
        "prozessautomatisierung", "bpmn", "geschäftsprozessmodellierung",
        "prozessberatung", "prozessanalyse", "prozesslandkarte",
    ],
    "IT-Projektmanager": [
        "it-projektmanagement", "it-projektleitung",
        "projektmanagement", "projektleitung", "projektmanager",
        "projektumsetzung", "systemeinführung", "softwareeinführung",
        "erp-einführung", "it-migration", "sap-einführung",
        "sap-migration",
    ],
    "IT-Cost Controller": [
        "it-kosten", "it-controlling", "it-kostenanalyse",
        "it-benchmarking", "it-budgetierung",
        "softwarekosten", "lizenzmanagement", "lizenzkostenoptimierung",
    ],
    "IT-Einkauf": [
        "it-beschaffung", "softwarebeschaffung", "it-vergabe",
        "ausschreibungsberatung", "beschaffungsberatung", "vergabeberatung",
        "vergabebegleitung", "ausschreibungsmanagement",
        "softwareauswahl", "lieferantenauswahl", "lieferantenbewertung",
    ],
    "Proxy-Product Owner": [
        "product owner", "backlog", "produktmanagement",
        "user story", "product backlog", "proxy-po",
    ],
    "Testmanager": [
        "testmanagement", "qualitätssicherung", "softwaretest",
        "abnahmetest", "testkonzept", "teststrategie",
        "testautomatisierung", "qa-management",
        "release-management", "integrationstests",
    ],
    "Scrum Master & Agile Coach": [
        "scrum", "agile coach", "agile transformation",
        "agile methoden", "scrum master", "kanban",
        "agile projektmethodik", "agiles projektmanagement",
    ],
}

# ---------------------------------------------------------------------------
# Tier 3: ReqPOOL Fit Bonus — terms that directly describe ReqPOOL's services
# ---------------------------------------------------------------------------

_REQPOOL_FIT_KEYWORDS = [
    "beratungsleistungen", "beratungsleistung",
    "managementberatung", "unternehmensberatung",
    "rahmenvertrag", "rahmenvereinbarung",
    "vergabebegleitung", "ausschreibungsmanagement",
    "softwarebeschaffung", "softwareauswahl",
    "lastenhefterstellung", "konzepterstellung",
    "pflichtenhefterstellung",
    "lieferantenauswahl", "lieferantenbewertung",
    "ist-analyse", "soll-konzept",
    "it-governance", "it-steuerung",
    "digitalisierungsberatung",
]

# ---------------------------------------------------------------------------
# Sector classification — sector + buyer type as filterable attributes.
# Sectors: Energie | Public | Industrie | Sonstige
# ---------------------------------------------------------------------------

# (buyer_type, keywords in buyer name) — order matters, first match wins.
# Energie checked before Public so "Stadtwerke" beats "Stadt".
_ENERGY_BUYER_TYPES: list[tuple[str, list[str]]] = [
    ("Netzbetreiber", [
        "netzbetreib", "netzgesellschaft", "übertragungsnetz", "verteilnetz",
        "50hertz", "amprion", "tennet", "transnetbw", "westnetz", "netze bw",
        "bayernwerk", "e.dis", "avacon", "schleswig-holstein netz",
        "netz leipzig", "ewe netz", "netze magdeburg", "netze odr",
        "syna", "süwag", "ovag netz", "eam",
    ]),
    ("Stadtwerke", ["stadtwerk", "swm", "swk", "swb", "stawag", "dew21", "heag"]),
    ("Energieversorger", [
        "energie", "enbw", "rwe", "e.on", "vattenfall", "ewe", "leag",
        "strom", "gas", "fernwärme", "kraftwerk", "windpark",
        "solar", "photovoltaik", "n-ergie", "mvv", "lechwerke", "mainova",
        "entega", "rheinenergie", "enso", "wemag", "pfalzwerke", "thüga",
        "innogy", "hansewerk",
    ]),
]

_PUBLIC_BUYER_TYPES: list[tuple[str, list[str]]] = [
    ("Ministerium", ["ministerium", "senatsverwaltung", "staatskanzlei", "senat "]),
    ("Bundesbehörde", [
        "bundesamt", "bundesanstalt", "bundesagentur", "bundesministerium",
        "bund ", "bundeswehr", "bundespolizei", "zoll",
    ]),
    ("Landesbehörde", ["landesamt", "landesanstalt", "landesbetrieb", "bezirksregierung", "land "]),
    ("Landkreis", ["landkreis", "kreisverwaltung", "kreis ", "landratsamt"]),
    ("Kommune", [
        "stadt ", "landeshauptstadt", "gemeinde", "kommunal", "magistrat",
        "stadtverwaltung", "bezirksamt", "zweckverband", "amt ",
    ]),
    ("Hochschule & Forschung", [
        "universität", "hochschule", "fachhochschule", "institut",
        "forschung", "fraunhofer", "max-planck", "helmholtz", "leibniz",
    ]),
    ("Öffentliche Einrichtung", [
        "klinik", "krankenhaus", "jobcenter", "polizei", "feuerwehr",
        "rundfunk", "kirche", "sparkasse", "kammer", "verkehrsgesellschaft",
        "verkehrsbetrieb", "flughafen", "hafen", "abwasser", "entsorgung",
    ]),
]

_INDUSTRY_BUYER_TYPES: list[tuple[str, list[str]]] = [
    ("Immobilien", [
        "immobili", "wohnbau", "wohnungsbau", "baugesellschaft",
        "gebäudemanagement", "facility", "hausverwaltung",
        "liegenschaft", "wohnungsgesellschaft", "vonovia", "wohnen",
    ]),
    ("Telekommunikation", [
        "telekom", "vodafone", "telefónica", "o2", "glasfaser", "breitband",
        "mobilfunk", "telekommunikation", "netcologne", "ewe tel", "m-net",
    ]),
    ("Rohstoffe & Chemie", [
        "rohstoff", "bergbau", "mining", "k+s", "basf", "chemie", "raffinerie",
    ]),
    ("Industrie & Wirtschaft", [
        "gmbh", "aktiengesellschaft", " ag", " se", " kg", "holding", "werke",
    ]),
]

# Keywords in TITLE that indicate a target-sector topic (used for the
# sector bonus and as fallback for sector classification)
_ENERGY_TITLE_KEYWORDS = [
    "redispatch", "marktkommunikation", "netzleitsystem",
    "billing", "abrechnungssystem", "energiedatenmanagement",
    "smart meter", "intelligentes messsystem",
    "mako", "gpke", "geli gas", "wim",
    "einspeisemanagement", "engpassmanagement",
    "netzbetrieb", "netzsteuerung", "messwesen",
    "energiewirtschaft", "energieversorger",
    "stadtwerke", "netzbetreiber",
    "stromhandel", "gashandel", "energiehandel",
    "ladesäule", "ladeinfrastruktur", "elektromobilität",
]

_SECTOR_TITLE_KEYWORDS = _ENERGY_TITLE_KEYWORDS + [
    # Immobilien
    "gebäudeautomation", "gebäudetechnik", "smart building",
    "facility management", "liegenschafts",
    # Telekommunikation
    "telekommunikation", "glasfaserausbau", "breitbandausbau",
    "5g", "mobilfunk", "netzausbau",
    # Rohstoffe
    "rohstoff", "bergbau", "raffinerie",
]

# Imported at function level to avoid circular import
_energy_buyers_cache: list[str] | None = None


def _get_target_buyers() -> list[str]:
    """Lazy-load ENERGY_BUYERS from rss_sources to avoid circular import."""
    global _energy_buyers_cache
    if _energy_buyers_cache is None:
        from src.rss_sources import ENERGY_BUYERS
        _energy_buyers_cache = ENERGY_BUYERS
    return _energy_buyers_cache


def _kw_in(text: str, kw: str) -> bool:
    """Keyword match with word boundaries for short tokens.

    Short abbreviations like 'rwe', 'eam' or 'swm' would otherwise match
    inside words ('meisterwerken' contains 'rwe', 'team' contains 'eam').
    """
    if len(kw) <= 5 and kw.isalnum():
        return re.search(r"\b" + re.escape(kw) + r"\b", text) is not None
    return kw in text


def _is_known_buyer(buyer_lower: str) -> bool:
    """Check buyer name against the known energy companies list."""
    return any(_kw_in(buyer_lower, eb.lower()) for eb in _get_target_buyers())


def _match_buyer_types(buyer_lower: str, groups: list[tuple[str, list[str]]]) -> str | None:
    """Return first buyer_type whose keywords match the buyer name."""
    for buyer_type, keywords in groups:
        if any(_kw_in(buyer_lower, kw) for kw in keywords):
            return buyer_type
    return None


def classify_sector(title: str, buyer: str) -> tuple[str, str]:
    """Classify an entry into (sector, buyer_type).

    Sectors: Energie | Public | Industrie | Sonstige.
    Buyer types e.g.: Netzbetreiber, Stadtwerke, Landkreis, Ministerium.
    """
    title_lower = (title or "").lower()
    buyer_lower = (buyer or "").lower()

    # Known energy companies list (from rss_sources) → Energie
    if _is_known_buyer(buyer_lower):
        bt = _match_buyer_types(buyer_lower, _ENERGY_BUYER_TYPES) or "Energieversorger"
        return "Energie", bt

    bt = _match_buyer_types(buyer_lower, _ENERGY_BUYER_TYPES)
    if bt:
        return "Energie", bt

    bt = _match_buyer_types(buyer_lower, _PUBLIC_BUYER_TYPES)
    if bt:
        return "Public", bt

    bt = _match_buyer_types(buyer_lower, _INDUSTRY_BUYER_TYPES)
    if bt:
        return "Industrie", bt

    # Fallback: energy-specific topic in the title
    if any(kw in title_lower for kw in _ENERGY_TITLE_KEYWORDS):
        return "Energie", "Energieversorger"

    return "Sonstige", "Sonstige"


def _is_target_sector(sector: str, title_lower: str, buyer_lower: str) -> bool:
    """Target sectors for ReqPOOL: Energie + Industrie (Immobilien/Telko/Rohstoffe),
    or sector-specific title topics."""
    if sector == "Energie":
        return True
    if sector == "Industrie":
        return True
    return any(kw in title_lower for kw in _SECTOR_TITLE_KEYWORDS)


# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_entry(entry: dict) -> dict:
    """Score a single entry for ReqPOOL relevance.

    One hard gate:
      1. Context Gate: CPV code (72xxx/794xx) OR title IT/consulting keywords

    Then four weighted tiers:
      2. Role Matching (max 50)
      3. ReqPOOL Fit Bonus (max 20)
      4. Sector Bonus (max 20) — weighted, not a hard gate
      5. Context Bonus (max 10)

    Returns dict with 'score' (0-100), 'matched_roles', 'sector',
    'buyer_type' and 'score_breakdown'.
    """
    title_lower = entry.get("title", "").lower()
    buyer_lower = entry.get("buyer", "").lower()
    cpv_codes = entry.get("cpv") or []
    text = f"{title_lower} {buyer_lower}"

    sector, buyer_type = classify_sector(title_lower, buyer_lower)

    # Gate 1: IT/Consulting Context — CPV or title keywords
    context_kw = _has_context_keywords(title_lower)
    context_cpv = _has_context_cpv(cpv_codes)
    if not context_kw and not context_cpv:
        return {
            "score": 0,
            "matched_roles": [],
            "sector": sector,
            "buyer_type": buyer_type,
            "score_breakdown": {"context": False, "sector": False},
        }

    # Tier 2: Role Matching
    matched_roles = []
    total_keyword_hits = 0
    for role, keywords in ROLE_KEYWORDS.items():
        role_hits = sum(1 for kw in keywords if kw in text)
        if role_hits > 0:
            matched_roles.append(role)
            total_keyword_hits += role_hits

    role_score = min(50, len(matched_roles) * 10 + total_keyword_hits * 4)

    # Tier 3: ReqPOOL Fit Bonus
    fit_hits = sum(1 for kw in _REQPOOL_FIT_KEYWORDS if kw in text)
    fit_bonus = min(20, fit_hits * 8)

    # Tier 4: Sector Bonus — weighted instead of hard gate (P3)
    is_target = _is_target_sector(sector, title_lower, buyer_lower)
    sector_bonus = 0
    if _is_known_buyer(buyer_lower):
        sector_bonus += 12
    elif sector in ("Energie", "Industrie"):
        sector_bonus += 6
    if any(kw in title_lower for kw in _SECTOR_TITLE_KEYWORDS):
        sector_bonus += 8
    sector_bonus = min(20, sector_bonus)

    # Tier 5: Context Bonus — reward strong IT context signals
    context_bonus = 0
    if context_cpv:
        context_bonus += 6
    if context_kw:
        context_bonus += 4

    raw_score = role_score + fit_bonus + sector_bonus + context_bonus
    final_score = min(100, raw_score)

    return {
        "score": final_score,
        "matched_roles": matched_roles,
        "sector": sector,
        "buyer_type": buyer_type,
        "score_breakdown": {
            "context": True,
            "sector": is_target,
            "role_score": role_score,
            "fit_bonus": fit_bonus,
            "sector_bonus": sector_bonus,
            "context_bonus": context_bonus,
        },
    }


def score_entries(entries: list[dict]) -> list[dict]:
    """Score all entries and attach relevance fields in-place."""
    for entry in entries:
        result = score_entry(entry)
        entry["relevance_score"] = result["score"]
        entry["matched_roles"] = result["matched_roles"]
        entry["sector"] = result["sector"]
        entry["buyer_type"] = result["buyer_type"]
    return entries
