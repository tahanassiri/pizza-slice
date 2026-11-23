"""Official / free trade stats tool — labels sector vs HS clearly."""

from __future__ import annotations

from app.agents.tool_contracts import ToolResult
from app.trade_data.types import TradeDataQuery


def get_trade_stats(
    trade_service: object | None,
    *,
    product: str,
    origin: str,
    hs6: str | None = None,
) -> ToolResult:
    if trade_service is None:
        return ToolResult(
            tool="get_trade_stats",
            ok=False,
            message_fa="سرویس آمار تجارت در دسترس نیست.",
            error_code="PROVIDER_UNAVAILABLE",
        )
    query = TradeDataQuery(
        product_hint=product,
        origin=origin,
        hs_code=hs6,
        flow="import",
    )
    try:
        result = trade_service.resolve(query) if hasattr(trade_service, "resolve") else None
        if result is None and hasattr(trade_service, "fetch"):
            result = trade_service.fetch(query)
    except Exception as exc:
        return ToolResult(
            tool="get_trade_stats",
            ok=False,
            message_fa=f"آمار تجارت ناموفق ({type(exc).__name__}).",
            error_code="PROVIDER_UNAVAILABLE",
        )

    if result is None:
        return ToolResult(
            tool="get_trade_stats",
            ok=False,
            message_fa="آمار تجارت برنگشت.",
            error_code="PROVIDER_UNAVAILABLE",
        )

    # Infer data scope honesty
    coverage = (result.coverage or "").lower()
    data_scope = "sector"
    if "hs6" in coverage or (result.hs_code and "bilateral" in coverage):
        data_scope = "hs6"
    elif "total" in coverage:
        data_scope = "total"

    records = [
        {
            "reporter_iso3": r.reporter_iso3,
            "partner_iso3": r.partner_iso3,
            "year": r.year,
            "value": r.value,
            "unit": r.unit,
            "product_code": r.product_code,
            "product_label": r.product_label,
            "flow": r.flow,
            "estimated": r.estimated,
        }
        for r in (result.records or [])
    ]
    return ToolResult(
        tool="get_trade_stats",
        ok=result.quality_status != "unavailable" and bool(records),
        message_fa=(
            f"آمار {result.source_name} دریافت شد "
            f"(کیفیت={result.quality_status}، دامنه={data_scope})."
        ),
        data={
            "quality_status": result.quality_status,
            "data_scope": data_scope,
            "source_name": result.source_name,
            "source_url": result.source_url,
            "reference_year": result.reference_year,
            "hs_code": result.hs_code,
            "warnings": result.warnings,
            "records": records,
            "cache_hit": result.cache_hit,
            "coverage": result.coverage,
            "provider_id": result.provider_id,
        },
        provenance=[
            {
                "url": result.source_url or "",
                "publisher": result.source_name,
                "fetched_at": result.retrieved_at,
                "data_scope": data_scope,
            }
        ],
        error_code=None
        if result.quality_status != "unavailable" and records
        else "INSUFFICIENT_EVIDENCE",
    )
