from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.schemas.contracts import Buyer, Market, Source


@dataclass
class ProviderResult:
    ok: bool
    message_fa: str
    markets: list[Market] | None = None
    buyers: list[Buyer] | None = None
    sources: list[Source] | None = None
    error_code: str | None = None
    meta: dict | None = None


class SearchProvider(Protocol):
    id: str

    def search_markets(self, product: str, origin: str) -> ProviderResult: ...

    def search_buyers(self, product: str, country_code: str) -> ProviderResult: ...


class TradeProvider(Protocol):
    id: str

    def trade_stats(self, product: str, origin: str) -> ProviderResult: ...
