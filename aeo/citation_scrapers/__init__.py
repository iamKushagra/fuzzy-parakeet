"""
Citation scrapers — find external forum threads that link to docs.confluent.io.

Mirrors the structure of aeo/scrapers/ but the unit of capture is different:
each row represents a *thread that cited a docs page*, not a question to answer.

Each platform module exposes:
    scrape_citations(domain: str = "docs.confluent.io",
                     lookback_hours: int = 720) -> list[dict]

Returned dicts have the shape consumed by aeo.citations.persist_citations().
"""
import re
from typing import List

# Captures docs.confluent.io URLs in raw text. Stops at whitespace, common
# punctuation, and quote characters so we don't grab trailing periods/parens.
_URL_RE = re.compile(
    r'https?://docs\.confluent\.io/[^\s<>"\'\)\]\}]+',
    re.IGNORECASE,
)


def extract_doc_urls(text: str, domain: str = "docs.confluent.io") -> List[str]:
    """Return all docs.confluent.io URLs found in `text`, deduped, in order.

    The `domain` arg is reserved for a future v2 that tracks
    developer.confluent.io / confluent.io/blog as well; for now any value
    other than the default is honored by simply substituting the host in
    the precompiled regex.
    """
    if not text:
        return []
    if domain == "docs.confluent.io":
        matches = _URL_RE.findall(text)
    else:
        rx = re.compile(
            rf'https?://{re.escape(domain)}/[^\s<>"\'\)\]\}}]+',
            re.IGNORECASE,
        )
        matches = rx.findall(text)
    seen, ordered = set(), []
    for u in matches:
        # Strip common trailing punctuation that the regex may include.
        u = u.rstrip(".,;:!?")
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return ordered


def context_around(text: str, url: str, window: int = 240) -> str:
    """Return up to ~`window` chars centered on the first occurrence of `url`."""
    if not text or not url:
        return ""
    idx = text.find(url)
    if idx < 0:
        return text[:window].strip()
    half = window // 2
    start = max(0, idx - half)
    end = min(len(text), idx + len(url) + half)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet
