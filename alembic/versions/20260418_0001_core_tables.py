"""add core operational tables + audit_logs

Revision ID: 20260418_0001
Revises: 20260417_0001
Create Date: 2026-04-18 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260418_0001"
down_revision = "20260417_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- ingest_events ---
    op.create_table(
        "ingest_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_event_id", sa.String(length=256), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("entity_tags", postgresql.JSON, nullable=True),
        sa.Column("symbol_tags", postgresql.JSON, nullable=True),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("signal_hint", sa.String(length=128), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("dedupe_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ingest_events_source", "ingest_events", ["source"])
    op.create_index("ix_ingest_events_dedupe_hash", "ingest_events", ["dedupe_hash"])

    # --- market_events (legacy) ---
    op.create_table(
        "market_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- candidate_markets ---
    op.create_table(
        "candidate_markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("polymarket_event_slug", sa.String(length=256), nullable=False),
        sa.Column("market_slug", sa.String(length=256), nullable=False),
        sa.Column("token_yes", sa.String(length=256), nullable=False),
        sa.Column("token_no", sa.String(length=256), nullable=False),
        sa.Column("mapping_score", sa.Float(), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=True),
        sa.Column("rule_text_changed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("orderbook_snapshot", postgresql.JSON, nullable=True),
        sa.Column("spread_snapshot", sa.Float(), nullable=True),
        sa.Column("time_to_resolution", sa.Float(), nullable=True),
        sa.Column("fees_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rules_parsed", postgresql.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_candidate_markets_event_id", "candidate_markets", ["event_id"])

    # --- candidate_orders ---
    op.create_table(
        "candidate_orders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("market_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("polymarket_condition_id", sa.String(length=256), nullable=True),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=False),
        sa.Column("size", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("thesis_summary", sa.Text(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_candidate_orders_status", "candidate_orders", ["status"])

    # --- positions ---
    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("polymarket_condition_id", sa.String(length=256), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_entry_price", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("realised_pnl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("unrealised_pnl", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_positions_candidate_id", "positions", ["candidate_id"])
    op.create_index("ix_positions_polymarket_condition_id", "positions", ["polymarket_condition_id"])

    # --- execution_records ---
    op.create_table(
        "execution_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("candidate_order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("exchange_order_id", sa.String(length=256), nullable=True),
        sa.Column("executed_price", sa.Float(), nullable=True),
        sa.Column("executed_size", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_execution_records_candidate_order_id", "execution_records", ["candidate_order_id"])

    # --- rule_snapshots ---
    op.create_table(
        "rule_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rule_snapshots_candidate_id", "rule_snapshots", ["candidate_id"])

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="INFO"),
        sa.Column("module", sa.String(length=64), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("extra", postgresql.JSON, nullable=True),
    )
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_candidate_id", "audit_logs", ["candidate_id"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("rule_snapshots")
    op.drop_table("execution_records")
    op.drop_table("positions")
    op.drop_table("candidate_orders")
    op.drop_table("candidate_markets")
    op.drop_table("market_events")
    op.drop_table("ingest_events")
