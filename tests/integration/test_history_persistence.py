"""
历史 thesis/risk/sizing 结果落库测试。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.risk_engine.service import RiskEngineService
from apps.sizing.service import SizingService
from apps.thesis.service import ThesisService
from libs.models.db_models import RiskHistory, SizingHistory, ThesisHistory


@pytest.mark.integration
@pytest.mark.asyncio
async def test_services_append_history_records(db_session: AsyncSession) -> None:
    candidate_id = uuid.uuid4()

    thesis_service = ThesisService(db_session)
    thesis = await thesis_service.generate(candidate_id)
    assert thesis.candidate_id == candidate_id

    risk_service = RiskEngineService(db_session)
    risk = await risk_service.check(
        candidate_id,
        {
            "market_name": "polymarket",
            "current_market_risk_usd": 0.0,
            "current_theme_risk_usd": 0.0,
            "daily_new_risk_usd": 0.0,
            "daily_loss_usd": 0.0,
            "orderbook_depth_usd": 1_000.0,
            "spread_pct": 0.01,
            "estimated_slippage_pct": 0.01,
            "expected_hold_minutes": 60,
            "hours_to_expiry": 48.0,
            "order_risk_usd": 50.0,
        },
    )
    assert risk.allow is True

    sizing_service = SizingService(db_session)
    sizing = sizing_service.calculate(
        candidate_id=candidate_id,
        p_market=0.45,
        q_raw=0.60,
        bankroll_override=10_000.0,
    )
    assert sizing.candidate_id == candidate_id

    thesis_rows = (
        await db_session.execute(select(ThesisHistory).where(ThesisHistory.candidate_id == candidate_id))
    ).scalars().all()
    risk_rows = (
        await db_session.execute(select(RiskHistory).where(RiskHistory.candidate_id == candidate_id))
    ).scalars().all()
    sizing_rows = (
        await db_session.execute(select(SizingHistory).where(SizingHistory.candidate_id == candidate_id))
    ).scalars().all()

    assert len(thesis_rows) == 1
    assert len(risk_rows) == 1
    assert len(sizing_rows) == 1
    assert thesis_rows[0].reasoning_summary == thesis.reasoning_summary
    assert risk_rows[0].allow is True
    assert sizing_rows[0].edge_net == sizing.edge_net
