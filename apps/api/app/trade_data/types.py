"""Source-independent trade data contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

QualityStatus = Literal["verified", "partial", "unavailable"]
TradeFlow = Literal["import", "export"]


@dataclass(frozen=True)
class TradeDataQuery:
    hs_code: str | None = None
    hs_revision: str | None = None
    reporter: str | None = None  # ISO3 when known
    partners: tuple[str, ...] = ()
    flow: TradeFlow = "import"
    years: tuple[int, ...] = ()
    metrics: tuple[str, ...] = ("trade_value",)
    product_hint: str | None = None
    origin: str | None = None


@dataclass
class TradeRecord:
    reporter_iso3: str
    partner_iso3: str
    year: int
    flow: TradeFlow
    value: float | None
    unit: str
    currency: str
    product_code: str
    product_label: str
    hs_code: str | None = None
    hs_revision: str | None = None
    estimated: bool = False
    note: str | None = None


@dataclass
class TradeDataResult:
    records: list[TradeRecord] = field(default_factory=list)
    source_name: str = ""
    source_url: str = ""
    retrieved_at: str = ""
    reference_year: int | None = None
    hs_code: str | None = None
    hs_revision: str | None = None
    unit: str = "USD"
    currency: str = "USD"
    coverage: str = ""
    quality_status: QualityStatus = "unavailable"
    warnings: list[str] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)  # Source-like dicts
    provider_id: str = ""
    cache_hit: bool = False


class TradeDataProvider(Protocol):
    id: str
    display_name: str

    def is_available(self) -> bool: ...

    def supports(self, query: TradeDataQuery) -> bool: ...

    def fetch(self, query: TradeDataQuery) -> TradeDataResult: ...
