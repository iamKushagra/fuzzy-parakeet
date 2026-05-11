import httpx
import time
from typing import List, Dict, Any
from datetime import datetime, timezone

BASE = "https://api.stackexchange.com/2.3"


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def scrape(topic_slug: str, keywords: List[str], lookback_hours: int = 25) -> List[Dict[str, Any]]:
    results = []
    seen_ids = set()
    cutoff_ts = int(time.time()) - (lookback_hours * 3600)

    queries = keywords[:8]

    with httpx.Client(timeout=15) as client:
        for query in queries:
            try:
                params = {
                    "order": "desc",
                    "sort": "creation",
                    "q": query,
                    "site": "stackoverflow",
                    "fromdate": cutoff_ts,
                    "pagesize": 20,
                    "filter": "withbody",
                }
                resp = client.get(f"{BASE}/search/advanced", params=params)
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("items", []):
                    q_id = str(item.get("question_id", ""))
                    if not q_id or q_id in seen_ids:
                        continue
                    title = item.get("title", "")
                    body = item.get("body", "")
                    if not _matches_keywords(title + " " + body, keywords):
                        continue

                    seen_ids.add(q_id)
                    results.append({
                        "platform": "stackoverflow",
                        "question_id": q_id,
                        "question_title": title,
                        "question_url": item.get("link", ""),
                        "body": body[:500] if body else "",
                        "created_at": datetime.fromtimestamp(
                            item.get("creation_date", 0), tz=timezone.utc
                        ).isoformat(),
                        "topic_slug": topic_slug,
                        "tags": item.get("tags", []),
                        "score": item.get("score", 0),
                        "answer_count": item.get("answer_count", 0),
                        "is_answered": item.get("is_answered", False),
                    })

                time.sleep(1.0)
            except Exception:
                continue

    return results
