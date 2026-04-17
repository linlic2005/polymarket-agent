"""
normalizer 模块的单元测试。

覆盖：
- compute_dedupe_hash 的确定性与唯一性
- normalize_opennews 各种 payload 变体
- 缺字段时的 fallback 行为
- 实体标签 / 标的标签提取
- 时间解析
"""

from __future__ import annotations

import pytest

from apps.ingestor.normalizer import (
    SOURCE_OPENNEWS,
    _extract_entity_tags,
    _extract_symbol_tags,
    _parse_datetime,
    compute_dedupe_hash,
    normalize_opennews,
)


# ------------------------------------------------------------------ #
# compute_dedupe_hash 测试
# ------------------------------------------------------------------ #

class TestComputeDedupeHash:
    """去重哈希计算测试。"""

    def test_deterministic(self) -> None:
        """相同输入应产生相同哈希。"""
        h1 = compute_dedupe_hash("src", "123", "headline")
        h2 = compute_dedupe_hash("src", "123", "headline")
        assert h1 == h2

    def test_64_char_hex(self) -> None:
        """输出应为 64 字符的十六进制字符串 (SHA-256)。"""
        h = compute_dedupe_hash("src", "id1", "title")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_source_different_hash(self) -> None:
        """不同 source 应产生不同哈希。"""
        h1 = compute_dedupe_hash("source_a", "123", "same headline")
        h2 = compute_dedupe_hash("source_b", "123", "same headline")
        assert h1 != h2

    def test_different_id_different_hash(self) -> None:
        """不同 source_event_id 应产生不同哈希。"""
        h1 = compute_dedupe_hash("src", "id_1", "same headline")
        h2 = compute_dedupe_hash("src", "id_2", "same headline")
        assert h1 != h2

    def test_different_headline_different_hash(self) -> None:
        """不同 headline 应产生不同哈希。"""
        h1 = compute_dedupe_hash("src", "123", "headline A")
        h2 = compute_dedupe_hash("src", "123", "headline B")
        assert h1 != h2

    def test_unicode_input(self) -> None:
        """Unicode 输入应正常处理。"""
        h = compute_dedupe_hash("src", "中文ID", "中文标题")
        assert len(h) == 64

    def test_empty_strings(self) -> None:
        """空字符串输入也应产生有效哈希。"""
        h = compute_dedupe_hash("", "", "")
        assert len(h) == 64


# ------------------------------------------------------------------ #
# normalize_opennews 测试
# ------------------------------------------------------------------ #

class TestNormalizeOpennews:
    """OpenNews 事件标准化测试。"""

    @pytest.fixture
    def full_payload(self) -> dict:
        """完整的 OpenNews 事件 payload。"""
        return {
            "id": "evt_001",
            "title": "Bitcoin Hits New ATH",
            "body": "Bitcoin reached $100k today.",
            "category": "crypto",
            "published_at": "2024-01-15T08:30:00Z",
            "tags": ["Bitcoin", "Cryptocurrency"],
            "symbols": ["BTC", "ETH"],
            "ai_score": 0.85,
            "signal": "bullish",
        }

    @pytest.fixture
    def minimal_payload(self) -> dict:
        """最小有效 payload（仅 id + title）。"""
        return {
            "id": "evt_002",
            "title": "Some Event",
        }

    def test_full_payload(self, full_payload: dict) -> None:
        """完整 payload 应正确标准化。"""
        dto = normalize_opennews(full_payload)
        assert dto.source == SOURCE_OPENNEWS
        assert dto.source_event_id == "evt_001"
        assert dto.headline == "Bitcoin Hits New ATH"
        assert dto.summary == "Bitcoin reached $100k today."
        assert dto.event_type == "crypto"
        assert dto.entity_tags == ["Bitcoin", "Cryptocurrency"]
        assert dto.symbol_tags == ["BTC", "ETH"]
        assert dto.ai_score == 0.85
        assert dto.signal_hint == "bullish"
        assert dto.published_at is not None
        assert len(dto.dedupe_hash) == 64
        assert dto.raw_payload is not None

    def test_minimal_payload(self, minimal_payload: dict) -> None:
        """最小 payload 应使用默认值。"""
        dto = normalize_opennews(minimal_payload)
        assert dto.source == SOURCE_OPENNEWS
        assert dto.source_event_id == "evt_002"
        assert dto.headline == "Some Event"
        assert dto.event_type == "news"  # 默认值
        assert dto.entity_tags == []
        assert dto.symbol_tags == []
        assert dto.ai_score is None
        assert dto.signal_hint is None
        assert dto.summary is None

    def test_missing_id_raises(self) -> None:
        """缺少 id 应抛出 ValueError。"""
        with pytest.raises(ValueError, match="'id'"):
            normalize_opennews({"title": "No ID"})

    def test_missing_title_raises(self) -> None:
        """缺少 title 应抛出 ValueError。"""
        with pytest.raises(ValueError, match="'title'"):
            normalize_opennews({"id": "123"})

    def test_empty_id_raises(self) -> None:
        """空 id 应抛出 ValueError。"""
        with pytest.raises(ValueError, match="'id'"):
            normalize_opennews({"id": "", "title": "Has Title"})

    def test_empty_title_raises(self) -> None:
        """空 title 应抛出 ValueError。"""
        with pytest.raises(ValueError, match="'title'"):
            normalize_opennews({"id": "123", "title": ""})

    def test_ai_score_clamped(self) -> None:
        """超范围的 ai_score 应被裁剪到 [0, 1]。"""
        dto = normalize_opennews({
            "id": "evt_003",
            "title": "Test",
            "ai_score": 1.5,
        })
        assert dto.ai_score == 1.0

    def test_ai_score_negative_clamped(self) -> None:
        """负数 ai_score 应被裁剪到 0。"""
        dto = normalize_opennews({
            "id": "evt_004",
            "title": "Test",
            "ai_score": -0.5,
        })
        assert dto.ai_score == 0.0

    def test_ai_score_invalid_string(self) -> None:
        """非数字 ai_score 应被设为 None。"""
        dto = normalize_opennews({
            "id": "evt_005",
            "title": "Test",
            "ai_score": "invalid",
        })
        assert dto.ai_score is None

    def test_category_none_fallback(self) -> None:
        """category 为 None 时应回退到 'news'。"""
        dto = normalize_opennews({
            "id": "evt_006",
            "title": "Test",
            "category": None,
        })
        assert dto.event_type == "news"

    def test_same_event_same_hash(self, full_payload: dict) -> None:
        """同一事件两次标准化应产生相同 dedupe_hash。"""
        dto1 = normalize_opennews(full_payload)
        dto2 = normalize_opennews(full_payload)
        assert dto1.dedupe_hash == dto2.dedupe_hash

    def test_different_events_different_hash(self) -> None:
        """不同事件应产生不同 dedupe_hash。"""
        dto1 = normalize_opennews({"id": "a", "title": "A"})
        dto2 = normalize_opennews({"id": "b", "title": "B"})
        assert dto1.dedupe_hash != dto2.dedupe_hash


# ------------------------------------------------------------------ #
# 辅助函数测试
# ------------------------------------------------------------------ #

class TestParseDatetime:
    """时间字符串解析测试。"""

    def test_iso_with_z(self) -> None:
        dt = _parse_datetime("2024-01-15T08:30:00Z")
        assert dt is not None
        assert dt.year == 2024

    def test_iso_with_tz(self) -> None:
        dt = _parse_datetime("2024-01-15T08:30:00+08:00")
        assert dt is not None

    def test_none_input(self) -> None:
        assert _parse_datetime(None) is None

    def test_empty_string(self) -> None:
        assert _parse_datetime("") is None

    def test_invalid_string(self) -> None:
        assert _parse_datetime("not-a-date") is None


class TestExtractEntityTags:
    """实体标签提取测试。"""

    def test_list_tags(self) -> None:
        assert _extract_entity_tags({"tags": ["A", "B"]}) == ["A", "B"]

    def test_string_tags(self) -> None:
        assert _extract_entity_tags({"tags": "A, B, C"}) == ["A", "B", "C"]

    def test_fallback_to_entities(self) -> None:
        assert _extract_entity_tags({"entities": ["X"]}) == ["X"]

    def test_empty(self) -> None:
        assert _extract_entity_tags({}) == []

    def test_dedup(self) -> None:
        result = _extract_entity_tags({"tags": ["A", "B", "A"]})
        assert result == ["A", "B"]


class TestExtractSymbolTags:
    """标的标签提取测试。"""

    def test_list_symbols(self) -> None:
        assert _extract_symbol_tags({"symbols": ["btc", "eth"]}) == ["BTC", "ETH"]

    def test_string_symbols(self) -> None:
        result = _extract_symbol_tags({"symbols": "btc, eth"})
        assert result == ["BTC", "ETH"]

    def test_fallback_to_tickers(self) -> None:
        assert _extract_symbol_tags({"tickers": ["sol"]}) == ["SOL"]

    def test_empty(self) -> None:
        assert _extract_symbol_tags({}) == []

    def test_uppercase(self) -> None:
        result = _extract_symbol_tags({"symbols": ["Btc"]})
        assert result == ["BTC"]
