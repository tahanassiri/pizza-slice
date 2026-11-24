import asyncio

from app.agents.decision_loop import _store_claims, run_decision_loop
from app.agents.observations import compact_evidence, evidence_context, load_observations, page_read_status
from app.agents.tool_contracts import ToolResult
from app.db.session import SessionLocal
from app.evidence.store import evidence_index_for_run, record_claim
from app.models.entities import Run
from app.services import admin_service
from app.tools.extract import extract_claims


def test_run_claim_index_counts_unique_claims_and_never_truncates_the_ledger():
    with SessionLocal() as db:
        run = Run(id="run_research_ledger", product="tea", origin_country="India")
        db.add(run)
        db.commit()
        url = "https://example.com/tea"
        claim = {"statement": "Germany imports tea from India.", "country": "DE"}
        state = {"claims": []}
        assert _store_claims(db, run, state, url, [claim, claim]) == 1
        assert _store_claims(db, run, state, url, [claim]) == 0
        for i in range(27):
            record_claim(db, run_id=run.id, source_url=url, product_scope="tea", statement=f"Tea observation {i}")
        rows = compact_evidence(evidence_index_for_run(db, run.id))
        assert len(rows) == len({row["id"] for row in rows}) == 28
        assert all(row["id"] == row["claim_id"] for row in rows)
        selected = evidence_context(rows, {row["id"] for row in rows}, {"offset": 24})
        assert [row["id"] for row in selected] == [row["id"] for row in rows[24:]]
        assert all(row.get("statement") for row in selected)


def test_failed_extraction_is_distinct_from_irrelevant_content():
    assert page_read_status(stored=0, raw_claims=0, extract_outcome="failed") == "extraction_failed"
    assert page_read_status(stored=0, raw_claims=0, extract_outcome="irrelevant") == "irrelevant"


def test_extraction_maps_destination_and_rejects_unrelated_trade_text():
    result = extract_claims(
        text="Germany imports significant quantities of tea from India every year. "
        "The United States imports bananas from many countries in the region.",
        url="https://example.com/trade",
        product="tea",
        origin="India",
    )
    assert len(result.data["claims"]) == 1
    assert result.data["claims"][0]["country"] == "DE"


def test_outcome_feedback_and_candidate_survive_operational_stop(monkeypatch):
    broken = "https://example.com/broken"
    valid = "https://example.com/tea"
    events = []
    monkeypatch.setattr(admin_service, "read_safety", lambda _db: {
        "max_run_tokens": 5, "max_repeated_actions": 1,
    })

    class Model:
        id = "openrouter"
        research_cleared = True
        tokens_used = 0

        def decide_research_action(self, context):
            self.tokens_used += 1
            if self.tokens_used == 1:
                return {"action": "call_tool", "tool": "search_web", "args": {"query": "tea imports"}}
            if self.tokens_used in {2, 3}:
                return {"action": "call_tool", "tool": "fetch_page", "args": {"url": broken}}
            if self.tokens_used == 4:
                assert "extraction_failed" in str(context["recent_actions"])
                return {"action": "call_tool", "tool": "fetch_page", "args": {"url": valid}}
            claim = context["evidence"][0]["id"]
            return {
                "action": "change_strategy",
                "args": {"resolved_questions": [{"id": "q1", "evidence_ids": [claim]}]},
                "market_proposals": [
                    {"country_code": "DE", "recommendation": "recommended", "evidence_ids": [claim],
                     "criteria": [{"criterion": "demand", "evidence_ids": [claim]}]},
                    {"country_code": "AE", "recommendation": "recommended", "evidence_ids": [claim]},
                ],
            }

    class Executor:
        llm = Model()
        budget = None

        def execute(self, call):
            if call.tool == "search_web":
                return ToolResult(tool=call.tool, ok=True, message_fa="", data={
                    "results": [{"url": broken, "title": "Tea source"}, {"url": valid, "title": "Tea imports"}],
                })
            if call.tool == "fetch_page":
                return ToolResult(tool=call.tool, ok=True, message_fa="", data={
                    "url": call.args["url"], "text": "Germany imports significant quantities of tea from India every year.",
                })
            if call.tool == "extract_claims":
                if call.args["url"] == broken:
                    return ToolResult(tool=call.tool, ok=False, message_fa="Parser did not open the document.",
                                      error_code="TOOL_ERROR")
                return extract_claims(text=call.args["text"], url=valid, product="tea", origin="India")
            raise AssertionError(call.tool)

    async def emit(_db, _run, **event):
        events.append(event.get("payload") or {})

    with SessionLocal() as db:
        run = Run(id="run_research_recovery", product="tea", origin_country="India", status="running")
        db.add(run)
        db.commit()
        result = asyncio.run(run_decision_loop(db, run, Executor(), emit, checkpoint={
            "completed_steps": ["classify", "memory"],
        }))
        assert result["provisional"]
        assert result["stop_reason"] == "OPERATIONAL_SPENDING"
        assert [market.country_code for market in result["markets"]] == ["DE"]
        assert [row["status"] for row in load_observations(db, run.id)] == ["extraction_failed", "extracted"]
        outcomes = [event for event in events if event.get("event_type") == "research.outcome"]
        assert outcomes[1]["error_code"] == "TOOL_ERROR"
        assert outcomes[2]["error_code"] == "SOURCE_ALREADY_PROCESSED"
        assert outcomes[-1]["rejected_proposals"] == [{"country": "AE", "reason": "country_mismatch"}]
        audit = events[-1]["research_audit"]
        assert len(audit["claims"]) == 1
        assert audit["coverage"]["DE"]["criteria"] == {"demand": 1}
        assert audit["resolved_questions"]["q1"] == [audit["claims"][0]["id"]]
