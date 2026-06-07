from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from dotenv import load_dotenv

from app.db.database import init_db
from app.bot.handlers import app as slack_app, handler

load_dotenv()

SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")


# ── Lifespan: DB init + Socket Mode startup ────────────────────────────────────

@asynccontextmanager
async def lifespan(api: FastAPI):
    # Initialise SQLite tables
    await init_db()
    print("✅ Database initialised")

    # Start Slack Socket Mode in background
    socket_handler = AsyncSocketModeHandler(slack_app, SLACK_APP_TOKEN)
    task = asyncio.create_task(socket_handler.start_async())
    print("✅ Slack Socket Mode connected")

    yield

    task.cancel()
    print("🔌 Slack Socket Mode disconnected")


# ── FastAPI app ────────────────────────────────────────────────────────────────

api = FastAPI(
    title="LunchLedger",
    description="Team Lunch Coordinator + Food Spend Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)


@api.get("/health")
async def health():
    return {"status": "ok", "service": "LunchLedger"}


@api.post("/slack/events")
async def slack_events(req: Request):
    """Fallback HTTP endpoint (not used in Socket Mode but useful for testing)."""
    return await handler.handle(req)


@api.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
    )