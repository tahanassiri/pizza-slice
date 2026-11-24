"""The live saffron run stopped at 92s because elapsed time was added again on every save."""

from __future__ import annotations

import asyncio
import json

from app.agents.loop_safety import active_elapsed, effective_limits, runtime_stop_message
from app.agents.market_scorer import score_from_evidence_markets
from app.agents.observations import page_read_status, processed_source
from app.agents.research_phase import ALREADY_PROCESSED_FEEDBACK
from app.db.session import SessionLocal
from app.evidence.store import claims_for_run
from app.jobs.durable import claim_task, create_task
from app.models.entities import ResearchTask, Run
from app.services import admin_service
from app.tools.extract import extract_claims, extract_html_tables

WITS_HTML = """
<table>
<tr><th>Reporter</th><th>Partner</th><th>Product code</th><th>Year</th><th>Trade Value (US$ Thousand)</th></tr>
<tr>
<td>Iran</td>
<td><a href="https://wits.worldbank.org/CountryProfile/en/Country/IND">India</a></td>
<td>091020</td>
<td>2024</td>
<td>1,234</td>
</tr>
</table>
"""


def test_repeated_safety_writes_do_not_cross_the_thirty_minute_cap():
    buggy = 0.0
    for _ in range(20):
        buggy += 92
    assert buggy >= 1800
    assert active_elapsed(0, 0, 92) == 92
    assert active_elapsed(92, 1000, 1010) == 102
    message = runtime_stop_message(92, 1800)
    assert "92" in message
    assert "1800" in message
    assert "شواهد و نقطه ادامه حفظ شد" in message


def test_effective_limit_keeps_zero_as_disabled():
    limits = effective_limits({"max_runtime_seconds": 0, "max_run_tokens": None})
    assert limits["max_runtime_seconds"] == 0
    assert limits["max_run_tokens"] == 200_000
    assert limits["max_consecutive_invalid"] == 3


def test_wits_table_keeps_real_cells_and_does_not_invent_numbers():
    extracted = extract_claims(
        text=WITS_HTML,
        url="https://wits.worldbank.org/saffron",
        product="زعفران",
        hs_code="091020",
    )
    assert extracted.data["outcome"] == "extracted"
    claim = extracted.data["claims"][0]
    statement = claim["statement"]
    assert "091020" in statement
    assert "2024" in statement
    assert "1,234" in statement
    assert "India" in statement
    assert "wits.worldbank.org/CountryProfile/en/Country/IND" in statement
    assert "Trade Value (US$ Thousand)" in statement
    assert "9999" not in statement
    assert claim["country"] == "IN"
    assert claim["period"] == "2024"
    assert claim["hs_scope"] == "091020"
    assert claim["confidence"] == "unknown"


def test_page_without_trade_rows_is_irrelevant_and_has_no_invented_claim():
    extracted = extract_claims(
        text="<p>Welcome to the trade site. Choose a dataset.</p>",
        url="https://wits.worldbank.org/",
        product="زعفران",
        hs_code="091020",
    )
    assert extracted.data["claims"] == []
    assert extracted.data["outcome"] == "irrelevant"
    blank = extract_claims(
        text="<table><tr><th>Name</th></tr><tr><td>Overview</td></tr></table>",
        url="https://wits.worldbank.org/overview",
        product="زعفران",
    )
    assert blank.data["claims"] == []
    assert blank.data["table_rows_seen"] == 1
    assert blank.data["outcome"] == "irrelevant"


def test_page_read_status_separates_rejection_from_an_irrelevant_page():
    assert page_read_status(stored=2, raw_claims=2, extract_outcome="extracted") == "extracted"
    assert page_read_status(stored=0, raw_claims=2, extract_outcome="extracted") == "rejected"
    assert page_read_status(stored=0, raw_claims=0, extract_outcome="irrelevant") == "irrelevant"


def test_qualitative_watch_market_is_published_without_a_score():
    markets = score_from_evidence_markets(
        [
            {
                "country_code": "IN",
                "recommendation": "watch",
                "evidence_ids": ["cl_india"],
                "data_scope": "qualitative",
                "risks": [],
            }
        ],
        product="زعفران",
        evidence_index={
            "cl_india": {
                "claim_id": "cl_india",
                "statement": "Partner: India; Product code: 091020; Year: 2024",
                "source_url": "https://wits.worldbank.org/saffron",
                "product": "زعفران",
                "country": "IN",
                "period": "2024",
                "data_scope": "qualitative",
            }
        },
    )
    assert len(markets) == 1
    market = markets[0]
    assert market.country_code == "IN"
    assert market.confidence == "low"
    assert any(item.key == "score_total" and item.value == "نامشخص" for item in market.metrics)
    assert any(item.key == "uncertainty" for item in market.metrics)
    assert any(item.key == "recommendation" and item.value == "watch" for item in market.metrics)
    assert all(item.value != "0.350" for item in market.metrics)


def test_processed_source_is_not_extracted_again_and_the_clock_stays_under_the_cap():
    tables = extract_html_tables(WITS_HTML)

    class FakeLLM:
        id = "openrouter"
        research_cleared = True
        tokens_used = 0
        output_method = "json_schema"
        contexts: list[dict] = []

        def decide_research_action(self, context):
            self.tokens_used += 20
            self.contexts.append(context)
            step = len(self.contexts)
            if step == 1:
                return json.dumps(
                    {
                        "action": "call_tool",
                        "tool": "search_web",
                        "args": {"query": "saffron Iran export 091020"},
                        "rationale_fa": "کشف بازار",
                        "market_proposals": [],
                        "unknowns": [],
                        "conflicts": [],
                    },
                    ensure_ascii=False,
                )
            if step in {2, 3}:
                return json.dumps(
                    {
                        "action": "call_tool",
                        "tool": "fetch_page",
                        "args": {"url": context["sources"][0]["url"]},
                        "rationale_fa": "خواندن WITS",
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
                    "rationale_fa": "بازار کیفی با عدم قطعیت",
                    "market_proposals": [
                        {
                            "country_code": "IN",
                            "recommendation": "watch",
                            "evidence_ids": [evidence_id],
                            "data_scope": "qualitative",
                            "risks": [],
                        }
                    ],
                    "unknowns": ["امتیاز عددی ساخته نشد"],
                    "conflicts": [],
                },
                ensure_ascii=False,
            )

    class Executor:
        def __init__(self):
            self.llm = FakeLLM()
            self.budget = None
            self.calls: list[str] = []

        def execute(self, call):
            self.calls.append(call.tool)
            if call.tool == "search_web":
                return _result(
                    {
                        "results": [
                            {
                                "url": "https://wits.worldbank.org/saffron",
                                "title": "WITS saffron 091020",
                                "snippet": "India import table for HS 091020.",
                                "publisher": "wits.worldbank.org",
                                "provider": "duckduckgo_html",
                            }
                        ]
                    }
                )
            if call.tool == "fetch_page":
                return _result(
                    {
                        "url": call.args["url"],
                        "text": WITS_HTML,
                        "tables": tables,
                        "fetched_at": "2026-11-24T00:00:00+00:00",
                    }
                )
            if call.tool == "assess_credibility":
                return _result({"level": "unknown"})
            if call.tool == "extract_claims":
                return extract_claims(
                    text=str(call.args.get("text") or ""),
                    url=str(call.args.get("url") or ""),
                    product=str(call.args.get("product") or ""),
                    tables=call.args.get("tables"),
                    hs_code=str(call.args.get("hs_code") or "") or None,
                )
            if call.tool == "save_evidence":
                return _result({"knowledge_id": "mem_saffron"})
            raise AssertionError(call.tool)

    events: list[dict] = []

    async def emit(db, run, **kwargs):
        del db, run
        events.append(kwargs)
        return None

    import app.agents.decision_loop as loop

    clock = {"t": 1000.0}
    started = {"at": None}

    def monotonic():
        clock["t"] += 10
        if started["at"] is None:
            started["at"] = clock["t"]
        return clock["t"]

    db = SessionLocal()
    original = loop.time.monotonic
    loop.time.monotonic = monotonic
    try:
        admin_service.update_safety(
            db,
            {
                "max_consecutive_invalid": 5,
                "max_repeated_actions": 6,
                "max_fruitless_searches": 4,
                "max_runtime_seconds": 1800,
                "max_run_tokens": 200000,
            },
        )
        db.add(
            Run(
                id="run_saffron_clock",
                product="زعفران",
                origin_country="ایران",
                guessed_hs_code="091020",
                status="running",
            )
        )
        db.commit()
        executor = Executor()
        checkpoint = {
            "version": 2,
            "completed_steps": ["classify", "memory"],
            "memory_status": "miss",
            "active_seconds": 0,
        }
        task = create_task(
            db,
            run_id="run_saffron_clock",
            stage="market_research",
            checkpoint=checkpoint,
        )
        assert claim_task(db, task.id, "saffron-test") is not None
        result = asyncio.run(
            loop.run_decision_loop(
                db,
                db.get(Run, "run_saffron_clock"),
                executor,
                emit,
                checkpoint=checkpoint,
                task_id=task.id,
                lease_owner="saffron-test",
            )
        )
        span = clock["t"] - started["at"]
        assert result["stop_reason"] != "OPERATIONAL_RUNTIME"
        assert result["active_seconds"] <= span + 1
        assert result["effective_limits"]["max_runtime_seconds"] == 1800
        assert executor.calls.count("extract_claims") == 1
        assert executor.calls.count("fetch_page") == 1
        visible = executor.llm.contexts[2]
        assert visible["evidence"]
        assert "091020" in visible["evidence"][0]["statement"]
        assert "1,234" in visible["evidence"][0]["statement"]
        assert visible["evidence"][0]["claim_id"] in visible["new_evidence_ids"]
        assert visible["sources"][0]["status"] == "extracted"
        assert visible["tool_schema"]["fetch_page"] == {"required": ["url"]}
        assert executor.llm.contexts[0]["tool_schema"]["fetch_page"]["url"] == "http(s) URL"
        assert ALREADY_PROCESSED_FEEDBACK in executor.llm.contexts[3].get("_correction", "")
        assert processed_source(
            {"observations": [{"url": "https://wits.worldbank.org/saffron", "url_key": "https://wits.worldbank.org/saffron", "status": "extracted"}]},
            "https://wits.worldbank.org/saffron",
        )
        assert result["markets"]
        assert result["markets"][0].country_code == "IN"
        assert any(item.key == "uncertainty" for item in result["markets"][0].metrics)
        assert any(item.key == "score_total" and item.value == "نامشخص" for item in result["markets"][0].metrics)
        stored = json.loads(db.get(ResearchTask, task.id).checkpoint_json)
        assert stored["state"]["seen_claim_ids"]
        assert stored["effective_limits"]["max_runtime_seconds"] == 1800
        assert stored["active_seconds"] < 1800
        assert (stored.get("last_stop") or {}).get("code") != "runtime"
        assert claims_for_run(db, "run_saffron_clock")
        start_event = next(item for item in events if (item.get("payload") or {}).get("event_type") == "research.loop_start")
        assert start_event["payload"]["effective_limits"]["max_runtime_seconds"] == 1800
        assert any(
            (item.get("payload") or {}).get("event_type") == "research.source_already_processed" for item in events
        )
    finally:
        loop.time.monotonic = original
        admin_service.update_safety(db, {"max_runtime_seconds": 1800})
        db.close()


class _Result:
    def __init__(self, data, message_fa="انجام شد"):
        self.ok = True
        self.message_fa = message_fa
        self.error_code = None
        self.data = data


def _result(data, message_fa="انجام شد"):
    return _Result(data, message_fa)


def test_runtime_stop_keeps_the_checkpoint_and_names_the_limit():
    import app.agents.decision_loop as loop

    clock = {"t": 0.0}

    def monotonic():
        clock["t"] += 80
        return clock["t"]

    class FakeLLM:
        id = "openrouter"
        research_cleared = True
        tokens_used = 0

        def decide_research_action(self, context):
            del context
            raise AssertionError("the limit was already reached")

    class Executor:
        def __init__(self):
            self.llm = FakeLLM()
            self.budget = None

        def execute(self, call):
            raise AssertionError(call.tool)

    events: list[dict] = []

    async def emit(db, run, **kwargs):
        del db, run
        events.append(kwargs)
        return None

    db = SessionLocal()
    original = loop.time.monotonic
    loop.time.monotonic = monotonic
    try:
        admin_service.update_safety(db, {"max_runtime_seconds": 30, "max_run_tokens": 200000})
        db.add(Run(id="run_saffron_stop", product="زعفران", origin_country="ایران", status="running"))
        db.commit()
        checkpoint = {
            "version": 2,
            "completed_steps": ["classify", "memory"],
            "memory_status": "miss",
            "active_seconds": 0,
            "state": {
                "claims": [{"statement": "India 091020 2024", "source_url": "https://wits.worldbank.org/saffron"}],
                "observations": [],
                "urls": ["https://wits.worldbank.org/saffron"],
            },
        }
        task = create_task(db, run_id="run_saffron_stop", stage="market_research", checkpoint=checkpoint)
        assert claim_task(db, task.id, "saffron-stop") is not None
        result = asyncio.run(
            loop.run_decision_loop(
                db,
                db.get(Run, "run_saffron_stop"),
                Executor(),
                emit,
                checkpoint=checkpoint,
                task_id=task.id,
                lease_owner="saffron-stop",
            )
        )
        assert result["stop_reason"] == "OPERATIONAL_RUNTIME"
        assert result["effective_limits"]["max_runtime_seconds"] == 30
        stored = json.loads(db.get(ResearchTask, task.id).checkpoint_json)
        assert stored["last_stop"]["code"] == "runtime"
        assert stored["last_stop"]["effective_limits"]["max_runtime_seconds"] == 30
        assert stored["state"]["claims"][0]["statement"] == "India 091020 2024"
        assert stored["state"]["urls"] == ["https://wits.worldbank.org/saffron"]
        message = next(item["message_fa"] for item in events if "سقف زمان عملیاتی" in item["message_fa"])
        assert "30" in message
        assert "شواهد و نقطه ادامه حفظ شد" in message
    finally:
        loop.time.monotonic = original
        admin_service.update_safety(db, {"max_runtime_seconds": 1800})
        db.close()
