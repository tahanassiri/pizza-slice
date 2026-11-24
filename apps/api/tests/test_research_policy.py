"""Market discovery stays open when no destination is selected. HS codes need source support."""

from __future__ import annotations

import asyncio

from app.agents.hs_code import accept_hs_evidence, parse_hs6
from app.agents.policy import SYSTEM_POLICY_FA
from app.agents.research_phase import buyer_research_blocked, premature_market_stop
from app.db.session import SessionLocal
from app.models.entities import Run
from app.services import admin_service


def test_rule_4_blocks_buyers_and_not_market_discovery():
    text = SYSTEM_POLICY_FA
    assert "کشف بازار" in text
    assert "تحقیق گسترده خریدار" in text
    assert "انتخاب کشور مقصد پیش‌نیاز کشف بازار نیست" in text
    assert premature_market_stop("conclude", []) is not None
    assert premature_market_stop("ask_user", []) is not None
    assert premature_market_stop("conclude", ["search_web"]) is None
    assert premature_market_stop("call_tool", []) is None
    assert buyer_research_blocked("verify_company", None) is not None
    assert buyer_research_blocked("verify_company", "AE") is None
    assert buyer_research_blocked("search_web", None) is None


def test_hs_parser_keeps_leading_zeros_and_does_not_join_digits():
    assert parse_hs6("091020") == "091020"
    assert parse_hs6('{"hs6":"091020"}') == "091020"
    assert parse_hs6("0910.20") == "091020"
    assert parse_hs6("revision 2017 code 0910.20") == "091020"
    assert parse_hs6("441900") == "441900"
    assert parse_hs6("UNKNOWN") is None
    assert parse_hs6("") is None


def test_unsupported_hs_guess_is_dropped_when_sources_disagree():
    sources = "Iran saffron is traded under HS 0910.20."
    assert accept_hs_evidence(
        hypothesis="441900",
        confirmed="091020",
        source_text=sources,
        search_ok=True,
    ) == ("091020", "medium")
    assert accept_hs_evidence(
        hypothesis="441900",
        confirmed="441900",
        source_text=sources,
        search_ok=True,
    ) == (None, "unknown")
    assert accept_hs_evidence(
        hypothesis="441900",
        confirmed=None,
        source_text="",
        search_ok=False,
    ) == ("441900", "low")


def test_router_classify_keeps_a_leading_zero_code(monkeypatch):
    from app.providers.openai_compat import OpenAICompatLLM
    from app.providers.structured_request import StructuredResult

    def fake(self, prompt, schema, **kwargs):
        assert "زعفران" in prompt
        return StructuredResult(ok=False, content="", raw_text="091020", category="malformed", data=None)

    monkeypatch.setattr(OpenAICompatLLM, "complete_structured", fake)
    code, confidence = OpenAICompatLLM(
        "sk-test", "mistralai/mistral-nemo", provider_id="openrouter"
    ).classify_hs("زعفران", None)
    assert code == "091020"
    assert confidence == "low"


def test_conclude_before_search_does_not_finish_the_run():
    class FakeLLM:
        id = "openrouter"
        research_cleared = True
        tokens_used = 0
        output_method = "json_schema"
        seen: list[str] = []

        def decide_research_action(self, context):
            self.tokens_used += 1
            self.seen.append(str(context.get("_correction") or ""))
            return (
                '{"action":"conclude","tool":null,"args":{},"rationale_fa":"طبق قانون ۴ متوقف شد",'
                '"market_proposals":[],"unknowns":[],"conflicts":[]}'
            )

    class Executor:
        def __init__(self):
            self.llm = FakeLLM()
            self.budget = None
            self.calls = 0

        def execute(self, call):
            self.calls += 1
            raise AssertionError(call.tool)

    async def emit(db, run, **kwargs):
        return None

    db = SessionLocal()
    try:
        admin_service.update_safety(
            db,
            {
                "max_consecutive_invalid": 5,
                "max_repeated_actions": 1,
                "max_runtime_seconds": 0,
                "max_run_tokens": 0,
            },
        )
        db.add(Run(id="run_early_stop", product="زعفران", origin_country="ایران", status="running"))
        db.commit()
        from app.agents.decision_loop import run_decision_loop

        executor = Executor()
        result = asyncio.run(
            run_decision_loop(
                db,
                db.get(Run, "run_early_stop"),
                executor,
                emit,
                checkpoint={"version": 2, "completed_steps": ["classify", "memory"], "memory_status": "miss"},
            )
        )
        assert result["markets"] == []
        assert result["stop_reason"] == "MARKET_DISCOVERY_INCOMPLETE"
        assert executor.calls == 0
        assert any("search_web" in note for note in executor.llm.seen)
    finally:
        db.close()
