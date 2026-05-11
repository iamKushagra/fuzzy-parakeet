import sqlite3
import math
from typing import List, Dict, Any
from datetime import datetime, timezone

from .config import TOPICS, DAILY_QUESTION_LIMIT

DB_PATH = "aeo_agent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_questions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    platform         TEXT NOT NULL,
    question_id      TEXT NOT NULL,
    question_url     TEXT NOT NULL,
    question_title   TEXT NOT NULL,
    topic_slug       TEXT NOT NULL,
    priority         TEXT NOT NULL DEFAULT 'normal',
    first_seen_date  TEXT NOT NULL,
    source_created_at TEXT,
    answer_drafted   TEXT,
    notified         INTEGER NOT NULL DEFAULT 0,
    posted           INTEGER NOT NULL DEFAULT 0,
    posted_at        TEXT,
    posted_url       TEXT,
    UNIQUE(platform, question_id)
);

CREATE TABLE IF NOT EXISTS aeo_scores (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_slug TEXT NOT NULL,
    score      REAL NOT NULL,
    recorded_date TEXT NOT NULL,
    note       TEXT,
    UNIQUE(topic_slug, recorded_date)
);
"""


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    # Migrate older DBs that may be missing source_created_at
    existing = {r[1] for r in conn.execute("PRAGMA table_info(seen_questions)")}
    if "source_created_at" not in existing:
        conn.execute("ALTER TABLE seen_questions ADD COLUMN source_created_at TEXT")
    conn.commit()
    return conn


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _recency_score(created_at: str) -> int:
    """Boost newer items. Items from Jan 2026 onward (the spec's target window)
    sit roughly in the <180d bucket; older items still earn some recency credit
    but the impact_score below is what lets very old highly-engaged questions
    surface."""
    dt = _parse_iso(created_at)
    if not dt:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (datetime.now(tz=timezone.utc) - dt).total_seconds() / 86400.0)
    if age_days < 1:    return 40
    if age_days < 7:    return 35
    if age_days < 30:   return 28
    if age_days < 90:   return 20
    if age_days < 180:  return 12
    if age_days < 365:  return 5
    return 0


def _impact_score(question: Dict[str, Any]) -> int:
    """Engagement-based boost — upvotes, points, +1 reactions, answer counts.
    Lets older-but-highly-engaged questions outrank fresh-but-low-signal ones.

    Logarithmic so a 1000-vote SO post doesn't dominate everything:
      score=0    -> 0
      score=5    -> ~12
      score=25   -> ~23
      score=100  -> ~33
      score=500  -> ~45
    Plus a smaller boost from answer_count signaling discussion volume.
    """
    raw_score = int(question.get("score") or 0)
    answer_count = int(question.get("answer_count") or 0)
    pts = 0
    if raw_score > 0:
        pts += min(50, int(math.log2(raw_score + 1) * 5))
    if answer_count > 0:
        pts += min(20, int(math.log2(answer_count + 1) * 4))
    return pts


def _is_high_priority(question: Dict[str, Any]) -> bool:
    topic_slug = question.get("topic_slug", "")
    topic = next((t for t in TOPICS if t.slug == topic_slug), None)
    if not topic:
        return False
    text = (question.get("question_title", "") + " " + question.get("body", "")).lower()
    return any(p.lower() in text for p in topic.priority_patterns)


def _score_question(question: Dict[str, Any]) -> int:
    """Higher = more relevant. Used for ranking within the daily limit."""
    score = 0
    if _is_high_priority(question):
        score += 100
    # Platform weights reflect AEO-citation-rate research:
    # Reddit (46.5% Perplexity citation rate) and StackOverflow are the
    # highest-leverage sources for AI-engine answers about Kafka.
    platform_weights = {
        "reddit": 35,
        "stackoverflow": 32,
        "hackernews": 22,
        "github": 18,
        "quora": 12,
    }
    score += platform_weights.get(question.get("platform", ""), 0)
    if not question.get("is_answered", False) and question.get("answer_count", 0) == 0:
        score += 15
    score += _recency_score(question.get("created_at", ""))
    score += _impact_score(question)
    return score


def filter_new(
    questions: List[Dict[str, Any]],
    conn: sqlite3.Connection,
    daily_limit: int = DAILY_QUESTION_LIMIT,
) -> List[Dict[str, Any]]:
    """
    Remove already-seen questions, attach priority flag, rank, and cap to daily_limit.
    Also persists new questions to DB (without answer yet).
    """
    new_questions = []
    seen_in_run: set = set()

    for q in questions:
        platform = q.get("platform", "")
        question_id = q.get("question_id", "")
        if not platform or not question_id:
            continue

        # In-run dedup: same question may match keywords across multiple
        # topics (e.g. one SO post tagged for both Flink and CDC). Keep the
        # first occurrence so it shows up once in the digest.
        key = (platform, question_id)
        if key in seen_in_run:
            continue
        seen_in_run.add(key)

        existing = conn.execute(
            "SELECT id FROM seen_questions WHERE platform=? AND question_id=?",
            (platform, question_id),
        ).fetchone()

        if existing:
            continue

        q["is_high_priority"] = _is_high_priority(q)
        q["rank_score"] = _score_question(q)
        new_questions.append(q)

    # Rank: priority + score primarily, recency as a secondary tiebreak.
    # _score_question already includes a recency bonus, but for items at the
    # same score we want the visibly-fresher one to win.
    def _sort_key(q: Dict[str, Any]):
        dt = _parse_iso(q.get("created_at", "")) or datetime.fromtimestamp(0, tz=timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (q["rank_score"], dt.timestamp())
    new_questions.sort(key=_sort_key, reverse=True)
    selected = new_questions[:daily_limit]

    now = datetime.now(tz=timezone.utc).isoformat()
    for q in selected:
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO seen_questions
                    (platform, question_id, question_url, question_title, topic_slug,
                     priority, first_seen_date, source_created_at, notified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    q.get("platform"),
                    q.get("question_id"),
                    q.get("question_url", ""),
                    q.get("question_title", ""),
                    q.get("topic_slug", ""),
                    "high" if q.get("is_high_priority") else "normal",
                    now,
                    q.get("created_at", ""),
                ),
            )
        except Exception:
            continue
    conn.commit()

    return selected


def mark_notified(question_ids: List[str], conn: sqlite3.Connection) -> None:
    for qid in question_ids:
        conn.execute(
            "UPDATE seen_questions SET notified=1 WHERE question_id=?", (qid,)
        )
    conn.commit()


def save_answer(question_id: str, answer: str, conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE seen_questions SET answer_drafted=? WHERE question_id=?",
        (answer, question_id),
    )
    conn.commit()
