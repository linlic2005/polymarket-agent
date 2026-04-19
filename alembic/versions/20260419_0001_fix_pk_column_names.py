"""fix primary key column names to match ORM models

Revision ID: 20260419_0001
Revises: 20260418_0001
Create Date: 2026-04-19 00:00:00

ORM models expect:
- ingest_events.event_id (not 'id')
- candidate_markets.candidate_id (not 'id')
"""

from __future__ import annotations

from alembic import op


revision = "20260419_0001"
down_revision = "20260418_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename primary key column on ingest_events: 'id' -> 'event_id'
    op.alter_column("ingest_events", "id", new_column_name="event_id")

    # Rename primary key column on candidate_markets: 'id' -> 'candidate_id'
    op.alter_column("candidate_markets", "id", new_column_name="candidate_id")


def downgrade() -> None:
    # Revert: event_id -> id on ingest_events
    op.alter_column("ingest_events", "event_id", new_column_name="id")
    # Revert: candidate_id -> id on candidate_markets
    op.alter_column("candidate_markets", "candidate_id", new_column_name="id")
