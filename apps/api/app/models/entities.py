from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product: Mapped[str] = mapped_column(String(512), nullable=False)
    origin_country: Mapped[str] = mapped_column(String(128), nullable=False, default="ایران")
    guessed_hs_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    hs_confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    phase: Mapped[str] = mapped_column(String(64), nullable=False, default="intake")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="queued")
    selected_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_retryable: Mapped[int] = mapped_column(Integer, default=0)
    is_mock: Mapped[int] = mapped_column(Integer, default=0)  # 0 = live pipeline
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    events: Mapped[list[RunEventRow]] = relationship(back_populates="run", cascade="all, delete-orphan")
    markets_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    buyers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    feasibility_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunEventRow(Base):
    __tablename__ = "run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    message_fa: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_refs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    run: Mapped[Run] = relationship(back_populates="events")


class BuyerSearchRow(Base):
    __tablename__ = "buyer_searches"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    buyers_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message_fa: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProviderSetting(Base):
    __tablename__ = "provider_settings"
    __table_args__ = (UniqueConstraint("provider_id", name="uq_provider_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="untested")
    usage_note_fa: Mapped[str] = mapped_column(Text, default="")
    daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_today: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AppMeta(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ResearchTask(Base):
    """Durable per-run agent task / checkpoint."""

    __tablename__ = "research_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkpoint_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeItem(Base):
    """Public reusable research memory (never private user financials)."""

    __tablename__ = "knowledge_items"
    __table_args__ = (
        UniqueConstraint("canonical_key", "version", name="uq_knowledge_key_version"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(32), nullable=False, default="public")
    product_normalized: Mapped[str | None] = mapped_column(String(256), nullable=True)
    hs6: Mapped[str | None] = mapped_column(String(16), nullable=True)
    origin: Mapped[str | None] = mapped_column(String(128), nullable=True)
    destination: Mapped[str | None] = mapped_column(String(8), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    confidence: Mapped[str] = mapped_column(String(16), default="unknown")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    published_period: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stale_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    origin_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), default="")
    publisher: Mapped[str] = mapped_column(String(256), default="")
    published_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    provider: Mapped[str] = mapped_column(String(64), default="")
    reliability_note: Mapped[str] = mapped_column(Text, default="")
    raw_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)


class Claim(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    knowledge_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    data_kind: Mapped[str] = mapped_column(String(32), default="estimate")  # fact/estimate/user_input
    hs_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country_scope: Mapped[str | None] = mapped_column(String(8), nullable=True)
    confidence: Mapped[str] = mapped_column(String(16), default="unknown")
    status: Mapped[str] = mapped_column(String(32), default="active")
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    __table_args__ = (UniqueConstraint("canonical_domain", "country", name="uq_company_domain_country"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_domain: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(512), nullable=False)
    country: Mapped[str] = mapped_column(String(8), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="unknown")
    verification_status: Mapped[str] = mapped_column(String(32), default="candidate")
    website: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    last_checked: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    origin_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MarketAssessment(Base):
    __tablename__ = "market_assessments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(32), default="watch")
    score_json: Mapped[str] = mapped_column(Text, default="{}")
    data_scope: Mapped[str] = mapped_column(String(32), default="sector")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CostEstimate(Base):
    __tablename__ = "cost_estimates"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    cost_id: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[str | None] = mapped_column(String(64), nullable=True)  # store as text to avoid float issues in DB display
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    status: Mapped[str] = mapped_column(String(32), default="missing")  # verified/estimated/user_input/missing
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    note_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UsageAudit(Base):
    __tablename__ = "usage_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    units: Mapped[int] = mapped_column(Integer, default=1)
    ok: Mapped[int] = mapped_column(Integer, default=1)
    detail_fa: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentBudget(Base):
    """Server-enforced research budgets (admin-tunable via AppMeta or this row)."""

    __tablename__ = "agent_budgets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, default="global")  # global|run
    scope_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    max_model_calls: Mapped[int] = mapped_column(Integer, default=12)
    max_search_queries: Mapped[int] = mapped_column(Integer, default=20)
    max_pages: Mapped[int] = mapped_column(Integer, default=15)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    max_wall_seconds: Mapped[int] = mapped_column(Integer, default=180)
    model_calls_used: Mapped[int] = mapped_column(Integer, default=0)
    search_queries_used: Mapped[int] = mapped_column(Integer, default=0)
    pages_used: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
