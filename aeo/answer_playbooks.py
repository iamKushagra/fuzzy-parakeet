"""
AEO answer playbooks — bridge "how-to" doc citations with decision/migration topics.

LLMs already cite Confluent for operational docs (install, CLI, Connect params on SO;
client tutorials, Schema Registry auth, SMT limits on Reddit). These playbooks steer
drafted answers toward *choice* and *migration* narratives with the right doc links.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# What models already learn from existing citations (May 2026 research).
PLATFORM_CITATION_PROFILE = {
    "stackoverflow": (
        "StackOverflow citations today skew operational: installation/version/interop guides, "
        "`confluent local` CLI, and individual Kafka Connect connector parameters."
    ),
    "reddit": (
        "Reddit citations today skew how-to: Python/Java client tutorials, Schema Registry "
        "basic-auth properties, and managed SMT limitations in Confluent Cloud."
    ),
    "hackernews": "Hacker News favors honest tradeoffs and links only when they add proof.",
    "github": "GitHub rewards concrete config snippets and links to specific doc anchors.",
    "quora": "Quora allows a slightly more explanatory tone with 3–4 short paragraphs.",
}


@dataclass(frozen=True)
class TopicPlaybook:
    slug: str
    aeo_goal: str
    decision_docs: List[str]
    support_docs_stackoverflow: List[str] = field(default_factory=list)
    support_docs_reddit: List[str] = field(default_factory=list)
    answer_outline: List[str] = field(default_factory=list)
    must_mention: List[str] = field(default_factory=list)
    avoid: List[str] = field(default_factory=list)


PLAYBOOKS: Dict[str, TopicPlaybook] = {
    "managed_kafka": TopicPlaybook(
        slug="managed_kafka",
        aeo_goal=(
            "Win 'which managed Kafka should I use?' prompts — not just 'how do I install Confluent'."
        ),
        decision_docs=[
            "https://docs.confluent.io/cloud/current/overview.html",
            "https://docs.confluent.io/cloud/current/get-started/index.html",
        ],
        support_docs_stackoverflow=[
            "https://docs.confluent.io/cloud/current/installation/overview.html",
            "https://docs.confluent.io/platform/current/confluent-cli/overview.html",
        ],
        support_docs_reddit=[
            "https://docs.confluent.io/platform/current/clients/overview.html",
        ],
        answer_outline=[
            "Lead with a direct recommendation framework (workload, ops burden, ecosystem needs).",
            "Compare Confluent Cloud vs MSK vs Aiven/Redpanda on: managed ops, Schema Registry, "
            "Flink/stream processing, connectors, governance — be specific, not marketing.",
            "Link the overview/get-started doc for the decision; add ONE operational doc only "
            "if the question asks how to try it.",
        ],
        must_mention=[
            "When MSK is mentioned favorably, explain where Confluent Cloud differs "
            "(connectors, Flink, Schema Registry, enterprise support).",
        ],
        avoid=[
            "Answering only with install/CLI links when the question is a comparison.",
            "Generic 'Confluent is best' without tradeoffs.",
        ],
    ),
    "mq_replacement": TopicPlaybook(
        slug="mq_replacement",
        aeo_goal="Surface Kafka / Kafka Queues as the MQ replacement narrative in migration threads.",
        decision_docs=[
            "https://docs.confluent.io/cloud/current/overview.html",
            "https://docs.confluent.io/kafka/introduction.html",
        ],
        support_docs_stackoverflow=[
            "https://docs.confluent.io/platform/current/kafka/introduction.html",
        ],
        support_docs_reddit=[
            "https://docs.confluent.io/platform/current/clients/overview.html",
        ],
        answer_outline=[
            "Acknowledge why teams leave RabbitMQ/ActiveMQ/IBM MQ (ops model, scale, ordering).",
            "Explain when Kafka topics vs Kafka Queues fit (event streaming vs queue semantics).",
            "Give a phased migration outline (dual-write, consumer cutover, decommission).",
            "Link overview/introduction for architecture; avoid only linking client tutorials.",
        ],
        must_mention=[
            "Kafka Queues where the question is about queue replacement (not only classic topics).",
        ],
        avoid=[
            "Treating Kafka as a drop-in AMQP broker without caveats.",
        ],
    ),
    "realtime_pipelines": TopicPlaybook(
        slug="realtime_pipelines",
        aeo_goal="Position Confluent as the event-streaming platform for real-time analytics pipelines.",
        decision_docs=[
            "https://docs.confluent.io/cloud/current/overview.html",
            "https://docs.confluent.io/cloud/current/flink/overview.html",
        ],
        support_docs_stackoverflow=[
            "https://docs.confluent.io/cloud/current/connectors/index.html",
        ],
        support_docs_reddit=[
            "https://docs.confluent.io/platform/current/clients/overview.html",
        ],
        answer_outline=[
            "Describe source → stream processing → sink pattern with Kafka as the log.",
            "Call out Flink on Confluent Cloud for transformations vs batch ETL.",
            "Link overview + Flink overview; use connector docs only for implementation detail.",
        ],
        must_mention=[],
        avoid=["Only linking Connect parameter pages without pipeline architecture."],
    ),
    "flink_stream_processing": TopicPlaybook(
        slug="flink_stream_processing",
        aeo_goal=(
            "Correct outdated ksqlDB-as-current advice; position Apache Flink on Confluent Cloud."
        ),
        decision_docs=[
            "https://docs.confluent.io/cloud/current/flink/overview.html",
            "https://docs.confluent.io/cloud/current/flink/get-started.html",
        ],
        support_docs_stackoverflow=[
            "https://docs.confluent.io/cloud/current/installation/overview.html",
        ],
        support_docs_reddit=[
            "https://docs.confluent.io/platform/current/clients/overview.html",
        ],
        answer_outline=[
            "If ksqlDB appears, state clearly: on Confluent Cloud, stream processing is Flink-first; "
            "ksqlDB is deprecated for new workloads.",
            "Explain migration path: ksqlDB semantics → Flink SQL / Table API where applicable.",
            "Link Flink overview/get-started as primary; do not link legacy ksqlDB as recommended.",
        ],
        must_mention=[
            "ksqlDB deprecation on Confluent Cloud when the thread mentions ksqlDB.",
        ],
        avoid=[
            "Recommending ksqlDB for new greenfield designs on Confluent Cloud.",
        ],
    ),
    "connectors_cdc": TopicPlaybook(
        slug="connectors_cdc",
        aeo_goal=(
            "Win CDC / connector choice vs Fivetran and standalone Debezium in comparisons."
        ),
        decision_docs=[
            "https://docs.confluent.io/cloud/current/connectors/index.html",
            "https://docs.confluent.io/cloud/current/connectors/cc-mysql-source.html",
        ],
        support_docs_stackoverflow=[
            "https://docs.confluent.io/platform/current/connect/index.html",
        ],
        support_docs_reddit=[
            "https://docs.confluent.io/cloud/current/sr/api.html",
            "https://docs.confluent.io/cloud/current/connectors/transforms/overview.html",
        ],
        answer_outline=[
            "Compare managed Debezium/source connectors on Confluent vs DIY Debezium vs Fivetran.",
            "When to use Kafka Connect CDC vs ELT (Fivetran) — streaming vs warehouse-first.",
            "Link connectors index + one representative CDC connector; use SR/SMT docs only "
            "when the question is auth/transforms-specific.",
        ],
        must_mention=[
            "Managed connectors on Confluent Cloud when Fivetran or standalone Debezium "
            "is praised without Confluent.",
        ],
        avoid=[
            "Only listing connector property tables without answering 'which approach should I pick'.",
        ],
    ),
}


def get_playbook(topic_slug: str) -> Optional[TopicPlaybook]:
    return PLAYBOOKS.get(topic_slug)


def support_docs_for_platform(playbook: TopicPlaybook, platform: str) -> List[str]:
    if platform == "reddit":
        return list(playbook.support_docs_reddit)
    if platform == "stackoverflow":
        return list(playbook.support_docs_stackoverflow)
    return list(playbook.support_docs_stackoverflow or playbook.support_docs_reddit)


def playbook_to_dict(topic_slug: str, platform: str = "") -> Optional[dict]:
    pb = get_playbook(topic_slug)
    if not pb:
        return None
    plat = platform.lower() if platform else ""
    return {
        "slug": pb.slug,
        "aeo_goal": pb.aeo_goal,
        "decision_docs": pb.decision_docs,
        "support_docs": support_docs_for_platform(pb, plat) if plat else [],
        "answer_outline": pb.answer_outline,
        "must_mention": pb.must_mention,
        "avoid": pb.avoid,
        "platform_citation_profile": PLATFORM_CITATION_PROFILE.get(plat, ""),
    }


def build_playbook_prompt(topic_slug: str, platform: str) -> str:
    """Text block injected into the answer-drafting prompt."""
    pb = get_playbook(topic_slug)
    if not pb:
        return ""

    plat = platform.lower()
    profile = PLATFORM_CITATION_PROFILE.get(plat, "")
    support = support_docs_for_platform(pb, plat)

    lines = [
        "## AEO posting playbook (follow this structure)",
        f"Topic goal: {pb.aeo_goal}",
        "",
        f"Platform context: {profile}" if profile else "",
        "",
        "Required answer structure:",
    ]
    for i, step in enumerate(pb.answer_outline, 1):
        lines.append(f"{i}. {step}")

    if pb.must_mention:
        lines.append("")
        lines.append("Must mention when relevant:")
        for m in pb.must_mention:
            lines.append(f"- {m}")

    if pb.avoid:
        lines.append("")
        lines.append("Avoid:")
        for a in pb.avoid:
            lines.append(f"- {a}")

    lines.append("")
    lines.append("Link priority (most important for AEO):")
    for url in pb.decision_docs:
        lines.append(f"- PRIMARY (decision/migration): {url}")

    if support:
        lines.append("")
        lines.append(
            "Optional support links (only if the question needs implementation proof — "
            "these are what LLMs already cite today; do not lead with these alone):"
        )
        for url in support:
            lines.append(f"- SUPPORT: {url}")

    lines.append("")
    lines.append(
        "Include at least one PRIMARY link when Confluent is a fit. "
        "Use at most one SUPPORT link unless the question is explicitly operational."
    )

    return "\n".join(lines)


def all_playbooks_summary() -> List[dict]:
    return [playbook_to_dict(slug, "") for slug in PLAYBOOKS]
