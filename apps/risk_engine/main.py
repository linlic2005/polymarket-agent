"""
Risk Engine 模块路由。

负责候选单的风控审核。
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from apps.risk_engine.service import RiskEngineService
from libs.models.schemas import RiskDecision
from libs.storage.database import async_session_dependency

router = APIRouter(prefix="/api/v1/risk", tags=["Risk Engine - 风控"])

class RiskCheckPayload(BaseModel):
    market_name: str = "polymarket"
    current_market_risk_usd: float = 0.0
    current_theme_risk_usd: float = 0.0
    daily_new_risk_usd: float = 0.0
    daily_loss_usd: float = 0.0
    orderbook_depth_usd: float = 500.0
    spread_pct: float = 0.05
    estimated_slippage_pct: float = 0.01
    expected_hold_minutes: int = 1440
    hours_to_expiry: float = 48.0
    order_risk_usd: float = 100.0

@router.post("/check/{candidate_id}", response_model=RiskDecision, summary="风控检查候选单")
async def risk_check(
    candidate_id: uuid.UUID,
    payload: RiskCheckPayload,
    session: AsyncSession = Depends(async_session_dependency),
) -> RiskDecision:
    """对候选单进行风控审核（基于结构化特征输入）。"""
    service = RiskEngineService(session)
    return await service.check(candidate_id, payload.model_dump())

@router.get("/limits", summary="查看当前风控限额")
async def get_limits() -> dict[str, Any]:
    """返回当前生效的风控限额配置。"""
    from libs.utils.yaml_loader import load_risk_limits
    return load_risk_limits()
