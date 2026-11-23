"""Optional UN Comtrade public preview — OFF by default, no mandatory key.

Public preview limits: ~500 records, constrained query dimensions.
Never use capped/incomplete preview output as a global ranking basis alone.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.trade_data.cache import TtlCache, trade_breaker, trade_cache
from app.trade_data.types import TradeDataQuery, TradeDataResult, TradeRecord
from app.trade_data.wits import ISO2_TO_ISO3

# Comtrade reporter numeric codes (subset)
ISO3_TO_COMTRADE: dict[str, int] = {
    "ARE": 784,
    "TUR": 792,
    "IRQ": 368,
    "CHN": 156,
    "DEU": 276,
    "IND": 356,
    "RUS": 643,
}

PUBLIC_PREVIEW = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
COMTRADE_DOCS = "https://comtrade.un.org/en/api-docs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ComtradePublicProvider:
    id = "comtrade_public"
    display_name = "UN Comtrade Public Preview"

    def __init__(self, enabled: bool = False, timeout: float = 20.0, cache: TtlCache | None = None):
        self.enabled = enabled
        self.timeout = timeout
        self.cache = cache or trade_cache

    def is_available(self) -> bool:
        return self.enabled and trade_breaker.allow(self.id)

    def supports(self, query: TradeDataQuery) -> bool:
        return self.is_available() and bool(query.hs_code)

    def fetch(self, query: TradeDataQuery) -> TradeDataResult:
        if not self.is_available():
            return TradeDataResult(
                source_name=self.display_name,
                source_url=COMTRADE_DOCS,
                retrieved_at=_now(),
                quality_status="unavailable",
                warnings=["Comtrade public preview غیرفعال است (پیش‌فرض)."],
                provider_id=self.id,
                coverage="none",
            )
        if not query.hs_code:
            return TradeDataResult(
                source_name=self.display_name,
                source_url=COMTRADE_DOCS,
                retrieved_at=_now(),
                quality_status="unavailable",
                warnings=["بدون کد HS، پیش‌نمایش Comtrade فراخوانی نمی‌شود."],
                provider_id=self.id,
                coverage="none",
            )

        year = max(query.years) if query.years else datetime.now(timezone.utc).year - 2
        hs = "".join(ch for ch in query.hs_code if ch.isdigit())[:6]
        reporters = list(query.partners) if query.partners else list(ISO3_TO_COMTRADE.keys())
        flow = "M" if query.flow == "import" else "X"

        records: list[TradeRecord] = []
        sources: list[dict] = []
        warnings = [
            "پیش‌نمایش عمومی Comtrade سقف ~۵۰۰ رکورد دارد؛ خروجی ناقص مبنای رتبه‌بندی سراسری نیست.",
        ]

        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            for iso3 in reporters[:5]:  # keep queries small
                code = ISO3_TO_COMTRADE.get(iso3)
                if code is None:
                    continue
                params = {
                    "reporterCode": code,
                    "period": year,
                    "partnerCode": 0,
                    "cmdCode": hs,
                    "flowCode": flow,
                    "maxRecords": 5,
                }
                cache_key = TtlCache.make_key("comtrade_pub", params)
                cached = self.cache.get(cache_key)
                if cached is not None:
                    rows = cached
                    url = PUBLIC_PREVIEW
                else:
                    try:
                        r = client.get(PUBLIC_PREVIEW, params=params)
                    except Exception:
                        trade_breaker.record_failure(self.id)
                        continue
                    if r.status_code != 200:
                        trade_breaker.record_failure(self.id)
                        continue
                    payload = r.json()
                    rows = payload.get("data") or []
                    self.cache.set(cache_key, rows)
                    trade_breaker.record_success(self.id)
                    url = str(r.url)

                for row in rows:
                    primary = row.get("primaryValue")
                    if primary is None:
                        continue
                    try:
                        value = float(primary)
                    except (TypeError, ValueError):
                        continue
                    records.append(
                        TradeRecord(
                            reporter_iso3=iso3,
                            partner_iso3="WLD",
                            year=int(row.get("refYear") or year),
                            flow=query.flow,
                            value=value,
                            unit="USD",
                            currency="USD",
                            product_code=str(row.get("cmdCode") or hs),
                            product_label=f"HS {hs} (Comtrade preview)",
                            hs_code=hs,
                            hs_revision=str(row.get("classificationCode") or query.hs_revision or ""),
                            estimated=False,
                        )
                    )
                sources.append(
                    {
                        "url": url,
                        "title": f"Comtrade preview HS {hs} — {iso3} {year}",
                        "publisher": "UN Comtrade",
                        "reporter_iso3": iso3,
                        "reference_year": year,
                        "fetched_at": _now(),
                        "provider": self.id,
                        "reliability_note": "Public preview — capped / optional",
                    }
                )

        if not records:
            return TradeDataResult(
                records=[],
                source_name=self.display_name,
                source_url=COMTRADE_DOCS,
                retrieved_at=_now(),
                reference_year=year,
                hs_code=hs,
                hs_revision=query.hs_revision,
                coverage="none",
                quality_status="unavailable",
                warnings=warnings + ["پیش‌نمایش Comtrade ردیف قابل‌استفاده‌ای برنگرداند."],
                sources=sources,
                provider_id=self.id,
            )

        return TradeDataResult(
            records=records,
            source_name=self.display_name,
            source_url=COMTRADE_DOCS,
            retrieved_at=_now(),
            reference_year=year,
            hs_code=hs,
            hs_revision=query.hs_revision or records[0].hs_revision,
            unit="USD",
            currency="USD",
            coverage=f"{len(records)} preview rows (capped)",
            quality_status="partial",
            warnings=warnings,
            sources=sources,
            provider_id=self.id,
        )


# Silence unused import lint if ISO2 map re-exported for callers
_ = ISO2_TO_ISO3
