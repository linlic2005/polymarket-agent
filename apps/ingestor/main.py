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


@router.post("/webhooks/opennews", response_model=MarketEventRead, summary="接收 OpenNews webhook")
async def receive_opennews_webhook(
    payload: dict[str, Any],
    session: AsyncSession = Depends(async_session_dependency),
) -> MarketEventRead:
    """处理来自 6551 OpenNews 的 webhook 推送。"""
    service = IngestorService(session)
    event = await service.ingest_opennews_webhook(payload)
    return MarketEventRead.model_validate(event)


@router.post("/fetch", summary="手动触发拉取事件")
async def trigger_fetch(
    session: AsyncSession = Depends(async_session_dependency),
) -> dict[str, Any]:
    """手动触发一次事件拉取。"""
    service = IngestorService(session)
    count = await service.fetch_and_ingest()
    return {"status": "ok", "ingested_count": count}


@router.get("/events", response_model=list[MarketEventRead], summary="列出已采集事件")
async def list_events(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(async_session_dependency),
) -> list[MarketEventRead]:
    """分页查询已采集的事件列表。"""
    service = IngestorService(session)
    events = await service.list_events(limit=limit, offset=offset)
    return [MarketEventRead.model_validate(e) for e in events]
