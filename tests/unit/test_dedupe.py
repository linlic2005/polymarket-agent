"""
去重逻辑 (dedupe) 的单元测试。

覆盖：
- IngestorService._is_duplicate 逻辑
- 重复事件被跳过（webhook）
- 重复事件在批量拉取中被统计
- 新事件成功入库

所有外部调用（数据库、OpenNews API）均通过 mock 替代，不连接真实服务。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from apps.ingestor.normalizer import SOURCE_OPENNEWS, compute_dedupe_hash
from apps.ingestor.service import DuplicateEventError, IngestorService


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

def _make_webhook_payload(
    event_id: str = "evt_100",
    title: str = "Test Event",
    **kwargs: Any,
) -> dict[str, Any]:
    """构造一个有效的 webhook payload。"""
    base = {
        "id": event_id,
        "title": title,
        "body": "Test body",
        "category": "politics",
        "published_at": "2024-06-01T12:00:00Z",
        "tags": ["Tag1"],
        "symbols": ["BTC"],
        "ai_score": 0.7,
        "signal": "bullish",
    }
    base.update(kwargs)
    return base


def _make_mock_session(existing_hashes: set[str] | None = None) -> AsyncMock:
    """
    创建一个 mock AsyncSession。

    Args:
        existing_hashes: 已存在的 dedupe_hash 集合，
                         用于模拟 _is_duplicate 查询结果。
    """
    existing = existing_hashes or set()
    session = AsyncMock()

    # mock session.execute() 返回的 result
    def mock_execute(stmt):
        """根据查询中的 dedupe_hash 判断是否存在。"""
        result = AsyncMock()
        # 从 stmt 中提取 dedupe_hash（简化：检查 existing set）
        # 由于 SQLAlchemy statement 不好直接解析，我们通过 side_effect 配合控制
        result.scalar_one_or_none = MagicMock(return_value=None)
        return result

    session.execute = AsyncMock(side_effect=mock_execute)
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()

    return session


def _make_mock_opennews_client(
    pull_events: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """创建一个 mock OpenNewsBusinessClient。"""
    client = MagicMock()
    client.pull_recent = AsyncMock(return_value=pull_events or [])
    client.validate_webhook_payload = MagicMock(side_effect=lambda p: p)
    client.close = AsyncMock()
    return client


# ------------------------------------------------------------------ #
# _is_duplicate 测试
# ------------------------------------------------------------------ #

class TestIsDuplicate:
    """测试 IngestorService._is_duplicate 内部方法。"""

    @pytest.mark.asyncio
    async def test_not_duplicate(self) -> None:
        """dedupe_hash 不存在时应返回 False。"""
        session = AsyncMock()
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none = MagicMock(return_value=None)
        session.execute = AsyncMock(return_value=result_mock)

        service = IngestorService(session=session)
        assert await service._is_duplicate("nonexistent_hash") is False

    @pytest.mark.asyncio
    async def test_is_duplicate(self) -> None:
        """dedupe_hash 已存在时应返回 True。"""
        session = AsyncMock()
        result_mock = AsyncMock()
        # 模拟返回一个已存在的 IngestEvent 对象
        result_mock.scalar_one_or_none = MagicMock(return_value=MagicMock())
        session.execute = AsyncMock(return_value=result_mock)

        service = IngestorService(session=session)
        assert await service._is_duplicate("existing_hash") is True


# ------------------------------------------------------------------ #
# Webhook 去重测试
# ------------------------------------------------------------------ #

class TestWebhookDedupe:
    """测试 webhook 入口的去重行为。"""

    @pytest.mark.asyncio
    async def test_new_event_saved(self) -> None:
        """新事件应成功入库。"""
        session = _make_mock_session()

        # mock _is_duplicate 返回 False（新事件）
        # mock refresh 设置 event_id 等属性
        def mock_refresh(obj):
            import uuid
            obj.event_id = uuid.uuid4()
            obj.received_at = datetime.now(timezone.utc)
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        session.refresh = AsyncMock(side_effect=mock_refresh)

        client = _make_mock_opennews_client()
        service = IngestorService(session=session, opennews_client=client)

        payload = _make_webhook_payload()
        result = await service.ingest_webhook(payload)

        # 验证 session.add 被调用
        session.add.assert_called_once()
        assert result.source == SOURCE_OPENNEWS
        assert result.headline == "Test Event"

    @pytest.mark.asyncio
    async def test_duplicate_event_raises(self) -> None:
        """重复事件应抛出 DuplicateEventError。"""
        session = AsyncMock()
        result_mock = AsyncMock()
        # 模拟 _is_duplicate 返回 True
        result_mock.scalar_one_or_none = MagicMock(return_value=MagicMock())
        session.execute = AsyncMock(return_value=result_mock)

        client = _make_mock_opennews_client()
        service = IngestorService(session=session, opennews_client=client)

        payload = _make_webhook_payload()
        with pytest.raises(DuplicateEventError, match="事件已存在"):
            await service.ingest_webhook(payload)

        # 验证 session.add 未被调用
        session.add.assert_not_called()


# ------------------------------------------------------------------ #
# Pull 批量去重测试
# ------------------------------------------------------------------ #

class TestPullDedupe:
    """测试批量拉取的去重统计。"""

    @pytest.mark.asyncio
    async def test_all_new(self) -> None:
        """所有事件都是新的场景。"""
        events = [
            _make_webhook_payload(event_id=f"evt_{i}", title=f"Event {i}")
            for i in range(3)
        ]

        session = _make_mock_session()

        def mock_refresh(obj):
            import uuid
            obj.event_id = uuid.uuid4()
            obj.received_at = datetime.now(timezone.utc)
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        session.refresh = AsyncMock(side_effect=mock_refresh)

        client = _make_mock_opennews_client(pull_events=events)
        service = IngestorService(session=session, opennews_client=client)
        result = await service.ingest_pull()

        assert result.total_fetched == 3
        assert result.new_ingested == 3
        assert result.duplicates_skipped == 0

    @pytest.mark.asyncio
    async def test_all_duplicates(self) -> None:
        """所有事件都是重复的场景。"""
        events = [
            _make_webhook_payload(event_id=f"evt_{i}", title=f"Event {i}")
            for i in range(2)
        ]

        session = AsyncMock()
        result_mock = AsyncMock()
        # 所有事件都已存在
        result_mock.scalar_one_or_none = MagicMock(return_value=MagicMock())
        session.execute = AsyncMock(return_value=result_mock)

        client = _make_mock_opennews_client(pull_events=events)
        service = IngestorService(session=session, opennews_client=client)
        result = await service.ingest_pull()

        assert result.total_fetched == 2
        assert result.new_ingested == 0
        assert result.duplicates_skipped == 2
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_mixed_new_and_duplicate(self) -> None:
        """混合新旧事件的场景。"""
        events = [
            _make_webhook_payload(event_id="new_1", title="New Event 1"),
            _make_webhook_payload(event_id="dup_1", title="Dup Event 1"),
            _make_webhook_payload(event_id="new_2", title="New Event 2"),
        ]

        call_count = 0

        session = AsyncMock()

        def mock_execute(stmt):
            nonlocal call_count
            result = AsyncMock()
            # 第 2 个事件（index=1）模拟为已存在
            if call_count == 1:
                result.scalar_one_or_none = MagicMock(return_value=MagicMock())
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            call_count += 1
            return result

        session.execute = AsyncMock(side_effect=mock_execute)
        session.flush = AsyncMock()

        def mock_refresh(obj):
            import uuid
            obj.event_id = uuid.uuid4()
            obj.received_at = datetime.now(timezone.utc)
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        session.refresh = AsyncMock(side_effect=mock_refresh)
        session.add = MagicMock()

        client = _make_mock_opennews_client(pull_events=events)
        service = IngestorService(session=session, opennews_client=client)
        result = await service.ingest_pull()

        assert result.total_fetched == 3
        assert result.new_ingested == 2
        assert result.duplicates_skipped == 1

    @pytest.mark.asyncio
    async def test_invalid_event_skipped(self) -> None:
        """标准化失败的事件应被跳过。"""
        events = [
            _make_webhook_payload(event_id="good_1", title="Good Event"),
            {"id": "", "title": ""},  # 无效事件
        ]

        session = _make_mock_session()

        def mock_refresh(obj):
            import uuid
            obj.event_id = uuid.uuid4()
            obj.received_at = datetime.now(timezone.utc)
            obj.created_at = datetime.now(timezone.utc)
            obj.updated_at = datetime.now(timezone.utc)

        session.refresh = AsyncMock(side_effect=mock_refresh)

        client = _make_mock_opennews_client(pull_events=events)
        service = IngestorService(session=session, opennews_client=client)
        result = await service.ingest_pull()

        # 1 个成功，1 个标准化失败被跳过（不计入 dup）
        assert result.new_ingested == 1
        assert result.total_fetched == 2


# ------------------------------------------------------------------ #
# dedupe_hash 一致性测试
# ------------------------------------------------------------------ #

class TestDedupeHashConsistency:
    """确保 dedupe_hash 在整个流程中保持一致。"""

    def test_hash_from_normalizer_matches_direct_compute(self) -> None:
        """normalizer 生成的 hash 应与 compute_dedupe_hash 直接计算一致。"""
        from apps.ingestor.normalizer import normalize_opennews

        payload = _make_webhook_payload(event_id="evt_hash_test", title="Hash Test")
        dto = normalize_opennews(payload)

        expected = compute_dedupe_hash(SOURCE_OPENNEWS, "evt_hash_test", "Hash Test")
        assert dto.dedupe_hash == expected

    def test_same_payload_always_same_hash(self) -> None:
        """同一 payload 多次标准化产生相同 hash。"""
        from apps.ingestor.normalizer import normalize_opennews

        payload = _make_webhook_payload()
        hashes = {normalize_opennews(payload).dedupe_hash for _ in range(10)}
        assert len(hashes) == 1
