"""Search observations reach the next decision. Snippets are not verified claims."""

from __future__ import annotations

import asyncio
import json

from app.agents.llm_decide import _DECISION_SCHEMA_HINT
from app.agents.observations import absorb_search_results, context_sources
from app.agents.research_phase import FRUITLESS_SEARCH_FEEDBACK, UNREAD_SOURCE_FEEDBACK
from app.db.session import SessionLocal
from app.evidence.store import claims_for_run
from app.models.entities import Run
from app.services import admin_service
from app.tools.extract import extract_claims
from app.tools.free_web import duckduckgo_html_items, wikipedia_items

PAGE = (
    "صادرات زعفران ایران به امارات در سال ۲۰۲۳ افزایش یافته است و بازار وارداتی این محصول فعال مانده است."
)


def test_prompt_separates_sources_from_verified_claims():
    assert "CONTEXT.sources" in _DECISION_SCHEMA_HINT
    assert "CONTEXT.evidence" in _DECISION_SCHEMA_HINT
    assert "not verified evidence" in _DECISION_SCHEMA_HINT
    assert "save_evidence writes memory only" in _DECISION_SCHEMA_HINT
    assert "fetch_page" in _DECISION_SCHEMA_HINT
    assert "extract_claims" in _DECISION_SCHEMA_HINT


def test_wikipedia_descriptions_become_snippets():
    items = wikipedia_items(
        [
            "saffron",
            ["Saffron"],
            ["Saffron is a spice from the flower of Crocus sativus."],
            ["https://en.wikipedia.org/wiki/Saffron"],
        ],
        lang="en",
    )
    assert items[0]["title"] == "Saffron"
    assert "Crocus" in items[0]["snippet"]
    assert items[0]["url"].startswith("https://")


def test_html_results_keep_snippet_text():
    gap = " " * 900
    html = (
        '<a class="result__a" href="https://example.com/saffron">UAE &amp; saffron</a>'
        + gap
        + '<a class="result__snippet" href="https://example.com/saffron">'
        "Import <b>demand</b> for saffron in the UAE."
        "</a>"
    )
    items = duckduckgo_html_items(html, max_results=3)
    assert items[0]["url"] == "https://example.com/saffron"
    assert items[0]["title"] == "UAE & saffron"
    assert items[0]["snippet"] == "Import demand for saffron in the UAE."


def test_search_observations_are_deduped_and_are_not_claims():
    db = SessionLocal()
    try:
        state: dict = {"urls": [], "observations": []}
        first = absorb_search_results(
            state,
            [
                {
                    "url": "https://example.com/saffron/",
                    "title": "UAE saffron import market",
                    "snippet": "Exports of saffron to the UAE rose.",
                    "publisher": "example.com",
                    "provider": "duckduckgo_html",
                },
                {
                    "url": "https://example.com/bare",
                    "title": "https://example.com/bare",
                    "snippet": "",
                },
            ],
            run_id="run_obs_unit",
            db=db,
        )
        assert first["new_useful"] == 1
        assert first["thin"] == 1
        assert len(state["observations"]) == 2
        assert state["observations"][0]["status"] == "unread"
        assert state["observations"][0]["title"] == "UAE saffron import market"
        assert "UAE" in state["observations"][0]["snippet"]
        again = absorb_search_results(
            state,
            [
                {
                    "url": "https://example.com/saffron",
                    "title": "UAE saffron import market",
                    "snippet": "Exports of saffron to the UAE rose.",
                }
            ],
            run_id="run_obs_unit",
            db=db,
        )
        assert again["new_useful"] == 0
        assert len(state["observations"]) == 2
        shown = context_sources(state["observations"])
        assert shown[0]["id"].startswith("ev_")
        assert shown[0]["status"] == "unread"
        assert claims_for_run(db, "run_obs_unit") == []
    finally:
        db.close()


def test_reworded_searches_without_new_sources_stop():
    queries = ["زعفران بازار صادرات", "saffron export markets", "بازار جهانی زعفران"]

    class FakeLLM:
        id = "openrouter"
        research_cleared = True
        tokens_used = 0
        output_method = "json_schema"
        contexts: list[dict] = []
        step = 0

        def decide_research_action(self, context):
            self.tokens_used += 3
            self.contexts.append(context)
            query = queries[min(self.step, len(queries) - 1)]
            self.step += 1
            return json.dumps(
                {
                    "action": "call_tool",
                    "tool": "search_web",
                    "args": {"query": query},
                    "rationale_fa": "جست‌وجوی دیگر",
                    "market_proposals": [],
                    "unknowns": [],
                    "conflicts": [],
                },
                ensure_ascii=False,
            )

    class Executor:
        def __init__(self):
            self.llm = FakeLLM()
            self.budget = None
            self.calls = 0

        def execute(self, call):
            self.calls += 1

            class Result:
                ok = True
                message_fa = "۸ نتیجه"
                error_code = None
                data = {"results": []}

            return Result()

    events: list[dict] = []

    async def emit(db, run, **kwargs):
        events.append(kwargs)
        return None

    db = SessionLocal()
    try:
        admin_service.update_safety(
            db,
            {
                "max_consecutive_invalid": 5,
                "max_repeated_actions": 10,
                "max_fruitless_searches": 3,
                "max_runtime_seconds": 0,
                "max_run_tokens": 0,
            },
        )
        db.add(Run(id="run_fruitless", product="زعفران", origin_country="ایران", status="running"))
        db.commit()
        from app.agents.decision_loop import run_decision_loop

        executor = Executor()
        result = asyncio.run(
            run_decision_loop(
                db,
                db.get(Run, "run_fruitless"),
                executor,
                emit,
                checkpoint={"version": 2, "completed_steps": ["classify", "memory"], "memory_status": "miss"},
            )
        )
        assert executor.calls == 3
        assert result["stop_reason"] == "NO_NEW_SOURCES"
        assert result["markets"] == []
        assert FRUITLESS_SEARCH_FEEDBACK in executor.llm.contexts[-1].get("_correction", "")
        search_events = [item for item in events if (item.get("payload") or {}).get("event_type") == "research.search_done"]
        assert search_events
        assert "شاهد تأییدشده نیست" in search_events[0]["message_fa"]
        assert search_events[0]["status"] == "running"
        assert all(
            (item.get("payload") or {}).get("event_type") == "research.search_done" for item in search_events
        )
    finally:
        db.close()


def test_search_then_fetch_then_ranked_market():
    class FakeLLM:
        id = "openrouter"
        research_cleared = True
        tokens_used = 0
        output_method = "json_schema"
        contexts: list[dict] = []

        def decide_research_action(self, context):
            self.tokens_used += 11
            self.contexts.append(context)
            if len(self.contexts) == 1:
                return json.dumps(
                    {
                        "action": "call_tool",
                        "tool": "search_web",
                        "args": {"query": "زعفران بازار صادرات"},
                        "rationale_fa": "کشف بازار",
                        "market_proposals": [],
                        "unknowns": [],
                        "conflicts": [],
                    },
                    ensure_ascii=False,
                )
            if len(self.contexts) == 2:
                source = context["sources"][0]
                return json.dumps(
                    {
                        "action": "call_tool",
                        "tool": "fetch_page",
                        "args": {"url": source["url"]},
                        "rationale_fa": "خواندن منبع",
                        "market_proposals": [],
                        "unknowns": [],
                        "conflicts": [],
                    },
                    ensure_ascii=False,
                )
            evidence_id = context["evidence"][0]["claim_id"]
            return json.dumps(
                {
                    "action": "conclude",
                    "tool": None,
                    "args": {},
                    "rationale_fa": "بازار بر اساس ادعا رتبه‌بندی شد",
                    "market_proposals": [
                        {
                            "country_code": "AE",
                            "recommendation": "recommended",
                            "evidence_ids": [evidence_id],
                            "data_scope": "qualitative",
                            "risks": [],
                        }
                    ],
                    "unknowns": [],
                    "conflicts": [],
                },
                ensure_ascii=False,
            )

    class Executor:
        def __init__(self):
            self.llm = FakeLLM()
            self.budget = None
            self.calls = []

        def execute(self, call):
            self.calls.append(call.tool)
            if call.tool == "search_web":
                return _result(
                    {
                        "results": [
                            {
                                "url": "https://example.com/saffron-uae",
                                "title": "UAE saffron import market",
                                "snippet": "Trade notes about saffron imports.",
                                "publisher": "example.com",
                                "provider": "duckduckgo_html",
                            }
                        ]
                    }
                )
            if call.tool == "fetch_page":
                return _result(
                    {
                        "url": call.args["url"],
                        "text": PAGE,
                        "fetched_at": "2026-11-24T00:00:00+00:00",
                    }
                )
            if call.tool == "assess_credibility":
                return _result({"level": "unknown"}, message_fa="اعتبار نامشخص")
            if call.tool == "extract_claims":
                return extract_claims(
                    text=str(call.args.get("text") or ""),
                    url=str(call.args.get("url") or ""),
                    product=str(call.args.get("product") or ""),
                )
            if call.tool == "save_evidence":
                return _result({"knowledge_id": "mem_test"}, message_fa="در حافظه عمومی ذخیره شد.")
            raise AssertionError(call.tool)

    events: list[dict] = []

    async def emit(db, run, **kwargs):
        events.append(kwargs)
        return None

    db = SessionLocal()
    try:
        admin_service.update_safety(
            db,
            {
                "max_consecutive_invalid": 5,
                "max_repeated_actions": 8,
                "max_fruitless_searches": 4,
                "max_runtime_seconds": 0,
                "max_run_tokens": 0,
            },
        )
        db.add(Run(id="run_obs_cycle", product="زعفران", origin_country="ایران", status="running"))
        db.commit()
        from app.agents.decision_loop import run_decision_loop

        executor = Executor()
        result = asyncio.run(
            run_decision_loop(
                db,
                db.get(Run, "run_obs_cycle"),
                executor,
                emit,
                checkpoint={"version": 2, "completed_steps": ["classify", "memory"], "memory_status": "miss"},
            )
        )
        assert "fetch_page" in executor.llm.contexts[0]["allowlisted_tools"]
        assert "extract_claims" in executor.llm.contexts[0]["allowlisted_tools"]
        assert "save_evidence" in executor.llm.contexts[0]["allowlisted_tools"]
        assert executor.llm.contexts[0]["sources"] == []
        assert executor.llm.contexts[0]["evidence"] == []
        discovered = executor.llm.contexts[1]["sources"][0]
        assert discovered["status"] == "unread"
        assert discovered["title"] == "UAE saffron import market"
        assert "saffron" in discovered["snippet"]
        assert discovered["id"].startswith("ev_")
        assert executor.llm.contexts[1]["evidence"] == []
        assert executor.llm.contexts[1]["research_state"]["unread"] == 1
        assert executor.llm.contexts[1]["research_state"]["verified_claims"] == 0
        assert executor.llm.contexts[2]["sources"][0]["status"] == "extracted"
        assert executor.llm.contexts[2]["evidence"]
        assert executor.llm.contexts[2]["research_state"]["verified_claims"] == 1
        assert result["markets"]
        assert result["markets"][0].country_code == "AE"
        assert result["observation_counts"]["verified_claims"] == 1
        assert claims_for_run(db, "run_obs_cycle")
        search_events = [item for item in events if (item.get("payload") or {}).get("event_type") == "research.search_done"]
        page_events = [item for item in events if (item.get("payload") or {}).get("event_type") == "market.evidence_ready"]
        assert "شاهد تأییدشده نیست" in search_events[0]["message_fa"]
        assert page_events[0]["status"] == "running"
        assert "ادعا ذخیره شد" in page_events[0]["message_fa"]
    finally:
        db.close()


def test_conclude_after_unread_sources_is_sent_back_once():
    class FakeLLM:
        id = "openrouter"
        research_cleared = True
        tokens_used = 0
        output_method = "json_object"
        contexts: list[dict] = []

        def decide_research_action(self, context):
            self.tokens_used += 2
            self.contexts.append(context)
            if len(self.contexts) == 1:
                return json.dumps(
                    {
                        "action": "call_tool",
                        "tool": "search_web",
                        "args": {"query": "saffron markets"},
                        "rationale_fa": "جست‌وجو",
                        "market_proposals": [],
                        "unknowns": [],
                        "conflicts": [],
                    },
                    ensure_ascii=False,
                )
            return json.dumps(
                {
                    "action": "conclude",
                    "tool": None,
                    "args": {},
                    "rationale_fa": "همین بس است",
                    "market_proposals": [],
                    "unknowns": [],
                    "conflicts": [],
                },
                ensure_ascii=False,
            )

    class Executor:
        def __init__(self):
            self.llm = FakeLLM()
            self.budget = None
            self.calls = 0

        def execute(self, call):
            self.calls += 1
            return _result(
                {
                    "results": [
                        {
                            "url": "https://example.com/market",
                            "title": "Saffron market note",
                            "snippet": "A short trade note.",
                        }
                    ]
                }
            )

    async def emit(db, run, **kwargs):
        return None

    db = SessionLocal()
    try:
        admin_service.update_safety(
            db,
            {
                "max_consecutive_invalid": 4,
                "max_repeated_actions": 6,
                "max_fruitless_searches": 4,
                "max_runtime_seconds": 0,
                "max_run_tokens": 0,
            },
        )
        db.add(Run(id="run_unread_nudge", product="زعفران", origin_country="ایران", status="running"))
        db.commit()
        from app.agents.decision_loop import run_decision_loop

        executor = Executor()
        result = asyncio.run(
            run_decision_loop(
                db,
                db.get(Run, "run_unread_nudge"),
                executor,
                emit,
                checkpoint={"version": 2, "completed_steps": ["classify", "memory"], "memory_status": "miss"},
            )
        )
        assert executor.calls == 1
        assert result["markets"] == []
        assert result["stop_reason"] == "insufficient_evidence"
        assert UNREAD_SOURCE_FEEDBACK in executor.llm.contexts[-1].get("_correction", "")
        assert len(executor.llm.contexts) == 3
    finally:
        db.close()


class _Result:
    def __init__(self, data, message_fa="انجام شد"):
        self.ok = True
        self.message_fa = message_fa
        self.error_code = None
        self.data = data


def _result(data, message_fa="انجام شد"):
    return _Result(data, message_fa)
