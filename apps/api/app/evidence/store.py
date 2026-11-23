"""Persist evidence sources and claims with provenance."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.entities import Claim, EvidenceSource
from app.schemas.contracts import Source


def record_evidence(
    db: Session,
    *,
    run_id: str | None,
    source: Source,
    excerpt: str | None = None,
) -> EvidenceSource:
    row = EvidenceSource(
        id=f"ev_{secrets.token_hex(8)}",
        run_id=run_id,
        url=source.url,
        title=source.title,
        publisher=source.publisher,
        published_at=source.published_at,
        fetched_at=datetime.now(timezone.utc),
        provider=source.provider,
        reliability_note=source.reliability_note,
        raw_excerpt=(excerpt or "")[:4000] or None,
    )
    db.add(row)
    db.commit()
    return row


def record_claim(
    db: Session,
    *,
    run_id: str,
    statement: str,
    data_kind: str = "estimate",
    hs_scope: str | None = None,
    country_scope: str | None = None,
    confidence: str = "unknown",
    evidence_id: str | None = None,
    knowledge_id: str | None = None,
) -> Claim:
    row = Claim(
        id=f"cl_{secrets.token_hex(8)}",
        run_id=run_id,
        knowledge_id=knowledge_id,
        evidence_id=evidence_id,
        statement=statement[:4000],
        data_kind=data_kind,
        hs_scope=hs_scope,
        country_scope=country_scope,
        confidence=confidence,
        status="active",
        version=1,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return row
