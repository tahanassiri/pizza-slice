"""TradeDataService — single entry for market modules.

Fallback order: WITS → existing research APIs → optional configured providers.
Never invent numbers; return partial/unavailable when evidence is weak.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.trade_data.comtrade_optional import ComtradePublicProvider
from app.trade_data.research import ResearchTradeProvider
from app.trade_data.types import TradeDataProvider, TradeDataQuery, TradeDataResult
from app.trade_data.wits import WitsTradeProvider


@dataclass
class TradeDataService:
    wits: WitsTradeProvider = field(default_factory=WitsTradeProvider)
    research: ResearchTradeProvider = field(default_factory=ResearchTradeProvider)
    comtrade_public: ComtradePublicProvider = field(
        default_factory=lambda: ComtradePublicProvider(enabled=False)
    )
    # Optional future: OEC/BACI when keyed — not required for this release
    extras: list[TradeDataProvider] = field(default_factory=list)

    def providers_in_order(self) -> list[TradeDataProvider]:
        ordered: list[TradeDataProvider] = [self.wits, self.research]
        if self.comtrade_public.is_available():
            # Optional — after research; never mandatory
            ordered.append(self.comtrade_public)
        ordered.extend(self.extras)
        return ordered

    def fetch(self, query: TradeDataQuery) -> TradeDataResult:
        """Try providers in order; prefer first result with numeric records.

        If WITS returns verified/partial with records → use it (optionally merge
        research sources). If WITS unavailable → try research, then optional.
        Never fabricate values when all fail.
        """
        attempts: list[TradeDataResult] = []
        research_sources: list[dict] = []

        for provider in self.providers_in_order():
            if not provider.is_available() or not provider.supports(query):
                continue
            try:
                result = provider.fetch(query)
            except Exception as exc:
                attempts.append(
                    TradeDataResult(
                        source_name=getattr(provider, "display_name", provider.id),
                        quality_status="unavailable",
                        warnings=[f"{provider.id} exception: {type(exc).__name__}"],
                        provider_id=provider.id,
                    )
                )
                continue
            attempts.append(result)

            if provider.id == "research":
                research_sources.extend(result.sources or [])
                # Research alone never upgrades to verified numeric ranking
                continue

            if result.records and result.quality_status in {"verified", "partial"}:
                # Attach research URLs as supplementary provenance when available
                if research_sources:
                    seen = {s.get("url") for s in result.sources}
                    for s in research_sources:
                        if s.get("url") and s.get("url") not in seen:
                            result.sources.append(s)
                    result.warnings.append(
                        "منابع تحقیق تکمیلی به پرووننس پیوست شد (بدون تغییر اعداد WITS)."
                    )
                result.warnings.append(
                    f"منبع فعال: {result.source_name} ({result.provider_id})"
                )
                return result

            if result.records and result.quality_status == "unavailable":
                # odd case — keep trying
                continue

        # Prefer any attempt that at least returned research sources
        for result in attempts:
            if result.sources and result.quality_status == "partial":
                result.warnings.append(
                    "داده عددی ساختاریافته در دسترس نبود؛ فقط منابع تحقیقاتی برگردانده شد."
                )
                return result

        warnings = ["هیچ منبع trade data باکیفیتی در دسترس نبود."]
        for a in attempts:
            warnings.extend(a.warnings[:2])
        return TradeDataResult(
            records=[],
            source_name="TradeDataService",
            retrieved_at=attempts[-1].retrieved_at if attempts else "",
            hs_code=query.hs_code,
            hs_revision=query.hs_revision,
            coverage="none",
            quality_status="unavailable",
            warnings=warnings,
            sources=[],
            provider_id="trade_data_service",
        )

    def status_snapshot(self) -> list[dict]:
        """Admin-facing source status (no secrets)."""
        rows = []
        for p in [self.wits, self.research, self.comtrade_public, *self.extras]:
            available = False
            try:
                available = bool(p.is_available())
            except Exception:
                available = False
            status = "active" if available else "inactive"
            if p.id == "comtrade_public" and not getattr(p, "enabled", False):
                status = "inactive"
            rows.append(
                {
                    "id": p.id,
                    "name": getattr(p, "display_name", p.id),
                    "status": status,
                    "optional": p.id in {"comtrade_public"},
                }
            )
        return rows
