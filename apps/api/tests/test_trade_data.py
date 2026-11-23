"""TradeDataService acceptance — no mandatory Comtrade key; no fake numbers."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from app.db.session import SessionLocal
from app.providers.registry import resolve_providers
from app.trade_data.cache import TtlCache
from app.trade_data.research import ResearchTradeProvider
from app.trade_data.service import TradeDataService
from app.trade_data.to_markets import trade_result_to_markets
from app.trade_data.types import TradeDataQuery, TradeDataResult, TradeRecord
from app.trade_data.wits import WitsTradeProvider, hs_to_wits_product


def test_hs_to_wits_product_mapping():
    code, label = hs_to_wits_product("080251")
    assert code == "06-15_Vegetable"
    assert "aggregate" in label.lower() or "sector" in label.lower() or "HS" in label
    code2, _ = hs_to_wits_product(None)
    assert code2 == "Total"
    # Ceramics / stone — must not fall through to Total
    code3, label3 = hs_to_wits_product("6907")
    assert code3 == "68-71_StoneGlas"
    assert "Total" not in code3
    assert "68" in label3 or "71" in label3 or "Stone" in label3
    code4, _ = hs_to_wits_product("4101")
    assert code4 == "41-43_HidesSkin"


def test_wits_fetch_uses_cache_and_records(monkeypatch):
    sample = {
        "dataSets": [
            {
                "series": {
                    "0:0:0:0:0": {"observations": {"0": [123456.0, 0]}},
                }
            }
        ]
    }

    class FakeResp:
        status_code = 200

        def json(self):
            return sample

    cache = TtlCache(ttl_seconds=60)
    provider = WitsTradeProvider(cache=cache, reporters=["ARE", "TUR", "DEU"])

    with patch("httpx.Client") as client_cls:
        http = MagicMock()
        http.__enter__.return_value = http
        http.get.return_value = FakeResp()
        client_cls.return_value = http

        q = TradeDataQuery(hs_code="080251", flow="import", product_hint="pistachio")
        first = provider.fetch(q)
        assert first.quality_status in {"verified", "partial"}
        assert len(first.records) == 3
        assert first.cache_hit is False

        second = provider.fetch(q)
        assert second.cache_hit is True
        assert len(second.records) == 3


def test_research_never_invents_numeric_records():
    search = MagicMock()
    search.search_markets.return_value = MagicMock(
        ok=True,
        message_fa="ok",
        sources=[
            MagicMock(
                model_dump=lambda: {
                    "url": "https://example.org/a",
                    "title": "A",
                    "publisher": "X",
                    "fetched_at": "2026-01-01T00:00:00Z",
                    "provider": "tavily",
                    "reliability_note": "search",
                }
            )
        ],
    )
    provider = ResearchTradeProvider(search_provider=search)
    result = provider.fetch(TradeDataQuery(product_hint="پسته", origin="ایران"))
    assert result.quality_status == "partial"
    assert result.records == []
    assert result.sources


def test_service_fallback_partial_when_wits_empty():
    wits = MagicMock()
    wits.id = "wits"
    wits.display_name = "WITS"
    wits.is_available.return_value = True
    wits.supports.return_value = True
    wits.fetch.return_value = TradeDataResult(
        quality_status="unavailable",
        warnings=["down"],
        provider_id="wits",
    )

    research = MagicMock()
    research.id = "research"
    research.display_name = "Research"
    research.is_available.return_value = True
    research.supports.return_value = True
    research.fetch.return_value = TradeDataResult(
        quality_status="partial",
        sources=[{"url": "https://example.org", "title": "t", "publisher": "p",
                  "fetched_at": "t", "provider": "research", "reliability_note": "n"}],
        warnings=["sources only"],
        provider_id="research",
    )

    from app.trade_data.comtrade_optional import ComtradePublicProvider

    svc = TradeDataService(
        wits=wits,
        research=research,
        comtrade_public=ComtradePublicProvider(enabled=False),
    )
    out = svc.fetch(TradeDataQuery(product_hint="x"))
    assert out.quality_status == "partial"
    assert out.records == []
    assert out.sources


def test_to_markets_unavailable_not_fake():
    result = TradeDataResult(quality_status="unavailable", warnings=["none"])
    pr = trade_result_to_markets(result, product="x", origin="ایران")
    assert pr.ok is False
    assert not pr.markets


def test_to_markets_ranks_records():
    result = TradeDataResult(
        quality_status="partial",
        source_name="WITS",
        reference_year=2022,
        unit="USD",
        records=[
            TradeRecord(
                reporter_iso3="DEU",
                partner_iso3="WLD",
                year=2022,
                flow="import",
                value=900.0,
                unit="USD",
                currency="USD",
                product_code="Total",
                product_label="All products",
            ),
            TradeRecord(
                reporter_iso3="ARE",
                partner_iso3="WLD",
                year=2022,
                flow="import",
                value=500.0,
                unit="USD",
                currency="USD",
                product_code="Total",
                product_label="All products",
            ),
            TradeRecord(
                reporter_iso3="TUR",
                partner_iso3="WLD",
                year=2022,
                flow="import",
                value=700.0,
                unit="USD",
                currency="USD",
                product_code="Total",
                product_label="All products",
            ),
        ],
        sources=[
            {
                "url": "https://wits.worldbank.org/x",
                "title": "WITS DEU",
                "publisher": "WITS",
                "fetched_at": "t",
                "provider": "wits",
                "reliability_note": "n",
            }
        ],
        provider_id="wits",
    )
    pr = trade_result_to_markets(result, product="پسته", origin="ایران")
    assert pr.ok
    assert [m.country_code for m in pr.markets] == ["DE", "TR", "AE"]
    assert any(m.key == "data_quality" for m in pr.markets[0].metrics)
    assert any(m.key == "pool_share" for m in pr.markets[0].metrics)
    assert any("چرا این کشور" in e for e in pr.markets[0].evidence)


def test_registry_uses_trade_data_without_comtrade(monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "auto")
    from app.core.config import get_settings

    get_settings.cache_clear()
    db = SessionLocal()
    try:
        bundle = resolve_providers(db)
        assert bundle.trade_service is not None
        assert bundle.trade_service.comtrade_public.enabled is False
        assert bundle.trade.id == "trade_data_service"
    finally:
        db.close()
        get_settings.cache_clear()


def test_pipeline_without_comtrade_key(client, monkeypatch):
    """Acceptance: empty Comtrade key — analysis still starts and can complete via WITS."""
    monkeypatch.setenv("PROVIDER_MODE", "auto")
    from app.core.config import get_settings

    get_settings.cache_clear()

    sample = {
        "dataSets": [
            {"series": {"0:0:0:0:0": {"observations": {"0": [9_000_000.0, 0]}}}}
        ]
    }
    wiki_sample = ["پسته", ["پسته"], [""], ["https://fa.wikipedia.org/wiki/پسته"]]

    class FakeResp:
        def __init__(self, payload, status=200):
            self.status_code = status
            self._payload = payload
            self.url = "https://wits.worldbank.org/mock"

        def json(self):
            return self._payload

    def fake_get(url, *args, **kwargs):
        u = str(url)
        if "wits.worldbank.org" in u:
            return FakeResp(sample)
        if "wikipedia" in u or "wikipedia.org" in u:
            return FakeResp(wiki_sample)
        return FakeResp({}, status=404)

    with patch("httpx.Client") as client_cls:
        http = MagicMock()
        http.__enter__.return_value = http
        http.get.side_effect = fake_get
        client_cls.return_value = http

        run_id = client.post(
            "/api/runs",
            json={"product": "پسته خام", "origin_country": "ایران", "hs_code": "080251"},
        ).json()["run_id"]

        snap = None
        for _ in range(120):
            snap = client.get(f"/api/runs/{run_id}").json()
            if snap["run"]["phase"] == "report" and snap.get("report") is not None:
                break
            time.sleep(0.05)

    get_settings.cache_clear()
    assert snap is not None
    assert snap["run"]["is_mock"] is False
    assert snap["report"] is not None
    # Either ranked markets from WITS or honest partial — never mock fake buyers/stats
    if snap["markets"]:
        assert len(snap["markets"]) <= 3
        q = next(
            (m for m in snap["markets"][0]["metrics"] if m["key"] == "data_quality"),
            None,
        )
        assert q is not None
        assert q["value"] in {"verified", "partial"}
    else:
        assert snap["run"]["status"] in {"partial", "completed"}
        assert "unavailable" in (snap["report"]["summary_fa"] or "") or snap["run"][
            "status"
        ] == "partial"
