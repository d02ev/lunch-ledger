from __future__ import annotations
from statistics import median
from app.models import MemberPreference, AggregatedPreference


def aggregate(preferences: dict[str, MemberPreference]) -> AggregatedPreference:
    """
    Converts raw member preferences into a single aggregated preference
    for the LangChain agent to act on.

    Rules:
    - Dietary: UNION of all restrictions (hard constraints — any violation = 0)
    - Cuisine:  majority vote scoring (soft preference)
    - Budget:   median (protects against outliers)
    - Mode:     majority vote; "no_preference" abstains
    """
    prefs = list(preferences.values())

    # ── Hard constraints (dietary) ─────────────────────────────────────────────
    hard_constraints: set[str] = set()
    for p in prefs:
        for d in p.dietary:
            if d != "none":
                hard_constraints.add(d)

    # ── Cuisine scoring ────────────────────────────────────────────────────────
    cuisine_scores: dict[str, int] = {}
    for p in prefs:
        for c in p.cuisine:
            if c != "any":
                cuisine_scores[c] = cuisine_scores.get(c, 0) + 1

    # ── Budget ceiling (median) ────────────────────────────────────────────────
    budgets = [p.budget for p in prefs]
    budget_ceiling = int(median(budgets)) if budgets else 400

    # ── Mode voting ───────────────────────────────────────────────────────────
    mode_votes: dict[str, int] = {"delivery": 0, "dine_out": 0}
    for p in prefs:
        if p.mode in mode_votes:
            mode_votes[p.mode] += 1

    if mode_votes["delivery"] >= mode_votes["dine_out"]:
        mode = "delivery"
    else:
        mode = "dine_out"

    return AggregatedPreference(
        mode=mode,
        hard_constraints=sorted(hard_constraints),
        cuisine_scores=cuisine_scores,
        budget_ceiling=budget_ceiling,
        member_count=len(prefs),
    )


def format_for_agent(agg: AggregatedPreference) -> str:
    """
    Produces a clear natural-language brief for the LangChain agent prompt.
    """
    cuisine_ranked = sorted(
        agg.cuisine_scores.items(), key=lambda x: x[1], reverse=True
    )
    cuisine_str = (
        ", ".join(f"{c} ({v} votes)" for c, v in cuisine_ranked)
        if cuisine_ranked
        else "no strong preference"
    )
    constraints_str = (
        ", ".join(agg.hard_constraints) if agg.hard_constraints else "none"
    )

    return (
        f"Team size: {agg.member_count}\n"
        f"Mode: {agg.mode}\n"
        f"Dietary restrictions (hard — must satisfy all): {constraints_str}\n"
        f"Cuisine preferences (soft — ranked): {cuisine_str}\n"
        f"Budget ceiling per person: ₹{agg.budget_ceiling}\n"
    )