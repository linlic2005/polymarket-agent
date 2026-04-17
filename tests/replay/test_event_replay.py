"""
Replay 模块回放与 CLI 测试。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.models.db_models import (
    CandidateOrder,
    IngestEvent,
    MarketResolution,
    MarketSnapshotHistory,
    ReplayCandidateResult,
    ReplayEquityPoint,
    ReplayRun,
    ReplayTradeResult,
    RiskHistory,
    SizingHistory,
    ThesisHistory,
)


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


async def _create_event(
    session: AsyncSession,
    *,
    published_at: datetime,
    headline: str,
) -> IngestEvent:
    event = IngestEvent(
        source="opennews_6551",
        source_event_id=str(uuid.uuid4()),
        published_at=published_at,
        received_at=published_at,
        event_type="news",
        entity_tags=["btc"],
        symbol_tags=["BTC"],
        headline=headline,
        summary=f"{headline} summary",
        dedupe_hash=uuid.uuid4().hex,
    )
    session.add(event)
    await session.flush()
    return event


async def _create_order(
    session: AsyncSession,
    *,
    event: IngestEvent,
    condition_id: str,
    side: str,
    outcome: str,
    target_price: float,
    size: float,
    created_at: datetime,
) -> CandidateOrder:
    order = CandidateOrder(
        market_event_id=event.event_id,
        polymarket_condition_id=condition_id,
        side=side,
        outcome=outcome,
        target_price=target_price,
        size=size,
        status="pending",
        dry_run=True,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(order)
    await session.flush()
    return order


async def _create_histories(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    edge_net: float,
    created_at: datetime,
    risk_allow: bool = True,
) -> None:
    session.add(
        ThesisHistory(
            candidate_id=candidate_id,
            direction="YES",
            p_market=0.45,
            q_raw=0.62,
            novelty_score=80.0,
            rule_clarity_score=90.0,
            pricing_dislocation_score=70.0,
            confidence=0.75,
            max_hold_minutes=1440,
            reasoning_summary="historical thesis",
            evidence=["e1"],
            created_at=created_at,
            updated_at=created_at,
        )
    )
    session.add(
        RiskHistory(
            candidate_id=candidate_id,
            allow=risk_allow,
            reason_codes=[] if risk_allow else ["blocked"],
            risk_metrics_json={"spread": 0.02},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    session.add(
        SizingHistory(
            candidate_id=candidate_id,
            p_market=0.45,
            q_raw=0.62,
            alpha=0.5,
            q_adj=0.535,
            taker_fee_per_share=0.01,
            expected_slippage_per_share=0.01,
            exit_cost_reserve=0.01,
            uncertainty_haircut=0.02,
            p_eff=0.49,
            edge_net=edge_net,
            f_full=0.1,
            f_half=0.05,
            f_final=0.05,
            sizing_reason_codes=[],
            created_at=created_at,
            updated_at=created_at,
        )
    )
    await session.flush()


async def _create_snapshot(
    session: AsyncSession,
    *,
    condition_id: str,
    outcome: str,
    snapshot_at: datetime,
    best_bid: float,
    best_ask: float,
    executable_size: float,
) -> None:
    session.add(
        MarketSnapshotHistory(
            condition_id=condition_id,
            outcome=outcome,
            snapshot_at=snapshot_at,
            best_bid=best_bid,
            best_ask=best_ask,
            executable_size=executable_size,
            spread=best_ask - best_bid,
            raw_payload={"best_bid": best_bid, "best_ask": best_ask},
        )
    )
    await session.flush()


async def _create_resolution(
    session: AsyncSession,
    *,
    condition_id: str,
    resolved_outcome: str,
    resolved_at: datetime,
) -> None:
    session.add(
        MarketResolution(
            condition_id=condition_id,
            resolved_outcome=resolved_outcome,
            resolved_at=resolved_at,
            payout_yes=1.0 if resolved_outcome == "YES" else 0.0,
            payout_no=1.0 if resolved_outcome == "NO" else 0.0,
        )
    )
    await session.flush()


@pytest.mark.replay
@pytest.mark.asyncio
async def test_replay_marks_missing_history_as_not_tradable(db_session: AsyncSession) -> None:
    from apps.replay.service import ReplayService

    event = await _create_event(
        db_session,
        published_at=_dt("2026-01-10T09:00:00"),
        headline="Missing history event",
    )
    await _create_order(
        db_session,
        event=event,
        condition_id="cond-missing",
        side="BUY",
        outcome="YES",
        target_price=0.60,
        size=10.0,
        created_at=_dt("2026-01-10T09:05:00"),
    )
    await db_session.commit()

    service = ReplayService(db_session)
    summary = await service.run(
        start=_dt("2026-01-01T00:00:00"),
        end=_dt("2026-01-31T23:59:59"),
        export_root=None,
    )

    assert summary.candidate_count == 1
    assert summary.tradable_count == 0
    assert summary.simulated_fill_count == 0

    result = (
        await db_session.execute(select(ReplayCandidateResult))
    ).scalar_one()
    assert result.is_tradable is False
    assert "missing_thesis_history" in result.not_tradable_reason


@pytest.mark.replay
@pytest.mark.asyncio
async def test_replay_executes_buy_and_sell_and_computes_metrics(
    db_session: AsyncSession,
) -> None:
    from apps.replay.service import ReplayService

    loss_event = await _create_event(
        db_session,
        published_at=_dt("2026-01-05T08:00:00"),
        headline="Sell side event",
    )
    loss_order = await _create_order(
        db_session,
        event=loss_event,
        condition_id="cond-sell",
        side="SELL",
        outcome="NO",
        target_price=0.60,
        size=5.0,
        created_at=_dt("2026-01-05T08:10:00"),
    )
    await _create_histories(
        db_session,
        candidate_id=loss_order.id,
        edge_net=0.10,
        created_at=_dt("2026-01-05T08:10:00"),
    )
    await _create_snapshot(
        db_session,
        condition_id="cond-sell",
        outcome="NO",
        snapshot_at=_dt("2026-01-05T08:11:00"),
        best_bid=0.62,
        best_ask=0.64,
        executable_size=5.0,
    )
    await _create_resolution(
        db_session,
        condition_id="cond-sell",
        resolved_outcome="NO",
        resolved_at=_dt("2026-01-06T08:11:00"),
    )

    win_event = await _create_event(
        db_session,
        published_at=_dt("2026-01-06T09:00:00"),
        headline="Buy side event",
    )
    win_order = await _create_order(
        db_session,
        event=win_event,
        condition_id="cond-buy",
        side="BUY",
        outcome="YES",
        target_price=0.60,
        size=10.0,
        created_at=_dt("2026-01-06T09:05:00"),
    )
    await _create_histories(
        db_session,
        candidate_id=win_order.id,
        edge_net=0.20,
        created_at=_dt("2026-01-06T09:05:00"),
    )
    await _create_snapshot(
        db_session,
        condition_id="cond-buy",
        outcome="YES",
        snapshot_at=_dt("2026-01-06T09:06:00"),
        best_bid=0.54,
        best_ask=0.55,
        executable_size=10.0,
    )
    await _create_resolution(
        db_session,
        condition_id="cond-buy",
        resolved_outcome="YES",
        resolved_at=_dt("2026-01-07T09:06:00"),
    )
    await db_session.commit()

    service = ReplayService(db_session)
    summary = await service.run(
        start=_dt("2026-01-01T00:00:00"),
        end=_dt("2026-01-31T23:59:59"),
        export_root=None,
    )

    assert summary.candidate_count == 2
    assert summary.tradable_count == 2
    assert summary.simulated_fill_count == 2
    assert summary.avg_net_edge == pytest.approx(0.15)
    assert summary.win_rate == pytest.approx(0.5)
    assert summary.cumulative_pnl == pytest.approx(2.6)
    assert summary.max_drawdown == pytest.approx(1.9)

    trade_rows = (
        await db_session.execute(
            select(ReplayTradeResult).order_by(ReplayTradeResult.fill_at.asc())
        )
    ).scalars().all()
    assert len(trade_rows) == 2
    assert trade_rows[0].fill_price == pytest.approx(0.62)
    assert trade_rows[1].fill_price == pytest.approx(0.55)

    equity_points = (
        await db_session.execute(
            select(ReplayEquityPoint).order_by(ReplayEquityPoint.timestamp.asc())
        )
    ).scalars().all()
    assert [point.cumulative_pnl for point in equity_points] == [
        pytest.approx(-1.9),
        pytest.approx(2.6),
    ]


@pytest.mark.replay
@pytest.mark.asyncio
async def test_replay_cli_exports_artifacts_and_persists_run(
    db_session: AsyncSession,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from apps.replay.main import run_cli

    event = await _create_event(
        db_session,
        published_at=_dt("2026-01-15T12:00:00"),
        headline="CLI replay event",
    )
    order = await _create_order(
        db_session,
        event=event,
        condition_id="cond-cli",
        side="BUY",
        outcome="YES",
        target_price=0.50,
        size=4.0,
        created_at=_dt("2026-01-15T12:05:00"),
    )
    await _create_histories(
        db_session,
        candidate_id=order.id,
        edge_net=0.12,
        created_at=_dt("2026-01-15T12:05:00"),
    )
    await _create_snapshot(
        db_session,
        condition_id="cond-cli",
        outcome="YES",
        snapshot_at=_dt("2026-01-15T12:06:00"),
        best_bid=0.48,
        best_ask=0.49,
        executable_size=10.0,
    )
    await _create_resolution(
        db_session,
        condition_id="cond-cli",
        resolved_outcome="YES",
        resolved_at=_dt("2026-01-16T12:06:00"),
    )
    await db_session.commit()

    @asynccontextmanager
    async def session_factory():
        yield db_session

    summary = await run_cli(
        start=_dt("2026-01-01T00:00:00"),
        end=_dt("2026-01-31T23:59:59"),
        session_factory=session_factory,
        export_root=tmp_path,
    )

    assert summary.candidate_count == 1

    run = (await db_session.execute(select(ReplayRun))).scalar_one()
    export_dir = Path(run.export_dir)
    assert export_dir.exists()
    assert (export_dir / "summary.csv").exists()
    assert (export_dir / "summary.json").exists()
    assert (export_dir / "candidate_results.csv").exists()
    assert (export_dir / "candidate_results.json").exists()
    assert (export_dir / "trade_results.csv").exists()
    assert (export_dir / "trade_results.json").exists()
    assert (export_dir / "equity_curve.csv").exists()
    assert (export_dir / "manifest.json").exists()

    stdout = capsys.readouterr().out
    assert stdout == ""


@pytest.mark.replay
@pytest.mark.asyncio
async def test_replay_ignores_history_written_after_order_time(
    db_session: AsyncSession,
) -> None:
    from apps.replay.service import ReplayService

    event = await _create_event(
        db_session,
        published_at=_dt("2026-01-20T10:00:00"),
        headline="Future history event",
    )
    order = await _create_order(
        db_session,
        event=event,
        condition_id="cond-future-history",
        side="BUY",
        outcome="YES",
        target_price=0.50,
        size=3.0,
        created_at=_dt("2026-01-20T10:05:00"),
    )
    await _create_histories(
        db_session,
        candidate_id=order.id,
        edge_net=0.10,
        created_at=_dt("2026-01-20T10:04:00"),
    )
    await _create_histories(
        db_session,
        candidate_id=order.id,
        edge_net=0.35,
        created_at=_dt("2026-01-20T10:10:00"),
    )
    await _create_snapshot(
        db_session,
        condition_id="cond-future-history",
        outcome="YES",
        snapshot_at=_dt("2026-01-20T10:05:30"),
        best_bid=0.47,
        best_ask=0.48,
        executable_size=10.0,
    )
    await _create_resolution(
        db_session,
        condition_id="cond-future-history",
        resolved_outcome="YES",
        resolved_at=_dt("2026-01-21T10:05:30"),
    )
    await db_session.commit()

    service = ReplayService(db_session)
    summary = await service.run(
        start=_dt("2026-01-01T00:00:00"),
        end=_dt("2026-01-31T23:59:59"),
        export_root=None,
    )

    assert summary.tradable_count == 1
    assert summary.avg_net_edge == pytest.approx(0.10)


@pytest.mark.replay
@pytest.mark.asyncio
async def test_replay_rejects_snapshots_after_market_resolution(
    db_session: AsyncSession,
) -> None:
    from apps.replay.service import ReplayService

    event = await _create_event(
        db_session,
        published_at=_dt("2026-01-22T08:00:00"),
        headline="Post resolution snapshot event",
    )
    order = await _create_order(
        db_session,
        event=event,
        condition_id="cond-post-resolution",
        side="BUY",
        outcome="YES",
        target_price=0.60,
        size=5.0,
        created_at=_dt("2026-01-22T08:05:00"),
    )
    await _create_histories(
        db_session,
        candidate_id=order.id,
        edge_net=0.15,
        created_at=_dt("2026-01-22T08:04:00"),
    )
    await _create_resolution(
        db_session,
        condition_id="cond-post-resolution",
        resolved_outcome="YES",
        resolved_at=_dt("2026-01-22T08:06:00"),
    )
    await _create_snapshot(
        db_session,
        condition_id="cond-post-resolution",
        outcome="YES",
        snapshot_at=_dt("2026-01-22T08:07:00"),
        best_bid=0.58,
        best_ask=0.59,
        executable_size=10.0,
    )
    await db_session.commit()

    service = ReplayService(db_session)
    summary = await service.run(
        start=_dt("2026-01-01T00:00:00"),
        end=_dt("2026-01-31T23:59:59"),
        export_root=None,
    )

    assert summary.tradable_count == 0
    candidate = (
        await db_session.execute(
            select(ReplayCandidateResult).where(
                ReplayCandidateResult.candidate_order_id == order.id
            )
        )
    ).scalar_one()
    assert candidate.not_tradable_reason is not None
    assert "missing_entry_snapshot" in candidate.not_tradable_reason
