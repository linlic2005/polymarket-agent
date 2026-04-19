"""
Rules 模块路由。

负责信号规则的管理与评估。
"""

from __future__ import annotations

from typing import Any
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.rules.service import RulesService
from libs.storage.database import async_session_dependency

router = APIRouter(prefix="/api/v1/rules", tags=["Rules - 信号规则"])


@router.post("/evaluate/{event_id}", summary="评估事件是否触发信号")
async def evaluate_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(async_session_dependency),
) -> dict[str, Any]:
    """基于规则引擎评估事件是否满足交易信号条件。"""
    service = RulesService(session)
    result = await service.evaluate(event_id)
    return result


@router.get("/{candidate_id}", summary="获取并分析候选市场规则")
async def get_candidate_rules(
    candidate_id: uuid.UUID,
    session: AsyncSession = Depends(async_session_dependency),
) -> dict[str, Any]:
    """通过 CandidateMarket id 加载规则和盘口数据并解析。"""
    service = RulesService(session)
    result = await service.get_and_parse_rules(candidate_id)
    return result
