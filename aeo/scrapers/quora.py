"""
Quora scraper via Google search (site:quora.com).
Quora's own site blocks headless scrapers, so we search Google for recent
Quora questions and parse the search result snippets.
"""
import httpx
import time
import hashlib
from typing import List, Dict, Any
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from ._common import google_lookback_tbs

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _stable_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def scrape(topic_slug: str, keywords: List[str], lookback_hours: int = 25) -> List[Dict[str, Any]]:
    results = []
    seen_ids = set()
    tbs = google_lookback_tbs(lookback_hours)

    queries = keywords[:6]

    with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:
        for query in queries:
            try:
                search_query = f"site:quora.com {query}"
                params = {
                    "q": search_query,
                    "num": 10,
                    "tbs": tbs,
                }
                resp = client.get("https://www.google.com/search", params=params)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")
                for g in soup.select("div.g"):
                    a_tag = g.select_one("a[href]")
                    if not a_tag:
                        continue
                    href = a_tag["href"]
                    if "quora.com" not in href:
                        continue

                    h3 = g.select_one("h3")
                    title = h3.get_text(strip=True) if h3 else ""
                    snippet_el = g.select_one("div.VwiC3b") or g.select_one("span.aCOpRe")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    if not title or not _matches_keywords(title + " " + snippet, keywords):
                        continue

                    q_id = _stable_id(href)
                    if q_id in seen_ids:
                        continue
                    seen_ids.add(q_id)

                    results.append({
                        "platform": "quora",
                        "question_id": q_id,
                        "question_title": title,
                        "question_url": href,
                        "body": snippet[:500],
                        "created_at": datetime.now(tz=timezone.utc).isoformat(),
                        "topic_slug": topic_slug,
                        "score": 0,
                    })

                time.sleep(2.0)  # be polite to Google
            except Exception:
                continue

    return results
