"""Structured output, validation, and operational safety. No live provider calls."""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.agents.decision_schema import validate_decision
from app.agents.loop_safety import operational_stop
from app.db.session import SessionLocal
from app.models.entities import Run
from app.providers.keyed import KeyedGeminiLLM
from app.providers.openai_compat import OpenAICompatLLM
from app.providers.response_norm import extract_json_value, log_call, parse_chat_completion
from app.providers.structured_request import next_method, request_body, select_output_method
from app.services import admin_service

SECRET = "sk-live-secret-should-not-leak"
MODEL = "mistralai/mistral-nemo"


def test_method_selection_uses_endpoint_parameters_not_a_model_list():
    assert select_output_method(["structured_outputs", "tools"]) == "json_schema"
    assert select_output_method(["response_format"]) == "json_object"
    assert select_output_method(["tools"]) == "function"
    assert select_output_method([]) == "prompt"
    from app.providers.structured_request import parameter_rejected

    assert parameter_rejected(404, "No endpoints found that support the requested parameters.")
    assert parameter_rejected(400, "tools are unsupported") is True
    assert parameter_rejected(404, "No such model") is False
    assert next_method("json_schema") == "json_object"
    assert next_method("json_object") == "function"
    assert next_method("function") == "prompt"
    assert next_method("prompt") is None


def test_schema_request_keeps_the_selected_model_and_requires_parameters():
    body = request_body(
        model=MODEL,
        prompt="decide",
        method="json_schema",
        schema={"type": "object"},
        schema_name="nova_decision",
        max_tokens=4096,
    )
    assert body["model"] == MODEL
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["provider"]["require_parameters"] is True
    assert body["plugins"] == [{"id": "response-healing"}]
    assert "json_schema" not in request_body(
        model=MODEL,
        prompt="decide",
        method="prompt",
        schema={"type": "object"},
        schema_name="nova_decision",
        max_tokens=512,
    )


def test_normalization_covers_fences_reasoning_tools_and_embedded_errors():
    assert extract_json_value('```json\n{"ok": true}\n```') == {"ok": True}
    assert extract_json_value('note {"ok": true,}') == {"ok": True}
    reasoned = parse_chat_completion(
        {
            "model": MODEL,
            "provider": "DeepInfra",
            "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7, "cost": 0.001},
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": [
                            {"type": "reasoning", "text": "private chain"},
                            {"type": "text", "text": '{"action":"conclude","tool":null,"args_json":"{}","rationale_fa":"بس","stop_reason":"sufficient","market_proposals":[],"unknowns":[],"conflicts":[]}'},
                        ]
                    },
                }
            ],
        }
    )
    assert "private" not in reasoned.content
    assert reasoned.provider_name == "DeepInfra"
    assert reasoned.cost == 0.001
    tool_call = parse_chat_completion(
        {
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {"function": {"name": "decide", "arguments": '{"action":"conclude","tool":null}'}}
                        ],
                    },
                }
            ]
        }
    )
    assert tool_call.content.startswith("{")
    truncated = parse_chat_completion(
        {"choices": [{"finish_reason": "length", "message": {"content": ""}}]}
    )
    assert truncated.truncated is True
    assert truncated.error_category == "truncated"
    empty = parse_chat_completion({"choices": [{"finish_reason": "stop", "message": {"content": ""}}]})
    assert empty.error_category == "empty"
    embedded = parse_chat_completion({"error": {"message": "bad"}, "choices": []})
    assert embedded.error_category == "provider_error"


def test_validation_does_not_invent_tool_arguments_or_markets():
    action, note = validate_decision({"action": "call_tool", "tool": "search_web", "args": {}})
    assert action is None
    assert "query" in note
    assert "saffron" not in note
    action, note = validate_decision(
        {
            "action": "conclude",
            "tool": None,
            "args_json": "{}",
            "rationale_fa": "شواهد کافی نیست",
            "stop_reason": "insufficient",
            "market_proposals": [],
            "unknowns": [],
            "conflicts": [],
        }
    )
    assert action is not None
    assert action.market_proposals == []
    assert note == ""


def test_unsupported_schema_falls_back_on_the_same_model(monkeypatch):
    seen: list[str] = []

    def fake_request(self, method, path, json_body=None):
        if method == "GET":
            return httpx.Response(
                200,
                json={"data": [{"id": MODEL, "supported_parameters": ["structured_outputs"]}]},
            )
        assert json_body["model"] == MODEL
        seen.append(json_body["response_format"]["type"])
        if json_body["response_format"]["type"] == "json_schema":
            return httpx.Response(400, json={"error": {"message": "response_format is unsupported"}})
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    monkeypatch.setattr(OpenAICompatLLM, "_request", fake_request)
    client = OpenAICompatLLM(SECRET, MODEL, provider_id="openrouter")
    result = client.complete_structured("{}", {"type": "object", "properties": {"ok": {"type": "boolean"}}}, schema_name="basic", purpose="capability-basic")
    assert result.ok is True
    assert result.method == "json_object"
    assert seen == ["json_schema", "json_object"]
    assert SECRET not in str(seen)


def test_length_retry_then_provider_error_and_secret_logging(monkeypatch, caplog):
    calls = {"n": 0}

    def fake_request(self, method, path, json_body=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "length", "message": {"content": ""}}], "usage": {"total_tokens": 9}},
            )
        return httpx.Response(
            200,
            json={"error": {"message": SECRET}, "choices": []},
        )

    monkeypatch.setattr(OpenAICompatLLM, "_request", fake_request)
    client = OpenAICompatLLM(SECRET, MODEL, provider_id="openrouter")
    with caplog.at_level(logging.INFO, logger="nova.llm"):
        result = client.complete_structured("x", None, schema_name="text", purpose="decide", force_method="prompt")
        log_call(model=MODEL, method="prompt", http_status=200, finish_reason="stop", usage={}, truncated=False, category="ok", provider_name="")
    assert calls["n"] == 2
    assert result.category == "provider_error"
    assert SECRET not in result.message_fa
    assert SECRET not in caplog.text


def test_repeated_invalid_responses_stop_without_switching_model():
    class FakeLLM:
        id = "openrouter"
        research_cleared = True
        tokens_used = 0
        output_method = "json_schema"
        model = MODEL

        def decide_research_action(self, context):
            assert context.get("product")
            self.tokens_used += 4
            return "not-json " + SECRET

    class Executor:
        def __init__(self):
            self.llm = FakeLLM()
            self.budget = None
            self.calls = 0

        def execute(self, call):
            self.calls += 1
            raise AssertionError("invalid output must not execute a tool")

    async def emit(db, run, **kwargs):
        return None

    db = SessionLocal()
    try:
        admin_service.update_safety(db, {"max_consecutive_invalid": 2, "max_runtime_seconds": 0, "max_run_tokens": 0})
        db.add(Run(id="run_invalid_json", product="زعفران", origin_country="ایران", status="running"))
        db.commit()
        run = db.get(Run, "run_invalid_json")
        executor = Executor()
        from app.agents.decision_loop import run_decision_loop

        result = asyncio.run(
            run_decision_loop(
                db,
                run,
                executor,
                emit,
                checkpoint={"version": 2, "completed_steps": ["classify", "memory"], "memory_status": "miss"},
            )
        )
        assert result["stop_reason"] == "OPERATIONAL_CONSECUTIVE_INVALID"
        assert result["markets"] == []
        assert executor.calls == 0
        assert executor.llm.model == MODEL
        assert SECRET not in result["plan"]["notes_fa"]
    finally:
        db.close()


def test_repeated_action_stops_and_cancellation_is_recoverable():
    decision = (
        '{"action":"call_tool","tool":"search_web","args":{"query":"saffron UAE"},'
        '"rationale_fa":"جستجو","market_proposals":[],"unknowns":[],"conflicts":[]}'
    )

    class FakeLLM:
        id = "openrouter"
        research_cleared = True
        tokens_used = 0
        output_method = "json_object"

        def decide_research_action(self, context):
            self.tokens_used += 1
            return decision

    class Executor:
        def __init__(self):
            self.llm = FakeLLM()
            self.budget = None
            self.calls = 0

        def execute(self, call):
            self.calls += 1

            class Result:
                ok = True
                message_fa = "نتیجه"
                error_code = None
                data = {"results": []}

            return Result()

    async def emit(db, run, **kwargs):
        return None

    db = SessionLocal()
    try:
        admin_service.update_safety(
            db,
            {
                "max_consecutive_invalid": 3,
                "max_repeated_actions": 2,
                "max_runtime_seconds": 0,
                "max_run_tokens": 0,
            },
        )
        db.add(Run(id="run_repeat", product="زعفران", origin_country="ایران", status="running"))
        db.commit()
        run = db.get(Run, "run_repeat")
        executor = Executor()
        from app.agents.decision_loop import run_decision_loop

        result = asyncio.run(
            run_decision_loop(
                db,
                run,
                executor,
                emit,
                checkpoint={"version": 2, "completed_steps": ["classify", "memory"], "memory_status": "miss"},
            )
        )
        assert result["stop_reason"] == "OPERATIONAL_NO_PROGRESS"
        assert executor.calls == 2
        assert result["markets"] == []

        run.status = "cancelled"
        db.commit()
        cancelled = asyncio.run(
            run_decision_loop(
                db,
                db.get(Run, "run_repeat"),
                Executor(),
                emit,
                checkpoint={"version": 2, "completed_steps": ["classify", "memory"], "memory_status": "miss"},
            )
        )
        assert cancelled["stop_reason"] == "OPERATIONAL_CANCELLED"
    finally:
        db.close()


def test_reasoning_text_is_not_the_decision():
    text, finish = KeyedGeminiLLM._decision_text(
        {
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"thought": True, "text": "hidden reasoning"},
                            {"text": '{"action":"conclude"}'},
                        ]
                    },
                }
            ]
        }
    )
    assert "hidden" not in text
    assert "conclude" in text
    assert finish == "STOP"


def test_operational_stop_distinguishes_limits_from_research_depth():
    assert operational_stop(invalid_streak=3, repeated=0, elapsed_seconds=1, tokens=1, limits={}, cancelled=False) == "consecutive_invalid"
    assert operational_stop(invalid_streak=1, repeated=4, elapsed_seconds=1, tokens=1, limits={"max_repeated_actions": 3}, cancelled=False) == "no_progress"
    assert operational_stop(invalid_streak=0, repeated=0, elapsed_seconds=10, tokens=10, limits={"max_runtime_seconds": 0, "max_run_tokens": 0, "max_consecutive_invalid": 3, "max_repeated_actions": 3}, cancelled=False) is None
