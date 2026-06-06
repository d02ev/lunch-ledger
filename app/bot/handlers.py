from __future__ import annotations
import os
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from app.core import session_manager, aggregate, format_for_agent
from app.agent import run_lunch_agent, generate_insight
from app.db import ledger
from app.models import MemberPreference
from app.bot import blocks

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

app = AsyncApp(token=SLACK_BOT_TOKEN)
handler = AsyncSlackRequestHandler(app)


# ── /lunch start ───────────────────────────────────────────────────────────────

@app.command("/lunch")
async def handle_lunch_command(ack, command, client, say):
    await ack()
    subcommand = (command.get("text") or "").strip().lower().split()[0] \
        if command.get("text") else "start"

    channel_id = command["channel_id"]
    user_id    = command["user_id"]
    args       = (command.get("text") or "").strip().split()

    if subcommand == "start":
        existing = session_manager.get_active_for_channel(channel_id)
        if existing:
            await say(f"⚠️ A session is already open (`{existing.session_id}`). "
                      f"Use `/lunch go` to process it or `/lunch cancel` to end it.")
            return

        session = session_manager.create(channel_id=channel_id, created_by=user_id)
        msg = await client.chat_postMessage(
            channel=channel_id,
            blocks=blocks.session_open(session),
            text=f"🍽️ Lunch session `{session.session_id}` is open!",
        )
        # Store message_ts so we can update it later
        session.message_ts = msg["ts"]

    elif subcommand == "go":
        await _process_session(channel_id, client, say)

    elif subcommand == "status":
        session = session_manager.get_active_for_channel(channel_id)
        if not session:
            await say("No active lunch session. Start one with `/lunch start`.")
            return
        joined = session_manager.members_joined(session.session_id)
        mins   = session_manager.time_remaining(session.session_id)
        names  = ", ".join(joined) if joined else "no one yet"
        await say(
            f"🕐 Session `{session.session_id}` | "
            f"{len(joined)} joined: {names} | {mins} min remaining"
        )

    elif subcommand == "cancel":
        session = session_manager.get_active_for_channel(channel_id)
        if session:
            session_manager.cancel(session.session_id)
            await say(f"❌ Session `{session.session_id}` cancelled.")
        else:
            await say("No active session to cancel.")

    elif subcommand == "report":
        period = args[1] if len(args) > 1 else "weekly"
        if period not in ("weekly", "monthly"):
            period = "weekly"
        summary = await ledger.get_spend_summary(channel_id, period)
        insight = await generate_insight(summary)
        summary.insight = insight
        await client.chat_postMessage(
            channel=channel_id,
            blocks=blocks.spend_report(summary),
            text=f"📊 {period.capitalize()} spend report",
        )

    elif subcommand == "budget":
        # /lunch budget set 15000
        if len(args) >= 3 and args[1] == "set":
            try:
                amount = int(args[2])
                await ledger.set_budget(channel_id, amount)
                await say(f"✅ Monthly budget set to ₹{amount:,}")
            except ValueError:
                await say("Usage: `/lunch budget set <amount>` e.g. `/lunch budget set 15000`")
        else:
            current = await ledger.get_budget(channel_id)
            await say(f"Current monthly budget: ₹{current:,}. "
                      f"Change with `/lunch budget set <amount>`")

    elif subcommand == "insights":
        summary = await ledger.get_spend_summary(channel_id, "monthly")
        insight = await generate_insight(summary)
        await say(f"💡 *Spend Insight*\n{insight}")

    else:
        await say(blocks.HELP_TEXT)


# ── Join button → open preferences modal ──────────────────────────────────────

@app.action("join_session")
async def handle_join(ack, body, client):
    await ack()
    session_id = body["actions"][0]["value"]
    await client.views_open(
        trigger_id=body["trigger_id"],
        view=blocks.preference_modal(session_id),
    )


# ── Preference modal submission ────────────────────────────────────────────────

@app.view("submit_preferences")
async def handle_preference_submission(ack, body, client):
    await ack()
    user   = body["user"]
    values = body["view"]["state"]["values"]
    meta   = body["view"]["private_metadata"]  # session_id

    dietary  = values["dietary_block"]["dietary_select"]["selected_options"]
    cuisine  = values["cuisine_block"]["cuisine_select"]["selected_options"]
    budget   = values["budget_block"]["budget_input"]["value"]
    mode     = values["mode_block"]["mode_select"]["selected_option"]["value"]

    pref = MemberPreference(
        member_id=user["id"],
        member_name=user["name"],
        dietary=[o["value"] for o in dietary],
        cuisine=[o["value"] for o in cuisine],
        budget=int(budget) if budget and budget.isdigit() else 400,
        mode=mode,
    )

    success = session_manager.add_preference(meta, pref)
    if not success:
        return  # session expired or closed

    # Update the session message to reflect new join count
    session = session_manager.get(meta)
    if session and session.message_ts:
        await client.chat_update(
            channel=session.channel_id,
            ts=session.message_ts,
            blocks=blocks.session_open(session),
            text=f"🍽️ Lunch session `{session.session_id}` — {len(session.preferences)} joined",
        )

    await client.chat_postEphemeral(
        channel=session.channel_id,
        user=user["id"],
        text=f"✅ Got your preferences! Waiting for others or use `/lunch go` to proceed.",
    )


# ── Confirm & Order button ─────────────────────────────────────────────────────

@app.action("confirm_order")
async def handle_confirm_order(ack, body, client, say):
    await ack()
    # In production: trigger actual place_food_order / book_table call here
    # For demo safety, we log and confirm
    session_id = body["actions"][0]["value"]
    session    = session_manager.get(session_id)
    if session:
        session_manager.mark_completed(session_id)
    await say("✅ Order confirmed! Your food is on its way. 🛵")


@app.action("see_alternatives")
async def handle_see_alternatives(ack, body, say):
    await ack()
    await say("🔄 Re-running agent for alternatives... _(coming in v2)_")


# ── Internal: process session ─────────────────────────────────────────────────

async def _process_session(channel_id: str, client, say) -> None:
    session = session_manager.get_active_for_channel(channel_id)

    if not session:
        await say("No active session. Start one with `/lunch start`.")
        return
    if not session.preferences:
        await say("⚠️ No one has joined yet! Share the session and wait for preferences.")
        return

    session_manager.mark_processing(session.session_id)
    await say("🤖 Analyzing preferences and finding the best option...")

    agg = aggregate(session.preferences)
    members = session_manager.members_joined(session.session_id)

    order = await run_lunch_agent(
        agg=agg,
        session_id=session.session_id,
        channel_id=channel_id,
        team_members=members,
    )

    # Persist to ledger
    await ledger.save_order(order)

    await client.chat_postMessage(
        channel=channel_id,
        blocks=blocks.order_result(order, agg),
        text=f"🍽️ Picked: {order.restaurant_name}",
    )