import os
import json
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from .config import TOPICS, PLATFORMS

PLATFORM_EMOJI = {
    "reddit": ":reddit:",
    "stackoverflow": ":stackoverflow:",
    "hackernews": ":orange_circle:",
    "quora": ":quora:",
    "github": ":github:",
}

PRIORITY_EMOJI = {
    "high": ":red_circle: *HIGH PRIORITY*",
    "normal": ":yellow_circle:",
}


def _topic_name(slug: str) -> str:
    t = next((t for t in TOPICS if t.slug == slug), None)
    return t.name if t else slug


def _platform_name(platform: str) -> str:
    return PLATFORMS.get(platform, platform.title())


def _build_digest_blocks(questions: List[Dict[str, Any]], run_date: str) -> list:
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📊 Confluent AEO Daily Digest — {run_date}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{len(questions)} new question{'s' if len(questions) != 1 else ''} found* "
                    f"across Reddit, StackOverflow, HackerNews, Quora & GitHub\n"
                    f"Full drafted answers are in each question's thread ↓"
                ),
            },
        },
        {"type": "divider"},
    ]

    for i, q in enumerate(questions, 1):
        platform = q.get("platform", "")
        priority = "high" if q.get("is_high_priority") else "normal"
        topic_name = _topic_name(q.get("topic_slug", ""))
        platform_name = _platform_name(platform)
        p_emoji = PLATFORM_EMOJI.get(platform, ":speech_balloon:")
        priority_label = PRIORITY_EMOJI[priority]
        title = q.get("question_title", "Untitled")
        url = q.get("question_url", "")

        text_lines = [
            f"{priority_label}  {p_emoji} *[{platform_name}]* · _{topic_name}_",
            f"*{i}. <{url}|{title}>*",
        ]

        # Add extra context for competitor mentions
        body = q.get("body", "")
        if body:
            snippet = body[:120].replace("\n", " ").strip()
            if snippet:
                text_lines.append(f"> {snippet}…")

        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(text_lines)},
            }
        )

    blocks.append({"type": "divider"})
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Confluent AEO Monitor | Questions deduped via SQLite | Answers drafted by Claude Sonnet",
                }
            ],
        }
    )
    return blocks


def _send_webhook(webhook_url: str, payload: dict) -> bool:
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def _send_local(local_url: str, questions: List[Dict[str, Any]], run_date: str) -> bool:
    """Fallback: POST a JSON digest to the local Flask dashboard.

    The dashboard stores it in the `digests` table and surfaces it in the
    "Latest Digest" card on the homepage. Used when no Slack creds are set.
    """
    body = {
        "run_date": run_date,
        "question_count": len(questions),
        "questions": [
            {
                "platform":          q.get("platform", ""),
                "question_id":       q.get("question_id", ""),
                "question_url":      q.get("question_url", ""),
                "question_title":    q.get("question_title", ""),
                "topic_slug":        q.get("topic_slug", ""),
                "priority":          "high" if q.get("is_high_priority") else "normal",
                "created_at":        q.get("created_at", ""),
                "body":              (q.get("body", "") or "")[:240],
                "answer_drafted":    q.get("answer_drafted", "") or "",
            }
            for q in questions
        ],
    }
    try:
        resp = httpx.post(local_url, json=body, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def _send_bot(token: str, channel: str, payload: dict) -> Optional[str]:
    """Returns thread_ts on success, None on failure."""
    try:
        resp = httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"channel": channel, **payload},
            timeout=10,
        )
        data = resp.json()
        if data.get("ok"):
            return data.get("ts")
        return None
    except Exception:
        return None


def _post_thread_answer(token: str, channel: str, thread_ts: str, question: Dict[str, Any]) -> None:
    answer = question.get("answer_drafted", "")
    if not answer:
        return
    title = question.get("question_title", "")
    url = question.get("question_url", "")
    text = f"*Drafted answer for:* <{url}|{title}>\n\n{answer}"
    try:
        httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"channel": channel, "thread_ts": thread_ts, "text": text},
            timeout=10,
        )
    except Exception:
        pass


def send_digest(questions: List[Dict[str, Any]], dry_run: bool = False) -> bool:
    if not questions:
        print("[Slack] No new questions to send today.")
        return True

    run_date = datetime.now(tz=timezone.utc).strftime("%B %d, %Y")
    blocks = _build_digest_blocks(questions, run_date)
    payload = {"blocks": blocks, "text": f"Confluent AEO Digest — {run_date}"}

    if dry_run:
        print("\n=== DRY RUN — Slack Digest ===")
        print(json.dumps(payload, indent=2))
        print("\n=== Drafted Answers ===")
        for q in questions:
            print(f"\n[{q.get('platform')}] {q.get('question_title')}")
            print(q.get("answer_drafted", "[no answer]"))
        return True

    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    bot_token = os.getenv("SLACK_BOT_TOKEN", "")
    channel_id = os.getenv("SLACK_CHANNEL_ID", "")

    if webhook_url:
        # Webhook mode: single digest message (no thread support)
        success = _send_webhook(webhook_url, payload)
        if success:
            print(f"[Slack] Digest sent via webhook ({len(questions)} questions).")
        else:
            print("[Slack] Webhook delivery failed.")
        return success

    elif bot_token and channel_id:
        # Bot token mode: digest + per-question thread answers
        thread_ts = _send_bot(bot_token, channel_id, payload)
        if not thread_ts:
            print("[Slack] Bot message delivery failed.")
            return False
        print(f"[Slack] Digest sent via bot token ({len(questions)} questions).")
        for q in questions:
            if q.get("answer_drafted"):
                _post_thread_answer(bot_token, channel_id, thread_ts, q)
        return True

    else:
        # No Slack creds: fall back to the local dashboard so the digest is
        # still visible somewhere. Disable with AEO_LOCAL_DIGEST_FALLBACK=false.
        fallback_enabled = os.getenv("AEO_LOCAL_DIGEST_FALLBACK", "true").lower() != "false"
        if not fallback_enabled:
            print(
                "[Slack] No credentials configured. "
                "Set SLACK_WEBHOOK_URL or SLACK_BOT_TOKEN + SLACK_CHANNEL_ID in .env"
            )
            return False

        local_url = os.getenv("LOCAL_DIGEST_URL", "http://localhost:5050/api/digest")
        ok = _send_local(local_url, questions, run_date)
        if ok:
            print(
                f"[Digest] No Slack creds — posted {len(questions)} questions "
                f"to local dashboard at {local_url}"
            )
            return True
        print(
            f"[Digest] No Slack creds and local dashboard at {local_url} "
            f"is unreachable. Start `python3 aeo_web.py` or set "
            f"SLACK_WEBHOOK_URL in .env."
        )
        return False
