"""Free World Bank API — no API key. Honest low-confidence market candidates."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.providers.base import ProviderResult
from app.schemas.contracts import Market, MarketMetric, Source

# Common destinations for Iran-origin goods (ISO2 display, WB path code, FA name)
# World Bank accepts ISO2 or ISO3 in /country/{code}
CANDIDATES: list[tuple[str, str, str]] = [
    ("AE", "AE", "امارات متحده عربی"),
    ("TR", "TR", "ترکیه"),
    ("IQ", "IQ", "عراق"),
    ("CN", "CN", "چین"),
    ("DE", "DE", "آلمان"),
    ("IN", "IN", "هند"),
    ("RU", "RU", "روسیه"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FreeWorldBankTradeProvider:
    id = "worldbank_free"

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    def _fetch_rows(self) -> tuple[list[tuple[str, str, float, str, str]], list[Source], int]:
        """Returns ranked tuples (iso2, name_fa, value, year, url), sources, error_count."""
        indicator = "NE.IMP.GNFS.CD"
        ranked: list[tuple[str, str, float, str, str]] = []
        sources: list[Source] = []
        errors = 0
        with httpx.Client(timeout=self.timeout) as client:
            for iso2, wb, name_fa in CANDIDATES:
                url = (
                    f"https://api.worldbank.org/v2/country/{wb}/indicator/{indicator}"
                    f"?format=json&per_page=5&MRV=1"
                )
                try:
                    r = client.get(url)
                    if r.status_code != 200:
                        errors += 1
                        continue
                    payload = r.json()
                    if not (isinstance(payload, list) and len(payload) > 1 and payload[1]):
                        continue
                    entry = payload[1][0]
                    if entry.get("value") is None:
                        continue
                    year = str(entry.get("date") or "")
                    value = float(entry["value"])
                    ranked.append((iso2, name_fa, value, year, url))
                    sources.append(
                        Source(
                            url=url,
                            title=f"World Bank {indicator} — {wb}",
                            publisher="World Bank",
                            published_at=year or None,
                            fetched_at=_now(),
                            provider=self.id,
                            reliability_note="آمار کلان واردات کالا/خدمات — نه HS اختصاصی محصول",
                        )
                    )
                except Exception:
                    errors += 1
        ranked.sort(key=lambda x: x[2], reverse=True)
        return ranked, sources, errors

    def trade_stats(self, product: str, origin: str) -> ProviderResult:
        try:
            ranked, sources, errors = self._fetch_rows()
        except Exception as exc:
            return ProviderResult(
                ok=False,
                message_fa=f"سرویس World Bank در دسترس نیست: {type(exc).__name__}",
                error_code="PROVIDER_UNAVAILABLE",
            )
        if not ranked:
            return ProviderResult(
                ok=False,
                message_fa="آمار تجارت آزاد دریافت نشد یا خالی بود.",
                sources=sources,
                error_code="PROVIDER_UNAVAILABLE" if errors else "INSUFFICIENT_EVIDENCE",
            )
        return ProviderResult(
            ok=True,
            message_fa=f"آمار کلان واردات از World Bank برای مقایسه اولیه «{product}» از مبدأ {origin}",
            sources=sources,
            meta={"indicator": "NE.IMP.GNFS.CD", "rows": len(ranked)},
        )

    def build_markets(self, product: str, origin: str) -> ProviderResult:
        try:
            ranked, sources, errors = self._fetch_rows()
        except Exception as exc:
            return ProviderResult(
                ok=False,
                message_fa=f"خطا در ساخت بازار از World Bank: {type(exc).__name__}",
                error_code="PROVIDER_UNAVAILABLE",
            )
        top = ranked[:3]
        if not top:
            return ProviderResult(
                ok=False,
                message_fa="شواهد کافی برای رتبه‌بندی بازار از داده آزاد به‌دست نیامد.",
                sources=sources,
                error_code="PROVIDER_UNAVAILABLE" if errors else "INSUFFICIENT_EVIDENCE",
            )

        markets: list[Market] = []
        for i, (iso2, name_fa, value, year, url) in enumerate(top, start=1):
            market_sources = [s for s in sources if s.url == url] or sources[:1]
            markets.append(
                Market(
                    country_code=iso2,
                    country_name_fa=name_fa,
                    rank=i,
                    evidence=[
                        f"واردات کلان کالا/خدمات ({year or 'آخرین سال'}): حدود {value:,.0f} USD (World Bank)",
                        f"رتبه‌بندی اولیه برای محصول «{product}» بر اساس حجم واردات کشور مقصد — نه داده HS اختصاصی",
                    ],
                    opportunities=[
                        "بازار با واردات کلان؛ نیاز به اعتبارسنجی تعرفه و کانال توزیع",
                    ],
                    risks=[
                        "داده World Bank محصول‌محور (HS) نیست",
                        "بدون جست‌وجوی تخصصی، تناسب محصول قطعی نیست",
                    ],
                    metrics=[
                        MarketMetric(
                            key="imports_usd",
                            label_fa="واردات کلان (USD)",
                            value=f"{value:,.0f}",
                            unit="USD",
                            estimated=False,
                        )
                    ],
                    confidence="low",
                    unknowns=[
                        "تعرفه دقیق HS",
                        "تقاضای محصول‌محور",
                        "رقبای مستقیم",
                    ],
                    sources=market_sources,
                )
            )

        return ProviderResult(
            ok=True,
            message_fa="سه بازار کاندید با داده آزاد World Bank (اطمینان پایین — بدون HS اختصاصی)",
            markets=markets,
            sources=sources,
        )
