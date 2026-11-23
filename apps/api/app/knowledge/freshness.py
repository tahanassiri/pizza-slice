"""TTL guidance by knowledge kind — admin-tunable defaults."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

# days until stale_after
TTL_DAYS: dict[str, int] = {
    "product_identity": 180,
    "market_stats": 90,
    "regulation": 30,
    "logistics": 14,
    "insurance_fx": 7,
    "company": 45,
    "buyer": 45,
    "cost_estimate": 14,
    "analysis": 60,
}


def stale_after_for_kind(kind: str, fetched_at: datetime | None = None) -> datetime:
    base = fetched_at or datetime.now(timezone.utc)
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    days = TTL_DAYS.get(kind, 60)
    return base + timedelta(days=days)


def is_stale(stale_after: datetime | None, *, now: datetime | None = None) -> bool:
    if stale_after is None:
        return False
    now = now or datetime.now(timezone.utc)
    if stale_after.tzinfo is None:
        stale_after = stale_after.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now >= stale_after
