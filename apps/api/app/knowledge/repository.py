"""Public knowledge store with privacy isolation."""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.knowledge.freshness import is_stale, stale_after_for_kind
from app.models.entities import KnowledgeItem


def normalize_product(name: str) -> str:
    text = (name or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text[:256]


def canonical_key(
    *,
    kind: str,
    product: str | None = None,
    hs6: str | None = None,
    origin: str | None = None,
    destination: str | None = None,
    metric: str | None = None,
    period: str | None = None,
) -> str:
    parts = [
        kind,
        normalize_product(product or ""),
        (hs6 or "").strip(),
        (origin or "").strip(),
        (destination or "").strip().upper(),
        (metric or "").strip(),
        (period or "").strip(),
    ]
    return "|".join(parts)


class KnowledgeRepository:
    def __init__(self, db: Session):
        self.db = db

    def lookup_public(
        self,
        *,
        kind: str,
        product: str | None = None,
        hs6: str | None = None,
        origin: str | None = None,
        destination: str | None = None,
        metric: str | None = None,
        period: str | None = None,
    ) -> tuple[KnowledgeItem | None, str]:
        """Return (item, status) where status is hit|stale|miss.

        Never returns private-scope rows.
        """
        key = canonical_key(
            kind=kind,
            product=product,
            hs6=hs6,
            origin=origin,
            destination=destination,
            metric=metric,
            period=period,
        )
        rows = list(
            self.db.scalars(
                select(KnowledgeItem)
                .where(
                    KnowledgeItem.canonical_key == key,
                    KnowledgeItem.scope == "public",
                    KnowledgeItem.status == "active",
                )
                .order_by(KnowledgeItem.version.desc())
            )
        )
        if not rows:
            return None, "miss"
        item = rows[0]
        if is_stale(item.stale_after):
            return item, "stale"
        return item, "hit"

    def save_public(
        self,
        *,
        kind: str,
        payload: dict,
        product: str | None = None,
        hs6: str | None = None,
        origin: str | None = None,
        destination: str | None = None,
        metric: str | None = None,
        period: str | None = None,
        confidence: str = "low",
        origin_run_id: str | None = None,
        published_period: str | None = None,
    ) -> KnowledgeItem:
        # Refuse private financial keys
        forbidden = {"target_sell_price", "fx_rate", "user_contact", "password", "api_key"}
        blob = json.dumps(payload, ensure_ascii=False)
        for bad in forbidden:
            if bad in blob.lower():
                raise ValueError(f"refusing to store private field marker: {bad}")

        key = canonical_key(
            kind=kind,
            product=product,
            hs6=hs6,
            origin=origin,
            destination=destination,
            metric=metric,
            period=period,
        )
        existing = list(
            self.db.scalars(
                select(KnowledgeItem)
                .where(KnowledgeItem.canonical_key == key)
                .order_by(KnowledgeItem.version.desc())
            )
        )
        version = (existing[0].version + 1) if existing else 1
        now = datetime.now(timezone.utc)
        item = KnowledgeItem(
            id=f"kn_{secrets.token_hex(8)}",
            canonical_key=key,
            kind=kind,
            scope="public",
            product_normalized=normalize_product(product) if product else None,
            hs6=hs6,
            origin=origin,
            destination=destination,
            payload_json=blob,
            confidence=confidence,
            fetched_at=now,
            published_period=published_period or period,
            last_verified_at=now,
            stale_after=stale_after_for_kind(kind, now),
            version=version,
            origin_run_id=origin_run_id,
            status="active",
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item
