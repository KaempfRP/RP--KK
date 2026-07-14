"""Tender Scout — Main entry point.

Orchestrates the full pipeline: fetch sources, deduplicate,
score, summarize, render HTML page, and report results.
"""

import logging

from src.ted_api import fetch_ted
from src.rss_sources import fetch_rss_sources
from src.dedup import init_db, filter_new, save_seen, get_stored_summaries, save_summaries
from src.scoring import score_entries
from src.summarizer import summarize_entries
from src.render import render_page

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("tender-scout")


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

    # 4. Merge all results
    all_results = ted_results + rss_results

    # 5. Deduplicate
    new_results = filter_new(all_results)
    logger.info("Neue Einträge: %d", len(new_results))

    # 6. Save new entries
    save_seen(new_results)

    # 7. Score entries (needed before summarization)
    score_entries(all_results)

    # 8. Generate AI summaries for high-relevance entries
    stored_summaries = get_stored_summaries()
    summaries = summarize_entries(all_results, stored_summaries)
    new_summaries = {k: v for k, v in summaries.items() if k not in stored_summaries}
    save_summaries(new_summaries)
    logger.info(
        "Summaries: %d gesamt, %d neu generiert",
        len(summaries), len(new_summaries),
    )

    # 9. Render HTML page
    new_ids = {e["id"] for e in new_results}
    output_path = render_page(all_results, new_ids, summaries=summaries)
    logger.info("HTML generiert: %s", output_path)

    # 10. Summary
    logger.info(
        "Zusammenfassung: %d TED, %s — %d neu",
        len(ted_results),
        ", ".join(f"{c} {s}" for s, c in sorted(source_counts.items())),
        len(new_results),
    )


if __name__ == "__main__":
    main()
