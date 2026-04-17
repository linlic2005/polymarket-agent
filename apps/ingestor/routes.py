"""
Ingestor 新 API 路由。

端点：
- POST /ingest/opennews/webhook  — 接收 OpenNews webhook 推送
- POST /ingest/opennews/pull     — 手动触发拉取事件
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.ingestor.service import DuplicateEventError, IngestorService
from libs.models.schemas import IngestEventRead, IngestPullResponse
from libs.storage.database import async_session_dependency

ingest_router = APIRouter(tags=["Ingestor - 事件接入"])


@ingest_router.post(
    "/ingest/opennews/webhook",
    response_model=IngestEventRead,
    status_code=status.HTTP_201_CREATED,
    summary="接收 OpenNews webhook 推送",
    responses={
        409: {"description": "事件已存在（去重命中）"},
        422: {"description": "Payload 格式错误"},
    },
)
async def opennews_webhook(
    payload: dict[str, Any],
    session: AsyncSession = Depends(async_session_dependency),
) -> IngestEventRead:
    """
    接收并处理来自 6551 OpenNews 的 webhook 推送事件。

    流程：校验 → 标准化 → 去重 → 落库
    """
    service = IngestorService(session)
    try:
        return await service.ingest_webhook(payload)
    except DuplicateEventError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@ingest_router.post(
    "/ingest/opennews/pull",
    response_model=IngestPullResponse,
    summary="手动触发拉取 OpenNews 事件",
)
async def opennews_pull(
    limit: int = 50,
    session: AsyncSession = Depends(async_session_dependency),
) -> IngestPullResponse:
    """
    手动触发一次 OpenNews 事件拉取。

    拉取最近的事件，自动去重后入库。
    """
    service = IngestorService(session)
    return await service.ingest_pull(limit=limit)
