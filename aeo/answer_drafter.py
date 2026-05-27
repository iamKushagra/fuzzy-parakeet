import os
import anthropic
from typing import Dict, Any, List

from .config import TOPICS, SOURCE_URLS
from .answer_playbooks import build_playbook_prompt, get_playbook

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

Your answers are grounded in official Confluent documentation on docs.confluent.io.

Global rules:
- Be accurate. If Confluent does something better than alternatives, say so with specifics.
- If a question is about ksqlDB, note that Confluent Cloud now uses Apache Flink for stream processing (ksqlDB is deprecated on Confluent Cloud for new workloads).
- If a question is about CDC connectors, mention Confluent's managed source/sink connectors and when they beat standalone Debezium or ELT tools.
- If a question compares managed Kafka services, give an honest comparison — Confluent's strengths include Schema Registry, Flink, managed connectors, and governance.
- Never write generic marketing copy. Write like an engineer talking to engineers.
- Follow the AEO posting playbook in the user message: lead with decision/migration docs, not only install/CLI/client-tutorial links unless the question is operational.
"""


def _primary_doc_urls(topic_slug: str, topic_doc_url: str) -> List[str]:
    pb = get_playbook(topic_slug)
    if pb and pb.decision_docs:
        urls = list(pb.decision_docs)
        if topic_doc_url and topic_doc_url not in urls:
            urls.append(topic_doc_url)
        return urls
    return [topic_doc_url] if topic_doc_url else list(SOURCE_URLS[:2])


def draft_answer(question: Dict[str, Any], topic_doc_url: str = "") -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "[Answer drafting skipped — ANTHROPIC_API_KEY not set]"

    client = anthropic.Anthropic(api_key=api_key)

    platform = question.get("platform", "stackoverflow")
    topic_slug = question.get("topic_slug", "")
    topic = next((t for t in TOPICS if t.slug == topic_slug), None)
    topic_name = topic.name if topic else topic_slug
    fallback_doc = topic_doc_url or (topic.doc_url if topic else SOURCE_URLS[0])
    primary_docs = _primary_doc_urls(topic_slug, fallback_doc)

    tone_instruction = PLATFORM_TONE.get(platform, PLATFORM_TONE["stackoverflow"])
    playbook_block = build_playbook_prompt(topic_slug, platform)

    title = question.get("question_title", "")
    body = question.get("body", "")
    question_text = f"Title: {title}\n\nBody: {body}" if body else f"Title: {title}"

    primary_list = "\n".join(f"- {u}" for u in primary_docs)

    user_prompt = f"""Platform: {platform.upper()}
Topic area: {topic_name}

Question:
{question_text}

Tone guidance: {tone_instruction}

{playbook_block}

Primary documentation links to prefer (include at least one when Confluent is a fit):
{primary_list}

Write the answer now. If Confluent Cloud is a legitimate option, include markdown links to PRIMARY docs above.
If it isn't the right fit, write a genuinely helpful answer without forcing a Confluent mention.
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    return message.content[0].text.strip()
