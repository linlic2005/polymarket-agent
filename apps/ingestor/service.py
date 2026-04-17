"""
Ingestor 编排服务。

职责：
1. 接收来自各入口（webhook / pull）的事件
2. 调用 normalizer 标准化
3. 基于 dedupe_hash 去重
4. 持久化到 ingest_events 表
5. 预留下游 mapper 触发点
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.ingestor.normalizer import normalize_opennews
from apps.ingestor.opennews_client import OpenNewsBusinessClient
from libs.models.db_models import IngestEvent
from libs.models.schemas import (
    IngestEventCreate,
    IngestEventRead,
    IngestPullResponse,
    MarketEventCreate,
)

logger = logging.getLogger(__name__)


class IngestorService:
    """事件接入编排服务。"""

    def __init__(
        self,
        session: AsyncSession,
        opennews_client: OpenNewsBusinessClient | None = None,
    ) -> None:
        """
        Args:
            session: 异步数据库会话
            opennews_client: OpenNews 业务客户端（可注入 mock）
        """
        self._session = session
        self._opennews = opennews_client or OpenNewsBusinessClient()

    # ------------------------------------------------------------------ #
    # 公开接口
    # ------------------------------------------------------------------ #

    async def ingest_webhook(self, payload: dict[str, Any]) -> IngestEventRead:
        """
        处理单条 webhook 推送事件。

        流程：validate → normalize → dedupe → save

        Args:
            payload: 原始 webhook JSON

        Returns:
            持久化后的事件读模型

        Raises:
            ValueError: payload 校验或标准化失败
            DuplicateEventError: 事件已存在（去重命中）
        """
        # 1. 校验
        self._opennews.validate_webhook_payload(payload)

        # 2. 标准化
        dto = normalize_opennews(payload)

        # 3. 去重检查
        if await self._is_duplicate(dto.dedupe_hash):
            raise DuplicateEventError(
                f"事件已存在: dedupe_hash={dto.dedupe_hash}"
            )

        # 4. 落库
        event = await self._save_event(dto)
        logger.info(
            "Webhook 事件已入库: event_id=%s source_event_id=%s",
            event.event_id,
            event.source_event_id,
        )
        return IngestEventRead.model_validate(event)

    async def ingest_pull(self, limit: int = 50) -> IngestPullResponse:
        """
        批量拉取并入库事件。

        流程：pull → normalize each → dedupe → save new

        Args:
            limit: 最大拉取数量

        Returns:
            拉取结果统计
        """
        raw_events = await self._opennews.pull_recent(limit=limit)
        total_fetched = len(raw_events)
        new_count = 0
        dup_count = 0

        for raw in raw_events:
            try:
                dto = normalize_opennews(raw)
            except (ValueError, KeyError) as exc:
                logger.warning("标准化失败，跳过事件: %s", exc)
                continue

            if await self._is_duplicate(dto.dedupe_hash):
                dup_count += 1
                continue

            await self._save_event(dto)
            new_count += 1

        logger.info(
            "Pull 完成: total=%d new=%d dup=%d",
            total_fetched,
            new_count,
            dup_count,
        )
        return IngestPullResponse(
            total_fetched=total_fetched,
            new_ingested=new_count,
            duplicates_skipped=dup_count,
        )

    async def list_events(
        self, *, limit: int = 50, offset: int = 0
    ) -> Sequence[IngestEvent]:
        """分页查询已采集事件。"""
        stmt = (
            select(IngestEvent)
            .order_by(IngestEvent.received_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ------------------------------------------------------------------ #
    # 内部方法
    # ------------------------------------------------------------------ #

    async def _save_event(self, dto: IngestEventCreate | MarketEventCreate) -> IngestEvent:
        """将 DTO 转为 ORM 对象并持久化。"""
        source_event_id = getattr(dto, "source_event_id", getattr(dto, "external_id", ""))
        headline = getattr(dto, "headline", getattr(dto, "title", ""))
        summary = getattr(dto, "summary", getattr(dto, "body", None))
        dedupe_hash = getattr(dto, "dedupe_hash", None) or hashlib.sha256(
            f"{dto.source}|{source_event_id}|{headline}".encode("utf-8")
        ).hexdigest()
        event = IngestEvent(
            source=dto.source,
            source_event_id=source_event_id,
            published_at=getattr(dto, "published_at", None),
            event_type=getattr(dto, "event_type", "legacy"),
            entity_tags=getattr(dto, "entity_tags", []),
            symbol_tags=getattr(dto, "symbol_tags", []),
            headline=headline,
            summary=summary,
            ai_score=getattr(dto, "ai_score", None),
            signal_hint=getattr(dto, "signal_hint", None),
            raw_payload=dto.raw_payload,
            dedupe_hash=dedupe_hash,
        )
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def _is_duplicate(self, dedupe_hash_or_source: str, source_event_id: str | None = None) -> bool:
        """基于 dedupe_hash 或旧版 source/external_id 组合检查事件是否已存在。"""
        if source_event_id is None:
            stmt = select(IngestEvent).where(IngestEvent.dedupe_hash == dedupe_hash_or_source)
        else:
            stmt = (
                select(IngestEvent)
                .where(IngestEvent.source == dedupe_hash_or_source)
                .where(IngestEvent.source_event_id == source_event_id)
            )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None


class DuplicateEventError(Exception):
    """事件去重命中时抛出的异常。"""
    pass
