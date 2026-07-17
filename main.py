"""Tender Scout — Main entry point.

Orchestrates the full pipeline: fetch sources, deduplicate,
score, render HTML page, and report results.
"""

import logging
from datetime import datetime, timezone

from src.ted_api import fetch_ted
from src.rss_sources import fetch_rss_sources
from src.dedup import init_db, filter_new, store_entries, get_all_entries
from src.scoring import score_entries
from src.render import render_page, normalize_date_for_sort

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tender-scout")

# How long a tender with no parseable deadline stays on the page after
# it was first seen (open-ended notices should not accumulate forever).
NO_DEADLINE_GRACE_DAYS = 30


def is_active(entry: dict, today) -> bool:
    """Keep a tender until its deadline passes (or, if the deadline is
    unknown, for a grace period after it was first seen)."""
    deadline_iso = normalize_date_for_sort(entry.get("deadline", ""))
    if not deadline_iso.startswith("1970"):
        try:
            deadline = datetime.strptime(deadline_iso[:10], "%Y-%m-%d").date()
            return deadline >= today
        except ValueError:
            pass
    # No usable deadline — fall back to first_seen recency
    first_seen = entry.get("first_seen", "")
    try:
        seen_date = datetime.fromisoformat(first_seen).date()
        return (today - seen_date).days <= NO_DEADLINE_GRACE_DAYS
    except (ValueError, TypeError):
        return True


def main() -> None:
    """Run the full tender scout pipeline."""
    logger.info("Tender Scout gestartet")

    # 1. Initialize database (includes schema migration)
    init_db()

    # 2. Fetch from TED API
    logger.info("Fetching TED Europa...")
    ted_results = fetch_ted()
    logger.info("TED: %d Ergebnisse", len(ted_results))

    # 3. Fetch from other sources
    logger.info("Fetching weitere Quellen...")
    rss_results = fetch_rss_sources()

    source_counts = {}
    for entry in rss_results:
        source_counts[entry["source"]] = source_counts.get(entry["source"], 0) + 1
    for source, count in sorted(source_counts.items()):
        logger.info("%s: %d Ergebnisse", source, count)

    # 4. Merge this run's fetch
    fetched = ted_results + rss_results

    # 5. Which of the fetched entries are genuinely new (for the NEU badge)?
    new_results = filter_new(fetched)
    logger.info("Neue Einträge: %d", len(new_results))

    # 6. Persist full data of everything fetched (insert new, refresh existing)
    store_entries(fetched)

    # 7. Load ALL stored tenders and keep the ones still open —
    #    this is what makes the page show every open tender, not just
    #    the current fetch window.
    today = datetime.now(timezone.utc).date()
    all_stored = get_all_entries()
    all_results = [e for e in all_stored if is_active(e, today)]
    logger.info(
        "Gespeichert: %d, davon offen (angezeigt): %d",
        len(all_stored), len(all_results),
    )

    # 8. Score entries
    score_entries(all_results)

    # 9. Render HTML page
    new_ids = {e["id"] for e in new_results}
    output_path = render_page(all_results, new_ids)
    logger.info("HTML generiert: %s", output_path)

    # 10. Summary
    logger.info(
        "Zusammenfassung: %d TED, %s — %d neu, %d offen angezeigt",
        len(ted_results),
        ", ".join(f"{c} {s}" for s, c in sorted(source_counts.items())),
        len(new_results),
        len(all_results),
    )


if __name__ == "__main__":
    main()
