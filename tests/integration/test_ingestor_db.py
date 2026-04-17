"""
集成测试 - Ingestor + 数据库。
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from apps.ingestor.service import IngestorService
from libs.models.schemas import MarketEventCreate


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ingest_and_deduplicate(db_session: AsyncSession) -> None:
    """测试事件入库和去重逻辑。"""
    service = IngestorService(db_session)

    dto = MarketEventCreate(
        source="test_source",
        external_id="evt_001",
        title="Test Election Event",
        body="Some body text",
        category="politics",
    )

    # 第一次入库
    event = await service._save_event(dto)
    assert event.event_id is not None
    assert event.source == "test_source"

    # 去重检查
    is_dup = await service._is_duplicate("test_source", "evt_001")
    assert is_dup is True

    # 不同 external_id 不应重复
    is_dup2 = await service._is_duplicate("test_source", "evt_002")
    assert is_dup2 is False
