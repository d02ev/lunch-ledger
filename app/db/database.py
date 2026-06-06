from __future__ import annotations
import os
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, DateTime, Text
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/lunchleger.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ── ORM Tables ─────────────────────────────────────────────────────────────────

class OrderRecord(Base):
    """One row per completed lunch session."""
    __tablename__ = "orders"

    session_id      = Column(String, primary_key=True)
    channel_id      = Column(String, nullable=False, index=True)
    restaurant_name = Column(String, nullable=False)
    restaurant_id   = Column(String, nullable=False)
    mode            = Column(String, nullable=False)   # delivery | dineout
    total_amount    = Column(Integer, nullable=False)
    agent_reasoning = Column(Text, default="")
    order_ref       = Column(String, nullable=True)
    placed_at       = Column(DateTime, default=datetime.utcnow)


class MemberSpend(Base):
    """Per-member spend breakdown for each session."""
    __tablename__ = "member_spend"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    session_id   = Column(String, nullable=False, index=True)
    channel_id   = Column(String, nullable=False, index=True)
    member_name  = Column(String, nullable=False)
    amount       = Column(Integer, nullable=False)
    placed_at    = Column(DateTime, default=datetime.utcnow)


class TeamBudget(Base):
    """Monthly budget per channel."""
    __tablename__ = "team_budget"

    channel_id = Column(String, primary_key=True)
    monthly_budget = Column(Integer, default=15000)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ── Init ───────────────────────────────────────────────────────────────────────

async def init_db() -> None:
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session