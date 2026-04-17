"""
Execution 模块对外 Endpoint 路由。
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.execution.service import ExecutionService
from libs.storage.database import async_session_dependency

router = APIRouter(prefix="/api/v1/orders", tags=["Execution - 订单执行"])

@router.post("/place/{candidate_id}", summary="下发/执行候选订单")
async def place_order(
    candidate_id: uuid.UUID,
    session: AsyncSession = Depends(async_session_dependency),
) -> dict[str, Any]:
    """触发前置查验并按状态机流转执行下单。"""
    service = ExecutionService(session)
    return await service.execute_candidate(candidate_id)

@router.post("/cancel/{order_id}", summary="撤销未成交的委托单")
async def cancel_order(
    order_id: uuid.UUID,
    exchange_order_id: str,
    session: AsyncSession = Depends(async_session_dependency),
) -> dict[str, Any]:
    """使用 Polymarket SDK 予以撤单。"""
    service = ExecutionService(session)
    success = await service.cancel_order_request(order_id, exchange_order_id)
    return {"success": success}

@router.get("/open", summary="获取所有的在途委托单")
async def get_open_orders(
    session: AsyncSession = Depends(async_session_dependency),
) -> list[dict[str, Any]]:
    """查询当前系统的 open orders。"""
    service = ExecutionService(session)
    return await service.fetch_open_orders()

@router.get("/positions", summary="获取现有所有持仓")
async def get_positions(
    session: AsyncSession = Depends(async_session_dependency),
) -> list[dict[str, Any]]:
    """获取所有实时在仓。"""
    service = ExecutionService(session)
    return await service.fetch_positions()
