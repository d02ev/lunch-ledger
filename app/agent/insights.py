from __future__ import annotations
import os
from openai import AsyncOpenAI
from app.models import SpendSummary

_client = AsyncOpenAI(
    base_url="https://models.inference.ai.azure.com",
    api_key=os.getenv("GITHUB_TOKEN"),
)


async def generate_insight(summary: SpendSummary) -> str:
    """
    Uses gpt-4o-mini via GitHub Models to generate a 2-3 sentence
    spend insight based on the team's food spend data.
    """
    budget_status = (
        "on track"       if summary.total_spend <= summary.budget * 0.8
        else "nearing limit" if summary.total_spend <= summary.budget
        else "over budget"
    )
    delivery_pct = (
        int(summary.delivery_spend / summary.total_spend * 100)
        if summary.total_spend > 0 else 0
    )

    prompt = (
        "You are a financial advisor for a small team's food budget. "
        "Analyze this spend data and give a 2-3 sentence actionable insight. "
        "Be specific, practical, and slightly conversational. No bullet points.\n\n"
        f"Period: {summary.period}\n"
        f"Total spend: ₹{summary.total_spend} / Budget: ₹{summary.budget} ({budget_status})\n"
        f"Delivery: ₹{summary.delivery_spend} ({delivery_pct}%) | "
        f"Dine-out: ₹{summary.dineout_spend} ({100 - delivery_pct}%)\n"
        f"Orders placed: {summary.session_count}\n"
        f"Top restaurant: {summary.top_restaurant or 'N/A'}\n"
        f"Per-member spend: {summary.per_member}\n\n"
        "Give one observation about the spending pattern and one concrete saving suggestion."
    )

    response = await _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()