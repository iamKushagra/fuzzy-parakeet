"""
Reddit scraper.
Reddit's API now requires OAuth for all search operations.
Primary strategy: Google search site:reddit.com (no auth needed).
Fallback: subreddit RSS feeds (no auth, but less targeted).
"""
import httpx
import time
import xml.etree.ElementTree as ET
import hashlib
from typing import List, Dict, Any
from datetime import datetime, timezone

from ..config import REDDIT_SUBREDDITS
from ._common import google_lookback_tbs

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": _UA,
    "Accept-Language": "en-US,en;q=0.9",
}


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _stable_id(url: str) -> str:
    return "r_" + hashlib.md5(url.encode()).hexdigest()[:16]


def _parse_rss(xml_text: str, topic_slug: str, keywords: List[str],
               cutoff_ts: float, subreddit: str) -> List[Dict]:
    results = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            updated_el = entry.find("atom:updated", ns)
            content_el = entry.find("atom:content", ns)

            title = title_el.text if title_el is not None else ""
            url = link_el.attrib.get("href", "") if link_el is not None else ""
            updated_str = updated_el.text if updated_el is not None else ""
            body = content_el.text if content_el is not None else ""

            if not url or not title:
                continue
            if not _matches_keywords(title + " " + (body or ""), keywords):
                continue

            try:
                dt = datetime.fromisoformat(updated_str.replace("Z", "+00:00"))
                if dt.timestamp() < cutoff_ts:
                    continue
                created_at = dt.isoformat()
            except Exception:
                created_at = datetime.now(tz=timezone.utc).isoformat()

            post_id = _stable_id(url)
            results.append({
                "platform": "reddit",
                "question_id": post_id,
                "question_title": title,
                "question_url": url,
                "body": (body or "")[:500],
                "created_at": created_at,
                "topic_slug": topic_slug,
                "subreddit": subreddit,
                "score": 0,
            })
    except Exception:
        pass
    return results


def scrape(topic_slug: str, keywords: List[str], lookback_hours: int = 72) -> List[Dict[str, Any]]:
    from bs4 import BeautifulSoup

    results = []
    seen_ids: set = set()
    cutoff_ts = time.time() - (lookback_hours * 3600)
    tbs = google_lookback_tbs(lookback_hours)

    # Narrow to most relevant subreddits for Google search
    subreddit_filter = " OR ".join(
        f"site:reddit.com/r/{s}" for s in REDDIT_SUBREDDITS[:4]
    )

    with httpx.Client(headers=HEADERS, timeout=15, follow_redirects=True) as client:

        # --- Strategy 1: Google search site:reddit.com ---
        for query in keywords[:6]:  # widened to surface more candidates; throttle below mitigates Google rate-limit risk
            try:
                search_q = f"({subreddit_filter}) {query}"
                params = {"q": search_q, "num": 10, "tbs": tbs}
                resp = client.get("https://www.google.com/search", params=params)
                if resp.status_code in (429, 302) and "sorry" in resp.url.path:
                    break  # rate limited; skip to RSS fallback

                soup = BeautifulSoup(resp.text, "html.parser")
                for g in soup.select("div.g"):
                    a_tag = g.select_one("a[href]")
                    if not a_tag:
                        continue
                    href = a_tag["href"]
                    if "reddit.com" not in href or "/comments/" not in href:
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

                    # Extract subreddit from URL
                    parts = href.split("/")
                    sub = parts[parts.index("r") + 1] if "r" in parts else ""

                    results.append({
                        "platform": "reddit",
                        "question_id": q_id,
                        "question_title": title,
                        "question_url": href,
                        "body": snippet[:500],
                        "created_at": datetime.now(tz=timezone.utc).isoformat(),
                        "topic_slug": topic_slug,
                        "subreddit": sub,
                        "score": 0,
                    })

                time.sleep(2.5)  # polite delay for Google
            except Exception:
                continue

        # --- Strategy 2: RSS fallback for top subreddits ---
        if not results:
            rss_ua = "python:com.confluent.aeo-monitor:v1.0 (educational research)"
            for sub in REDDIT_SUBREDDITS[:3]:
                try:
                    rss_url = f"https://www.reddit.com/r/{sub}/new.rss"
                    resp = client.get(rss_url, headers={**HEADERS, "User-Agent": rss_ua,
                                                        "Accept": "application/rss+xml"})
                    if resp.status_code != 200:
                        continue
                    parsed = _parse_rss(resp.text, topic_slug, keywords, cutoff_ts, sub)
                    for item in parsed:
                        if item["question_id"] not in seen_ids:
                            seen_ids.add(item["question_id"])
                            results.append(item)
                    time.sleep(1.5)
                except Exception:
                    continue

    return results
