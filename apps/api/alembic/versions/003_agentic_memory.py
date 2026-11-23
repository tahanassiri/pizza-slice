"""agentic memory, tasks, evidence, budgets

Revision ID: 003
Revises: 002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "research_tasks",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.String(64), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkpoint_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message_fa", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_research_tasks_run_id", "research_tasks", ["run_id"])

    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("canonical_key", sa.String(512), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(32), nullable=False, server_default="public"),
        sa.Column("product_normalized", sa.String(256), nullable=True),
        sa.Column("hs6", sa.String(16), nullable=True),
        sa.Column("origin", sa.String(128), nullable=True),
        sa.Column("destination", sa.String(8), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_period", sa.String(64), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stale_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("origin_run_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.UniqueConstraint("canonical_key", "version", name="uq_knowledge_key_version"),
    )
    op.create_index("ix_knowledge_items_canonical_key", "knowledge_items", ["canonical_key"])

    op.create_table(
        "evidence_sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("title", sa.String(512), nullable=False, server_default=""),
        sa.Column("publisher", sa.String(256), nullable=False, server_default=""),
        sa.Column("published_at", sa.String(64), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False, server_default=""),
        sa.Column("reliability_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("raw_excerpt", sa.Text(), nullable=True),
    )
    op.create_index("ix_evidence_sources_run_id", "evidence_sources", ["run_id"])

    op.create_table(
        "claims",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("knowledge_id", sa.String(64), nullable=True),
        sa.Column("evidence_id", sa.String(64), nullable=True),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("data_kind", sa.String(32), nullable=False, server_default="estimate"),
        sa.Column("hs_scope", sa.String(32), nullable=True),
        sa.Column("country_scope", sa.String(8), nullable=True),
        sa.Column("confidence", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("supersedes", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_claims_run_id", "claims", ["run_id"])

    op.create_table(
        "company_profiles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("canonical_domain", sa.String(256), nullable=False),
        sa.Column("company_name", sa.String(512), nullable=False),
        sa.Column("country", sa.String(8), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="unknown"),
        sa.Column("verification_status", sa.String(32), nullable=False, server_default="candidate"),
        sa.Column("website", sa.String(1024), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=False),
        sa.Column("origin_run_id", sa.String(64), nullable=True),
        sa.UniqueConstraint("canonical_domain", "country", name="uq_company_domain_country"),
    )
    op.create_index("ix_company_profiles_canonical_domain", "company_profiles", ["canonical_domain"])

    op.create_table(
        "market_assessments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("country_code", sa.String(8), nullable=False),
        sa.Column("recommendation", sa.String(32), nullable=False, server_default="watch"),
        sa.Column("score_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("data_scope", sa.String(32), nullable=False, server_default="sector"),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_market_assessments_run_id", "market_assessments", ["run_id"])

    op.create_table(
        "cost_estimates",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("run_id", sa.String(64), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("cost_id", sa.String(64), nullable=False),
        sa.Column("amount", sa.String(64), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(32), nullable=False, server_default="missing"),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("note_fa", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_cost_estimates_run_id", "cost_estimates", ["run_id"])

    op.create_table(
        "usage_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=True),
        sa.Column("provider_id", sa.String(64), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ok", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("detail_fa", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_usage_audit_run_id", "usage_audit", ["run_id"])

    op.create_table(
        "agent_budgets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(64), nullable=False, server_default="global"),
        sa.Column("scope_id", sa.String(64), nullable=True),
        sa.Column("max_model_calls", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("max_search_queries", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_pages", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("max_wall_seconds", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("model_calls_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("search_queries_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pages_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("agent_budgets")
    op.drop_table("usage_audit")
    op.drop_table("cost_estimates")
    op.drop_table("market_assessments")
    op.drop_table("company_profiles")
    op.drop_table("claims")
    op.drop_table("evidence_sources")
    op.drop_table("knowledge_items")
    op.drop_table("research_tasks")
