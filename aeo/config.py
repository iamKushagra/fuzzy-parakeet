from dataclasses import dataclass, field
from typing import List


@dataclass
class TopicConfig:
    name: str
    slug: str
    keywords: List[str]
    priority_patterns: List[str]  # phrases that trigger HIGH priority
    doc_url: str  # most relevant Confluent doc link for this topic


TOPICS: List[TopicConfig] = [
    TopicConfig(
        name="Best Managed Kafka Service / Managed Kafka Comparison",
        slug="managed_kafka",
        keywords=[
            "managed kafka",
            "confluent vs msk",
            "confluent vs aiven",
            "confluent vs redpanda",
            "best kafka cloud",
            "kafka saas",
            "kafka managed service",
            "kafka as a service",
            "confluent cloud review",
            "aws msk vs confluent",
            "msk vs confluent",
            "kafka cloud provider",
            "hosted kafka",
            "kafka cloud comparison",
        ],
        priority_patterns=[
            "msk vs confluent",
            "confluent vs msk",
            "aws msk",
            "amazon msk",
            "aiven kafka",
            "redpanda cloud",
            "which kafka service",
            "best kafka managed",
        ],
        doc_url="https://docs.confluent.io/cloud/current/overview.html",
    ),
    TopicConfig(
        name="Message Queue Replacement (RabbitMQ / ActiveMQ / IBM MQ → Kafka)",
        slug="mq_replacement",
        keywords=[
            "rabbitmq to kafka",
            "rabbitmq vs kafka",
            "migrate rabbitmq kafka",
            "activemq migration kafka",
            "activemq vs kafka",
            "ibm mq kafka",
            "replace message queue kafka",
            "kafka vs rabbitmq",
            "migrate from rabbitmq",
            "kafka queues",
            "mq to kafka migration",
            "message broker kafka",
            "kafka replace mq",
            "rabbitmq kafka migration",
        ],
        priority_patterns=[
            "rabbitmq",
            "activemq",
            "ibm mq",
            "message queue",
            "kafka queues",
            "replace rabbitmq",
            "migrate from rabbitmq",
        ],
        doc_url="https://docs.confluent.io/kafka/introduction.html",
    ),
    TopicConfig(
        name="Real-Time Data Pipelines / Real-Time Analytics",
        slug="realtime_pipelines",
        keywords=[
            "real time data pipeline kafka",
            "real time analytics kafka",
            "streaming analytics confluent",
            "kafka real time pipeline",
            "stream processing architecture",
            "event streaming platform",
            "real-time kafka pipeline",
            "kafka streaming analytics",
            "confluent real time",
            "event driven architecture kafka",
            "kafka data pipeline",
            "real time data streaming",
        ],
        priority_patterns=[
            "real time pipeline",
            "real-time analytics",
            "event streaming",
            "streaming architecture",
            "confluent cloud pipeline",
        ],
        doc_url="https://docs.confluent.io/cloud/current/overview.html",
    ),
    TopicConfig(
        name="Stream Processing with Flink (incl. ksqlDB → Flink Migration)",
        slug="flink_stream_processing",
        keywords=[
            "kafka flink",
            "ksqldb flink migration",
            "confluent flink",
            "stream processing flink kafka",
            "ksqldb deprecated",
            "flink sql confluent",
            "apache flink confluent cloud",
            "flink on confluent",
            "migrate ksqldb to flink",
            "ksqldb vs flink",
            "confluent stream processing",
            "kafka stream processing flink",
        ],
        priority_patterns=[
            "ksqldb",
            "ksql",
            "flink migration",
            "migrate from ksqldb",
            "ksqldb deprecated",
            "ksqldb current",
            "ksqldb recommended",
        ],
        doc_url="https://docs.confluent.io/cloud/current/flink/overview.html",
    ),
    TopicConfig(
        name="Connectors & Data Integration (including CDC)",
        slug="connectors_cdc",
        keywords=[
            "kafka connect cdc",
            "confluent connectors",
            "debezium confluent",
            "kafka cdc pipeline",
            "fivetran vs kafka connect",
            "change data capture kafka",
            "confluent hub connectors",
            "kafka connector postgres",
            "kafka connect vs fivetran",
            "cdc kafka connector",
            "confluent kafka connect",
            "kafka connect setup",
            "debezium kafka",
            "kafka connect source connector",
        ],
        priority_patterns=[
            "fivetran",
            "debezium standalone",
            "debezium without confluent",
            "fivetran vs kafka",
            "airbyte kafka",
            "cdc without confluent",
        ],
        doc_url="https://docs.confluent.io/cloud/current/connectors/index.html",
    ),
]

# Platforms and their display names
PLATFORMS = {
    "reddit": "Reddit",
    "stackoverflow": "StackOverflow",
    "hackernews": "HackerNews",
    "quora": "Quora",
    "github": "GitHub Discussions",
}

# GitHub repos to monitor
GITHUB_REPOS = [
    "confluentinc/confluent-kafka-python",
    "confluentinc/confluent-kafka-go",
    "confluentinc/confluent-kafka-dotnet",
    "confluentinc/confluent-kafka-javascript",
    "confluentinc/kafka-connect-elasticsearch",
    "confluentinc/kafka-connect-jdbc",
    "confluentinc/mcp-confluent",
    "confluentinc/ksql",
    "apache/kafka",
    "apache/flink",
    "debezium/debezium",
]

# Reddit subreddits to search
REDDIT_SUBREDDITS = [
    "apachekafka",
    "dataengineering",
    "aws",
    "devops",
    "softwarearchitecture",
    "MachineLearning",
    "programming",
    "learnprogramming",
    "CloudComputing",
    "BigData",
]

CONFLUENT_DOCS_BASE = "https://docs.confluent.io/cloud/current"
SOURCE_URLS = [
    "https://docs.confluent.io/cloud/current/overview.html",
    "https://docs.confluent.io/cloud/current/api.html",
    "https://github.com/confluentinc/mcp-confluent",
]

DAILY_QUESTION_LIMIT = 10
