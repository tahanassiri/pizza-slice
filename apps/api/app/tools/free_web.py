"""Provider-neutral no-cost search. No API keys and no paid search dependency."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import quote, unquote, urlparse

import httpx

from app.agents.tool_contracts import ToolResult

UA = "NOVA-ExportResearch/1.0 (export intelligence; contact: local-dev)"
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freshness(text: str) -> dict:
    years = _YEAR.findall(text or "")
    if not years:
        return {"published_period": None, "freshness": "unknown"}
    return {"published_period": years[-1], "freshness": "dated"}


def _item(
    *,
    url: str,
    title: str,
    publisher: str,
    provider: str,
    snippet: str = "",
    reliability_note: str,
) -> dict:
    fresh = _freshness(f"{title} {snippet}")
    return {
        "url": url,
        "title": (title or url)[:200],
        "snippet": (snippet or "")[:400],
        "publisher": publisher,
        "fetched_at": _now(),
        "provider": provider,
        "reliability_note": reliability_note,
        **fresh,
    }


def search_wikipedia(query: str, *, lang: str = "en", limit: int = 5) -> list[dict]:
    url = (
        f"https://{lang}.wikipedia.org/w/api.php"
        f"?action=opensearch&search={quote(query)}&limit={limit}&namespace=0&format=json"
    )
    with httpx.Client(timeout=12.0, headers={"User-Agent": UA}, follow_redirects=False) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
    return wikipedia_items(data, lang=lang)


def wikipedia_items(data: object, *, lang: str) -> list[dict]:
    """OpenSearch returns [query, titles, descriptions, urls]. Descriptions are snippets."""

    titles = data[1] if isinstance(data, list) and len(data) > 1 else []
    descriptions = data[2] if isinstance(data, list) and len(data) > 2 else []
    links = data[3] if isinstance(data, list) and len(data) > 3 else []
    if not isinstance(descriptions, list):
        descriptions = []
    items: list[dict] = []
    for index, link in enumerate(links):
        if not str(link).startswith("http"):
            continue
        title = titles[index] if index < len(titles) else link
        snippet = descriptions[index] if index < len(descriptions) else ""
        items.append(
            _item(
                url=str(link),
                title=str(title),
                snippet=str(snippet or ""),
                publisher=f"Wikipedia ({lang})",
                provider="wikipedia_free",
                reliability_note="دانشنامه عمومی — آمار تجارت قطعی نیست",
            )
        )
    return items


def search_duckduckgo_instant(query: str, *, max_results: int = 5) -> list[dict]:
    """DuckDuckGo instant-answer JSON. No key. Distinct from Wikipedia."""

    with httpx.Client(timeout=12.0, headers={"User-Agent": UA}, follow_redirects=False) as client:
        response = client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
        )
        if response.status_code != 200:
            raise RuntimeError(f"ddg_instant_http_{response.status_code}")
        data = response.json()
    items: list[dict] = []
    abstract_url = str(data.get("AbstractURL") or "")
    if abstract_url.startswith("http"):
        items.append(
            _item(
                url=abstract_url,
                title=str(data.get("Heading") or abstract_url),
                snippet=str(data.get("AbstractText") or ""),
                publisher="DuckDuckGo Instant",
                provider="duckduckgo_instant",
                reliability_note="خلاصهٔ جست‌وجوی بدون کلید — نیازمند خواندن منبع",
            )
        )
    topics = data.get("RelatedTopics") or []
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        link = str(topic.get("FirstURL") or "")
        if not link.startswith("http"):
            continue
        items.append(
            _item(
                url=link,
                title=str(topic.get("Text") or link)[:200],
                snippet=str(topic.get("Text") or ""),
                publisher="DuckDuckGo Instant",
                provider="duckduckgo_instant",
                reliability_note="موضوع مرتبط بدون کلید — نیازمند اعتبارسنجی",
            )
        )
        if len(items) >= max_results:
            break
    return items


def search_duckduckgo_html(query: str, *, max_results: int = 5) -> list[dict]:
    with httpx.Client(timeout=15.0, headers={"User-Agent": UA}, follow_redirects=False) as client:
        response = client.post("https://html.duckduckgo.com/html/", data={"q": query})
        if response.status_code != 200:
            raise RuntimeError(f"ddg_http_{response.status_code}")
        html = response.text
    return duckduckgo_html_items(html, max_results=max_results)


def duckduckgo_html_items(html: str, *, max_results: int) -> list[dict]:
    items: list[dict] = []
    for match in re.finditer(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        re.I | re.S,
    ):
        href = unquote(match.group(1))
        title = unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
        if "uddg=" in href:
            wrapped = re.search(r"uddg=([^&]+)", href)
            if wrapped:
                href = unquote(wrapped.group(1))
        if not href.startswith("http"):
            continue
        host = urlparse(href).hostname or ""
        if host.endswith("duckduckgo.com"):
            continue
        window = html[match.end() : match.end() + 2500]
        snippet_match = re.search(
            r'class="result__snippet"[^>]*>(.*?)</(?:a|td|div|span)>',
            window,
            re.I | re.S,
        )
        snippet = ""
        if snippet_match:
            snippet = unescape(re.sub(r"<[^>]+>", " ", snippet_match.group(1)))
            snippet = re.sub(r"\s+", " ", snippet).strip()
        items.append(
            _item(
                url=href,
                title=title or href,
                snippet=snippet,
                publisher="DuckDuckGo HTML",
                provider="duckduckgo_html",
                reliability_note="نتیجه جست‌وجوی وب — نیازمند خواندن صفحه",
            )
        )
        if len(items) >= max_results:
            break
    return items


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme.lower()}://{host}{path}"


def free_web_search(
    query: str,
    *,
    max_results: int = 5,
    country: str | None = None,
    followups: list[str] | None = None,
) -> ToolResult:
    primary = (query or "").strip()
    if len(primary) < 2:
        return ToolResult(
            tool="search_web",
            ok=False,
            message_fa="پرس‌وجو کوتاه است.",
            error_code="INVALID_QUERY",
        )

    planned = [primary]
    for extra in followups or []:
        text = str(extra or "").strip()
        if text and text not in planned:
            planned.append(text)
    planned = planned[:3]
    if country:
        planned = [f"{item} {country}" if country.lower() not in item.lower() else item for item in planned]

    results: list[dict] = []
    errors: list[dict] = []
    providers = (
        ("wikipedia_en", lambda q: search_wikipedia(q, lang="en", limit=3)),
        ("wikipedia_fa", lambda q: search_wikipedia(q, lang="fa", limit=3)),
        ("duckduckgo_instant", lambda q: search_duckduckgo_instant(q, max_results=max_results)),
        ("duckduckgo_html", lambda q: search_duckduckgo_html(q, max_results=max_results)),
    )
    for planned_query in planned:
        for name, fn in providers:
            try:
                results.extend(fn(planned_query))
            except Exception as exc:
                errors.append(
                    {"provider": name, "query": planned_query, "error": type(exc).__name__}
                )

    seen: set[str] = set()
    deduped: list[dict] = []
    for item in results:
        key = _normalize_url(str(item.get("url") or ""))
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= max_results:
            break

    if not deduped:
        return ToolResult(
            tool="search_web",
            ok=False,
            message_fa=(
                "جست‌وجوی رایگان وب نتیجه‌ای نداد ("
                + (
                    "; ".join(f"{err['provider']}:{err['error']}" for err in errors)
                    or "no_providers"
                )
                + "). حقایق وب جعل نمی‌شود."
            ),
            error_code="WEB_SEARCH_BLOCKED" if errors else "INSUFFICIENT_EVIDENCE",
            data={
                "errors": errors,
                "query": primary,
                "followups": planned[1:],
                "searched_at": _now(),
            },
            spent={"search": 1},
        )

    non_wiki = [item for item in deduped if item.get("provider") != "wikipedia_free"]
    return ToolResult(
        tool="search_web",
        ok=True,
        message_fa=f"{len(deduped)} نتیجه وب رایگان یافت شد.",
        data={
            "results": deduped,
            "query": primary,
            "followups": planned[1:],
            "searched_at": _now(),
            "errors": errors,
            "providers": sorted({str(item.get("provider")) for item in deduped}),
            "beyond_wikipedia": bool(non_wiki),
        },
        provenance=deduped,
        spent={"search": 1},
    )
