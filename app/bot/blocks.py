from __future__ import annotations
from app.models import LunchSession, PlacedOrder, AggregatedPreference, SpendSummary

HELP_TEXT = """
*LunchLedger Commands*
• `/lunch start` — Open a new team lunch session
• `/lunch go` — Trigger the agent now (don't wait for timeout)
• `/lunch status` — See who's joined the current session
• `/lunch cancel` — Cancel the current session
• `/lunch report [weekly|monthly]` — View spend summary
• `/lunch budget set <amount>` — Set monthly team budget (₹)
• `/lunch insights` — AI-generated spend patterns
""".strip()


# ── Session Open Message ───────────────────────────────────────────────────────

def session_open(session: LunchSession) -> list[dict]:
    joined = list(session.preferences.values())
    joined_text = (
        "\n".join(f"• {p.member_name}" for p in joined)
        if joined else "_No one yet — be the first!_"
    )

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🍽️ Lunch Session Open"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Session ID*\n`{session.session_id}`"},
                {"type": "mrkdwn", "text": f"*Opened by*\n<@{session.created_by}>"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Team joined ({len(joined)}):*\n{joined_text}",
            },
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🙋 Join & Set Preferences"},
                    "style": "primary",
                    "action_id": "join_session",
                    "value": session.session_id,
                }
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Use `/lunch go` when everyone's joined · `/lunch cancel` to abort",
                }
            ],
        },
    ]


# ── Preference Modal ───────────────────────────────────────────────────────────

def preference_modal(session_id: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "submit_preferences",
        "private_metadata": session_id,
        "title": {"type": "plain_text", "text": "Your Lunch Preferences"},
        "submit": {"type": "plain_text", "text": "Submit"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "dietary_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Dietary Restrictions"},
                "hint": {"type": "plain_text", "text": "These are hard constraints — all must be satisfied"},
                "element": {
                    "type": "multi_static_select",
                    "action_id": "dietary_select",
                    "placeholder": {"type": "plain_text", "text": "Select all that apply"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "🥗 Vegetarian"}, "value": "vegetarian"},
                        {"text": {"type": "plain_text", "text": "🌱 Vegan"}, "value": "vegan"},
                        {"text": {"type": "plain_text", "text": "🥜 No Nuts"}, "value": "no_nuts"},
                        {"text": {"type": "plain_text", "text": "☪️ Halal"}, "value": "halal"},
                        {"text": {"type": "plain_text", "text": "🌾 Gluten-Free"}, "value": "gluten_free"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "cuisine_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Cuisine Preference"},
                "hint": {"type": "plain_text", "text": "Pick your favourites — majority wins"},
                "element": {
                    "type": "multi_static_select",
                    "action_id": "cuisine_select",
                    "placeholder": {"type": "plain_text", "text": "Select cuisines"},
                    "options": [
                        {"text": {"type": "plain_text", "text": "🍛 Indian"}, "value": "indian"},
                        {"text": {"type": "plain_text", "text": "🍜 Chinese"}, "value": "chinese"},
                        {"text": {"type": "plain_text", "text": "🍕 Italian"}, "value": "italian"},
                        {"text": {"type": "plain_text", "text": "🌮 Mexican"}, "value": "mexican"},
                        {"text": {"type": "plain_text", "text": "🥗 Continental"}, "value": "continental"},
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "budget_block",
                "label": {"type": "plain_text", "text": "Budget per person (₹)"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "budget_input",
                    "placeholder": {"type": "plain_text", "text": "e.g. 350"},
                    "initial_value": "400",
                },
            },
            {
                "type": "input",
                "block_id": "mode_block",
                "label": {"type": "plain_text", "text": "Delivery or Dine-out?"},
                "element": {
                    "type": "static_select",
                    "action_id": "mode_select",
                    "options": [
                        {"text": {"type": "plain_text", "text": "🛵 Delivery"}, "value": "delivery"},
                        {"text": {"type": "plain_text", "text": "🍽️ Dine-out"}, "value": "dine_out"},
                        {"text": {"type": "plain_text", "text": "🤷 No preference"}, "value": "no_preference"},
                    ],
                    "initial_option": {
                        "text": {"type": "plain_text", "text": "🤷 No preference"},
                        "value": "no_preference",
                    },
                },
            },
        ],
    }


# ── Order Result Message ───────────────────────────────────────────────────────

def order_result(order: PlacedOrder, agg: AggregatedPreference) -> list[dict]:
    mode_emoji = "🛵" if order.mode == "delivery" else "🍽️"
    mode_label = "Delivery" if order.mode == "delivery" else "Dine-out"

    constraints = ", ".join(agg.hard_constraints) if agg.hard_constraints else "none"
    top_cuisine = (
        max(agg.cuisine_scores, key=agg.cuisine_scores.get)
        if agg.cuisine_scores else "any"
    )

    per_member_text = "\n".join(
        f"• {m.member_name}: ₹{m.amount:,}"
        for m in order.per_member
    )

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{mode_emoji} Lunch Pick Ready!"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Restaurant*\n{order.restaurant_name}"},
                {"type": "mrkdwn", "text": f"*Mode*\n{mode_label}"},
                {"type": "mrkdwn", "text": f"*Total*\n₹{order.total_amount:,}"},
                {"type": "mrkdwn", "text": f"*Team size*\n{len(order.per_member)} people"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*🤖 Why this pick?*\n{order.agent_reasoning}\n\n"
                    f"*Constraints applied:* {constraints} | "
                    f"*Top cuisine:* {top_cuisine} | "
                    f"*Budget ceiling:* ₹{agg.budget_ceiling}"
                ),
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Per person:*\n{per_member_text}"},
        },
        {"type": "divider"},
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Confirm & Order"},
                    "style": "primary",
                    "action_id": "confirm_order",
                    "value": order.session_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "🔄 See Alternatives"},
                    "action_id": "see_alternatives",
                    "value": order.session_id,
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "📒 This order will be logged to the team ledger on confirmation."}
            ],
        },
    ]


# ── Spend Report Message ───────────────────────────────────────────────────────

def spend_report(summary: SpendSummary) -> list[dict]:
    period_label = summary.period.capitalize()
    budget_pct   = int(summary.total_spend / summary.budget * 100) if summary.budget else 0
    status_emoji = "✅" if budget_pct <= 80 else "⚠️" if budget_pct <= 100 else "🔴"
    delivery_pct = int(summary.delivery_spend / summary.total_spend * 100) if summary.total_spend else 0

    per_member_text = (
        "\n".join(f"• {name}: ₹{amt:,}" for name, amt in summary.per_member.items())
        if summary.per_member else "_No data_"
    )

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📊 {period_label} Food Spend Report"},
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Total Spend*\n₹{summary.total_spend:,} / ₹{summary.budget:,} {status_emoji}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Budget Used*\n{budget_pct}%",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Delivery*\n₹{summary.delivery_spend:,} ({delivery_pct}%)",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Dine-out*\n₹{summary.dineout_spend:,} ({100 - delivery_pct}%)",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Sessions*\n{summary.session_count} lunches",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Top Restaurant*\n{summary.top_restaurant or 'N/A'}",
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Per person:*\n{per_member_text}"},
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"💡 *Insight*\n{summary.insight}" if summary.insight else "💡 _Run `/lunch insights` for AI-powered analysis_",
            },
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "Use `/lunch budget set <amount>` to update your monthly budget"}
            ],
        },
    ]