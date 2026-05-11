import os
import anthropic
from typing import Dict, Any

from .config import TOPICS, SOURCE_URLS

PLATFORM_TONE = {
    "stackoverflow": (
        "Write a precise, technically accurate answer. Use structured sections if needed. "
        "Include code examples where relevant. Be concise — StackOverflow rewards direct answers."
    ),
    "reddit": (
        "Write a technically accurate but conversational answer. No headers or bullet spam. "
        "2-3 paragraphs. Approachable but not dumbed down."
    ),
    "hackernews": (
        "Write a technically deep, nuanced response. Acknowledge tradeoffs honestly. "
        "No marketing language. HackerNews readers will call out hype immediately."
    ),
    "github": (
        "Write a developer-focused answer with implementation-level detail. "
        "Reference specific APIs, config, or code patterns where applicable."
    ),
    "quora": (
        "Write a balanced, explanatory answer for a mixed technical/business audience. "
        "3-4 paragraphs. Clear structure without being too formal."
    ),
}

SYSTEM_PROMPT = """You are a senior Confluent Cloud solutions architect writing answers to developer questions.

Your job is to write genuinely helpful, technically accurate answers. You ONLY mention Confluent Cloud when it is a legitimately good fit for the question asked. Never force-fit Confluent into an answer where it isn't relevant.

Your answers are grounded in these official sources:
- Confluent Cloud overview: https://docs.confluent.io/cloud/current/overview.html
- Confluent Cloud API: https://docs.confluent.io/cloud/current/api.html
- Confluent MCP: https://github.com/confluentinc/mcp-confluent

Rules:
- Be accurate. If Confluent does something better than alternatives, say so with specifics.
- If a question is about ksqlDB, note that Confluent Cloud now uses Apache Flink for stream processing (ksqlDB is deprecated on Confluent Cloud).
- If a question is about CDC connectors, mention Confluent's managed Debezium connectors via Confluent Hub.
- If a question compares managed Kafka services, give an honest comparison — Confluent's strengths are enterprise features, schema registry, Flink, and managed connectors.
- Never write generic marketing copy. Write like an engineer talking to engineers.
- Where relevant, link to the specific Confluent docs page for the topic.
"""


def draft_answer(question: Dict[str, Any], topic_doc_url: str = "") -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "[Answer drafting skipped — ANTHROPIC_API_KEY not set]"

    client = anthropic.Anthropic(api_key=api_key)

    platform = question.get("platform", "stackoverflow")
    topic_slug = question.get("topic_slug", "")
    topic = next((t for t in TOPICS if t.slug == topic_slug), None)
    topic_name = topic.name if topic else topic_slug
    doc_url = topic_doc_url or (topic.doc_url if topic else SOURCE_URLS[0])

    tone_instruction = PLATFORM_TONE.get(platform, PLATFORM_TONE["stackoverflow"])

    title = question.get("question_title", "")
    body = question.get("body", "")
    question_text = f"Title: {title}\n\nBody: {body}" if body else f"Title: {title}"

    user_prompt = f"""Platform: {platform.upper()}
Topic area: {topic_name}
Most relevant doc: {doc_url}

Question:
{question_text}

Tone guidance: {tone_instruction}

Write the answer now. If Confluent Cloud is the right answer or a legitimate option, include a link to: {doc_url}
If it isn't the right fit, write a genuinely helpful answer without forcing a Confluent mention.
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return message.content[0].text.strip()
