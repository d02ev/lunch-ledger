from __future__ import annotations
import os
from datetime import date
from langchain.agents import AgentExecutor, create_react_agent
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain import hub
from app.models import AggregatedPreference, PlacedOrder, OrderItem
from app.agent import swiggy_client

# Default location — override via env or pass dynamically
DEFAULT_LAT = float(os.getenv("DEFAULT_LAT", "12.9716"))
DEFAULT_LNG = float(os.getenv("DEFAULT_LNG", "77.5946"))


# ── LangChain Tools ────────────────────────────────────────────────────────────

@tool
async def search_delivery_restaurants(query: str) -> str:
    """Search for food delivery restaurants matching a cuisine query."""
    result = await swiggy_client.search_restaurants(
        query=query,
        latitude=DEFAULT_LAT,
        longitude=DEFAULT_LNG,
    )
    return str(result)


@tool
async def search_dineout_restaurants(query: str) -> str:
    """Search for dine-out restaurants matching a cuisine query."""
    result = await swiggy_client.search_dineout_restaurants(
        query=query,
        latitude=DEFAULT_LAT,
        longitude=DEFAULT_LNG,
    )
    return str(result)


@tool
async def get_menu(restaurant_id: str) -> str:
    """Get the menu for a specific restaurant by its ID."""
    result = await swiggy_client.get_restaurant_menu(restaurant_id)
    return str(result)


@tool
async def check_dineout_slots(restaurant_id_and_party_size: str) -> str:
    """
    Check available dine-out slots.
    Input format: 'restaurant_id|party_size'  e.g. 'rest_123|4'
    """
    parts = restaurant_id_and_party_size.split("|")
    restaurant_id = parts[0].strip()
    party_size = int(parts[1].strip()) if len(parts) > 1 else 4
    result = await swiggy_client.get_available_slots(
        restaurant_id=restaurant_id,
        date=date.today().isoformat(),
        party_size=party_size,
    )
    return str(result)


@tool
async def build_delivery_cart(restaurant_id_and_items: str) -> str:
    """
    Build a delivery cart.
    Input format: 'restaurant_id|item_id:qty,item_id:qty'
    e.g. 'rest_123|item_1:2,item_2:1'
    """
    parts = restaurant_id_and_items.split("|")
    restaurant_id = parts[0].strip()
    items = []
    if len(parts) > 1:
        for pair in parts[1].split(","):
            item_id, qty = pair.strip().split(":")
            items.append({"item_id": item_id.strip(), "quantity": int(qty.strip())})
    result = await swiggy_client.update_food_cart(restaurant_id, items)
    return str(result)


TOOLS = [
    search_delivery_restaurants,
    search_dineout_restaurants,
    get_menu,
    check_dineout_slots,
    build_delivery_cart,
]


# ── Agent Builder ──────────────────────────────────────────────────────────────

GITHUB_TOKEN   = os.getenv("GITHUB_TOKEN")
GITHUB_MODELS_URL = "https://models.inference.ai.azure.com"


def build_agent() -> AgentExecutor:
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        base_url=GITHUB_MODELS_URL,
        api_key=GITHUB_TOKEN,
    )
    prompt = hub.pull("hwchase17/react")
    agent = create_react_agent(llm, TOOLS, prompt)
    return AgentExecutor(agent=agent, tools=TOOLS, verbose=True, max_iterations=8)


# ── Main Orchestration Entry Point ─────────────────────────────────────────────

async def run_lunch_agent(
    agg: AggregatedPreference,
    session_id: str,
    channel_id: str,
    team_members: list[str],
) -> PlacedOrder:
    """
    Runs the LangChain agent with aggregated preferences.
    Returns a PlacedOrder (dry-run safe — actual placement is gated by Slack confirm button).
    """
    constraints = ", ".join(agg.hard_constraints) if agg.hard_constraints else "none"
    top_cuisines = sorted(agg.cuisine_scores.items(), key=lambda x: x[1], reverse=True)
    cuisine_hint = top_cuisines[0][0] if top_cuisines else "any"

    task = f"""
You are a team lunch coordinator. Your job is to find the best restaurant for a team
and explain your reasoning clearly.

Team preferences:
- Mode: {agg.mode}
- Dietary restrictions (HARD — must satisfy ALL): {constraints}
- Top cuisine preference: {cuisine_hint}
- Budget ceiling per person: ₹{agg.budget_ceiling}
- Team size: {agg.member_count}

Steps:
1. Search for {agg.mode} restaurants for "{cuisine_hint}" cuisine.
2. If mode is "delivery", also check the menu and build a sample cart.
3. If mode is "dine_out", check available slots for today.
4. Pick the best restaurant that satisfies ALL dietary restrictions and fits the budget.
5. Clearly explain WHY you picked this restaurant in 2-3 sentences.
6. Return your final answer in this exact format:
   RESTAURANT_NAME: <name>
   RESTAURANT_ID: <id>
   REASONING: <your 2-3 sentence explanation>
   CART_OR_SLOT: <cart_id or slot_id from the API>
   ESTIMATED_TOTAL: <total in ₹>
"""

    executor = build_agent()
    result = await executor.ainvoke({"input": task})
    output = result.get("output", "")

    # ── Parse agent output ────────────────────────────────────────────────────
    lines = {
        k.strip(): v.strip()
        for line in output.splitlines()
        if ":" in line
        for k, v in [line.split(":", 1)]
    }

    restaurant_name = lines.get("RESTAURANT_NAME", "Unknown Restaurant")
    restaurant_id   = lines.get("RESTAURANT_ID", "unknown_id")
    reasoning       = lines.get("REASONING", output[:300])
    estimated_total = int("".join(filter(str.isdigit, lines.get("ESTIMATED_TOTAL", "0"))) or "0")

    # Distribute total evenly across members (simplified)
    per_person = estimated_total // max(len(team_members), 1)
    per_member = [
        OrderItem(member_name=name, items=[], amount=per_person)
        for name in team_members
    ]

    return PlacedOrder(
        session_id=session_id,
        channel_id=channel_id,
        restaurant_name=restaurant_name,
        restaurant_id=restaurant_id,
        mode=agg.mode,
        total_amount=estimated_total,
        per_member=per_member,
        agent_reasoning=reasoning,
    )