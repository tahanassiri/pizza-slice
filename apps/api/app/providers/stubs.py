"""Phase B stubs — no paid/external calls. Honest insufficient/unavailable results."""

from __future__ import annotations

from datetime import datetime, timezone

from app.providers.base import ProviderResult
from app.schemas.contracts import Source


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class StubSearchProvider:
    id = "stub_search"

    def search_markets(self, product: str, origin: str) -> ProviderResult:
        return ProviderResult(
            ok=False,
            message_fa=f"شواهد کافی برای رتبه‌بندی بازار «{product}» از مبدأ {origin} در دسترس نیست (ارائه‌دهنده زنده هنوز وصل نیست).",
            markets=[],
            sources=[
                Source(
                    url="https://example.invalid/phase-b-stub",
                    title="Stub search — Phase B",
                    publisher="NOVA Stub",
                    fetched_at=_now(),
                    provider=self.id,
                    reliability_note="stub — بدون داده تجاری واقعی",
                )
            ],
            error_code="INSUFFICIENT_EVIDENCE",
        )

    def search_buyers(self, product: str, country_code: str) -> ProviderResult:
        return ProviderResult(
            ok=False,
            message_fa=f"خریدار بالقوه‌ای برای {product} در {country_code} یافت نشد (جست‌وجوی زنده در فاز C).",
            buyers=[],
            error_code="NO_BUYERS",
        )


class StubTradeProvider:
    id = "stub_comtrade"

    def trade_stats(self, product: str, origin: str) -> ProviderResult:
        return ProviderResult(
            ok=False,
            message_fa="آمار تجارت زنده در دسترس نیست — Comtrade هنوز پیکربندی/فعال نشده است.",
            sources=[
                Source(
                    url="https://example.invalid/comtrade-stub",
                    title="Trade stub",
                    publisher="NOVA Stub",
                    fetched_at=_now(),
                    provider=self.id,
                    reliability_note="stub — بدون آمار واقعی",
                )
            ],
            error_code="PROVIDER_UNAVAILABLE",
        )


class StubLLMProvider:
    id = "stub_llm"

    def classify_hs(self, product: str, hs_hint: str | None) -> tuple[str | None, str]:
        if hs_hint and hs_hint.strip():
            return hs_hint.strip(), "medium"
        # Honest: no invented definitive HS
        return None, "unknown"
