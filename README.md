# 🧾 LunchLedger

> **Team Lunch Coordinator + Food Spend Intelligence**
> A Slack bot that coordinates team lunch orders across Swiggy's Food and Dineout MCPs —
> and tracks every rupee spent, so your team always knows where the food budget goes.

---

## The Problem

Office teams waste 10–15 minutes every day debating where to order lunch. And nobody tracks
how much the team actually spends on food until the month-end bill arrives.

LunchLedger solves both — in Slack, where the conversation already happens.

---

## Demo Flow

```
/lunch start
→ Bot opens a session with a "Join & Set Preferences" button

[Alice, Bob, Charlie each click the button and fill a modal]
→ Dietary restrictions, cuisine preference, budget, delivery vs dine-out

/lunch go
→ LangChain agent aggregates preferences
→ Routes to Food MCP (delivery) or Dineout MCP (dine-in) based on majority vote
→ Applies hard dietary constraints, scores cuisine preferences, enforces budget ceiling
→ Posts: restaurant pick + reasoning + per-person cost breakdown + Confirm button

[Team clicks Confirm]
→ Order logged to SQLite ledger

/lunch report monthly
→ Total spend vs budget, delivery/dine-out split, top restaurant, per-person breakdown
→ AI-generated insight: "You're on track but spending 40% more on Fridays..."
```

---

## Architecture

```
Slack (Bolt + Socket Mode)
         │
    FastAPI app
    ┌────┴────────────┐
Session Manager    SQLite Ledger
(in-memory)        (aiosqlite)
    │                   │
Preference          Spend Reports
Aggregator          + Budget Tracking
    │                   │
LangChain Agent ────────┘
  ┌──────┴──────┐
Food MCP    Dineout MCP     GitHub Models
(delivery)  (dine-in)       gpt-4o-mini
                            (agent + insights)
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| Socket Mode (no ngrok) | Zero infrastructure overhead — no redirect URIs, no public URL needed |
| SQLite + aiosqlite | No DB server needed; persists across restarts via Docker volume |
| uv | Fast, deterministic installs; single tool for env + package management |
| GitHub Models (free tier) | Single `GITHUB_TOKEN` covers all LLM calls — agent and insights |
| `gpt-4o-mini` for everything | Best tool-calling support on GitHub Models; well within free-tier rate limits |
| Dietary = hard constraint | Union of all restrictions — any violation disqualifies a restaurant |
| Budget = median | Protects against outliers pulling the ceiling too high or low |
| Mode = majority vote | Democratic; agent explains the tiebreak in its reasoning |
| Insights via LLM | Natural language > charts for a Slack-native experience |

---

## Setup

### 1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

uv is the package and environment manager for this project. It replaces pip and venv.

### 2. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Under **Socket Mode** → Enable Socket Mode → Generate an App-Level Token (`xapp-...`) with `connections:write` scope
3. Under **OAuth & Permissions** → Add Bot Token Scopes:
   - `commands`, `chat:write`, `chat:write.public`, `im:write`, `channels:read`
4. Under **Slash Commands** → Add `/lunch`
5. Under **Interactivity & Shortcuts** → Enable (required for modals and buttons)
6. Install to workspace → copy Bot Token (`xoxb-...`)

> No redirect URIs are required. Socket Mode uses an outbound WebSocket connection
> from your server to Slack — no inbound HTTP endpoint is ever registered.

### 3. Get a GitHub Token

Go to [github.com/settings/tokens](https://github.com/settings/tokens) → Generate a classic token.
No special scopes needed — GitHub Models only requires a valid token.

This single token covers **all LLM calls** in the project (agent orchestration + spend insights).

### 4. Configure environment

```bash
cp .env.example .env
```

Fill in the four required variables:

```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SWIGGY_API_KEY=...
GITHUB_TOKEN=ghp_...
```

Everything else has a working default and can be left as-is for the demo.

### 5. Run

```bash
# Option A — Docker (recommended for demo)
docker compose up --build

# Option B — Local with uv
uv sync                           # creates .venv + installs all deps
uv run uvicorn main:api --reload
```

### Health check

```
GET http://localhost:8000/health
→ {"status": "ok", "service": "LunchLedger"}
```

---

## Environment Variables

### Required

| Variable | Where to get it |
|---|---|
| `SLACK_BOT_TOKEN` | Slack App → OAuth & Permissions → Bot User OAuth Token (`xoxb-...`) |
| `SLACK_APP_TOKEN` | Slack App → Basic Information → App-Level Tokens (`xapp-...`) |
| `SWIGGY_API_KEY` | Swiggy MCP Builders Club dashboard |
| `GITHUB_TOKEN` | [github.com/settings/tokens](https://github.com/settings/tokens) |

### Optional (have sensible defaults)

| Variable | Default | Notes |
|---|---|---|
| `SWIGGY_MCP_URL` | `https://mcp.swiggy.com/sse` | Override if Swiggy changes the endpoint |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/lunchleger.db` | SQLite file path |
| `SESSION_TIMEOUT_MINUTES` | `15` | How long a session waits for preferences |
| `DEFAULT_MONTHLY_BUDGET` | `15000` | Default team budget in ₹ |
| `DEFAULT_LAT` | `12.9716` | Restaurant search latitude (Bangalore) |
| `DEFAULT_LNG` | `77.5946` | Restaurant search longitude (Bangalore) |

---

## Commands Reference

| Command | Description |
|---|---|
| `/lunch start` | Open a new team lunch session |
| `/lunch go` | Trigger the agent immediately (skip the timeout) |
| `/lunch status` | See who has joined and how much time is left |
| `/lunch cancel` | Cancel the active session |
| `/lunch report` | Weekly spend summary |
| `/lunch report monthly` | Monthly spend summary |
| `/lunch budget set 15000` | Set the monthly team food budget (₹) |
| `/lunch insights` | AI-generated spend pattern analysis |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Package / Env Manager | [uv](https://docs.astral.sh/uv/) |
| API Framework | FastAPI + Uvicorn |
| Slack Integration | Slack Bolt for Python (Socket Mode) |
| Agent Orchestration | LangChain (ReAct) |
| LLM | `gpt-4o-mini` via [GitHub Models](https://github.com/marketplace/models) |
| MCP Servers | Swiggy Food MCP + Dineout MCP |
| Database | SQLite via aiosqlite + SQLAlchemy async ORM |
| Data Validation | Pydantic v2 |
| HTTP Client | httpx (async) |
| Containerisation | Docker + Docker Compose (uv base image) |

---

## Project Structure

```
lunchleger/
├── main.py                           # FastAPI entrypoint + Socket Mode lifespan startup
├── pyproject.toml                    # uv project manifest + all dependencies
├── .python-version                   # pins Python 3.12
├── Dockerfile                        # ghcr.io/astral-sh/uv base image
├── docker-compose.yml                # one-command run with SQLite volume
├── .env.example                      # all env vars with descriptions
└── app/
    ├── models/
    │   └── schemas.py                # Pydantic v2 models: preferences, sessions, orders, spend
    ├── core/
    │   ├── session_manager.py        # In-memory session lifecycle + auto-expiry
    │   └── preference_aggregator.py  # Constraint satisfaction + cuisine scoring
    ├── db/
    │   ├── database.py               # SQLAlchemy async engine + ORM table definitions
    │   └── ledger.py                 # Repository: save orders, read spend summaries
    ├── agent/
    │   ├── swiggy_client.py          # Async HTTP wrappers for Food + Dineout MCP tools
    │   ├── lunch_agent.py            # LangChain ReAct agent + multi-MCP routing
    │   └── insights.py               # gpt-4o-mini spend insight generator (GitHub Models)
    └── bot/
        ├── handlers.py               # All slash commands + Slack interaction handlers
        └── blocks.py                 # Block Kit message and modal builders
```

---

## Built for Swiggy MCP Builders Club

This project was built as part of the [Swiggy MCP Builders Club](https://mcp.swiggy.com/builders/developers/).
It uses the **Food MCP** and **Dineout MCP** servers, chaining them through a single LangChain
ReAct agent that routes based on team preference voting — delivery or dine-out, decided democratically.

The financial layer — spend tracking, budget alerts, and AI-generated insights — is the
differentiating angle: treating team food spend as an operations problem, not just an ordering problem.