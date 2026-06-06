from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


# ── Preference Models ──────────────────────────────────────────────────────────

DIETARY_OPTIONS = ["vegetarian", "vegan", "no_nuts", "halal", "gluten_free", "none"]
CUISINE_OPTIONS = ["indian", "chinese", "italian", "mexican", "continental", "any"]

class MemberPreference(BaseModel):
    member_id: str
    member_name: str
    dietary: list[str] = Field(default_factory=list)   # hard constraints
    cuisine: list[str] = Field(default_factory=list)   # soft preferences
    budget: int = Field(default=400, ge=100, le=2000)  # ₹ per person
    mode: Literal["delivery", "dine_out", "no_preference"] = "no_preference"


# ── Session Models ─────────────────────────────────────────────────────────────

class LunchSession(BaseModel):
    session_id: str
    channel_id: str
    created_by: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    preferences: dict[str, MemberPreference] = Field(default_factory=dict)
    status: Literal["open", "processing", "completed", "cancelled"] = "open"
    message_ts: str | None = None  # Slack message timestamp for updates


class AggregatedPreference(BaseModel):
    mode: Literal["delivery", "dine_out"]
    hard_constraints: list[str]   # dietary restrictions (union)
    cuisine_scores: dict[str, int]  # cuisine → vote count
    budget_ceiling: int            # median budget
    member_count: int


# ── Order / Booking Models ─────────────────────────────────────────────────────

class OrderItem(BaseModel):
    member_name: str
    items: list[str]
    amount: int


class PlacedOrder(BaseModel):
    session_id: str
    channel_id: str
    restaurant_name: str
    restaurant_id: str
    mode: Literal["delivery", "dine_out"]
    total_amount: int
    per_member: list[OrderItem]
    placed_at: datetime = Field(default_factory=datetime.utcnow)
    order_ref: str | None = None     # Swiggy order/booking ref
    agent_reasoning: str = ""        # why this restaurant was picked


# ── Finance Models ─────────────────────────────────────────────────────────────

class SpendSummary(BaseModel):
    period: str                       # "weekly" | "monthly"
    total_spend: int
    budget: int
    delivery_spend: int
    dineout_spend: int
    session_count: int
    top_restaurant: str | None
    per_member: dict[str, int]        # member_name → spend
    insight: str = ""                 # Claude-generated insight