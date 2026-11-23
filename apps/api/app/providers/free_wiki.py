"""Free Wikipedia OpenSearch — product context sources only (no invented markets)."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.providers.base import ProviderResult
from app.schemas.contracts import Source


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FreeWikiSearchProvider:
    id = "wikipedia_free"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def search_product_context(self, product: str) -> ProviderResult:
        q = quote(product)
        url = (
            "https://fa.wikipedia.org/w/api.php"
            f"?action=opensearch&search={q}&limit=3&namespace=0&format=json"
        )
        try:
            with httpx.Client(timeout=self.timeout, headers={"User-Agent": "NOVA-Export/0.1"}) as client:
                r = client.get(url)
                if r.status_code != 200:
                    return ProviderResult(
                        ok=False,
                        message_fa="ویکی‌پدیا پاسخ نداد.",
                        error_code="PROVIDER_UNAVAILABLE",
                    )
                data = r.json()
        except Exception as exc:
            return ProviderResult(
                ok=False,
                message_fa=f"ویکی‌پدیا در دسترس نیست ({type(exc).__name__}).",
                error_code="PROVIDER_UNAVAILABLE",
            )

        titles = data[1] if isinstance(data, list) and len(data) > 1 else []
        links = data[3] if isinstance(data, list) and len(data) > 3 else []
        sources: list[Source] = []
        for title, link in zip(titles, links):
            sources.append(
                Source(
                    url=link,
                    title=str(title),
                    publisher="Wikipedia (fa)",
                    fetched_at=_now(),
                    provider=self.id,
                    reliability_note="منبع عمومی دانشنامه‌ای — جایگزین آمار تجارت نیست",
                )
            )

        if not sources:
            return ProviderResult(
                ok=False,
                message_fa="منبع زمینه‌ای برای محصول یافت نشد.",
                error_code="INSUFFICIENT_EVIDENCE",
            )
        return ProviderResult(
            ok=True,
            message_fa="منابع زمینه‌ای ویکی‌پدیا جمع‌آوری شد",
            sources=sources,
        )

    def search_markets(self, product: str, origin: str) -> ProviderResult:
        # Wiki alone cannot rank export markets honestly
        ctx = self.search_product_context(product)
        return ProviderResult(
            ok=False,
            message_fa=(
                f"ویکی‌پدیا برای «{product}» از مبدأ {origin} رتبه‌بندی بازار نمی‌دهد "
                "(فقط منبع زمینه‌ای)."
            ),
            sources=ctx.sources,
            error_code="INSUFFICIENT_EVIDENCE",
        )

    def search_buyers(self, product: str, country_code: str) -> ProviderResult:
        return ProviderResult(
            ok=False,
            message_fa=f"فهرست خریدار از ویکی‌پدیا برای {product}/{country_code} استخراج نمی‌شود.",
            buyers=[],
            error_code="NO_BUYERS",
        )
