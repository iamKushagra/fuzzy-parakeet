import httpx
import time
from typing import List, Dict, Any
from datetime import datetime, timezone

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def scrape(topic_slug: str, keywords: List[str], lookback_hours: int = 25) -> List[Dict[str, Any]]:
    results = []
    seen_ids = set()
    cutoff_ts = int(time.time()) - (lookback_hours * 3600)

    queries = keywords[:5]

    with httpx.Client(timeout=15) as client:
        for query in queries:
            try:
                params = {
                    "query": query,
                    "tags": "(story,ask_hn,show_hn)",
                    "numericFilters": f"created_at_i>={cutoff_ts}",
                    "hitsPerPage": 20,
                }
                resp = client.get(f"{ALGOLIA_BASE}/search", params=params)
                resp.raise_for_status()
                data = resp.json()

                for hit in data.get("hits", []):
                    obj_id = hit.get("objectID", "")
                    if not obj_id or obj_id in seen_ids:
                        continue
                    title = hit.get("title", "") or hit.get("story_title", "")
                    text = hit.get("story_text", "") or hit.get("comment_text", "") or ""
                    if not _matches_keywords(title + " " + text, keywords):
                        continue

                    seen_ids.add(obj_id)
                    created_raw = hit.get("created_at", "")
                    results.append({
                        "platform": "hackernews",
                        "question_id": obj_id,
                        "question_title": title,
                        "question_url": f"https://news.ycombinator.com/item?id={obj_id}",
                        "body": text[:500],
                        "created_at": created_raw,
                        "topic_slug": topic_slug,
                        "score": hit.get("points", 0) or 0,
                        "author": hit.get("author", ""),
                    })

                time.sleep(0.5)
            except Exception:
                continue

    return results
