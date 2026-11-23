from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.providers.free_wiki import FreeWikiSearchProvider
from app.providers.free_worldbank import FreeWorldBankTradeProvider
from app.providers.registry import resolve_providers
from app.providers.stubs import StubSearchProvider
from app.db.session import SessionLocal


def test_registry_stub_mode(monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "stub")
    from app.core.config import get_settings

    get_settings.cache_clear()
    db = SessionLocal()
    try:
        bundle = resolve_providers(db)
        assert bundle.mode == "stub"
        assert isinstance(bundle.search, StubSearchProvider)
    finally:
        db.close()
        get_settings.cache_clear()


def test_worldbank_build_markets_from_mock_http():
    sample = [
        {"page": 1},
        [
            {
                "date": "2023",
                "value": 1000000.0,
            }
        ],
    ]

    class FakeResp:
        status_code = 200

        def json(self):
            return sample

    with patch("httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.return_value = FakeResp()
        client_cls.return_value = client
        result = FreeWorldBankTradeProvider().build_markets("پسته", "ایران")

    assert result.ok
    assert result.markets and len(result.markets) == 3
    assert result.markets[0].confidence == "low"
    assert all(m.sources for m in result.markets)


def test_wiki_insufficient_for_markets():
    with patch.object(
        FreeWikiSearchProvider,
        "search_product_context",
        return_value=MagicMock(ok=True, sources=[]),
    ):
        result = FreeWikiSearchProvider().search_markets("پسته", "ایران")
    assert result.ok is False
    assert result.error_code == "INSUFFICIENT_EVIDENCE"


def test_pipeline_auto_mode_with_mocked_wits(client, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "auto")
    from app.core.config import get_settings

    get_settings.cache_clear()

    wits_sample = {
        "dataSets": [
            {"series": {"0:0:0:0:0": {"observations": {"0": [5_000_000.0, 0]}}}}
        ]
    }
    wiki_sample = [
        "پسته",
        ["پسته"],
        [""],
        ["https://fa.wikipedia.org/wiki/پسته"],
    ]

    class FakeResp:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload
            self.url = "https://wits.worldbank.org/mock"

        def json(self):
            return self._payload

    def fake_get(url, *args, **kwargs):
        if "wits.worldbank.org" in str(url):
            return FakeResp(wits_sample)
        return FakeResp(wiki_sample)

    import time

    # Both providers import the same httpx module — patch Client once and route by URL.
    with patch("httpx.Client") as client_cls:
        http = MagicMock()
        http.__enter__.return_value = http
        http.get.side_effect = fake_get
        client_cls.return_value = http

        run_id = client.post(
            "/api/runs",
            json={"product": "پسته خام", "origin_country": "ایران"},
        ).json()["run_id"]

        snap = None
        for _ in range(100):
            snap = client.get(f"/api/runs/{run_id}").json()
            if snap["run"]["phase"] == "report" and snap.get("report") is not None:
                break
            time.sleep(0.05)

    get_settings.cache_clear()
    assert snap is not None
    assert snap["run"]["is_mock"] is False
    assert len(snap["markets"]) == 3, snap["run"]
    assert snap["report"] is not None
    assert snap["report"]["is_mock"] is False
    assert "WITS" in (snap["report"]["summary_fa"] or "") or any(
        m.get("key") == "data_quality" for m in snap["markets"][0]["metrics"]
    )
