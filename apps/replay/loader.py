"""
Replay 数据加载器。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.models.db_models import (
    CandidateOrder,
    IngestEvent,
    MarketResolution,
    MarketSnapshotHistory,
    RiskHistory,
    SizingHistory,
    ThesisHistory,
)


@dataclass(slots=True)
class ReplayInput:
    event: IngestEvent
    order: CandidateOrder
    thesis: ThesisHistory | None
    risk: RiskHistory | None
    sizing: SizingHistory | None
    snapshot: MarketSnapshotHistory | None
    resolution: MarketResolution | None


async def _latest_by_candidate(
    session: AsyncSession,
    model: type[ThesisHistory] | type[RiskHistory] | type[SizingHistory],
    candidate_id,
    as_of: datetime,
):
    stmt = (
        select(model)
        .where(model.candidate_id == candidate_id)
        .where(model.created_at <= as_of)
        .order_by(model.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def load_replay_inputs(
    session: AsyncSession,
    *,
    start: datetime,
    end: datetime,
) -> list[ReplayInput]:
    stmt = (
        select(CandidateOrder, IngestEvent)
        .join(IngestEvent, CandidateOrder.market_event_id == IngestEvent.event_id)
        .where(IngestEvent.published_at.is_not(None))
        .where(IngestEvent.published_at >= start)
        .where(IngestEvent.published_at <= end)
        .order_by(IngestEvent.published_at.asc(), CandidateOrder.created_at.asc())
    )
    rows = (await session.execute(stmt)).all()
    replay_inputs: list[ReplayInput] = []

    for order, event in rows:
        thesis = await _latest_by_candidate(session, ThesisHistory, order.id, order.created_at)
        risk = await _latest_by_candidate(session, RiskHistory, order.id, order.created_at)
        sizing = await _latest_by_candidate(session, SizingHistory, order.id, order.created_at)

        snapshot = None
        resolution = None
        if order.polymarket_condition_id:
            resolution_stmt = (
                select(MarketResolution)
                .where(MarketResolution.condition_id == order.polymarket_condition_id)
                .limit(1)
            )
            resolution = (await session.execute(resolution_stmt)).scalar_one_or_none()

            snapshot_stmt = (
                select(MarketSnapshotHistory)
                .where(MarketSnapshotHistory.condition_id == order.polymarket_condition_id)
                .where(MarketSnapshotHistory.outcome == order.outcome)
                .where(MarketSnapshotHistory.snapshot_at >= order.created_at)
                .order_by(MarketSnapshotHistory.snapshot_at.asc())
            )
            if resolution is not None:
                snapshot_stmt = snapshot_stmt.where(
                    MarketSnapshotHistory.snapshot_at < resolution.resolved_at
                )

            snapshot_stmt = (
                snapshot_stmt
                .order_by(MarketSnapshotHistory.snapshot_at.asc())
                .limit(1)
            )
            snapshot = (await session.execute(snapshot_stmt)).scalar_one_or_none()

        replay_inputs.append(
            ReplayInput(
                event=event,
                order=order,
                thesis=thesis,
                risk=risk,
                sizing=sizing,
                snapshot=snapshot,
                resolution=resolution,
            )
        )

    return replay_inputs
