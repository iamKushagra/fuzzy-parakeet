# Confluent AEO Monitoring Agent — Full Specification

## Purpose

Build a daily automated agent that monitors high-traffic developer platforms for questions related to Confluent Cloud's five core AEO (Answer Engine Optimization) topic gaps. The agent surfaces new high-intent questions, drafts technically precise answers grounded in Confluent's official documentation, and delivers a daily Slack digest. The goal is to improve Confluent Cloud's citation rate in AI engines (ChatGPT, Claude, Perplexity, Gemini) by enabling the team to post accurate, authoritative answers on platforms that AI engines heavily cite.

---

## Background & Problem

AI engines like Perplexity (46.5% Reddit citation rate), Google AIO (21% Reddit citation rate), ChatGPT, and Gemini pull answers heavily from Reddit, StackOverflow, Quora, HackerNews, and GitHub Discussions. Confluent Cloud's current visibility in AI-generated answers across five critical topic areas is low or zero:

| AEO Topic | Current Visibility (May 2026) | Gap |
|---|---|---|
| Best Managed Kafka Service / Managed Kafka Comparison | 10% | Confluent wins only 1 in 10 prompts vs. competitors |
| Message Queue Replacement (RabbitMQ / ActiveMQ / IBM MQ → Kafka) | 0% | Kafka Queues not picked up by AI engines at all |
| Real-Time Data Pipelines / Real-Time Analytics | 35% | Disappears at category/discovery stage |
| Stream Processing with Flink (incl. ksqlDB → Flink Migration) | 0% | AI engines still describe deprecated ksqlDB as current |
| Connectors & Data Integration (including CDC) | 32% | Fivetran and standalone Debezium dominate; Confluent nearly absent |

---

## Agent Behavior

### 1. Monitoring Scope

**Platforms to scrape daily:**
- Reddit (public JSON API — no key required)
- StackOverflow / StackExchange (free read API — no key required for basic use)
- Quora (web scraping)
- HackerNews (Algolia API — fully free, no key)
- GitHub Discussions (public GraphQL API — no key for public repos)

**GitHub repos to monitor:**
- All `confluentinc/*` org repos
- `apache/kafka`
- `apache/flink`
- Other Kafka-adjacent repos (e.g., `debezium/debezium`, `apache/kafka-connect-*`)

**No API keys required at launch.** Designed to work with public endpoints and rate-limit-safe scraping. Keys can be added later to increase rate limits.

---

### 2. Topic Areas & Keywords

Each topic area has a defined set of high-intent search keywords:

**Topic 1 — Best Managed Kafka Service / Managed Kafka Comparison**
- Keywords: `managed kafka`, `confluent vs msk`, `confluent vs aiven`, `best kafka cloud`, `kafka saas`, `kafka managed service comparison`, `confluent cloud review`, `aws msk vs confluent`
- Priority flag: Any question mentioning AWS MSK positively or comparing MSK favorably → **HIGH PRIORITY**

**Topic 2 — Message Queue Replacement**
- Keywords: `rabbitmq to kafka`, `activemq migration kafka`, `ibm mq kafka`, `replace message queue kafka`, `kafka vs rabbitmq`, `migrate from rabbitmq`, `kafka queues`, `mq to kafka`
- Priority flag: Any question where Kafka Queues feature is missing from the discussion → **HIGH PRIORITY**

**Topic 3 — Real-Time Data Pipelines / Real-Time Analytics**
- Keywords: `real time data pipeline kafka`, `real time analytics kafka`, `streaming analytics confluent`, `kafka real time pipeline`, `stream processing architecture`, `event streaming platform`

**Topic 4 — Stream Processing with Flink / ksqlDB → Flink Migration**
- Keywords: `kafka flink`, `ksqldb flink migration`, `confluent flink`, `stream processing flink kafka`, `ksqldb deprecated`, `flink sql confluent`, `apache flink confluent cloud`
- Priority flag: Any question or answer still referencing ksqlDB as current/recommended → **HIGH PRIORITY** (accuracy problem — needs correction)

**Topic 5 — Connectors & Data Integration (CDC)**
- Keywords: `kafka connect cdc`, `confluent connectors`, `debezium confluent`, `kafka cdc pipeline`, `fivetran vs kafka connect`, `change data capture kafka`, `confluent hub connectors`, `kafka connector postgres`
- Priority flag: Any question praising Fivetran or standalone Debezium without mentioning Confluent → **HIGH PRIORITY**

---

### 3. Question Filtering

**Include:**
- High-intent questions: "which service should I use", "how do I migrate from X to Y", "what's the best way to..."
- Educational questions with commercial intent: "how does Kafka Flink work", "what is CDC in Kafka"
- Comparison questions: "X vs Y", "difference between X and Y"
- Migration/architecture decision questions

**Exclude:**
- Pure academic/homework questions with no commercial intent
- Questions already answered definitively with no Confluent gap
- Non-English questions (English only for now)
- Questions seen in previous runs (deduplicated via SQLite)

---

### 4. Deduplication & State

- **Storage:** Local SQLite database (`aeo_agent.db`) in the project directory
- **Tracked fields per question:** `platform`, `question_id`, `question_url`, `question_title`, `topic_area`, `priority`, `first_seen_date`, `answer_drafted`, `notified`
- **Logic:** A question is only included in a digest once. Subsequent runs skip questions already in the DB.
- **Retention:** Questions stay in DB indefinitely for historical tracking.

---

### 5. Answer Drafting

**When to mention Confluent:**
- Only when Confluent Cloud is genuinely the right answer or a legitimate option
- Never force-fit Confluent into answers where it isn't relevant
- Credibility-first approach: accurate, helpful answer first; Confluent mention natural and earned

**Tone by platform:**
- StackOverflow: Precise, technical, code examples where relevant, concise
- Reddit: Technically accurate but conversational, slightly more approachable
- HackerNews: Technically deep, nuanced, acknowledges tradeoffs honestly
- GitHub Discussions: Developer-focused, implementation-level detail
- Quora: Balanced, slightly more explanatory for mixed audience

**Answer grounding — source of truth:**
- Confluent Cloud Overview: https://docs.confluent.io/cloud/current/overview.html
- Confluent Cloud API: https://docs.confluent.io/cloud/current/api.html/
- Confluent MCP GitHub: https://github.com/confluentinc/mcp-confluent
- Topic-specific doc pages linked inline where relevant (optional but preferred)
- Agent should cite specific doc pages when the topic maps to one (e.g., Flink questions → link to Flink on Confluent Cloud docs)

**Answer length:**
- StackOverflow: 3–5 paragraphs with structured sections
- Reddit: 2–3 paragraphs, no headers
- HackerNews: 2–4 paragraphs, no fluff
- GitHub / Quora: 3–4 paragraphs

---

### 6. Slack Delivery

**Trigger:** Daily at 7:00 PM IST (13:30 UTC)

**Channel:** Configured via `SLACK_WEBHOOK_URL` or `SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID` in `.env` (credentials provided separately)

**Digest format:**
- Main message: Summary of top 10 new questions found that day, grouped by topic area
- Each question entry shows: platform badge, topic label, priority flag (if high), question title, URL, one-line context
- Full drafted answer posted as a **thread reply** under each question summary

**Daily digest cap:** Top 10 questions (prioritized: HIGH PRIORITY first, then by recency)

**Sample message structure:**
```
📊 *Confluent AEO Daily Digest — May 10, 2026*
10 new questions found across Reddit, StackOverflow, HackerNews

🔴 HIGH PRIORITY  [StackOverflow] [Managed Kafka]
"AWS MSK vs Confluent Cloud for financial data pipelines"
→ https://stackoverflow.com/questions/...
Answer drafted ↓ (see thread)

🟡  [Reddit] [CDC / Connectors]
"Debezium standalone vs Kafka Connect for Postgres CDC"
→ https://reddit.com/r/...
Answer drafted ↓ (see thread)
```

---

### 7. Scheduling

- **Method:** macOS `launchd` plist (preferred over cron for reliability on macOS)
- **Schedule:** Daily at 7:00 PM IST
- **Script entrypoint:** `aeo_agent.py`
- **Virtual environment:** `.venv` in project directory
- **Logs:** Written to `aeo_agent.log` in project directory

---

### 8. Tech Stack

| Component | Choice | Reason |
|---|---|---|
| Language | Python 3.13 | Already in use in project |
| Virtual env | `.venv` (already exists) | Consistent with project |
| HTTP scraping | `httpx` + `BeautifulSoup4` | Async-capable, clean parsing |
| AI answer drafting | Anthropic Claude API (`claude-sonnet-4-6`) | Best technical writing quality |
| State / dedup | SQLite via `sqlite3` (stdlib) | Zero infrastructure, simple |
| Slack delivery | Slack Incoming Webhooks or `slack-sdk` | Simple, reliable |
| Scheduling | macOS `launchd` plist | More reliable than cron on macOS |
| Env config | `.env` via `python-dotenv` | Already pattern in project |

---

### 9. Environment Variables

```env
# Slack (provided later)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
# OR
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL_ID=C...

# Anthropic (for answer drafting)
ANTHROPIC_API_KEY=sk-ant-...

# Optional tuning
AEO_DAILY_LIMIT=10          # max questions per digest
AEO_DRY_RUN=false           # if true, prints digest to terminal instead of Slack
AEO_LOG_LEVEL=INFO
```

---

### 10. File Structure

```
python-chat-bot/
├── aeo_agent.py              # main entrypoint
├── aeo_agent.db              # SQLite state (auto-created)
├── aeo_agent.log             # daily run logs
├── aeo/
│   ├── __init__.py
│   ├── config.py             # topic areas, keywords, platform config
│   ├── scrapers/
│   │   ├── reddit.py
│   │   ├── stackoverflow.py
│   │   ├── hackernews.py
│   │   ├── quora.py
│   │   └── github_discussions.py
│   ├── filter.py             # dedup, priority scoring, question filtering
│   ├── answer_drafter.py     # Claude API integration for answer generation
│   └── slack_notifier.py     # Slack digest formatting and delivery
├── .env                      # secrets (gitignored)
├── .env.example              # template
└── com.confluent.aeo-agent.plist  # macOS launchd config
```

---

### 11. Success Metrics (for future tracking)

- Number of high-intent questions surfaced per week per topic area
- Number of answers posted by team (manual action post-digest)
- AEO visibility score improvement (tracked manually each month, baseline above)
- Platform distribution of questions (which platform drives most volume)

---

### 12. Out of Scope (v1)

- Auto-posting answers (human reviews and posts manually)
- Twitter/X monitoring
- LinkedIn monitoring
- Multi-language support
- Web dashboard
- Answer performance tracking (upvotes, citations)

---

*Last updated: May 2026 | Owner: kkesav@confluent.io*
