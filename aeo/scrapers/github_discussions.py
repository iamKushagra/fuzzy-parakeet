"""
GitHub Discussions scraper.
Uses GitHub REST search API (issues endpoint also indexes discussions).
Falls back gracefully if rate-limited (60 req/hour unauthenticated).
Set GITHUB_TOKEN in .env for 5000 req/hour.
"""
import httpx
import os
import time
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta

from ..config import GITHUB_REPOS

BASE = "https://api.github.com"


def _get_headers() -> dict:
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def scrape(topic_slug: str, keywords: List[str], lookback_hours: int = 25) -> List[Dict[str, Any]]:
    results = []
    seen_ids = set()
    cutoff_dt = datetime.now(tz=timezone.utc) - timedelta(hours=lookback_hours)
    cutoff_str = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Cap repos to 4 to stay within GitHub's query length limit and 60 req/hr rate.
    # Add GITHUB_TOKEN to .env to raise limit to 5000 req/hr.
    repo_filter = " ".join(f"repo:{r}" for r in GITHUB_REPOS[:4])
    queries = keywords[:3]

    with httpx.Client(headers=_get_headers(), timeout=15) as client:
        for query in queries:
            try:
                # GitHub REST search covers issues & PRs; discussions aren't
                # indexed here but issues in these repos capture the same intent.
                search_q = f"{query} {repo_filter} created:>={cutoff_str}"
                params = {"q": search_q, "per_page": 15, "sort": "created", "order": "desc"}
                resp = client.get(f"{BASE}/search/issues", params=params)

                if resp.status_code == 403:
                    # Rate limited — stop gracefully
                    break
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("items", []):
                    item_id = str(item.get("id", ""))
                    if not item_id or item_id in seen_ids:
                        continue
                    title = item.get("title", "")
                    body = (item.get("body") or "")[:500]
                    if not _matches_keywords(title + " " + body, keywords):
                        continue

                    seen_ids.add(item_id)
                    repo_url = item.get("repository_url", "")
                    repo_name = repo_url.replace(f"{BASE}/repos/", "") if repo_url else ""

                    results.append({
                        "platform": "github",
                        "question_id": item_id,
                        "question_title": title,
                        "question_url": item.get("html_url", ""),
                        "body": body,
                        "created_at": item.get("created_at", ""),
                        "topic_slug": topic_slug,
                        "repo": repo_name,
                        "score": item.get("reactions", {}).get("+1", 0),
                        "answer_count": item.get("comments", 0),
                    })

                time.sleep(1.0)
            except Exception:
                continue

    return results
