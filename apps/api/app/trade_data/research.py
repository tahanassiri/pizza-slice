"""Deep research adapter — uses existing search APIs only.

Collects and validates findings; never invents trade statistics.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.trade_data.types import TradeDataQuery, TradeDataResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ResearchTradeProvider:
    """Wraps Tavily / Wiki / Exa-style search providers already in the registry."""

    id = "research"
    display_name = "Deep Research (existing search APIs)"

    def __init__(self, search_provider: object | None = None):
        self.search = search_provider

    def is_available(self) -> bool:
        return self.search is not None

    def supports(self, query: TradeDataQuery) -> bool:
        return self.is_available()

    def fetch(self, query: TradeDataQuery) -> TradeDataResult:
        if not self.search:
            return TradeDataResult(
                source_name=self.display_name,
                retrieved_at=_now(),
                quality_status="unavailable",
                warnings=["هیچ ارائه‌دهنده جست‌وجوی تحقیقاتی پیکربندی نشده است."],
                provider_id=self.id,
                coverage="none",
            )

        product = query.product_hint or query.hs_code or "product"
        origin = query.origin or "ایران"
        sources: list[dict] = []
        warnings: list[str] = [
            "تحقیق تکمیلی فقط منابع را جمع می‌کند؛ عدد تجارت ساختگی تولید نمی‌شود.",
        ]

        # Prefer market search if available
        if hasattr(self.search, "search_markets"):
            try:
                result = self.search.search_markets(product, origin)
                for s in result.sources or []:
                    sources.append(s.model_dump() if hasattr(s, "model_dump") else dict(s))
                if not result.ok and result.message_fa:
                    warnings.append(result.message_fa)
            except Exception as exc:
                warnings.append(f"جست‌وجوی بازار ناموفق: {type(exc).__name__}")

        if hasattr(self.search, "search_product_context"):
            try:
                ctx = self.search.search_product_context(product)
                for s in ctx.sources or []:
                    sources.append(s.model_dump() if hasattr(s, "model_dump") else dict(s))
            except Exception as exc:
                warnings.append(f"زمینه محصول ناموفق: {type(exc).__name__}")

        # Dedupe by URL
        seen: set[str] = set()
        deduped: list[dict] = []
        for s in sources:
            url = str(s.get("url") or "")
            if not url or url in seen:
                continue
            seen.add(url)
            deduped.append(s)

        if not deduped:
            return TradeDataResult(
                records=[],
                source_name=self.display_name,
                source_url="",
                retrieved_at=_now(),
                hs_code=query.hs_code,
                hs_revision=query.hs_revision,
                coverage="none",
                quality_status="unavailable",
                warnings=warnings + ["منبع معتبری با عدد قابل‌استناد یافت نشد."],
                sources=[],
                provider_id=self.id,
            )

        return TradeDataResult(
            records=[],  # intentional — no fabricated numeric trade rows
            source_name=self.display_name,
            source_url=deduped[0].get("url") or "",
            retrieved_at=_now(),
            hs_code=query.hs_code,
            hs_revision=query.hs_revision,
            unit="n/a",
            currency="n/a",
            coverage=f"{len(deduped)} source URLs (qualitative)",
            quality_status="partial",
            warnings=warnings
            + [
                "منابع تحقیقاتی پیوست شد؛ بدون ردیف عددی تأییدشده از WITS/آمار رسمی "
                "رتبه‌بندی قطعی انجام نمی‌شود."
            ],
            sources=deduped,
            provider_id=self.id,
        )
