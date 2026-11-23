"""Unit tests for agentic memory, scoring, budget, buyer verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.agents.market_scorer import cards_to_markets, clamp_weights, score_from_trade_records
from app.agents.state_machine import assert_transition, can_transition
from app.db.session import SessionLocal
from app.knowledge.freshness import is_stale, stale_after_for_kind
from app.knowledge.repository import KnowledgeRepository
from app.tools.budget import BudgetExceeded, consume, ensure_run_budget
from app.tools.verify_company import verify_company


def test_state_transitions():
    assert can_transition("queued", "running")
    assert not can_transition("completed", "running")
    assert_transition("running", "partial")


def test_memory_isolation_and_stale(tmp_path=None):
    db = SessionLocal()
    try:
        repo = KnowledgeRepository(db)
        item = repo.save_public(
            kind="market_stats",
            payload={"markets": [{"country_code": "AE"}]},
            product="pistachio",
            hs6="080251",
            origin="ایران",
            metric="ranked_markets",
            period="2022",
            confidence="low",
            origin_run_id="run_a",
        )
        hit, status = repo.lookup_public(
            kind="market_stats",
            product="pistachio",
            hs6="080251",
            origin="ایران",
            metric="ranked_markets",
            period="2022",
        )
        assert status == "hit"
        assert hit is not None
        assert hit.id == item.id

        # Different product must miss (no cross-HS chapter bleed by product name)
        miss, status2 = repo.lookup_public(
            kind="market_stats",
            product="industrial polymer resin",
            hs6="080251",
            origin="ایران",
            metric="ranked_markets",
            period="2022",
        )
        assert status2 == "miss"
        assert miss is None

        # stale detection
        past = datetime.now(timezone.utc) - timedelta(days=1)
        assert is_stale(past)
        assert not is_stale(stale_after_for_kind("product_identity"))
    finally:
        db.close()


def test_budget_enforced():
    db = SessionLocal()
    try:
        b = ensure_run_budget(db, "run_budget_test")
        b.max_search_queries = 2
        b.search_queries_used = 0
        db.commit()
        consume(db, b, kind="search", units=1, run_id="run_budget_test", tool_name="search_web")
        consume(db, b, kind="search", units=1, run_id="run_budget_test", tool_name="search_web")
        try:
            consume(db, b, kind="search", units=1, run_id="run_budget_test", tool_name="search_web")
            assert False, "expected BudgetExceeded"
        except BudgetExceeded:
            pass
    finally:
        db.close()


def test_scorer_no_fake_zeros_and_sector_label():
    records = [
        {
            "reporter_iso3": "ARE",
            "partner_iso3": "WLD",
            "year": 2022,
            "value": 100.0,
            "unit": "USD",
            "product_code": "06-15_Vegetable",
            "product_label": "Vegetable sector aggregate",
            "flow": "import",
            "estimated": False,
        },
        {
            "reporter_iso3": "TUR",
            "partner_iso3": "WLD",
            "year": 2022,
            "value": 80.0,
            "unit": "USD",
            "product_code": "06-15_Vegetable",
            "product_label": "Vegetable sector aggregate",
            "flow": "import",
            "estimated": False,
        },
        {
            "reporter_iso3": "DEU",
            "partner_iso3": "WLD",
            "year": 2022,
            "value": 60.0,
            "unit": "USD",
            "product_code": "06-15_Vegetable",
            "product_label": "Vegetable sector aggregate",
            "flow": "import",
            "estimated": False,
        },
        {
            "reporter_iso3": "CHN",
            "partner_iso3": "WLD",
            "year": 2022,
            "value": 40.0,
            "unit": "USD",
            "product_code": "06-15_Vegetable",
            "product_label": "Vegetable sector aggregate",
            "flow": "import",
            "estimated": False,
        },
        {
            "reporter_iso3": "IND",
            "partner_iso3": "WLD",
            "year": 2022,
            "value": 20.0,
            "unit": "USD",
            "product_code": "06-15_Vegetable",
            "product_label": "Vegetable sector aggregate",
            "flow": "import",
            "estimated": False,
        },
    ]
    cards = score_from_trade_records(
        records,
        data_scope="sector",
        source_name="WITS",
        reference_year=2022,
        quality_status="partial",
        product="pistachio",
    )
    assert cards
    legal = next(c for c in cards[0].criteria if c.key == "legal")
    assert legal.unknown is True
    assert legal.score_value is None
    markets = cards_to_markets(cards, reference_year=2022, source_name="WITS")
    rec = [m for m in markets if any(x.key == "recommendation" and x.value == "recommended" for x in m.metrics)]
    risky = [m for m in markets if any(x.key == "recommendation" and x.value == "risky" for x in m.metrics)]
    assert 1 <= len(rec) <= 3
    assert len(risky) <= 2
    assert any(x.key == "data_scope" and x.value == "sector" for x in markets[0].metrics)


def test_clamp_weights_bounds():
    w = clamp_weights({"demand": 0.99, "legal": 0.01})
    assert 0.15 <= w["demand"] <= 0.40
    assert abs(sum(w.values()) - 1.0) < 1e-6


def test_seller_listing_rejected():
    result = verify_company(
        company_name="Best Pistachio Exporters Co",
        website="https://www.alibaba.com/product/pistachio",
        country="AE",
        product="pistachio",
        snippets=["We sell and export pistachio worldwide for sale"],
        fetch=False,
    )
    assert result.data["verification_status"] == "rejected"


def test_buyerish_needs_review_without_page():
    result = verify_company(
        company_name="Gulf Food Trading",
        website="https://gulffood-example.test",
        country="AE",
        product="pistachio",
        snippets=["Leading pistachio importer and distributor in UAE"],
        fetch=False,
    )
    assert result.data["verification_status"] in {"needs_review", "source_backed"}


def test_two_products_different_memory_keys():
    db = SessionLocal()
    try:
        repo = KnowledgeRepository(db)
        repo.save_public(
            kind="market_stats",
            payload={"markets": [{"country_code": "AE"}], "product": "pistachio"},
            product="pistachio",
            origin="ایران",
            metric="ranked_markets",
        )
        repo.save_public(
            kind="market_stats",
            payload={"markets": [{"country_code": "DE"}], "product": "saffron"},
            product="saffron",
            origin="ایران",
            metric="ranked_markets",
        )
        a, sa = repo.lookup_public(
            kind="market_stats", product="pistachio", origin="ایران", metric="ranked_markets"
        )
        b, sb = repo.lookup_public(
            kind="market_stats", product="saffron", origin="ایران", metric="ranked_markets"
        )
        assert sa == "hit" and sb == "hit"
        assert a.canonical_key != b.canonical_key
        assert "AE" in a.payload_json and "DE" in b.payload_json
    finally:
        db.close()
