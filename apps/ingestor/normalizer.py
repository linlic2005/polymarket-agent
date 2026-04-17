"""
事件标准化模块。

职责：
1. 将各事件源的原始 payload (dict) 转换为统一的 IngestEventCreate DTO
2. 计算去重哈希 (dedupe_hash)
3. 提取实体标签 / 标的标签

所有函数均为纯函数，无副作用，便于单元测试。
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from libs.models.schemas import IngestEventCreate

logger = logging.getLogger(__name__)

# 事件来源常量
SOURCE_OPENNEWS = "opennews_6551"


def compute_dedupe_hash(source: str, source_event_id: str, headline: str) -> str:
    """
    计算去重哈希。

    使用 source + source_event_id + headline 的组合作为去重依据，
    生成 SHA-256 hex digest（64 字符）。

    Args:
        source: 事件来源标识
        source_event_id: 外部事件 ID
        headline: 事件标题

    Returns:
        64 字符的 hex 哈希字符串
    """
    raw = f"{source}|{source_event_id}|{headline}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_datetime(value: str | None) -> datetime | None:
    """
    尝试将 ISO 格式字符串解析为 datetime。

    支持常见格式：
    - 2024-01-15T08:30:00Z
    - 2024-01-15T08:30:00+08:00
    - 2024-01-15 08:30:00

    Returns:
        解析后的 datetime 对象，失败则返回 None。
    """
    if not value:
        return None
    try:
        # 处理 Z 后缀
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (ValueError, TypeError):
        logger.warning("无法解析时间字符串: %s", value)
        return None


def _extract_entity_tags(raw: dict[str, Any]) -> list[str]:
    """
    从原始 payload 中提取实体标签。

    优先使用 'tags' 字段，回退到 'entities' 字段。

    Returns:
        去重后的实体标签列表。
    """
    tags = raw.get("tags", [])
    if not tags:
        tags = raw.get("entities", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return list(dict.fromkeys(tags))  # 保序去重


def _extract_symbol_tags(raw: dict[str, Any]) -> list[str]:
    """
    从原始 payload 中提取标的标签。

    优先使用 'symbols' 字段，回退到 'tickers' 字段。

    Returns:
        去重后的标的标签列表（统一大写）。
    """
    symbols = raw.get("symbols", [])
    if not symbols:
        symbols = raw.get("tickers", [])
    if isinstance(symbols, str):
        symbols = [s.strip() for s in symbols.split(",") if s.strip()]
    return list(dict.fromkeys(s.upper() for s in symbols))


def normalize_opennews(raw: dict[str, Any]) -> IngestEventCreate:
    """
    将 OpenNews 原始 payload 标准化为 IngestEventCreate DTO。

    字段映射：
    - id → source_event_id
    - title → headline
    - body → summary
    - category → event_type（fallback: "news"）
    - published_at → published_at（ISO 解析）
    - tags → entity_tags
    - symbols → symbol_tags
    - ai_score → ai_score
    - signal → signal_hint

    Args:
        raw: OpenNews 原始事件 dict

    Returns:
        标准化后的 IngestEventCreate DTO

    Raises:
        ValueError: 缺少必要字段（id, title）时抛出
    """
    source_event_id = str(raw.get("id", ""))
    if not source_event_id:
        raise ValueError("OpenNews 事件缺少 'id' 字段")

    headline = raw.get("title", "")
    if not headline:
        raise ValueError("OpenNews 事件缺少 'title' 字段")

    entity_tags = _extract_entity_tags(raw)
    symbol_tags = _extract_symbol_tags(raw)
    published_at = _parse_datetime(raw.get("published_at"))
    event_type = raw.get("category", "news") or "news"
    ai_score = raw.get("ai_score")
    signal_hint = raw.get("signal")

    # 确保 ai_score 在有效范围内
    if ai_score is not None:
        try:
            ai_score = float(ai_score)
            ai_score = max(0.0, min(1.0, ai_score))
        except (ValueError, TypeError):
            ai_score = None

    dedupe_hash = compute_dedupe_hash(SOURCE_OPENNEWS, source_event_id, headline)

    return IngestEventCreate(
        source=SOURCE_OPENNEWS,
        source_event_id=source_event_id,
        published_at=published_at,
        event_type=event_type,
        entity_tags=entity_tags,
        symbol_tags=symbol_tags,
        headline=headline,
        summary=raw.get("body"),
        ai_score=ai_score,
        signal_hint=signal_hint,
        raw_payload=json.dumps(raw, ensure_ascii=False, default=str),
        dedupe_hash=dedupe_hash,
    )
