"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-11-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("product", sa.String(length=512), nullable=False),
        sa.Column("origin_country", sa.String(length=128), nullable=False),
        sa.Column("guessed_hs_code", sa.String(length=32), nullable=True),
        sa.Column("hs_confidence", sa.String(length=16), nullable=True),
        sa.Column("phase", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("selected_country", sa.String(length=8), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message_fa", sa.Text(), nullable=True),
        sa.Column("error_retryable", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_mock", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("markets_json", sa.Text(), nullable=True),
        sa.Column("buyers_json", sa.Text(), nullable=True),
        sa.Column("feasibility_json", sa.Text(), nullable=True),
        sa.Column("report_json", sa.Text(), nullable=True),
    )
    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("phase", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("message_fa", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("source_refs_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_run_events_event_id", "run_events", ["event_id"], unique=True)
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])
    op.create_table(
        "provider_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="untested"),
        sa.Column("usage_note_fa", sa.Text(), nullable=False, server_default=""),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column("used_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider_id", name="uq_provider_id"),
    )
    op.create_table(
        "app_meta",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_meta")
    op.drop_table("provider_settings")
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_index("ix_run_events_event_id", table_name="run_events")
    op.drop_table("run_events")
    op.drop_table("runs")
