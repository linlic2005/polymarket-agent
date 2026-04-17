"""
Sizing 模块路由。

负责候选单的仓位计算。
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.sizing.service import SizingService
from libs.models.schemas import SizingDecision
from libs.storage.database import async_session_dependency

router = APIRouter(prefix="/api/v1/sizing", tags=["Sizing - 仓位计算"])

class SizingPayload(BaseModel):
    p_market: float
    q_raw: float
    bankroll_usd: float | None = None

@router.post("/calculate/{candidate_id}", response_model=SizingDecision, summary="计算建议仓位")
async def calculate_size(
    candidate_id: uuid.UUID,
    payload: SizingPayload,
    session: AsyncSession = Depends(async_session_dependency),
) -> SizingDecision:
    """
    基于胜率、边际和资金量计算建议仓位（使用净边际半凯利）。
    """
    service = SizingService(session)
    return service.calculate(
        candidate_id=candidate_id,
        p_market=payload.p_market,
        q_raw=payload.q_raw,
        bankroll_override=payload.bankroll_usd
    )
