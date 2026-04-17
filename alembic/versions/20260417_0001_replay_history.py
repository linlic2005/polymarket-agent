"""add replay and history tables

Revision ID: 20260417_0001
Revises:
Create Date: 2026-04-17 22:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260417_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "thesis_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("p_market", sa.Float(), nullable=False),
        sa.Column("q_raw", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("rule_clarity_score", sa.Float(), nullable=False),
        sa.Column("pricing_dislocation_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("max_hold_minutes", sa.Integer(), nullable=False),
        sa.Column("reasoning_summary", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_thesis_history_candidate_id", "thesis_history", ["candidate_id"])

    op.create_table(
        "risk_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("allow", sa.Boolean(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("risk_metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_risk_history_candidate_id", "risk_history", ["candidate_id"])

    op.create_table(
        "sizing_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("p_market", sa.Float(), nullable=False),
        sa.Column("q_raw", sa.Float(), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False),
        sa.Column("q_adj", sa.Float(), nullable=False),
        sa.Column("taker_fee_per_share", sa.Float(), nullable=False),
        sa.Column("expected_slippage_per_share", sa.Float(), nullable=False),
        sa.Column("exit_cost_reserve", sa.Float(), nullable=False),
        sa.Column("uncertainty_haircut", sa.Float(), nullable=False),
        sa.Column("p_eff", sa.Float(), nullable=False),
        sa.Column("edge_net", sa.Float(), nullable=False),
        sa.Column("f_full", sa.Float(), nullable=False),
        sa.Column("f_half", sa.Float(), nullable=False),
        sa.Column("f_final", sa.Float(), nullable=False),
        sa.Column("sizing_reason_codes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sizing_history_candidate_id", "sizing_history", ["candidate_id"])

    op.create_table(
        "market_snapshot_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("condition_id", sa.String(length=256), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("best_bid", sa.Float(), nullable=False),
        sa.Column("best_ask", sa.Float(), nullable=False),
        sa.Column("executable_size", sa.Float(), nullable=False),
        sa.Column("spread", sa.Float(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
    )
    op.create_index("ix_market_snapshot_history_condition_id", "market_snapshot_history", ["condition_id"])
    op.create_index("ix_market_snapshot_history_outcome", "market_snapshot_history", ["outcome"])
    op.create_index("ix_market_snapshot_history_snapshot_at", "market_snapshot_history", ["snapshot_at"])

    op.create_table(
        "market_resolutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("condition_id", sa.String(length=256), nullable=False),
        sa.Column("resolved_outcome", sa.String(length=8), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payout_yes", sa.Float(), nullable=False),
        sa.Column("payout_no", sa.Float(), nullable=False),
    )
    op.create_index("ix_market_resolutions_condition_id", "market_resolutions", ["condition_id"], unique=True)
    op.create_index("ix_market_resolutions_resolved_at", "market_resolutions", ["resolved_at"])

    op.create_table(
        "replay_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_anchor", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("tradable_count", sa.Integer(), nullable=False),
        sa.Column("avg_net_edge", sa.Float(), nullable=False),
        sa.Column("simulated_fill_count", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Float(), nullable=False),
        sa.Column("avg_holding_minutes", sa.Float(), nullable=False),
        sa.Column("max_drawdown", sa.Float(), nullable=False),
        sa.Column("cumulative_pnl", sa.Float(), nullable=False),
        sa.Column("export_dir", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "replay_candidate_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("replay_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("condition_id", sa.String(length=256), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=False),
        sa.Column("order_size", sa.Float(), nullable=False),
        sa.Column("is_tradable", sa.Boolean(), nullable=False),
        sa.Column("was_filled", sa.Boolean(), nullable=False),
        sa.Column("net_edge", sa.Float(), nullable=True),
        sa.Column("fill_price", sa.Float(), nullable=True),
        sa.Column("fill_size", sa.Float(), nullable=True),
        sa.Column("fill_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("not_tradable_reason", sa.Text(), nullable=True),
        sa.Column("not_filled_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_replay_candidate_results_replay_run_id", "replay_candidate_results", ["replay_run_id"])
    op.create_index("ix_replay_candidate_results_candidate_order_id", "replay_candidate_results", ["candidate_order_id"])
    op.create_index("ix_replay_candidate_results_event_id", "replay_candidate_results", ["event_id"])
    op.create_index("ix_replay_candidate_results_condition_id", "replay_candidate_results", ["condition_id"])

    op.create_table(
        "replay_trade_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("replay_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("condition_id", sa.String(length=256), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("outcome", sa.String(length=8), nullable=False),
        sa.Column("fill_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fill_price", sa.Float(), nullable=False),
        sa.Column("fill_size", sa.Float(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_outcome", sa.String(length=8), nullable=False),
        sa.Column("payout_per_share", sa.Float(), nullable=False),
        sa.Column("pnl", sa.Float(), nullable=False),
        sa.Column("holding_minutes", sa.Float(), nullable=False),
        sa.Column("is_win", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_replay_trade_results_replay_run_id", "replay_trade_results", ["replay_run_id"])
    op.create_index("ix_replay_trade_results_candidate_result_id", "replay_trade_results", ["candidate_result_id"])
    op.create_index("ix_replay_trade_results_candidate_order_id", "replay_trade_results", ["candidate_order_id"])
    op.create_index("ix_replay_trade_results_condition_id", "replay_trade_results", ["condition_id"])
    op.create_index("ix_replay_trade_results_fill_at", "replay_trade_results", ["fill_at"])
    op.create_index("ix_replay_trade_results_resolved_at", "replay_trade_results", ["resolved_at"])

    op.create_table(
        "replay_equity_points",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("replay_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cumulative_pnl", sa.Float(), nullable=False),
        sa.Column("drawdown", sa.Float(), nullable=False),
    )
    op.create_index("ix_replay_equity_points_replay_run_id", "replay_equity_points", ["replay_run_id"])
    op.create_index("ix_replay_equity_points_timestamp", "replay_equity_points", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_replay_equity_points_timestamp", table_name="replay_equity_points")
    op.drop_index("ix_replay_equity_points_replay_run_id", table_name="replay_equity_points")
    op.drop_table("replay_equity_points")

    op.drop_index("ix_replay_trade_results_resolved_at", table_name="replay_trade_results")
    op.drop_index("ix_replay_trade_results_fill_at", table_name="replay_trade_results")
    op.drop_index("ix_replay_trade_results_condition_id", table_name="replay_trade_results")
    op.drop_index("ix_replay_trade_results_candidate_order_id", table_name="replay_trade_results")
    op.drop_index("ix_replay_trade_results_candidate_result_id", table_name="replay_trade_results")
    op.drop_index("ix_replay_trade_results_replay_run_id", table_name="replay_trade_results")
    op.drop_table("replay_trade_results")

    op.drop_index("ix_replay_candidate_results_condition_id", table_name="replay_candidate_results")
    op.drop_index("ix_replay_candidate_results_event_id", table_name="replay_candidate_results")
    op.drop_index("ix_replay_candidate_results_candidate_order_id", table_name="replay_candidate_results")
    op.drop_index("ix_replay_candidate_results_replay_run_id", table_name="replay_candidate_results")
    op.drop_table("replay_candidate_results")

    op.drop_table("replay_runs")

    op.drop_index("ix_market_resolutions_resolved_at", table_name="market_resolutions")
    op.drop_index("ix_market_resolutions_condition_id", table_name="market_resolutions")
    op.drop_table("market_resolutions")

    op.drop_index("ix_market_snapshot_history_snapshot_at", table_name="market_snapshot_history")
    op.drop_index("ix_market_snapshot_history_outcome", table_name="market_snapshot_history")
    op.drop_index("ix_market_snapshot_history_condition_id", table_name="market_snapshot_history")
    op.drop_table("market_snapshot_history")

    op.drop_index("ix_sizing_history_candidate_id", table_name="sizing_history")
    op.drop_table("sizing_history")

    op.drop_index("ix_risk_history_candidate_id", table_name="risk_history")
    op.drop_table("risk_history")

    op.drop_index("ix_thesis_history_candidate_id", table_name="thesis_history")
    op.drop_table("thesis_history")
