"""
Ingestor 模块路由。

负责：
- 接收 OpenNews webhook 推送
- 提供手动拉取事件的 API
- 列出已接收的事件
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.ingestor.service import IngestorService
from apps.ingestor.routes import ingest_router
from libs.models.schemas import MarketEventCreate, MarketEventRead, IngestEventRead
from libs.storage.database import async_session_dependency

router = APIRouter(prefix="/api/v1/ingestor", tags=["Ingestor - 事件接入"])

# 注册新版 ingest 路由（POST /ingest/opennews/webhook, POST /ingest/opennews/pull）
router.include_router(ingest_router)


@router.get("/events", response_model=list[IngestEventRead], summary="列出已采集事件")
async def list_events(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(async_session_dependency),
) -> list[IngestEventRead]:
    """分页查询已采集的事件列表。"""
    service = IngestorService(session)
    events = await service.list_events(limit=limit, offset=offset)
    return [IngestEventRead.model_validate(e) for e in events]
