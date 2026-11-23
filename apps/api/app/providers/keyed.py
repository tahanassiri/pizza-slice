"""Optional keyed providers — called ONLY when an encrypted key is configured.
Never logs secrets. Phase C: live-capable; without key → unavailable (no paid call).
"""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.providers.base import ProviderResult
from app.schemas.contracts import Buyer, Source


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
        """Return source-backed *candidate* buyers from search hits — no fake contacts."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.api_key,
                        "query": (
                            f"{product} importer OR buyer OR distributor "
                            f"company {country_code}"
                        ),
                        "search_depth": "basic",
                        "max_results": 8,
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
            buyers: list[Buyer] = []
            sources: list[Source] = []
            seen_hosts: set[str] = set()

            for item in results:
                url = (item.get("url") or "").strip()
                title = (item.get("title") or "").strip()
                snippet = (item.get("content") or item.get("snippet") or "").strip()
                if not url or not title:
                    continue
                host = urlparse(url).netloc.lower().removeprefix("www.")
                if not host or host in seen_hosts:
                    continue
                seen_hosts.add(host)

                company = title.split("|")[0].split(" - ")[0].split(" – ")[0].strip()
                company = company[:140] or host
                src = Source(
                    url=url,
                    title=title[:200],
                    publisher="Tavily",
                    fetched_at=_now(),
                    provider=self.id,
                    reliability_note=(
                        "نتیجه جست‌وجوی زنده — خریدار تأییدشده/تماس‌شده نیست؛ نیازمند بررسی انسانی"
                    ),
                )
                sources.append(src)
                fit: list[str] = []
                if snippet:
                    fit.append(snippet[:320])
                fit.append(f"منبع وب: {title[:160]}")
                fit.append(f"کشور هدف جست‌وجو: {country_code} · محصول: {product}")
                buyers.append(
                    Buyer(
                        company_name=company,
                        website=url,
                        country=country_code,
                        business_type="کاندید وب‌جست‌وجو (نقش تأییدنشده)",
                        fit_evidence=fit,
                        contact=None,
                        verification_status="needs_review",
                        sources=[src],
                    )
                )
                if len(buyers) >= 10:
                    break

            if not buyers:
                return ProviderResult(
                    ok=False,
                    message_fa="نتیجهٔ قابل‌استفاده‌ای برای کاندید خریدار پیدا نشد.",
                    buyers=[],
                    sources=sources,
                    error_code="NO_BUYERS",
                )

            return ProviderResult(
                ok=True,
                message_fa=(
                    f"{len(buyers)} کاندید خریدار از نتایج جست‌وجو "
                    "(نیازمند بررسی — بدون تماس ساختگی)."
                ),
                buyers=buyers,
                sources=sources,
                meta={"raw_count": len(results), "candidate_count": len(buyers)},
            )
        except Exception as exc:
            return ProviderResult(
                ok=False,
                message_fa=f"جست‌وجوی خریدار ناموفق ({type(exc).__name__}).",
                buyers=[],
                error_code="PROVIDER_UNAVAILABLE",
            )


def _digits_hs(text: str) -> tuple[str | None, str]:
    digits = "".join(ch for ch in text if ch.isdigit())[:6]
    if len(digits) == 6:
        return digits, "low"
    return None, "unknown"


_HS_PROMPT = (
    "Return ONLY a 6-digit HS code guess for this product, or UNKNOWN. Product: {product}"
)


class KeyedGeminiLLM:
    id = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-3.8-flash", timeout: float = 20.0):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def classify_hs(self, product: str, hs_hint: str | None) -> tuple[str | None, str]:
        if hs_hint and hs_hint.strip():
            return hs_hint.strip(), "medium"
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        prompt = _HS_PROMPT.format(product=product)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(
                    url,
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                )
            if r.status_code == 429 or r.status_code != 200:
                return None, "unknown"
            text = (
                r.json()
                .get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            return _digits_hs(text)
        except Exception:
            return None, "unknown"


class KeyedOpenAICompatLLM:
    """OpenAI Chat Completions — also used for DeepSeek (compatible base URL)."""

    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        provider_id: str = "openai",
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 30.0,
    ):
        self.id = provider_id
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def classify_hs(self, product: str, hs_hint: str | None) -> tuple[str | None, str]:
        if hs_hint and hs_hint.strip():
            return hs_hint.strip(), "medium"
        prompt = _HS_PROMPT.format(product=product)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                r = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0,
                        "max_tokens": 32,
                    },
                )
            if r.status_code == 429 or r.status_code != 200:
                return None, "unknown"
            text = (
                (r.json().get("choices") or [{}])[0]
                .get("message", {})
                .get("content", "")
                or ""
            )
            return _digits_hs(text)
        except Exception:
            return None, "unknown"


def build_llm(provider: str, api_key: str, model: str):
    if provider == "google":
        return KeyedGeminiLLM(api_key, model=model)
    if provider == "openai":
        return KeyedOpenAICompatLLM(
            api_key, model, provider_id="openai", base_url="https://api.openai.com/v1"
        )
    if provider == "deepseek":
        return KeyedOpenAICompatLLM(
            api_key,
            model,
            provider_id="deepseek",
            base_url="https://api.deepseek.com/v1",
        )
    return KeyedGeminiLLM(api_key, model=model)
