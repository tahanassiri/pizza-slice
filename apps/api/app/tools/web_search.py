"""Web search tool adapter over registry search providers."""

from __future__ import annotations

from datetime import datetime, timezone

from app.agents.tool_contracts import ToolResult


def search_web(
    search_provider: object,
    *,
    query: str,
    country: str | None = None,
    max_results: int = 5,
) -> ToolResult:
    q = query.strip()
    if len(q) < 2:
        return ToolResult(
            tool="search_web",
            ok=False,
            message_fa="پرس‌وجو کوتاه است.",
            error_code="INVALID_QUERY",
        )

    # Prefer product context / markets search APIs already on providers
    sources = []
    try:
        if country and hasattr(search_provider, "search_buyers"):
            # reuse as generic search only when explicitly buyer-oriented query
            pass
        if hasattr(search_provider, "search_markets"):
            result = search_provider.search_markets(q, country or "ایران")
            sources = list(result.sources or [])
            if not result.ok and not sources:
                return ToolResult(
                    tool="search_web",
                    ok=False,
                    message_fa=result.message_fa or "جست‌وجو نتیجه‌ای نداشت.",
                    error_code=result.error_code or "INSUFFICIENT_EVIDENCE",
                    spent={"search": 1},
                )
        elif hasattr(search_provider, "search_product_context"):
            ctx = search_provider.search_product_context(q)
            sources = list(ctx.sources or [])
        else:
            return ToolResult(
                tool="search_web",
                ok=False,
                message_fa="ارائه‌دهنده جست‌وجو در دسترس نیست.",
                error_code="PROVIDER_UNAVAILABLE",
            )
    except Exception as exc:
        return ToolResult(
            tool="search_web",
            ok=False,
            message_fa=f"جست‌وجو ناموفق ({type(exc).__name__}).",
            error_code="PROVIDER_UNAVAILABLE",
            spent={"search": 1},
        )

    items = [
        {
            "url": s.url,
            "title": s.title,
            "publisher": s.publisher,
            "fetched_at": s.fetched_at,
            "reliability_note": s.reliability_note,
        }
        for s in sources[:max_results]
    ]
    return ToolResult(
        tool="search_web",
        ok=bool(items),
        message_fa=f"{len(items)} منبع وب یافت شد." if items else "منبعی یافت نشد.",
        data={"results": items, "query": q, "searched_at": datetime.now(timezone.utc).isoformat()},
        provenance=items,
        error_code=None if items else "INSUFFICIENT_EVIDENCE",
        spent={"search": 1},
    )
