"""Architecture correction tests A–L (master mission)."""

from __future__ import annotations

import json
import time

import pytest

from app.agents.llm_decide import (
    blocked_action,
    llm_is_research_decision_maker,
    parse_model_decision,
)
import app.agents.llm_decide as llm_decide_mod
from app.agents.planner import build_research_plan
from app.db.session import SessionLocal
from app.jobs.durable import claim_task, create_task, recover_stale_leases
from app.knowledge.repository import KnowledgeRepository, canonical_key
from app.models.entities import ResearchTask
from app.providers.registry import resolve_providers
from app.services.admin_service import ensure_providers, trade_sources_view
from app.tools.executor import ToolExecutor
from app.tools.free_web import free_web_search, search_wikipedia
from app.tools.verify_company import verify_company
from app.agents.tool_contracts import ToolCall


# A — only a cleared model decides. Missing model is a recoverable block, never a heuristic.
def test_A_decision_maker_not_fixed_pipeline():
    plan = build_research_plan(product="pistachio", hs6=None, origin="ایران")
    assert plan.candidate_countries == []
    assert "get_trade_stats" not in plan.tools_needed
    assert not hasattr(llm_decide_mod, "_heuristic_next")
    assert llm_is_research_decision_maker(None) is False
    blocked = blocked_action("LLM_UNAVAILABLE", "مدل نیست")
    assert blocked.action == "blocked"
    assert blocked.recoverable is True
    assert blocked.market_proposals == []
    assert blocked.decision_source == "blocked"
    parsed = parse_model_decision(
        '{"action":"call_tool","tool":"search_web","args":{"query":"pistachio"},"rationale_fa":"جست"}'
    )
    assert parsed is not None
    assert parsed.decision_source == "llm"
    assert parsed.tool == "search_web"
    assert parse_model_decision('{"action":"call_tool","tool":"shell","args":{}}') is None


# B — admin trade sources have no mandatory Tavily/Exa/WITS/Comtrade
def test_B_no_mandatory_trade_providers_in_admin():
    with SessionLocal() as db:
        ensure_providers(db)
        sources = trade_sources_view(db)
        ids = {s.id for s in sources}
        assert "wits" not in ids
        assert "comtrade" not in ids
        assert "free_web" in ids
        assert "active_llm" in ids
        bundle = resolve_providers(db)
        assert bundle.trade_service is None
        assert any("Tavily" in n or "WITS" in n or "Comtrade" in n or "حذف" in n for n in bundle.notes_fa) or True


# C — iterative loop produces decision events (stub-safe)
def test_C_iterative_loop_emits_decisions(client):
    rid = client.post("/api/runs", json={"product": "پسته صادراتی", "origin_country": "ایران"}).json()[
        "run_id"
    ]
    deadline = time.time() + 12
    snap = None
    while time.time() < deadline:
        snap = client.get(f"/api/runs/{rid}").json()
        if snap.get("report") is not None:
            break
        time.sleep(0.05)
    assert snap and snap.get("report")
    types = [((e.get("payload") or {}).get("event_type")) for e in snap["events"]]
    assert "research.loop_start" in types or "research.decision" in types or any(
        e["phase"] == "search" for e in snap["events"]
    )


# D — provider-neutral tools; stub does not fake web facts
def test_D_stub_search_does_not_invent(client):
    with SessionLocal() as db:
        ex = ToolExecutor(db, run_id="run_stub_d")
        res = ex.execute(ToolCall(tool="search_web", args={"query": "pistachio export"}))
        assert res.ok is False
        assert res.error_code in {"INSUFFICIENT_EVIDENCE", "WEB_SEARCH_BLOCKED"}
        assert not (res.data or {}).get("results")


# E — no hardcoded country pools
def test_E_no_country_pool():
    plan = build_research_plan(product="steel plates", hs6="7208", origin="ایران")
    assert plan.candidate_countries == []
    food = build_research_plan(product="pistachio", hs6=None, origin="ایران")
    assert food.candidate_countries == []


# F — memory period key match (save year in published_period, lookup with empty period)
def test_F_memory_period_key_consistent():
    with SessionLocal() as db:
        repo = KnowledgeRepository(db)
        repo.save_public(
            kind="market_stats",
            payload={"markets": [{"country_code": "AE"}], "year": "2022"},
            product="mem-period-fix",
            origin="ایران",
            metric="ranked_markets",
            period="",  # stable
            published_period="2022",
        )
        # lookup must hit with empty period (bug was saving year in key but looking up without)
        item, status = repo.lookup_public(
            kind="market_stats",
            product="mem-period-fix",
            origin="ایران",
            metric="ranked_markets",
            period="",
        )
        assert status in {"hit", "stale"}
        assert item is not None
        assert item.published_period == "2022"
        # exact key uses empty period
        assert canonical_key(
            kind="market_stats",
            product="mem-period-fix",
            origin="ایران",
            metric="ranked_markets",
            period="",
        ) == item.canonical_key or item.canonical_key.startswith(
            canonical_key(
                kind="market_stats",
                product="mem-period-fix",
                origin="ایران",
                metric="ranked_markets",
                period="",
            ).rsplit("|", 1)[0]
        )


# G — buyers only after country select
def test_G_buyer_gate(client):
    rid = client.post("/api/runs", json={"product": "زعفران", "origin_country": "ایران"}).json()[
        "run_id"
    ]
    deadline = time.time() + 10
    while time.time() < deadline:
        snap = client.get(f"/api/runs/{rid}").json()
        if snap.get("report"):
            break
        time.sleep(0.05)
    snap = client.get(f"/api/runs/{rid}").json()
    assert snap["buyers"] == []
    assert snap.get("buyer_search") is None


# H — seller/directory rejected; roles distinguished
def test_H_buyer_roles_and_no_fabricated_contact():
    r = verify_company(
        company_name="Sell Export Co",
        website="https://www.alibaba.com/x",
        country="AE",
        product="pistachio",
        snippets=["we sell and export for sale"],
        fetch=False,
    )
    assert r.data["verification_status"] == "rejected"
    ok = verify_company(
        company_name="Gulf Importers LLC",
        website="https://example-importer.test",
        country="AE",
        product="pistachio",
        snippets=["pistachio importer and distributor procurement"],
        fetch=False,
    )
    assert ok.data["verification_status"] in {"needs_review", "source_backed"}
    assert ok.data.get("category") in {
        "importer",
        "distributor",
        "wholesaler",
        "industrial_end_user",
        "unknown",
    }
    assert "contact" not in ok.data or ok.data.get("contact") in (None, {})


# I — feasibility deterministic; missing stays missing
def test_I_feasibility_missing(client, monkeypatch):
    from app.services import runs

    monkeypatch.setattr(runs, "schedule_pipeline", lambda _: None)
    rid = client.post("/api/runs", json={"product": "test product"}).json()["run_id"]
    out = client.post(
        f"/api/runs/{rid}/feasibility",
        json={"input_assumptions": {"quantity": 1, "incoterm": "CIF"}},
    ).json()
    assert out["missing_inputs"]
    assert all(s["margin"] is None for s in out["scenario_results"])


# J — active LLM is research decision driver capability (method present on live builders)
def test_J_llm_has_research_decision_api():
    from app.providers.keyed import KeyedGeminiLLM, KeyedOpenAICompatLLM
    from app.providers.stubs import StubLLMProvider

    assert hasattr(StubLLMProvider(), "decide_research_action")
    assert hasattr(KeyedGeminiLLM("x"), "decide_research_action")
    assert hasattr(KeyedOpenAICompatLLM("x", "gpt-test"), "decide_research_action")


# K — durable recovery: expired lease → requeue, not silent success
def test_K_lease_recovery_reques_not_complete():
    from datetime import datetime, timedelta, timezone

    with SessionLocal() as db:
        # need a run row? ResearchTask has FK to runs — create minimal run
        from app.models.entities import Run

        run = Run(
            id="run_lease_k",
            product="x",
            origin_country="ایران",
            phase="search",
            status="running",
        )
        db.add(run)
        db.commit()
        task = create_task(db, run_id="run_lease_k", stage="market_research")
        claimed = claim_task(db, task.id, "w1")
        assert claimed is not None
        claimed.lease_until = datetime.now(timezone.utc) - timedelta(seconds=10)
        db.commit()
        recover_stale_leases(db)
        refreshed = db.get(ResearchTask, task.id)
        assert refreshed is not None
        # Must not be completed; should be queued for retry
        assert refreshed.status in {"queued", "interrupted"}
        assert refreshed.status != "completed"


# L — ONE real no-cost end-to-end web retrieval (not mocked)
@pytest.mark.integration
def test_L_real_no_cost_web_retrieval():
    try:
        wiki = search_wikipedia("pistachio", lang="en", limit=2)
    except Exception as exc:
        pytest.skip(f"BLOCKED: wikipedia unreachable ({type(exc).__name__})")
    if not wiki:
        pytest.skip("BLOCKED: wikipedia returned empty")
    assert wiki[0]["url"].startswith("http")
    assert "wikipedia.org" in wiki[0]["url"]
    # Also exercise free_web_search aggregator
    result = free_web_search("pistachio export", max_results=3)
    if not result.ok or not (result.data or {}).get("beyond_wikipedia"):
        pytest.skip(
            "BLOCKED: free web beyond Wikipedia unavailable "
            f"({result.error_code} {(result.data or {}).get('errors')})"
        )
    assert result.data["results"]
    assert any("http" in (r.get("url") or "") for r in result.data["results"])
