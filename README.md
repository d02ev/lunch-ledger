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
→ Claude-generated insight: "You're on track but spending 40% more on Fridays..."
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
Food MCP    Dineout MCP        Claude API
(delivery)  (dine-in)         (insights)
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| Socket Mode (no ngrok) | Zero infrastructure overhead for demo and local dev |
| SQLite + aiosqlite | No DB server needed; persists across restarts via Docker volume |
| Dietary = hard constraint | Union of all restrictions — any violation disqualifies a restaurant |
| Budget = median | Protects against outliers pulling the ceiling too high or low |
| Mode = majority vote | Democratic; agent explains the tiebreak in its reasoning |
| Insights via Claude API | Natural language > charts for a Slack-native experience |

---

## Setup

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Under **Socket Mode** → Enable Socket Mode → Generate an App-Level Token (`xapp-...`)
3. Under **OAuth & Permissions** → Add Bot Token Scopes:
   - `commands`, `chat:write`, `chat:write.public`, `im:write`
4. Under **Slash Commands** → Add `/lunch`
5. Under **Interactivity & Shortcuts** → Enable → Request URL can be anything (Socket Mode ignores it)
6. Install to workspace → copy Bot Token (`xoxb-...`)

### 2. Configure environment

```bash
cp .env.example .env
# Fill in SLACK_BOT_TOKEN, SLACK_APP_TOKEN, SWIGGY_API_KEY, ANTHROPIC_API_KEY
```

### 3. Run

```bash
# Option A — Docker (recommended for demo)
docker compose up --build

# Option B — Local with uv
uv sync                          # creates .venv + installs all deps from pyproject.toml
uv run uvicorn main:api --reload
```

> **uv** is the package and environment manager for this project.
> Install it first if needed:
> ```bash
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```

---

## Commands Reference

| Command | Description |
|---|---|
| `/lunch start` | Open a new team lunch session |
| `/lunch go` | Trigger the agent immediately |
| `/lunch status` | See who's joined the current session |
| `/lunch cancel` | Cancel the active session |
| `/lunch report` | Weekly spend summary |
| `/lunch report monthly` | Monthly spend summary |
| `/lunch budget set 15000` | Set monthly team budget (₹) |
| `/lunch insights` | AI-generated spend pattern analysis |

---

## Tech Stack

- **[FastAPI](https://fastapi.tiangolo.com/)** — async API server
- **[Slack Bolt for Python](https://slack.dev/bolt-python/)** — Slack bot framework
- **[LangChain](https://python.langchain.com/)** — agent orchestration
- **[Swiggy MCP](https://mcp.swiggy.com/)** — Food + Dineout MCP servers
- **[Anthropic Claude API](https://anthropic.com/)** — spend insight generation
- **SQLAlchemy + aiosqlite** — async SQLite ORM
- **Pydantic v2** — data validation throughout

---

## Project Structure

```
lunchleger/
├── main.py                      # FastAPI entrypoint + Socket Mode startup
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── app/
    ├── models/
    │   └── schemas.py           # Pydantic models: preferences, sessions, orders, spend
    ├── core/
    │   ├── session_manager.py   # In-memory session lifecycle
    │   └── preference_aggregator.py  # Constraint satisfaction + scoring
    ├── db/
    │   ├── database.py          # SQLAlchemy async engine + ORM tables
    │   └── ledger.py            # Repository: save orders, read spend summaries
    ├── agent/
    │   ├── swiggy_client.py     # Async wrappers for Food + Dineout MCP tools
    │   ├── lunch_agent.py       # LangChain ReAct agent + multi-MCP routing
    │   └── insights.py          # Claude API spend insight generator
    └── bot/
        ├── handlers.py          # All slash commands + interaction handlers
        └── blocks.py            # Block Kit message builders
```

---

## Built for Swiggy MCP Builders Club

This project was built as part of the [Swiggy MCP Builders Club](https://mcp.swiggy.com/builders/developers/).
It uses the **Food MCP** and **Dineout MCP** servers, chaining them through a single LangChain agent
that routes based on team preference voting.

The financial layer — spend tracking, budget alerts, and Claude-generated insights — is the
differentiating feature: treating team food spend as an operations problem, not just an ordering problem.