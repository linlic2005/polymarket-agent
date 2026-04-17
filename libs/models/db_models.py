"""
SQLAlchemy ORM 基类与核心表定义。

所有数据库表统一使用 DeclarativeBase，并在此文件注册。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ------------------------------------------------------------------ #
# 基类
# ------------------------------------------------------------------ #
class Base(DeclarativeBase):
    """所有 ORM 模型继承此基类。"""
    pass


class TimestampMixin:
    """通用时间戳 mixin，自动记录创建/更新时间。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ------------------------------------------------------------------ #
# 市场 / 事件（旧版，保留兼容）
# ------------------------------------------------------------------ #
class MarketEvent(TimestampMixin, Base):
    """外部事件源（如 6551 OpenNews）推送的原始事件。"""

    __tablename__ = "market_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False, comment="事件来源标识")
    external_id: Mapped[str] = mapped_column(String(256), nullable=False, comment="外部事件 ID")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="事件正文 / 摘要")
    category: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    raw_payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="原始 JSON")
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ------------------------------------------------------------------ #
# 统一事件模型（Ingestor 新版）
# ------------------------------------------------------------------ #
class IngestEvent(TimestampMixin, Base):
    """
    统一事件模型 —— 所有事件源（OpenNews 等）标准化后的事件记录。

    通过 dedupe_hash 进行全局去重，保证同一事件不重复入库。
    """

    __tablename__ = "ingest_events"
    __table_args__ = (
        UniqueConstraint("dedupe_hash", name="uq_ingest_events_dedupe_hash"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        comment="内部事件唯一 ID",
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="事件来源标识，如 opennews_6551",
    )
    source_event_id: Mapped[str] = mapped_column(
        String(256), nullable=False,
        comment="外部事件源的原始 ID",
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="事件在源端的发布时间",
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="系统接收时间",
    )
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False, default="unknown",
        comment="事件类型，如 news / alert / announcement",
    )
    entity_tags: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=list,
        comment="实体标签列表，如 ['Trump', 'SEC']",
    )
    symbol_tags: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, default=list,
        comment="标的标签列表，如 ['BTC', 'ETH']",
    )
    headline: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="事件标题 / 头条",
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="事件摘要",
    )
    ai_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="AI 相关性评分 (0.0 ~ 1.0)",
    )
    signal_hint: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True,
        comment="信号提示，如 bullish / bearish / neutral",
    )
    raw_payload: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="原始 JSON 字符串",
    )
    dedupe_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True,
        comment="去重哈希 (SHA-256)",
    )


# ------------------------------------------------------------------ #
# 候选市场
# ------------------------------------------------------------------ #
class CandidateMarket(TimestampMixin, Base):
    """
    事件映射产生的候选市场。
    记录了相关 Polymarket 条件的映射分数和提取的规则。
    """
    __tablename__ = "candidate_markets"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="关联的 IngestEvent id"
    )
    polymarket_event_slug: Mapped[str] = mapped_column(String(256), nullable=False)
    market_slug: Mapped[str] = mapped_column(String(256), nullable=False)
    token_yes: Mapped[str] = mapped_column(String(256), nullable=False)
    token_no: Mapped[str] = mapped_column(String(256), nullable=False)
    mapping_score: Mapped[float] = mapped_column(Float, nullable=False, comment="0~1")
    rule_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    orderbook_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    spread_snapshot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    time_to_resolution: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fees_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    rules_parsed: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


# ------------------------------------------------------------------ #
# 候选单
# ------------------------------------------------------------------ #
class CandidateOrder(TimestampMixin, Base):
    """
    候选单 —— 经过信号匹配 + 风控筛选后待执行的订单草案。
    status 流转: pending → approved → submitted → filled / rejected / cancelled
    """

    __tablename__ = "candidate_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    market_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, comment="关联事件 ID"
    )
    polymarket_condition_id: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, comment="Polymarket 条件 ID"
    )
    side: Mapped[str] = mapped_column(String(8), nullable=False, comment="BUY / SELL")
    outcome: Mapped[str] = mapped_column(String(64), nullable=False, comment="YES / NO")
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False, comment="下单数量")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", comment="订单状态"
    )
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    thesis_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="交易论点")
    risk_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="风控评分")
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


# ------------------------------------------------------------------ #
# 仓位
# ------------------------------------------------------------------ #
class Position(TimestampMixin, Base):
    """当前持仓快照。"""

    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    polymarket_condition_id: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="Polymarket 条件 ID"
    )
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_entry_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    realised_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unrealised_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


# ------------------------------------------------------------------ #
# 执行记录
# ------------------------------------------------------------------ #
class ExecutionRecord(TimestampMixin, Base):
    """每次（含 dry-run）执行的完整日志。"""

    __tablename__ = "execution_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    exchange_order_id: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, comment="交易所返回的订单 ID"
    )
    executed_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    executed_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ------------------------------------------------------------------ #
# 历史结果
# ------------------------------------------------------------------ #
class ThesisHistory(TimestampMixin, Base):
    """结构化 thesis 历史快照。"""

    __tablename__ = "thesis_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    p_market: Mapped[float] = mapped_column(Float, nullable=False)
    q_raw: Mapped[float] = mapped_column(Float, nullable=False)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False)
    rule_clarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    pricing_dislocation_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    max_hold_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class RiskHistory(TimestampMixin, Base):
    """风控决策历史快照。"""

    __tablename__ = "risk_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    allow: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    risk_metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class SizingHistory(TimestampMixin, Base):
    """仓位计算历史快照。"""

    __tablename__ = "sizing_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    p_market: Mapped[float] = mapped_column(Float, nullable=False)
    q_raw: Mapped[float] = mapped_column(Float, nullable=False)
    alpha: Mapped[float] = mapped_column(Float, nullable=False)
    q_adj: Mapped[float] = mapped_column(Float, nullable=False)
    taker_fee_per_share: Mapped[float] = mapped_column(Float, nullable=False)
    expected_slippage_per_share: Mapped[float] = mapped_column(Float, nullable=False)
    exit_cost_reserve: Mapped[float] = mapped_column(Float, nullable=False)
    uncertainty_haircut: Mapped[float] = mapped_column(Float, nullable=False)
    p_eff: Mapped[float] = mapped_column(Float, nullable=False)
    edge_net: Mapped[float] = mapped_column(Float, nullable=False)
    f_full: Mapped[float] = mapped_column(Float, nullable=False)
    f_half: Mapped[float] = mapped_column(Float, nullable=False)
    f_final: Mapped[float] = mapped_column(Float, nullable=False)
    sizing_reason_codes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)


class MarketSnapshotHistory(Base):
    """历史盘口快照。"""

    __tablename__ = "market_snapshot_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    condition_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    best_bid: Mapped[float] = mapped_column(Float, nullable=False)
    best_ask: Mapped[float] = mapped_column(Float, nullable=False)
    executable_size: Mapped[float] = mapped_column(Float, nullable=False)
    spread: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)


class MarketResolution(Base):
    """历史市场最终决议结果。"""

    __tablename__ = "market_resolutions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    condition_id: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    resolved_outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payout_yes: Mapped[float] = mapped_column(Float, nullable=False)
    payout_no: Mapped[float] = mapped_column(Float, nullable=False)


# ------------------------------------------------------------------ #
# Replay 结果
# ------------------------------------------------------------------ #
class ReplayRun(TimestampMixin, Base):
    """一次 replay run 的汇总结果。"""

    __tablename__ = "replay_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_anchor: Mapped[str] = mapped_column(String(32), nullable=False, default="published_at")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tradable_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_net_edge: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    simulated_fill_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_holding_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cumulative_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    export_dir: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)


class ReplayCandidateResult(TimestampMixin, Base):
    """逐候选单回放结果。"""

    __tablename__ = "replay_candidate_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    replay_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    candidate_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    condition_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    target_price: Mapped[float] = mapped_column(Float, nullable=False)
    order_size: Mapped[float] = mapped_column(Float, nullable=False)
    is_tradable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    was_filled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    net_edge: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fill_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fill_size: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fill_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    not_tradable_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    not_filled_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ReplayTradeResult(TimestampMixin, Base):
    """逐成交回放结果。"""

    __tablename__ = "replay_trade_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    replay_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    candidate_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    candidate_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    condition_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    fill_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    fill_price: Mapped[float] = mapped_column(Float, nullable=False)
    fill_size: Mapped[float] = mapped_column(Float, nullable=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    resolved_outcome: Mapped[str] = mapped_column(String(8), nullable=False)
    payout_per_share: Mapped[float] = mapped_column(Float, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, nullable=False)
    holding_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    is_win: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ReplayEquityPoint(Base):
    """Replay 资金曲线点。"""

    __tablename__ = "replay_equity_points"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    replay_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    cumulative_pnl: Mapped[float] = mapped_column(Float, nullable=False)
    drawdown: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
