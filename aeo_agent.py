#!/usr/bin/env python3
"""
Confluent AEO Monitoring Agent
Runs daily: scrapes Reddit/SO/HN/Quora/GitHub, deduplicates, drafts answers,
sends Slack digest at 7 PM IST.
"""
import os
import sys
import logging
import argparse
from dotenv import load_dotenv

load_dotenv()

from aeo.config import TOPICS, DAILY_QUESTION_LIMIT
from aeo.filter import init_db, filter_new, mark_notified, save_answer
from aeo.answer_drafter import draft_answer
from aeo.slack_notifier import send_digest
from aeo.scrapers import reddit, stackoverflow, hackernews, quora, github_discussions

LOG_FILE = os.getenv("AEO_LOG_FILE", "aeo_agent.log")
LOG_LEVEL = os.getenv("AEO_LOG_LEVEL", "INFO").upper()
DB_PATH = os.getenv("AEO_DB_PATH", "aeo_agent.db")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


def run(dry_run: bool = False) -> None:
    log.info("=== Confluent AEO Agent starting ===")
    dry_run = dry_run or os.getenv("AEO_DRY_RUN", "false").lower() == "true"

    conn = init_db(DB_PATH)

    # --- Scrape all platforms for all topics ---
    scrapers = [
        ("reddit", reddit.scrape),
        ("stackoverflow", stackoverflow.scrape),
        ("hackernews", hackernews.scrape),
        ("quora", quora.scrape),
        ("github", github_discussions.scrape),
    ]

    # 72h window — wide enough to catch niche topics on low-volume platforms.
    # Dedup via SQLite ensures we never surface the same question twice.
    lookback_hours = int(os.getenv("AEO_LOOKBACK_HOURS", "72"))

    all_raw: list = []
    for topic in TOPICS:
        log.info(f"Scraping topic: {topic.name}")
        for platform_name, scrape_fn in scrapers:
            try:
                results = scrape_fn(topic.slug, topic.keywords, lookback_hours)
                log.info(f"  [{platform_name}] {len(results)} raw results")
                all_raw.extend(results)
            except Exception as e:
                log.warning(f"  [{platform_name}] scraper error: {e}")

    log.info(f"Total raw results: {len(all_raw)}")

    # --- Deduplicate and select top questions ---
    new_questions = filter_new(all_raw, conn, DAILY_QUESTION_LIMIT)
    log.info(f"New questions after dedup + ranking: {len(new_questions)}")

    if not new_questions:
        log.info("No new questions today. Sending empty digest notification.")
        if not dry_run:
            send_digest([], dry_run=False)
        return

    # --- Draft answers ---
    for q in new_questions:
        topic = next((t for t in TOPICS if t.slug == q.get("topic_slug")), None)
        doc_url = topic.doc_url if topic else ""
        log.info(f"Drafting answer for: {q.get('question_title', '')[:60]}...")
        try:
            answer = draft_answer(q, doc_url)
            q["answer_drafted"] = answer
            if not dry_run:
                save_answer(q["question_id"], answer, conn)
        except Exception as e:
            log.warning(f"  Answer drafting failed: {e}")
            q["answer_drafted"] = ""

    # --- Send Slack digest ---
    log.info("Sending Slack digest...")
    success = send_digest(new_questions, dry_run=dry_run)

    if success and not dry_run:
        mark_notified([q["question_id"] for q in new_questions], conn)
        log.info(f"Marked {len(new_questions)} questions as notified.")

    log.info("=== AEO Agent run complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Confluent AEO Monitoring Agent")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print digest to terminal instead of sending to Slack",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Override daily question limit (default: 10)",
    )
    args = parser.parse_args()

    if args.limit:
        import aeo.config as cfg
        cfg.DAILY_QUESTION_LIMIT = args.limit

    run(dry_run=args.dry_run)
