"""
Pydantic v2 DTO / Schema 定义。

用于 API 输入输出、内部服务间消息传递。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ------------------------------------------------------------------ #
# 通用
# ------------------------------------------------------------------ #
class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str = "ok"
    version: str = "0.1.0"
    app_env: str = "development"
    dry_run: bool = True


# ------------------------------------------------------------------ #
# 事件
# ------------------------------------------------------------------ #
class MarketEventCreate(BaseModel):
    """创建 MarketEvent 所需字段。"""

    source: str = Field(..., max_length=64, description="事件来源标识")
    external_id: str = Field(..., max_length=256)
    title: str
    body: Optional[str] = None
    category: Optional[str] = None
    raw_payload: Optional[str] = None


class MarketEventRead(MarketEventCreate):
    """MarketEvent 的完整读模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    received_at: datetime
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ #
# 候选市场
# ------------------------------------------------------------------ #
class CandidateMarketCreate(BaseModel):
    event_id: uuid.UUID
    polymarket_event_slug: str
    market_slug: str
    token_yes: str
    token_no: str
    mapping_score: float = Field(..., ge=0, le=1.0)
    rule_text: Optional[str] = None
    orderbook_snapshot: Optional[dict] = None
    spread_snapshot: Optional[float] = None
    time_to_resolution: Optional[float] = None
    fees_enabled: bool = False
    rules_parsed: Optional[dict] = None


class CandidateMarketRead(CandidateMarketCreate):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ #
# 候选单
# ------------------------------------------------------------------ #
class CandidateOrderCreate(BaseModel):
    """创建候选单所需字段。"""

    market_event_id: uuid.UUID
    polymarket_condition_id: Optional[str] = None
    side: str = Field(..., pattern="^(BUY|SELL)$")
    outcome: str = Field(..., pattern="^(YES|NO)$")
    target_price: float = Field(..., gt=0, le=1)
    size: float = Field(..., gt=0)
    thesis_summary: Optional[str] = None


class CandidateOrderRead(CandidateOrderCreate):
    """候选单完整读模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    dry_run: bool
    risk_score: Optional[float] = None
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ #
# 仓位
# ------------------------------------------------------------------ #
class PositionRead(BaseModel):
    """仓位读模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    polymarket_condition_id: str
    outcome: str
    size: float
    avg_entry_price: float
    realised_pnl: float
    unrealised_pnl: float
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ #
# 执行记录
# ------------------------------------------------------------------ #
class ExecutionRecordRead(BaseModel):
    """执行记录读模型。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_order_id: uuid.UUID
    exchange_order_id: Optional[str] = None
    executed_price: Optional[float] = None
    executed_size: Optional[float] = None
    status: str
    dry_run: bool
    error_message: Optional[str] = None
    executed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ #
# 投研 (Thesis)
# ------------------------------------------------------------------ #
class ThesisResult(BaseModel):
    """投研结论结果。"""

    candidate_id: uuid.UUID
    direction: str = Field(..., pattern="^(YES|NO)$")
    p_market: float = Field(..., ge=0, le=1)
    q_raw: float = Field(..., ge=0, le=1)
    novelty_score: float = Field(..., ge=0, le=100)
    rule_clarity_score: float = Field(..., ge=0, le=100)
    pricing_dislocation_score: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    max_hold_minutes: int = Field(..., ge=0)
    reasoning_summary: str
    evidence: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------ #
# 风控
# ------------------------------------------------------------------ #
class RiskDecision(BaseModel):
    """风控决策结果。"""

    allow: bool
    reason_codes: list[str] = Field(default_factory=list)
    risk_metrics_json: dict = Field(default_factory=dict)


# ------------------------------------------------------------------ #
# 仓位管理（sizing）
# ------------------------------------------------------------------ #
class SizingDecision(BaseModel):
    """仓位计算决策结果。"""

    candidate_id: uuid.UUID
    p_market: float
    q_raw: float
    alpha: float
    q_adj: float
    taker_fee_per_share: float
    expected_slippage_per_share: float
    exit_cost_reserve: float
    uncertainty_haircut: float
    p_eff: float
    edge_net: float
    f_full: float
    f_half: float
    f_final: float
    sizing_reason_codes: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------ #
# 统一事件模型（Ingestor）
# ------------------------------------------------------------------ #
class IngestEventCreate(BaseModel):
    """创建 IngestEvent 所需字段。"""

    source: str = Field(..., max_length=64, description="事件来源标识")
    source_event_id: str = Field(..., max_length=256, description="外部事件 ID")
    published_at: Optional[datetime] = Field(None, description="事件发布时间")
    event_type: str = Field(default="unknown", max_length=64, description="事件类型")
    entity_tags: list[str] = Field(default_factory=list, description="实体标签")
    symbol_tags: list[str] = Field(default_factory=list, description="标的标签")
    headline: str = Field(..., description="标题")
    summary: Optional[str] = Field(None, description="摘要")
    ai_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="AI 评分")
    signal_hint: Optional[str] = Field(None, max_length=128, description="信号提示")
    raw_payload: Optional[str] = Field(None, description="原始 JSON 字符串")
    dedupe_hash: str = Field(..., max_length=64, description="去重哈希")


class IngestEventRead(IngestEventCreate):
    """IngestEvent 完整读模型。"""

    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID
    received_at: datetime
    created_at: datetime
    updated_at: datetime


class OpenNewsWebhookPayload(BaseModel):
    """OpenNews webhook 推送的原始负载结构。"""

    id: str = Field(..., description="OpenNews 事件 ID")
    title: str = Field(default="", description="标题")
    body: Optional[str] = Field(None, description="正文")
    category: Optional[str] = Field(None, description="分类")
    published_at: Optional[str] = Field(None, description="发布时间 ISO 格式")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    symbols: list[str] = Field(default_factory=list, description="标的符号列表")
    ai_score: Optional[float] = Field(None, description="AI 评分")
    signal: Optional[str] = Field(None, description="信号提示")

    model_config = ConfigDict(extra="allow")


class IngestPullResponse(BaseModel):
    """批量拉取事件响应。"""

    status: str = "ok"
    total_fetched: int = Field(default=0, description="拉取到的事件数")
    new_ingested: int = Field(default=0, description="新入库数（去重后）")
    duplicates_skipped: int = Field(default=0, description="跳过的重复事件数")


# ------------------------------------------------------------------ #
# 编排与控制流 (Orchestrator)
# ------------------------------------------------------------------ #
class ApprovalDecision(BaseModel):
    """审批决策结果。"""

    candidate_id: uuid.UUID
    approved: bool
    approver: str
    note: Optional[str] = None
    decided_at: datetime = Field(default_factory=datetime.utcnow)


# ------------------------------------------------------------------ #
# 报表 (Reporting)
# ------------------------------------------------------------------ #
class DailyReport(BaseModel):
    """每日生成的工作情况结单。"""

    date: str
    events_received_count: int
    candidates_generated_count: int
    risk_rejected_count: int
    approval_granted_count: int
    orders_placed_count: int
    orders_filled_count: int
    current_positions_count: int
    realized_pnl_usd: float
    unrealized_pnl_usd: float


# ------------------------------------------------------------------ #
# Replay
# ------------------------------------------------------------------ #
class ReplayRunSummary(BaseModel):
    """单次 replay run 的汇总结果。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    start_at: datetime
    end_at: datetime
    window_anchor: str
    status: str
    candidate_count: int
    tradable_count: int
    avg_net_edge: float
    simulated_fill_count: int
    win_rate: float
    avg_holding_minutes: float
    max_drawdown: float
    cumulative_pnl: float
    export_dir: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReplayCandidateResult(BaseModel):
    """逐候选单 replay 结果。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    replay_run_id: uuid.UUID
    candidate_order_id: uuid.UUID
    event_id: uuid.UUID
    condition_id: Optional[str] = None
    side: str
    outcome: str
    target_price: float
    order_size: float
    is_tradable: bool
    was_filled: bool
    net_edge: Optional[float] = None
    fill_price: Optional[float] = None
    fill_size: Optional[float] = None
    fill_at: Optional[datetime] = None
    not_tradable_reason: Optional[str] = None
    not_filled_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ReplayTradeResult(BaseModel):
    """逐成交 replay 结果。"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    replay_run_id: uuid.UUID
    candidate_result_id: uuid.UUID
    candidate_order_id: uuid.UUID
    condition_id: str
    side: str
    outcome: str
    fill_at: datetime
    fill_price: float
    fill_size: float
    resolved_at: datetime
    resolved_outcome: str
    payout_per_share: float
    pnl: float
    holding_minutes: float
    is_win: bool
    created_at: datetime
    updated_at: datetime


class ReplayExportManifest(BaseModel):
    """Replay 导出清单。"""

    run_id: uuid.UUID
    export_dir: str
    files: dict[str, str]
