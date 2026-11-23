"""Optional keyed providers — called ONLY when an encrypted key is configured.
Never logs secrets. Phase C: live-capable; without key → unavailable (no paid call).
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.providers.base import ProviderResult
from app.schemas.contracts import Source


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class KeyedTavilySearch:
    id = "tavily"

    def __init__(self, api_key: str, timeout: float = 15.0):
        self.api_key = api_key
        self.timeout = timeout

    def search_markets(self, product: str, origin: str) -> ProviderResult:
        # Live path when key present — still may return insufficient if no results
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": f"{product} export market from {origin}",
                        "search_depth": "basic",
                        "max_results": 5,
                    },
                )
            if r.status_code == 401:
                return ProviderResult(
                    ok=False,
                    message_fa="کلید Tavily نامعتبر است.",
                    error_code="PROVIDER_UNAVAILABLE",
                )
            if r.status_code == 429:
                return ProviderResult(
                    ok=False,
                    message_fa="سهمیه Tavily تمام شده است.",
                    error_code="RATE_LIMITED",
                )
            if r.status_code != 200:
                return ProviderResult(
                    ok=False,
                    message_fa=f"Tavily خطا داد ({r.status_code}).",
                    error_code="PROVIDER_UNAVAILABLE",
                )
            data = r.json()
            results = data.get("results") or []
            sources = [
                Source(
                    url=item.get("url") or "https://tavily.com",
                    title=item.get("title") or "Tavily result",
                    publisher="Tavily",
                    fetched_at=_now(),
                    provider=self.id,
                    reliability_note="نتیجه جست‌وجوی زنده — رتبه‌بندی بازار جداگانه لازم است",
                )
                for item in results
                if item.get("url")
            ]
            if not sources:
                return ProviderResult(
                    ok=False,
                    message_fa="Tavily نتیجه‌ای برنگرداند.",
                    error_code="INSUFFICIENT_EVIDENCE",
                )
            # Do not invent Market objects from snippets alone in Phase C free path;
            # orchestrator prefers World Bank ranked markets + these as extra sources.
            return ProviderResult(
                ok=True,
                message_fa="منابع جست‌وجوی Tavily دریافت شد",
                sources=sources,
                meta={"raw_count": len(results)},
            )
        except Exception as exc:
            return ProviderResult(
                ok=False,
                message_fa=f"Tavily در دسترس نیست ({type(exc).__name__}).",
                error_code="PROVIDER_UNAVAILABLE",
            )

    def search_buyers(self, product: str, country_code: str) -> ProviderResult:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": f"{product} importer buyer company {country_code}",
                        "search_depth": "basic",
                        "max_results": 5,
                    },
                )
            if r.status_code == 429:
                return ProviderResult(
                    ok=False,
                    message_fa="سهمیه Tavily تمام شده است.",
                    buyers=[],
                    error_code="RATE_LIMITED",
                )
            if r.status_code != 200:
                return ProviderResult(
                    ok=False,
                    message_fa="جست‌وجوی خریدار Tavily ناموفق بود.",
                    buyers=[],
                    error_code="PROVIDER_UNAVAILABLE",
                )
            results = (r.json() or {}).get("results") or []
            # Honest: search hits ≠ verified buyers — return empty with sources
            sources = [
                Source(
                    url=item.get("url") or "https://tavily.com",
                    title=item.get("title") or "search hit",
                    publisher="Tavily",
                    fetched_at=_now(),
                    provider=self.id,
                    reliability_note="نتیجه جست‌وجو — خریدار تأییدشده نیست",
                )
                for item in results
                if item.get("url")
            ]
            return ProviderResult(
                ok=False,
                message_fa="نتایج جست‌وجو برای خریدار یافت شد اما بدون راستی‌آزمایی فهرست خریدار ساخته نمی‌شود.",
                buyers=[],
                sources=sources,
                error_code="NO_BUYERS",
            )
        except Exception as exc:
            return ProviderResult(
                ok=False,
                message_fa=f"جست‌وجوی خریدار ناموفق ({type(exc).__name__}).",
                buyers=[],
                error_code="PROVIDER_UNAVAILABLE",
            )


class KeyedGeminiLLM:
    id = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: float = 20.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def classify_hs(self, product: str, hs_hint: str | None) -> tuple[str | None, str]:
        if hs_hint and hs_hint.strip():
            return hs_hint.strip(), "medium"
        # Live-capable: only call when key present. Keep response constrained.
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        prompt = (
            "Return ONLY a 6-digit HS code guess for this product, or UNKNOWN. "
            f"Product: {product}"
        )
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(
                    url,
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                )
            if r.status_code == 429:
                return None, "unknown"
            if r.status_code != 200:
                return None, "unknown"
            text = (
                r.json()
                .get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            digits = "".join(ch for ch in text if ch.isdigit())[:6]
            if len(digits) == 6:
                return digits, "low"
            return None, "unknown"
        except Exception:
            return None, "unknown"
