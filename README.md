# 🚀 Confluent AEO Monitoring Agent

> Daily-running agent that surfaces high-intent questions from Reddit, StackOverflow, HackerNews, Quora, and GitHub on five Confluent Cloud AEO topic gaps — and drafts grounded answers so the team can post them where AI engines (ChatGPT, Claude, Perplexity, Gemini) heavily cite. Ships with a live Flask dashboard and a one-command public deploy.

<p align="left">
  <img alt="python" src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="flask" src="https://img.shields.io/badge/flask-3.x-000?logo=flask&logoColor=white">
  <img alt="anthropic" src="https://img.shields.io/badge/Claude-Sonnet%204.5-D97757?logo=anthropic&logoColor=white">
  <img alt="sqlite" src="https://img.shields.io/badge/SQLite-stdlib-003B57?logo=sqlite&logoColor=white">
  <img alt="systemd" src="https://img.shields.io/badge/systemd-on%20EC2-FCC624?logo=linux&logoColor=black">
  <img alt="cloudflare" src="https://img.shields.io/badge/Cloudflare%20Tunnel-public%20URL-F38020?logo=cloudflare&logoColor=white">
  <img alt="status" src="https://img.shields.io/badge/status-live-22c55e">
</p>

---

## 📑 Table of contents

1. [Why this exists](#-why-this-exists)
2. [What it does](#-what-it-does)
3. [Architecture](#-architecture)
4. [Tech stack](#-tech-stack)
5. [Quick start (TL;DR)](#-quick-start-tldr)
6. [Prerequisites](#-prerequisites)
7. [Step-by-step install](#-step-by-step-install)
8. [Environment variables](#-environment-variables)
9. [Run it locally](#-run-it-locally-dev)
10. [Deploy to production](#-deploy-to-production-systemd--cloudflare-tunnel)
11. [Operations cheat-sheet](#-operations-cheat-sheet)
12. [Project structure](#-project-structure)
13. [Customising topics & keywords](#-customising-topics--keywords)
14. [Troubleshooting](#-troubleshooting)
15. [Roadmap / out-of-scope](#-roadmap--out-of-scope-v1)

---

## 🎯 Why this exists

AI engines pull answers heavily from a handful of developer platforms. As of **May 2026**, Confluent Cloud's citation rate across our five strategic AEO topics is low or zero:

| AEO topic | Current visibility | Gap |
|---|---|---|
| Best Managed Kafka Service / comparison | **10%** | Confluent wins only 1 in 10 prompts vs. competitors |
| Message Queue Replacement (RabbitMQ / ActiveMQ / IBM MQ → Kafka) | **0%** | Kafka Queues not picked up at all |
| Real-Time Data Pipelines / Analytics | **35%** | Disappears at discovery stage |
| Stream Processing with Flink (ksqlDB → Flink Migration) | **0%** | AI engines still describe deprecated ksqlDB as current |
| Connectors & Data Integration (incl. CDC) | **32%** | Fivetran & standalone Debezium dominate |

> Goal: surface fresh, high-intent questions on these topics daily so the team can post **accurate, authoritative answers** on the very platforms AI engines cite — and lift our citation rate.

---

## ✨ What it does

- 🔍 **Scrapes 5 platforms × 5 topics daily** — Reddit, StackOverflow, HackerNews, Quora, GitHub (issues + discussions)
- 🎚️ **Smart ranking** — combines priority pattern matching, platform weights (Reddit 35, SO 32, HN 22, GitHub 18, Quora 12), engagement (log-scaled upvotes & answer counts), and a recency curve. Older-but-impactful questions still surface.
- 🧠 **AI answer drafting** — Claude Sonnet 4.5 generates platform-appropriate drafts grounded in `docs.confluent.io`
- 🚫 **Dedup forever** — SQLite tracks every question we've ever seen, so digests are always net-new
- 📬 **Slack digest at 13:30 UTC** (= 7:00 PM IST) — top-N questions grouped by topic, with drafted answers as thread replies. Falls back to an in-app digest card if Slack creds are missing.
- 📊 **Live web dashboard** — filter/search questions, view per-topic & per-platform breakdowns, track AEO scores over time, mark questions as posted, see the 7-day activity sparkline
- 🛰️ **One-command public hosting** — Flask via Gunicorn + Cloudflare Tunnel + systemd timer, all behind a public HTTPS URL the team can bookmark

---

## 🏗️ Architecture

```
                    ┌──────────────────────────────────────────────────────┐
                    │              EC2 instance (Amazon Linux 2023)         │
                    │                                                       │
   13:30 UTC daily  │   ┌───────────────────────────────────────────┐      │
   ──────────────►  │   │  confluent-aeo-agent.service (oneshot)    │      │
   (systemd timer)  │   │                                            │      │
                    │   │  aeo_agent.py                              │      │
                    │   │   ├─ Scrape Reddit / SO / HN / Quora / GH  │      │
                    │   │   ├─ Filter & dedup (SQLite)               │      │
                    │   │   ├─ Rank (priority + impact + recency)    │      │
                    │   │   ├─ Draft answers (Anthropic Claude API)  │      │
                    │   │   └─ Send Slack digest (or local fallback) │      │
                    │   └────────────────┬───────────────────────────┘      │
                    │                    │                                   │
                    │                    ▼                                   │
                    │   ┌───────────────────────────────────────────┐      │
                    │   │           aeo_agent.db (SQLite)            │      │
                    │   │   seen_questions │ aeo_scores │ digests    │      │
                    │   └────────────────┬───────────────────────────┘      │
                    │                    │                                   │
                    │                    ▼                                   │
                    │   ┌───────────────────────────────────────────┐      │
                    │   │  confluent-aeo-web.service                 │      │
                    │   │  Gunicorn → aeo_web:app on 127.0.0.1:5050  │      │
                    │   └────────────────┬───────────────────────────┘      │
                    └────────────────────┼──────────────────────────────────┘
                                         │
                    ┌────────────────────▼──────────────────────────────────┐
                    │   confluent-aeo-tunnel.service                        │
                    │   cloudflared (Cloudflare Quick Tunnel)               │
                    └────────────────────┬──────────────────────────────────┘
                                         │
                                         ▼
                            🌐 https://<random>.trycloudflare.com
                            (sharable URL for the Confluent team)
```

---

## 🧰 Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python **3.11** | Available on Amazon Linux 2023; supports `python-dotenv ≥ 1.2.2` |
| HTTP / scraping | `httpx`, `requests`, `beautifulsoup4` | Async-capable, clean HTML parsing |
| AI drafting | `anthropic` (Claude Sonnet 4.5) | Strong technical-writing quality |
| State / dedup | `sqlite3` (stdlib) | Zero infrastructure |
| Web | `flask` + `gunicorn` | Production-grade WSGI, 2 workers × 4 threads |
| Slack | `slack-sdk` | Official SDK, supports webhook & bot token |
| Public URL | `cloudflared` (Quick Tunnel) | Free, no AWS networking, fast (~370 ms RTT) |
| Scheduler | `systemd` timer | Persistent, runs even after missed window |
| Env config | `python-dotenv` | Already a project pattern |

---

## ⚡ Quick start (TL;DR)

```bash
git clone https://github.com/<you>/confluent-aeo.git
cd confluent-aeo

python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
$EDITOR .env

python3 aeo_agent.py --dry-run

python3 aeo_web.py
```

Open http://localhost:5050 → done. For production hosting see **[Deploy to production](#-deploy-to-production-systemd--cloudflare-tunnel)**.

---

## ✅ Prerequisites

| Required | What you need |
|---|---|
| **OS** | Linux (tested on Amazon Linux 2023). macOS works for local dev. |
| **Python** | 3.11 or newer (`python-dotenv ≥ 1.2.2` requires 3.10+) |
| **`sudo` access** | Only for the systemd hosting setup |
| **Anthropic API key** | Free trial works. Grab one at https://console.anthropic.com/ |

| Optional | What you get |
|---|---|
| **Slack webhook** | Posts the daily digest to a channel (otherwise digest renders in-app) |
| **GitHub PAT** | Raises rate limit from 60 → 5000 req/hr (lets the agent sweep all 11 monitored repos × all keywords) |
| **`cloudflared`** | Public URL for the dashboard (free, no domain required) |

---

## 🛠️ Step-by-step install

### 1. Clone & enter the repo

```bash
git clone https://github.com/<you>/confluent-aeo.git
cd confluent-aeo
```

### 2. Create a Python 3.11 virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

> On Amazon Linux 2023, Python 3.11 is pre-installed at `/usr/bin/python3.11`. On Ubuntu run `sudo apt install -y python3.11 python3.11-venv`. On macOS use Homebrew: `brew install python@3.11`.

### 3. Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Playwright's Chromium browser (used by the Quora scraper fallback)

```bash
python -m playwright install chromium
```

### 5. Configure environment variables

```bash
cp .env.example .env
$EDITOR .env
```

Fill in **`ANTHROPIC_API_KEY`** at minimum. Everything else has safe defaults. See the **[Environment variables](#-environment-variables)** table for what each setting does.

### 6. Smoke-test the agent (no Slack, no DB writes for answers)

```bash
python3 aeo_agent.py --dry-run
```

You should see scraper logs for each topic and a digest printed to the terminal.

### 7. Start the dashboard

```bash
python3 aeo_web.py
```

Open http://localhost:5050.

---

## 🔐 Environment variables

All env vars live in `.env` and are loaded via `python-dotenv` (and `systemd EnvironmentFile=` in production). Anything left blank uses a safe default.

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(empty)_ | **Required** for answer drafting. Get one at https://console.anthropic.com. Without it, drafts are skipped silently. |
| `SLACK_WEBHOOK_URL` | _(empty)_ | Incoming webhook for daily digest. Simplest Slack option. |
| `SLACK_BOT_TOKEN` | _(empty)_ | Alternative to webhook — needed for thread replies & richer formatting. Pair with `SLACK_CHANNEL_ID`. |
| `SLACK_CHANNEL_ID` | _(empty)_ | Channel ID (`C…`) for the bot token path. |
| `LOCAL_DIGEST_URL` | `http://localhost:5050/api/digest` | Fallback target when no Slack creds. Dashboard renders it as "Latest Digest". |
| `AEO_LOCAL_DIGEST_FALLBACK` | `true` | Disable in-app fallback by setting to `false`. |
| `GITHUB_TOKEN` | _(empty)_ | Personal access token (`public_repo` scope). Bumps GitHub rate from 60 → 5000 req/hr. |
| `AEO_DRY_RUN` | `false` | When `true`, prints digest to stdout and does NOT persist answers to the DB or send to Slack. |
| `AEO_DAILY_LIMIT` | `25` | Max questions surfaced per digest. |
| `AEO_LOOKBACK_HOURS` | `13140` | Scrape window. `13140 = 18 months` — wide enough for Jan 2026 onward plus older-impactful candidates. |
| `AEO_LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `AEO_DB_PATH` | `aeo_agent.db` | SQLite location. |
| `AEO_LOG_FILE` | `aeo_agent.log` | Agent log file. |
| `AEO_WEB_PORT` | `5050` | Port the Flask dashboard binds to. |

---

## 💻 Run it locally (dev)

```bash
source .venv/bin/activate

python3 aeo_agent.py --dry-run

python3 aeo_agent.py

python3 aeo_agent.py --limit 50

python3 aeo_web.py
```

Dashboard: http://localhost:5050

---

## 🌍 Deploy to production (systemd + Cloudflare Tunnel)

This sets up **four** systemd units so the agent runs daily, the dashboard auto-starts on boot, and a public HTTPS URL is available for sharing.

### A. Install `cloudflared`

```bash
curl -fsSL -o /tmp/cloudflared.rpm \
  https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-x86_64.rpm
sudo rpm -i --force /tmp/cloudflared.rpm
cloudflared --version
```

### B. Create the four systemd units

**`/etc/systemd/system/confluent-aeo-web.service`** — Flask via Gunicorn

```ini
[Unit]
Description=Confluent AEO Dashboard (Flask via Gunicorn)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ec2-user
Group=ec2-user
WorkingDirectory=/home/ec2-user/aeo
EnvironmentFile=/home/ec2-user/aeo/.env
ExecStart=/home/ec2-user/aeo/.venv/bin/gunicorn \
    --bind 127.0.0.1:5050 --workers 2 --threads 4 --timeout 60 \
    --access-logfile - --error-logfile - aeo_web:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**`/etc/systemd/system/confluent-aeo-agent.service`** — one-shot agent run

```ini
[Unit]
Description=Confluent AEO Agent (daily scrape + Slack digest)
After=network-online.target

[Service]
Type=oneshot
User=ec2-user
WorkingDirectory=/home/ec2-user/aeo
EnvironmentFile=/home/ec2-user/aeo/.env
ExecStart=/home/ec2-user/aeo/.venv/bin/python /home/ec2-user/aeo/aeo_agent.py
```

**`/etc/systemd/system/confluent-aeo-agent.timer`** — daily at 13:30 UTC (= 7:00 PM IST)

```ini
[Unit]
Description=Run Confluent AEO Agent daily at 13:30 UTC

[Timer]
OnCalendar=*-*-* 13:30:00 UTC
Persistent=true
Unit=confluent-aeo-agent.service

[Install]
WantedBy=timers.target
```

**`/etc/systemd/system/confluent-aeo-tunnel.service`** — Cloudflare Quick Tunnel

```ini
[Unit]
Description=Cloudflare Quick Tunnel for Confluent AEO Dashboard
After=network-online.target confluent-aeo-web.service
Requires=confluent-aeo-web.service

[Service]
Type=simple
User=ec2-user
ExecStart=/usr/bin/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:5050
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### C. Enable everything

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now \
  confluent-aeo-web.service \
  confluent-aeo-agent.timer \
  confluent-aeo-tunnel.service
```

### D. Grab the public URL

```bash
sudo journalctl -u confluent-aeo-tunnel.service --since '10 minutes ago' \
  | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1
```

That URL is your team's bookmarkable dashboard. ✨

> ⚠️ **The trycloudflare URL is stable while `cloudflared` stays up, but changes on every restart.** For a permanent URL like `https://aeo.<yourdomain>.com`, see the upgrade path in [`HOSTING.md`](./HOSTING.md).

---

## 🧑‍🔧 Operations cheat-sheet

```bash
systemctl is-active confluent-aeo-web confluent-aeo-tunnel confluent-aeo-agent.timer

sudo journalctl -u confluent-aeo-web -f
sudo journalctl -u confluent-aeo-tunnel -f
sudo journalctl -u confluent-aeo-agent -n 200 --no-pager

sudo systemctl start confluent-aeo-agent.service

sudo systemctl restart confluent-aeo-web
sudo systemctl restart confluent-aeo-tunnel

systemctl list-timers confluent-aeo-agent.timer

sqlite3 /home/ec2-user/aeo/aeo_agent.db \
  "SELECT topic_slug, COUNT(*) FROM seen_questions GROUP BY topic_slug"

sqlite3 /home/ec2-user/aeo/aeo_agent.db \
  "SELECT date(first_seen_date), COUNT(*) FROM seen_questions GROUP BY 1 ORDER BY 1 DESC LIMIT 10"
```

---

## 📂 Project structure

```
.
├── aeo_agent.py                # 🚀 Main agent entrypoint (CLI)
├── aeo_web.py                  # 🌐 Flask dashboard
├── aeo_agent.db                # 💾 SQLite state (auto-created, git-ignored)
├── aeo_agent.log               # 📜 Run log (git-ignored)
├── aeo/
│   ├── __init__.py
│   ├── config.py               # ⚙️  Topics, keywords, repos, subreddits
│   ├── filter.py               # 🧮 Dedup + ranking (recency + impact + priority)
│   ├── answer_drafter.py       # 🤖 Claude API integration
│   ├── slack_notifier.py       # 💬 Slack digest formatting & delivery
│   └── scrapers/
│       ├── _common.py          # 🔧 Shared helpers (Google `tbs` window mapping)
│       ├── reddit.py
│       ├── stackoverflow.py
│       ├── hackernews.py
│       ├── quora.py
│       └── github_discussions.py
├── templates/index.html        # 🎨 Dashboard UI (Alpine.js + Chart.js + Tailwind via CDN)
├── static/                     # Static assets (currently empty)
├── requirements.txt            # 📦 Python deps
├── .env / .env.example         # 🔐 Secrets & tuning (.env is git-ignored)
├── .gitignore
├── AEO_AGENT_SPEC.md           # 📐 Full design spec
├── HOSTING.md                  # 🛰️  Deep-dive: tunnel upgrades & SSO
└── README.md                   # 👋 You are here
```

---

## 🎨 Customising topics & keywords

Edit `aeo/config.py`. Each `TopicConfig` has:

```python
TopicConfig(
    name="…",
    slug="…",                  # used in DB & dashboard
    keywords=[…],              # OR-matched on title + body
    priority_patterns=[…],     # phrases that trigger 🔴 HIGH priority
    doc_url="https://docs.confluent.io/…",  # cited in drafted answers
)
```

Other knobs:

- `GITHUB_REPOS` — repos to query for issues/discussions
- `REDDIT_SUBREDDITS` — subreddits used in Google `site:` searches & RSS fallback
- `DAILY_QUESTION_LIMIT` — overridden by `AEO_DAILY_LIMIT` env var

After changes:

```bash
sudo systemctl restart confluent-aeo-web
sudo systemctl start confluent-aeo-agent.service
```

---

## 🔧 Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Address already in use` on port 5050 | A stray `python3 aeo_web.py` is running | `sudo lsof -i :5050` → `kill <pid>` → `sudo systemctl restart confluent-aeo-web` |
| `python-dotenv` install fails | venv is Python 3.9 | Recreate venv with `python3.11 -m venv .venv` |
| Tunnel URL changes | Quick tunnels rotate on `cloudflared` restart | Upgrade to a named tunnel — see [`HOSTING.md`](./HOSTING.md) |
| Agent finds 0 new questions | Same upstream content was already deduped | Add more keywords, set `GITHUB_TOKEN`, or just wait — the daily timer will catch fresh content |
| 403 from GitHub | Rate-limited (60 req/hr unauthenticated) | Add `GITHUB_TOKEN=ghp_…` to `.env`, restart agent |
| Answers empty in DB | Running with `AEO_DRY_RUN=true` | Flip to `false` in `.env` |
| Chart "Last 7 Days" shows one bar | All questions have `first_seen_date = today` | Agent needs to run on multiple distinct days; daily timer takes care of this |
| Playwright complains about missing browsers | Forgot step 4 of install | `.venv/bin/python -m playwright install chromium` |

Full deep-dive logs:

```bash
sudo journalctl -u confluent-aeo-agent -n 500 --no-pager | less
```

---

## 🗺️ Roadmap / out-of-scope (v1)

- 🚫 Auto-posting answers (human reviews & posts manually)
- 🚫 Twitter/X & LinkedIn monitoring
- 🚫 Multi-language support
- 🚫 Answer performance tracking (upvotes, citations earned)
- ✅ Web dashboard (shipped)
- ✅ AEO score tracking over time (shipped)
- ✅ Local digest fallback (shipped)
- 🔜 Named-tunnel + SSO restricted to `@confluent.io`

---

## 📝 License & ownership

Internal Confluent project. Last updated **May 2026** · Owner: **kkesav@confluent.io**

---

<p align="center">
  Built for the AEO team at <a href="https://confluent.io">Confluent</a> · Made with ☕ and a healthy distrust of free tunnels
</p>
