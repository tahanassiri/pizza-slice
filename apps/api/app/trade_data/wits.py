"""WITS Trade Stats adapter (World Bank) — free, no API key.

Uses aggregate product *groups* (Sector / Total), NOT HS6 bilateral rows.
Never mislabel aggregate totals as product-HS bilateral trade.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import httpx

from app.trade_data.cache import TtlCache, trade_breaker, trade_cache
from app.trade_data.types import TradeDataQuery, TradeDataResult, TradeRecord

WITS_BASE = "https://wits.worldbank.org/API/V1/SDMX/V21/datasource/tradestats-trade"
WITS_DOCS = "https://wits.worldbank.org/witsapiintro.aspx"

# ISO2 → ISO3 destination pool (Iran-export–relevant + major sector importers).
# Broader than the old 7-country set so sector rankings are not stuck on CN/DE/IN.
ISO2_TO_ISO3: dict[str, str] = {
    "AE": "ARE",
    "TR": "TUR",
    "IQ": "IRQ",
    "SA": "SAU",
    "OM": "OMN",
    "KW": "KWT",
    "QA": "QAT",
    "AZ": "AZE",
    "AM": "ARM",
    "GE": "GEO",
    "PK": "PAK",
    "KZ": "KAZ",
    "CN": "CHN",
    "IN": "IND",
    "RU": "RUS",
    "DE": "DEU",
    "IT": "ITA",
    "NL": "NLD",
    "FR": "FRA",
    "GB": "GBR",
    "ES": "ESP",
    "PL": "POL",
    "KR": "KOR",
    "JP": "JPN",
    "MY": "MYS",
    "SG": "SGP",
    "BR": "BRA",
}

ISO3_TO_ISO2: dict[str, str] = {v: k for k, v in ISO2_TO_ISO3.items()}

ISO3_NAME_FA: dict[str, str] = {
    "ARE": "امارات متحده عربی",
    "TUR": "ترکیه",
    "IRQ": "عراق",
    "SAU": "عربستان سعودی",
    "OMN": "عمان",
    "KWT": "کویت",
    "QAT": "قطر",
    "AZE": "جمهوری آذربایجان",
    "ARM": "ارمنستان",
    "GEO": "گرجستان",
    "PAK": "پاکستان",
    "KAZ": "قزاقستان",
    "CHN": "چین",
    "IND": "هند",
    "RUS": "روسیه",
    "DEU": "آلمان",
    "ITA": "ایتالیا",
    "NLD": "هلند",
    "FRA": "فرانسه",
    "GBR": "بریتانیا",
    "ESP": "اسپانیا",
    "POL": "لهستان",
    "KOR": "کره جنوبی",
    "JPN": "ژاپن",
    "MYS": "مالزی",
    "SGP": "سنگاپور",
    "BRA": "برزیل",
}

# HS chapter → WITS sector product code (honest group aggregate)
_HS_SECTORS: list[tuple[int, int, str, str]] = [
    (1, 5, "01-05_Animal", "Animal products (HS 01–05)"),
    (6, 15, "06-15_Vegetable", "Vegetable products (HS 06–15)"),
    (16, 24, "16-24_FoodProd", "Food products (HS 16–24)"),
    (25, 26, "25-26_Minerals", "Minerals (HS 25–26)"),
    (27, 27, "27-27_Fuels", "Fuels (HS 27)"),
    (28, 38, "28-38_Chemicals", "Chemicals (HS 28–38)"),
    (39, 40, "39-40_PlastiRub", "Plastics & rubber (HS 39–40)"),
    (41, 43, "41-43_HidesSkin", "Hides & skins (HS 41–43)"),
    (44, 49, "44-49_Wood", "Wood & paper (HS 44–49)"),
    (50, 63, "50-63_TextCloth", "Textiles & clothing (HS 50–63)"),
    (64, 67, "64-67_Footwear", "Footwear (HS 64–67)"),
    (68, 71, "68-71_StoneGlas", "Stone, glass & ceramics (HS 68–71)"),
    (72, 83, "72-83_Metals", "Metals (HS 72–83)"),
    (84, 85, "84-85_MachElec", "Machinery & electrical (HS 84–85)"),
    (86, 89, "86-89_Transport", "Transport (HS 86–89)"),
    (90, 99, "90-99_Miscellan", "Miscellaneous (HS 90–99)"),
]


def hs_to_wits_product(hs_code: str | None) -> tuple[str, str]:
    """Map HS code to nearest WITS sector group. Falls back to Total."""
    if not hs_code:
        return "Total", "All products (aggregate Total — not HS-specific)"
    digits = "".join(ch for ch in hs_code if ch.isdigit())
    if len(digits) < 2:
        return "Total", "All products (aggregate Total — not HS-specific)"
    try:
        chapter = int(digits[:2])
    except ValueError:
        return "Total", "All products (aggregate Total — not HS-specific)"
    for lo, hi, code, label in _HS_SECTORS:
        if lo <= chapter <= hi:
            return code, f"{label} — WITS sector aggregate, not HS{len(digits)} bilateral"
    return "Total", "All products (aggregate Total — not HS-specific)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_observation(payload: dict) -> float | None:
    try:
        series = (payload.get("dataSets") or [{}])[0].get("series") or {}
        if not series:
            return None
        first = next(iter(series.values()))
        obs = (first.get("observations") or {}).get("0")
        if not obs:
            return None
        return float(obs[0])
    except Exception:
        return None


class WitsTradeProvider:
    id = "wits"
    display_name = "WITS Trade Stats"

    def __init__(
        self,
        timeout: float = 18.0,
        cache: TtlCache | None = None,
        reporters: list[str] | None = None,
    ):
        self.timeout = timeout
        self.cache = cache or trade_cache
        self.reporters = reporters or list(ISO2_TO_ISO3.values())

    def is_available(self) -> bool:
        return trade_breaker.allow(self.id)

    def supports(self, query: TradeDataQuery) -> bool:
        return True

    def _candidate_years(self, query: TradeDataQuery) -> list[int]:
        if query.years:
            return sorted(set(query.years), reverse=True)
        # WITS often lags 2–4 years; prefer recent complete years first
        y = datetime.now(timezone.utc).year
        return [y - 2, y - 3, y - 4]

    def _fetch_one(
        self, reporter: str, year: int, product: str, indicator: str
    ) -> tuple[str, float | None, str, bool]:
        """Return (iso3, value, url, from_cache). Empty country rows are not breaker failures."""
        url = (
            f"{WITS_BASE}/reporter/{reporter}/year/{year}/partner/WLD"
            f"/product/{product}/indicator/{indicator}?format=JSON"
        )
        cache_key = TtlCache.make_key(
            "wits",
            {"r": reporter, "y": year, "p": product, "i": indicator},
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return reporter, cached[0], url, True

        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
                r = client.get(url)
        except Exception:
            trade_breaker.record_failure(self.id)
            return reporter, None, url, False

        if r.status_code >= 500:
            trade_breaker.record_failure(self.id)
            return reporter, None, url, False

        if r.status_code != 200:
            # Missing reporter/year/product is common — cache miss, don't trip breaker
            self.cache.set(cache_key, (None, url))
            return reporter, None, url, False

        value = _parse_observation(r.json())
        trade_breaker.record_success(self.id)
        self.cache.set(cache_key, (value, url))
        return reporter, value, url, False

    def fetch(self, query: TradeDataQuery) -> TradeDataResult:
        if not self.is_available():
            return TradeDataResult(
                source_name=self.display_name,
                source_url=WITS_DOCS,
                retrieved_at=_now(),
                quality_status="unavailable",
                warnings=["مدارشکن WITS باز است — پس از خطاهای مکرر موقتاً رد شد."],
                provider_id=self.id,
                coverage="none",
            )

        product, product_label = hs_to_wits_product(query.hs_code)
        years = self._candidate_years(query)
        indicator = "MPRT-TRD-VL" if query.flow == "import" else "XPRT-TRD-VL"
        reporters = list(query.partners) if query.partners else self.reporters
        # partners in query are destinations reporting imports (ISO3)
        if query.reporter and not query.partners:
            reporters = [query.reporter]

        records: list[TradeRecord] = []
        sources: list[dict] = []
        warnings: list[str] = [
            "WITS TradeStats از گروه‌های محصولی/کل استفاده می‌کند؛ این عدد تجارت دوجانبه HS6 نیست.",
        ]
        cache_hit = False
        errors = 0
        year_used: int | None = None

        # Parallel per-year reporter fetches (expanded destination pool)
        for year in years:
            year_records: list[TradeRecord] = []
            year_sources: list[dict] = []
            year_errors = 0
            year_cache = False
            with ThreadPoolExecutor(max_workers=min(10, max(4, len(reporters)))) as pool:
                futures = [
                    pool.submit(self._fetch_one, iso3, year, product, indicator)
                    for iso3 in reporters
                ]
                for fut in as_completed(futures):
                    iso3, value, url, from_cache = fut.result()
                    if from_cache:
                        year_cache = True
                    if value is None:
                        year_errors += 1
                        continue
                    year_records.append(
                        TradeRecord(
                            reporter_iso3=iso3,
                            partner_iso3="WLD",
                            year=year,
                            flow=query.flow,
                            value=value,
                            unit="USD",
                            currency="USD",
                            product_code=product,
                            product_label=product_label,
                            hs_code=query.hs_code,
                            hs_revision=query.hs_revision,
                            estimated=False,
                            note="WITS MPRT/XPRT-TRD-VL as reported by API",
                        )
                    )
                    year_sources.append(
                        {
                            "url": url,
                            "title": f"WITS {indicator} — {iso3} {year} {product}",
                            "publisher": "World Bank WITS",
                            "published_at": str(year),
                            "fetched_at": _now(),
                            "provider": self.id,
                            "reliability_note": product_label,
                        }
                    )
            if year_records:
                records = year_records
                sources = year_sources
                errors = year_errors
                cache_hit = year_cache
                year_used = year
                break
            errors += year_errors

        if not records:
            return TradeDataResult(
                records=[],
                source_name=self.display_name,
                source_url=WITS_DOCS,
                retrieved_at=_now(),
                reference_year=years[0] if years else None,
                hs_code=query.hs_code,
                hs_revision=query.hs_revision,
                unit="USD",
                currency="USD",
                coverage="none",
                quality_status="unavailable",
                warnings=warnings
                + [
                    f"هیچ ردیف WITS برای سال‌های {years} / محصول {product} دریافت نشد "
                    f"(خطا/خالی: {errors})."
                ],
                sources=sources,
                provider_id=self.id,
                cache_hit=cache_hit,
            )

        year = year_used or years[0]

        quality: str = "verified" if product != "Total" and len(records) >= 3 else "partial"
        if product == "Total":
            warnings.append(
                "رتبه‌بندی بر واردات کل (Total) است — نه تقاضای محصول‌محور HS."
            )
            quality = "partial"

        return TradeDataResult(
            records=records,
            source_name=self.display_name,
            source_url=WITS_DOCS,
            retrieved_at=_now(),
            reference_year=year,
            hs_code=query.hs_code,
            hs_revision=query.hs_revision,
            unit="USD",
            currency="USD",
            coverage=f"{len(records)} reporters · product={product} · partner=WLD",
            quality_status=quality,  # type: ignore[arg-type]
            warnings=warnings,
            sources=sources,
            provider_id=self.id,
            cache_hit=cache_hit,
        )
