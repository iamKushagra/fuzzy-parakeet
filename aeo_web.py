#!/usr/bin/env python3
"""
Confluent AEO Dashboard — Flask backend
Run: source .venv/bin/activate && python3 aeo_web.py
"""
import os
import sqlite3
from datetime import datetime, timezone
from flask import Flask, jsonify, request, render_template, abort
from dotenv import load_dotenv

load_dotenv()

# Resolve paths relative to this file so the server works from any cwd
_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.getenv("AEO_DB_PATH", os.path.join(_HERE, "aeo_agent.db"))

app = Flask(__name__,
            template_folder=os.path.join(_HERE, "templates"),
            static_folder=os.path.join(_HERE, "static"))


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Ensure schema exists (handles first-run before agent has run)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS seen_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL,
            question_id TEXT NOT NULL,
            question_url TEXT NOT NULL,
            question_title TEXT NOT NULL,
            topic_slug TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'normal',
            first_seen_date TEXT NOT NULL,
            answer_drafted TEXT,
            notified INTEGER NOT NULL DEFAULT 0,
            posted INTEGER NOT NULL DEFAULT 0,
            posted_at TEXT,
            posted_url TEXT,
            UNIQUE(platform, question_id)
        );
        CREATE TABLE IF NOT EXISTS aeo_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_slug TEXT NOT NULL,
            score REAL NOT NULL,
            recorded_date TEXT NOT NULL,
            note TEXT,
            UNIQUE(topic_slug, recorded_date)
        );
        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT NOT NULL,
            run_date TEXT,
            question_count INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL
        );
    """)
    # Migrate older DBs that are missing the new columns
    existing = {r[1] for r in conn.execute("PRAGMA table_info(seen_questions)")}
    for col, defn in [("posted", "INTEGER NOT NULL DEFAULT 0"),
                      ("posted_at", "TEXT"),
                      ("posted_url", "TEXT")]:
        if col not in existing:
            conn.execute(f"ALTER TABLE seen_questions ADD COLUMN {col} {defn}")
    conn.commit()
    return conn


TOPIC_NAMES = {
    "managed_kafka":        "Managed Kafka Comparison",
    "mq_replacement":       "MQ → Kafka Migration",
    "realtime_pipelines":   "Real-Time Pipelines",
    "flink_stream_processing": "Flink / ksqlDB",
    "connectors_cdc":       "Connectors & CDC",
}

BASELINE_SCORES = {
    "managed_kafka": 10,
    "mq_replacement": 0,
    "realtime_pipelines": 35,
    "flink_stream_processing": 0,
    "connectors_cdc": 32,
}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stats")
def stats():
    db = get_db()

    total = db.execute("SELECT COUNT(*) FROM seen_questions").fetchone()[0]
    high  = db.execute("SELECT COUNT(*) FROM seen_questions WHERE priority='high'").fetchone()[0]
    posted = db.execute("SELECT COUNT(*) FROM seen_questions WHERE posted=1").fetchone()[0]
    unanswered = db.execute(
        "SELECT COUNT(*) FROM seen_questions WHERE answer_drafted IS NULL OR answer_drafted=''"
    ).fetchone()[0]

    by_topic = {
        row["topic_slug"]: row["cnt"]
        for row in db.execute(
            "SELECT topic_slug, COUNT(*) as cnt FROM seen_questions GROUP BY topic_slug"
        )
    }

    by_platform = {
        row["platform"]: row["cnt"]
        for row in db.execute(
            "SELECT platform, COUNT(*) as cnt FROM seen_questions GROUP BY platform"
        )
    }

    # Recent 7 days activity
    daily = [
        {"date": row["day"], "count": row["cnt"]}
        for row in db.execute(
            """SELECT date(first_seen_date) as day, COUNT(*) as cnt
               FROM seen_questions
               WHERE first_seen_date >= date('now', '-7 days')
               GROUP BY day ORDER BY day"""
        )
    ]

    return jsonify({
        "total": total,
        "high_priority": high,
        "posted": posted,
        "unanswered": unanswered,
        "by_topic": by_topic,
        "by_platform": by_platform,
        "daily_activity": daily,
        "topic_names": TOPIC_NAMES,
    })


@app.route("/api/questions")
def questions():
    db = get_db()

    topic    = request.args.get("topic", "")
    platform = request.args.get("platform", "")
    priority = request.args.get("priority", "")
    posted   = request.args.get("posted", "")
    search   = request.args.get("q", "")
    page     = max(1, int(request.args.get("page", 1)))
    per_page = 20

    where, params = [], []
    if topic:    where.append("topic_slug=?");    params.append(topic)
    if platform: where.append("platform=?");      params.append(platform)
    if priority: where.append("priority=?");      params.append(priority)
    if posted == "yes": where.append("posted=1")
    if posted == "no":  where.append("posted=0")
    if search:
        where.append("question_title LIKE ?")
        params.append(f"%{search}%")

    clause = ("WHERE " + " AND ".join(where)) if where else ""

    total_rows = db.execute(
        f"SELECT COUNT(*) FROM seen_questions {clause}", params
    ).fetchone()[0]

    rows = db.execute(
        f"""SELECT id, platform, question_id, question_url, question_title,
                   topic_slug, priority, first_seen_date, source_created_at,
                   answer_drafted, notified, posted, posted_at, posted_url
            FROM seen_questions {clause}
            ORDER BY
                CASE priority WHEN 'high' THEN 0 ELSE 1 END,
                COALESCE(source_created_at, first_seen_date) DESC
            LIMIT ? OFFSET ?""",
        params + [per_page, (page - 1) * per_page],
    ).fetchall()

    return jsonify({
        "total": total_rows,
        "page": page,
        "per_page": per_page,
        "questions": [dict(r) for r in rows],
        "topic_names": TOPIC_NAMES,
    })


@app.route("/api/questions/<question_id>/mark-posted", methods=["POST"])
def mark_posted(question_id):
    db = get_db()
    data = request.get_json(silent=True) or {}
    posted_url = data.get("posted_url", "")
    now = datetime.now(tz=timezone.utc).isoformat()

    cur = db.execute(
        "UPDATE seen_questions SET posted=1, posted_at=?, posted_url=? WHERE question_id=?",
        (now, posted_url, question_id),
    )
    db.commit()
    if cur.rowcount == 0:
        abort(404)
    return jsonify({"ok": True})


@app.route("/api/questions/<question_id>/unmark-posted", methods=["POST"])
def unmark_posted(question_id):
    db = get_db()
    db.execute(
        "UPDATE seen_questions SET posted=0, posted_at=NULL, posted_url=NULL WHERE question_id=?",
        (question_id,),
    )
    db.commit()
    return jsonify({"ok": True})


@app.route("/api/aeo-scores", methods=["GET"])
def get_aeo_scores():
    db = get_db()
    rows = db.execute(
        "SELECT topic_slug, score, recorded_date, note FROM aeo_scores ORDER BY recorded_date"
    ).fetchall()
    scores = [dict(r) for r in rows]

    # Seed baseline scores (May 2026) if table is empty
    if not scores:
        baseline_date = "2026-05-05"
        for slug, val in BASELINE_SCORES.items():
            try:
                db.execute(
                    "INSERT OR IGNORE INTO aeo_scores (topic_slug, score, recorded_date, note) VALUES (?,?,?,?)",
                    (slug, val, baseline_date, "Baseline (May 5, 2026)"),
                )
            except Exception:
                pass
        db.commit()
        rows = db.execute(
            "SELECT topic_slug, score, recorded_date, note FROM aeo_scores ORDER BY recorded_date"
        ).fetchall()
        scores = [dict(r) for r in rows]

    return jsonify({"scores": scores, "topic_names": TOPIC_NAMES, "baselines": BASELINE_SCORES})


@app.route("/api/aeo-scores", methods=["POST"])
def add_aeo_score():
    db = get_db()
    data = request.get_json()
    if not data:
        abort(400)

    topic_slug    = data.get("topic_slug", "").strip()
    score         = data.get("score")
    recorded_date = data.get("recorded_date", datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"))
    note          = data.get("note", "")

    if not topic_slug or score is None:
        abort(400)

    db.execute(
        """INSERT INTO aeo_scores (topic_slug, score, recorded_date, note)
           VALUES (?,?,?,?)
           ON CONFLICT(topic_slug, recorded_date) DO UPDATE SET score=excluded.score, note=excluded.note""",
        (topic_slug, float(score), recorded_date, note),
    )
    db.commit()
    return jsonify({"ok": True})


# ── Digest sink (Slack fallback) ──────────────────────────────────────────────
# When the agent has no Slack credentials, slack_notifier POSTs the daily
# digest here instead, and the dashboard renders it as a "Latest Digest" card.

import json as _json


@app.route("/api/digest", methods=["POST"])
def receive_digest():
    data = request.get_json(silent=True) or {}
    questions = data.get("questions") or []
    if not isinstance(questions, list):
        abort(400)

    run_date = data.get("run_date") or datetime.now(tz=timezone.utc).strftime("%B %d, %Y")
    received_at = datetime.now(tz=timezone.utc).isoformat()

    db = get_db()
    db.execute(
        "INSERT INTO digests (received_at, run_date, question_count, payload) VALUES (?,?,?,?)",
        (received_at, run_date, len(questions), _json.dumps(data)),
    )
    db.commit()
    return jsonify({"ok": True, "received_at": received_at, "question_count": len(questions)})


@app.route("/api/digest/latest", methods=["GET"])
def latest_digest():
    db = get_db()
    row = db.execute(
        "SELECT received_at, run_date, question_count, payload FROM digests ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if not row:
        return jsonify({"digest": None})

    try:
        payload = _json.loads(row["payload"])
    except Exception:
        payload = {}

    return jsonify({
        "digest": {
            "received_at": row["received_at"],
            "run_date": row["run_date"],
            "question_count": row["question_count"],
            "questions": payload.get("questions", []),
        },
        "topic_names": TOPIC_NAMES,
    })


if __name__ == "__main__":
    port = int(os.getenv("AEO_WEB_PORT", 5050))
    print(f"\n  Confluent AEO Dashboard → http://localhost:{port}\n")
    app.run(debug=False, port=port)
