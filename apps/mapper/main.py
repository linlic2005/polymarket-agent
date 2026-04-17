"""
Mapper 模块路由。

负责将已采集的事件映射到 Polymarket 条件市场。
"""

from __future__ import annotations

from typing import Any
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.mapper.service import MapperService
from libs.storage.database import async_session_dependency

router = APIRouter(prefix="/api/v1/mapper", tags=["Mapper - 事件映射"])


@router.post("/signals/map/{event_id}", summary="映射事件到 Polymarket 市场")
async def map_event(
    event_id: uuid.UUID,
    session: AsyncSession = Depends(async_session_dependency),
) -> dict[str, Any]:
    """将指定事件映射到可能的 Polymarket 条件市场。"""
    service = MapperService(session)
    result = await service.map_event_to_markets(event_id)
    return result


@router.get("/mappings", summary="列出所有映射关系")
async def list_mappings(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(async_session_dependency),
) -> dict[str, Any]:
    """查询已完成的事件-市场映射列表。"""
    service = MapperService(session)
    return await service.list_mappings(limit=limit, offset=offset)
