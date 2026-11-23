"""Convert TradeDataResult → Market list for the existing analysis UI."""

from __future__ import annotations

from app.providers.base import ProviderResult
from app.schemas.contracts import Market, MarketMetric, Source
from app.trade_data.types import TradeDataResult
from app.trade_data.wits import ISO3_NAME_FA, ISO3_TO_ISO2


def _sources_from_result(result: TradeDataResult) -> list[Source]:
    out: list[Source] = []
    for s in result.sources or []:
        try:
            out.append(
                Source(
                    url=str(s.get("url") or result.source_url or "https://wits.worldbank.org"),
                    title=str(s.get("title") or result.source_name or "trade source"),
                    publisher=str(s.get("publisher") or result.source_name or "unknown"),
                    published_at=s.get("published_at"),
                    fetched_at=str(s.get("fetched_at") or result.retrieved_at or ""),
                    provider=str(s.get("provider") or result.provider_id or "trade"),
                    reliability_note=str(
                        s.get("reliability_note")
                        or f"quality={result.quality_status}; {result.coverage}"
                    ),
                )
            )
        except Exception:
            continue
    return out


def trade_result_to_markets(
    result: TradeDataResult,
    *,
    product: str,
    origin: str,
    limit: int = 3,
) -> ProviderResult:
    """Rank markets by product-sector import value (share among pool). No fake ranks."""
    sources = _sources_from_result(result)

    if result.quality_status == "unavailable" or not result.records:
        return ProviderResult(
            ok=False,
            message_fa=(
                "آمار تجاری کافی برای رتبه‌بندی بازار در دسترس نیست "
                f"(وضعیت: {result.quality_status})."
            ),
            markets=[],
            sources=sources,
            error_code="INSUFFICIENT_EVIDENCE"
            if result.quality_status == "partial"
            else "PROVIDER_UNAVAILABLE",
            meta={
                "quality_status": result.quality_status,
                "warnings": result.warnings,
                "source_name": result.source_name,
                "reference_year": result.reference_year,
                "hs_code": result.hs_code,
                "hs_revision": result.hs_revision,
                "cache_hit": result.cache_hit,
            },
        )

    numeric = [r for r in result.records if r.value is not None and float(r.value) > 0]
    pool_total = sum(float(r.value or 0) for r in numeric)
    ranked = sorted(numeric, key=lambda r: float(r.value or 0), reverse=True)[:limit]

    if not ranked:
        return ProviderResult(
            ok=False,
            message_fa="ردیفی با مقدار عددی معتبر برای رتبه‌بندی نبود.",
            markets=[],
            sources=sources,
            error_code="INSUFFICIENT_EVIDENCE",
            meta={"quality_status": result.quality_status, "warnings": result.warnings},
        )

    confidence = "medium" if result.quality_status == "verified" else "low"
    markets: list[Market] = []
    for i, rec in enumerate(ranked, start=1):
        iso2 = ISO3_TO_ISO2.get(rec.reporter_iso3, rec.reporter_iso3[:2])
        name_fa = ISO3_NAME_FA.get(rec.reporter_iso3, rec.reporter_iso3)
        year = rec.year
        value = float(rec.value or 0)
        unit = rec.unit or result.unit or "USD"
        share = (value / pool_total * 100.0) if pool_total > 0 else 0.0
        market_sources = [
            s
            for s in sources
            if rec.reporter_iso3 in (s.title or "") or rec.reporter_iso3 in (s.url or "")
        ] or sources[:1]

        is_aggregate = (
            "aggregate" in (rec.product_label or "").lower()
            or "Total" in (rec.product_code or "")
            or "sector" in (rec.product_label or "").lower()
        )

        evidence = [
            (
                f"چرا این کشور: رتبه {i} از نظر ارزش واردات «{rec.product_code}» "
                f"در مجموعهٔ گزارش‌دهندگان بررسی‌شده "
                f"({share:.1f}% از مجموع pool · {value:,.0f} {unit} · سال {year})."
            ),
            (
                f"منبع: {result.source_name} · شاخص: {rec.flow} · "
                f"واحد: {unit} · کیفیت: {result.quality_status}"
            ),
            f"پوشش محصول: {rec.product_label}",
        ]
        if result.hs_code:
            evidence.append(
                f"HS ورودی: {result.hs_code}"
                + (f" (revision {result.hs_revision})" if result.hs_revision else "")
                + f" → گروه WITS: {rec.product_code}"
            )
        if is_aggregate:
            evidence.append(
                "برچسب: دادهٔ گروهی/کل است — نه تجارت دوجانبهٔ دقیق HS6؛ عدد ساختگی نیست."
            )
        if result.quality_status == "partial":
            evidence.append("وضعیت: داده ناقص — رتبه‌بندی با شواهد موجود و برچسب‌خورده.")

        markets.append(
            Market(
                country_code=iso2,
                country_name_fa=name_fa,
                rank=i,
                evidence=evidence,
                opportunities=[
                    "واردات قابل‌توجه در پوشش داده‌شده؛ تعرفه و کانال توزیع را جداگانه بررسی کنید",
                ],
                risks=[
                    *result.warnings[:2],
                    "نبود داده ≠ تقاضای صفر؛ خلأ آماری به‌عنوان فرصت قطعی تفسیر نشود",
                ],
                metrics=[
                    MarketMetric(
                        key="trade_value",
                        label_fa=f"ارزش واردات گروه ({year})",
                        value=f"{value:,.0f}",
                        unit=unit,
                        estimated=bool(rec.estimated),
                    ),
                    MarketMetric(
                        key="pool_share",
                        label_fa="سهم در مجموعه بررسی‌شده",
                        value=f"{share:.1f}",
                        unit="%",
                        estimated=False,
                    ),
                    MarketMetric(
                        key="data_quality",
                        label_fa="کیفیت داده",
                        value=result.quality_status,
                        unit=None,
                        estimated=False,
                    ),
                    MarketMetric(
                        key="source",
                        label_fa="منبع",
                        value=result.source_name,
                        unit=None,
                        estimated=False,
                    ),
                    MarketMetric(
                        key="reference_year",
                        label_fa="سال مرجع",
                        value=str(result.reference_year or year),
                        unit=None,
                        estimated=False,
                    ),
                    MarketMetric(
                        key="wits_product",
                        label_fa="کد گروه WITS",
                        value=rec.product_code or "—",
                        unit=None,
                        estimated=False,
                    ),
                ],
                confidence=confidence,  # type: ignore[arg-type]
                unknowns=[
                    "تعرفه دقیق برای HS کامل",
                    "خریداران تأییدشده",
                    *(["داده HS6 دوجانبه"] if is_aggregate else []),
                ],
                sources=market_sources,
            )
        )

    msg = (
        f"{len(markets)} بازار از {result.source_name} "
        f"(کیفیت: {result.quality_status}، سال: {result.reference_year})"
    )
    return ProviderResult(
        ok=True,
        message_fa=msg,
        markets=markets,
        sources=sources,
        meta={
            "quality_status": result.quality_status,
            "warnings": result.warnings,
            "source_name": result.source_name,
            "source_url": result.source_url,
            "reference_year": result.reference_year,
            "hs_code": result.hs_code,
            "hs_revision": result.hs_revision,
            "coverage": result.coverage,
            "cache_hit": result.cache_hit,
            "product": product,
            "origin": origin,
            "pool_total": pool_total,
            "pool_size": len(numeric),
        },
    )
