from __future__ import annotations
import os
import httpx
from typing import Any
from dotenv import load_dotenv

load_dotenv()

SWIGGY_MCP_URL = os.getenv("SWIGGY_MCP_URL", "https://mcp.swiggy.com/sse")
SWIGGY_API_KEY = os.getenv("SWIGGY_API_KEY", "")

HEADERS = {
    "Authorization": f"Bearer {SWIGGY_API_KEY}",
    "Content-Type": "application/json",
}


async def _call(tool: str, params: dict) -> dict[str, Any]:
    """Generic MCP tool call via HTTP POST."""
    payload = {"tool": tool, "params": params}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(SWIGGY_MCP_URL, json=payload, headers=HEADERS)
        resp.raise_for_status()
        return resp.json()


# ── Food MCP ───────────────────────────────────────────────────────────────────

async def search_restaurants(
    query: str,
    latitude: float,
    longitude: float,
    dietary_filters: list[str] | None = None,
) -> dict:
    return await _call("search_restaurants", {
        "query": query,
        "latitude": latitude,
        "longitude": longitude,
        "dietary_filters": dietary_filters or [],
    })


async def get_restaurant_menu(restaurant_id: str) -> dict:
    return await _call("get_restaurant_menu", {"restaurant_id": restaurant_id})


async def update_food_cart(restaurant_id: str, items: list[dict]) -> dict:
    """items: [{"item_id": str, "quantity": int}]"""
    return await _call("update_food_cart", {
        "restaurant_id": restaurant_id,
        "items": items,
    })


async def place_food_order(cart_id: str, address: str) -> dict:
    return await _call("place_food_order", {
        "cart_id": cart_id,
        "delivery_address": address,
    })


async def track_food_order(order_id: str) -> dict:
    return await _call("track_food_order", {"order_id": order_id})


# ── Dineout MCP ────────────────────────────────────────────────────────────────

async def search_dineout_restaurants(
    query: str,
    latitude: float,
    longitude: float,
    dietary_filters: list[str] | None = None,
) -> dict:
    return await _call("search_restaurants_dineout", {
        "query": query,
        "latitude": latitude,
        "longitude": longitude,
        "dietary_filters": dietary_filters or [],
    })


async def get_available_slots(restaurant_id: str, date: str, party_size: int) -> dict:
    """date: YYYY-MM-DD"""
    return await _call("get_available_slots", {
        "restaurant_id": restaurant_id,
        "date": date,
        "party_size": party_size,
    })


async def book_table(
    restaurant_id: str, slot_id: str, party_size: int, user_name: str
) -> dict:
    return await _call("book_table", {
        "restaurant_id": restaurant_id,
        "slot_id": slot_id,
        "party_size": party_size,
        "user_name": user_name,
    })