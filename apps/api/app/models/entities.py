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
