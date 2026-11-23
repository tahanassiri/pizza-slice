"""Persist evidence sources and claims with stable ids and required provenance."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Claim, EvidenceSource
from app.schemas.contracts import Source


def stable_id(prefix: str, *parts: object) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def record_evidence(
    db: Session,
    *,
    run_id: str | None,
    source: Source,
    excerpt: str | None = None,
    product: str | None = None,
    country: str | None = None,
    period: str | None = None,
) -> EvidenceSource:
    evidence_id = stable_id(
        "ev",
        run_id or "",
        source.url,
        product or "",
        country or "",
        period or source.published_at or "",
    )
    existing = db.get(EvidenceSource, evidence_id)
    if existing:
        return existing
    row = EvidenceSource(
        id=evidence_id,
        run_id=run_id,
        url=source.url,
        title=source.title,
        publisher=source.publisher,
        published_at=period or source.published_at,
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
    source_url: str,
    data_kind: str = "estimate",
    hs_scope: str | None = None,
    country_scope: str | None = None,
    product_scope: str | None = None,
    period: str | None = None,
    confidence: str = "unknown",
    evidence_id: str | None = None,
    knowledge_id: str | None = None,
) -> Claim:
    """A claim without a source URL is not stored. Missing period stays null, not a score."""

    url = (source_url or "").strip()
    if not url:
        raise ValueError("claim requires a source_url")
    if not (product_scope or country_scope or hs_scope):
        raise ValueError("claim requires a product, country, or HS scope")
    claim_id = stable_id(
        "cl",
        run_id,
        url,
        statement.strip()[:500],
        product_scope or "",
        country_scope or "",
        period or "",
    )
    existing = db.get(Claim, claim_id)
    if existing:
        return existing
    if evidence_id is None:
        evidence_id = stable_id("ev", run_id, url, product_scope or "", country_scope or "", period or "")
        if db.get(EvidenceSource, evidence_id) is None:
            db.add(
                EvidenceSource(
                    id=evidence_id,
                    run_id=run_id,
                    url=url,
                    title=url[:512],
                    publisher="web",
                    published_at=period,
                    fetched_at=datetime.now(timezone.utc),
                    provider="evidence",
                    reliability_note="claim source",
                )
            )
    row = Claim(
        id=claim_id,
        run_id=run_id,
        knowledge_id=knowledge_id,
        evidence_id=evidence_id,
        statement=statement[:4000],
        data_kind=data_kind,
        hs_scope=hs_scope,
        country_scope=country_scope,
        product_scope=product_scope,
        period=period,
        source_url=url,
        confidence=confidence if confidence in {"high", "medium", "low", "unknown"} else "unknown",
        status="active",
        version=1,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return row


def claims_for_run(db: Session, run_id: str) -> list[Claim]:
    return list(
        db.scalars(select(Claim).where(Claim.run_id == run_id, Claim.status == "active")).all()
    )


def evidence_index_for_run(db: Session, run_id: str) -> dict[str, dict]:
    """Stable evidence ids the model may cite. Missing fields stay null."""

    index: dict[str, dict] = {}
    rows = list(db.scalars(select(Claim).where(Claim.run_id == run_id)).all())
    for row in rows:
        evidence_id = row.evidence_id or row.id
        index[evidence_id] = {
            "id": evidence_id,
            "claim_id": row.id,
            "source_url": row.source_url,
            "period": row.period,
            "product": row.product_scope,
            "country": row.country_scope,
            "hs_scope": row.hs_scope,
            "statement": row.statement,
            "data_scope": "qualitative",
            "data_kind": row.data_kind,
        }
        index[row.id] = index[evidence_id]
    return index


# Keep a token helper available for callers that still need a random id.
def new_token(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"
