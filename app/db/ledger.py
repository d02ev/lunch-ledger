from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy import select, func
from app.db.database import OrderRecord, MemberSpend, TeamBudget, AsyncSessionLocal
from app.models import PlacedOrder, SpendSummary


class LedgerRepository:
    """All DB operations for LunchLedger's financial layer."""

    # ── Writes ─────────────────────────────────────────────────────────────────

    async def save_order(self, order: PlacedOrder) -> None:
        async with AsyncSessionLocal() as session:
            record = OrderRecord(
                session_id=order.session_id,
                channel_id=order.channel_id,
                restaurant_name=order.restaurant_name,
                restaurant_id=order.restaurant_id,
                mode=order.mode,
                total_amount=order.total_amount,
                agent_reasoning=order.agent_reasoning,
                order_ref=order.order_ref,
                placed_at=order.placed_at,
            )
            session.add(record)

            for member in order.per_member:
                spend = MemberSpend(
                    session_id=order.session_id,
                    channel_id=order.channel_id,
                    member_name=member.member_name,
                    amount=member.amount,
                    placed_at=order.placed_at,
                )
                session.add(spend)

            await session.commit()

    async def set_budget(self, channel_id: str, amount: int) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.get(TeamBudget, channel_id)
            if result:
                result.monthly_budget = amount
                result.updated_at = datetime.utcnow()
            else:
                session.add(TeamBudget(channel_id=channel_id, monthly_budget=amount))
            await session.commit()

    # ── Reads ──────────────────────────────────────────────────────────────────

    async def get_budget(self, channel_id: str) -> int:
        async with AsyncSessionLocal() as session:
            result = await session.get(TeamBudget, channel_id)
            return result.monthly_budget if result else 15000

    async def get_spend_summary(
        self, channel_id: str, period: str = "weekly"
    ) -> SpendSummary:
        days = 7 if period == "weekly" else 30
        since = datetime.utcnow() - timedelta(days=days)

        async with AsyncSessionLocal() as session:
            # Total spend + mode breakdown
            orders = (
                await session.execute(
                    select(OrderRecord).where(
                        OrderRecord.channel_id == channel_id,
                        OrderRecord.placed_at >= since,
                    )
                )
            ).scalars().all()

            total = sum(o.total_amount for o in orders)
            delivery_total = sum(o.total_amount for o in orders if o.mode == "delivery")
            dineout_total = sum(o.total_amount for o in orders if o.mode == "dine_out")

            # Top restaurant
            restaurant_freq: dict[str, int] = {}
            for o in orders:
                restaurant_freq[o.restaurant_name] = (
                    restaurant_freq.get(o.restaurant_name, 0) + 1
                )
            top_restaurant = (
                max(restaurant_freq, key=restaurant_freq.get)
                if restaurant_freq
                else None
            )

            # Per-member spend
            member_rows = (
                await session.execute(
                    select(MemberSpend.member_name, func.sum(MemberSpend.amount))
                    .where(
                        MemberSpend.channel_id == channel_id,
                        MemberSpend.placed_at >= since,
                    )
                    .group_by(MemberSpend.member_name)
                )
            ).all()
            per_member = {row[0]: row[1] for row in member_rows}

            budget = await self.get_budget(channel_id)

            return SpendSummary(
                period=period,
                total_spend=total,
                budget=budget,
                delivery_spend=delivery_total,
                dineout_spend=dineout_total,
                session_count=len(orders),
                top_restaurant=top_restaurant,
                per_member=per_member,
            )

    async def get_raw_orders(self, channel_id: str, days: int = 30) -> list[OrderRecord]:
        since = datetime.utcnow() - timedelta(days=days)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(OrderRecord).where(
                    OrderRecord.channel_id == channel_id,
                    OrderRecord.placed_at >= since,
                ).order_by(OrderRecord.placed_at.desc())
            )
            return result.scalars().all()


ledger = LedgerRepository()