"""No-cost web search — Wikipedia + DuckDuckGo HTML. No API keys. No paid providers."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import quote, unquote

import httpx

from app.agents.tool_contracts import ToolResult

UA = "NOVA-ExportResearch/1.0 (export intelligence; contact: local-dev)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def search_wikipedia(query: str, *, lang: str = "en", limit: int = 5) -> list[dict]:
    q = quote(query)
    url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=opensearch&search={q}&limit={limit}&namespace=0&format=json"
    )
    with httpx.Client(timeout=12.0, headers={"User-Agent": UA}) as client:
        r = client.get(url)
        r.raise_for_status()
        data = r.json()
    titles = data[1] if isinstance(data, list) and len(data) > 1 else []
    links = data[3] if isinstance(data, list) and len(data) > 3 else []
    out = []
    for title, link in zip(titles, links):
        out.append(
            {
                "url": link,
                "title": str(title),
                "publisher": f"Wikipedia ({lang})",
                "fetched_at": _now(),
                "reliability_note": "دانشنامه عمومی — آمار تجارت قطعی نیست",
                "provider": "wikipedia_free",
            }
        )
    return out


def search_duckduckgo_html(query: str, *, max_results: int = 5) -> list[dict]:
    """Parse DuckDuckGo HTML results — no API key. May fail if blocked; then callers fall back."""
    with httpx.Client(
        timeout=15.0,
        headers={"User-Agent": UA},
        follow_redirects=True,
    ) as client:
        r = client.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
        )
        if r.status_code != 200:
            raise RuntimeError(f"ddg_http_{r.status_code}")
        html = r.text
    # result links: <a rel="nofollow" class="result__a" href="...">
    items: list[dict] = []
    for m in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.I | re.S,
    ):
        href = unquote(m.group(1))
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        # DDG sometimes wraps as //duckduckgo.com/l/?uddg=<url>
        if "uddg=" in href:
            um = re.search(r"uddg=([^&]+)", href)
            if um:
                href = unquote(um.group(1))
        if not href.startswith("http"):
            continue
        items.append(
            {
                "url": href,
                "title": title[:200] or href,
                "publisher": "DuckDuckGo",
                "fetched_at": _now(),
                "reliability_note": "نتیجه جست‌وجوی وب — نیازمند خواندن صفحه و اعتبارسنجی",
                "provider": "duckduckgo_html",
            }
        )
        if len(items) >= max_results:
            break
    return items


def free_web_search(query: str, *, max_results: int = 5, country: str | None = None) -> ToolResult:
    q = (query or "").strip()
    if len(q) < 2:
        return ToolResult(
            tool="search_web",
            ok=False,
            message_fa="پرس‌وجو کوتاه است.",
            error_code="INVALID_QUERY",
        )

    results: list[dict] = []
    errors: list[str] = []

    # 1) Wikipedia (en + fa) — reliable no-cost
    for lang in ("en", "fa"):
        try:
            results.extend(search_wikipedia(q, lang=lang, limit=3))
        except Exception as exc:
            errors.append(f"wiki_{lang}:{type(exc).__name__}")

    # 2) DuckDuckGo HTML — broader discovery
    try:
        ddg_q = q if not country else f"{q} {country}"
        results.extend(search_duckduckgo_html(ddg_q, max_results=max_results))
    except Exception as exc:
        errors.append(f"ddg:{type(exc).__name__}")

    # Dedupe by URL
    seen: set[str] = set()
    deduped: list[dict] = []
    for item in results:
        u = item.get("url") or ""
        if not u or u in seen:
            continue
        seen.add(u)
        deduped.append(item)
        if len(deduped) >= max_results:
            break

    if not deduped:
        return ToolResult(
            tool="search_web",
            ok=False,
            message_fa=(
                "جست‌وجوی رایگان وب نتیجه‌ای نداد "
                f"({'; '.join(errors) or 'no_providers'}). حقایق وب جعل نمی‌شود."
            ),
            error_code="WEB_SEARCH_BLOCKED" if errors else "INSUFFICIENT_EVIDENCE",
            data={"errors": errors, "query": q},
            spent={"search": 1},
        )

    return ToolResult(
        tool="search_web",
        ok=True,
        message_fa=f"{len(deduped)} نتیجه وب رایگان یافت شد.",
        data={"results": deduped, "query": q, "searched_at": _now(), "errors": errors},
        provenance=deduped,
        spent={"search": 1},
    )
