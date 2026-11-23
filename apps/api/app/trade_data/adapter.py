"""Bridge TradeDataService → legacy TradeProvider interface used by orchestrator."""

from __future__ import annotations

from app.providers.base import ProviderResult
from app.schemas.contracts import Source
from app.trade_data.service import TradeDataService
from app.trade_data.to_markets import trade_result_to_markets
from app.trade_data.types import TradeDataQuery, TradeDataResult


class TradeDataProviderAdapter:
    """Exposes build_markets / trade_stats for orchestrator compatibility."""

    id = "trade_data_service"

    def __init__(self, service: TradeDataService):
        self.service = service
        self._last: ProviderResult | None = None

    def _fetch(self, product: str, origin: str, hs_code: str | None) -> TradeDataResult:
        query = TradeDataQuery(
            hs_code=hs_code,
            hs_revision="HS" if hs_code else None,
            flow="import",
            product_hint=product,
            origin=origin,
        )
        return self.service.fetch(query)

    def trade_stats(self, product: str, origin: str, hs_code: str | None = None) -> ProviderResult:
        return self._stats_result(self._fetch(product, origin, hs_code))

    @staticmethod
    def _stats_result(result: TradeDataResult) -> ProviderResult:
        sources = []
        for s in result.sources or []:
            try:
                sources.append(
                    Source(
                        url=str(s.get("url") or result.source_url or ""),
                        title=str(s.get("title") or result.source_name),
                        publisher=str(s.get("publisher") or result.source_name),
                        published_at=s.get("published_at"),
                        fetched_at=str(s.get("fetched_at") or result.retrieved_at),
                        provider=str(s.get("provider") or result.provider_id),
                        reliability_note=str(
                            s.get("reliability_note") or f"quality={result.quality_status}"
                        ),
                    )
                )
            except Exception:
                continue
        ok = result.quality_status in {"verified", "partial"} and (
            bool(result.records) or bool(sources)
        )
        return ProviderResult(
            ok=ok,
            message_fa=(
                f"آمار تجارت از {result.source_name or 'TradeData'} "
                f"(کیفیت: {result.quality_status})"
            ),
            sources=sources,
            error_code=None if ok else "PROVIDER_UNAVAILABLE",
            meta={
                "quality_status": result.quality_status,
                "warnings": result.warnings,
                "reference_year": result.reference_year,
                "coverage": result.coverage,
                "cache_hit": result.cache_hit,
                "records": len(result.records),
            },
        )

    def build_markets(
        self, product: str, origin: str, hs_code: str | None = None
    ) -> ProviderResult:
        return self._markets_result(self._fetch(product, origin, hs_code), product, origin)

    def trade_stats_and_markets(
        self, product: str, origin: str, hs_code: str | None = None
    ) -> tuple[ProviderResult, ProviderResult]:
        result = self._fetch(product, origin, hs_code)
        return self._stats_result(result), self._markets_result(result, product, origin)

    def _markets_result(self, result: TradeDataResult, product: str, origin: str) -> ProviderResult:
        out = trade_result_to_markets(result, product=product, origin=origin)
        self._last = out
        return out
